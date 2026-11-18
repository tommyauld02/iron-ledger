"""Your week (b104): the day weeks start on, and the week wrap-up.

The owner's weeks run Monday to Sunday and the app's ran Sunday to Saturday,
so Settings -> Your week picks the first day, any of the seven, and every week
in the app follows it: the week strip, the Gym's board and goal, the cardio
goal, the daily line, the Log's calendar. Sunday stays the default, so a log
from before it reads exactly as it did.

The wrap-up is last week's numbers: calories and protein in all and a day,
carbs and fat and water for whoever tracks them, the gym, steps, cardio, body
weight, the checklist and check-ins. It pops up once, the first time the app
is open in a new week, never over another sheet or a running clock, and waits
on the Log tab until the next week's takes its place.

Pinned to a Wednesday so "last week" is the same seven days whatever day the
suite actually runs on. The clock can be moved on: window.__off for midnight
passing with the app open, setOff() for a page opened on another day.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
import os, sys, datetime
d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d

REAL = datetime.date.today()
SHIFT = (2 - REAL.weekday()) % 7                    # days forward to a Wednesday
T = REAL + datetime.timedelta(days=SHIFT)
def k(n): return (T + datetime.timedelta(days=n)).isoformat()
WED = k(0)
SUN_THIS, MON_THIS = k(-3), k(-2)                   # this week's start, Sunday- and Monday-first
MON_LAST = k(-9)                                    # last week, Monday to Sunday: k(-9) .. k(-3)
BUILD = None

CLOCK = """
 const REAL = Date; window.__off = Number(sessionStorage.getItem("__off")) || %d;
 class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+window.__off); else super(...a);} static now(){return REAL.now()+window.__off;} }
 window.Date = FD;
""" % (SHIFT * 86400000)

G = {"cal": {"dir": "-", "v": 2400}, "pro": {"dir": "+", "v": 160}}
MOVES = {"back": ["Barbell Row"], "push": ["Bench Press"], "legs": ["Back Squat"]}

def food(cal, pro, carb=None, fat=None, i=0):
    f = {"id": "f%d" % i, "note": "Food", "cal": cal, "pro": pro}
    if carb is not None: f["carb"] = carb; f["fat"] = fat
    return f

def last_week(extra=None):
    """Mon k(-9) to Sun k(-3), Monday-first: seven days of food, four gym days,
    water, steps, two cardio sessions and two weigh-ins."""
    days = {}
    for n, i in enumerate(range(-9, -2)):
        days[k(i)] = {"food": [food(2200, 170, 240, 70, n)], "lifts": [], "updated": 1, "goal": G,
                      "water": 1900, "steps": 8000}
    for i, c in [(-9, "back"), (-8, "push"), (-6, "legs"), (-4, "back")]:
        days[k(i)]["lifts"] = [{"id": "l%d" % -i, "cat": c, "movement": MOVES[c][0],
                                "sets": [{"w": 100, "r": 10}, {"w": 100, "r": 10}]}]
        days[k(i)]["workoutMs"] = 3600000
    days[k(-7)]["cardio"] = [{"id": "c1", "type": "Run", "min": 30, "dist": 3, "cal": 300, "t": 1}]
    days[k(-5)]["cardio"] = [{"id": "c2", "type": "Bike", "min": 20, "t": 1}]
    days[k(-9)]["bw"] = 182.0
    days[k(-3)]["bw"] = 180.5
    if extra: extra(days)
    return days

def span(start):
    a = datetime.date.fromisoformat(start); z = a + datetime.timedelta(days=6)
    return a.strftime("%b") + " " + str(a.day) + " \u2013 " + ("" if a.month == z.month else z.strftime("%b") + " ") + str(z.day)

def done(p):
    """Got it, when the wrap-up is up: a missing pop-up is a failed check, not a 30 s timeout."""
    if p.locator("#wrapSheet").is_visible():
        p.click("#wrapDone"); p.wait_for_timeout(200)

def store(days=None, **kw):
    s = {"days": days if days is not None else last_week(), "goal": G, "region": "United States", "pantry": [],
         "v": 1, "moves": MOVES, "movesOwned": True}
    if BUILD: s["build"] = BUILD
    s.update(kw)
    return s

res = []
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))
def saved(p): return p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
def wrap_up(p): return p.locator("#wrapSheet").is_visible()
def tiles(p, sec):
    return p.evaluate("""s=>[...document.querySelectorAll('[data-wrap="'+s+'"] .wr-tiles > div')].map(e=>
        [e.querySelector('b').textContent, e.querySelector('span').textContent])""", sec)
def lines(p, sec):
    return p.evaluate("""s=>[...document.querySelectorAll('[data-wrap="'+s+'"] .wr-line')].map(e=>
        ({t:e.textContent, won:e.classList.contains('is-won')}))""", sec)
def secs(p): return p.eval_on_selector_all("#wrapBody [data-wrap]", "e=>e.map(x=>x.dataset.wrap)")
def strip_first(p): return p.evaluate("()=>{const b=document.querySelector('#weekStrip .week-day'); return b&&b.dataset.day}")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 375, "height": 812}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(CLOCK)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://" + d + "/mntl-dt.html"); p.wait_for_timeout(300)
    BUILD = p.evaluate("()=>document.documentElement.innerHTML.match(/BUILD = \"([^\"]+)\"/)[1]")

    def open_with(s, wait=900):
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", s)
        setOff(SHIFT * 86400000)
        p.reload(); p.wait_for_timeout(wait)

    def setOff(ms):
        p.evaluate("o=>sessionStorage.setItem('__off', String(o))", ms)

    def tab(name):
        p.click('.tabs button[data-tab="%s"]' % name); p.wait_for_timeout(350)

    # ================= the day weeks start on =================
    open_with(store())
    check("pinned to a Wednesday", p.evaluate("()=>new Date().getDay()") == 3, WED)
    check("a log from before it starts weeks on Sunday", strip_first(p) == SUN_THIS, str(strip_first(p)))
    check("nothing pops up on the first open of this build", not wrap_up(p))
    check("which counts this week as begun", saved(p).get("wrapSeen") == SUN_THIS, str(saved(p).get("wrapSeen")))
    p.click("#setBtn"); p.wait_for_timeout(300)
    sel = p.locator("#setWeekStart")
    opts = p.eval_on_selector_all("#setWeekStart option", "e=>e.map(o=>o.textContent)")
    check("Settings offers all seven days", opts == ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], str(opts))
    check("Sunday is chosen", sel.input_value() == "0")
    fs = p.evaluate("()=>parseFloat(getComputedStyle(document.getElementById('setWeekStart')).fontSize)")
    check("the picker is 16px or more (iOS zoom)", fs >= 16, str(fs))
    hb = p.evaluate("()=>document.getElementById('setWeekStart').getBoundingClientRect().height")
    check("the picker is 44px or more", hb >= 44, str(hb))
    check("the hint says how weeks run", "Weeks run Sunday to Saturday" in p.text_content("#setWrapHint"))

    sel.select_option("1"); p.wait_for_timeout(400)
    s = saved(p)
    check("Monday is saved", s.get("weekStart") == 1, str(s.get("weekStart")))
    check("and said", "Weeks now run Monday to Sunday" in (p.text_content("#undobar") or ""), p.text_content("#undobar") or "")
    check("changing it is not a new week starting", s.get("wrapSeen") == MON_THIS and not wrap_up(p), str(s.get("wrapSeen")))
    check("the hint follows", "Weeks run Monday to Sunday" in p.text_content("#setWrapHint"))
    p.click("#setDone"); p.wait_for_timeout(250)
    check("the week strip starts on Monday", strip_first(p) == MON_THIS, str(strip_first(p)))
    days_shown = p.eval_on_selector_all("#weekStrip .week-day .wd", "e=>e.map(x=>x.textContent).join('')")
    check("Monday to Sunday across the top", days_shown == "MTWTFSS", days_shown)

    tab("gym")
    gtiles = p.eval_on_selector_all(".wb-tile[data-planday]", "e=>e.map(b=>b.querySelector('.wb-d').textContent.slice(0,3))")
    check("the Gym's planned week starts on Monday", gtiles[0] == "MON" and gtiles[-1] == "SUN", str(gtiles))
    first_tile = p.evaluate("()=>document.querySelector('.wb-tile[data-planday]').dataset.planday")
    check("its first tile is this Monday", first_tile == MON_THIS, first_tile)
    lab = p.get_attribute(".wb-tile[data-planday]", "aria-label") or ""
    check("and says so to a screen reader", lab.startswith("Monday "), lab)
    p.click('[data-planday="%s"]' % k(2)); p.wait_for_timeout(200)
    check("a tile still plans its own weekday", "Every Friday" in (p.text_content(".wb-pick") or ""))
    p.click('[data-setplan="legs"]'); p.wait_for_timeout(250)
    check("and the plan is kept by weekday", (saved(p).get("week") or [None] * 7)[5] == "legs", str(saved(p).get("week")))

    tab("log")
    dow = p.eval_on_selector_all(".month.is-big .dow-row span", "e=>e.map(x=>x.textContent).join('')")
    check("the Log's calendar starts on Monday", dow == "MTWTFSS", dow)
    # the first of the month sits under its own weekday
    ok_pad = p.evaluate("""()=>{const m=document.querySelector('.month.is-big .month-grid');
        const blanks=m.querySelectorAll('.cal-cell.blank').length; const first=m.querySelector('[data-go]').dataset.go.split('-').map(Number);
        const dw=new Date(first[0],first[1]-1,first[2]).getDay(); return blanks===(dw+6)%7}""")
    check("the 1st falls under its weekday", ok_pad)

    # every one of the seven, through the app's own weekStart: a fresh open each
    for ws in range(7):
        s = store(weekStart=ws, wrapSeen=None)
        s.pop("wrapSeen")
        open_with(s, 700)
        first = strip_first(p)
        dt = datetime.date.fromisoformat(first)
        check("weeks starting %s begin on that day" % ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][ws],
              (dt.weekday() + 1) % 7 == ws and 0 <= (T - dt).days <= 6, first)

    # the cardio goal and the gym goal count the week the setting says
    def cardio_extra(days):
        days[SUN_THIS] = {"food": [], "lifts": [], "updated": 1, "cardio": [{"id": "cs", "type": "Run", "min": 40, "t": 1}]}
        days[MON_THIS] = {"food": [], "lifts": [], "updated": 1, "cardio": [{"id": "cm", "type": "Run", "min": 15, "t": 1}]}
    open_with(store(last_week(cardio_extra), weekStart=0, cardioGoal={"kind": "min", "period": "week", "v": 150}))
    tab("cardio")
    sun_have = p.text_content(".cardio-goal") or ""
    open_with(store(last_week(cardio_extra), weekStart=1, cardioGoal={"kind": "min", "period": "week", "v": 150}))
    tab("cardio")
    mon_have = p.text_content(".cardio-goal") or ""
    check("Sunday-first counts Sunday's cardio in this week", "55" in sun_have, sun_have[:120])
    check("Monday-first leaves it in last week", "15" in mon_have and "55" not in mon_have, mon_have[:120])

    # ================= the wrap-up pops up once =================
    p.set_viewport_size({"width": 402, "height": 874})
    open_with(store(weekStart=1, wrapSeen=MON_LAST, cfOn=True, waterOn=True,
                    week=[None, "back", "push", None, "legs", "back", None]))
    check("a new week pops up last week's wrap-up", wrap_up(p))
    check("it names the week", p.text_content("#wrapTitle") == span(MON_LAST), p.text_content("#wrapTitle"))
    check("and how weeks run", "Last week, Monday to Sunday." == p.text_content("#wrapSub"), p.text_content("#wrapSub"))
    check("this week is marked as said", saved(p).get("wrapSeen") == MON_THIS, str(saved(p).get("wrapSeen")))
    check("every section tracked is there", secs(p) == ["food", "water", "gym", "steps", "cardio", "bw"], str(secs(p)))
    ft = tiles(p, "food")
    check("calories and protein, in all and a day", ft[:4] == [["15,400", "Calories, total"], ["1,190 g", "Protein, total"],
          ["2,200", "Calories a day"], ["170 g", "Protein a day"]], str(ft))
    check("carbs and fat with Carbs & fat shown", ft[4:] == [["1,680 g", "Carbs, total"], ["490 g", "Fat, total"]], str(ft))
    fl = lines(p, "food")
    check("a whole week on target is gold", fl and fl[0]["won"] and "All 7 days logged" in fl[0]["t"] and "all 7 on target" in fl[0]["t"], str(fl))
    check("no average note when all seven were logged", len(fl) == 1, str(fl))
    wt = tiles(p, "water")
    check("water in the unit chosen", wt == [["450 oz", "Water, total"], ["64 oz", "Water a day"]], str(wt))
    check("water's goal, 7 of 7 is gold", lines(p, "water") == [{"t": "Goal hit 7 of 7 days.", "won": True}], str(lines(p, "water")))
    gt = tiles(p, "gym")
    check("training days, sets, pounds and time", gt == [["4", "Training days"], ["8", "Sets"], ["8,000", "lb moved"], ["4h", "In the gym"]], str(gt))
    gl = lines(p, "gym")
    check("against the planned week, met is gold", gl == [{"t": "4 of 4 planned gym days.", "won": True}], str(gl))
    st = tiles(p, "steps")
    check("steps in all and a day", st == [["56,000", "Steps, total"], ["8,000", "Steps a day"]], str(st))
    ct = tiles(p, "cardio")
    check("cardio sessions, minutes, miles and kcal", ct == [["2", "Sessions"], ["50", "Minutes"], ["3", "Miles"], ["300", "kcal burned"]], str(ct))
    cl = lines(p, "cardio")
    check("the cardio goal for the week, short is not gold", len(cl) == 1 and "Weekly goal: 50 of 150 min." == cl[0]["t"] and not cl[0]["won"], str(cl))
    bl = lines(p, "bw")
    check("body weight, first to last", bl and bl[0]["t"] == "182.0 → 180.5 lb, down 1.5 lb over 2 weigh-ins.", str(bl))
    check("nothing is red", p.locator("#wrapSheet .is-miss, #wrapSheet [class*=miss]").count() == 0)
    check("it says where it is kept", "Log tab" in (p.text_content("#wrapSheet .wr-foot") or ""))
    nowide = p.evaluate("()=>{const i=document.querySelector('#wrapSheet .sheet-inner');return i.scrollWidth<=i.clientWidth+1}")
    check("nothing runs off the side", nowide)
    done(p)
    check("Got it puts it away", not wrap_up(p))
    p.reload(); p.wait_for_timeout(900)
    check("once: not again on the next open", not wrap_up(p))

    # ================= kept on the Log tab =================
    tab("log")
    card = p.locator("#wrapOpen")
    check("the Log tab keeps it", card.count() == 1)
    say = p.text_content("#wrapOpen") or ""
    check("its card says the week and a few numbers", "Week wrap-up" in say and "4 gym days" in say and "2,200 kcal a day" in say, say)
    bb = card.bounding_box()
    check("the card is a full-size target", bb and bb["height"] >= 44 and bb["width"] >= 200, str(bb))
    top = p.evaluate("()=>{const a=document.getElementById('wrapOpen').getBoundingClientRect();const c=document.querySelector('.year-card').getBoundingClientRect();return a.bottom<=c.top}")
    check("above the year", top)
    card.click(); p.wait_for_timeout(300)
    check("tapping it opens the same wrap-up", wrap_up(p) and secs(p)[:2] == ["food", "water"])
    p.click("#wrapSheet", position={"x": 200, "y": 20}); p.wait_for_timeout(250)
    check("tapping outside closes it", not wrap_up(p))
    p.click("#prevYear"); p.wait_for_timeout(250)
    check("not on another year's page", p.locator("#wrapOpen").count() == 0)
    p.click("#nextYear"); p.wait_for_timeout(250)

    # ================= only what was tracked =================
    def lean(days):
        for kk in list(days):
            for f in ("water", "steps", "cardio", "bw", "workoutMs"):
                days[kk].pop(f, None)
            days[kk]["lifts"] = []
            days[kk]["food"] = [food(2000, 150, i=1)]
        days.pop(k(-3)); days.pop(k(-4))     # five days logged
    open_with(store(last_week(lean), weekStart=1, wrapSeen=MON_LAST, waterOn=True))
    check("food alone is the whole wrap-up", secs(p) == ["food"], str(secs(p)))
    check("no carbs and fat with Carbs & fat hidden", len(tiles(p, "food")) == 4, str(tiles(p, "food")))
    fl = lines(p, "food")
    check("five days logged, all short of protein: not gold", fl[0]["t"] == "5 of 7 days logged · 0 on target." and not fl[0]["won"], str(fl))
    check("the average is over the days logged", any("average of the 5 days you logged" in x["t"] for x in fl), str(fl))
    check("water switched on but never used is left out", "water" not in secs(p))

    # a gym goal with no plan, missed, by someone who trains with the app
    def gym_short(days):
        days[k(-30)] = {"food": [], "lifts": [{"id": "old", "cat": "back", "movement": "Barbell Row", "sets": [{"w": 100, "r": 5}]}], "updated": 1}
        for i in (-9, -8, -6): days[k(i)]["lifts"] = []; days[k(i)].pop("workoutMs", None)
    open_with(store(last_week(gym_short), weekStart=1, wrapSeen=MON_LAST, gymGoal=3))
    gl = lines(p, "gym")
    check("against the workouts-a-week goal, short is not gold", gl == [{"t": "1 of your 3 workouts a week.", "won": False}], str(gl))

    def no_gym(days):
        for kk in days: days[kk]["lifts"] = []; days[kk].pop("workoutMs", None)
    open_with(store(last_week(no_gym), weekStart=1, wrapSeen=MON_LAST, gymGoal=3))
    check("no gym section for someone who has never trained with the app", "gym" not in secs(p), str(secs(p)))

    # the daily checklist and a check-in
    def ticks(days):
        for n, i in enumerate(range(-9, -2)):
            days[k(i)]["supps"] = {"cr": True} if n else {}
        days[k(-5)]["prog"] = {"note": "Feeling lean", "photo": "p1"}
    open_with(store(last_week(ticks), weekStart=1, wrapSeen=MON_LAST, supps=[{"id": "cr", "name": "Creatine", "dose": "5 g"}]))
    ll = lines(p, "list")
    check("the checklist, 6 of 7 is gold", ll == [{"t": "Finished 6 of 7 days.", "won": True}], str(ll))
    check("check-ins are counted", lines(p, "prog") == [{"t": "1 check-in, with a photo.", "won": False}], str(lines(p, "prog")))

    # kg, and a daily steps goal
    open_with(store(weekStart=1, wrapSeen=MON_LAST, bwUnit="kg", cardioGoal={"kind": "steps", "period": "day", "v": 8000}))
    bl = lines(p, "bw")
    check("body weight in kg", bl and bl[0]["t"] == "82.6 → 81.9 kg, down 0.7 kg over 2 weigh-ins.", str(bl))
    sl = lines(p, "steps")
    check("a daily steps goal, every day is gold", sl == [{"t": "8,000-step goal hit 7 of 7 days.", "won": True}], str(sl))
    check("and no cardio goal line beside it", lines(p, "cardio") == [], str(lines(p, "cardio")))

    # ================= when it holds back =================
    def empty(days): days.clear()
    open_with(store(last_week(empty), weekStart=1, wrapSeen=MON_LAST))
    check("a week with nothing logged is passed over", not wrap_up(p) and saved(p).get("wrapSeen") == MON_THIS)
    tab("log")
    check("and has no card on the Log", p.locator("#wrapOpen").count() == 0)

    def clock(days): days[WED] = {"food": [], "lifts": [], "updated": 1, "workoutStart": 1}
    open_with(store(last_week(clock), weekStart=1, wrapSeen=MON_LAST))
    check("never over a running workout clock", not wrap_up(p))
    check("and it waits rather than being spent", saved(p).get("wrapSeen") == MON_LAST, str(saved(p).get("wrapSeen")))

    open_with(store(weekStart=1, wrapSeen=MON_LAST, build="2026-10-13.60"))
    check("What's new comes first", p.locator("#newsSheet").is_visible() and not wrap_up(p))
    p.click("#newsDone"); p.wait_for_timeout(300)
    check("then the wrap-up", wrap_up(p))
    done(p)

    open_with(store(weekStart=1, wrapSeen=MON_LAST, wrapPop=False))
    check("Log tab only: nothing pops up", not wrap_up(p))
    tab("log")
    check("but it is on the Log", p.locator("#wrapOpen").count() == 1)
    p.click("#setBtn"); p.wait_for_timeout(250)
    check("Settings shows Log tab only", p.get_attribute('[data-pick-wrap="off"]', "aria-pressed") == "true")
    p.click('[data-pick-wrap="on"]'); p.wait_for_timeout(250)
    s = saved(p)
    check("switched back on, it starts with the next week", s.get("wrapPop") is True and s.get("wrapSeen") == MON_THIS and not wrap_up(p), str(s.get("wrapSeen")))
    p.click("#setDone"); p.wait_for_timeout(200)

    # midnight into a new week, with the app open: Sunday night to Monday
    s = store(weekStart=1, wrapSeen=MON_THIS)    # this week's has been said already
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", s)
    setOff((SHIFT + 4) * 86400000)        # Sunday k(4), the last day of this week
    p.reload(); p.wait_for_timeout(900)
    check("Sunday is still this week: nothing to say", not wrap_up(p) and p.evaluate("()=>new Date().getDay()") == 0)
    sv = saved(p)
    sv["days"][k(1)] = {"food": [food(2100, 165, i=9)], "lifts": [], "updated": 1, "goal": G}
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", sv)
    p.reload(); p.wait_for_timeout(900)
    p.evaluate("()=>{window.__off+=86400000; window.dispatchEvent(new Event('focus'))}")
    p.wait_for_timeout(500)
    check("midnight into Monday pops up the week just gone", wrap_up(p))
    check("the week just gone", p.text_content("#wrapTitle") == span(MON_THIS), p.text_content("#wrapTitle"))
    done(p)

    # a week across the end of a month says both months: Wednesday, Dec 9
    # 2026, Monday-first, is the week after Mon Nov 30 to Sun Dec 6
    to = (datetime.date(2026, 12, 9) - REAL).days * 86400000
    s = store({"2026-11-30": {"food": [food(2000, 150)], "lifts": [], "updated": 1},
               "2026-12-03": {"food": [food(2000, 150)], "lifts": [], "updated": 1}},
              weekStart=1, wrapSeen="2026-11-30")
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", s)
    setOff(to)
    p.reload(); p.wait_for_timeout(900)
    check("a week across two months names both", p.text_content("#wrapTitle") == "Nov 30 \u2013 Dec 6", p.text_content("#wrapTitle"))
    done(p)

    # ================= a restore =================
    open_with(store(weekStart=0))
    p.click("#backupBtn"); p.wait_for_timeout(300)
    incoming = store(weekStart=1, wrapPop=False, wrapSeen="2020-01-06")
    import json
    p.fill("#backupText", json.dumps(incoming))
    p.click("#restoreBtn"); p.wait_for_timeout(500)
    if p.locator("#closeSheet").is_visible(): p.click("#closeSheet"); p.wait_for_timeout(200)
    s = saved(p)
    check("the week's start comes with a restore", s.get("weekStart") == 1, str(s.get("weekStart")))
    check("and the pop-up choice", s.get("wrapPop") is False)
    check("but not which week this phone has said", s.get("wrapSeen") == MON_THIS, str(s.get("wrapSeen")))

    # ================= a small phone =================
    p.set_viewport_size({"width": 320, "height": 640})
    open_with(store(weekStart=1, wrapSeen=MON_LAST, cfOn=True, waterOn=True))
    nowide = p.evaluate("()=>{const i=document.querySelector('#wrapSheet .sheet-inner');return i.scrollWidth<=i.clientWidth+1}")
    check("320px: the tiles fit", nowide)
    p.locator("#wrapDone").scroll_into_view_if_needed(); p.wait_for_timeout(150)
    gb = p.locator("#wrapDone").bounding_box()
    check("320px: Got it is reachable and full size", gb and gb["height"] >= 44 and gb["y"] + gb["height"] <= 640, str(gb))
    done(p)
    tab("log")
    wide = p.evaluate("()=>document.documentElement.scrollWidth<=window.innerWidth")
    check("320px: the Log does not scroll sideways", wide)

    check("no page errors", not errs, "; ".join(errs[:3]))
    b.close()

fails = [r for r in res if r[0] == "FAIL"]
for r in res:
    print(("  " if r[0] == "PASS" else "✕ ") + r[1] + ("" if r[0] == "PASS" else "  [" + r[2] + "]"))
print("%d passed, %d FAILED" % (len(res) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
