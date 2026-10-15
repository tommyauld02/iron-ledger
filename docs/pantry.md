# The pantry and the daily checklist

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**Your pantry answers to part of its name.** A pantry entry used to be found
only by its whole name, so someone who saved "Costco protein coffee" and later
typed "protein coffee" missed the pantry entirely and got the table's black
coffee — 1 kcal logged for a 130 kcal drink, with nothing to suggest anything
was wrong. `matchPantryItem()` now also matches when what you typed appears as
a run of words inside the saved name, two words minimum so a bare "coffee"
still means coffee, and it tries a singular form so "2 protein coffees" lands.
`parseQty()` drops a leading article too: "half a protein coffee" used to leave
"a protein coffee" behind, which matched nothing.

**The pantry `+` asks how much.** It used to log exactly one saved serving, so
four slices of bacon meant pressing `+` four times and combining the rows
afterwards — found in real use, on the first morning. `+` now opens
`#panSheet`: minus, the number, plus, a unit picker where one is meaningful,
and a live total. `panAmount()` does the maths and nothing is written until
*Add to ledger*, so backing out leaves the day untouched. The note records what
was eaten — `Bacon · 4 slices` — because "Bacon" alone gives no way to tell one
slice from four when you read it back a month later.

The unit picker obeys the **same rule as the estimate review: switching
converts, it never re-reads.** Re-reading 340 g as 340 oz is nine kilograms of
yogurt logged in one tap. Weight and volume convert through grams; a count unit
has no honest conversion to grams, so that direction resets to the saved
serving rather than carrying a number across that would mean something else.

**A count is one of the thing.** Typing 4 and picking "slice" means "one
serving is four slices", and `normPantry` then reported `1 slice · 172 kcal` —
a fourfold overcount stated with complete confidence, on every line in the app.
`savePan` now stores one piece and **says that it did**, because changing what
someone typed and not mentioning it is its own kind of silence. The total is
preserved exactly: four of them logs what was entered. `normPantry` divides the
same way on read, so records saved before this still come back true without
anyone's pantry being rewritten underneath them.

**The daily checklist is not food.** Creatine and a multivitamin have no
calories worth logging, but whether you took them is exactly what you want to
see across a week. `store.supps` is the list — `{id, name, dose}` — and each
day carries `d.supps = {id: true}` for what was ticked. It is built on the
Pantry tab, because that is where you set up what the app knows about you, and
ticked on Macros between the target bar and the add form: it belongs to the day
you are looking at, and it is the last thing you check rather than the first
thing you log. Nothing renders at all when the list is empty — an empty
checklist is a nag with no content.

**Ticking patches the DOM; it must not call `render()`.** The add-food fields
keep no draft, so a redraw would wipe whatever is half typed into them — and
you reach for the checklist mid-entry precisely because it is sitting right
there. The handler updates the row, its `aria-pressed` and the `n of m` count
in place, the way the workout clock and the estimate rows already do.

**Rule 7 applies here with a different noun.** Renaming keeps the id, so every
day already ticked follows the new name. Removing writes the name into
`store.suppsRetired` and goes through `offerUndo()`, and `dayTitle()` names
those ticks as *"also Creatine — no longer on your list"* rather than dropping
them — a tick against nothing is history silently reassigned.

On the calendar a complete day gets a **dot, not a colour**: the cell already
means hit-or-miss on calories, and two colour systems in one twelve-month grid
is a code nobody can read. The day's title says `checklist done`, or names what
was missed — "3 of 4" a month later tells you nothing about which one you keep
forgetting. The Log tab gains *Checklist days* and *Best run* **only when a
list exists**, which also keeps `.yearstats` even rather than orphaning a tile
on its own row. `suppStreak()` compares whole days rather than milliseconds,
because the clocks change twice a year and a 23-hour gap is still one day.

**A meal eaten often is saved to the pantry.** From the estimate review (*Save
this meal to your pantry*, with a name field) or from a meal already in the day
(*Save to pantry* in its actions). `saveMealToPantry()` writes one pantry entry
with the meal's totals as the serving, unit `meal`, and its parts in `items`, so
`+` and the quantity sheet work on it like anything else — and logging it puts a
**meal** in the day, parts scaled by how many, rather than one anonymous number.
One name is one entry: saving over it says *Updated*, and undo puts the old one
back. A meal with a part still waiting for numbers cannot be saved, because it
would bake a zero into every future log of it — and a note stands in the
button's place rather than a button that cannot work.

**Or combined in the pantry itself.** The owner was found making a shake every
night from three foods already in the pantry and logging them one at a time.
*+ Combine foods into one* opens a draft (`panCombine`) at the top of the list.
Each food goes in through its own `+`, which opens **the same how-much sheet**
with its button reading *Add to the mix*, so "2 scoops" is said the way it
always is. *Save as one* hands the parts to `saveMealToPantry()`, so the result
is an ordinary saved meal. The three foods are never touched. A saved meal
added to a draft goes in as its parts, scaled, because meals never nest.

What it refuses, and says why in `#combWarn` instead of acting like a dead button:
fewer than two foods, no name, and **a name that is already one of your
foods**. One name is one entry, so saving a shake as "Protein powder" would
replace the protein powder, which is the one thing the owner asked to keep.
The draft is not data, but it took several taps to build, so *Cancel* still
offers undo. A food added to the draft shows a tick on its `+` and a notice,
because the draft can be well above the row that was tapped.

**The pantry is filed in sections.** Asked for once it grew: Breakfast,
Lunch, Dinner, Snacks and Desserts (`PAN_SECS`), in the order a day runs — he
listed them in another order; this one is for finding things. `panTab` is
transient: the app always opens on All, so nothing saved is hidden behind a
tab someone forgot they left open.

**A food is in as many sections as it is eaten at — or none.** b45 filed each
food in exactly one, and the first morning of sorting showed why that was
wrong: protein coffee is breakfast *and* a snack. `secs` is a list. *All* is
every food in one alphabetical list, the way the pantry always was, each
naming its meals under its name; a section's tab is the foods eaten then; a
food in none simply lives in All, with nothing nagging it to be sorted. b45
wrote a single `sec`, and `rawSecs()` reads it the same way, so nothing saved
then had to be rewritten to still count. An id this build does not know — a
newer backup — is kept as it is while the known ones change around it
(`setPanSecs()`): shown nowhere, lost nowhere.

**Saving says where it went.** The form asks *Which meals is it for?* with the
five as buttons, any number on, starting on the section whose tab you are
standing in. Saved while another section is showing, the new food would land
off screen — the Add that saved perfectly and said nothing — so the list
follows it to one of its sections, or to All, and `notify()` names them.
Saving a meal from the estimate asks with the same buttons; on a meal already
in the day, *Save to pantry* is a picker, so the one section chosen is the
save, and more can be added from the pantry. Saving over a meal of the same
name without choosing keeps the sections it had.

**The sections themselves are the owner's.** Someone who never eats
breakfast takes it away; someone who trains early adds a pre-workout. *Edit
sections*, over the list, is the Gym tab's *Edit splits* in miniature: each
name is a field that renames on change — the id stays, so every food in it
follows — Remove takes one away, and a field at the foot adds one.
`store.panSecs` holds them once anything is changed; until then the starting
five stand in (`panSections()`), so nothing is written for no reason.

Taking a section away does not touch a single food. Its id stays on every food
that was in it — unknown to the list, so shown nowhere and lost nowhere — and
undo puts the section back with its foods already in it. With no sections at
all there are no tabs, no choices on the forms and no Meals button, and a meal
already in the day is saved with a plain button, since there is nothing to
choose. Names are typed now, not written into the code, so everywhere one is
drawn it goes through `esc()`. A restore brings the sections with it, the way
it brings the routine.

**A food's meals are changed on its own row.** *Meals ▾* sits under Remove and
opens the five as buttons on the row, with Done. Each press is its own change,
said out loud and undoable. The food being edited stays in view even once it
is taken out of the section on show — it must not vanish from under the
finger mid-choice — and goes when Done is pressed. Its meals are named under
its name, where Remove already makes that row 44px tall, so they cost no
height. The section buttons flip `aria-pressed` in place through `pressSec()`
rather than calling `render()`, because the meal's name box keeps no draft and
would snap back to its default — the checklist ticks' rule.
