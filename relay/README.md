# The food finder relay

*Don't know the numbers* asks a free AI about any food your pantry doesn't
know, with nothing for the person using the app to set up. The key can't live
in the app (the site is public, so it would be copied out and its free
allowance used up), so it lives here: a small Cloudflare Worker that holds the
Gemini key, asks Gemini, checks the numbers add up, and asks again when they
don't. It only ever answers food questions from the app's own address.

Free: Cloudflare Workers' free plan (about 100,000 requests a day) and
Gemini's free tier. Tested by `tests/relay.py` with no network and no key.

## Set it up (once — Tommy)

Agents never create accounts or handle keys, so these steps are yours.

1. **A Gemini key.** Open https://aistudio.google.com/apikey and sign in.
   Make a key just for this — *Create API key*, named "MNTL D&T relay" —
   so turning one key off never breaks Hermes or anything else. Copy it.
   Never paste it into a chat, an issue or a file.
2. **A Cloudflare account.** Free, at https://dash.cloudflare.com/sign-up.
   It asks you to pick a `workers.dev` name; that becomes part of the address.
3. **Deploy and give it the key**, in a terminal:

   ```
   npx wrangler login
   cd C:\Users\Tommy\code\iron-ledger\relay
   npx wrangler deploy
   npx wrangler secret put GEMINI_KEY
   ```

   `login` opens the browser to sign in to Cloudflare. `deploy` prints the
   relay's address — `https://iron-ledger-finder.<your-name>.workers.dev`.
   `secret put` asks for the key: paste it there, and only there.

   If PowerShell says *running scripts is disabled on this system*, type
   `npx.cmd` wherever these steps say `npx`. It is the same program without
   the script PowerShell refuses; no setting needs changing.
4. **Tell Nick the address** (not the key). It goes into `RELAY_URL` in
   `mntl-dt.html`, with `/find` on the end.

## Changing it later

Edit `worker.js`, run `./verify.sh` (the relay's own suite is
`tests/relay.py`), then `npx wrangler deploy` from this folder. The key stays
where it is.

To switch the key: make a new one, `npx wrangler secret put GEMINI_KEY`,
then delete the old one in AI Studio.

When lookups fail: run `npx wrangler tail` from this folder and try a lookup.
Each time Gemini says no, or can't be reached, the relay logs Gemini's own
status and message (`Gemini 400: …`); the app only ever gets a code like
`failed`. The key is cut out of anything logged.

## What it guards

- Browsers on other websites get no answer: only `ALLOWED_ORIGINS` (the Pages
  site and the iPhone app) and a phone on the home wifi do. **That is not a lock.** A script can
  claim any origin, and an app whose every byte is public has no secret to
  prove itself with. What limits the damage is the rest of this list.
- `PER_PHONE`: 20 lookups a minute from any one address.
- At most 2 KB a question — refused on its stated size, or as soon as 2 KB has
  been read when it doesn't say — and 300 characters of food. The prompt is built here, so the relay can't be used as a
  general-purpose AI.
- Only food rows go back. The key never does, and the log cuts out anything
  shaped like a key.
- The key is on Gemini's **free tier**: its Google project has no billing
  account. Keep it that way, because nothing in the relay can check it. Then the
  worst abuse can do is use up the day's free allowance — the app says the
  finder is busy until it resets at midnight Pacific. With billing turned on,
  the same abuse would be paid for, so set a budget cap in Google Cloud before
  ever doing that. To check: AI Studio → API keys shows the key's plan as
  *Free*. If abuse ever shows up in `npx wrangler tail`, the next step is a
  Cloudflare Turnstile check in the app.

## Which model answers

Each Gemini model has its own free daily allowance, and the better the model
the smaller it is: 500 lookups a day for each lite model, 20 for each stronger
one (your limits page, 2026-11-16). The stronger ones give better numbers, and
are the ones the free tier most often turns away. So `wrangler.toml` has two
lists, and the relay asks down both at the same time:

- `BEST`: the stronger models. Their answer is used if it comes inside 8
  seconds.
- `MODELS`: the lite models. Their answer is used when no best model was in
  time, so a lookup is never worse than it was before there was a `BEST`.

Down either list, a model that is overloaded, out of allowance, too slow,
retired or unreadable hands the question to the next; one out of allowance is
left alone until Google says it's back. Only when every model on both lists has
said no does the app hear "busy". A refused key is said straight away, since
another model would not help.

`EFFORT` (default `low`) is how much the model thinks before it answers.

To see each model's real allowance on this key: https://ai.dev/rate-limit
(signed in as the key's owner). To try a change against real Gemini without
replacing the live relay: `npx wrangler dev --remote` from this folder runs a
test copy with the live relay's key, answering at `http://localhost:8787/find`
(send `Origin: http://localhost:8000`).
