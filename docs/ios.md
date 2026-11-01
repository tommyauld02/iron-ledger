# The iPhone app

MNTL D&T in the App Store is the same `mntl-dt.html`, wrapped by
[Capacitor](https://capacitorjs.com) in a small native shell (`ios/`). It is a
wrap, not a rewrite: the HTML file stays the one source of truth,
`./verify.sh` keeps guarding it, and the Pages web app carries on unchanged.
Android comes later as its own track and will sit beside it as `android/`;
nothing here is iPhone-only except the `ios/` folder itself.

## What is where

```
package.json            Capacitor 8.5.3, @capacitor/preferences 8.0.1 and
                        @capgo/capacitor-updater 8.52.1, pinned exactly
capacitor.config.json   app id, the name under the icon, webDir, the updater's settings
tools/make-www.mjs      assembles www/ from mntl-dt.html, fonts/, icons/, vendor/,
                        and the live-update manifest Pages publishes
tools/shell-version.py  the shell's version and its ledger, ios/shell-versions.json
www/                    generated, never committed (the same rule as dist/)
ios/App/                the Xcode project; Swift Package Manager, no CocoaPods
ios/App/App/public/     Capacitor's copy of www/, generated, never committed
ios/ExportOptions.plist how the TestFlight workflow signs and uploads
.github/workflows/testflight.yml   builds on GitHub's Mac and uploads to TestFlight
.github/workflows/ios-build.yml    compiles the app, unsigned, on pull requests
```

`www/` holds `mntl-dt.html` as `index.html`, beside `fonts/`, `icons/`,
`vendor/` and the manifest. Left out on purpose: `sw.js` (the app ships its
own files and never registers a service worker) and `media/` (the b69
walkthrough video, which no longer shows in What's new).

The app's icon is `ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png`,
made by `tools/make-icons.py` with the others. Never hand-draw it.

## Settled once, and why

- **Bundle ID `app.mntldt`.** Permanent once the first build reaches App Store
  Connect. It is the reverse of a domain (`mntldt.app`, which appeared free on
  2026-10-21), which is Apple's convention; buying the domain is not required
  for the ID to work.
- **iPhone only.** `TARGETED_DEVICE_FAMILY = 1`, so there is no iPad review
  and no iPad screenshots. Portrait only, as the web app's manifest says.
- **`ITSAppUsesNonExemptEncryption` is NO.** The app uses only the standard
  HTTPS the system provides (the food finder's relay). Nothing in it bundles
  encryption, which is also one reason the log is not kept in SQLite: the
  community SQLite plugin brings SQLCipher with it. The live-update plugin
  only hashes files (SHA-256, with Apple's own CryptoKit); its optional
  encrypted bundles are not used.
- **The camera** is asked for with words saying what it is for: barcodes and
  labels, read on the phone. iOS stops an app that opens the camera without
  them.
- **The launch screen** is a plain background in the phone's light or dark,
  not Capacitor's logo.
- **`capacitor://localhost`** is the app's address on iPhone (Capacitor's
  default), and it is in the relay's `ALLOWED_ORIGINS`. Without it the relay
  answers 403, Ask an agent says it cannot reach the food finder, and the
  pantry, barcodes and label reading all still work.

## The log lives in native storage

How and why is in `docs/architecture.md` (*In the iPhone app the log lives in
native storage*). In short: `@capacitor/preferences` (UserDefaults on iOS)
under the same key, `iron-ledger-v1`, with `save()` and `saveError` keeping
their promise that a failed write never looks like a successful one.
`tests/native.py` proves it with a stand-in for Capacitor's bridge.

## How an update reaches phones

There are two ways, and neither needs the MacBook.

| What changed | How it ships | Reaches phones |
|---|---|---|
| `mntl-dt.html` (fixes, wording, layout, new screens for logging food and training) | **Live update**: merge to `main`, as for the web app | On the next cold start after the phone has fetched it, usually the same day |
| Anything in the shell: a plugin, a permission, the icon or name, `ios/`, `capacitor.config.json`, `package.json` dependencies | **Store build**: run *Build for TestFlight*, then submit in App Store Connect | TestFlight in about 15 minutes; the App Store after review, usually a day |

### Live updates

Every Pages deploy also publishes `live/manifest.json`
(`tools/make-www.mjs --manifest`, run by `pages.yml`): the BUILD, the shell
version it needs (`minNative`), and every file the app ships with its SHA-256
and its address on Pages. In the app:

1. On opening, and on coming back to it (at most every half hour), the app
   reads the manifest.
2. A newer BUILD made for this phone's shell is downloaded in the background
   by `@capgo/capacitor-updater`. Every file is checked against its hash; a file
   unchanged since the store build is copied out of the app instead of
   downloaded, so usually only the HTML file comes down. A file that fails its
   hash fails the whole download, which is tried again later.
3. The app says *"Update b79 opens next time you start the app"*.
4. At the next **cold start** (after the app was swiped away, or iOS closed
   it), before anything is drawn, the app switches to it. Never while in use,
   not even on coming back from the background, because a reload then would
   lose the rest timer and anything half typed. This is why the plugin's own
   `next()` is never used: it swaps the moment the app goes to the background.
5. The new build starts and tells the plugin it is ready. The header shows its
   number (`b79`) and What's new lists what changed, the same as on the web.
   A build that does not get that far within 10 seconds is rolled back by the
   plugin to the one before, and the app never tries that build again.
   The age check (b79) does not hold this up: the app says it is ready
   while the check is still on screen, since the build has started.

How the app decides is in `mntl-dt.html` (*live updates*), and
`tests/live.py` checks every rule with a stand-in for the plugin and the
manifest.

**Privacy.** The plugin is set to never contact Capgo: `updateUrl`,
`channelUrl` and `statsUrl` are empty in `capacitor.config.json`, so it sends
no statistics and no device ID anywhere. The only requests are the manifest and
the files, from GitHub Pages, the same host as the web app. No log data goes
with them. The privacy policy should still say the app checks GitHub Pages for
updates.

**A bad live update reaches every phone fast.** The rollback only catches a
build that fails to start. A build that starts but has a bug is fixed by
shipping the fix the same way, with a new BUILD. `./verify.sh` gates every
Pages deploy, so it gates every live update too.

### What must go through a store build

Apple allows web code downloaded later only if it does not change the app's
primary purpose or add features that do not fit what was reviewed (App Review
Guideline 2.5.2, and the interpreted-code section of the Apple Developer
Program License Agreement). Fixes and improvements to logging food and
training are within that. These always go through review instead:

- a new plugin or any native code, so any change under `ios/`, to
  `capacitor.config.json`, or to `package.json`'s dependencies
- a new permission (camera, notifications, Health, location)
- the icon, the name, the launch screen
- a new purpose: ads, accounts, payments, anything a reviewer would see as a
  different app

**The shell's version keeps this honest.** Each live update says which shell
it needs (`MARKETING_VERSION` in the Xcode project, the one place the version
is set), and a phone with an older shell ignores it. Phones on the older shell
keep the last build made for them until the store update reaches them.
`tools/shell-version.py` fingerprints the shell, and `tests/live.py` fails if
the shell has changed while the version has not. So after changing the shell:

1. In Xcode, raise **Version** (General tab) for the App target, e.g. 1.0 → 1.1.
   That sets `MARKETING_VERSION` in both configurations. (Or edit both lines of
   `project.pbxproj`.)
2. Record it:
   ```bash
   python tools/shell-version.py --record
   ```
3. Commit both, merge, and run *Build for TestFlight*.

### Store builds from GitHub: Build for TestFlight

`.github/workflows/testflight.yml` runs on GitHub's Mac (macOS 26, Xcode 26.6).
Start it from the GitHub app (**Actions → Build for TestFlight → Run
workflow**) or from a terminal:

```bash
gh workflow run testflight.yml
```

- It builds `main` only, and only after `./verify.sh` passes on that commit in
  the same run.
- The version is `MARKETING_VERSION`; the build number is the workflow's run
  number, which only goes up, as App Store Connect requires.
- It signs automatically. Apple keeps the distribution certificate (cloud
  signing), so no certificate or profile is in the repo or its secrets.
- It uploads straight to App Store Connect. The build shows in TestFlight once
  Apple has processed it, usually 5 to 15 minutes. The encryption question is
  already answered by the app (`ITSAppUsesNonExemptEncryption` is NO).

It needs three repository secrets, from one App Store Connect API key with
the **Admin** role (cloud signing needs it):

| Secret | What goes in it |
|---|---|
| `ASC_KEY_ID` | the key's ID, 10 characters |
| `ASC_ISSUER_ID` | the Issuer ID shown above the list of keys |
| `ASC_KEY_P8` | the whole text of the downloaded `AuthKey_<ID>.p8` file, including its BEGIN and END lines |

The workflow writes the key to a temporary file for the length of the build,
never prints it, and deletes it however the job ends. Agents never create or
handle the key; Tommy makes it at App Store Connect → Users and Access →
Integrations → App Store Connect API, and pastes the three values at GitHub →
the repo → Settings → Secrets and variables → Actions.

**A pasted key rarely arrives byte for byte.** The first two uploads (b78)
failed with `Invalid authentication key credential specified
(CryptoKit.CryptoKitASN1Error.invalidPEMDocument)`. That is Apple's tools
refusing the key's *shape*, not the key: GitHub's web form sends line breaks as
CRLF, and an editor can indent the lines, fold them onto one, or turn the
dashes into long ones. A third (b78, run 40786069915) passed all of that and
still failed: Apple's PEM reader wants the body in lines of exactly 64
characters, and a re-wrapped paste has other lengths. So the workflow no longer
repairs the paste; it takes the body alone (whatever the line breaks, spaces or
dashes on the BEGIN/END lines), writes a fresh file with exact BEGIN/END lines
and 64-character lines, and asks `openssl pkey` to read it. It stops with a
plain error, before xcodebuild, if BEGIN/END is missing, a character no key
contains is in the body, or openssl cannot read the result (a character lost or
changed). Most reliable of all is to skip pasting:
`gh secret set ASC_KEY_P8 --repo tommyauld02/iron-ledger < AuthKey_<ID>.p8`.

`.github/workflows/ios-build.yml` also compiles the app, unsigned and with no
secrets, on every pull request that touches the shell, so a change that would
not build is caught before it is merged.

## Running it on your iPhone (Tommy, on the MacBook)

Once, to set up the Mac:

1. Install **Xcode** from the Mac App Store and open it once, letting it
   install its extra components. Then install Node.js 24 from
   https://nodejs.org (the LTS download).
2. In Xcode: **Xcode → Settings → Accounts → +**, choose **Apple ID**, and
   sign in with the Apple ID you enrolled in the Developer Program with. Your
   team shows as *Tommy Auld (Individual)*. This step is yours: agents never
   sign in or handle certificates.
3. On the iPhone: **Settings → Privacy & Security → Developer Mode → On**, and
   restart the phone when it asks. (The switch only appears after the phone
   has been plugged into a Mac running Xcode once — if it is missing, do step
   6 first, then come back.)

Each time you want the current build on the phone:

4. Open **Terminal** and get the code:
   ```bash
   git clone https://github.com/tommyauld02/iron-ledger.git
   cd iron-ledger
   ```
   (Already cloned? `cd iron-ledger` and `git pull` instead.)

   Until pull request #35 is merged, `ios/` exists only on its branch, so
   check that out too (with `git fetch` first in a clone you already had):
   ```bash
   git checkout claude/ios-wrap-native-storage
   ```
   Once it is merged, `main` has everything and this step goes.
5. Install the pieces and copy the app into the shell, then open Xcode:
   ```bash
   npm install
   npm run sync
   npm run open
   ```
6. Plug the iPhone in with a cable and tap **Trust** on the phone if asked.
7. In Xcode, click **App** at the top of the left sidebar, then the **App**
   target, then **Signing & Capabilities**. Tick **Automatically manage
   signing** and choose your team. The Bundle Identifier must read
   `app.mntldt`. Automatic signing registers the `app.mntldt` App ID with
   Apple for you, so there is nothing to create by hand at
   developer.apple.com. Your team (ID `HKA266QX4X`) is committed in the
   project, so Xcode has nothing to write here. If a clone from before that
   shows the project file as modified, discard Xcode's copy before pulling:
   ```bash
   git restore ios/App/App.xcodeproj/project.pbxproj
   ```
8. At the top of the window, pick your iPhone from the device menu (next to
   the ▶ button), then press **▶**. The first build fetches Capacitor itself,
   which takes a few minutes.
9. If the phone says *Untrusted Developer*: **Settings → General → VPN &
   Device Management**, tap your Apple ID, then **Trust**. Press ▶ again.

## What to check on the phone

The suites run the app as a phone, but not as *this* app on *this* phone.
These are the things only the iPhone can answer:

1. It opens to the welcome, with the MNTL D&T icon and name on the home screen.
2. Log a food and a set. Swipe the app away from the app switcher, open it
   again: both are still there.
3. Restart the phone, open the app: still there. This is UserDefaults
   surviving a reboot, which no test on a PC can show.
4. Settings → turn on Dark. The status bar and the tab bar match.
5. Scan a barcode (allow the camera when asked) and read a label from the
   pantry's *+ New*. Both read on the phone with no signal.
6. Backup → *Send a copy*: the share sheet opens with an `mntl-dt-<date>.json`
   file.
7. Ask an agent with a connection: it asks permission, then answers.
8. Type in any box: the keyboard does not cover it, and the page does not
   zoom.

Anything that looks wrong: a screenshot and the build number from the
header (`b77`) is enough to start from.
