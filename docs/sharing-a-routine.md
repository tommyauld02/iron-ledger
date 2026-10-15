# Sharing a routine

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

The Coach tab exists so someone else can set a routine for the owner — a
brother, a friend. Nothing ships for that yet, and the groundwork matters more
than the feature.

**Put away, not taken out.** The owner asked to bin it for now — it has a use,
just not yet. `store.coachOn` is off unless switched on under Settings →
*Coach tab*, and `applyTabs()` hides the tab; it is `hidden` in the markup as
well, so a phone with it off never sees it flash in. Nothing is lost while it
is hidden: its days are the same splits the Gym tab's *Edit splits* changes,
and switching it back on finds it as it was. Hiding it while standing on it
lands on Gym rather than on nothing. The tab bar is `grid-auto-flow: column`,
so four tabs share it evenly. The choice travels with a backup. Every suite
that walks the tabs sets `coachOn: true` in its fixture, so Coach is still
measured for whoever turns it back on.

**Built, and built to the shape below.** Coach has *Share this routine* and
*Load a routine*. Sharing produces `ILROUTINE1:` followed by base64 — base64
rather than raw JSON because the code gets sent through messaging apps, where
JSON meets smart quotes and line wrapping. `parseRoutineCode()` is liberal in
return: tagged or untagged, wrapped over lines, or plain JSON if that is what
someone pasted.

**The export carries no ids at all.** That is the whole design. Rather than
guarding against a collision, `exportRoutine()` sends only names and movements,
and `importRoutine()` mints a fresh `"d" + uid()` for every incoming day — so
two people who both still have `back`, `push` and `legs` cannot collide,
because nothing of theirs is ever adopted. Days are **added**, never swapped
in, and the whole import is one `offerUndo()`.

It carries the routine and nothing else: no food, no lifts, no pantry, no goal,
no dates. `tests/share.py` asserts that by looking for those keys in the
decoded payload.

**Do not route sharing through `mergeInto`.** Restore and import are different
operations wearing similar clothes. `mergeInto` does
`store.routine = incoming.routine` — a wholesale replace, which is right for
your own backup landing on your own phone and wrong for anything else.

**The trap is day ids.** `DEFAULT_ROUTINE` uses fixed ids — `back`, `push`,
`legs` — so two people who never renamed their days have *the same ids for
different days*. Feeding another person's routine through restore today is
demonstrably rule 7 broken: a workout logged under your `back` renders under
their name for `back`, `store.retired` stays empty, and nothing records what
the day was called when you trained it. Verified, not theorised.

So an import path must **remap incoming day ids to fresh ones** before
anything touches the store, and must add days rather than replace them.
`addSplit()` already mints `"d" + uid()`, which is collision-safe; only the
three seeded defaults are not, and they cannot be renamed retroactively
without orphaning the history of everyone already using them.

**Movements collide the same way.** `mergeInto` merges `incoming.moves[id]`
into `store.moves[id]` by id, so their bench press lands in your back day if
the ids happen to match. Remapping ids first fixes this too.
