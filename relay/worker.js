/* MNTL D&T's food finder relay — a Cloudflare Worker.
 *
 * The owner wanted "Don't know the numbers" to work the moment the app is
 * opened: no key to paste, no sign-in. A key cannot live in the app — the
 * repo and the Pages site are public, so it would be copied out of the page,
 * its free allowance used up and the key shut off. So the key lives here, as
 * the Worker secret GEMINI_KEY, and the app asks this instead of Gemini.
 *
 * It does one thing: find the macros of a food. The app sends the words and
 * the country, POST /find {food, region}; the prompt is built here, so this
 * cannot be borrowed as a free general-purpose AI. It is a small agent rather
 * than one question: ask, check that each answer's calories add up from its
 * protein, carbs and fat, and ask once more about any that don't.
 *
 * Guarding the free allowance. Browsers on other websites get no answer: only
 * the app's own origins do (ALLOWED_ORIGINS, plus a phone on the home wifi for
 * development). That is not a lock — a script can claim any origin, and an app
 * whose every byte is public has no secret to prove itself with — so the rest
 * is what limits the damage: each address is held to the PER_PHONE rate, a
 * question is at most MAX_BODY bytes and MAX_FOOD characters, the prompt is
 * built here so it only ever answers food questions, and the reply is cut down
 * to food rows. The key is on Gemini's free tier — its Google project has no
 * billing account, which nothing here can check, so keep it that way — and
 * then the worst abuse can do is use up the day's free allowance (the app says
 * the finder is busy until it resets). With billing on, the same abuse would
 * be paid for: set a budget cap in Google Cloud first.
 *
 * Deploy and set the key: see relay/README.md. Nothing here is secret.
 */

const GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions";
export const MAX_FOOD = 300;
export const MAX_BODY = 2048;
const MAX_REGION = 60;
const MAX_ITEMS = 12;
const MAX_NOTE = 400;
const BASES = ["published", "typical", "rough"];

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = originAllowed(origin, env);
    const cors = allowed
      ? { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", "Vary": "Origin" }
      : { "Vary": "Origin" };

    if (new URL(request.url).pathname !== "/find") return reply(404, { error: "not_found" }, cors);
    if (request.method === "OPTIONS") return new Response(null, { status: allowed ? 204 : 403, headers: cors });
    if (!allowed) return reply(403, { error: "origin" }, cors);
    if (request.method !== "POST") return reply(405, { error: "method" }, cors);
    if (!env.GEMINI_KEY) return reply(503, { error: "not_set_up" }, cors);

    if (env.PER_PHONE) {
      const who = request.headers.get("CF-Connecting-IP") || "unknown";
      const { success } = await env.PER_PHONE.limit({ key: who });
      if (!success) return reply(429, { error: "slow_down" }, cors);
    }

    // A question is a few hundred bytes. Anything far bigger is refused: on its
    // stated size before a byte is read, or, when it doesn't say, as soon as
    // the bytes read pass MAX_BODY — never by reading it all first.
    if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY) return reply(413, { error: "too_long" }, cors);
    let raw = "";
    try { raw = await readCapped(request, MAX_BODY); } catch (e) { /* answered below */ }
    if (raw === null) return reply(413, { error: "too_long" }, cors);
    let body = null;
    try { body = JSON.parse(raw); } catch (e) { /* answered below */ }
    const rawFood = body && typeof body.food === "string" ? body.food : "";
    if (rawFood.length > MAX_FOOD) return reply(400, { error: "too_long" }, cors);
    const food = clean(rawFood, MAX_FOOD);
    const region = clean(body && body.region, MAX_REGION) || "United States";
    if (!food) return reply(400, { error: "bad_request" }, cors);

    try {
      return reply(200, await findMacros(food, region, env), cors);
    } catch (e) {
      const code = (e && e.code) || "failed";
      return reply(code === "busy" ? 429 : 502, { error: code }, cors);
    }
  }
};

// The body as text, read a piece at a time and given up on (null) the moment
// it passes `max` bytes, so an endless body costs no more than `max` to refuse.
export async function readCapped(request, max) {
  if (!request.body) return "";
  const reader = request.body.getReader();
  const pieces = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) {
      try { await reader.cancel(); } catch (e) { /* already gone */ }
      return null;
    }
    pieces.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const p of pieces) { all.set(p, at); at += p.byteLength; }
  return new TextDecoder().decode(all);
}

// The Pages site, anything listed in ALLOWED_ORIGINS, and a phone on the home
// wifi running tools/serve.py (localhost or a private address), for testing.
export function originAllowed(origin, env) {
  if (!origin) return false;
  const listed = String((env && env.ALLOWED_ORIGINS) || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (listed.indexOf(origin) > -1) return true;
  return /^http:\/\/(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$/.test(origin);
}

function clean(v, max) {
  return typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim().slice(0, max) : "";
}

function reply(status, obj, headers) {
  return new Response(JSON.stringify(obj), {
    status, headers: Object.assign({ "Content-Type": "application/json", "Cache-Control": "no-store" }, headers)
  });
}

function err(code, detail) { const e = new Error(detail || code); e.code = code; return e; }

// Gemini's own words when it says no, for `npx wrangler tail`: the app only
// ever sees a code, and "failed" alone cannot tell a region block from an
// outage. The key is cut out first, in case an error ever quotes it back.
function note(env, msg) {
  const key = env && env.GEMINI_KEY;
  let text = key ? msg.split(key).join("[key]") : msg;
  // and anything shaped like a Google key, in case one is ever quoted back
  // cut short or with another key's characters
  text = text.replace(/AIza[0-9A-Za-z_-]{8,}/g, "[key]");
  console.error(text.slice(0, 600));
}

// Keep in step with estimatePrompt() in mntl-dt.html, which asks Claude
// the same question when the app is opened inside Claude.
export function estimatePrompt(food, region) {
  return "You find the calories and macros of food people have eaten. Reply with JSON only.\n\n" +
    "Food eaten: \"" + food + "\"\n" +
    "Country: " + region + "\n\n" +
    "Rules:\n" +
    "- Answer for " + region + ": use that country's food composition data, its retail and " +
      "restaurant products, and its typical cuts, preparations and serving sizes. A named store " +
      "or brand means that country's version of it, and an ambiguous unit means whatever that " +
      "country normally uses.\n" +
    "- Split the description into individual foods, one object each. A restaurant order is one object per item. " +
      "List only what the text names: never add a drink, alcohol, side or sauce nobody mentioned.\n" +
    "- Use the stated quantity, however large: 55 pieces is 55 pieces, never a normal serving. " +
      "Weights of rice, pasta and grains are cooked weight unless the text says dry or uncooked.\n" +
    "- A vague amount (\"a big plate\", \"a lot\", \"half the bag\", \"all you can eat\") still gets real numbers: " +
      "decide what a realistic amount is, use it, and say what you assumed in the note.\n" +
    "- A mix with no kind given (\"sushi\", \"wings\", \"tacos\", \"cookies\") is the average of the usual " +
      "assortment as served, neither its lightest kind nor its heaviest.\n" +
    "- If a brand, store or restaurant is named and you know its published nutrition, use those figures " +
      "and set basis to \"published\". For a generic food use standard food composition data and set basis " +
      "to \"typical\". If you are unsure what it is or how big it was, give your best estimate and set basis to \"rough\".\n" +
    "- If a quantity is missing, assume one typical serving and say so in the note.\n" +
    "- If the text is not food at all, return no items.\n" +
    "- amount: how much, in a few words, such as \"6 oz\", \"1 cup\", \"1 medium\", \"55 pieces\" or \"1 burger\".\n" +
    "- grams: what that amount weighs in grams, or 0 if you cannot say.\n" +
    "- calories: whole kcal. protein, carbs, fat: whole grams. Calories should come close to " +
      "4 x protein + 4 x carbs + 9 x fat, apart from alcohol.\n" +
    "- count: how many pieces or items the amount is (55 pieces is 55, 3 slices is 3); 1 for a weight, a volume or one dish.\n" +
    "- note: one short sentence naming any assumption worth knowing, or an empty string.\n\n" +
    'Return exactly this shape: {"items":[{"food":"","amount":"","grams":0,"calories":0,"protein":0,' +
      '"carbs":0,"fat":0,"basis":"typical","count":1}],"note":""}';
}

// Calories come to about 4 a gram of protein and carbs and 9 a gram of fat,
// so an answer far from that has a slip in it.
export function addsUp(it) {
  if (it.carbs == null || it.fat == null || !it.calories) return true;
  const sum = 4 * it.protein + 4 * it.carbs + 9 * it.fat;
  return Math.abs(sum - it.calories) <= Math.max(40, it.calories * 0.2);
}

export function recheckPrompt(food, region, out, off) {
  return estimatePrompt(food, region) + "\n\nYou answered:\n" + JSON.stringify({ items: out.items, note: out.note }) + "\n\n" +
    "These don't add up — calories should come close to 4 x protein + 4 x carbs + 9 x fat: " +
    off.map((it) => it.food + " (" + it.calories + " kcal, but " + (4 * it.protein + 4 * it.carbs + 9 * it.fat) +
      " from its macros)").join("; ") +
    ". Check them and answer again in exactly the same shape. If alcohol explains a gap, keep its calories and say so in the note.";
}

// Free models wrap JSON in a code fence or a sentence; the object is found in
// the reply rather than the reply being taken as the object. And the lite
// model now and then garbles a number: "a big plate of spaghetti bolognese"
// came back with "carbs":95id three times in eight (2026-11-16), which is not
// JSON, so the lookup failed on a reply that was otherwise right. A number
// with letters stuck to its end is read as the number.
export function readJson(text) {
  if (Array.isArray(text)) text = text.map((x) => (x && x.text) || "").join("");
  if (typeof text !== "string") return null;
  const a = text.indexOf("{"), b = text.lastIndexOf("}");
  if (a < 0 || b < a) return null;
  const body = text.slice(a, b + 1);
  try { return JSON.parse(body); } catch (e) { /* try it mended */ }
  try { return JSON.parse(body.replace(/(":\s*-?\d+(?:\.\d+)?)[A-Za-z]+(?=\s*[,}\]])/g, "$1")); } catch (e) { return null; }
}

// What the model said, cut down to food rows. The count is kept only as far
// as answer(), which drops it before anything goes back to the app.
const MAX_COUNT = 5000;
export function tidy(out) {
  const n = (v) => { const x = Math.round(Number(v)); return isFinite(x) && x >= 0 ? x : null; };
  const items = (out && Array.isArray(out.items) ? out.items : [])
    .filter((it) => it && typeof it.food === "string" && it.food.trim())
    .slice(0, MAX_ITEMS)
    .map((it) => ({
      food: clean(it.food, 80), amount: clean(it.amount, 40), grams: n(it.grams) || 0,
      calories: n(it.calories) || 0, protein: n(it.protein) || 0, carbs: n(it.carbs), fat: n(it.fat),
      basis: BASES.indexOf(it.basis) > -1 ? it.basis : "rough",
      count: Math.min(n(it.count) || 1, MAX_COUNT)
    }));
  return { items: items, note: clean(out && out.note, 200) };
}
// Only food rows go back to the app: named, numbered, nothing else. A food
// that was counted says what one of it came to, under the answer, so a number
// as big as 55 pieces of sushi can be checked against the piece it stands on:
// "55 at about 45 kcal and 2.4 g protein each". Worked out from the totals,
// so it always agrees with them.
export function answer(got, rechecked) {
  const how = got.items.filter((it) => it.count >= 2 && it.calories).map((it) =>
    it.food + ": " + it.count + " at about " + Math.round(it.calories / it.count) + " kcal and " +
    (Math.round(it.protein / it.count * 10) / 10) + " g protein each.");
  return {
    items: got.items.map((it) => ({ food: it.food, amount: it.amount, grams: it.grams, calories: it.calories,
      protein: it.protein, carbs: it.carbs, fat: it.fat, basis: it.basis })),
    note: clean([got.note].concat(how).filter(Boolean).join(" "), MAX_NOTE), rechecked: rechecked
  };
}

// Which model answers. Gemini's free tier gives each model its own daily
// allowance, and the better the model the smaller it is. Read from the
// owner's own page (ai.dev/rate-limit) on 2026-11-16: the two lite models get
// 500 lookups a day each, every stronger one 20. Measured the same day on the
// owner's example and eight other awkward foods, the stronger ones were
// plainly better where the lite one guesses: 30 chicken wings came to about
// 2,600 kcal from Gemini 4 Hydrogen and Gemini 3.6 Flash alike (a restaurant
// lists 2,200 to 3,300) and 1,400 to 2,100 from the lite model. But they are
// also the ones the free tier turns away or keeps waiting: Gemini 3.8 Flash
// answered none of thirteen lookups in 28 seconds each.
//
// So there are two lists, asked at the same time. BEST is the stronger
// models, given BEST_WAIT to answer; MODELS is the lite ones, which nearly
// always answer in a second or two. The best answer is used if it comes in
// time, the lite one if it doesn't, so a lookup is never worse than it was and
// never waits longer than BEST_WAIT for nothing. Down either list, a model
// that is overloaded (503, 500), out of allowance (429), too slow, gone (404)
// or unreadable hands the question to the next. Only when every one has said
// no is the app told — busy if any was merely busy. A refused key is said
// straight away: another model would not help.
const OVERLOADED = [429, 500, 503];
const ATTEMPT_MS = 12000;
// A model whose allowance is spent is left alone until Google says it is back
// ("Please retry in 15h24m4.9s"), so every lookup does not pay for asking it
// first. Remembered per Worker instance, which is enough to skip it for a run
// of lookups; a fresh instance asks once and learns again.
const resting = new Map();
export function restFor(text) {
  const m = /retry in\s+(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?/i.exec(text || "");
  if (!m || !(m[1] || m[2] || m[3])) return 0;
  const ms = ((+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0)) * 1000;
  return Math.min(ms, 24 * 3600 * 1000);
}
const listed = (v) => String(v || "").split(",").map((s) => s.trim()).filter(Boolean);
export function modelsFor(env) {
  if (env.MODELS) return listed(env.MODELS);
  return [env.MODEL || "gemini-flash-lite-latest"].concat(env.FALLBACK_MODEL ? [env.FALLBACK_MODEL] : []);
}
export function bestFor(env) { return listed(env.BEST); }
const BEST_WAIT = 8000;
export function forgetResting() { resting.clear(); }

// The app gives a lookup 45 seconds (RELAY_WAIT) and then says it took too
// long. Three models at 12 seconds each, asked twice when the numbers need a
// second look, could run to 72: on 2026-11-16 a lookup that answered took 47,
// so the phone had given up on an answer that then arrived for nobody. So a
// lookup has a budget, BUDGET_MS, well inside the app's wait. No model is
// started with less than MIN_LEFT of it to go, and none is given longer than
// what is left.
const BUDGET_MS = 30000;
const MIN_LEFT = 3000;
async function ask(prompt, env, until) {
  const best = bestFor(env);
  if (!best.length) return askDown(prompt, modelsFor(env), env, until);
  const settled = (p) => p.then((ok) => ({ ok: ok }), (e) => ({ e: e }));
  // Both at once: the lite answer is usually in hand long before it is needed.
  const lite = settled(askDown(prompt, modelsFor(env), env, until));
  const wait = Math.min(until, Date.now() + (Number(env.BEST_WAIT) || BEST_WAIT));
  const b = await settled(askDown(prompt, best, env, wait));
  if (b.ok) return b.ok;
  if (b.e && b.e.code === "key") throw b.e;
  const l = await lite;
  if (l.ok) return l.ok;
  throw l.e;
}

// Down one list of models until one answers.
async function askDown(prompt, models, env, until) {
  let last = null, busy = false;
  for (const model of models) {
    if ((resting.get(model) || 0) > Date.now()) { busy = true; continue; }
    const left = until - Date.now();
    if (left < MIN_LEFT) { busy = true; break; }
    try { return await askModel(prompt, model, env, left); }
    catch (e) {
      // A refused key is the same key for every model. A reply that could
      // not be read is one model's slip, so the next is asked (until b101 it
      // failed the lookup there and then).
      if (!e || e.code === "key") throw e;
      if (e.code === "busy") busy = true;
      last = e;
    }
  }
  throw busy ? err("busy") : last || err("busy");
}

// A little thinking before the answer (b101). Asked to think "low", the lite
// model gave the same 2,090 kcal for 55 pieces of sushi twice running, where
// without it the same question had come back as 1,650 and 2,200; and the
// stronger models answer in 2 to 6 seconds instead of 6 to 26. EFFORT in
// wrangler.toml changes it; "none" leaves the model to its own default.
const EFFORT = "low";
async function askModel(prompt, model, env, left) {
  let r, text;
  const effort = String(env.EFFORT == null ? EFFORT : env.EFFORT).trim();
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), Math.min(Number(env.ATTEMPT_MS) || ATTEMPT_MS, left));
  try {
    r = await fetch(GEMINI, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + env.GEMINI_KEY },
      body: JSON.stringify(Object.assign({ model: model, temperature: 0.2, messages: [{ role: "user", content: prompt }] },
        effort && effort !== "none" ? { reasoning_effort: effort } : {})),
      signal: ctl.signal
    });
    text = await r.text();
  } catch (e) {
    const slow = ctl.signal.aborted;
    note(env, (slow ? "Gemini too slow (" : "Gemini unreachable (") + model + "): " + String(e));
    throw err(slow ? "busy" : "failed", String(e));
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) {
    note(env, "Gemini " + r.status + " (" + model + "): " + text);
    if (r.status === 429) { const ms = restFor(text); if (ms) resting.set(model, Date.now() + ms); }
    throw err(OVERLOADED.indexOf(r.status) > -1 ? "busy"
      : r.status === 401 || r.status === 403 || (r.status === 400 && /api.?key/i.test(text)) ? "key"
      : r.status === 404 ? "model" : "failed", "Gemini " + r.status);
  }
  let j = null;
  try { j = JSON.parse(text); } catch (e) { /* unreadable below */ }
  const msg = j && j.choices && j.choices[0] && j.choices[0].message;
  const out = readJson(msg && msg.content);
  if (!out) {
    // Why, for the log, and never what: the reply may repeat the food typed.
    const said = msg && typeof msg.content === "string" ? msg.content.length : 0;
    note(env, "Gemini unreadable (" + model + "): " + said + " characters, finish " +
      String((j && j.choices && j.choices[0] && j.choices[0].finish_reason) || "unknown"));
    throw err("unreadable");
  }
  return tidy(out);
}

// Ask, check, and ask once more about anything that doesn't add up. The second
// answer is kept only if it adds up better; what still doesn't, the app flags.
// The second look is skipped when the budget has no room for it: an answer
// the app can flag beats one that arrives after the phone has given up.
const RECHECK_NEEDS = 6000;
export async function findMacros(food, region, env) {
  const until = Date.now() + (Number(env.BUDGET_MS) || BUDGET_MS);
  const first = await ask(estimatePrompt(food, region), env, until);
  const off = first.items.filter((it) => !addsUp(it));
  if (!off.length || until - Date.now() < RECHECK_NEEDS) return answer(first, false);
  let second = null;
  try { second = await ask(recheckPrompt(food, region, first, off), env, until); } catch (e) { /* keep the first */ }
  const still = second ? second.items.filter((it) => !addsUp(it)).length : off.length;
  if (second && second.items.length && still < off.length) {
    if (!second.note) second.note = first.note;
    return answer(second, true);
  }
  return answer(first, true);
}
