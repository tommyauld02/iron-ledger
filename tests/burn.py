"""Calories burned (b106): what a workout, a cardio session and a day's steps burned.

Asked for by the owner (2026-11-20): an estimate at the end of a workout, on
cardio, and anywhere else it fits. He chose "shown only": the burn is never
added to the food target, because How active already counts training there.

Each number is the EXTRA on top of the resting burn, rounded to ten:
  - the gym: the workout clock's time x weight x 2.5 (lifting, 3.5 MET)
  - walking and running: 0.5 and 1 kcal per kg per km, from the miles typed
    or the minutes at an ordinary pace
  - anything else by its name's MET; a name the app doesn't know is asked
    about once (Easy, Steady, Hard), and the answer is the type's
  - steps: steps x 41.5% of the height = km, at the walking cost, less any
    walk or run session's own distance, so nothing is counted twice
  - a number typed from a machine or a watch always wins

The weight is the day's (the last weigh-in on or before it). Without a weight
nothing is estimated; without a height, steps aren't. Each says what it needs.

Pinned to noon today, so midnight passing never moves a day.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
import os, sys, re, json, math, datetime
d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d

SRC = open("mntl-dt.html", encoding="utf-8").read()
BUILD = re.search(r'var BUILD = "([^"]+)"', SRC).group(1)
TERMS = re.search(r'var TERMS = "([^"]+)"', SRC).group(1)
T0 = datetime.date.today()
def k(n): return (T0 + datetime.timedelta(days=n)).isoformat()
T = k(0)
SUN = T0 - datetime.timedelta(days=(T0.weekday() + 1) % 7)       # this week's Sunday (the default start)
def wk(n): return (SUN + datetime.timedelta(days=n)).isoformat()

CLOCK = """
 (() => {
   const REAL = Date;
   window.__off = new REAL(%d, %d, %d, 12).getTime() - REAL.now();
   class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+window.__off); else super(...a);} static now(){return REAL.now()+window.__off;} }
   window.Date = FD;
 })();
""" % (T0.year, T0.month - 1, T0.day)

LB_KG = 0.45359237
KG = 182 * LB_KG
def rnd(x): return int(math.floor(x / 10.0 + 0.5)) * 10   # the app's Math.round, to ten: .5 goes up (Python's round() would go to even)
def fmt(n): return "{:,}".format(int(round(n)))
G = {"cal": {"dir": "-", "v": 2270}, "pro": {"dir": "+", "v": 160}}
MOVES = {"push": ["Bench Press"]}
ME = {"name": "Tommy", "dob": "1992-03-14", "sex": "m", "ft": "5", "inch": "11", "act": "1.55", "aim": "-500", "setup": True}

def store(days, **kw):
    s = {"v": 1, "build": BUILD, "adult": True, "terms": TERMS, "termsAt": 1, "region": "United States", "pantry": [],
         "moves": MOVES, "movesOwned": True, "goal": G, "days": days, "wrapSeen": SUN.isoformat(),
         "profile": dict(ME), "lineGot": {}}
    s.update(kw)
    return s
def today(**kw):
    day = {"food": [], "lifts": [], "updated": 1, "goal": G, "bw": 182.0}
    day.update(kw)
    return {T: day}

res = []
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(CLOCK)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://" + d + "/mntl-dt.html")
    p.wait_for_timeout(300)

    def open_with(s, tab=None):
        p.evaluate("s=>{localStorage.clear(); localStorage.setItem('iron-ledger-v1',JSON.stringify(s))}", s)
        p.goto("file://" + d + "/mntl-dt.html")
        p.wait_for_function("()=>{const v=document.getElementById('view');return !!v&&v.children.length>0}", timeout=15000)
        p.wait_for_timeout(200)
        # What's new and the week wrap-up are other suites' business.
        for sel in ["#wrapDone", "#newsDone", "#wnDone"]:
            if p.locator(sel).count() and p.locator(sel).first.is_visible():
                p.click(sel); p.wait_for_timeout(150)
        if tab:
            p.click('[data-tab="%s"]' % tab); p.wait_for_timeout(300)
    def text(sel):
        return p.evaluate("s=>{const e=document.querySelector(s);return e?e.innerText:''}", sel)
    def saved():
        return p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))") or {}
    def bar():
        return p.evaluate("()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent")
    def card(cid):
        return p.evaluate("""c=>{const e=document.querySelector('.cardio-card[data-cid="'+c+'"]'); if(!e) return null;
          const s=[...e.querySelectorAll('.cc-stats > div')].map(x=>x.innerText.replace(/\\n/g,' '));
          return {kcal: s[2]||'', est: !!e.querySelector('.cc-stats b.is-est'), foot: e.querySelector('.lift-foot span').textContent,
                  ask: !!e.querySelector('[data-ceffort]')}}""", cid)
    def reachable(sel):
        return p.evaluate("""s=>[...document.querySelectorAll(s)].map(e=>{e.scrollIntoView({block:'center'});
          const r=e.getBoundingClientRect(), hit=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
          return {w:Math.round(r.width), h:Math.round(r.height), ok: !!hit && (hit===e || e.contains(hit))}})""", sel)

    # ================= the gym: Day complete =================
    lifts = [{"id": "l1", "cat": "push", "movement": "Bench Press", "sets": [{"w": 185, "r": 8}] * 3}]
    open_with(store(today(lifts=lifts, workoutMs=58 * 60000, gymLocked=True, cat="push")), "gym")
    want = rnd(2.5 * KG * 58 / 60)
    check("gym: Day complete says what the workout burned", text("#ddTime") == "TOOK 58:00 · BURNED ABOUT %d KCAL" % want
          or text("#ddTime").lower() == ("took 58:00 · burned about %d kcal" % want), text("#ddTime"))
    check("gym: and what it stands on, naming the weight", text("#ddBurn") == "An estimate from your weight, 182.0 lb, and the time on the clock.", text("#ddBurn"))
    check("gym: it changes nothing in the log", "burn" not in json.dumps(saved()["days"][T]).lower())

    open_with(store(today(lifts=lifts, workoutMs=58 * 60000, gymLocked=True, cat="push"), bwUnit="kg"), "gym")
    check("gym: the weight in the unit chosen", "82.6 kg" in text("#ddBurn"), text("#ddBurn"))

    nob = today(lifts=lifts, workoutMs=58 * 60000, gymLocked=True, cat="push"); del nob[T]["bw"]
    open_with(store(nob), "gym")
    check("gym: no weight, no number, and it says what it needs",
          "burned" not in text("#ddTime").lower() and text("#ddBurn") == "Add your weight in Settings → You to see what this burned.",
          text("#ddTime") + " | " + text("#ddBurn"))

    open_with(store(today(lifts=lifts, gymLocked=True, cat="push")), "gym")
    check("gym: no clock, no time and no burn", p.locator("#ddTime").count() == 0 and p.locator("#ddBurn").count() == 0)

    # ================= cardio: each session =================
    sess = [{"id": "c1", "type": "Bike", "min": 30, "t": 1},
            {"id": "c2", "type": "Rower", "min": 15, "cal": 180, "t": 2},
            {"id": "c3", "type": "Walk", "min": 40, "dist": 2.0, "t": 3},
            {"id": "c4", "type": "Run", "min": 25, "dist": 2.5, "t": 4},
            {"id": "c5", "type": "Incline walk", "min": 30, "t": 5},
            {"id": "c6", "type": "Treadmill", "min": 20, "t": 6}]
    E = {"c1": rnd(6 * KG * 30 / 60), "c3": rnd(0.5 * KG * 2.0 * 1.609344), "c4": rnd(1 * KG * 2.5 * 1.609344), "c5": rnd(5 * KG * 30 / 60)}
    open_with(store(today(cardio=sess)), "cardio")
    for cid, name in [("c1", "Bike, by its MET"), ("c3", "a walk, by its miles"), ("c4", "a run, by its miles"), ("c5", "an incline walk, uphill")]:
        c = card(cid)
        check("cardio: %s is estimated, and marked as one" % name,
              c and c["kcal"] == "~%s kcal · est." % fmt(E[cid]) and c["est"] and c["foot"].endswith("about %s kcal" % fmt(E[cid])), str(c))
    c = card("c2")
    check("cardio: calories typed from the machine win", c and c["kcal"] == "180 kcal" and not c["est"] and "about" not in c["foot"], str(c))
    c = card("c6")
    check("cardio: a name the app doesn't know has no number yet, and asks", c and c["kcal"] == "— kcal" and c["ask"], str(c))
    total = sum(E.values()) + 180
    head = text(".cardio-page .sec-title span")
    check("cardio: the day's minutes and what they burned", head == "160 min · about %s kcal today" % fmt(rnd(total)), head)
    hits = reachable('.cardio-card[data-cid="c6"] [data-ceffort]')
    check("cardio: the three answers are 44px and take the tap", len(hits) == 3 and all(h["h"] >= 44 and h["ok"] for h in hits), str(hits))

    p.click('.cardio-card[data-cid="c6"] [data-ceffort="steady"]'); p.wait_for_timeout(300)
    steady = rnd(5 * KG * 20 / 60)
    check("cardio: an answer says so on the bar", bar() == "Treadmill counts as steady", bar())
    check("cardio: and is kept for the type", saved().get("cardioEffort") == {"Treadmill": "steady"}, str(saved().get("cardioEffort")))
    c = card("c6")
    check("cardio: the card now has its estimate, and asks no more", c and c["kcal"] == "~%d kcal · est." % steady and not c["ask"], str(c))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    c = card("c6")
    check("cardio: Undo takes the answer back", not saved().get("cardioEffort") and c and c["ask"], str(saved().get("cardioEffort")))

    # Change: how hard, for a type the app doesn't know, and typed calories
    p.click('.cardio-card[data-cid="c6"] [data-cedit]'); p.wait_for_timeout(300)
    check("change: asks how hard, for a name it doesn't know", p.locator("[data-ceeff]").count() == 3)
    p.click('[data-ceeff="hard"]'); p.wait_for_timeout(100)
    p.click("#ceSave"); p.wait_for_timeout(300)
    hard = rnd(7 * KG * 20 / 60)
    c = card("c6")
    check("change: Save keeps how hard, says so, and the card has the new number", saved().get("cardioEffort") == {"Treadmill": "hard"}
          and bar() == "Changed Treadmill to 20 min" and c and c["kcal"] == "~%d kcal · est." % hard, bar() + " " + str(c))
    p.click('.cardio-card[data-cid="c1"] [data-cedit]'); p.wait_for_timeout(300)
    check("change: a name it knows isn't asked about", p.locator("[data-ceeff]").count() == 0)
    p.fill("#ceCal", "300"); p.click("#ceSave"); p.wait_for_timeout(300)
    c = card("c1")
    check("change: a typed number replaces the estimate", c and c["kcal"] == "300 kcal" and not c["est"], str(c))

    p.click("#cardioByHand"); p.wait_for_timeout(300)
    check("by hand: the calories box says what an empty one means",
          "Leave it empty and the app estimates it from your weight." in text("#cardioAdd"), text("#cardioAdd")[:200])
    p.click("#cAddCancel"); p.wait_for_timeout(200)

    # the day finished: the card's total is marked as holding an estimate
    open_with(store(today(cardio=sess[:2], cardioDone=True)), "cardio")
    stats = p.evaluate("()=>[...document.querySelectorAll('.daydone .dd-stats > div')].map(x=>x.innerText.replace(/\\n/g,' '))")
    check("cardio complete: the day's kcal, marked ~", stats and stats[-1].lower() == ("~%s kcal" % fmt(rnd(E["c1"] + 180))), str(stats))

    # the Calories goal counts estimates
    open_with(store(today(cardio=sess[:2]), cardioGoal={"kind": "cal", "period": "day", "v": 500}), "cardio")
    num = " ".join(text(".cardio-goal .cg-num").split())
    check("calories goal: estimates count toward it", num == "%s of 500 kcal" % fmt(E["c1"] + 180), num)

    # no weight: nothing is estimated
    nw = today(cardio=sess[:1]); del nw[T]["bw"]
    open_with(store(nw), "cardio")
    c = card("c1")
    check("cardio: no weight, no estimate", c and c["kcal"] == "— kcal" and not c["est"], str(c))

    # ================= steps =================
    SG = {"kind": "steps", "period": "day", "v": 10000}
    stride_km = 12240 * (71 * 2.54) * 0.415 / 100000
    open_with(store(today(steps=12240), cardioGoal=SG), "cardio")
    check("steps: what they burned, from weight and height",
          text("#stepsBurn") == "12,240 steps burned about %d kcal, from your weight and height" % rnd(0.5 * KG * stride_km), text("#stepsBurn"))
    open_with(store(today(steps=12240, cardio=[sess[3]]), cardioGoal=SG), "cardio")
    check("steps: a run's own steps aren't counted twice",
          text("#stepsBurn") == "12,240 steps burned about %d kcal, on top of your Run" % rnd(0.5 * KG * (stride_km - 2.5 * 1.609344)), text("#stepsBurn"))
    noh = store(today(steps=12240), cardioGoal=SG); noh["profile"] = {"name": "Tommy", "setup": True}
    open_with(noh, "cardio")
    check("steps: no height, and it says where to add one", text("#stepsBurn") == "Add your height in Settings → You to see what your steps burned.", text("#stepsBurn"))
    met = store(today(steps=12240), cardioGoal=SG, bwUnit="kg"); met["profile"] = dict(ME, cm=180); del met["profile"]["ft"]; del met["profile"]["inch"]
    open_with(met, "cardio")
    check("steps: a height in cm works the same",
          text("#stepsBurn").startswith("12,240 steps burned about %d kcal" % rnd(0.5 * KG * 12240 * 180 * 0.415 / 100000)), text("#stepsBurn"))
    open_with(store(today(steps=12240)), "cardio")
    check("steps: no line while the goal counts something else", p.locator("#stepsBurn").count() == 0)

    # ================= Settings: the height beside the weight =================
    open_with(store(today()))
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("settings: who, with the height", "Male · 5′11″ · 182.0 lb" in text("#setWho"), text("#setWho"))
    p.click("#setClose") if p.locator("#setClose").count() else None
    open_with(met)
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("settings: a height in cm, with kg", "180 cm · 82.6 kg" in text("#setWho"), text("#setWho"))

    # ================= the week wrap-up =================
    days = {}
    for n in range(-7, 0):
        days[wk(n)] = {"food": [{"id": "f%d" % n, "note": "Food", "cal": 2200, "pro": 160}], "lifts": [], "updated": 1, "goal": G,
                       "steps": 10000, "bw": 182.0}
    for n in (-6, -4, -2):
        days[wk(n)]["lifts"] = [{"id": "l%d" % n, "cat": "push", "movement": "Bench Press", "sets": [{"w": 185, "r": 8}] * 3}]
        days[wk(n)]["workoutMs"] = 3600000
    days[wk(-5)]["cardio"] = [{"id": "w1", "type": "Bike", "min": 30, "t": 1}]
    days[wk(-3)]["cardio"] = [{"id": "w2", "type": "Run", "min": 25, "dist": 2.5, "cal": 345, "t": 1}]
    open_with(store(days, wrapSeen=wk(-7)))
    if not p.locator("#wrapSheet").is_visible():
        p.click('[data-tab="log"]'); p.wait_for_timeout(300); p.click("#wrapOpen"); p.wait_for_timeout(300)
    secs = p.eval_on_selector_all("#wrapBody [data-wrap]", "e=>e.map(x=>x.dataset.wrap)")
    check("wrap-up: a Burned section, after Cardio", "burn" in secs and secs.index("burn") == secs.index("cardio") + 1, str(secs))
    gym = 3 * rnd(2.5 * KG)
    st1 = rnd(0.5 * KG * 10000 * (71 * 2.54) * 0.415 / 100000)
    st_run = rnd(0.5 * KG * (10000 * (71 * 2.54) * 0.415 / 100000 - 2.5 * 1.609344))
    steps = 6 * st1 + st_run
    cardio = rnd(6 * KG * 0.5) + 345
    tot = gym + cardio + steps
    bt = p.evaluate("()=>[...document.querySelectorAll('[data-wrap=\"burn\"] .wr-tiles > div')].map(e=>[e.querySelector('b').textContent,e.querySelector('span').textContent])")
    check("wrap-up: burned in all and a day, marked ~", bt == [["~" + fmt(rnd(tot)), "kcal, total"], ["~" + fmt(rnd(tot / 7.0)), "kcal a day"]], str(bt))
    bl = p.evaluate("()=>[...document.querySelectorAll('[data-wrap=\"burn\"] .wr-line')].map(e=>e.textContent)")
    check("wrap-up: where it came from, and that it's an estimate",
          len(bl) == 2 and bl[0] == "Gym about %s · cardio about %s · steps about %s." % (fmt(gym), fmt(rnd(cardio)), fmt(rnd(steps)))
          and "Your food target already allows for training." in bl[1], str(bl))
    ct = p.evaluate("()=>[...document.querySelectorAll('[data-wrap=\"cardio\"] .wr-tiles > div')].map(e=>e.querySelector('b').textContent+' '+e.querySelector('span').textContent)")
    check("wrap-up: cardio's kcal hold the estimate too", ("~%s kcal burned" % fmt(rnd(cardio))) in ct, str(ct))

    # ================= the food target never moves =================
    open_with(store(today(lifts=lifts, workoutMs=58 * 60000, gymLocked=True, cat="push", steps=12240, cardio=sess[:2]), cardioGoal=SG), "macros")
    check("shown only: the calorie target is the goal, untouched", "of 2,270 kcal" in text(".today-card"), text(".today-card")[:160])

    # ================= a small phone =================
    p.set_viewport_size({"width": 320, "height": 640})
    open_with(store(today(cardio=sess, steps=12240), cardioGoal=SG), "cardio")
    wide = p.evaluate("()=>document.documentElement.scrollWidth<=window.innerWidth")
    check("320px: the Cardio tab does not scroll sideways", wide)
    hits = reachable('.cardio-card[data-cid="c6"] [data-ceffort]')
    check("320px: the answers still take the tap", len(hits) == 3 and all(h["h"] >= 44 and h["w"] >= 44 and h["ok"] for h in hits), str(hits))

    check("no page errors", not errs, "; ".join(errs[:3]))
    b.close()

fails = [r for r in res if r[0] == "FAIL"]
for r in res:
    print(("  " if r[0] == "PASS" else "✕ ") + r[1] + ("" if r[0] == "PASS" else "  [" + r[2] + "]"))
print("%d passed, %d FAILED" % (len(res) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
