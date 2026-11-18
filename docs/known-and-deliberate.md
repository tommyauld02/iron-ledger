# Known and deliberate

Moved word for word from `CLAUDE.md` (issue #10), which keeps the seven
rules and the index of these docs. The rules apply here too.

- The goal bar's centre divider does not line up with the T chart's stem. The
  owner asked to leave that section alone; it is his call.
- Rest days are not painted red on the calendar. Offered, declined.
- The age check is self-declared. It records the answer someone gives; it
  cannot know their age, and someone under 18 can tap the other button. That
  is what an age screen is in an app with no accounts and no ID check, and the
  privacy policy and Terms say the app is for adults.
- *I'm under 18* has no way back, as approved on 2026-10-28: the answer is
  kept and the sorry screen shows on every open. A mis-tap on a first open
  costs a reinstall. On a phone with a log it locks the person out of Backup
  too; the log is kept, not deleted, but the only way back in is clearing the
  app's data, which loses it. Raised with the owner with b79.
- Barcode scanning used to be the one genuine reason to go native. It is in the
  web app now (b61, zxing-wasm), so nothing found so far needs a native build.
- *Ask an agent* needs a connection for anything not in your pantry.
  The owner chose that on 2026-10-14 when the food finder replaced the built-in
  table, the USDA library and the menus ("99% of people have internet"); they
  were removed, not kept as an offline fallback. Offline, a food goes in as a
  *needs numbers* placeholder to fill once there is signal. The pantry,
  barcodes (once grocery brands are downloaded) and the label reader still work
  with no connection.
- The food finder's numbers are an AI's estimate, tagged as such, and checked
  only for adding up (4·protein + 4·carbs + 9·fat), not against a source. A
  chain's figure is the model's memory of what the chain publishes, not a
  reading of its page: Gemini's free tier cannot search the web (checked again
  2026-11-16: Google Search grounding is "not available" on the free tier for
  every Gemini 3 and 4 model, and the owner's limits page shows 0 a day). With
  billing on it is 5,000 searches a month free, then $14 a thousand, which is
  the owner's call. If exactness matters for a food eaten often, save it to
  the pantry from its label.
- The food finder shares one free Gemini key through the relay, and each model
  on it has its own daily allowance: 500 a day for each lite model, 20 for
  each stronger one (2026-11-16). Since b101 a stronger model is asked
  alongside the lite one and used when it answers in time, so the first 40 or
  so lookups a day are the better ones and the same food can come back a little
  different later in the day. That is plenty for the owner and his testers; if
  the app is ever used widely enough to use them all up, *busy, or at today's
  free limit* is what people see until midnight Pacific, and the fix is turning
  billing on for that key (a fraction of a cent a lookup), which is the owner's
  call.
- A lookup can take up to about 8 seconds since b101, where it took 1 or 2:
  that is how long the stronger models are given before the lite answer is
  used. The owner asked for the most accurate number, and a search takes as
  long. When the first of them is silent, as Gemini 4 Hydrogen was the day
  after b101, the next is asked beside it after 4 seconds, so that day costs 5
  or so and not 8 (`docs/food.md`, *A best model that says nothing is not
  waited out*).
- The relay's origin check keeps other websites out, not scripts: anyone can
  claim the app's origin. Nothing in a public app can prove it is the app. The
  per-address limit, the size cap and the server-built prompt limit what a
  script can do, and while the key stays on the free tier (no billing account
  on its Google project — nothing in the relay can check that) the worst is
  using up the day's allowance. Turning billing on would make abuse cost money:
  set a budget cap first. A Cloudflare Turnstile check is the next step if abuse ever shows
  up in the relay's log.
