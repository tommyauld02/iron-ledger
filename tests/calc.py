"""Your calories from your own results (b107): the calculator, body fat, and the real burn.

Asked for by the owner (2026-11-20), after the burn estimates of b106:
  - the goal calculator reviewed: seven aims, protein by choice (0.7, 0.85 or
    1 g a pound, of the goal weight when losing toward one), carbs and fat
    from a style, and a warning past 1% of the weight a week;
  - body fat %, "filling it if known, or if it wants to be guessed", with how
    to find it: a tape measure (the US Navy method), drawings of what each
    level looks like, and the other ways. A reading is kept on its day with
    where it came from; with one, the resting burn comes from lean mass;
  - "take the data from a user's weekly summary": the real burn, from the three
    whole weeks ending with the last one summed up (average eaten + pounds lost
    a day x 3,500), on the Log, in the wrap-up and in the calculator; and when
    the weight isn't moving toward the goal, a line on Macros with a new target
    to try, a step at a time, that only a tap sets, with Undo.

Pinned to noon today. The expected real burn is worked out here in Python
with the same arithmetic, not read back from the app.
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
SUN = T0 - datetime.timedelta(days=(T0.weekday() + 1) % 7)         # this week's Sunday (the default start)
END = SUN - datetime.timedelta(days=1)                               # last week's Saturday
WIN = [(END - datetime.timedelta(days=20 - i)).isoformat() for i in range(21)]

CLOCK = """
 (() => {
   const REAL = Date;
   window.__off = new REAL(%d, %d, %d, 12).getTime() - REAL.now();
   class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+window.__off); else super(...a);} static now(){return REAL.now()+window.__off;} }
   window.Date = FD;
 })();
""" % (T0.year, T0.month - 1, T0.day)

LB_KG = 0.45359237
def r10(x): return int(math.floor(x / 10.0 + 0.5)) * 10
def r5(x): return int(math.floor(x / 5.0 + 0.5)) * 5
def fmt(n): return "{:,}".format(int(n))
G = {"cal": {"dir": "-", "v": 2270}, "pro": {"dir": "+", "v": 160}}
ME = {"name": "Tommy", "dob": "2000-03-14", "sex": "m", "ft": "5", "inch": "11", "act": "1.55", "aim": "-500", "setup": True}

def log(kcal=2240, start=197.6, per_day=0.0, skip=(), goal_at=None, upto=0):
    """Days from 50 days ago to yesterday: food adding to kcal, a weigh-in
    every other day along a straight line (with a wobble that cancels), the
    goal stamped on each. goal_at = {day: goal} changes it from that day."""
    days, g = {}, G
    for n in range(50, upto, -1):
        key = k(-n)
        if goal_at and key in goal_at: g = goal_at[key]
        if key in skip: continue
        days[key] = {"food": [{"id": "f" + key, "note": "Food", "cal": kcal, "pro": 160}], "lifts": [], "updated": 1, "goal": g}
        if n % 2 == 0:
            days[key]["bw"] = round(start + per_day * (50 - n) + (0.3 if n % 4 == 0 else -0.3), 1)
    return days

def real_py(days):
    """The app's realBurn(), here: three weeks ending last Saturday."""
    n = cal = 0; pts = []
    for x, key in enumerate(WIN):
        dd = days.get(key)
        if dd and dd.get("food"): n += 1; cal += sum(f["cal"] for f in dd["food"])
        if dd and isinstance(dd.get("bw"), (int, float)): pts.append((x, dd["bw"]))
    if n < 18 or len(pts) < 6: return None
    mx = sum(p[0] for p in pts) / len(pts); my = sum(p[1] for p in pts) / len(pts)
    slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / sum((p[0] - mx) ** 2 for p in pts)
    avg = cal / float(n)
    return {"burn": r10(avg - slope * 3500), "avg": int(math.floor(avg + 0.5)), "change": slope * 20, "rate": slope * 7}

def store(days, **kw):
    s = {"v": 1, "build": BUILD, "adult": True, "terms": TERMS, "termsAt": 1, "region": "United States", "pantry": [],
         "goal": G, "days": days, "wrapSeen": SUN.isoformat(), "profile": dict(ME), "lineGot": {}}
    s.update(kw)
    return s

res = []
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(CLOCK)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://" + d + "/mntl-dt.html"); p.wait_for_timeout(300)

    def open_with(s, tab=None):
        p.evaluate("s=>{localStorage.clear(); localStorage.setItem('iron-ledger-v1',JSON.stringify(s))}", s)
        p.goto("file://" + d + "/mntl-dt.html")
        p.wait_for_function("()=>{const v=document.getElementById('view');return !!v&&v.children.length>0}", timeout=15000)
        p.wait_for_timeout(200)
        for sel in ["#wrapDone", "#newsDone"]:
            if p.locator(sel).count() and p.locator(sel).first.is_visible():
                p.click(sel); p.wait_for_timeout(150)
        if tab: p.click('[data-tab="%s"]' % tab); p.wait_for_timeout(300)
    def text(sel): return p.evaluate("s=>{const e=document.querySelector(s);return e?e.innerText:''}", sel)
    def saved(): return p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))") or {}
    def bar(): return p.evaluate("()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent")
    def line(): return p.evaluate("()=>{const e=document.querySelector('.dayline');return e?{head:e.querySelector('b').textContent,sub:e.querySelector('.dl-text span').textContent,use:(e.querySelector('[data-useline]')||{}).textContent||''}:null}")
    def burnline():
        """The real-burn line only: a good week has a line of its own."""
        x = line()
        return x if x and "3 weeks" in x["head"] else None
    def profile_edit():
        p.click("#setBtn"); p.wait_for_timeout(300); p.click("#setProfile"); p.wait_for_timeout(300)
    def sizes(sel):
        return p.evaluate("""s=>[...document.querySelectorAll(s)].map(e=>{e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),
          hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2), cs=getComputedStyle(e);
          return {id:e.id||e.textContent.trim().slice(0,14),h:Math.round(r.height),w:Math.round(r.width),ok:!!hit&&(hit===e||e.contains(hit)),
                  fs:parseFloat(cs.fontSize),tag:e.tagName}})""", sel)

    # ================= the calculator =================
    fresh = {T: {"food": [], "lifts": [], "updated": 1, "goal": G, "bw": 197.0}}
    open_with(store(fresh, bwGoal=185, cfOn=True))
    profile_edit()
    aims = p.eval_on_selector_all("#pfAim option", "e=>e.map(x=>x.textContent)")
    check("aims: seven, from losing 2 lb a week to gaining 1",
          aims == ["Lose 2 lb a week", "Lose 1½ lb a week", "Lose 1 lb a week", "Lose ½ lb a week", "Stay the same", "Gain ½ lb a week", "Gain 1 lb a week"], str(aims))
    pros = p.evaluate("()=>[...document.querySelectorAll('[data-pfpro]')].map(b=>b.textContent+(b.getAttribute('aria-pressed')==='true'?'*':''))")
    check("protein: three choices, 0.85 g/lb unless chosen", pros == ["0.7 g/lb", "0.85 g/lb*", "1 g/lb"], str(pros))
    check("protein: losing toward a goal, per pound of the goal", text("#pfProSay").startswith("For each pound of your goal weight, 185 lb"), text("#pfProSay"))
    bmr = 10 * 197 * LB_KG + 6.25 * 71 * 2.54 - 5 * 26 + 5
    cal = r10(bmr * 1.55 - 500); pro = r5(185 * 0.85); fat = r5(cal * 0.30 / 9); carb = r5((cal - pro * 4 - fat * 9) / 4.0)
    out = text("#pfCalc")
    check("calculator: the working, with protein of the goal and carbs and fat",
          ("To lose 1 lb a week: %s kcal, and %d g protein, 0.85 g for every pound of your 185 lb goal. Carbs and fat: %d g and %d g." % (fmt(cal), pro, carb, fat)) in out, out)
    p.click('[data-pfpro="1"]'); p.wait_for_timeout(150)
    check("protein: 1 g/lb changes the working", ("%d g protein, a gram for every pound of your 185 lb goal" % r5(185)) in text("#pfCalc"), text("#pfCalc"))
    p.click("#pfUse"); p.wait_for_timeout(200)
    check("use these numbers: calories, protein, carbs and fat",
          [p.input_value(x) for x in ["#pfCal", "#pfPro", "#pfCarb", "#pfFat"]] == [str(cal), str(r5(185)), str(r5((cal - r5(185) * 4 - fat * 9) / 4.0)), str(fat)],
          str([p.input_value(x) for x in ["#pfCal", "#pfPro", "#pfCarb", "#pfFat"]]))
    p.select_option("#pfStyle", "low"); p.wait_for_timeout(150)
    check("carbs and fat: a lower-carb style is 40% fat", ("Carbs and fat:" in text("#pfCalc")) and (" g and %d g." % r5(cal * 0.40 / 9)) in text("#pfCalc"), text("#pfCalc"))
    p.select_option("#pfAim", "-750"); p.wait_for_timeout(150)
    check("1½ lb a week at 197 lb: no warning (under 1% of the weight)", "faster than 1%" not in text("#pfCalc"), text("#pfCalc"))
    p.select_option("#pfAim", "-1000"); p.wait_for_timeout(150)
    check("2 lb a week at 197 lb: just past 1.97 lb, so said", "faster than 1% of your weight a week" in text("#pfCalc"), text("#pfCalc"))
    p.click("#pfCancel"); p.wait_for_timeout(200)

    # the target editor's calculator has the same choices
    open_with(store(fresh, bwGoal=185, cfOn=True), "macros")
    p.click("#openGoal"); p.wait_for_timeout(200); p.click("#gcOpen"); p.wait_for_timeout(200)
    check("target editor: protein and carbs-and-fat choices", p.locator("#gcPro option").count() == 3 and p.locator("#gcStyle option").count() == 3)
    p.click('[data-gcsex="m"]'); p.fill("#gcAge", "26"); p.wait_for_timeout(100)
    p.click("#gcUse"); p.wait_for_timeout(200)
    check("target editor: Use fills carbs and fat too", p.input_value("#gCarb") != "" and p.input_value("#gFat") == str(fat), p.input_value("#gCarb") + "/" + p.input_value("#gFat"))

    # ================= body fat =================
    open_with(store(fresh, bwGoal=185))
    profile_edit()
    check("body fat: an optional box under the height", p.locator("#pfBf").count() == 1 and p.input_value("#pfBf") == "" and "If you know it." in text("#pfBfSay"))
    sz = sizes("#pfBf, #pfBfHow")
    check("body fat: the box is 16px (no iOS zoom) and Don't know it? is 44px and takes the tap",
          sz[0]["fs"] >= 16 and sz[1]["h"] >= 44 and sz[1]["ok"], str(sz))
    p.click("#pfBfHow"); p.wait_for_timeout(250)
    tabs = p.eval_on_selector_all("[data-bftab]", "e=>e.map(x=>x.textContent+(x.getAttribute('aria-pressed')==='true'?'*':''))")
    check("don't know it: three ways, the tape first", tabs == ["Tape measure*", "By look", "Other ways"], str(tabs))
    check("tape: says what it needs, and Use waits", "Type your waist and neck" in text("#pfTapeOut") and p.is_disabled("#pfTapeUse"))
    p.fill("#pfTapeW", "36"); p.fill("#pfTapeN", "16.5"); p.wait_for_timeout(150)
    navy = 86.010 * math.log10(36 - 16.5) - 70.041 * math.log10(71) + 36.76      # the Navy method in inches
    want = int(math.floor(navy + 0.5))
    check("tape: the US Navy method, from waist, neck and height", text("#pfTapeOut").startswith("About %d%% body fat." % want) and text("#pfTapeUse").lower() == "use %d%%" % want,
          text("#pfTapeOut") + " | " + text("#pfTapeUse"))
    sz = sizes("#pfTapeW, #pfTapeN, [data-bftab], #pfTapeUse, #pfBfClose")
    check("tape: fields 16px, buttons 44px, all take the tap", all(x["ok"] for x in sz) and all(x["fs"] >= 16 for x in sz if x["tag"] == "INPUT")
          and all(x["h"] >= 44 for x in sz if x["tag"] == "BUTTON"), str(sz))
    p.click('[data-bftab="look"]'); p.wait_for_timeout(250)
    cards = p.eval_on_selector_all(".bf-card b", "e=>e.map(x=>x.textContent)")
    check("by look: six drawings for men, about 10% to 35%+", cards == ["About 10%", "About 15%", "About 20%", "About 25%", "About 30%", "About 35%+"], str(cards))
    check("by look: each is drawn, with words", p.locator(".bf-card svg .bf-body").count() == 6 and p.locator(".bf-card > span:last-child").count() == 6)
    sz = sizes(".bf-card, #pfLookUse")
    check("by look: every card 44px and takes the tap", all(x["h"] >= 44 and x["ok"] for x in sz), str(sz))
    p.click('[data-bflook="20"]'); p.wait_for_timeout(200)
    check("by look: a pick is pressed, and Use says it", p.get_attribute('[data-bflook="20"]', "aria-pressed") == "true" and text("#pfLookUse").lower() == "use about 20%")
    p.click('[data-bftab="other"]'); p.wait_for_timeout(200)
    ways = p.eval_on_selector_all(".bf-ways b", "e=>e.map(x=>x.textContent)")
    check("other ways: scan, gym machine, scale, calipers, tape", ways == ["A DEXA scan", "A gym body-scan machine", "A smart scale", "Skinfold calipers", "A tape measure"], str(ways))
    p.click('[data-bftab="tape"]'); p.wait_for_timeout(200)
    check("tape: what was typed is still there after the other tabs", p.input_value("#pfTapeW") == "36")
    p.click("#pfTapeUse"); p.wait_for_timeout(250)
    check("use: the sheet goes and the box has it, saying where it came from",
          p.locator("#pfBfSheet").count() == 0 and p.input_value("#pfBf") == str(want) and text("#pfBfSay").startswith("From your tape measure. Save to keep it."), text("#pfBfSay"))
    lean = 197 * LB_KG * (1 - want / 100.0)
    check("with body fat, the resting burn is from lean mass",
          ("%s at rest, from your lean mass at %d%% body fat" % (fmt(r10(370 + 21.6 * lean)), want)) in text("#pfCalc"), text("#pfCalc"))
    p.click("#pfSave"); p.wait_for_timeout(300)
    td = saved()["days"][T]
    check("save: today's reading, with where it came from", td.get("bf") == want and td.get("bfBy") == "tape", str({x: td.get(x) for x in ("bf", "bfBy")}))
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("settings: you, with body fat", text("#setWho").endswith("197.0 lb · %d%% body fat" % want), text("#setWho"))
    p.click("#setProfile"); p.wait_for_timeout(300)
    check("reopened: the box says where and when", text("#pfBfSay").startswith("From your tape measure, today."), text("#pfBfSay"))
    p.fill("#pfBf", "70"); p.click("#pfSave"); p.wait_for_timeout(250)
    check("a number that can't be right is said, not saved", "Body fat is a percentage from 3 to 60" in text("#pfErr") and saved()["days"][T].get("bf") == want, text("#pfErr"))
    p.fill("#pfBf", ""); p.wait_for_timeout(100)
    check("emptied: it says the app goes back to height and weight", text("#pfBfSay").startswith("Left empty"), text("#pfBfSay"))
    p.click("#pfSave"); p.wait_for_timeout(300)
    check("emptied and saved: no longer used, and the reading stays in the log",
          (saved().get("profile") or {}).get("bfOff") is True and saved()["days"][T].get("bf") == want)
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undo: back in use", not (saved().get("profile") or {}).get("bfOff"))

    # women: hips, and their own drawings; kg: cm
    her = store(fresh); her["profile"] = dict(ME, sex="f"); her["bwUnit"] = "kg"; her["profile"]["cm"] = 165
    del her["profile"]["ft"]; del her["profile"]["inch"]
    open_with(her); profile_edit(); p.click("#pfBfHow"); p.wait_for_timeout(250)
    check("women: hips too, in cm with kg", p.locator("#pfTapeH").count() == 1 and "waist · cm" in text("#pfBfSheet").lower(), text("#pfBfSheet")[:200])
    p.fill("#pfTapeW", "76"); p.fill("#pfTapeN", "33"); p.fill("#pfTapeH", "98"); p.wait_for_timeout(150)
    fem = 495 / (1.29579 - 0.35004 * math.log10(76 + 98 - 33) + 0.22100 * math.log10(165)) - 450
    check("women: the Navy method's own equation", text("#pfTapeOut").startswith("About %d%% body fat." % int(math.floor(fem + 0.5))), text("#pfTapeOut"))
    p.click('[data-bftab="look"]'); p.wait_for_timeout(200)
    cards = p.eval_on_selector_all(".bf-card b", "e=>e.map(x=>x.textContent)")
    check("women: their own drawings, about 15% to 40%+", cards[0] == "About 15%" and cards[-1] == "About 40%+" and len(cards) == 6, str(cards))
    noone = store(fresh); noone["profile"] = {"name": "Sam", "setup": True}
    open_with(noone); profile_edit(); p.click("#pfBfHow"); p.wait_for_timeout(250)
    check("no gender or height yet: the tape says so", "Fill in your gender and height" in text("#pfTapeOut"))

    # ================= the real burn, and the line =================
    days = log()
    want_r = real_py(days)
    open_with(store(days, bwGoal=185), "log")
    check("log: the real burn under the goal weight", text("#bwReal") == "Your real burn: about %s kcal a day, from 3 weeks of food and weigh-ins." % fmt(want_r["burn"]), text("#bwReal"))
    p.click('[data-tab="macros"]'); p.wait_for_timeout(300)
    ln = line()
    nxt = r10(max(1500, 2270 - 300, want_r["burn"] - 500))
    check("macros: weight steady, what was eaten, and a target to try",
          ln and ln["head"] == "Weight steady for 3 weeks." and ln["sub"] == "You averaged %s kcal a day. Try %s and see how the next 3 weeks go." % (fmt(want_r["avg"]), fmt(nxt))
          and ln["use"] == "Use %s" % fmt(nxt), str(ln))
    sz = sizes(".dayline button")
    check("macros: Use and Got it, 44px each, both take the tap", len(sz) == 2 and all(x["h"] >= 44 and x["ok"] for x in sz), str(sz))
    check("nothing changes without a tap", saved()["goal"]["cal"]["v"] == 2270)
    p.click("[data-useline]"); p.wait_for_timeout(300)
    s = saved()
    check("use: the target from today, said on the bar", s["goal"]["cal"] == {"dir": "-", "v": nxt} and s["days"][T]["goal"]["cal"]["v"] == nxt
          and bar() == "Calorie target %s from today" % fmt(nxt), bar() + " " + json.dumps(s["goal"]))
    check("use: yesterday keeps the target it was judged against", s["days"][k(-1)]["goal"]["cal"]["v"] == 2270)
    check("use: the line goes", burnline() is None, str(line()))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undo: the old target, and the line back", saved()["goal"]["cal"]["v"] == 2270 and burnline() is not None, str(line()))
    p.click(".dayline [data-gotline]"); p.wait_for_timeout(300)
    check("got it: the line goes, and nothing changed", burnline() is None and saved()["goal"]["cal"]["v"] == 2270, str(line()))
    open_with(store(days, bwGoal=185, lineGot={"macros/burn:x": k(-10)}), "macros")
    check("put away 10 days ago: still quiet (three weeks)", burnline() is None, str(line()))
    open_with(store(days, bwGoal=185, lineGot={"macros/burn:x": k(-25)}), "macros")
    check("put away 25 days ago: it can speak again", burnline() is not None, str(line()))

    # the calculator uses it
    p.click("#setBtn"); p.wait_for_timeout(300); p.click("#setProfile"); p.wait_for_timeout(300)
    check("calculator: from your log, in place of the formula",
          text("#pfCalc").startswith("From your log, you burn about %s kcal a day: 3 weeks of food and weigh-ins. The formula guessed" % fmt(want_r["burn"])), text("#pfCalc"))
    p.click("#pfCancel"); p.wait_for_timeout(200)
    p.click("#setDone"); p.wait_for_timeout(200)          # Cancel goes back to Settings, by design

    # the wrap-up says it
    p.click('[data-tab="log"]'); p.wait_for_timeout(300); p.click("#wrapOpen"); p.wait_for_timeout(300)
    bl = p.evaluate("()=>[...document.querySelectorAll('[data-wrap=\"bw\"] .wr-line')].map(e=>e.textContent)")
    check("wrap-up: the real burn, from this week and the two before", any(x.startswith("Your real burn: about %s kcal a day, from this week and the two before" % fmt(want_r["burn"])) for x in bl), str(bl))

    # eating over the target: said, and nothing to Use
    over = log(kcal=2480)
    open_with(store(over, bwGoal=185), "macros")
    ln = line()
    check("ate over the target: said, with no new target", ln and ln["sub"] == "You averaged 2,480 kcal a day, 210 over your 2,270 target. Sticking to 2,270 should get it moving."
          and ln["use"] == "", str(ln))

    # losing much faster than the aim: the other way
    fast = log(kcal=1700, start=205, per_day=-0.4)
    rf = real_py(fast)
    open_with(store(fast, bwGoal=185), "macros")
    ln = line()
    up = r10(min(2270 + 300, rf["burn"] - 500))
    check("losing much faster than the aim: eat a little more",
          ln and ln["head"].endswith("in 3 weeks, faster than your aim.") and ln["head"].startswith("Down ")
          and ln["sub"] == "You averaged 1,700 kcal a day. Try %s to keep more of your muscle." % fmt(up) and ln["use"] == "Use %s" % fmt(up), str(ln) + " want " + str(up))

    # quiet when the log can't say
    patchy = log(skip=set(WIN[::4]))
    open_with(store(patchy, bwGoal=185), "macros")
    check("a patchy log (under 18 of 21 days): quiet", burnline() is None, str(line()))
    p.click('[data-tab="log"]'); p.wait_for_timeout(300)
    check("a patchy log: no real burn on the Log either", p.locator("#bwReal").count() == 0)
    changed = log(goal_at={WIN[10]: {"cal": {"dir": "-", "v": 2100}, "pro": {"dir": "+", "v": 160}}})
    open_with(store(changed, bwGoal=185), "macros")
    check("a target changed inside the three weeks: quiet until it has had three weeks", burnline() is None, str(line()))
    hold = store(log(), bwGoal=185); hold["profile"]["aim"] = "0"; del hold["bwGoal"]
    open_with(hold, "macros")
    check("holding steady on purpose: nothing to say", burnline() is None, str(line()))

    # ================= a small phone =================
    p.set_viewport_size({"width": 320, "height": 640})
    open_with(store(fresh, bwGoal=185, cfOn=True)); profile_edit(); p.click("#pfBfHow"); p.wait_for_timeout(250)
    p.click('[data-bftab="look"]'); p.wait_for_timeout(200)
    wide = p.evaluate("()=>{const i=document.querySelector('#pfBfSheet .sheet-inner');return i.scrollWidth<=i.clientWidth+1}")
    check("320px: the drawings fit", wide)
    open_with(store(log(), bwGoal=185), "macros")
    wide = p.evaluate("()=>document.documentElement.scrollWidth<=window.innerWidth")
    sz = sizes(".dayline button")
    check("320px: the line with Use fits, and both buttons take the tap", wide and len(sz) == 2 and all(x["ok"] for x in sz), str(sz))

    check("no page errors", not errs, "; ".join(errs[:3]))
    b.close()

fails = [r for r in res if r[0] == "FAIL"]
for r in res:
    print(("  " if r[0] == "PASS" else "✕ ") + r[1] + ("" if r[0] == "PASS" else "  [" + str(r[2]) + "]"))
print("%d passed, %d FAILED" % (len(res) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
