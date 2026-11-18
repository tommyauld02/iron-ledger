"""The App Store screenshots, rendered from the app itself.

    python3 tools/make-screenshots.py            # store/screenshots/*.png
    python3 tools/make-screenshots.py --plain    # the app screens only, no captions

Apple's required size for iPhone is 6.9 inches: 1320 x 2868, which is an
iPhone Pro Max's 440 x 956 points at 3x. Every screen is mntl-dt.html opened
as the iPhone app opens it (the same stand-in for the native shell that
tests/darkcheck.py uses), on a demo log made here: about five weeks of a
push, pull, legs split, food and cardio, the way a real log looks once it
has been used. Nothing is drawn by hand; change the app and run this again.

Like icons/, the output is generated: never edit a screenshot by hand.
store/screenshots/ is not committed, so this is how anyone gets them.
"""
from playwright.sync_api import sync_playwright
import os, re, sys, json, time, random, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "store", "screenshots")
PLAIN = "--plain" in sys.argv
W, H, SCALE = 440, 956, 3            # points, and 3x: 1320 x 2868

today = datetime.date.today()
T = today.isoformat()
NOW = int(time.time() * 1000)
rnd = random.Random(7)              # the same log every run


def key(n):
    return (today - datetime.timedelta(days=n)).isoformat()


# ---------- the demo log ----------
SPLIT = [
    {"id": "push", "name": "Push", "short": "Push"},
    {"id": "pull", "name": "Pull", "short": "Pull"},
    {"id": "legs", "name": "Legs", "short": "Legs"},
]
# Each movement: (name, starting weight five weeks ago, the step it goes up by, reps, sets)
MOVES = {
    "push": [("Bench Press", 175, 5, 8, 4), ("Incline DB Press", 60, 5, 10, 3),
             ("Overhead Press", 105, 5, 8, 3), ("Cable Lateral Raise", 15, 2.5, 15, 3),
             ("Rope Pushdown", 50, 5, 12, 3)],
    "pull": [("Barbell Row", 155, 5, 8, 4), ("Lat Pulldown", 130, 5, 10, 4),
             ("Seated Cable Row", 120, 5, 12, 3), ("Face Pull", 40, 5, 15, 3),
             ("Hammer Curl", 30, 2.5, 12, 3)],
    "legs": [("Back Squat", 225, 10, 6, 4), ("Romanian Deadlift", 185, 10, 8, 3),
             ("Leg Press", 360, 20, 12, 3), ("Lying Leg Curl", 90, 5, 12, 3),
             ("Standing Calf Raise", 135, 10, 15, 3)],
}
GOAL = {"cal": {"dir": "-", "v": 2400}, "pro": {"dir": "+", "v": 165}, "carb": 250, "fat": 75}

# Today is a pull day, and so is every third day before it.
def split_on(n):
    return SPLIT[(1 - n) % 3]["id"]


def week_plan():
    # Sunday first, and Sunday is the rest day. The other six follow the
    # split from today, so the week's board reads true.
    plan = [None] * 7
    for n in range(-3, 4):
        d = today - datetime.timedelta(days=n)
        dow = (d.weekday() + 1) % 7
        plan[dow] = "~rest" if dow == 0 else split_on(n)
    return plan


MEALS = [
    ("Eggs and oats", 520, 32, 52, 19),
    ("Greek yogurt and berries", 260, 24, 30, 4),
    ("Protein shake", 160, 30, 6, 2),
    ("Chicken rice bowl", 690, 52, 78, 16),
    ("Turkey sandwich", 480, 36, 48, 14),
    ("Salmon, potatoes and greens", 640, 44, 52, 26),
    ("Steak and rice", 720, 54, 70, 22),
    ("Banana", 105, 1, 27, 0),
    ("Cottage cheese", 180, 24, 8, 5),
]
uid_n = [0]
def uid():
    uid_n[0] += 1
    return "d%04d" % uid_n[0]


def food_day(n):
    # Mostly on target, the way a log looks after five weeks of trying:
    # two big meals a day from the high-protein ones, and one day a
    # week a meal out that goes over.
    big = [MEALS[3], MEALS[5], MEALS[6]]
    picks = [MEALS[0], MEALS[2], rnd.choice(big), rnd.choice(big), MEALS[8]]
    if n % 7 == 4:
        picks[3] = ("Burger and fries", 1250, 42, 110, 64)
    out = []
    for name, cal, pro, carb, fat in picks:
        j = rnd.uniform(.97, 1.03)
        out.append({"id": uid(), "cal": round(cal * j), "pro": round(pro * j), "carb": round(carb * j),
                    "fat": round(fat * j), "note": name, "t": 1})
    return out


def lifts_for(cat, weeks_ago):
    out = []
    for i, (name, w0, step, reps, sets) in enumerate(MOVES[cat]):
        w = w0 + step * (5 - weeks_ago)
        ss = []
        for s in range(sets):
            r = reps - (1 if s == sets - 1 and rnd.random() < .5 else 0)
            ss.append({"w": w, "r": r})
        out.append({"id": uid(), "cat": cat, "movement": name, "sets": ss,
                    "doneAt": i + 1, "lapMs": rnd.randint(7, 11) * 60000, "closed": True})
    return out


def demo_log():
    days = {}
    for n in range(36, 0, -1):
        k = key(n)
        d = {"food": food_day(n), "updated": 1, "goal": GOAL, "water": rnd.choice([3000, 3000, 3250, 2750])}
        cat = split_on(n)
        # Sunday is the rest day, as the plan says
        dow = ((today - datetime.timedelta(days=n)).weekday() + 1) % 7
        if dow != 0:
            d["lifts"] = lifts_for(cat, n // 7)
            d["workoutMs"] = rnd.randint(52, 70) * 60000
            d["gym"] = "g1"; d["gymLocked"] = True
        if n % 3 == 0:
            d["cardio"] = [{"id": uid(), "type": "Incline walk", "min": 25, "dist": 1.6, "cal": 210, "t": 1}]
        if n % 2 == 0:
            d["bw"] = round(186.5 - (36 - n) * 0.12 + rnd.uniform(-.4, .4), 1)
        d["supps"] = {"s1": True, "s2": True, "s3": n % 4 != 0}
        if n in (34, 20, 6):
            d["prog"] = {"at": NOW - n * 86400000, "note": ["Starting point", "Shoulders filling out", "Leaner, stronger"][[34, 20, 6].index(n)]}
        days[k] = d
    # today: halfway through a pull day
    pulls = lifts_for("pull", 0)
    row, pulldown = pulls[0], pulls[1]
    row["lapMs"] = 9 * 60000
    pulldown.update({"sets": pulldown["sets"][:2]})
    for m in (pulldown,):
        m.pop("doneAt"); m.pop("lapMs"); m.pop("closed")
    rest = [{"id": uid(), "cat": "pull", "movement": m[0], "sets": []} for m in MOVES["pull"][2:]]
    days[T] = {
        "food": [
            {"id": uid(), "cal": 520, "pro": 32, "carb": 52, "fat": 19, "note": "Eggs and oats", "t": 1},
            {"id": uid(), "cal": 160, "pro": 30, "carb": 6, "fat": 2, "note": "Protein shake", "t": 1},
            {"id": uid(), "note": "chicken burrito bowl", "items": [
                {"id": uid(), "cal": 330, "pro": 50, "carb": 0, "fat": 13, "note": "Grilled chicken · 6 oz", "est": True},
                {"id": uid(), "cal": 210, "pro": 4, "carb": 45, "fat": 2, "note": "Rice · 1 cup", "est": True},
                {"id": uid(), "cal": 120, "pro": 8, "carb": 20, "fat": 1, "note": "Black beans · ½ cup", "est": True},
                {"id": uid(), "cal": 25, "pro": 1, "carb": 5, "fat": 0, "note": "Salsa · ¼ cup", "est": True}]},
            {"id": uid(), "cal": 180, "pro": 24, "carb": 8, "fat": 5, "note": "Cottage cheese", "t": 1},
            {"id": uid(), "cal": 640, "pro": 44, "carb": 52, "fat": 26, "note": "Salmon, potatoes and greens", "t": 1},
        ],
        "lifts": [row, pulldown] + rest,
        "workoutStart": NOW - 23 * 60000,
        "gym": "g1",
        "water": 2250,
        "cardio": [{"id": uid(), "type": "Incline walk", "min": 20, "dist": 1.3, "cal": 160, "t": NOW - 4 * 3600000}],
        "supps": {"s1": True, "s2": True},
        "updated": 1, "goal": GOAL,
    }
    return {
        "v": 1, "days": days, "goal": GOAL, "build": BUILD, "region": "United States",
        "routine": {"name": "Push pull legs", "days": SPLIT},
        "moves": {c: [m[0] for m in MOVES[c]] for c in MOVES}, "movesOwned": True,
        "week": week_plan(), "gymGoal": 6, "bwGoal": 178,
        "gyms": [{"id": "g1", "name": "Downtown gym", "tag": "DT"}], "gymLast": "g1", "gymAsked": True,
        "cardioTypes": ["Incline walk", "Bike"], "cardioGoal": {"kind": "steps", "period": "week", "v": 70000},
        "healthSteps": {"on": True, "at": NOW - 3600000},
        "cfOn": True, "waterOn": True, "waterGoalMl": 3000,
        "supps": [{"id": "s1", "name": "Creatine", "dose": "5 g"}, {"id": "s2", "name": "Vitamin D", "dose": "2000 IU"},
                  {"id": "s3", "name": "Fish oil", "dose": "2 caps"}],
        "pantry": [
            {"id": "p1", "name": "Eggs", "serveQty": 1, "serveUnit": "egg", "serveG": 50, "sCal": 72, "sPro": 6, "sCarb": 0, "sFat": 5, "aliases": [], "secs": ["breakfast"]},
            {"id": "p2", "name": "Rolled oats", "serveQty": 0.5, "serveUnit": "cup", "serveG": 40, "sCal": 150, "sPro": 5, "sCarb": 27, "sFat": 3, "aliases": ["oats"], "secs": ["breakfast"]},
            {"id": "p3", "name": "Whey protein", "serveQty": 1, "serveUnit": "scoop", "serveG": 31, "sCal": 120, "sPro": 24, "sCarb": 3, "sFat": 1, "aliases": ["shake"], "secs": ["snacks"]},
            {"id": "p4", "name": "Chicken breast", "serveQty": 4, "serveUnit": "oz", "serveG": 112, "sCal": 187, "sPro": 35, "sCarb": 0, "sFat": 4, "aliases": [], "secs": ["dinner"]},
            {"id": "p5", "name": "Jasmine rice", "serveQty": 1, "serveUnit": "cup", "serveG": 158, "sCal": 205, "sPro": 4, "sCarb": 45, "sFat": 0, "aliases": ["rice"], "secs": ["dinner"]},
            {"id": "p6", "name": "Cottage cheese", "serveQty": 0.5, "serveUnit": "cup", "serveG": 113, "sCal": 90, "sPro": 12, "sCarb": 4, "sFat": 2.5, "aliases": [], "secs": ["snacks"]},
        ],
        "profile": {"name": "Alex", "dob": "1996-05-14", "sex": "m", "ft": 6, "inch": 0, "act": "1.55", "aim": "-300", "setup": True},
        "consent": {"adult": True, "terms": TERMS, "termsAt": NOW - 40 * 86400000, "ai": True, "aiAt": NOW - 40 * 86400000},
        "lastBackupAt": NOW - 3600000, "seen": True, "theme": "dark",
    }


# The iPhone app's shell, as tests/darkcheck.py stands it in: the log in
# native storage, Apple Health's daily steps on hand.
SHELL = """(() => {
  const prefs = { 'CapacitorStorage.iron-ledger-v1': %s }, steps = %s;
  window.Capacitor = {
    isNativePlatform: () => true, getPlatform: () => 'ios',
    isPluginAvailable: (n) => n === 'Preferences' || n === 'HealthSteps',
    nativePromise: (plugin, method, o) => {
      o = o || {};
      if (plugin === 'Preferences') {
        if (method === 'set') prefs['CapacitorStorage.' + o.key] = o.value;
        return Promise.resolve(method === 'get' ? { value: prefs['CapacitorStorage.' + o.key] || null } : {});
      }
      if (method === 'status') return Promise.resolve({ available: true, asked: true });
      if (method === 'days') return Promise.resolve({ days: steps });
      return Promise.resolve({});
    }
  };
})();"""


app_src = open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()
BUILD = re.search(r'var BUILD = "([^"]+)"', app_src).group(1)
TERMS = re.search(r'var TERMS = "([^"]+)"', app_src).group(1)


def steps_by_day():
    return {key(n): rnd.randint(9000, 13000) for n in range(0, 36)} | {T: 6840}


# ---------- the screens ----------
# Ask an agent answers through the stand-in relay the suites use
# (tests/fakeai.py), so the screen is the same every run and no request
# reaches the real finder or spends its daily allowance.
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fakeai, logways


def open_app(b, log):
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=SCALE,
                        has_touch=True, is_mobile=True, color_scheme="dark")
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(SHELL % (json.dumps(json.dumps(log)), json.dumps(steps_by_day())))
    fakeai.phone(ctx)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://" + ROOT.replace("\\", "/") + "/mntl-dt.html")
    p.wait_for_timeout(1200)
    return ctx, p, errs


def tab(p, name):
    p.click('.tabs button[data-tab="%s"]' % name)
    p.wait_for_timeout(500)
    p.evaluate("window.scrollTo(0, 0)")
    p.wait_for_timeout(300)


def bring_up(p, text, gap):
    """Scroll so the heading that reads `text` sits `gap` points under the slim
    bar that takes the stage's place once the page scrolls."""
    p.evaluate("""([text, gap]) => {
      const el = [...document.querySelectorAll('#view *')].find(e =>
        e.children.length < 3 && e.offsetParent && e.textContent.trim().startsWith(text));
      if (!el) throw new Error('nothing reads ' + text);
      window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 300);
    }""", [text, gap])
    p.wait_for_timeout(500)          # the slim bar slides in
    p.evaluate("""([text, gap]) => {
      const el = [...document.querySelectorAll('#view *')].find(e =>
        e.children.length < 3 && e.offsetParent && e.textContent.trim().startsWith(text));
      const bar = document.getElementById('stageMini');
      const h = bar ? Math.max(bar.getBoundingClientRect().bottom, 0) : 0;
      window.scrollTo(0, el.getBoundingClientRect().top + scrollY - h - gap);
    }""", [text, gap])
    p.wait_for_timeout(500)


def gym(p):
    tab(p, "gym")
    p.click('button.cat[data-cat="pull"]'); p.wait_for_timeout(400)
    # the movement under way: last time's sets, today's rows and the check
    bring_up(p, "Lat Pulldown", 26)


def macros(p):
    tab(p, "macros")


def ask(p):
    tab(p, "macros")
    logways.open_way(p, "estimate")
    p.fill("#estText", "two eggs, two slices of toast and a banana")
    p.click("#runEst"); p.wait_for_timeout(1500)
    bring_up(p, "Ask an agent", 14)


def body(p):
    # yesterday's push day, locked in: Day complete and the recovery map
    tab(p, "gym")
    p.evaluate("""() => [...document.querySelectorAll('button')]
      .find(x => /previous day/i.test(x.getAttribute('aria-label') || '')).click()""")
    p.wait_for_timeout(600)
    bring_up(p, "Day complete", 20)


def cardio(p):
    tab(p, "cardio")


def calendar(p):
    tab(p, "log")


# (file, what to do, the headline with one word in *teal* or **gold**, the line under it)
SCREENS = [
    ("1-gym", gym, "Every set. The number to *beat*.", "Last time sits right beside today."),
    ("2-macros", macros, "Hit your protein. Earn the **gold**.", "Calories and protein on one bar."),
    ("3-ask", ask, "Say what you *ate*.", "Ask an agent finds the calories and macros."),
    ("4-recovery", body, "See what needs *rest*.", "A body map from the sets you logged."),
    ("5-cardio", cardio, "Steps from Apple *Health*.", "Or minutes, miles, calories and sessions."),
    ("6-log", calendar, "No account. Your log stays *yours*.", "Everything is kept on your phone."),
]


# ---------- the caption around each screen ----------
# The app's own floor, chalk, teal and gold (the Chalk and Iron tokens in
# mntl-dt.html, dark theme) and its own lettering from fonts/.
FLOOR = re.search(r':root\[data-theme="dark"\] \{ --floor: (#[0-9A-Fa-f]{6})', app_src).group(1)
LINE = re.search(r':root\[data-theme="dark"\] \{[^}]*--floor-line: (#[0-9A-Fa-f]{6})', app_src).group(1)
CHALK = re.search(r"--chalk: (#[0-9A-Fa-f]{6})", app_src).group(1)
CHALK_DIM = re.search(r"--chalk-dim: (#[0-9A-Fa-f]{6})", app_src).group(1)
TEAL = re.search(r':root\[data-theme="dark"\] \{[^}]*?--accent: (#[0-9A-Fa-f]{6})', app_src, re.S).group(1)
GOLD = re.search(r"--gold: (#[0-9A-Fa-f]{6}); --gold-hub", app_src).group(1)

STATUS = """<svg viewBox="0 0 440 50" width="100%%" height="100%%">
  <text x="58" y="33" font-family="Archivo" font-weight="700" font-size="17" fill="%(c)s" text-anchor="middle">9:41</text>
  <g fill="%(c)s" transform="translate(316 21)">
    <rect x="0" y="8" width="3.4" height="4.5" rx="1"/><rect x="5" y="5.5" width="3.4" height="7" rx="1"/>
    <rect x="10" y="3" width="3.4" height="9.5" rx="1"/><rect x="15" y="0" width="3.4" height="12.5" rx="1"/>
  </g>
  <g fill="none" stroke="%(c)s" stroke-width="2" stroke-linecap="round" transform="translate(345 20)">
    <path d="M1 4.5a11 11 0 0 1 15 0"/><path d="M4 7.6a6.6 6.6 0 0 1 9 0"/><circle cx="8.5" cy="11" r="1.2" fill="%(c)s" stroke="none"/>
  </g>
  <g transform="translate(372 19)">
    <rect x=".5" y=".5" width="24" height="12.5" rx="3.8" fill="none" stroke="%(c)s" stroke-opacity=".45"/>
    <rect x="2.5" y="2.5" width="18" height="8.5" rx="2" fill="%(c)s"/>
    <path d="M26.5 4.6v4.3a2.2 2.2 0 0 0 0-4.3z" fill="%(c)s" fill-opacity=".45"/>
  </g>
</svg>"""


def headline(text):
    text = re.sub(r"\*\*(.+?)\*\*", r'<b class="gold">\1</b>', text)
    return re.sub(r"\*(.+?)\*", r'<b class="teal">\1</b>', text)


def framed(shot, title, sub):
    fonts = "file://" + ROOT.replace("\\", "/") + "/fonts/"
    return """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: 'Big Shoulders Display'; font-weight: 100 900; src: url(%(f)sBigShoulders-latin.woff2) format('woff2'); }
@font-face { font-family: 'Archivo'; font-weight: 400 800; font-stretch: 100%% 125%%; src: url(%(f)sArchivo-latin.woff2) format('woff2'); }
html, body { margin: 0; width: %(w)dpx; height: %(h)dpx; overflow: hidden; }
body { background: %(floor)s radial-gradient(rgba(242,241,236,.06) 1px, transparent 1.3px) 0 0 / 14px 14px;
  color: %(chalk)s; display: flex; flex-direction: column; align-items: center; }
header { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 18px 0 8px; }
h1 { margin: 0 26px; font: 800 46px/0.94 'Big Shoulders Display', sans-serif; text-transform: uppercase;
  letter-spacing: .01em; text-align: center; text-wrap: balance; }
b { font-weight: 800; } .teal { color: %(teal)s; } .gold { color: %(gold)s; }
p { margin: 12px 30px 0; font: 500 16.5px/1.35 'Archivo', sans-serif; color: %(dim)s; text-align: center; }
.phone { flex: none; margin-bottom: 24px; width: 316px; border-radius: 40px; overflow: hidden;
  border: 1.5px solid %(line)s; box-shadow: 0 0 0 6px #000, 0 0 0 7.5px %(line)s, 0 24px 60px rgba(0,0,0,.6); background: #000; }
.status { height: 36px; background: %(floor)s; }
.phone img { display: block; width: 100%%; }
</style></head><body>
<header><h1>%(title)s</h1><p>%(sub)s</p></header>
<div class="phone"><div class="status">%(status)s</div><img src="file://%(shot)s"></div>
</body></html>""" % {"f": fonts, "w": W, "h": H, "floor": FLOOR, "chalk": CHALK, "dim": CHALK_DIM, "teal": TEAL,
                     "gold": GOLD, "line": LINE, "title": headline(title), "sub": sub,
                     "status": STATUS % {"c": CHALK}, "shot": shot.replace("\\", "/")}


def main():
    plain_dir = os.path.join(OUT, "plain")
    os.makedirs(plain_dir, exist_ok=True)
    log = demo_log()
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, go, title, sub in SCREENS:
            if only and not any(o in name for o in only):
                continue
            ctx, p, errs = open_app(b, log)
            go(p)
            shot = os.path.join(plain_dir, name + ".png")
            p.screenshot(path=shot)
            ctx.close()
            if errs:
                sys.exit("%s: the app threw %s" % (name, errs))
            out = shot
            if not PLAIN:
                page_file = os.path.join(plain_dir, name + ".html")
                with open(page_file, "w", encoding="utf-8") as f:
                    f.write(framed(shot, title, sub))
                pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
                pg.goto("file://" + page_file.replace("\\", "/"))
                pg.wait_for_timeout(400)
                out = os.path.join(OUT, name + ".png")
                pg.screenshot(path=out)
                pg.close()
                os.remove(page_file)
            print(out)
        b.close()


if __name__ == "__main__":
    main()
