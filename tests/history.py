"""A lift's history (b108): every time a movement was done, on a line.

And, from the same list, Done bringing the next movement up.

Asked for by the owner (2026-11-21, from a list of improvements he was shown):
a log of every set should answer "is this lift going up?", and nothing did.

  - History, on an open card's Last box, opens a sheet: the best set each
    time (topSet(): five pounds is worth one rep, warm-ups never count), a
    line through them, the best ever in gold, the change from the first to
    the last on the line, and the sessions newest first. Twelve at most.
  - The best set is counted at the best ever's reps, by the same rule, so a
    135x10 and a 145x8 are the same height. A lift never done with weight is
    counted in reps.
  - Where counts, as it does for To beat: a gym's history is that gym's, the
    sheet switches between the gyms the movement was done at and Every gym,
    and a movement that takes its numbers from every gym has no switch.
  - Your lifts, on the Log: each movement's best set the last time and its
    change over the eight weeks before, newest first, six then Show all; a
    row opens the same sheet.
  - Nothing is stored: opening, switching and closing leave the log as it was.

Pinned to noon today, so midnight passing never moves a day.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
import os, sys, re, json, datetime
d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d

SRC = open("mntl-dt.html", encoding="utf-8").read()
BUILD = re.search(r'var BUILD = "([^"]+)"', SRC).group(1)
TERMS = re.search(r'var TERMS = "([^"]+)"', SRC).group(1)
T0 = datetime.date.today()
def k(n): return (T0 + datetime.timedelta(days=n)).isoformat()
T = k(0)

CLOCK = """
 (() => {
   const REAL = Date;
   window.__off = new REAL(%d, %d, %d, 12).getTime() - REAL.now();
   class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+window.__off); else super(...a);} static now(){return REAL.now()+window.__off;} }
   window.Date = FD;
 })();
""" % (T0.year, T0.month - 1, T0.day)

G = {"cal": {"dir": "-", "v": 2270}, "pro": {"dir": "+", "v": 160}}
MOVES = {"push": ["Bench Press", "Overhead Press", "Dip", "DB Curl", "Squat", "Fly", "Cable Row", "Lunge", "Lateral Raise"]}
GYMS = [{"id": "g1", "name": "Downtown", "tag": "DT"}, {"id": "g2", "name": "Apartment", "tag": "APT"}]
ME = {"name": "Tommy", "dob": "1992-03-14", "sex": "m", "ft": "5", "inch": "11", "act": "1.55", "aim": "-500", "setup": True}
uid = [0]
def lift(mv, sets):
    uid[0] += 1
    return {"id": "l%d" % uid[0], "cat": "push", "movement": mv,
            "sets": [dict(zip(("w", "r", "tech"), s)) if len(s) == 3 else {"w": s[0], "r": s[1]} for s in sets]}

# Bench Press at DT, once a week for six weeks, warm-up first (a heavy
# "warm-up" proves a warm-up is never the best). One heavier day at APT,
# which DT's line must not show. Today, at DT, one set in.
BENCH = [(-42, 185, 8), (-35, 185, 9), (-28, 190, 8), (-21, 190, 9), (-14, 195, 8), (-7, 200, 8)]
days = {}
def on(n, gym, *lifts):
    day = days.setdefault(k(n), {"food": [], "lifts": [], "updated": 1, "goal": G})
    if gym: day["gym"] = gym
    day["lifts"].extend(lifts)
for n, w, r in BENCH:
    on(n, "g1", lift("Bench Press", [(250, 1, "warmup"), (w, r), (w, r - 1)]))
on(-10, "g2", lift("Bench Press", [(225, 8)]))
# Overhead Press, mixed reps: 95x10 first, 105x8 last and best (R = 8).
# 95x10 is worth 95 + 5x2 = 105 at 8 reps, so the line is level.
on(-30, "g1", lift("Overhead Press", [(95, 10)]))
on(-16, "g1", lift("Overhead Press", [(100, 9)]))
on(-2, "g1", lift("Overhead Press", [(105, 8)]))
# Dip, body weight: 8, 10 and 11 reps.
on(-29, "g1", lift("Dip", [(0, 8)]))
on(-15, "g1", lift("Dip", [(0, 10)]))
on(-1, "g1", lift("Dip", [(0, 11)]))
# DB Curl takes its numbers from every gym: no switch.
on(-20, "g1", lift("DB Curl", [(35, 10)]))
on(-6, "g2", lift("DB Curl", [(40, 10)]))
# Squat, fourteen times, best the very first and over eight weeks before the
# last: off the twelve shown, and outside Your lifts' eight weeks.
on(-72, "g1", lift("Squat", [(315, 5)]))
for i in range(13):
    on(-60 + i * 4, "g1", lift("Squat", [(275, 5)]))
# Lateral Raise, long ago: the seventh, behind Show all.
on(-50, "g1", lift("Lateral Raise", [(20, 15)]))
# Fly only at APT: today at DT is a first time here.
on(-9, "g2", lift("Fly", [(150, 12)]))
# Cable Row and Lunge: nothing but warm-ups, and nothing at all.
on(-8, "g1", lift("Cable Row", [(100, 12, "warmup")]))
today = {"food": [], "updated": 1, "goal": G, "cat": "push", "gym": "g1", "lifts": [
    lift("Bench Press", [(200, 9)]), lift("Fly", []), lift("Lunge", []), lift("Cable Row", [])]}
days[T] = today

def store(**kw):
    s = {"v": 1, "build": BUILD, "adult": True, "terms": TERMS, "termsAt": 1, "region": "United States", "pantry": [],
         "moves": MOVES, "movesOwned": True, "goal": G, "days": json.loads(json.dumps(days)), "wrapSeen": T,
         "profile": dict(ME), "lineGot": {}, "gyms": GYMS, "gymLast": "g1", "gymAsked": True,
         "gymShared": {"DB Curl": True}, "seen": True}
    s.update(kw)
    return s

def worth(w, r): return w / 5.0 + r
def short(key):
    dt = datetime.date.fromisoformat(key)
    return dt.strftime("%b ") + str(dt.day)

res = []
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
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
        for sel in ["#wrapDone", "#newsDone", "#wnDone"]:
            if p.locator(sel).count() and p.locator(sel).first.is_visible():
                p.click(sel); p.wait_for_timeout(150)
        if tab:
            p.click('[data-tab="%s"]' % tab); p.wait_for_timeout(300)
    def saved(): return p.evaluate("()=>localStorage.getItem('iron-ledger-v1')")
    def sheet_open(): return p.evaluate("()=>!document.getElementById('histSheet').hidden")
    def body(): return p.evaluate("()=>document.getElementById('histBody').innerText")
    def rows(): return p.evaluate("()=>[...document.querySelectorAll('#histBody .hist-row')].map(r=>[r.dataset.histday,r.querySelector('.hr-when').textContent,r.querySelector('.hr-what').textContent,r.classList.contains('is-best')])")
    def change(): return p.evaluate("()=>{const e=document.getElementById('histCh');return e?[e.textContent,e.className]:null}")
    def scopes(): return p.evaluate("()=>[...document.querySelectorAll('[data-histscope]')].map(b=>[b.textContent,b.getAttribute('aria-pressed')])")
    def reach(sel):
        return p.evaluate("""s=>[...document.querySelectorAll(s)].filter(e=>e.offsetParent).map(e=>{
          e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect();
          const h=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
          return {w:Math.round(r.width), h:Math.round(r.height), ok: !!h && (h===e || e.contains(h))};})""", sel)
    def cardbtn(mv): return '.lift [data-hist="%s"]' % mv

    # ================= the card =================
    open_with(store(), "gym")
    before = saved()
    btn = reach(cardbtn("Bench Press"))
    check("card: History sits in the Last box", p.locator('.lift .lastbox [data-hist="Bench Press"]').count() == 1)
    check("card: History is 44px and takes the tap", len(btn) == 1 and btn[0]["w"] >= 44 and btn[0]["h"] >= 44 and btn[0]["ok"], str(btn))
    col = p.evaluate("""()=>{const b=document.querySelector('.lift [data-hist="Bench Press"]'), t=document.createElement('i');
      t.style.color='var(--accent)'; document.body.appendChild(t); const a=getComputedStyle(t).color; t.remove();
      return [getComputedStyle(b).color, a];}""")
    check("card: History is teal, because it can be tapped", col[0] == col[1], str(col))
    check("card: the set to beat (here, Beaten) is still on the line beside it",
          p.evaluate("()=>document.querySelector('.lift .lastbox .lb-foot .beat').innerText").startswith("\u2191 Beaten"))
    check("card: a first time at this gym, done elsewhere, still has History",
          p.locator(cardbtn("Fly")).count() == 1 and p.locator('.lift .lastbox [data-hist="Fly"]').count() == 0)
    check("card: never done (or only warm-ups) has no History",
          p.locator(cardbtn("Lunge")).count() == 0 and p.locator(cardbtn("Cable Row")).count() == 0)

    # ================= the sheet, at DT =================
    p.locator(cardbtn("Bench Press")).click(); p.wait_for_timeout(300)
    check("sheet: History opens it", sheet_open())
    check("sheet: named for the movement", p.evaluate("()=>document.querySelector('#histBody h2').textContent") == "Bench Press")
    dt = [(n, w, r) for n, w, r in BENCH] + [(0, 200, 9)]
    best = max(dt, key=lambda x: (worth(x[1], x[2]), x[1]))
    check("sheet: the best ever, in gold, by five pounds a rep (a warm-up never)",
          p.evaluate("()=>document.querySelector('#histBody .hist-best').textContent") == "★ Best %dx%d".replace("x", "×") % (best[1], best[2]),
          p.evaluate("()=>document.querySelector('#histBody .hist-best').textContent"))
    rw = rows()
    check("sheet: one row a time it was done at DT, newest first, Today on top",
          [r[0] for r in rw] == [k(n) for n, _, _ in reversed(dt)] and rw[0][1] == "Today", str([r[0] for r in rw]))
    check("sheet: APT's heavier day is not on DT's line", k(-10) not in [r[0] for r in rw])
    check("sheet: each row says its sets and its best set",
          rw[1][2] == "3 sets · best 200×8" and rw[0][2] == "1 set · best ★ 200×9", str(rw[:2]))
    check("sheet: only the best ever's row is gold", [r[3] for r in rw] == [True] + [False] * (len(rw) - 1), str([r[3] for r in rw]))
    check("sheet: a dot a time, the best ever's gold",
          p.evaluate("()=>[document.querySelectorAll('#histBody circle').length, document.querySelectorAll('#histBody circle[data-histtop]').length]") == [7, 1])
    # first 185x8, last 200x9, counted at 9 reps: 180 then 200, up 20
    weeks = round(42 / 7.0)
    check("sheet: up from the first to the last, at the best ever's reps",
          change() == ["▲ Up 20 lb in %d weeks" % weeks, "hist-ch is-up"], str(change()))
    check("sheet: says where, and that warm-ups are left out, and how it counts mixed reps",
          "at DT, warm-ups left out" in body() and "Counted at 9 reps: 5 lb is worth one rep." in body(), body()[:200])
    check("sheet: the switch has each gym it was done at and Every gym, DT pressed",
          scopes() == [["DT", "true"], ["APT", "false"], ["Every gym", "false"]], str(scopes()))
    seg = reach("[data-histscope]") + reach("#histDone")
    check("sheet: its buttons are 44px and take the tap", len(seg) == 4 and all(x["h"] >= 44 and x["w"] >= 44 and x["ok"] for x in seg), str(seg))

    p.click('[data-histscope="g2"]'); p.wait_for_timeout(250)
    check("switch: APT shows only APT's day", [r[0] for r in rows()] == [k(-10)] and scopes()[1][1] == "true", str(rows()))
    check("switch: one time is a row and a word, not a line",
          "Once so far" in body() and p.locator("#histBody svg").count() == 0 and change() is None)
    p.click('[data-histscope=""]'); p.wait_for_timeout(250)
    ev = rows()
    check("switch: Every gym shows both gyms, each row naming its gym",
          len(ev) == 8 and ev[0][1] == "Today · DT" and ("%s · APT" % short(k(-10))) in [r[1] for r in ev], str([r[1] for r in ev]))
    check("switch: Every gym says so", "at every gym" in body())
    p.click("#histDone"); p.wait_for_timeout(200)
    check("Done closes it", not sheet_open())
    p.locator(cardbtn("Fly")).click(); p.wait_for_timeout(300)
    check("a first time here opens at the gym it was done at, with no switch to nowhere",
          [r[0] for r in rows()] == [k(-9)] and "at APT" in body() and not scopes(), str(scopes()))
    p.mouse.click(200, 30); p.wait_for_timeout(200)
    check("a tap on the shade closes it", not sheet_open())
    check("nothing is saved by looking", saved() == before)

    # ================= Your lifts, on the Log =================
    open_with(store(), "log")
    before = saved()
    names = p.evaluate("()=>[...document.querySelectorAll('#liftsCard .lc-row')].map(r=>r.querySelector('.lc-name').textContent)")
    check("log: Your lifts, newest first, six of them",
          names == ["Bench Press", "Dip", "Overhead Press", "DB Curl", "Fly", "Squat"], str(names))
    check("log: Show all names how many", p.evaluate("()=>document.getElementById('liftsMore').textContent") == "Show all 7")
    def row(mv):
        return p.evaluate("""m=>{const r=[...document.querySelectorAll('#liftsCard .lc-row')].find(x=>x.dataset.hist===m);
          return r?[r.querySelector('.lc-best').textContent, r.querySelector('.lc-best').className, r.querySelector('.lc-ch').textContent, r.querySelector('.lc-ch').className]:null}""", mv)
    # Bench at DT (its last gym): 8 weeks before today reaches back to -42.
    check("log: last time's best, gold when it is the best ever, and the change",
          row("Bench Press") == ["★ 200×9", "lc-best is-won", "▲ 20 lb", "lc-ch is-up"], str(row("Bench Press")))
    check("log: mixed reps at the best's reps: level", row("Overhead Press")[2:] == ["= level", "lc-ch is-same"], str(row("Overhead Press")))
    check("log: body weight in reps", row("Dip")[2:] == ["▲ 3 reps", "lc-ch is-up"], str(row("Dip")))
    # Squat: last 275x5, eight weeks before it 275x5 (the 315 was 60 days before it)
    check("log: the change is over eight weeks, not all time", row("Squat")[2] == "= level", str(row("Squat")))
    check("log: once is no change", row("Fly")[2] == "", str(row("Fly")))
    lr = reach("#liftsCard .lc-row")
    check("log: rows are 44px and take the tap", len(lr) == 6 and all(x["h"] >= 44 and x["ok"] for x in lr), str(lr))
    p.click("#liftsMore"); p.wait_for_timeout(250)
    check("log: Show all shows every one", p.locator("#liftsCard .lc-row").count() == 7)
    check("log: and becomes Show fewer", p.evaluate("()=>document.getElementById('liftsMore').textContent") == "Show fewer")
    p.click("#liftsMore"); p.wait_for_timeout(250)
    check("log: Show fewer goes back to six", p.locator("#liftsCard .lc-row").count() == 6)

    p.click('#liftsCard [data-hist="Squat"]'); p.wait_for_timeout(300)
    check("log: a row opens its history", sheet_open() and p.evaluate("()=>document.querySelector('#histBody h2').textContent") == "Squat")
    sr = rows()
    check("twelve at most: the last twelve of fourteen", len(sr) == 12 and "the last 12 of 14 times" in body(), str(len(sr)))
    check("a best off the line is said under it", ("Your best, 315×5, was on %s." % short(k(-72))) in body(), body()[-80:])
    check("and no row is gold when it is not shown", not any(r[3] for r in sr))
    check("the same weight all along reads level", change()[0].startswith("Level over"), str(change()))
    p.click("#histDone"); p.wait_for_timeout(200)
    p.click('#liftsCard [data-hist="Dip"]'); p.wait_for_timeout(300)
    check("body weight: counted in reps", change() == ["▲ Up 3 reps in 4 weeks", "hist-ch is-up"], str(change()))
    p.click("#histDone"); p.wait_for_timeout(200)
    p.click('#liftsCard [data-hist="DB Curl"]'); p.wait_for_timeout(300)
    check("every gym's movement: no switch, both gyms, says every gym",
          not scopes() and len(rows()) == 2 and "at every gym" in body(), str(scopes()))
    p.click("#histDone"); p.wait_for_timeout(200)
    check("the Log's way in saves nothing either", saved() == before)

    # ================= a drop =================
    dropped = store()
    dropped["days"][T]["lifts"].append(lift("Overhead Press", [(85, 8)]))
    open_with(dropped, "log")
    p.click('#liftsCard [data-hist="Overhead Press"]'); p.wait_for_timeout(300)
    check("down reads down, in red, like Compare", change() == ["▼ Down 20 lb in 4 weeks", "hist-ch is-down"], str(change()))
    p.click("#histDone"); p.wait_for_timeout(200)

    # ================= no gyms =================
    plain = store(gyms=[], gymShared={})
    for v in plain["days"].values(): v.pop("gym", None)
    open_with(plain, "gym")
    p.locator(cardbtn("Bench Press")).click(); p.wait_for_timeout(300)
    check("no gyms: no switch, no gym named, every day counts",
          not scopes() and "at every gym" not in body() and "at DT" not in body() and len(rows()) == 8, body()[:160])
    p.click("#histDone"); p.wait_for_timeout(200)

    # ================= Done brings the next movement up (b108) =================
    open_with(store(), "gym")
    p.locator('.lift [data-done]').first.evaluate("e=>e.scrollIntoView({block:'center'})"); p.wait_for_timeout(200)
    p.locator('.lift [data-done]').first.click(); p.wait_for_timeout(900)
    g = p.evaluate("""()=>{const top=Math.max((document.querySelector('.topbar')||{getBoundingClientRect:()=>({bottom:0})}).getBoundingClientRect().bottom,
        document.documentElement.hasAttribute('data-stage')?54:0);
      const nx=[...document.querySelectorAll('.lift[data-li]')].find(c=>!c.classList.contains('is-closed'));
      return {edge: top, at: Math.round(nx.getBoundingClientRect().top), name: nx.querySelector('h3').textContent,
              folded: !!document.querySelector('.lift.is-closed')};}""")
    check("Done: the card folds and the next one open slides up under the bar",
          g["folded"] and g["name"].startswith("Fly") and abs(g["at"] - (g["edge"] + 8)) <= 3, str(g))

    # ================= a small phone =================
    p.set_viewport_size({"width": 320, "height": 640})
    open_with(store(), "gym")
    p.locator(cardbtn("Bench Press")).click(); p.wait_for_timeout(300)
    wide = p.evaluate("()=>{const i=document.querySelector('#histSheet .sheet-inner');return document.documentElement.scrollWidth<=window.innerWidth && i.scrollWidth<=i.clientWidth}")
    check("320px: the sheet does not scroll sideways", wide)
    seg = reach("[data-histscope]")
    check("320px: the switch still takes the tap", len(seg) == 3 and all(x["h"] >= 44 and x["ok"] for x in seg), str(seg))
    p.click("#histDone"); p.wait_for_timeout(200)
    open_with(store(), "log")
    wide = p.evaluate("()=>{const c=document.getElementById('liftsCard');return document.documentElement.scrollWidth<=window.innerWidth && c.scrollWidth<=c.clientWidth}")
    check("320px: Your lifts fits", wide)

    check("no page errors", not errs, "; ".join(errs[:3]))
    b.close()

fails = [r for r in res if r[0] == "FAIL"]
for r in res:
    print(("  " if r[0] == "PASS" else "✕ ") + r[1] + ("" if r[0] == "PASS" else "  [" + r[2] + "]"))
print("%d passed, %d FAILED" % (len(res) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
