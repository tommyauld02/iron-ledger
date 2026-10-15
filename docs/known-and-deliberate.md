# Known and deliberate

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

- The goal bar's centre divider does not line up with the T chart's stem. The
  owner asked to leave that section alone; it is his call.
- Rest days are not painted red on the calendar. Offered, declined.
- Barcode scanning used to be the one genuine reason to go native. It is in the
  web app now (b61, zxing-wasm), so nothing found so far needs a native build.
- *Don't know the numbers* needs a connection for anything not in your pantry.
  The owner chose that on 2026-10-14 when the food finder replaced the built-in
  table, the USDA library and the menus ("99% of people have internet"); they
  were removed, not kept as an offline fallback. Offline, a food goes in as a
  *needs numbers* placeholder to fill once there is signal. The pantry,
  barcodes (once grocery brands are downloaded) and the label reader still work
  with no connection.
- The food finder's numbers are an AI's estimate, tagged as such, and checked
  only for adding up (4·protein + 4·carbs + 9·fat), not against a source. A
  chain's figure is the model's memory of what the chain publishes, not a
  reading of its page: Gemini's free tier cannot search the web (as of
  2026-10). If exactness matters for a food eaten often, save it to the pantry
  from its label.
- The food finder shares one free Gemini key through the relay, and each model
  on it has its own daily allowance (the big Flash model only 20 a day; the
  relay asks the lightest first and works down the list). That is plenty for
  the owner and his testers; if the app is ever used widely enough to use them
  all up, *busy, or at today's free limit* is what people see until midnight
  Pacific, and the fix is turning billing on for that key (a fraction of a cent
  a lookup), which is the owner's call.
- The relay's origin check keeps other websites out, not scripts: anyone can
  claim the app's origin. Nothing in a public app can prove it is the app. The
  per-address limit, the size cap and the server-built prompt limit what a
  script can do, and while the key stays on the free tier (no billing account
  on its Google project — nothing in the relay can check that) the worst is
  using up the day's allowance. Turning billing on would make abuse cost money:
  set a budget cap first. A Cloudflare Turnstile check is the next step if abuse ever shows
  up in the relay's log.
