"""The built-in food table: structure, then behaviour.

The table is the thing that makes the app work with no network and no account,
and it is edited by hand. Two ways it broke while being grown from 111 entries
to 265, both silent until something else caught them:

  - an entry appended after the last one, which had no trailing comma, took the
    whole script down with "Unexpected token '{'";
  - "mac and cheese" resolved to cheddar, because splitItems() splits on the
    word "and" before any matching happens, so the alias could never fire.

So this checks the shape of the data as well as the answers it gives.
"""
from playwright.sync_api import sync_playwright
import os, io, re, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = ROOT.replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))

SRC = io.open(os.path.join(ROOT, "iron-ledger.html"), encoding="utf-8").read()

# units the parser actually understands; anything else in a u: map is dead data
OK_UNITS = {"cup", "tbsp", "tsp", "slice", "scoop", "can", "bar", "fillet", "breast",
            "patty", "link", "rasher", "container", "serving", "bottle", "packet",
            "pouch", "box", "tub", "carton", "stick", "bag", "each", "half"}

body = SRC.split("var FOODS = [", 1)[1]
depth = 1
for i, ch in enumerate(body):
    if ch == "[": depth += 1
    elif ch == "]":
        depth -= 1
        if depth == 0: body = body[:i]; break

entries = []
for line in body.split("\n"):
    t = line.strip()
    if not t or t.startswith("//"): continue
    m = re.match(r'\{ n: "([^"]+)", k: ([\d.]+), d: ([\d.]+), p: ([\d.]+), '
                 r'a: \[([^\]]*)\], u: (\{\}|\{ [^}]* \}) \},$', t)
    if not m:
        entries.append(("MALFORMED", t)); continue
    entries.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)),
                    re.findall(r'"([^"]+)"', m.group(5)),
                    re.findall(r'(\w+):', m.group(6))))

bad = [e for e in entries if e[0] == "MALFORMED"]
check("every entry parses", not bad, "; ".join(x[1][:60] for x in bad[:3]))
foods = [e for e in entries if e[0] != "MALFORMED"]
check("the table is not suspiciously small", len(foods) >= 250, "%d foods" % len(foods))

names = [f[0] for f in foods]
dup_names = sorted({n for n in names if names.count(n) > 1})
check("no duplicate names", not dup_names, ", ".join(dup_names[:5]))

seen, dup_alias = {}, []
for f in foods:
    for a in f[4]:
        if a in seen: dup_alias.append('"%s": %s / %s' % (a, seen[a], f[0]))
        seen[a] = f[0]
check("no alias points at two foods", not dup_alias, "; ".join(dup_alias[:4]))

unknown = ["%s: %s" % (f[0], u) for f in foods for u in f[5] if u not in OK_UNITS]
check("no unparseable unit keys", not unknown, "; ".join(unknown[:5]))

# a swapped k/p or a stray decimal shows up as impossible protein
impossible = ["%s (%gk %gp)" % (f[0], f[1], f[3]) for f in foods if f[3] * 4 > f[1] * 1.25]
check("protein is possible for the calories", not impossible, "; ".join(impossible[:5]))
check("every food has a serving size", all(f[2] > 0 for f in foods))
check("every food has at least one alias", all(f[4] for f in foods))

# ---- the matcher, ported: longest whole-word alias wins ---------------------
def norm(x):
    x = re.sub(r'[^a-z0-9/%.\s]', ' ', str(x).lower())
    return re.sub(r'\s+', ' ', x).strip()
DRY = re.compile(r'\b(dry|uncooked|raw)\b')
def match(q):
    n = " " + norm(q) + " "; wants = bool(DRY.search(n)); best = None; bl = 0
    for f in foods:
        for a in f[4]:
            if (" " + a + " ") not in n: continue
            l = len(a) + (20 if wants and DRY.search(a) else 0) - (20 if not wants and DRY.search(a) else 0)
            if l > bl: bl = l; best = f[0]
    return best if bl > 0 else None

unfindable = [f[0] for f in foods if match(f[4][0]) != f[0]]
check("every food is found by its own first alias", not unfindable, ", ".join(unfindable[:5]))

# ---- behaviour, through the real app, with no Claude to fall back on -------
CASES = [
    ("8 oz ribeye", "Ribeye"), ("2 cups white rice", "White rice"),
    ("200g pulled pork", "Pulled pork"), ("3 chicken wings", "Chicken wing"),
    ("1 cup mashed potatoes", "Mashed potato"), ("instant ramen", "ramen"),
    ("1 burrito", "Burrito"), ("cheeseburger", "Cheeseburger"),
    ("150g pork belly", "Pork belly"), ("1 cup mac and cheese", "Mac and cheese"),
    ("2 tbsp half and half", "Half and half"), ("250g brisket", "Brisket"),
    ("1 can sardines", "Sardines"), ("2 pancakes", "Pancake"),
    ("1 cup fried rice", "Fried rice"), ("1 slice cheesecake", "Cheesecake"),
]
G = {"cal": {"dir": "-", "v": 2400}, "pro": {"dir": "+", "v": 180}}
import datetime
T = datetime.date.today().isoformat()
STORE = {"days": {T: {"food": [], "lifts": [], "updated": 1, "goal": G}}, "moves": None,
         "goal": G, "region": "United States", "pantry": [], "v": 1}

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")   # the offline table must stand alone
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(600)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(1000)
    try:
        p.click("text=Got it", timeout=2000)
    except Exception:
        pass

    wrong = []
    for q, want in CASES:
        p.fill("#estText", q); p.click("#runEst"); p.wait_for_timeout(600)
        rows = p.evaluate("""() => [...document.querySelectorAll('.rev-item')].map(x => ({
            food: x.querySelector('.food').textContent,
            cal: Number(x.querySelector('[data-ic]').value),
            src: x.querySelector('.src-tag').textContent}))""")
        if not rows or want.lower() not in rows[0]["food"].lower() or rows[0]["cal"] <= 0:
            wrong.append("%s -> %s" % (q, rows[0]["food"] if rows else "nothing"))
        p.click("#discardEst"); p.wait_for_timeout(180)
    check("calorie-dense staples resolve with no network", not wrong, "; ".join(wrong[:4]))

    # splitting must still work on genuinely separate foods
    p.fill("#estText", "chicken and rice"); p.click("#runEst"); p.wait_for_timeout(700)
    two = p.eval_on_selector_all(".rev-item", "e => e.length")
    check("a real 'and' still separates two foods", two == 2, "%d rows" % two)
    check("no page errors", not errs, str(errs[:2]))
    b.close()

for s, n, det in res: print("%-6s %-46s %s" % (s, n, det))
_bad = sum(1 for r in res if r[0] == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - _bad, _bad))
raise SystemExit(1 if _bad else 0)
