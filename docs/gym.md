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

**The bottom bar: three boxes, the way Macros has them (b87).** Asked for by
the owner, to carry Macros' layout over: what you watch all session stays open
at the top — the workout clock, then the planned week, then *Today's split* —
and the rest is folded until pressed. The dock holds three buttons (`.ways3`,
`data-gymway`): *Choose gym*, *Add movement* (the filled one in the middle,
because it is used most) and *Rest timer*. Choose gym and Add movement open a
box at the foot of the page, under the movements, one at a time (`gymWay`),
with Close in its head; pressing the open one folds it. It survives redraws,
so adding a movement leaves the box open for the next, and `showGymWay()`
brings the box up to just above the dock, never past its own top, so the
movement just added — right above the box — is on screen too (rule 3).

The gym button reads *Choose gym*, the owner's words, not where the day is
marked (*At APT* was tried first): it says what it does, the way *Add
movement* does, and every movement already wears the gym's tag. Its spoken
label adds where today is. It carries a dot when the day needs a gym: today with gyms and none marked, a past day with
lifts and none, or the one-time question about earlier workouts still
waiting. Adding or editing a gym keeps its box open (`gymEdit` sets `gymWay`).
Add movement on a locked day opens to a line saying why there is no form,
because a press that shows nothing reads as a dead button.

The rest timer's box opens **in the dock**, above the three, not in the page,
because it is watched while the page is scrolled to the set being logged.
**One tap starts it** (`restGo(true)`): the box is only ever reached for after a
set, so opening it and pressing Start were two taps for one job. Opened on a
rest already running, it shows it and does not restart it; Stop is inside.
`restOpen` is that state; it is patched by `drawRest()` rather than a redraw,
so a half-typed weight survives it. Folded while it runs, the count goes on and
shows on the button itself (*Rest 1:23*, highlighted) — a rest in progress is
never hidden. The iPhone app's *Buzz at* row shows only with the box open and
the clock running; folding it does not cancel an alert already set.

**The week is one row of seven (b87)**, so *Today's split* is on the first
screen. A tile is the day over its date and the tag; the split's name went
with the room for it, and the tag's letter and colour (and the label, read
aloud) say which. *Clear plan* moved from an eighth tile to the board's
heading. A tile is about `(width − 78) / 7` wide — 46px on the owner's 402px
phone, 44px from 388px — so narrower phones (the SE, the 13 mini) keep two rows
rather than drop under rule 5's 44px.

The suites open each box the way a person would, through `tests/gymways.py`;
`mobile` and `hittest` walk the Gym three more times (`gym:gym`, `gym:move`,
`gym:rest`), and `darkcheck` checks each box and the folded running count.

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
The tag shows on the logged row, on the folded card and in next time's *Last*
box (*Last time, set by set*, below), which is where it pays off: you see which
set was the drop. `techShort()` answers an id it does not know with the id itself, so a
technique from a newer backup or a retired one still reads as itself rather
than vanishing.

A new set's technique comes **from last time's matching set, never from the
set before.** It used to be "normal for every new set", so that a drop tag
could not quietly ride along onto every set after it; the same worry holds,
which is why the set before is still never the source. Each row to do (*Today's
sets are rows*, below) starts on the tag of the set of last time it stands for
— set 1 was a warm-up, so row 1's box reads *warm-up* — and a row past last
time's sets, or with no last time, starts on normal as it always did. The box
is a native picker laid over the label (`.tech select`), so choosing one is a
tap and a pick.

**A tap on a set opens it; it no longer removes it.** Tapping a set used to
delete it outright — the same remove-and-add-again the owner called out for
movements. It now opens `#setEditSheet`: weight, reps, technique, Save, and
*Remove this set* set apart below the everyday actions. Reps are required and it
says so; weight may be nothing (bodyweight). Changing and removing both go
through `offerUndo()`. The sheet re-finds the set by day, movement and position
each time rather than holding the object, so a redraw or an undo in between
cannot leave it writing to a set that is no longer on the page.

**Today's sets are rows (b100).** The owner's own layout, from a sketch: last
time in a box of its own, then today as one row per set, so the sets he is
about to do are on screen before he does them. Before b100 a set was added one
at a time through the set sheet (b66 to b99), opened from an entry row of lb,
reps, the technique box and Set. Now `todayHtml()` draws, under *Last*:

- **the sets logged**, in the order they were done, each a button that opens
  it in the set sheet to change or remove, with how it went against last time
  beside it (`= Matched`, `↑ Beat`, `↓ Short`, below);
- **the sets still to do**, one row each: weight, reps, the technique box and a
  check. Last time's numbers sit in the boxes as grey placeholders (*Last time,
  set by set*, below), and the next row has the filled check;
- **a count with − Set and + Set** (`4 sets, as last time`, or `5 sets · 4 last
  time`).

A row to do is a plan and nothing more, which is the point of the check: a set
filled in for you but never lifted must not be in the log, and nothing else
could tell a set done from a set skipped. So the check is the one way a set
goes in. It takes what was typed, or the grey number where nothing was, and
calls `logSet()`. That is still the only way a set is added, so the first set of
the day still starts a forgotten clock (*A forgotten Start*, above). A set that
went as it did last time is one tap; before b100 it was two (Set, then Add set).
The row turning into the set, with its Matched or Beat, is what says it was
logged (rule 3). Reps are required: a check with none says *How many reps?*
through `notify()` and puts the cursor in the reps. Weight may be nothing
(bodyweight). Enter in the weight moves to the reps, and Enter in the reps logs
the row.

**Which rows, and how many.** `todayRows()` builds them. The rows to do are
last time's sets after the furthest one done today. That is `lastPlan()`'s
*next*, so a warm-up skipped today is not offered again once the working sets
have begun. With no last time there is always one row ready, holding the set
before's numbers. + Set adds a row after the last, holding the numbers of the
row above it on normal. − Set takes the last row to do off, and is disabled
when there is none: a logged set is never taken off by it, because that is a
delete and has its own Remove, with undo, in the set sheet. How many rows were
added or taken off is `rowAdj`, by movement, and what has been typed into a row
not yet logged is `rowDraft`. Neither is in the log, since a plan is not
history, so a reload starts again from last time. A draft is keyed by the row's
place on the card. That is what keeps it where it was when the row above is
logged, and when the grey numbers change under it (*The fields follow*,
below). Logging a row added with + Set uses it up, so the count stays.
Logging rows out of order is allowed and needs no special case: the set
goes in as the next one done, and pairs as any other would.

On a barbell lift the set sheet's *On the bar* picture (`barHtml()`) sits under
the rows for the next row's weight, and follows what is typed into it. The
sheet still shows it for a set being changed. Every row is one line on every
phone: below 360px wide the columns narrow so the weight and reps boxes keep
room for a three-digit number (`mobile` checks both). The sheet's *Edit* still
changes the movement for a set being changed. The card's own ▾ does it for
everything else, and both go through `changeMovement()`. The suites log a set
through the row with their `log_set()` helpers.

**The set sheet has no steppers (b89).** b66 put −5 / +5 under the weight and
−1 / +1 under the reps. The owner asked on 2026-11-07 for them to go, to clean
the sheet up: the numbers are typed, and the sheet already opens on last
time's next set, so there is usually little to type. The five-pounds-a-rep rule
(*Five pounds is worth one rep*, below) is untouched — it never depended on the
buttons. `sweep` checks the sheet has no such button, so they cannot drift back
on unnoticed.

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

**The rest timer is start and stop, plus an alert in the iPhone app.** Asked
for as the simplest possible thing, and kept that way: it lives in the `.dock` above the
tab bar on the Gym tab only, so it is under the thumb wherever the page is
scrolled, and it saves nothing. Since b87 its box is folded until *Rest timer*
in the bottom bar is pressed (see *The bottom bar* above). It is a timestamp (`restStart`) and not a
counter, for the workout clock's reason — the phone goes in a pocket between
sets and iOS suspends the app. It keeps running while another tab is looked at.
Because it sits in the dock, **`hittest`'s usable band now ends at the dock's
top, not the tab bar's**, and the whole dock counts as chrome; otherwise
anything scrolled under the rest bar reads as covered.

**The rest alert tells a phone in a pocket.** iPhone app only (b85), because
only a notification reaches a locked phone; added to help the app pass Apple's
4.2 review as more than a website. While the clock runs, a row above it offers
*Buzz at* 1:00, 1:30, 2:00, 3:00 or Off. It starts Off, and the row is gone when
the clock is stopped, so a rest with no alert looks as it always did. The first
pick asks iOS's permission; refused, it says so and still buzzes with the app
open. The time is kept under `mntl-rest-alert` in native storage, not in the log:
backups have no use for it, and a `save()` would end the undo run for the set
just logged. With the app open the notification stays quiet (`foreground: false`)
and `drawRestAlert()` says it instead, so it never arrives twice.
`sound: "default"` is not decoration: iOS plays nothing without a sound, and with
no sound a phone in a pocket does not buzz. `schedule.at` must be a real `Date`;
the bridge passes it to iOS as a date, and a string is ignored, which would make
the notification go off at once.

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

**The planned week split: a board of this week, between the workout clock
and today's split** (between where you train and today's split until b87,
when where you train moved to the bottom bar). Asked for by the owner, for two kinds of people. Someone who
plans gives each day of the week a split — Mondays back, Tuesdays legs —
by tapping that day's tile and choosing a split, *Rest day* or *Open*; the
choice is for every week (`store.week`, seven entries, Sunday first like the
calendar: a split's id, `PLAN_REST`, or null for Open), says what it did and
offers Undo (rules 3 and 6), and *Clear plan* does the same for all seven.
Someone who doesn't plan leaves every day Open and trains from *Today's
split* as always. *Today's split* stays exactly as it was for both.

**A tile says what happened before what was meant to.** `weekTile()` decides:
a day trained shows its first movement's split, the way the week strip
colours it, with a ✓ and a filled tag — today only once it is locked in,
because until then it is still going, and a day gone by as soon as anything
is on it, locked or not, because a forgotten Lock in is not a rest day. A day
gone by with nothing on it is *Rest*, whatever was planned. Today and the days
ahead show the plan as a ringed tag, or *Open*. None of this is stored: Open
turns into Rest at midnight because the day is over, and a Rest turns into
what was trained the moment it is logged.

**A day forgotten is logged after the fact.** Tapping a day gone by (or today,
seen from another day) offers *Log Sunday, Oct 18* — or *Open* when something
is already on it — which goes to that day so it is logged the usual way under
Today's split and locked in. Planning a day gone by changes every week from
now on, never what that day was.

**A plan is not history.** Nothing logged ever reads `store.week`, so rule 7
has nothing to guard here: a split that is removed, or replaced by loading
someone's routine, simply reads as Open (`plannedFor()` resolves ids against
`cats()` every time), and undoing the removal brings the plan back with it.
`store.week` rides along in a backup and a restore. The special day is never
planned, the same as it is never scheduled.

**Opening a day picks its planned split — once.** A day with nothing logged
opens on its planned split; `planPickedFor` remembers the day so a split
tapped after that sticks through every redraw, and the plan is left alone. A
day with lifts on it is left alone too. The week strip across the top marks a
planned day ahead with a ring in its split's colour. A planned rest day with
nothing logged says so where the movements would be, and the chips stay there
for training anyway.

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
you look back at it, so both come back in next time's *Last* box — the day's
in brackets after its date, the movement's in quotes under its sets — and the comparison and the calendar day's title name the day's.
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
the same everywhere, so the gym tag on an open card is a switch (b100; it was
the set sheet's *Targets from* row, which a logged set still shows): one tap
takes a movement's numbers from any gym (`store.gymShared`, by name), the tag
reads *every gym*, and the change says so with undo, because it changes what
*To beat* means. New movements stay separate per gym. He picked that default because
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
changed one thing of his own: keep *To beat*, take the suggestions line away.
Since b100 (his layout, *Today's sets are rows*, above) it is a box of its own
on an open card with a last time at this gym (`prev`): *Last at APT · Oct 7 ·
1h 37m session (felt strong)* (the gym, the date, how long that whole session
took from the day's banked `workoutMs`, and the day's note), then one line per
set, `Set 2 · 100×15` (a tag reads `60×15 warm-up`, and normal says nothing),
then the movement's own note in quotes, then *To beat*. Nothing in it is
tappable and nothing is teal, because teal means you can tap it. Today's
numbers are not in it any more: they are the rows under it, each logged row
with its label (`= Matched` grey, `↑ Beat` in `--hit`, `↓ Short` grey).
`lastPlan()` still does the pairing, and the rows and the labels both read it.

**A first time at this gym** still shows only the other gym's numbers, on one
line ending *not a target here*, and no box: another gym's numbers are never a
target, and laid out as sets they would read as one. Its one row to do is empty
(*lb*, *reps*). A folded card has no box and no rows. A locked day closes every
movement that has sets, so the one left open has none. It keeps its *Last* box,
to read, and has no rows to fill in and no − Set or + Set.

**Pairing is by kind, in order.** The i-th warm-up today pairs with the i-th
warm-up last time, and the i-th working set (anything that is not `warmup`)
with the i-th working set. Paired by position instead, one extra warm-up today
would shift everything below it by one: a Matched becomes a Short, and the rows
to do hold the wrong sets. By kind, the extra warm-up is a logged row with
nothing to measure it against, and the working sets still meet their own. The
label is `setWorth()`, the owner's five-pounds-a-rep rule, so more is Beat,
equal is Matched, less is Short. *Next*, the first row to do, follows
progress: the set after the furthest one done today. It was first written as
the first set with no partner, which offered a skipped warm-up again after the
working sets had begun, and filled the pop-up with it. Lexi caught it in
review. A logged row always shows its own tag, since it is today's record.

**The rows start where last week did.** Each row to do holds the numbers of
the set of last time it stands for, as grey placeholders, and starts on its
tag: row 4 reads `200 × 10`, row 1 `60 × 15` and *warm-up*. With nothing typed,
its check logs exactly that, which is the one-tap set. Without one (past last
time's sets, or no last time) a row holds the numbers of the row above it, as
the set sheet's weight-of-the-set-before always did, since sets so often
repeat. From b100 that includes the reps, because the check now logs whatever a
row holds. Before b100 this was the set sheet's pre-fill, with a line naming
the set it came from (*Last time, set 4: 200×10 · APT · Oct 7*). The line went
with the sheet's add mode: each row now sits under the *Last* box it was
filled from.

**Typing replaces what is in the box.** Typing 12 over 15 gave 1512, because a
focused field puts the caret at the end. Focusing a row's weight or reps selects
what is in it (`selectAll()`, at once and again in a timeout, in case the caret
is placed after the focus event). A grey placeholder is not in the box, so
typing over one is just typing. A set being *changed* in the sheet keeps the
old behaviour, a caret where it was tapped, to fix one digit.

**The grey numbers follow, and a typed number stays.** *Every gym* (the gym
tag, below) and changing the movement (the card's ▾) both change which last
time applies. The grey numbers are placeholders, so they simply follow the new
last time, and a number typed into a row is kept because drafts are keyed by
the row's place on the card. Typing the weight, then switching to *every gym*,
fills the reps in grey and keeps the weight. Switching back to a gym with no
last time leaves *lb* and *reps* in grey and keeps the weight typed. Before b100
the set sheet did this with `setEditing.put`, which remembered what it had
written into each field.

`sweep` covers all of it with one four-set history, as `Leg Extension`: the
*Last* box's head, sets, note and *To beat*; four rows holding 60×15 warm-up,
100×15, 150×15 and 200×10; one tap logging the warm-up as a warm-up; Enter from
the reps logging; typing replacing a typed 15; matched / matched / short; a draft
kept through a redraw; + Set and − Set and the count; a set worth more reading
Beat in `--hit`; − Set never taking a logged set; an extra warm-up not shifting
the working sets; a skipped warm-up not offered again; two gyms giving a *Last*
box only from the gym you are at; the gym tag switching with undo; a typed
number kept through *every gym* and through changing the movement; and folded
and locked cards. `darkcheck`'s fixture paints matched, beat, short, a next
row, a row to do and the count, and fails if one is missing; `mobile` fits a
six-set history and today's rows on every phone size.

**What a movement works (b88).** For the recovery body map, every movement
needs its muscles: the main ones and the ones that help. Movements are the
owner's own names, so there are three ways to know, in this order, and
`worksOf()` says which it used: what he has said (`store.muscles`, keyed by
`moveKey()` — case, hyphens and spacing do not make a different movement),
the built-in `MOVE_WORKS` (every name the Coach library and the starter lists
suggest), or a guess from the words in the name (`MOVE_GUESS`, first match
wins, so the narrow rules come first: a dumbbell kickback is triceps before
"kickback" is glutes, a leg curl hamstrings before "curl" is biceps, a rowing
machine cardio before "row" is back). A guess says so on the card — *a guess
from "row"* — because a guess passed off as fact is how a wrong number gets
trusted. A name none of the three place asks, once: *What does this work? Tap
to say*. The sheet's sixteen muscles cycle main → helps → off; nothing is
written until Save, which says what it saved and can be undone (rules 3 and
6). The answer is kept by name, so it holds for every day the movement was
or will be logged, and a restore adds the backup's answers without
overwriting this phone's. *Change* on any card starts from what the app
believes and wins over the list from then on.

**The recovery body map (b88).** Asked for by the owner: after a workout, the
body coloured by what needs recovery. Locked in, *Day complete* shows the
figure front and back, and under it each muscle with its sets and roughly how
long until it is ready — colour alone says nothing to a colour-blind eye, and
the list gives the numbers. Counting (`dayMuscles()`) is in working sets:
warm-ups are out; a helping muscle counts half, the fractional counting that
matched results best across 67 studies (Pelland et al. 2024, a preprint); a
set to failure, drop, rest-pause, myo-reps, forced, negatives or AMRAP counts
one and a half, because going to or past failure is what the recovery studies
tie to a slower recovery (Pareja-Blanco et al. 2017, 2020). Red from 6 sets
(about 3 days), yellow from 3 (about 2), green under 3 (about 1), untrained
grey. No study gives a "this many sets, this many days" chart, so these are a
reasoned estimate and the card says so: *a guide from your sets, not a
measurement*. A movement nobody has placed is named on the card rather than
silently left out, and counts once answered.

The figures are drawn for this app (`BODY`, `HAIR`, `bodySvg()`): a
200 x 432 box, each shape the left half and mirrored, muscle shapes carrying
their muscle id. The female figure is the same shapes narrowed through the
shoulders and waist and widened at the hips, with its own chest and hair.
The profile picks the figure (`bodyFig()`: male, female, or Other's chosen
equation); with nothing to go on, the card asks once and keeps the answer in
`store.bodyFig`. Colours are the app's own tokens, so both themes follow.
`muscles` is the suite.
