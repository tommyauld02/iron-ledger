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
`iron-ledger-<date>.json` file (Files, Notes, AirDrop to a laptop) rather than
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

**Rendering is a full redraw into `#view`, wrapped in try/catch.** Handlers are
delegated on `#view` and the tab bar, which are never replaced — an earlier
version wired handlers sequentially after a long render, so one throw left
every later button dead and silent. If `render()` throws on the Macros tab, a
plain fallback view still lets you log.

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
`iron-ledger.html`; never hand-edit either.

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
