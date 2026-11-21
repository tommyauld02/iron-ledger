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
a sentence, and that must not read as a failure. Nor must a garbled number:
the lite model answered *a big plate of spaghetti bolognese* with
`"carbs":95id` three times in eight (2026-11-16), so a number with letters
stuck to its end is read as the number (`readJson()`), and a reply that still
can't be read hands the question to the next model rather than failing the
lookup. It garbles words too: on 2026-11-17 the live relay answered *55 pieces
of sushi* with the amount "55 pieces" and two Burmese letters after it, which
went to the phone as the row's amount. So when what was typed is in Latin
letters, letters of any other writing system are taken out of the names,
amounts and note that go back (`unstray()`). Accents stay (jalapeño, phở),
and so do Greek letters, for the µ in a unit. A question typed in another
writing system is left exactly as the model answered it, since there those
letters are the answer; and a name that would be emptied is left as it came,
because the app drops a row with no name. Which models are asked is *Two
lists of models* below.

**Better numbers for a count or a vague amount (b101).** The owner's ask
(2026-11-16): the finder should do what a search does for "55 pieces of
sushi", without leaving the app. Measured that day on the live relay, named
restaurant food was already right (20 McNuggets, 2 Big Macs and a large fries,
a Chipotle bowl all matched what the chains publish), but a count or a vague
amount was not: the same question came back as 1,650 kcal and then 2,200, 30
chicken wings as 1,410 (a restaurant lists 2,200 to 3,300), and *all you can
eat korean bbq, ate a lot* came with two pints of beer nobody typed. Three
things changed, each measured on the same sixteen foods:

- *The prompt.* A stated quantity is used however large ("55 pieces is 55
  pieces, never a normal serving"), a vague amount still gets real numbers
  with the assumption in the note, a mix with no kind given is the average of
  the usual assortment, and nothing is listed that the text did not name.
- *A little thinking* (`EFFORT`, `reasoning_effort: "low"`). The lite model
  then gave 2,090 kcal for the sushi twice running.
- *A stronger model when one is free*, see *Two lists of models*.

After: sushi 2,590 kcal and 110 g protein, wings 2,895 and 255 g, and the
named food as exact as before. A food that was counted says what one of it
came to under the answer, *55 at about 47 kcal and 2 g protein each*, worked
out from the totals (`answer()` in the relay, `eachNote()` in the app for
Claude's answers), so the total can be checked against the piece it stands on.
The model is asked for that count as the last thing in each row.

Two things were tried and dropped, so they are not tried again blind. Asking
for ONE piece and multiplying in the relay fixed the sushi and broke named
food: a 20-piece box of McNuggets is published as a box (830 kcal), and built
from a piece it came to 870 and 950; *half a large pepperoni pizza* came back
as one slice. Asking for the piece first and the total after pushed the lite
model's wings to 4,200 to 5,100 kcal. The lite model's totals for a usual size
are better than its idea of a piece. And Google Search grounding, the obvious
way to match a search, is not on the free tier for any Gemini 3 or 4 model
(pricing page and the owner's own limits page, 2026-11-16): it needs billing,
which is the owner's call (*Known and deliberate*).

**Two lists of models, asked at once (b101).** Each Gemini model has its own
free daily allowance, and the better the model the smaller: read from the
owner's limits page (ai.dev/rate-limit, 2026-11-16), the two lite models get
500 lookups a day each and every stronger one 20. The stronger ones are
plainly better where the lite one guesses (the wings above), but they are also
the ones the free tier turns away or keeps waiting. So `relay/wrangler.toml`
has two lists and the relay asks down both at the same time (`ask()`):

- `BEST`, the stronger models (`gemini-4-hydrogen`, then
  `gemini-3-flash-preview`), whose answer is used if it comes inside
  `BEST_WAIT`, 8 seconds. With light thinking they answer in 2 to 6.
- `MODELS`, the lite ones (`gemini-flash-lite-latest`, which is Gemini 3.5
  Flash Lite, then `gemini-3.1-flash-lite`, then the big Flash as a last
  resort), whose answer is usually in hand in a second or two and is used when
  no best model was in time.

So a lookup is never worse than it was before there was a `BEST`, and never
waits more than 8 seconds for nothing. The busiest day in the four weeks
before this used 40 lookups, and the two best models allow 40 between them, so
for now most answers come from a best model; past that, and whenever they are
busy, the lite ones answer. Left off `BEST` on purpose: Gemini 3.8 Flash
(`gemini-flash-latest`) answered none of thirteen lookups in 28 seconds each
that day, and Gemini 3.6 Flash was right but took 12 to 21 seconds every time.
Gemma 4 has 14,400 a day but was overloaded on every try, so it is not on a
list either. Every lookup now uses one lite request as well as a best one.

**A best model that says nothing is not waited out (2026-11-17).** The day
b101 went live, Gemini 4 Hydrogen answered nothing at all: not in 28 seconds,
not for "a banana", with or without the thinking setting. It did not say no,
which would have handed the question on at once; it said nothing. Asked in
turn, it used up all of `BEST_WAIT`, Gemini 3 Flash (answering in 1.4 seconds
that same hour) was never asked, and every lookup took 8 seconds to come back
with the lite answer: the wait of the new relay and the numbers of the old
one. So the best list is asked with a head start each (`askBest()`):

- A best model that has said nothing after `HEAD_START`, 4 seconds, is left
  running and the next is asked beside it. The first good answer is used and
  whoever is still running is told to stop, which is not logged as a failure.
- 4 seconds, because a healthy best model answers in 2 to 6: most of the
  time the first is the only one asked, and the second's 20 a day are not
  spent beside it. A silent first model costs 4 seconds, then, not 8.
- A model passed while silent, or silent to the end of its time, rests for
  `SLOW_REST`, ten minutes, in the same list a spent allowance rests in. The
  lookups after it go straight to the one that answers (1.1 seconds, measured
  the same day), and neither wait for the silent one nor spend its allowance.
  That memory is the Worker instance's, so a fresh instance pays the 4
  seconds once and learns again.
- A model that says no outright (busy, out of allowance, gone, unreadable)
  still hands on at once, as down the lite list.
- Hydrogen stays first. On the owner's example it gave 110 g of protein for
  55 pieces of sushi, inside what a search gives (2 to 4 g a piece), where
  Gemini 3 Flash gave 83. The owner asked for the most accurate number.

**A lookup has 30 seconds (b101).** The app waits 45 (`RELAY_WAIT`) and then
says it took too long. Three models at 12 seconds each, asked twice when the
numbers needed a second look, could run to 72, and on 2026-11-16 a lookup that
did answer took 47: the phone had given up on an answer that then arrived for
nobody. The relay now has a budget (`BUDGET_MS`): no model is started with
under 3 seconds of it left, none is given longer than what is left, and the
second look is skipped when there is no room for it.

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
a list: a model that is overloaded, out of allowance, slower than 12 seconds,
retired or unreadable hands the question to the next, and one out of allowance
is skipped until Google says it's back (`restFor()`). Since b101 there are two
lists, asked at once (*Two lists of models*, above); the app hears *busy* only
when every model on both has said no. Until b101 the list was
`gemini-flash-lite-latest`, `gemini-flash-latest`, `gemini-3.5-flash-lite`,
and the third was the model the first alias already pointed at: the same
allowance, asked twice. Most names on the lists are pinned models, not
aliases, and pinned models retire: on 2026-10-19 `gemini-2.5-flash-lite`
answered 404 "no longer available to new users" while both aliases were
overloaded, so four lookups in six (100 g brown rice) came back *busy*. When
the log shows a 404, replace that model in `relay/wrangler.toml` and redeploy;
`gemini-3-flash-preview` is a preview and will be the first to go.

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

**The calculator, reviewed (b107).** Asked for by the owner: set the goal
from what a person prefers. `calcNumbers()` takes options, the same in both
places it runs (the profile's *Your goals* and the target editor's *Work it
out*):
- **Seven aims**, lose 2 lb a week to gain 1 (`AIMS`), 500 kcal a day per
  pound a week. Past 1% of the weight a week, the working says it is hard to
  keep muscle at that pace.
- **Protein by choice**, 0.7, 0.85 (the default) or 1 g a pound
  (`profile.proPer`). Losing toward a goal weight lower than today's, it is
  per pound of the goal: 1 g per pound of today's weight, the rule until
  b107, told a 260 lb person to eat 260 g.
- **Carbs and fat** from a style (`profile.cfStyle`: Balanced 30% fat,
  Lower carb 40%, Higher carb 20%), only with Carbs & fat shown; protein
  first, fat its share, carbs the rest. *Use these numbers* fills all four.
- **Body fat**, when there is a reading: the resting burn from lean mass
  (Katch-McArdle, 370 + 21.6 × lean kg) in place of Mifflin-St Jeor.
- **The real burn**, when the log has one (below): it replaces the formula's
  whole guess, and the working says so (*From your log … The formula
  guessed …*).

**Body fat % (b107).** In the owner's words: *"the option of filling it if
known, or if it wants to be guessed, but also including how one can figure
it out, or examples of what different percentages look like"*. An optional
box under the height in Settings → You, and *Don't know it?* opens a sheet
(`pfBfSheetHtml()`) with three ways:
- **Tape measure**: waist and neck (and hips, for the female equation) in the
  weight's unit, and the height already in the profile; the US Navy method
  (`navyBf()`), within about 3–4% of a scan. *Use 18%* fills the box.
- **By look**: six drawings a sex (`torsoSvg()`, drawn from numbers: no
  photos, nobody's body), about 10% to 35%+ for men and 15% to 40%+ for
  women, each with plain, neutral words. Within about 5%, and it says a tape
  gets closer.
- **Other ways**: a DEXA scan, a gym body-scan machine, a smart scale,
  calipers and the tape, each with how close it gets.
A reading is the day's, like a weigh-in (`d.bf`, `d.bfBy`: typed, tape or
look), so it has a history; `latestBf()` is used. The box says where it came
from and when (*From your tape measure, Nov 20*), so a guess is never passed
off as a scan. Emptied and saved, `profile.bfOff` stops the app using any,
and the readings stay. 3 to 60, or it says so. Settings → You's line names
it. Apple Health could fill it later, in the same store build as Active
Energy.

**Your real burn, from the weekly summaries (b107).** The owner: *"to have an
accurate calculation you need data expanding over a week ... let's take the
data from a user's weekly summary"*. One week alone is too noisy (a pound of
water is 500 kcal a day over a week), so `realBurn()` takes the three whole
weeks ending with the last one summed up: the average eaten on the days
logged, plus the pounds lost a day × 3,500, from a straight line through the
weigh-ins. It needs 18 of the 21 days logged (a forgotten day would look like
eating nothing) and 6 weigh-ins, one in the first week and one in the last;
a calorie target changed inside the three weeks, or lowered in the week
before them (the quick loss then is mostly water), means waiting. It shows on
the Log's body weight card (`#bwReal`), in the wrap-up's Body weight section,
and in the calculator.

**When the weight isn't moving, a target to try (b107).** The owner: *"if a
user is not getting closer to their weight goal or simply not losing weight,
let's suggest a calorie goal to them based on what they had vs. what they
should lower it to"*. `burnAdvice()` speaks when the weight moved less than
half the aim's pace toward the goal (the profile's aim; with none, the goal
weight at a pound a week). It says what was eaten and a new target, the real
burn less 500 a pound a week, but a step of 300 at most and never under
1,500 (men) or 1,200 (women). Eating over the target is said instead, with
nothing to change. Losing faster than 1% of the weight a week gets the other
line, to eat a little more. It is a daily line on Macros (`docs/ui.md`) with
*Use 1,970*, which sets the target from today with Undo; nothing changes
without the tap. Put away or used, it waits three weeks. `tests/calc.py`
covers all of this.

**Meals read through, never store.** A meal is `{id, note, items:[...]}`. Its
calories and protein come from `rowCal()`/`rowPro()` summing the items on every
draw — never written onto the meal — so the day total cannot drift from its
contents no matter how much you combine, split, take out, and undo. Meals never
nest; combining flattens. `tidyMeals(d)` is the single rule that a meal of one
or zero items dissolves back into plain rows — call it after anything that can
remove an item. `locate(d, id)` finds a row at the top level *or* inside a meal;
use it anywhere food is looked up by id.

**Three ways in, each named under its picture (b71).** From b98 the three are
on the plate's sheet: the plate above the tabs says *Log food* and brings them
up, *Ask an agent* first and filled, each with a line under its name
(`docs/ui.md`, *The plate*). What follows is why there are three and what each
is, which has not changed. Until b98 the bottom bar on
Macros was three buttons: *Log numbers* (a pencil — writing down numbers you
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
with the cursor in the first field, the way the set sheet opened for a new
set until b100. One is open
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
