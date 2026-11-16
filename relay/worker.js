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
//
// The answer is worked out a piece at a time (b101). The owner's example was
// "55 pieces of sushi": asked for the total, the same model said 1,650 kcal
// one minute and 2,200 the next, and put 30 wings at half what a restaurant
// lists. So it is asked what ONE piece is and how many there were, and the
// multiplying is done here (totalled()), where it cannot slip.
export function estimatePrompt(food, region) {
  return "You estimate the calories and macros of food people have eaten, the way a careful dietitian " +
    "answers \"how many calories and how much protein is in that?\". Reply with JSON only.\n\n" +
    "Food eaten: \"" + food + "\"\n" +
    "Country: " + region + "\n\n" +
    "Rules:\n" +
    "- Answer for " + region + ": use that country's food composition data, its retail and " +
      "restaurant products, and its typical cuts, preparations and serving sizes. A named store " +
      "or brand means that country's version of it, and an ambiguous unit means whatever that " +
      "country normally uses.\n" +
    "- Split the description into individual foods, one object each. A restaurant order is one object per item. " +
      "Only what the text names or plainly implies: never add a drink, side or sauce nobody mentioned.\n" +
    "- Always give real numbers. A vague, large or unusual amount (\"a big plate\", \"a lot\", \"55 pieces\", " +
      "\"half the bag\") still gets your best estimate: decide what a realistic amount is, use it, and say what " +
      "you assumed in the note. Never shrink a big amount to a normal serving.\n" +
    "- Work it out a piece at a time. count is how many pieces, items or servings were eaten (55 pieces of " +
      "sushi is 55, 3 slices is 3, 2 burgers is 2) and \"each\" describes ONE of them; the app multiplies. " +
      "For a weight or a volume (\"6 oz\", \"200 g\", \"2 cups\") or a single dish, count is 1 and \"each\" is all of it.\n" +
    "- Numbers are for the food as eaten: cooked, the edible part only (no bone, shell or peel), and with what it " +
      "is normally cooked and served with (frying oil, skin, breading, sauce, dressing, cheese) unless the text " +
      "says otherwise. Food that reads as eaten out gets the restaurant's portion and recipe, not a home one.\n" +
    "- A mix with no kind given (\"sushi\", \"wings\", \"tacos\", \"cookies\") is the average of the usual " +
      "assortment, not its lightest kind.\n" +
    "- Use the stated quantity. Weights of rice, pasta and grains are cooked weight unless the text says dry or uncooked.\n" +
    "- If a brand, store or restaurant is named and you know its published nutrition, use those figures " +
      "and set basis to \"published\". For a generic food use standard food composition data and set basis " +
      "to \"typical\". If you are unsure what it is or how big it was, give your best estimate and set basis to \"rough\".\n" +
    "- If a quantity is missing, assume one typical serving and say so in the note.\n" +
    "- If the text is not food at all, return no items.\n" +
    "- amount: all of it, in a few words, such as \"55 pieces\", \"6 oz\", \"1 cup\" or \"2 burgers\".\n" +
    "- each.grams: what ONE weighs in grams, or 0 if you cannot say.\n" +
    "- each.calories: kcal in ONE. each.protein, each.carbs, each.fat: grams in ONE, to one decimal place. " +
      "Calories should come close to 4 x protein + 4 x carbs + 9 x fat, apart from alcohol.\n" +
    "- note: one short sentence naming any assumption worth knowing, or an empty string.\n\n" +
    'Return exactly this shape: {"items":[{"food":"","amount":"","count":1,"each":{"grams":0,"calories":0,' +
      '"protein":0,"carbs":0,"fat":0},"basis":"typical"}],"note":""}';
}

// Calories come to about 4 a gram of protein and carbs and 9 a gram of fat,
// so an answer far from that has a slip in it.
export function addsUp(it) {
  if (it.carbs == null || it.fat == null || !it.calories) return true;
  const sum = 4 * it.protein + 4 * it.carbs + 9 * it.fat;
  return Math.abs(sum - it.calories) <= Math.max(40, it.calories * 0.2);
}

export function recheckPrompt(food, region, out, off) {
  return estimatePrompt(food, region) + "\n\nYour answer came to these totals:\n" + JSON.stringify(out) + "\n\n" +
    "These don't add up — calories should come close to 4 x protein + 4 x carbs + 9 x fat: " +
    off.map((it) => it.food + " (" + it.calories + " kcal, but " + (4 * it.protein + 4 * it.carbs + 9 * it.fat) +
      " from its macros)").join("; ") +
    ". Check them and answer again in exactly the same shape. If alcohol explains a gap, keep its calories and say so in the note.";
}

// Free models wrap JSON in a code fence or a sentence; the object is found in
// the reply rather than the reply being taken as the object.
export function readJson(text) {
  if (Array.isArray(text)) text = text.map((x) => (x && x.text) || "").join("");
  if (typeof text !== "string") return null;
  const a = text.indexOf("{"), b = text.lastIndexOf("}");
  if (a < 0 || b < a) return null;
  try { return JSON.parse(text.slice(a, b + 1)); } catch (e) { return null; }
}

// One piece times how many: the multiplying the model is not trusted with.
// An answer in the old shape (totals, no "each") is read as it always was, so
// a model that ignores the new shape still gets through.
const MAX_COUNT = 2000;
export function totalled(it) {
  const num = (v) => { const x = Number(v); return isFinite(x) && x >= 0 ? x : null; };
  const whole = (v) => (v == null ? null : Math.round(v));
  const each = it && it.each && typeof it.each === "object" ? it.each : null;
  if (!each) {
    return { count: 1, grams: whole(num(it.grams)) || 0, calories: whole(num(it.calories)) || 0,
             protein: whole(num(it.protein)) || 0, carbs: whole(num(it.carbs)), fat: whole(num(it.fat)) };
  }
  let count = num(it.count);
  if (!count) count = 1;
  count = Math.min(count, MAX_COUNT);
  const times = (v) => { const x = num(v); return x == null ? null : Math.round(x * count); };
  return { count: count, grams: times(each.grams) || 0, calories: times(each.calories) || 0,
           protein: times(each.protein) || 0, carbs: times(each.carbs), fat: times(each.fat),
           one: { calories: Math.round(num(each.calories) || 0), protein: Math.round((num(each.protein) || 0) * 10) / 10 } };
}

// Only food rows go back to the app: named, numbered, nothing else. A food
// that was counted says what one of it came to, in the note, so a number as
// big as 55 pieces of sushi can be checked against the piece it was built on.
export function tidy(out) {
  const how = [];
  const items = (out && Array.isArray(out.items) ? out.items : [])
    .filter((it) => it && typeof it.food === "string" && it.food.trim())
    .slice(0, MAX_ITEMS)
    .map((it) => {
      const t = totalled(it), food = clean(it.food, 80);
      if (t.one && t.count >= 2 && t.one.calories) {
        how.push(food + ": " + t.count + " at about " + t.one.calories + " kcal and " + t.one.protein + " g protein each.");
      }
      return { food: food, amount: clean(it.amount, 40), grams: t.grams,
               calories: t.calories, protein: t.protein, carbs: t.carbs, fat: t.fat,
               basis: BASES.indexOf(it.basis) > -1 ? it.basis : "rough" };
    });
  return { items: items, note: clean([clean(out && out.note, 200)].concat(how).filter(Boolean).join(" "), MAX_NOTE) };
}

// Gemini's free tier gives each model its own daily allowance, and the
// busiest model the smallest: on the first night gemini-flash-latest answered
// "high demand" (503) five times, then "quota exceeded … limit: 20" a day
// (429), while gemini-flash-lite-latest answered every lookup. So the relay
// works down MODELS, lightest first: a model that is overloaded (503, 500),
// out of allowance (429), slower than ATTEMPT_MS or gone (404) hands the
// question to the next. Only when every one has said no is the app told — busy
// if any was merely busy. A refused key is said straight away: another model
// would not help.
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
export function modelsFor(env) {
  if (env.MODELS) return String(env.MODELS).split(",").map((s) => s.trim()).filter(Boolean);
  return [env.MODEL || "gemini-flash-lite-latest"].concat(env.FALLBACK_MODEL ? [env.FALLBACK_MODEL] : []);
}
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
  const models = modelsFor(env);
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

async function askModel(prompt, model, env, left) {
  let r, text;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), Math.min(Number(env.ATTEMPT_MS) || ATTEMPT_MS, left));
  try {
    r = await fetch(GEMINI, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + env.GEMINI_KEY },
      body: JSON.stringify({ model: model, temperature: 0.2, messages: [{ role: "user", content: prompt }] }),
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
  if (!off.length || until - Date.now() < RECHECK_NEEDS) return Object.assign(first, { rechecked: false });
  let second = null;
  try { second = await ask(recheckPrompt(food, region, first, off), env, until); } catch (e) { /* keep the first */ }
  const still = second ? second.items.filter((it) => !addsUp(it)).length : off.length;
  if (second && second.items.length && still < off.length) {
    return { items: second.items, note: second.note || first.note, rechecked: true };
  }
  return Object.assign(first, { rechecked: true });
}
