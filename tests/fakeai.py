"""A stand-in for the food finder's relay, for the suites.

The app asks the relay (relay/worker.js, on Cloudflare), which asks Gemini;
the suites never reach either. This answers the relay's request the way the
relay would after a careful model had answered it, from a small fixture of
foods, so a suite checks what the app does with an answer rather than what a
real model happens to say that day. It is a test fixture, not a food list the
app ships: the app has none since the finder replaced them (b63). The relay's
own behaviour — its prompt, the re-check, the limits — is tests/relay.py.

    import fakeai
    fakeai.phone(ctx)                      # the app points at the stand-in, which answers
    fakeai.phone(ctx, log=asked)           # ...and records each question
    fakeai.phone(ctx, reply=fn)            # fn(question) -> dict | (status, dict|str) | "abort" | None

A question is {"food", "region", "url", "origin"}. Nonsense ("xyzzy") gets no
items, as the relay returns for text that is not food; a food the fixture
doesn't know gets a rough guess, as a model would give.
"""
import json, re

RELAY = "https://relay.iron-ledger.test/find"
RELAY_SCRIPT = "window.IRON_LEDGER_RELAY=%s;" % json.dumps(RELAY)
NO_RELAY_SCRIPT = "window.IRON_LEDGER_RELAY='';"   # a copy of the app with no finder

# name: kcal, protein, carbs, fat per 100 g; a typical serving in grams; how a
# portion word weighs; "published" when it is a chain's or a brand's own figure.
FOODS = {
    "chicken breast": (165, 31, 0, 3.6, 170, {"breast": 170}, "typical"),
    "chicken": (165, 31, 0, 3.6, 170, {}, "typical"),
    "white rice": (130, 2.7, 28, 0.3, 158, {"cup": 158}, "typical"),
    "rice": (130, 2.7, 28, 0.3, 158, {"cup": 158}, "typical"),
    "sirloin": (206, 29, 0, 9.2, 170, {}, "typical"),
    "eggs": (143, 12.6, 0.7, 9.5, 50, {}, "typical"),
    "egg": (143, 12.6, 0.7, 9.5, 50, {}, "typical"),
    "toast": (265, 9, 49, 3.6, 28, {"slice": 28}, "typical"),
    "banana": (89, 1.1, 22.8, 0.3, 118, {}, "typical"),
    "oats": (389, 16.9, 66, 6.9, 40, {"cup": 81}, "typical"),
    "greek yogurt": (73, 10, 3.9, 1.9, 170, {"container": 150}, "typical"),
    "whole milk": (61, 3.2, 4.8, 3.3, 244, {"cup": 244}, "typical"),
    "milk": (61, 3.2, 4.8, 3.3, 244, {"cup": 244}, "typical"),
    "avocado bowl": (150, 5, 15, 8, 450, {}, "rough"),
    "beef wellington": (270, 13, 15, 17.5, 250, {}, "rough"),
    "big mac": (257, 11.9, 20.5, 13.7, 219, {}, "published"),
    "quarter pounder with cheese": (260, 15.3, 18, 14, 202, {}, "published"),
    "french fries": (323, 3.6, 41.7, 15, 111, {"medium": 111, "large": 150}, "published"),
}
WEIGHTS = {"g": 1, "gram": 1, "grams": 1, "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
           "lb": 453.592, "lbs": 453.592, "kg": 1000}
WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "half": 0.5}


def _qty(s):
    s = s.strip()
    if "/" in s:
        a, b = s.split("/", 1)
        return float(a) / float(b)
    return float(s) if re.match(r"^\d*\.?\d+$", s) else WORDS.get(s.lower(), 1)


def item(part):
    """What a careful model would say about one food, or None for nonsense."""
    m = re.match(r"^\s*(\d+\s+\d+/\d+|\d+/\d+|\d*\.?\d+|a|an|one|two|three|half)?\s*"
                 r"(g|grams?|oz|ounces?|lbs?|kg|cups?|slices?|containers?|medium|large|small)?\.?\s+(?:of\s+)?(.*)$",
                 " " + part.strip(), re.I)
    q = _qty(m.group(1)) if m and m.group(1) else 1
    unit = (m.group(2) or "").lower() if m else ""
    name = (m.group(3) if m else part).lower().strip()
    key = max((k for k in FOODS if k in name), key=len, default=None)
    if not key:
        if not re.search(r"[aeiou]", name) or name in ("xyzzy",):
            return None
        k, p, c, f, typ, por, basis = (200, 8, 22, 9, 250, {}, "rough")
    else:
        k, p, c, f, typ, por, basis = FOODS[key]
    if unit in WEIGHTS:
        g = q * WEIGHTS[unit]
        amount = "%g %s" % (q, "g" if WEIGHTS[unit] == 1 else unit)
    elif unit.rstrip("s") in por:
        g = q * por[unit.rstrip("s")]
        amount = "%g %s" % (q, unit)
    else:
        g = q * typ
        amount = "%g" % q if m and m.group(1) else "1 serving"
    return {"food": part.strip().capitalize() if not key else key.capitalize(), "amount": amount,
            "grams": round(g), "calories": round(k * g / 100), "protein": round(p * g / 100),
            "carbs": round(c * g / 100), "fat": round(f * g / 100), "basis": basis}


def answer(food):
    """The relay's reply to one question, as the fixture would have it."""
    parts = [x for x in re.split(r"\s*(?:&|,|\+|;|\band\b|\n)\s*", food) if len(x.strip()) > 1]
    items = [i for i in (item(x) for x in parts) if i]
    return {"items": items, "note": "" if items else "I couldn't tell what that is.", "rechecked": False}


def install(target, reply=None, log=None):
    """Answer the relay on a page or a browser context."""
    def handle(route):
        req = route.request
        cors = {"Access-Control-Allow-Origin": req.headers.get("origin") or "*",
                "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "POST, OPTIONS"}
        if req.method == "OPTIONS":
            route.fulfill(status=204, headers=cors)
            return
        try:
            body = json.loads(req.post_data or "{}")
        except Exception:
            body = {}
        q = {"food": body.get("food", ""), "region": body.get("region", ""), "url": req.url,
             "body": body, "origin": req.headers.get("origin", "")}
        if log is not None:
            log.append(q)
        got = reply(q) if reply else None
        if got is None:
            got = answer(q["food"])
        if got == "abort":
            route.abort("internetdisconnected")
            return
        status, obj = got if isinstance(got, tuple) else (200, got)
        route.fulfill(status=status, body=obj if isinstance(obj, str) else json.dumps(obj),
                      content_type="application/json", headers=cors)
    target.route(RELAY, handle)


AI_SCRIPT = "window.IRON_LEDGER_AI=true;"   # Ask an agent's permission, already given


def phone(ctx, reply=None, log=None, allowed=True):
    """A phone whose app asks the stand-in relay.

    Since b79 Ask an agent asks before it sends anything. These phones have
    already said yes (the app's stand-in, window.IRON_LEDGER_AI, which a yes
    or no in the log overrides), unless allowed=False; tests/agecheck.py is
    the suite that answers the sheet itself."""
    ctx.add_init_script(RELAY_SCRIPT)
    if allowed:
        ctx.add_init_script(AI_SCRIPT)
    install(ctx, reply=reply, log=log)
