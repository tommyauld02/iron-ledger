# The Cardio tab

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**Cardio has a tab of its own.** Asked for by Nygle, a tester, and placed
where Coach used to sit, between Gym and Log (Coach, when switched on, follows
it). It is the Gym tab's shape kept simple. `renderCardio()` draws it, and a
day carries `d.cardio`, a list of `{id, type, min, dist?, cal?, t}`. The types
are the owner's own names (`store.cardioTypes`), added from the picker's *+ New
type…* and taken off with its minus. Like movements, a session carries its
own name, so taking a type off the list leaves history alone.

*Start cardio session* asks what it is, then runs a clock (`d.cardioStart`,
`d.cardioType`) that is a timestamp for the workout clock's reason. *Stop and
log it* turns it into a session (`stopCardio()`) under the same rules as the
workout clock. Over `MAX_SESSION_MS` it was forgotten, so nothing is logged,
and the bar goes *Left running* first. Under a minute it was a mis-tap, and
the app says nothing was logged. Midnight stops it on the day it started and
says so. Sessions can also be added by hand: minutes are required and say so;
miles and calories are optional. The calories are typed from the machine or a
watch. The app does not guess them, because it does not know anyone's weight
and a made-up number is the confident wrong one. *Finish cardio* is *Lock in
the day*: a *Cardio complete* card, `celebrate()`, and *Unlock*. There is no
rest timer here; it stays a Gym-tab thing.

**The goal counts what the owner chooses.** Minutes a week is the default
(the owner's call). He asked for distance and calories burned as goals too,
each daily, weekly or monthly, so `store.cardioGoal` is `{kind, period, v}`
over `CARDIO_KINDS` × `CARDIO_PERIODS`, and `cardioTotals(key, period)` sums
the day, its Sunday-first week, or its month. Switching what is counted or how
often goes to that pairing's starting number (`CARDIO_GOAL_START`) rather than
re-reading the old one, which is the unit picker's rule. The editor flips its
buttons in place, so a number being typed survives. Met, the line turns
`--hit`. On the Log tab, `cardioTrackerHtml()` draws the last eight of the
goal's own periods against a dashed goal line, grey under it and green on it
(never teal, which means *tap*), with an even number of tiles. It draws
nothing until something has been logged. Calendar colours are untouched, and a
day's title names its cardio.
