# The iPhone app

MNTL D&T in the App Store is the same `mntl-dt.html`, wrapped by
[Capacitor](https://capacitorjs.com) in a small native shell (`ios/`). It is a
wrap, not a rewrite: the HTML file stays the one source of truth,
`./verify.sh` keeps guarding it, and the Pages web app carries on unchanged.
Android comes later as its own track and will sit beside it as `android/`;
nothing here is iPhone-only except the `ios/` folder itself.

## What is where

```
package.json            Capacitor 8.5.3 and @capacitor/preferences 8.0.1, pinned exactly
capacitor.config.json   app id, the name under the icon, webDir
tools/make-www.mjs      assembles www/ from mntl-dt.html, fonts/, icons/, vendor/
www/                    generated, never committed (the same rule as dist/)
ios/App/                the Xcode project; Swift Package Manager, no CocoaPods
ios/App/App/public/     Capacitor's copy of www/, generated, never committed
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
  community SQLite plugin brings SQLCipher with it.
- **The camera** is asked for with words saying what it is for: barcodes and
  labels, read on the phone. iOS stops an app that opens the camera without
  them.
- **The launch screen** is a plain background in the phone's light or dark,
  not Capacitor's logo.
- **`capacitor://localhost`** is the app's address on iPhone (Capacitor's
  default). The relay will need it in `ALLOWED_ORIGINS` before the food finder
  answers inside the app — a later step of the launch plan. Until then, Ask an
  agent says it cannot reach the food finder, and the pantry, barcodes and
  label reading all still work.

## The log lives in native storage

How and why is in `docs/architecture.md` (*In the iPhone app the log lives in
native storage*). In short: `@capacitor/preferences` (UserDefaults on iOS)
under the same key, `iron-ledger-v1`, with `save()` and `saveError` keeping
their promise that a failed write never looks like a successful one.
`tests/native.py` proves it with a stand-in for Capacitor's bridge.

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
   developer.apple.com.
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
7. Ask an agent with a connection: it says it cannot reach the food finder.
   That is expected until the relay knows the app's address.
8. Type in any box: the keyboard does not cover it, and the page does not
   zoom.

Anything that looks wrong: a screenshot and the build number from the
header (`b77`) is enough to start from.
