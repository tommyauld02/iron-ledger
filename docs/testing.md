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

Suites: `sweep` features · `days` date rollover and month/year boundaries · `week` the
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
service worker in the app · `live` the iPhone app's live updates against a
stand-in updater and manifest: what is taken and when, the shell-version and
downgrade guards, a build that failed to start, an updater that never
answers, the manifest Pages publishes, and that the shell's version was raised
if the shell changed · `agecheck` the age check and Ask an agent's
permission, answered as a person would: under 18, 18 or older, an incomplete
check, a relaunch, an existing install with a log, the web build and the
iPhone app; Not now, Allow and ask, Find it again, Tap to estimate,
withdrawing in Settings (one question already on its way), and that no request
reaches the stand-in relay without both answers · `relay` the
relay itself, run in Node against a fake Gemini (exits 77, SKIPPED, with no
Node) · `pwa` the offline shell, served the
way Pages serves it, with the network cut, and what still answers offline · `handoff` safe-area opt-in, all
three wake paths, measured touch targets on a 402x874 phone, and the
no-Claude-and-no-network mode Pages actually runs in · `touch` real touch
events via CDP
including the press-and-hold drag · `mobile` fit and font audit across five
iPhone sizes · plus `commit`, `noclaude`, `yourwords`, `firstrun`, `photo2`,
`taborder`.

**Every suite but `agecheck` opens past the age check.** From b79 the app
asks before anything else, which would stop every suite at the door. Each one
imports `tests/answered.py` first; it adds `window.IRON_LEDGER_ADULT=true` to
every browser context, the app's stand-in for an answer already given, which
it reads only while the log holds no answer of its own. Nothing is written to
the log, so a fixture is exactly what the suite saved. `fakeai.phone()` does
the same for Ask an agent's permission (`IRON_LEDGER_AI`) unless
`allowed=False`. A new suite that opens the app imports `answered` too, or it
will time out on the age check. `darkcheck` measures both screens while hidden,
since none of its pages ever shows them; `agecheck` measures them on screen.

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
- **Tests ran for a while against a stale generated copy** and passed
  everything against an old build. The suites now read `mntl-dt.html`
  directly, so there is nothing to go stale.
