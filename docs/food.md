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

**Your pantry first, the food finder second.** The pantry is the one list
left on the phone, and it answers with no network and no account. Everything it
can't answer goes to the food finder. An earlier version of this rule was
"offline table first, Claude second", and it broke twice the same way: a code
path that asked "is Claude available?" *before* trying the table. The same trap
is still there for the pantry — if you write `if (finder())`, ask whether the
pantry should have run first.

**The food finder: a free AI, with nothing to set up.** The owner's call on
2026-10-14: rather than a list the app ships, a small agent finds the numbers
for whatever was eaten. He accepted that this needs a connection — "99% of
people have internet" — so the built-in table (`FOODS`), the USDA food library
(`vendor/usda/foods.js`, `tools/make-foods.py`) and the restaurant menus
(`vendor/menus/`, `tools/make-menus.py`, `tools/menus/`) were removed in b63
rather than kept as a fallback. And it has to work the moment the app is
opened: **no key to paste, no sign-in** — his words, after seeing a first
version that asked for a key in Settings.

**The key lives in a relay, never in the app.** The repo and the Pages site
are public, so a key in `mntl-dt.html` would be copied out, its free
allowance used up and the key shut off (and `TEAM.md` forbids keys in the repo;
`finder` fails the build if one appears). So the app asks `relay/worker.js`, a
Cloudflare Worker on the free plan that the owner deployed once with the Gemini
key as its secret (`relay/README.md` has his steps). `RELAY_URL` is its
address; `window.IRON_LEDGER_RELAY` overrides it, for the suites' stand-in or
`wrangler dev`. A copy opened from disk doesn't ask it at all: such a page has
no web address, which the relay refuses, so it says the finder isn't available
in it rather than failing every time — and that keeps the suites, which open
the app from disk, off the network. Why not straight to a model from the phone: only Gemini's and
OpenRouter's free services answer a web page at all (NVIDIA's, which the
team's Hermes agents use, sends no CORS headers — checked 2026-10-14), and
either would need a key on the phone. Hermes on the owner's PC is out of reach
from a phone. Supabase was the other host considered; its free projects pause
after a week unused, which would stop the finder for everyone.

**Ask an agent asks before it first sends (b79).** Apple's guideline
5.1.2(i) (November 2025) wants a clear yes before anything goes to someone
else's AI, and Gemini's free tier may keep what it is sent, use it to improve
Google's products and have people read it. So the first time a question would
go to the relay, a sheet (`#aiSheet`) says what is sent — what you type and
your country — and what Google may do with it, with *Allow and ask* and *Not
now*. The question waits on the answer (`needAi()`); *Not now* sends nothing,
and the review opens with the food as *needs numbers* and *Nothing was sent*.
It asks again the next time, because a press that did nothing would read as a
dead button. A food the pantry knows never asks: nothing would be sent.
Settings → *Ask an agent* shows when it was allowed and turns it off; off
takes effect at once, and a question already on its way is called back and its
answer not used. *On* there goes through the same sheet. `relayFind()` itself
refuses unless the age check and the permission are both yes, so no way in —
the words box, a pending row's *Tap to estimate*, *Find it again*, *Look up
this name's numbers* — can reach the relay around it. Claude, inside the
Claude viewer, is not asked about: it is not Google, and it is only reached
when the relay can't be. `agecheck` covers all of it. The review under every
answer says *AI answers can be wrong; check the label where there is one*
(b80), as the Terms (section 4) do.

**Only the words describing the food are sent**, with the country chosen on
the form: `{food, region}`, nothing from the day, a goal or a pantry name, no
key and no cookie. The relay builds the prompt itself, so it cannot be used as
a general-purpose AI; browsers on other websites get no answer (only the Pages
origin and a phone on the home wifi do — though a script can claim any origin,
so that is not a lock), 20 lookups a minute per address (`PER_PHONE`), at most
2 KB a question and 300 characters of food, and nothing but food rows go back.
The key is on Gemini's free tier (its Google project has no billing account,
which the relay cannot check), so abuse can at worst use up the day's
allowance; with billing on it would be paid for, so a budget cap comes first. `tests/relay.py` runs the Worker in Node against a
fake Gemini and checks every one of those.

**A small agent, not one question.** The relay asks (`estimatePrompt()`:
split into foods, grams, kcal, protein, carbs, fat, and a `basis` — the
brand's published figures, typical values, or a rough guess), then checks each
answer the way `make-menus.py` used to check a copied line: calories should come
within 20% (or 40 kcal) of 4·protein + 4·carbs + 9·fat (`addsUp()`). Anything
that doesn't is asked about once more, quoting the gap (`recheckPrompt()`), and
the second answer is kept only if it adds up better. The app checks every
answer again (`modelItems()`), so a slip that survives is flagged on its row —
*These calories don't match its protein, carbs and fat* — never quietly
logged. A drink with alcohol is the honest exception and the flag says so. The
relay reads Gemini's reply leniently: free models wrap JSON in a code fence or
a sentence, and that must not read as a failure. The models are aliases, so a
renamed model does not break the finder, and they are a list (`MODELS`), see
*When it can't answer* below.

Inside Claude, a published artifact cannot reach the internet, so the relay is
out of reach and Claude (`sample`) answers instead, with the app's own copy of
the prompt and the same check-and-ask-again loop (`askClaude()`). Keep the two
prompts in step. Claude is only the fallback for *unreachable*: a relay that
answers "busy" says so rather than being quietly swapped for Claude.

Answers are `ai` rows tagged *AI · typical*, *AI · brand's figures* or *AI ·
rough guess*, with a gram basis whenever the AI gave a weight, so the portion is
correctable like a pantry food weighed in grams; a weight that was typed comes
back in its unit. They are marked as estimates in the ledger, like Claude's.
The review reads in the order things were typed (`inOrder()`), so it can be
checked against what was typed. When the pantry knew none of it, the finder
gets the words exactly as typed, because the splitter tears dish names apart
("mac and cheese"); `joinedAliases()` now protects the pantry's own names
instead of the table's.

**When it can't answer, the food waits.** Every failure has a code from the
relay and its own words (`finderMessage()`): busy or at today's free limit,
too many lookups from this phone, too many words at once, a problem on the
relay's side, no connection, too slow (45 s), a reply that wasn't numbers. The
review still opens, with the pantry's rows answered and the rest as *needs
numbers* placeholders, each with *Find it again*, which asks about that row
alone (`reaskRow()`). A copy of the app with no relay and no Claude sends
nothing anywhere and says the finder isn't available in it. Behind a code, the
relay logs Gemini's own status and message, with the key cut out (`note()`,
read with `npx wrangler tail`): on its first day every lookup came back
`failed`, and the code alone could not say why. The log said Gemini 503, "This
model is currently experiencing high demand", five times in a row — the free
tier turning people away from its busiest model — and then "quota exceeded …
limit: 20" a day for that model, while `gemini-flash-lite-latest` answered every
lookup. Each model has its own free daily allowance, so the relay works down
`MODELS`, lightest first (`gemini-flash-lite-latest`, `gemini-flash-latest`,
`gemini-3.5-flash-lite`): a model that is overloaded, out of allowance, slower
than 12 seconds or retired hands the question to the next, and one out of
allowance is skipped until Google says it's back (`restFor()`). The app hears
*busy* only when every model has said no. The last one is a pinned model, not
an alias, and pinned models retire: on 2026-10-19 `gemini-2.5-flash-lite`
answered 404 "no longer available to new users" while both aliases were
overloaded, so four lookups in six (100 g brown rice) came back *busy*. When
the log shows a 404, replace that model in `relay/wrangler.toml` and redeploy.

The suites never reach the relay or a real AI. `tests/fakeai.py` stands in for
the relay, answering from a small fixture of foods the way the relay would
after a careful model, recording what was asked, and letting a check make it
busy, wrong or unreachable.

**Grocery brands: what a barcode is found in, and a download the owner
chooses.** A scanned barcode is a number; the AI cannot turn it into a product,
and guessing would be the confident wrong answer. So barcodes stay on a list,
the one shipped list left. `tools/make-brands.py` turns USDA's Branded Foods (about 3 GB of CSV) into
`vendor/usda/brands-<release>.js`: US products not discontinued, the newest
submission per barcode, with calories, protein, the label's serving and every
barcode a product is sold under — about 390,000 products, 35 MB, under 8 MB as
Pages serves it. That is too big to land on a phone unasked, so it is never
precached: the scanner offers *Download grocery brands · 8 MB* the first time,
Settings → *Grocery brands* offers it too (and removing it), and
`store.brandsOn` remembers the choice. It is a fact about this phone, so a
restore does not carry it.

It is held as **columns, not records**: one lowercase `brand|name` line per
product in a single string, searched with `indexOf`, plus arrays of numbers
beside it. Half a million small objects never exist. The generator folds
everything to plain ASCII on purpose — one accented letter anywhere makes a
browser hold the whole string at two bytes a letter. Searching it by typed
words (`searchBrands()`) went with the food library panel in b63; the finder
answers typed words now.

A scanned product is a `label` item (*brand label · 2026*): servings as the
label states them, or 100 g said as such. It is the published number, so it is
not marked as an estimate in the ledger.

**The service worker keeps it across builds.** It lives in its own cache,
`iron-ledger-data`, which `activate` does not delete with the old build's
shell; otherwise every update would make every phone download 8 MB again. The
release is in the file name, so new USDA data is a new file. `pwa` checks it
is not precached, survives an update, and answers offline.

**Restaurant menus** were a sheet of seven chains' own published numbers,
from b61 until the food finder replaced them in b63. Ask the finder for
"a medium McDonald's fries": it answers with the chain's figures where it knows
them, and tags the row *brand's figures*.

**Barcodes: in the web app.** *Scan a barcode* is a tab of its own in *Don't
know the numbers*, whose one button opens the scanner, and a quick button again
under a review, so a package can join a meal being checked. Camera, photo, or
the number typed. The
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
`carb`/`fat` when the food's numbers include them: the food finder (it is
asked for both), the brands, Claude's answers, the pantry (optional fields)
and the numbers form (optional fields). **A row
without them is counted as missing, never as zero**: the day's line reads
*Carbs 210 g · Fat 64 g · 2 foods without them*. Typing over a review row's
calories or protein lets its carbs and fat go, because they would no longer add
up to it; changing its weight scales them. The kettlebells fill toward the
carbs and fat targets in the goal; **with neither set, a card under the bar
still shows the day's carbs and fat** and opens the target at carbs
(`#kbSetGoal`). Drawing nothing there read as a screen that had not caught up
(the owner's video, b67). Settings says where both carbs & fat and water show
up, and switching either on from another tab says so on the bar, because the
screen behind the sheet has neither.

**Water, body weight, and the goal calculator.** Water is a Settings switch
too: a line on Macros (`d.water`, millilitres, shown in oz or ml) that patches
in place like the checklist. Body weight is a card on the Log tab (`d.bw`, in
pounds, shown in lb or kg) with a trend line — each day the trend moves a
tenth of the way to the scale — and an undoable *Log today*. The target editor
has *Work it out from your height and weight*: Mifflin-St Jeor × activity,
minus or plus for the aim, protein at a gram per pound, the working shown. It
fills the two fields; *Save target* still decides. Calories never go below
1,200 (women) or 1,500 (men) without saying so. Under the working it says
*Estimates only, not medical advice* (b80), which is what the Terms say of
every target. Since b81 the same arithmetic (`calcNumbers()`) runs in the
profile's *Your goals*, from the profile's boxes; the calculator here takes
its age from the birth date and its equation from the profile (Other picks
one), and *Use these numbers* writes into `store.profile`, never over it
(`docs/architecture.md`, *The profile sets the goals*).

**Meals read through, never store.** A meal is `{id, note, items:[...]}`. Its
calories and protein come from `rowCal()`/`rowPro()` summing the items on every
draw — never written onto the meal — so the day total cannot drift from its
contents no matter how much you combine, split, take out, and undo. Meals never
nest; combining flattens. `tidyMeals(d)` is the single rule that a meal of one
or zero items dissolves back into plain rows — call it after anything that can
remove an item. `locate(d, id)` finds a row at the top level *or* inside a meal;
use it anywhere food is looked up by id.

**Three ways in, each named under its picture (b71).** The bottom bar on
Macros is three buttons: *Log numbers* (a pencil — writing down numbers you
have), *Ask an agent* (a # — numbers you don't know) and *Scan* (a barcode).
The owner found the old bar confusing: a pencil beside *What did you eat?*, a
bare # and a barcode said nothing about which was which, and the pencil opened
the box for numbers you *don't* know while the # opened the one for numbers you
do — the opposite of what he read them as. So each says its name, and *Ask an
agent*, the one used most, is the filled one in the middle and a little wider.
*Scan* opens the barcode reader itself rather than a box with a scan button in
it.

*Ask an agent* is one plain-words box, labelled *What did you eat?*, with the
shorthand as its example ("Half a protein coffee, 6 oz sirloin and a cup of
rice"). It used to be one of three tabs (b64) beside *Scan a barcode* and *Have
the measurements*, a table of Amount / Unit / Food rows that opened by default
because a blank box tells a first-timer nothing. The owner asked (b71) whether
that table still ran through a downloaded list, which would make it worth
keeping as an offline mode. It didn't: the lists went in b63 (below), and the
table only composed the same sentence (`6 oz chicken breast & 1 cup rice`) and
sent it to the same pantry-then-finder path. So it went, with the tabs, and the
example and label carry what the table's field names used to. Nothing was lost
offline: the pantry still answers first with no connection, and scanning works
offline once grocery brands are downloaded.

Two things that are easy to get wrong here. `estDraft` empties on commit —
leaving the words in the box is how someone logs the same meal twice without
noticing. And pressing *Work out the macros* with nothing typed sets `estHint`
and says so; doing nothing at all would read exactly like a dead button.

**Both ways in are folded until asked for.** The owner, from real use: the
two forms under the checklist made Macros twice the height of a phone. They are
buttons now, named for when you would reach for each — *Log numbers* and *Ask
an agent* since b71 (see above). Each opens its box directly under itself
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
whose words and review are kept. A tap on the dimmed page does the same. After
a successful add a pop-up goes and the confirmation above the buttons says
what went in. That confirmation is now also set when an estimate is committed,
which used to go in without a word: in place the rows appearing was the only
sign, and behind a closing pop-up even that was hidden.

The forms only exist after a press now, which is this project's known blind
spot, so the walks in `mobile`, `hittest` and `handoff` visit Macros three
times: folded, and with each box open. Each says so if its box fails to open,
rather than passing on nothing. `darkcheck` opens both boxes and the scanner,
and `handoff` measures both first fields for 44px and the 16px zoom rule.

The suites feed the resolver through the words box, so the ones testing food
matching rather than entry call a local `words(p)` helper first. It opens
*Ask an agent* if it is folded; `way(p, "numbers")` opens the numbers box.

**A row is corrected in place, by tapping its name.** Asked for by the owner
(b65), who logged "Pure protein bar" meaning "Built Protein bar" and could only
delete it and start again. A plain row's name is a button (`.nm-btn`, with a
teal *Edit* as its marker) that opens a box under the row the way a meal opens
(`rowEditing`, `rowEditHtml()`): the name, calories and protein, carbs and fat
when they are on. *Save* says what it did on the undo bar — *Renamed to …* or
*Updated …* — and Undo puts the old row back whole (`commitRowEdit()`). Save
acts on the press, like *Add to ledger*, because the keyboard is open when it
is tapped. A rename keeps the row as it was otherwise, `est` included; numbers
typed over are the person's own, so `est` and `pending` go, and carbs and fat
go too unless their fields were on screen to be corrected — the rule for typing
over a review row. A row left with neither calories nor protein is refused,
said in the box without a redraw so what was typed stays — except a waiting
row, whose name can be fixed before it is looked up. A different food has different numbers, so *Look up this name's
numbers* sends the new name through `runEstimate()` with the row as
`replacing`, exactly as *Tap to estimate* does — pantry first, the review
opens, and the answer takes the row's place when added. A finder row's name
reads *food · amount*; it is asked as *amount food*, the way it would be typed.

The name is still where a row is held to drag it: the drag's guard lets
`.nm-btn` through, and a release after a hold is swallowed so it doesn't also
open the box. Fields never start a drag, since holding one is how a phone
moves the cursor. Meals are not edited by this box; *Name this meal* and *Take
out* are theirs. `meals` and `finder` check all of it.

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
