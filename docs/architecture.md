# Architecture: storage, backup, undo, dates and the offline shell

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**Storage is localStorage first.** That is the only store that works from a
phone home screen, where the page is served top-level and every Claude
capability resolves `null`. `db` is an opportunistic mirror when the app is
opened inside Claude, never a dependency. Backup/restore is copyable JSON,
and the Backup panel shows the build number and the last captured JS error —
that pair has turned an unreproducible bug into a five-minute fix twice.

**A failed write must never look like a successful one.** `save()` returns a
boolean and sets `saveError`; it used to be `catch (e) { /* quota */ }`, which
meant the app rendered the row, printed "✓ Added" and lost the entry on the
next load. Every caller that claims success — the add-food flash, the Add
button, the pantry `+` tick — is gated on that boolean, and while writes are
failing the `#savebar` says so until one succeeds. The reason is also written
into `lastError`, so the Backup panel names it. Storage being full is only one
trigger: the same path fires in private browsing and under iOS storage
pressure, which arrive long before the quota does.

**In the iPhone app the log lives in native storage.** Inside the Capacitor
shell (`docs/ios.md`) a WebView's localStorage is website data to iOS, which
may clear it when the phone runs low on space — and this log has no second
copy. So when `NATIVE` is true, `readLog()` and `writeLog()` go to
`@capacitor/preferences` (UserDefaults on iOS, SharedPreferences on Android)
under the same key, `iron-ledger-v1`, through
`Capacitor.nativePromise("Preferences", …)`, which the bridge provides with no
JavaScript bundled. On the web they are localStorage, exactly as before, and
the web build never touches the bridge. Preferences over SQLite because the
log is one JSON document under one key, which is a key-value store's whole
job; it is Capacitor's own plugin, released with it; and the community SQLite
plugin brings SQLCipher, an encryption library that would muddy the App
Store's export-compliance answer. At about 1.1 KB a day the log stays a few
megabytes for years, well within what UserDefaults holds; revisit if it ever
grows to tens of megabytes. `@capacitor/preferences` has no 5 MB ceiling,
unlike localStorage.

Native storage answers later and `save()` must answer now, which is why this
needs care. Startup waits: `openLog()` reads the log before `load()` and the
first render, and on the web runs them at once, so startup there is
unchanged. Until the log has been read, `writeLog()` refuses — a tap in that
moment would otherwise write an empty log over the real one — and if it
cannot be read at all, nothing is written for the whole session and the save
bar says the log could not be opened. Every write is sent the moment it is
made; the bridge runs plugin calls one after another, so the last write sent
is the last one kept. A write that fails comes back a moment later, possibly
after its own change said "✓ Added": that ✓ is taken back (`lastAdded`
cleared and redrawn), the bar goes up, `save()` returns false until a write
lands, and the newest log is sent again every five seconds. Every write is the
whole log, so the one that lands keeps everything before it. The one thing
that can still read wrong is the other way round: while writes are failing, a
change whose own write then lands says "Not saved" — the safe direction. A first open with nothing in native storage carries across a
log left in the WebView's own localStorage before writing anything. The look
key, `iron-ledger-look`, stays in localStorage: it is only the pre-paint
script's copy of `store.theme` and `store.accent`. `tests/native.py` covers
each of these against a stand-in bridge whose storage survives the browser.

**Nothing expires, and there is no cap.** No pruning, no cutoff, no bound on
the date or year arrows — `store.days` keeps every day forever. A fully logged
day costs about 1.1 KB, so a 5 MB origin holds roughly 4,700 days, about
thirteen years. Capacity is not the constraint; the write path is.

**On a phone there is no second copy.** `db` only exists inside the Claude
viewer, so on the Pages build `queueSync()` returns immediately and
localStorage is the only place the log lives. Nothing else notices if it goes.
The app therefore records `store.lastBackupAt` whenever a copy actually
reaches the clipboard, and after 14 days — or if no copy has ever been taken —
the header Backup button carries a dot and the panel says how long it has
been. The dot uses the accent, not `--miss`: nothing is broken, there is just
something worth doing. `lastBackupAt` is deliberately **not** merged on
restore, because a phone you have just restored onto has not taken a copy of
its own and should still be asked for one.

**Getting a copy off the phone is one tap where the phone allows it.** Copying
is three steps on a phone — copy, leave the app, find somewhere to paste — and
the backup is the only net under a week of logging. Where `navigator.share`
exists the sheet offers *Send a copy*, which hands over a real
`mntl-dt-<date>.json` file (`iron-ledger-<date>.json` before b74) (Files, Notes, AirDrop to a laptop) rather than
a wall of text. Copy stays, drops to `.ghost`, and is the only path where
sharing is not available; `saveWord()` keeps the instructions naming the button
that is actually on screen.

It is counted as a backup on the **same rule as Copy: only when it completed**.
Backing out of the share sheet rejects with `AbortError` and must not touch
`lastBackupAt` — recording a copy that was never taken is the same class of lie
as a failed write reporting success, and here it would silence the one nudge
that protects the log. `navigator.canShare({files})` is probed because a phone
without file sharing still takes the text.

**What's new: once, after an update.** Asked for by the owner. `NEWS` in the
app lists each build's changes in plain words, newest first. The build that
last saved this phone's data is read **before** startup stamps the current one
(`prevBuild`), and every entry newer than it is shown — four at most — with
*Got it*. Because the stamp happens on the same open, it shows once. A phone
with no `build` at all is opening the app for the first time, gets the welcome
instead, and is not told what changed. **Add a `NEWS` entry with every build
that changes something a person would notice**, written the way the owner
talks about the app, not the way the code does. `darkcheck`'s fixture carries
an older build so the pop-up is measured, and `sweep` checks once-only, the
cap and the first-open case. `darkcheck` dismisses the welcome by its own id:
`text=Got it` matched What's new's button too and closed it before it could be
measured.

**b69's walkthrough video is a one-off.** The redesign changed every screen, so
the owner recorded a walkthrough (`media/new-look-walkthrough.mp4`, phone screen
with their face in a corner) and asked for it this once; later builds go back
to words only. An entry carries `video`, `poster` and `vnote`. It plays inline
with `preload="none"`, so nothing downloads until it is tapped, and closing the
sheet pauses it, because a hidden sheet keeps playing. It is left out where it
cannot play: the artifact copy (no manifest, no `media/`) and offline, which
get the words. `sw.js` passes `/media/` straight to the network, since Safari
asks for video in byte ranges that a cached whole file cannot answer, and
`pages.yml` copies `media/`. Once that entry has aged out of the four shown,
the file and the `video` branch in `showNews()` can go.

**Rendering is a full redraw into `#view`, wrapped in try/catch.** Handlers are
delegated on `#view` and the tab bar, which are never replaced — an earlier
version wired handlers sequentially after a long render, so one throw left
every later button dead and silent. If `render()` throws on the Macros tab, a
plain fallback view still lets you log.

**The age check comes before anything else (b79).** Gemini's terms are for
adults, so the whole app is 18+ (decided 2026-10-28). `startUp()` reads the
log and applies the look, then either opens the app (`openApp()`: the build
stamp, the first render, What's new) or shows the age check over everything,
with `.app` inert, and opens the app only for someone 18 or older. Until then
nothing is drawn and nothing is saved, so closing the app on that screen asks
again next time. A phone that had the app before b79 is asked once, and its
What's new waits behind the check. A no is kept, so the sorry screen comes
back on every open; a log already on the phone is left exactly as it was.
`liveReady()` is called either way: the build has started, and the live
updater rolls back a build that stays quiet for 10 seconds. The answers live
in the log as `store.consent` — `adult`, `ai`, `aiAt` (when Ask an agent was
allowed), `terms` and `termsAt`, nothing else — under the same key. Like
`lastBackupAt`, `mergeInto()` does not carry them across a restore: they were
answered on this phone.

**It asks for a birth date, and gives a second chance (b81).** b79's two
buttons meant one wrong tap on *I'm under 18* shut a phone out for good, and
the only way back was clearing the app, log and all. Tommy chose the birth
date as the fix (2026-10-28): month by name, day and year (`dobFrom()` says
what is wrong with one that can't be right). A date under 18 is said back
first, *Is that right?* (`#ageCheck`), with *Change the date* keeping it to
fix; *Yes, that's right* keeps the no and drops anything given before (Ask an
agent's yes, the Terms, a birth date) and calls back a question on its way to
the relay. The sorry screen has *Wrong birth date? Enter it again*, from empty,
as many times as it takes — Tommy's call; the check is self-declared either
way, and a limit would be the dead end again. An adult's birth date is kept in
the profile (`store.profile.dob`), never in `consent`; under 18 only the no is
kept, no date. A first yes goes on to the profile, with What's new behind it.

**The profile sets the goals (b81).** Asked for by Tommy (2026-10-28) as a
"log in": a local account on this phone, with no server (accounts that share
and follow come later, with one). `showProfile()` draws it into `#profGate`,
the age check's card on its own ground: after a first yes, *About you* then
*Your goals*, each skippable, and from Settings → You both on one page with
Save and Cancel. `store.profile` is the person — `name`, `dob`, `sex` (`m`, `f`
or `o`, and for `o`, `calcSex`, the equation the calculator uses), height (`cm`,
or `ft` and `inch`), `act`, `aim`, `setup`. The goals are not copied into it:
they stay where the tabs already read them (`store.goal`, `waterOn` and
`waterGoalMl`, `cardioGoal`), with two new ones beside them, `gymGoal`
(workouts a week, under the week board on Gym) and `bwGoal` (a goal weight in
pounds, beside the trend on Log). So the target editor, Settings and the
Cardio tab change the same goals, and the profile always opens on the ones in
force. Calories and protein apply from today on, as *Save target* does; the
weight box is the body weight card's number, so a changed one is today's
weigh-in. The goal calculator's arithmetic is `calcNumbers()`, shared by both,
and its *Use these numbers* writes into the profile, never over it. One Save is
one Undo. A birth date changed to under 18 goes to the age check, said back
first. `mergeInto()` brings the profile and the two new goals back, but keeps
this phone's birth date: it came with this phone's age check.

**The yes to the age check is the yes to the Terms (b80).** The screen says
*By tapping Continue, you agree to the Terms of Use*, so a birth date of 18 or
older records `terms`, the version agreed to (`TERMS`, the effective date of the Terms as
published), and `termsAt`, when — what shows someone agreed, and Settings →
About shows the date. The Terms (section 13) promise that a significant change
is agreed to again, so changing `TERMS` asks every adult once, on the next
open, with `#termsAsk` (*The Terms of Use have changed*, one *I agree*, the
links) before the app opens. Change it for a significant change only, and
publish the new Terms first. A b79 yes has no version and counts as
`TERMS_FIRST`; it shows no date rather than a made-up one.

**`TERMS_FIRST` is older than the Terms as published, on purpose.** b79 to b81
asked people to agree while the links to the Terms led to a 404, so those
yeses are asked once more at b82, now there is something to read. `TERMS` is
the Terms' effective date, and `legal` fails if the page says otherwise.

**Days are judged against the goal in force when they were logged.**
`stampGoal()` snapshots it, so changing your target today never rewrites last
month's calendar.

**The app is installed, not just bookmarked.** `manifest.webmanifest` and
`sw.js` make it a real PWA: standalone display, home-screen icon, and an
offline shell. The service worker is **network-first for documents** and
cache-first for fonts and icons. That direction is deliberate and is the fix
for the iOS-serves-an-old-build problem this project kept hitting — online you
always get the current build, offline the cache answers. The worker reads its
version from its own `?v=` query, which the app sets from `BUILD`, so there is
no second version to bump.

**Only the app's own document is cached as the app.** The Privacy Policy,
Support and Terms pages (`privacy.html`, `support.html`, `terms.html`, copied
to the site by `pages.yml` and linked from App Store Connect) sit in the
worker's scope too. Before they existed, every page navigation was saved as
`./`, so one visit to the privacy policy would have made it what the app
opened offline. The worker now leaves any navigation that is not the scope
root or `index.html` to the network, and `legal` visits all three pages,
cuts the network and checks the app still opens. The pages carry their own
copy of the colour tokens and fonts, and follow `iron-ledger-look`, so a
phone set to dark in the app gets them dark.

Inside the iPhone app there is no service worker at all: the app ships its
own files, and on Android it would be served over https, which the protocol
test alone would let through, so registration also checks `!NATIVE`.

Registration is gated on the app's own `<link rel="manifest">`, not on the
protocol. Artifacts are https too, so a protocol test would send them chasing a
`sw.js` that isn't there and write a phantom error into the Backup panel;
`build.sh` strips the manifest link from both artifact copies, so they never
register.

**Fonts are self-hosted.** Google Fonts was the only outbound reference in the
whole file and there are no `fetch` calls anywhere, so removing it made the app
genuinely offline. Archivo is a variable font on two axes — one file per
subset spans weight 400–800 and width 100–125% — because the redesign's big
numbers are set at 800 and 125%, and a browser can fake a weight but never a
width. Do not re-add per-weight Archivo files. IBM Plex Mono is static, one
per weight. Latin and latin-ext only. `tools/make-fonts.py` regenerates
`fonts/` and prints the `@font-face` block that sits at the top of
`mntl-dt.html`; never hand-edit either.

**Dates re-check on wake.** iOS suspends a home-screen app rather than closing
it, so `TODAY` computed once at load meant food logged after midnight landed on
yesterday. `checkDayRollover()` runs on visibilitychange, focus and pageshow.

**Undo walks back, one press at a time, until the run ends.** Found using b45:
sorting several foods, only the last could be taken back, and only for nine
seconds. `offerUndo()` now pushes onto `undoStack`; the bar shows the newest,
Undo takes it back, and the bar moves on to the one before. Only a change that
cannot be undone — a set logged, a food added or saved — ends the run, and it
does not time out. Looking is not a change: the bar belongs to the screen the
run was made on (`screenKey()`, tab and day), so another tab hides it and
coming back brings it back, which is what someone who checks the calendar and
returns to undo expects — `sweep` and `share` both do exactly that. An undoable
change made on another screen starts a new run there. A notice from `notify()`
still goes after nine seconds, and hands the bar back to whatever can still be
undone on the screen showing.

The rule that ends a run is also what makes it safe. Every restore expects the
world exactly as its own change left it. Because anything that cannot be
undone ends the run, the stack only ever holds changes made one straight after
another, and taking them back newest first gives each restore precisely that
world. It is detected per tap: `save()` calls `noteSave()`, which looks, once
the tap's work is finished, for an `offerUndo()` made during the same tap; if
there was none, the change was not undoable and the run is over. A restore's
own `save()` is exempt (`undoing`). Every call site saves first and offers
second, in the same handler — keep it that way, or its own save ends its run.
