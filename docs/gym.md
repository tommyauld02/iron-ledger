# The Gym tab

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**The workout clock is a timestamp, not a counter.** `d.workoutStart` is when
you pressed Start; the elapsed time is always `now - workoutStart`, computed
fresh. Nothing counts up in a variable, which is the whole point — iOS suspends
the app the moment you put the phone in your pocket, and a counter would come
back reading two minutes for a ninety minute session. `d.workoutMs` is what has
been banked, and the two **add**, so a second session on the same day tops up
the first rather than replacing it.

The clock sits **above** *Today's split*, not below it. It is the first thing
you touch walking in and the last before you leave; it should not be something
you scroll to find.

*Lock in the day* is what stops it: `lockDay` calls `stopWorkout(d)` before
anything else, so the number the card shows is the number that gets stored. The
running clock is redrawn by a `setInterval` that writes into `#workoutClock`
directly rather than calling `render()` — a full redraw once a second would
fight anything being typed into a weight field. One interval, cleared and
restarted on every draw, and it clears itself if the element it writes to is
gone.

Discard exists because a mis-tap at nine in the morning otherwise becomes a six
hour session, and it goes through `offerUndo()` like everything else
destructive. The calendar and the Log tab's *Avg session* read **banked** time
only: a clock still running is not a finished session and must not drag the
average down all afternoon.

**A forgotten Start is started by the first set.** Found in the gym: Start was
never pressed and a whole session went untimed. `addSet()` now starts the
clock at the first set of the day — at that set's own `t`, so the two agree to
the millisecond — when the day is today, has no clock running, no banked time
and no set on it. Each condition is doing work. A set typed into last Tuesday
is a record being filled in, not a session beginning. Banked time means the
day was already timed. And a set already on the day means the clock was either
not wanted or thrown away with Discard, so it stays thrown away. The first
movement's lap then runs from that set rather than from a Start that never
came. Start is still there, and still the more accurate of the two: the set is
logged after it is lifted.

It says so with `notify()`, which is the undo bar with no button. An Undo
there would sit directly above the rest timer's Start, and the thumb goes to
Start rest straight after logging a set — one wet miss from quietly taking
back the very thing that was just fixed. Discard, on the clock itself, is the
way out, with its own undo. `offerUndo()` now hides its button whenever there
is nothing to restore, because a dead Undo is a lie.

**A forgotten clock records nothing rather than a lie.** Nobody locks in the
day from the car park, so a clock is going to be left running overnight — and
`14:32:07` on a calendar day is precisely the confident wrong number rule 3
exists to stop. Two things handle it. `checkDayRollover()` stops the clock on
the day it started on, because a session belongs to the day you trained, not
the day you next opened the app. And `stopWorkout()` banks a run only if it is
under `MAX_SESSION_MS` — six hours, generous for the longest real day anyone
has in a gym. Past that the time is dropped, the way the label reader leaves a
field it could not read empty. The lifts are untouched; the day simply does not
claim a duration.

Dropping it silently would be the same bug from the other end, so the running
bar names the state before you get there: past the bound it goes `.is-stale`,
loses the accent, reads *Left running*, and says the time will not be saved.
The once-a-second tick only writes digits, so it hands over to one `render()`
at the moment the bound is crossed and stops.

**Each movement gets a Done, and a time.** Asked for after the first real
session: once you have moved on, the card you left is a target for misplaced
taps, and there was no way to see how long any one movement took. Done appears
once a movement has a set; tapping it folds the card down to what you did and
how long it took, with nothing left on it to hit but *Reopen*.

The time is a **lap**: from the last movement you finished — or from *Start
workout*, for the first — to this one's Done. `finishLift()` computes it once
and stores it as `lapMs` beside `doneAt`, so nothing afterwards (another
movement removed, the clock restarted, this one reopened) can quietly rewrite
it. Undo straight after Done puts back exactly what was there, for the Done
tapped a set early; *Reopen* later keeps the time, because it is for fixing a
number after you have moved on, not for re-timing.

It records **no time rather than a wrong one**, the same rule as a forgotten
workout clock, in three cases: no clock running; a lap past `MAX_SESSION_MS`;
and a movement whose first set came before the last Done — it was being worked
alongside another, a superset or a Done forgotten and tapped late, so the time
since that Done is not all its own. That last check is why sets now carry a `t`
timestamp. Only an earlier *Done* disqualifies: a first set logged just before
*Start workout* is the normal way to begin.

*Lock in the day* times the movement you were still on, because nobody taps
Done on the last one before locking in — but only when exactly one is open.
Several open means no telling whose time is whose, so none of them is given
one. Lock stays the thing that stops the clock, and it times the last movement
*before* `stopWorkout()` takes the anchor away.

The folded card only exists after a press, so it is in the fixtures of
`darkcheck`, `hittest` and `mobile` from the start rather than waiting to be
found. The lap tests run on a clock the suite moves by hand, pinned to noon, so
a seven minute set of rows takes seven minutes to the app and none to CI, and
the laps come out exact.

**A movement can be changed without losing its sets.** Picking Barbell Curl
when Dumbbell Curl was meant used to mean Remove and add again, and the sets
went with it. The name on an open card is a button with a ▾; it opens a picker
on that split's movements (plus whatever it is called now, in case that is no
longer on the list) and *+ New movement…*. Saving swaps `l.movement` and
nothing else. Undo puts the old name back — and takes a name typed in the
editor back out of the split's list, so a typo does not stay behind in the
library. The target is 44px tall without growing the card: the padding is
taken back with a negative margin. Closed and locked cards do not offer it;
the point of folding a card is that nothing on it can be hit by accident.

**How a set was done: a technique box beside weight and reps.** Drop set,
rest-pause, to failure, warm-up and the rest live in `TECHNIQUES`, and a set
carries `tech` **only when it is something other than normal** — most sets are
just sets, and never touching the box is the ordinary path all the way to Done.
The tag shows on the chip, on the folded card and on next time's rows (*Last
time, set by set*, below), which is where it pays off: you see which set was
the drop. `techShort()` answers an id it does not know with the id itself, so a
technique from a newer backup or a retired one still reads as itself rather
than vanishing.

A new set's technique comes **from last time's matching set, named in the line
over the fields, never from the set before.** It used to be "normal for every
new set", so that a drop tag could not quietly ride along onto every set after
it; the same worry holds, which is why the set before is still never the
source. When last time has a next set the box opens on that set's tag — set 1
was a warm-up, so the sheet opens on *Warm-up* and says *Last time, set 1: 60×15
warm-up* — and with no last time, or all of it done, it opens on normal as it
always did. It is chosen in the set sheet now, below.

**A tap on a set opens it; it no longer removes it.** Tapping a chip used to
delete the set outright — the same remove-and-add-again the owner called out for
movements. It now opens `#setEditSheet`: weight, reps, technique, Save, and
*Remove this set* set apart below the everyday actions. Reps are required and it
says so; weight may be nothing (bodyweight). Changing and removing both go
through `offerUndo()`. The sheet re-finds the set by day, movement and position
each time rather than holding the object, so a redraw or an undo in between
cannot leave it writing to a set that is no longer on the page.

**Logging a set happens in the set sheet too.** From real use: the sheet that
changes a set lets you focus on the thing you are doing, with the rest of the
card out of the way — so it is now how a set is added as well. The card's
entry row keeps its look (lb, reps, the technique box, Set) but each part is a
button that opens the sheet on the field it stands for, the cursor already
there. Adding opens on last time's next set where there is one (*Last time,
set by set*, below) and otherwise on the weight of the set before, because sets
so often repeat it; Enter in the weight moves to the reps, and Enter in the
reps adds the set. The sheet carries the number to beat, since the card is
behind it, and *Edit* beside the title changes the movement without
leaving it — `changeMovement()`, shared with the card's own picker, so both
keep the sets, both undo, and both take a typed name back off the list.
`logSet()` is the one way a set is added, which keeps the first-set clock
start in one place. The suites log through it with a `log_set()` helper.

**Supersets are a tag, not a nesting.** `l.ss` marks the members; every loop
over `d.lifts` — totals, *Last*, laps, the calendar — keeps working untouched,
and only drawing, timing and the drag know about groups. `tidySupersets()` is
the one place the rules are restored after anything that moves or removes a
movement: members sit next to each other, a group has at least two, and a group
is open or finished as a whole. Removing a member snapshots every link first, so
undo puts the superset back and not just the movement.

A superset is **timed as one movement** — the owner's own description of one.
`finishUnit()` takes a single lift or a whole group; the members still to be
finished share one lap stored on the first of them, and a group's time is the
sum of its members'. That also comes out right for a superset put together
after the fact: sequential laps add up, and an overlapped partner was already
recorded untimed with its time on the other. Members have no Done of their own;
the bracket has *Done with superset*, then its time and *Reopen*, plus *Split*
while open. *Lock in the day* counts a superset as the one unit it is.

**Arranging is the Macros drag, adapted to cards.** A food row is one line; a
movement card is a quarter of the screen and full of buttons. So a card is
picked up by its **grip** (`touch-action: none`, which is the only thing keeping
a real touch from being taken over by the page as a scroll), not by a hold
anywhere, and the moment it is picked up **every card folds to one line** so the
whole list fits on screen and the page can be scrolled so the held card stays
under the finger. Where it lands decides: on another card's *superset* zone the
two become a superset; anywhere else it moves. The zones sit **left of the
grips**, so a thumb sliding straight up or down the grip column always moves and
never supersets by accident — `touch` drives exactly that with real finger
events, and a diagonal aim at the middle of a row does cross a zone.

Order inside a superset is the point of one, so a card dropped next to a member
of its own superset stays in it — that is what lets the order inside a
two-movement superset be swapped. Dropped strictly between two members of
another superset, it joins that one. Anywhere else it leaves.

Letting go expands the cards again, and the release is followed by a click on
whatever is under the finger by then — Done, Remove, a set. A capture-phase
listener on `#view` swallows clicks for 400 ms after a drag, before any card's
own handler can see one. Put straight back where it started, nothing changes
and nothing is offered to undo.

**The rest timer is start and stop, and nothing else.** Asked for as the
simplest possible thing, and kept that way: it lives in the `.dock` above the
tab bar on the Gym tab only, so it is under the thumb wherever the page is
scrolled, and it saves nothing. It is a timestamp (`restStart`) and not a
counter, for the workout clock's reason — the phone goes in a pocket between
sets and iOS suspends the app. It keeps running while another tab is looked at.
Because it sits in the dock, **`hittest`'s usable band now ends at the dock's
top, not the tab bar's**, and the whole dock counts as chrome; otherwise
anything scrolled under the rest bar reads as covered.

**The movement lists are the owner's own names.** The app used to start every
split with a dozen movements of its own, and in real use the owner spent time
between sets scrolling past them for his — named his way. A new phone now
starts with empty lists: with nothing named yet, the field to name one is
simply there, Enter adds it, and it is on the list from then on.

A phone that had the old lists is cleaned once (`store.movesOwned` marks it
done): a starting name (`SEED_MOVES`, kept only for this) comes off a list
unless it was ever logged, under any split. Anything typed stays, anything
trained stays, history is untouched because every lift carries its own name,
and the app says how many it took off rather than letting them vanish. The
one case it cannot tell apart is a name someone typed that happens to match a
starting name exactly and was never logged — rare, and typed again in a moment.
Test fixtures that stand for a phone already on this build set `movesOwned`,
or the clean-up runs on them; `share`'s did not at first and lost a typed
"Hack Squat". The Coach tab's library is separate and stays: it only adds a
name when one is tapped.

**The Add movement list has a minus.** A native picker cannot hold a button per
option, so `#mDrop` sits beside it and takes out whichever movement is chosen,
with undo. It is disabled on *+ New movement*, where there is nothing to take.
Only the list of choices changes — every workout already logged keeps the
movement, because a lift carries its own name (rule 7).

**Compared with last time.** A sheet, from *Compare with last time* under the
movements. The session is set against the last session of the **same split**
(legs against yesterday's chest would say nothing), and each movement against
the last time it was done: top weight, sets, reps, volume and time. Up is
`--hit` and down is `--miss`, the macro colours, as the owner asked — and he
listed a longer session with the heavier weights, so time is coloured the same
way. A figure missing on either side is shown as *not compared* rather than
counted as a change.

**A special day is outside the routine on purpose.** Asked for from home:
two pairs of dumbbells and no machines, so no Back / Bi / Tri day — biceps and
shoulders instead — and the same for yoga, or a friend's workout. `SPECIAL` is
a built-in day, not a split: its chip sits after the splits, `cat()` always
knows it, and it is never renamed, removed, scheduled or exported with a
routine. Its Add movement list offers every split's movements, grouped by
split, plus its own; borrowing one leaves the splits' lists alone
(`allMoves()`), a new name typed there is kept as the special day's own, and
the minus only takes off its own.

**Its lifts still count, because history is by name.** "Hammer Curl" at home
is "Hammer Curl" at the gym: `lastTime()` never looked at the split, so the
home session is next time's *Last* and its *To beat* — which by the owner's
five-pounds-a-rep rule makes a light, high-rep home set a real target: 25×20
is worth more than 35×10. What it must not do is stand in for a split's
session: `compareHtml()` leaves special lifts out when it finds the last
session of the same split, so the next back day is set against the last real
back day, while each movement is still set against the last time it was done,
wherever that was. On the special day itself there is no session to compare,
and it says so. A day with only a clock — yoga — can be locked in, which banks
its time, and the calendar calls it a session rather than "no gym".

**Notes: one for the day, one on each movement.** Asked for from the gym:
*at home* or *hotel gym* for the day (`d.gymNote`), and *last set was really
hard* on a movement (`l.note`). They are the context that explains a number when
you look back at it, so both come back on next time's *Last* line — the day's
in brackets after its date, the movement's in quotes after that, clipped
short there — and the comparison and the calendar day's title name the day's.
The day's note is offered under the clock and stays writable after *Lock in
the day*: "trained at the hotel" is often only worth saying afterwards, and it
changes no lift. A movement's is written on its open card, just above Done,
and read everywhere else. Saving an emptied note is how one is taken away, and
every save says what it did through `offerUndo()`. Their quiet labels are
`--ink-2`, not `--ink-3`: the day's sit on the page's ground, where ink-3
measures 4.3:1.

**The set to beat.** Asked for from the gym: starting a movement, what is the
number to pass? Every open card carries it under *Last* — last time's best
set, never a warm-up — as *To beat · 145×8*. When one of today's sets goes past
it the line turns `--hit` and reads *↑ Beaten · 145×9 over 145×8*, and the
folded card keeps it, so tapping Done does not take the moment away.

**Five pounds is worth one rep — the owner's rule, not a formula from a
book.** In his words, 150×7 is the same as 145×8, and 145×10 beats 150×7. So
`setWorth()` counts a set as its reps plus one for every `LB_PER_REP` pounds,
`topSet()` takes the set worth most (the heavier of two worth the same,
because that is the one that was on the bar), and `beats()` means worth more.
Worth the same is a match, not a win, so 150×7 against 145×8 stays *To beat*.
The same rate settles what he did not spell out: 145×9 beats 150×7, because it
is worth 150×8. And it picks the target as well as judging it — 30×12 is last
time's best over a heavier 35×6 — because a target chosen by weight alone
could be "beaten" by a set worth less than one already done last time.

The first version was stricter: more weight for at least the same reps, or
more reps for at least the same weight, and anything else was a trade it
would not call either way. He answered that with the exchange rate, which is
the better rule because it decides every case.

**Every way past it counts — but it is no longer spelled out.** One number was
not enough: a light, high-rep day at home made the gym's target 25×20, and
"beat that" read as "outdo it with heavier dumbbells". The owner's answer was
the three ways a lifter actually progresses, each of which counts: the next
tier of weight at the same reps (`LB_PER_REP`), one more rep, or one more set
at that level. All three are still how a movement is *Beaten* — `beats()` and
`setsAtLeast()` are unchanged, so a light home day's 25×21 still beats 25×20.
The set is counted by the same rule: any set worth at least the target is a set
at that level, so 140×9 counts toward "a 3rd set of 145×8". An extra set beats
it only when no single set already has, and reads *↑ Beaten · a 3rd set of
145×8*.

What went is the line that listed them under *To beat* (*+5 lb 150×8 · +1 rep
145×9 · +1 set a 3rd set of 145×8*, `.beat-ways`, and the same text in the set
sheet, `#seWays`). The owner asked on 2026-10-14 for it to go, because the card
was too busy; *To beat · 145×8* and the *↑ Beaten* lines stay exactly as they
were. The rows of *Last time, set by set* do that line's job a different way:
they show the set to match, set by set, instead of three ways to pass one. The
checks that looked for the line now assert it is gone (`sweep`, `darkcheck`),
so it cannot drift back on unnoticed.

Any tag rides along with the number, so `120×12 rest-pause` never passes for
a straight set of twelve. A finished day shows *Beaten* where it was and
nothing where it was not: *To beat* with nothing left to do about it is a nag.

**The target is from the same gym.** The owner trains in two places, and the
same movement on different machines is a different number: the fly goes 150
for reps at the apartment gym and 110 at 24 Hour Fitness, so one target was
wrong at both. `store.gyms` holds `{id, name, tag}`, chosen under the clock
(*Training at*), and a day carries `d.gym`. `lastTime(movement, before, gym)`
then counts only days trained there. Today with nothing chosen is wherever he
trained last (`store.gymLast`, via `dayGym()`), and `stampGym()` writes it onto
the day the moment anything is logged, so the record says where even if the
default moves on. Choosing on a past day puts that day right and leaves
tomorrow's default alone.

The gym is a **tag beside the name** (`Pec Fly · APT`), never part of it.
That was his choice over a suffix in the name: with a suffix every movement is
in the list twice, a new tag means renaming history, and dumbbells could not
share numbers. That last point is what **Every gym** is for: a dumbbell weighs
the same everywhere, so the set sheet's *Targets from* row
switches a movement to take its numbers from any gym (`store.gymShared`, by
name). New movements stay separate per gym. He picked that default because
it is the safe one: a machine nobody flips never shows another gym's target.

Never done at this gym, the card shows where it was done, with the numbers,
and says *not a target here*. It never shows them as *To beat*. A day nobody
marked is the same: never a target at a gym, only a reference. When the first
gym goes in, the app asks once where the earlier workouts were
(`store.gymAsked`). Marking them is one undo; leaving them unmarked is too.

Rule 7 with a third noun: a removed gym's name goes into `store.gymsRetired`,
and its days say *a gym you no longer train at* on the Gym tab and the
calendar. Renaming keeps the id, so history follows. *Compare with last time*
looks for the last session of the split **at the same gym**. With no gyms at
all, nothing changes from before, so a phone that never adds one never
notices the feature.

**Last time, set by set.** Asked for by the owner (issue #5): *To beat* gives
one number, but in the gym the question is "what did I do on this set last
week?". He was shown four ways to answer it on the card, picked one, and
changed one thing of his own — keep *To beat*, take the suggestions line away.
On an open card with a last time at this gym (`prev`), under *To beat*, there
is one read-only row per set of last time: `Set 2 · 100×15` on the left
(`setText`, so a tag reads `60×15 warm-up`), and on the right today's numbers
and a label — `= Matched` (grey), `↑ Beat` (`--hit`), `↓ Short` (grey) — or,
on the first set still to do, a grey *next*. `lastPlan()` builds them and the
card and the pop-up both read it. On a 320px phone a long row wraps inside
itself (last time's tag under its numbers, the status under today's) and
never puts today's numbers under the row, where they read as the next row's;
`mobile` checks it at every size.

**Pairing is by kind, in order.** The i-th warm-up today pairs with the i-th
warm-up last time, and the i-th working set (anything that is not `warmup`)
with the i-th working set. Paired by position instead, one extra warm-up today
would shift every row below it by one — a Matched becomes a Short and the
pop-up pre-fills the wrong set. By kind, the extra warm-up has no row and the
working sets still meet their own. The label is `setWorth()` — the owner's
five-pounds-a-rep rule — so more is Beat, equal is Matched, less is Short; and
*next* follows progress: the set after the furthest one done today. It was
first written as the first set with no partner, which offered a skipped warm-up
again after the working sets had begun, and filled the pop-up with it. Lexi
caught it in review. Today's tag
is written beside its numbers only when it is not last time's, so a warm-up row
stays on one line; a rest-pause set against a normal one says so.

Nothing in the rows is tappable and nothing is teal, because teal means you
can tap it. Rows are not drawn when there is no `prev`: **a first time at this
gym still shows only the other gym's numbers under the *not a target here*
line, because another gym's numbers are never a target** — rows would present
them as one. A folded card keeps no rows. A locked card draws none either; a
locked day closes every movement that has sets, so the one left open is a
movement with none, and its *Last* line still carries last time's sets as it
always did. The *Last* line on an open card is now where, when and both notes
(`Last at APT · Oct 7 (felt strong) · “last set was really hard”`), and its sets
are the rows below.

**The Set pop-up starts where last week did.** Adding a set opens on last
time's next set: its weight, reps and technique, and a line above *To beat*
naming it — `Last time, set 4: 200×10 · APT · Oct 7`, the gym only when gyms
exist, the tag included (`set 1: 60×15 warm-up`). That is `setFillFor()`;
without a next set — all of last time's sets are done, or there is no last
time — the sheet is exactly what it was: the weight of the set before, blank
reps, normal, no line. Opened from **Set** with numbers in it, no field takes
focus, so the keyboard stays down: the numbers are there to check, then *Add
set*. Opened from **lb**, **reps** or the technique box it focuses that field
with its value selected. Without a pre-fill Set still opens on the weight.

**Typing replaces a pre-filled number.** Typing 12 over a pre-filled 15 gave
1512, because a focused field puts the caret at the end. While a set is being
*added*, focusing weight or reps selects what is in it, and *Enter* from the
weight moves to the reps with them selected. A set being *changed* keeps the
old behaviour — a caret where it was tapped, to fix one digit. The selection
is made at once and again in a timeout, as a precaution against a caret being
placed after the focus event.

**The fields follow the sheet, but only the ones nobody touched.** *Every gym*
(a movement's *Targets from*) and *Edit* (change the movement) both change
which last time applies while the sheet is open, so both re-fill. A refill
must never overwrite a number someone has typed: `setEditing.put` remembers
what the code last wrote into each field, and a refill writes only into a field
that still holds exactly that. Typing the weight, then flipping to *Every gym*,
fills the reps and leaves the weight alone. Flipping back to a gym with no last
time empties what was filled and keeps what was typed. The line always follows
the current last time. Without a next set, the fields go back to the set before
and blank reps.

`sweep` covers all of it with one four-set history, as `Leg Extension`: rows
read matched / matched / short with *next* on set 4, a set worth more reads
Beat in `--hit`, an extra warm-up does not shift the working sets, Set opens at
200 / 10 / normal with the *set 4* line and at 60×15 warm-up for set 1, past
last time's count it opens as before, typing replaces, *Every gym* and *Edit*
re-fill untouched fields only, two gyms give rows only from the gym you are at,
and the suggestions line is gone from the card and the sheet. `darkcheck`'s
fixture paints matched, beat, short and next — and fails if one is missing —
and measures the pop-up with its line; `mobile` fits a six-set history with a
tag on both sides of a row on every phone size.
