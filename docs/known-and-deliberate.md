# Known and deliberate

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

- The goal bar's centre divider does not line up with the T chart's stem. The
  owner asked to leave that section alone; it is his call.
- Rest days are not painted red on the calendar. Offered, declined.
- Barcode scanning used to be the one genuine reason to go native. It is in the
  web app now (b61, zxing-wasm), so nothing found so far needs a native build.
- The food table is hand-built reference values, 310 of them, weighted towards
  what actually moves a calorie count: meats, grains, starches, fats, prepared
  meals. Produce is covered but deliberately not expanded — a stick of celery
  is not what breaks a day. Rebuilding it from the USDA FoodData Central bulk
  CSV is the open thread; live API calls are impossible from a published
  artifact anyway (CSP blocks all outbound fetch).

  Fast food is in there — 45 chain items, because "no time to cook" is when
  someone least knows what they ate. Those are stored the same way as anything
  else, per 100 g, with `k` derived from the published total and the serving
  weight so that one serving reproduces the total even if the gram figure is
  a little off. **Brand values drift** as chains reformulate; treat them as a
  close estimate, not a label reading. A counted item must carry `each` as
  *one piece*, not one box — a ten-piece nugget entry with `each: 162` turned
  "10 mcnuggets" into 4,201 calories.

  `tests/foods.py` guards it, because growing it broke twice in ways nothing
  else caught. Adding an entry after the last one killed the whole script — the
  final entry had no trailing comma. And `splitItems()` splits on the words
  "and" and "with" *before* matching, so "mac and cheese" resolved to cheddar;
  aliases containing those words are now stitched back together across the
  split, using an underscore rather than a control character, because `\band\b`
  still matches across a non-word one. Unit keys are checked too: `medium`,
  `large` and `small` are typed words that map to the key `each`, so a `u:` map
  keyed by them is never read.
