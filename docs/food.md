# Logging food

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

**Reading a nutrition label.** Inside the Claude viewer the `sample` capability
reads the panel and can name the product. On the hosted copy there is no
capability, so the panel is read on the device with Tesseract from
`vendor/tesseract/` — 14.4 MB, and **the app's one dependency**. It is loaded
lazily: nothing is fetched until the button is pressed, so the offline core
stays at 150 KB, and the service worker keeps it afterwards so later scans work
offline. It is deliberately absent from the worker's precache list.

The calorie figure is found by **how it is printed**, not by reading order. It
is set far larger than anything else on a panel, and OCR splits it into
separate digit-words and scatters them through the text — a plain text scan
pulled *609* out of a blurred panel, which is exactly the confident wrong
number rule 3 exists to stop. `readPanel()` takes the tallest numeric words
sitting on one line and reads them left to right.

Nothing it cannot read is guessed. A panel carries plenty of numbers larger
than the calories — sodium in mg, carbs, every % daily value — so a "take the
biggest number" fallback would log sodium. Blank fields go into the form and
the person fills them, which is safe because the reader fills the *form*, never
the ledger. **The product name is not on the panel** — that is front-of-pack
branding — so it is always left empty.

The vendor files are downloaded, not written: the wrapper and worker from
tesseract.js 5.1.1, the SIMD LSTM core, and the standard English model. The
small `tessdata_fast` model is a third of the size and was rejected — it missed
protein on a blurred panel, and protein is half of what this app tracks. Only
the SIMD core is shipped, which needs iOS 16.4 or newer.

**Offline answers first, Claude second.** The built-in ~115-food table and the
user's pantry resolve most entries with no network and no account. `sample` is
the fallback for what they can't handle. This has broken twice in the same way:
a code path that checked "is Claude available?" *before* trying the offline
table, so the offline capability was silently dead on the phone. If you write
`if (sampleFn)`, ask whether the offline path should run first.

**The food library: USDA's data, shipped with the app.** The owner wanted an
answer for anything eaten, such as a McDonald's meal or a home plate of rice,
veg and steak, with no internet and no cost. USDA FoodData Central is public
domain, so `tools/make-foods.py` turns three of its sets into
`vendor/usda/foods.js`: Foundation (2026), SR Legacy (2018, which has every
cut of meat raw and cooked and a fast-food group with McDonald's, Wendy's,
Applebee's…) and FNDDS (2024, foods as eaten, with typical portions such as
"1 item"). It keeps the name, kcal and protein per 100 g, and up to four
portions per food: 13.5k foods in 1.5 MB, about 0.3 MB as Pages serves it.
**Never hand-edit it**; re-run the script. The service worker precaches it,
so a lookup works offline from the first one and sends nothing anywhere.

It loads with a `<script>` tag on first use (`loadLibrary()`), not `fetch()`,
because a page opened from disk cannot fetch a file beside it, and the suites
open the app from disk. In the artifact copies there is no `vendor/`, and the
panel says it could not be opened rather than spinning.

**A partial match says so.** "Cava harissa avocado bowl" used to log a 240 kcal
avocado, because `matchIn()` takes the longest known name found anywhere in
what was typed. `matchAlias()` now also returns which name it was, and
`missedWords()` lists the typed words it did not cover; cooking words and
sizes are neutral, and the food's own name counts as covered. A review row
with missed words, or one that matched nothing, says what happened and offers
*Look it up in the food library* (and *Keep this match*). `searchLibrary()`
ranks by how many typed words a name contains, then the plainest name; raw
and baby food sink unless asked for. `libPortion()` turns the typed amount
into grams: a typed weight, a size typed ("medium fries" means the medium
portion), a unit named in a portion ("1 cup"), or the typical portion times
the count, or 100 g said as such. A pick replaces the row with a `usda` item
that has a gram basis, so its weight is editable like the built-in table's.
Its tag carries the data's year (`srcLabel()`), because the 2018 fast-food
numbers are older than the chains' current recipes. It lands in the review,
never straight in the ledger.

Two old bugs went with it. A food named with *with* — "Quarter Pounder with
cheese" — had only "quarter pounder" as an alias, so typing its full name
split on *with* and logged a separate cheddar. `joinedAliases()` now protects
every food's own name too. And "2 medium fries" read back as "2 eachs".

**Grocery brands: step 2, and a download the owner chooses.** The library
answers "rice"; it does not answer "the Great Value milk in my fridge".
`tools/make-brands.py` turns USDA's Branded Foods (about 3 GB of CSV) into
`vendor/usda/brands-<release>.js`: US products not discontinued, the newest
submission per barcode, with calories, protein, the label's serving and every
barcode a product is sold under — about 390,000 products, 35 MB, under 8 MB as
Pages serves it. That is too big to land on a phone unasked, so it is never
precached: the library panel offers *Download grocery brands · 8 MB* under
its results, Settings → *Food library* offers it too (and removing it), and
`store.brandsOn` remembers the choice. It is a fact about this phone, so a
restore does not carry it.

It is held as **columns, not records**: one lowercase `brand|name` line per
product in a single string, searched with `indexOf`, plus arrays of numbers
beside it. Half a million small objects never exist. The generator folds
everything to plain ASCII on purpose — one accented letter anywhere makes a
browser hold the whole string at two bytes a letter. `searchBrands()` starts
from the rarest typed word and ranks like the library does. A brand counts as
*named* only on whole words, and all of its words or a long first one: "rice"
is not Riceland and "big mac" is not the Big Y supermarket, while "kirkland"
is still Kirkland Signature. The panel puts whichever group matched more of
what was typed first, and on a tie the brands only when one was named.

A brand pick is a `label` item (*brand label · 2026*): the typed weight if one
was typed, otherwise servings as the label states them — "2 chobani greek
yogurt" is two of its containers — or 100 g said as such.

**The service worker keeps it across builds.** It lives in its own cache,
`iron-ledger-data`, which `activate` does not delete with the old build's
shell; otherwise every update would make every phone download 8 MB again. The
release is in the file name, so new USDA data is a new file. `pwa` checks it
is not precached, survives an update, and answers offline.

**Restaurant menus: step 4, from the chains themselves.** *Don't know the
numbers* opens with two quick buttons, *Restaurant menu* and *Scan a barcode*,
at the top of the form and again under a review. The menu sheet lists the
chains; a chain lists its items by group, each with its options (sizes, counts,
proteins) as buttons; a tap adds to an order pinned to the foot of the sheet
(`#menuTray` is sticky — sticky has to sit on a direct child of the scroller,
which the first version got wrong), and *Add to the estimate* puts the order in
the review as one meal. The order is kept while the sheet is closed.

The data is `vendor/menus/menus.js`, built by `tools/make-menus.py` from one
text file per chain in `tools/menus/`, each headed with its source and the date
it was read: McDonald's (its product pages), Chick-fil-A (its nutrition page),
Taco Bell (its official Nutritionix table), Chipotle, Popeyes, In-N-Out and
Five Guys (their PDFs). **Every number is the chain's own.** Five Guys
publishes parts, not burgers, so its burgers are added up from its parts and
say so in their names. The generator refuses a line whose calories do not
roughly equal 4·protein + 4·carbs + 9·fat, which catches a copying slip.
Wendy's, Subway, Raising Cane's and Panda Express are not in yet: Wendy's site
blocks automated reading and the others could not be fetched the night this
was built. Fountain drinks are as each chain lists them (McDonald's without
ice). A pick is a `menu` item: counted, not weighed, tagged *restaurant menu ·
2026*, and not marked as an estimate in the ledger — nor is a `label` item.

Typed words find menu items too (`searchMenus()`), as a *Restaurant menus*
group in the food library panel, first when the chain was named: "mcdonalds
big mac" is today's Big Mac before USDA's 2018 one.

**Barcodes: step 3, in the web app.** Camera, photo, or the number typed. The
reader is zxing-cpp compiled to WebAssembly (`vendor/zxing/`, zxing-wasm 3.1.4,
MIT/Apache-2.0), its engine shipped as base64 inside a script so it loads from
disk like everything else; it lives in the service worker's data store with
the brands, and is fetched when the brands are so the first scan works
offline. Codes are looked up in the brands' barcode column (`brandByUpc()`,
leading zeros dropped, UPC-E expanded), **your pantry first**. Not found, it
says so and offers *Save it to your pantry*, which opens the form carrying the
barcode (`upc` on the pantry entry), so the next scan finds it. On the Pantry
tab, *Scan its barcode* fills the form from the label instead. The camera's
answer only counts while it is still starting: a number typed meanwhile used
to be wiped by a late "no camera". Leaving the tab stops the camera.

**Carbs and fat: off until chosen.** Settings → *Carbs & fat*. Rows carry
`carb`/`fat` when the food's numbers include them: the built-in table (268 of
310 entries, matched to USDA where its kcal and protein agree with the
table's), the library and the brands (regenerated with both), the menus, the
pantry (optional fields) and the numbers form (optional fields). **A row
without them is counted as missing, never as zero**: the day's line reads
*Carbs 210 g · Fat 64 g · 2 foods without them*. Typing over a review row's
calories or protein lets its carbs and fat go, because they would no longer add
up to it; changing its weight scales them.

**Water, body weight, and the goal calculator.** Water is a Settings switch
too: a line on Macros (`d.water`, millilitres, shown in oz or ml) that patches
in place like the checklist. Body weight is a card on the Log tab (`d.bw`, in
pounds, shown in lb or kg) with a trend line — each day the trend moves a
tenth of the way to the scale — and an undoable *Log today*. The target editor
has *Work it out from your height and weight*: Mifflin-St Jeor × activity,
minus or plus for the aim, protein at a gram per pound, the working shown. It
fills the two fields; *Save target* still decides. Calories never go below
1,200 (women) or 1,500 (men) without saying so.

**Meals read through, never store.** A meal is `{id, note, items:[...]}`. Its
calories and protein come from `rowCal()`/`rowPro()` summing the items on every
draw — never written onto the meal — so the day total cannot drift from its
contents no matter how much you combine, split, take out, and undo. Meals never
nest; combining flattens. `tidyMeals(d)` is the single rule that a meal of one
or zero items dissolves back into plain rows — call it after anything that can
remove an item. `locate(d, id)` finds a row at the top level *or* inside a meal;
use it anywhere food is looked up by id.

**The way in is a table, not a blank box.** "What did you eat?" over an empty
textarea tells someone opening the app for the first time nothing about what it
accepts — the owner said so, and he was right. Macros now opens on labelled
fields with examples in them, the shape the pantry form already uses: Amount /
Unit / Food, one row per item, `+ Add another`, and a datalist on the food field
carrying every name in `FOODS` plus the pantry, so "what does it know?" is
answered by typing rather than by guessing and being told no.

The plain-words box did **not** go away. It is what makes "half a protein
coffee" and "chicken and rice" work in one line, and it is faster once you know
the shape, so it sits behind *Or just describe it in words* and takes over the
form when opened. Swapping to it carries the table across as text — but never
over the top of words already in the box.

The table is a way to **compose** the same sentence, not a second code path:
`rowChunk()` turns one row into `"6 oz chicken breast"` and `rowsText()` joins
them with `&`, which is exactly what `splitItems()` already splits on. Pantry,
the built-in table and Claude resolve it unchanged. Every unit the picker offers
is a word `parseQty()` knows, so the picker cannot produce a chunk the parser
then shrugs at.

Two things that are easy to get wrong here. `estRows` empties on commit along
with `estDraft` — leaving the rows filled in is how someone logs the same meal
twice without noticing. And pressing *Work out the macros* with nothing filled
in sets `estHint` and says so; doing nothing at all would read exactly like a
dead button.

**Both ways in are folded until asked for.** The owner, from real use: the
two forms under the checklist made Macros twice the height of a phone. They are
two buttons now, named for when you would reach for each: *Log calories /
protein* ("You know the numbers") and *Don't know the numbers* ("Name the food
and how much — it works them out"). Each opens its box directly under itself
with the cursor in the first field, the way the set sheet opens. One is open
at a time, and pressing the open one folds it again. `logWay` is that state.
It is transient but survives redraws, so adding an entry leaves the box open
for the next one. Folded, a normal day fits on the phone without scrolling.

Two things keep folding from hiding a result. The *✓ Added* confirmation sits
above the buttons, not inside a box, because the pantry's `+` lands there too.
And an estimate that is working or waiting for review opens its box by itself,
because a pending row's *Tap to estimate* would otherwise run an estimate into
a folded box and look dead. Folding while one is showing puts it aside in
`estShut`, opening brings it back, and a new estimate opens the box again.

**How they open is a setting, because the owner wanted to try each.** Shown
pictures of a box opening in place and of the same box as a pop-up like the
set sheet, he could not choose, so Settings → *Adding food opens* offers *In
place*, *Pop-up* and *Mix* (`store.logOpen`, read through `logOpen()`;
`popsUp(w)` answers per box). Mix pops up the short numbers form and opens the
long estimate in place. The choice travels with a backup, and a box already
open changes at once when it is switched.

A pop-up is drawn **inside `#view`** like the in-place box, as a `.sheet`. That
is deliberate: the delegated Add and every handler wired after a draw reach it
unchanged, and there is no second copy of either form. Closing it is folding
it: *Cancel* on the numbers, which keep no draft, *Close* on the estimate,
whose table and review are kept. A tap on the dimmed page does the same. After
a successful add a pop-up goes and the confirmation above the buttons says
what went in. That confirmation is now also set when an estimate is committed,
which used to go in without a word: in place the rows appearing was the only
sign, and behind a closing pop-up even that was hidden.

The forms only exist after a press now, which is this project's known blind
spot, so the walks in `mobile`, `hittest` and `handoff` visit Macros three
times: folded, then with each box open. Each says so if its box fails to open,
rather than passing on nothing. `darkcheck` opens both, and `handoff` measures
both first fields for 44px and the 16px zoom rule.

The suites feed the resolver through the words box, so the ones testing food
matching rather than entry call a local `words(p)` helper first. It opens
*Don't know the numbers* if it is folded; `way(p, "numbers")` does the same
for the numbers box. `sweep` and
`estmeal` drive the table itself, because that is the front door now.

**Grams are the basis; the unit is only how it is shown.** The whole food
table is keyed per 100 g and every macro is derived from `it.grams`, so that
is what gets stored and nothing downstream has to know what unit you like.
`WEIGH` maps g/oz/lb to grams, `fromG()`/`toG()` convert at the edges, and
`store.wunit` is the standing choice — set it under *Weigh food in* on the
estimate form, or from the picker on any review row.

Two rules make it safe. **Switching a unit converts, it never re-reads**: 150 g
becoming 150 oz is a four kilogram chicken breast logged in one tap, so the
food stays the same size and only the reading changes; you then type over it if
you meant something else. And **a weight you typed comes back in the unit you
typed it in** — someone who entered "6 oz" and is shown 170 g has to do
arithmetic to check their own entry, so `resolveTable()` and `resolvePantry()`
carry the typed unit through as `it.unit`. A row with no unit of its own
follows `store.wunit`, which is why changing one row redraws the review rather
than patching one field.

The standing picker and a review are never on screen together — the review
replaces the form — so there is deliberately no "update the open review" branch
on it. Mid-review, the row picker is the way.
