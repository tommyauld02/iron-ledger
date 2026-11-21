# Testing, in detail

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

`hittest` came from the cowork project and asks what the size audit cannot:
when you tap the middle of a control, does the tap reach it, or is something
on top? It scrolls in viewport-sized steps because `elementFromPoint` only
answers inside the viewport, and it ignores a corner clipped by an ordinary
neighbour while flagging one taken by something floating over the layout. It
was print-only as it arrived and now exits non-zero, because a control a tap
cannot reach is a dead button by another name.

**A control that only exists after a press is the blind spot this app keeps
falling into.** Three times now: the finished-day card's contrast, the split
editor's fit, and three naming fields that shipped 23px tall because
`.rt-inline` centres its children and they never stretched. Nothing that walks
the tabs as it finds them will ever paint these. `handoff` now opens every one
of them — meal name, rename a day, add a movement, add a day, add a split —
and measures it for 44px and the 16px iOS-zoom rule.

**`keys` types into every field and scrolls every tab, on two phones (b87).**
The owner: "when new updates drop there seem to be keyboard and scroll bugs
that come back." They came back because only Macros' two boxes were ever typed
into under a keyboard (sweep's *THE KEYBOARD*), and nothing scrolled the other
tabs. Its first run found four that had been shipping: Find in your pantry
vanished while typed in (the dock it sits in hid with the keyboard); the room
under the page sat below the dock, so putting the keyboard away near the foot
of Macros, the checklist, Add movement, Choose gym or Cardio left the dock
hanging over an empty stretch; on a 320px phone the add-a-split row was 379px
wide and zoomed the whole page out; and the set pop-up's Reps went under the
keyboard. For each field in its `FIELDS` list it taps, raises a keyboard (the
same visual-viewport stand-in as sweep's), and wants the field above it,
uncovered, focused and taking what is typed, the page never shorter and never
wider than the phone; then puts the keyboard away and wants the dock at the
bottom, there and at the very end of the page, and the room gone once
scrolled away. It does it again as the iPhone app (no room of the page's own,
the field never hidden with the dock). Then each of `SCREENS` — every tab,
folded and with each box open — is scrolled top to bottom: the dock at the
bottom the whole way, nothing off the side, and the last thing on the page
ending above the dock. On the owner's 402x874 and a 320x568. **A new field or
a new box goes into its lists.** Since b102 it also stands in for shell 1.5's
`KeyboardReset`: a keyboard short with nothing typed in, a field that lets go
of a keyboard that never leaves, and coming back to the app a keyboard short
each ask it once; a field, a select's picker and a zoomed page never do, nor
does a shell without it. And back in the app with the keyboard up and
`innerHeight` shrunk to 106px above it, the dock steps aside.

**`muscles` covers what a movement works and the recovery body map (b88).**
The built-in list, the guesses (narrow rules before broad ones, and a name
with nothing to read left as a question), the question sheet's three-state
taps, Save that says what it did and undoes, Not now / the X / the dim page
keeping nothing, Change starting from the list and winning from then on, by
name and on every day. Then a locked day: the body front and back, the sets
by hand (warm-up out, helping muscle half, a set to failure one and a half),
the colours on the list and on the figure, an unplaced movement named and
then counted once answered, the profile's figure, and the one-time choice
when the profile does not say. `darkcheck` opens the sheet and a locked day
for contrast, and `keys` scrolls a locked day.

**`progress` covers the Progress tab (b90).** Check-ins with a note, a weight
or a photo; the photo shrunk and kept in IndexedDB, never in the log or a
backup, and back after a restart; a day that already has one; Compare side by
side and as a slider; the Log's camera, ring and peek; Remove, Undo and the
photo bin after the next open; a photo this phone does not have; kg; the
iPhone app with and without the Filesystem plugin, against a stand-in bridge
that refuses a missing file as the real plugin does;
and the tabs at 320px. It opens over `http`, because its reloads stand for
the app being closed and opened (see *agecheck* below). The full list is in
`docs/progress.md`.

**`calc` covers the calculator, body fat and the real burn (b107).** Seven
aims and the 1% warning; protein by choice and of the goal weight; carbs and
fat by style, filled by Use, in both calculators; body fat's box and sheet
(the tape in both equations and in cm, the six drawings a sex, the other
ways, Use, Save with where it came from, an impossible number, emptying it,
Undo), lean mass in the working; the real burn on the Log, in the wrap-up and
in the calculator, worked out in Python with the app's arithmetic; the Macros
line (what was eaten, the target to try, Use with Undo, Got it, three weeks
quiet), eating over the target, losing too fast, and quiet for a patchy log,
a target just changed, or holding steady; 44px, 16px and 320px. A good week
has a daily line of its own, so the suite looks for the burn line by what it
says rather than for any line. `darkcheck` measures the profile and each of
body fat's ways in both themes and every accent.

**`burn` covers calories burned (b106).** Day complete's line and what it
stands on (the weight, in lb and in kg), and nothing without a weight or a
clock; each kind of cardio estimate (a name's MET, a walk and a run by their
miles, an incline walk), typed calories winning, the heading's total; a name
the app doesn't know asking how hard, the answer kept for the type, said on
the bar and undone; how hard changed in Change; the by-hand note; Cardio
complete's total and the Calories goal counting estimates; steps from weight
and height, a run's own steps taken out, no height, a height in cm; the
height in Settings; the wrap-up's Burned section; the food target untouched;
and 320px. Its expected numbers are worked out with the app's own arithmetic,
rounded the way `Math.round` rounds (.5 up), not Python's `round`, which goes
to even and once failed it on 322.5.

When you add a suite, end it the way the gates do. A suite that reports FAIL
and exits 0 is a report wearing a test's clothes, and rule 1 quietly stops
meaning anything.

A suite exiting **77** means it could not run at all, which is not the same as
the app being broken. `verify.sh` names those separately at the end and still
exits 0. Nothing uses it at the moment.

**`audit2.py` was deleted rather than repaired.** It read a `MEASURE` snippet
from an `audit.py` that only ever existed in the original author's working
directory, so from the day this repo was seeded it did nothing — and the old
`verify.sh` piped every suite into `tail`, which threw away the exit code, so
the traceback scrolled past looking like an empty section. Its job is done
twice over now: `mobile` and `handoff` measure every control against the 44px
rule and gate on it, and `hittest` checks the tap reaches the control. Two
lessons worth keeping: a helper outside the repo is a suite that only works on
one machine, and a suite whose exit code is discarded is not a test.

Suites: `sweep` features · `days` date rollover and month/year boundaries · `weekwrap`
the day weeks start on and the week wrap-up (b104) · `burn` calories burned
(b106) · `calc` the calculator, body fat and the real burn (b107) · `week` the
planned week split: what each tile says, locking in, logging a day later,
Rest at midnight, a removed split, the pick on opening · `probe` clicks every tappable and asserts something changed · `darkcheck` WCAG
contrast in both themes · `coach` routine
builder and history preservation · `meals` combine/split/take out ·
`estmeal` the estimate-as-one-meal path · `finder` the food finder's contract
from the app's side: no key in the app, only the food and the country sent,
the pantry first, Claude only when the relay is out of reach · `native` the
iPhone app's log in native storage, against a stand-in Capacitor bridge whose
storage outlives the browser: a restart with the WebView wiped, a failed
write and its retry, a log that cannot be read, taps before it is read, no
service worker in the app, and the privacy manifest: bundled by Xcode, its
reasons, and every reasoned API in the shell's and installed plugins' Swift
declared · `live` the iPhone app's live updates against a
stand-in updater and manifest: what is taken and when, the shell-version and
downgrade guards, a build that failed to start, an updater that never
answers, the manifest Pages publishes, and that the shell's version was raised
if the shell changed · `agecheck` the age check and Ask an agent's
permission, answered as a person would: under 18, 18 or older, an incomplete
check, a relaunch, an existing install with a log, the web build and the
iPhone app; Not now, Allow and ask, Find it again, Tap to estimate,
withdrawing in Settings (one question already on its way), and that no request
reaches the stand-in relay without both answers · `profile` the birth date
and the profile it opens: dates that can't be right, *Is that right?*, the
second chance as many times as it takes (a log untouched), nothing to the relay
before both yeses, About you and Your goals saved where the tabs read them,
with Undo, Other's equation, lb and kg, Settings → You and Cancel, the
calculator writing into the profile rather than over it, a birth date changed
to under 18, the Gym and Log goal lines, a restore, native storage · `relay` the
relay itself, run in Node against a fake Gemini (exits 77, SKIPPED, with no
Node) · `pwa` the offline shell, served the
way Pages serves it, with the network cut, and what still answers offline ·
`legal` the Privacy Policy, Support and Terms pages App Store Connect links
to: the deploy copies them, each links to the others and the app, no
`[placeholder]` from the drafts is left, 44px links a press reaches, contrast
and no sideways scroll in both themes, and the worker keeps the app as its
offline copy after they are visited · `handoff` safe-area opt-in, all
three wake paths, measured touch targets on a 402x874 phone, and the
no-Claude-and-no-network mode Pages actually runs in · `touch` real touch
events via CDP
including the press-and-hold drag · `mobile` fit and font audit across five
iPhone sizes · plus `commit`, `noclaude`, `yourwords`, `firstrun`, `photo2`,
`taborder` · `progress` the Progress tab, its photos and the Log's marks.

**Every suite but `agecheck` and `profile` opens past the age check.** From b79 the app
asks before anything else, which would stop every suite at the door. Each one
imports `tests/answered.py` first; it adds `window.IRON_LEDGER_ADULT=true` to
every browser context, the app's stand-in for an answer already given, which
it reads only while the log holds no answer of its own. Nothing is written to
the log, so a fixture is exactly what the suite saved. `fakeai.phone()` does
the same for Ask an agent's permission (`IRON_LEDGER_AI`) unless
`allowed=False`. A new suite that opens the app imports `answered` too, or it
will time out on the age check. `darkcheck` measures both screens while hidden,
since none of its pages ever shows them; `agecheck` measures them on screen.

**A way to log food is reached through the plate (b98).** Macros' three ways
are on the plate's sheet, so a press on `[data-logway]` alone waits for a
button that is not showing. `tests/logways.py` does it the way a person does:
`open_way(p, "numbers")` (only if it is folded), `press(p, "estimate")` (the
plate, then the button, whatever it does), `scan(p)`, and `states(p)` for
which are open. A list of taps (`keys`, `handoff`, `probe`) puts `#plate`
before the way. `tests/gymways.py` is the same idea for the Gym's bar, which
did not move.

**Pantry is opened through the switch (b99).** It is a section of Macros, so
there is no `[data-tab="pantry"]` to press. `tests/rooms.py` opens any tab by
name: `rooms.go(p, "pantry")` presses Macros if the switch is not on screen,
then *Pantry*, and waits until the page has stopped scrolling, because
choosing Pantry brings the list to the top. The suites that walk the tabs by
name (`mobile`, `hittest`, `handoff`, `darkcheck`, `keys`, `probe`) go
through it, so "pantry" is still one of the screens they measure. A list of
taps puts the Macros tab and `[data-fseg="pantry"]` where the Pantry tab was.

**`relay` fakes a model that says nothing, not only one that says no
(2026-11-17).** Its fake Gemini answers per model (`byModel`), and `"hang"`
is a model that never replies until it is told to stop. The checks on the
best list use it for what a status code cannot show: that a silent model
gives the next a head start instead of using the whole wait, that it is told
to stop once there is an answer, and that the lookups after it do not ask it
again. They measure time, so their waits are a few seconds of real clock.

**A run that crosses midnight fails on the clock, not the app.** A suite takes
today's date once, when it starts, and seeds its fixture on that day; the app
re-checks the date as it goes (`checkDayRollover()`). `sweep` runs for about
nine minutes, and a full run started at ten to midnight (b98) had its fixture
become yesterday halfway through: a tap on a row timed out, because the app
had moved on to an empty today. Every check before and after it passed. Run it
again; do not go looking for the bug. `weekwrap` is the one suite immune to
it: its clock is pinned to noon of the day it means, not shifted from real
time, so the run can cross midnight and stay on its day.

**A day carried in storage can reach the page a reload late.** `weekwrap`
first moved its clock by writing the offset to `sessionStorage` and then
reloading. On CI (PR #68, run 44423695727) two of those writes landed one
reload late: the page meant for Dec 9 opened on the day before it (no wrap-up,
an empty title), and the restore after it opened on Dec 9 (Dec 7 stamped where
this week's Monday was expected). The two writes and the reload travel to the
browser separately, with nothing ordering them; it never once lost locally, in
70 tries and under a 6× CPU slowdown. Replaying the old suite with those two
writes moved after their reloads fails exactly CI's two checks with CI's
values. Now each page is opened with its day in its own address
(`mntl-dt.html?day=2026-12-09`, read only by the suite's clock; the app never
reads its address), and `go()` fails a check by name if the page's date is not
the day it meant. A suite that moves the clock passes the day in the address.

**`agecheck` and `profile` open over http, and seed their log once.** They used
to fail now and then on CI with the age check back after a reload (2026-10-29,
2026-10-31; a rerun passed). Opened from `file://`, Chromium sometimes hands a
reloaded page an empty `localStorage` for seconds on end, while the log is safe
and back on the next reload: 7 of 1,320 tries under load, against 0 of 560 over
`http://127.0.0.1`. The fixture's "write it if the key is empty" then wrote the
old log back. So these suites use the address a phone would, and `window.name`
lets the fixture go in once per tab. Zero in 560 is not proof, Safari's engine
was not tried, and answering the age check during such a read would save over
the log, so if this ever appears on `http` treat it as an app bug.

**CI runs Linux, and a platform default is a platform difference.** The
technique box is a native `<select>` made invisible, and it set no colours of
its own. Linux Chromium gave its options a dark-scheme default that measured
4.34:1; Windows gave them something else, so `darkcheck` passed on the owner's
machine and failed in CI — for **b39 and b40 both, which therefore never
deployed**, while the phone sat on b38. Two fixes, both kept: every
`select option` is told its colours outright, so no platform decides how
legible a picker is; and **a push is not done until CI is green and the live
page serves the new `BUILD`** — b39 was pushed without anyone watching, which
is how one failure became two.

**A suite writes to a file, not to CI's log.** On PR #14 every check passed and
the run still went red: `sweep` died printing its ~800 results with
`BlockingIOError: [Errno 11] write could not complete without blocking`. The
log on CI is a pipe, `verify.sh` sends each suite's stderr into it with
`2>&1`, and the Playwright driver sharing it can leave it non-blocking, so a
big enough print fails partway. It passed on the commit before, so it is luck
rather than a broken test. `verify.sh` now sends each suite to a temporary file
and prints that afterwards; a file always blocks.

Two lessons paid for the hard way:

- **A test that measures hidden elements passes while measuring nothing.** A
  touch-target check reported green because no panel was open. Assert the
  elements are on screen before asserting anything about them.
- **A broken expression shows up as text, not as an error.** A patch left
  `: '') + +` in the pantry form: unary plus on the next string, so the
  warning paragraph became the word *NaN* — no exception, no page error, and
  every size and colour check still green. Two pantry checks failed only
  because they happened to look for that paragraph. `mobile` now walks each
  tab's text nodes for `NaN` and `undefined`, node by node, because innerText
  runs *NaN* into the button after it and a word-boundary search then finds
  nothing; it was proven on the broken build before being trusted.
- **A pixel budget is a font test in disguise.** "Folded, the day fits on
  the phone" passed on Windows and failed in CI at 895 of 874: Linux draws the
  same fixture 21px taller, and whether a day fits depends on how much is
  logged anyway. Assert what the feature owns — the folded buttons stay
  small, folding saves most of a screen — with headroom, not an exact fit.
- **A month written into a check is a date bomb.** The fixtures place days
  relative to today, so "five days ago" is September for a while and then is
  not: a special-day check that looked for "Sep" passed for weeks and failed
  in CI on October 6th — CI runs on UTC, so it crossed first. Work out the
  expected date from the fixture's own date.
- **A shell heredoc rewrites backslashes.** Patches passed to Python through
  `<<'EOF'` on this machine arrived with `\b` turned into a backspace
  character, which landed invisibly in the app's source — once in a comment
  for weeks, once in a regular expression where it silently broke the match.
  Write patch scripts to a file and run the file. `sweep` now fails on any
  control character in the source. `sed -i` with a Windows path in the
  replacement does the same damage: `\U`, `\f` and `\a` become case changes
  and control characters.
- **A redraw wipes what a test typed.** The app redraws `#view` whole, so a
  number filled in just before a redraw is gone when its button is pressed.
  `darkcheck` typed a barcode the moment the scanner's field appeared, but
  the sheet asks for the camera then, and in a browser with none the refusal
  redraws it some 400 ms later. Once in a while it fell in the 30 ms
  between typing and Look up, and "a scanned product is not on screen"
  failed with nothing wrong in the app (2026-10-17, Windows). Wait for
  whatever redraws to be done — there, the camera's answer on the sheet —
  before typing, then wait for the result rather than sleeping.
- **A machine types sooner than anything deferred.** `sweep` began failing on
  untouched `main` (b100, 2026-11-16) with different checks on different runs:
  a stray set `85x5` where `185x5` was typed, or a crash at a colour check
  because a set typed as 205 had gone in as 05 and read Short, so there was no
  Beat on the page to measure. A Gym row's box selects what is in it in a
  `setTimeout(0)` after it is focused; Playwright's first key arrives about
  5 ms after its tap, and the timeout ran before it on some runs and after it
  on others (8 of 12 on this Mac, about the same with the page's clock put
  back to the Friday CI passed on, so it was never the date). When it ran
  after, the first digit was selected and the second typed over it. The fault
  was the app's, small as it was: the box is now selected only if it still
  holds what it held when focused, so nothing typed is ever typed over, and
  `sweep` pins it with a digit put in during the same turn as the focus,
  which is ahead of the timeout on any machine (it gave 05 five times in five
  on b100). No person types 5 ms after a tap, so nobody saw this on a phone.
  Two things to keep: when different checks fail on different runs of the
  same code, look for something the app defers and the test does not wait
  for; and a suite that prints only at the end hides everything behind a
  crash, so `sweep` now says each failure as it happens and, if it stops
  early, how far it got.
- **Tests ran for a while against a stale generated copy** and passed
  everything against an old build. The suites now read `mntl-dt.html`
  directly, so there is nothing to go stale.
