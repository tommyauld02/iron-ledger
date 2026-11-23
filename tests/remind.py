"""Reminders and the rest timer on each set (b108).

From a list of improvements the owner was shown on 2026-11-21:

  - Reminders, iPhone app only, each off until turned on in Settings: no food
    logged by an evening time, and a weigh-in in the morning, every day or
    once a week on the day weeks start. Each is a notification booked ahead
    for fourteen days and booked again when the log changes or the app comes
    back; a day with food (or a weight) is left out. Turning one on asks iOS
    first, and a refusal leaves it off and says where to fix it.
  - The rest timer can start by itself on each set logged today.

The iPhone shell is stood in for the way tests/native.py and the screenshot
tool do it: the log in native storage, and a LocalNotifications that keeps
what is booked in window.__ln so the suite can read it.

Pinned to noon today (and to 6 am for the weigh-in that is still ahead).
"""
import answered   # every page has said 18 or older: tests/answered.py
import logways
from playwright.sync_api import sync_playwright
import os, sys, re, json, datetime
d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
URL = "file://" + d + "/mntl-dt.html"

SRC = open("mntl-dt.html", encoding="utf-8").read()
BUILD = re.search(r'var BUILD = "([^"]+)"', SRC).group(1)
TERMS = re.search(r'var TERMS = "([^"]+)"', SRC).group(1)
T0 = datetime.date.today()
def k(n): return (T0 + datetime.timedelta(days=n)).isoformat()
T = k(0)
def dayno(key): return (datetime.date.fromisoformat(key) - datetime.date(2020, 1, 1)).days

def clock(hour):
    return """
 (() => {
   const REAL = Date;
   window.__off = new REAL(%d, %d, %d, %d).getTime() - REAL.now();
   class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+window.__off); else super(...a);} static now(){return REAL.now()+window.__off;} }
   window.Date = FD;
 })();
""" % (T0.year, T0.month - 1, T0.day, hour)

SHELL = """(() => {
  const prefs = { 'CapacitorStorage.iron-ledger-v1': %s };
  window.__ln = { pending: [], perm: 'granted', asked: 0, calls: [] };
  window.Capacitor = {
    isNativePlatform: () => true, getPlatform: () => 'ios',
    isPluginAvailable: (n) => n === 'Preferences' || n === 'LocalNotifications',
    nativePromise: (plugin, method, o) => {
      o = o || {};
      if (plugin === 'Preferences') {
        if (method === 'set') prefs['CapacitorStorage.' + o.key] = o.value;
        if (method === 'remove') delete prefs['CapacitorStorage.' + o.key];
        return Promise.resolve(method === 'get' ? { value: prefs['CapacitorStorage.' + o.key] || null } : {});
      }
      if (plugin === 'LocalNotifications') {
        const ln = window.__ln; ln.calls.push(method);
        if (method === 'requestPermissions') { ln.asked++; return Promise.resolve({ display: ln.perm }); }
        if (method === 'getPending') return Promise.resolve({ notifications: ln.pending.map(n => ({ id: n.id })) });
        if (method === 'cancel') {
          const gone = (o.notifications || []).map(n => n.id);
          ln.pending = ln.pending.filter(n => gone.indexOf(n.id) === -1);
          return Promise.resolve({});
        }
        if (method === 'schedule') {
          (o.notifications || []).forEach(n => {
            ln.pending = ln.pending.filter(x => x.id !== n.id);
            const at = n.schedule && n.schedule.at;
            ln.pending.push({ id: n.id, title: n.title, body: n.body, sound: n.sound,
              isDate: at instanceof Date, at: at instanceof Date ? at.getTime() : null });
          });
          return Promise.resolve({});
        }
      }
      return Promise.resolve({});
    }
  };
  window.__prefs = prefs;
})();"""

G = {"cal": {"dir": "-", "v": 2270}, "pro": {"dir": "+", "v": 160}}
ME = {"name": "Tommy", "dob": "1992-03-14", "sex": "m", "ft": "5", "inch": "11", "act": "1.55", "aim": "-500", "setup": True}
MOVES = {"push": ["Bench Press"]}

def store(days=None, **kw):
    s = {"v": 1, "build": BUILD, "adult": True, "terms": TERMS, "termsAt": 1, "region": "United States", "pantry": [],
         "moves": MOVES, "movesOwned": True, "goal": G, "days": days or {}, "wrapSeen": T,
         "profile": dict(ME), "lineGot": {}, "seen": True,
         "consent": {"adult": True, "terms": TERMS, "termsAt": 1}}
    s.update(kw)
    return s

res = []
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errs = []

    def phone(s, hour=12, native=True):
        ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
        ctx.add_init_script("delete window.claude;")
        ctx.add_init_script(clock(hour))
        if native:
            ctx.add_init_script(SHELL % json.dumps(json.dumps(s)))
        p = ctx.new_page()
        p.on("pageerror", lambda e: errs.append(str(e)))
        if not native:
            p.goto(URL); p.evaluate("s=>{localStorage.clear(); localStorage.setItem('iron-ledger-v1',JSON.stringify(s))}", s)
        p.goto(URL)
        p.wait_for_function("()=>{const v=document.getElementById('view');return !!v&&v.children.length>0}", timeout=15000)
        p.wait_for_timeout(400)
        for sel in ["#wrapDone", "#newsDone", "#wnDone"]:
            if p.locator(sel).count() and p.locator(sel).first.is_visible():
                p.click(sel); p.wait_for_timeout(150)
        return ctx, p
    def settings(p):
        p.click("#setBtn"); p.wait_for_timeout(300)
        p.locator("#setRem").evaluate("e=>e.scrollIntoView({block:'center'})"); p.wait_for_timeout(150)
    def pending(p): return p.evaluate("()=>window.__ln.pending.slice().sort((a,b)=>a.id-b.id)")
    def said(p): return p.evaluate("()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent")
    def saved(p): return json.loads(p.evaluate("()=>window.__prefs['CapacitorStorage.iron-ledger-v1']"))
    def local(ms):
        dt = datetime.datetime.fromtimestamp(ms / 1000.0)
        return dt.date().isoformat(), dt.strftime("%H:%M")
    def settle(p, ms=1700): p.wait_for_timeout(ms)

    # ================= the web: no reminders =================
    ctx, p = phone(store(), native=False)
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("web: there are no reminders to set", p.evaluate("()=>document.getElementById('setRem').hidden"))
    check("web: the rest timer setting is there, and starts as it always has, by its button",
          p.evaluate("()=>[...document.querySelectorAll('#setRestAuto button')].map(b=>[b.textContent,b.getAttribute('aria-pressed')])")
          == [["When I press it", "true"], ["On each set", "false"]])
    ctx.close()

    # ================= the iPhone app =================
    ctx, p = phone(store(days={k(1): {"food": [{"id": "f1", "cal": 300, "pro": 20, "note": "Oats"}], "lifts": [], "updated": 1, "goal": G}}))
    settle(p, 400)
    check("app: nothing is booked until a reminder is turned on", pending(p) == [])
    check("app: and iOS is not asked", p.evaluate("()=>window.__ln.asked") == 0)
    settings(p)
    check("app: Settings has Reminders, both off",
          not p.evaluate("()=>document.getElementById('setRem').hidden")
          and p.evaluate("()=>[...document.querySelectorAll('#setRem [aria-pressed=true]')].map(b=>b.textContent)") == ["Off", "Off"])
    check("app: with them off, no times to pick",
          not p.locator("#setRemFoodAt").is_visible() and not p.locator("#setRemBwAt").is_visible())

    p.click('[data-rem-food="on"]'); settle(p)
    pd = pending(p)
    food = [x for x in pd if 7100000 <= x["id"] < 7200000]
    want = [k(n) for n in range(14) if n != 1]          # tomorrow already has food
    check("food on: iOS is asked first", p.evaluate("()=>window.__ln.asked") == 1)
    check("food on: it says so", said(p) == "Reminder on · 8:00 pm on a day with no food logged", said(p))
    check("food on: saved in the log", saved(p).get("remind", {}).get("food", {}).get("on") is True)
    check("food on: one a day for two weeks at 8 pm, from today, none on a day with food",
          [local(x["at"]) for x in food] == [(kk, "20:00") for kk in want], str([local(x["at"]) for x in food][:3]))
    check("food on: the id is the day's, so a day never has two", [x["id"] for x in food] == [7100000 + dayno(kk) for kk in want])
    check("food on: each is a real date, with a sound (iOS is silent without one)",
          all(x["isDate"] and x["sound"] == "default" and x["title"] == "No food logged yet today" for x in food))
    check("food on: its time is there to change", p.locator("#setRemFoodAt").is_visible())

    p.select_option("#setRemFoodAt", "21:30"); settle(p)
    food = [x for x in pending(p) if 7100000 <= x["id"] < 7200000]
    check("food time: every one moves, and it says so",
          len(food) == 13 and all(local(x["at"])[1] == "21:30" for x in food) and "9:30 pm" in said(p), said(p))

    # Logging food today takes today's off, a moment later.
    p.click("#setDone"); p.wait_for_timeout(200)
    logways.open_way(p, "numbers", 350)
    p.fill("#fCal", "500"); p.fill("#fPro", "40"); p.fill("#fNote", "Lunch")
    p.click("#addFood"); settle(p)
    food = [x for x in pending(p) if 7100000 <= x["id"] < 7200000]
    check("food logged today: today's reminder is taken off, the rest stay",
          [local(x["at"])[0] for x in food] == [kk for kk in want if kk != T], str([local(x["at"])[0] for x in food][:2]))

    # ================= weigh-in =================
    settings(p)
    p.evaluate("()=>{window.__ln.perm='denied'}")
    p.click('[data-rem-bw="on"]'); settle(p, 500)
    check("refused: it stays off and says where to turn notifications on",
          saved(p).get("remind", {}).get("bw", {}).get("on") is not True and "iPhone Settings" in said(p)
          and p.evaluate("()=>document.querySelector('[data-rem-bw=off]').getAttribute('aria-pressed')") == "true", said(p))
    check("refused: nothing is booked for it", not [x for x in pending(p) if x["id"] >= 7200000])
    p.evaluate("()=>{window.__ln.perm='granted'}")
    p.click('[data-rem-bw="on"]'); settle(p)
    bw = [x for x in pending(p) if x["id"] >= 7200000]
    check("weigh-in on: every morning at 7, from tomorrow (7 am today has gone)",
          [local(x["at"]) for x in bw] == [(k(n), "07:00") for n in range(1, 14)], str([local(x["at"]) for x in bw][:2]))
    check("weigh-in on: it says so", said(p) == "Weigh-in reminder on · 7:00 am every morning", said(p))
    check("weigh-in: how often offers the day weeks start on",
          p.evaluate("()=>[...document.querySelectorAll('#setRemBwEvery option')].map(o=>o.textContent)") == ["Every morning", "Once a week, Sundays"])
    p.select_option("#setRemBwEvery", "week"); settle(p)
    bw = [x for x in pending(p) if x["id"] >= 7200000]
    sundays = [k(n) for n in range(1, 14) if (T0 + datetime.timedelta(days=n)).weekday() == 6]
    check("weigh-in weekly: only on Sundays", [local(x["at"])[0] for x in bw] == sundays and "on Sundays" in said(p), str(bw))
    sizes = p.evaluate("""()=>[...document.querySelectorAll('#setRem button, #setRem select, #setRestAuto button')].filter(e=>e.offsetParent)
        .map(e=>{const r=e.getBoundingClientRect();return [e.textContent.trim().slice(0,12), Math.round(r.height), parseFloat(getComputedStyle(e).fontSize), e.tagName]})""")
    check("settings: every control is 44px", sizes and all(x[1] >= 44 for x in sizes), str([x for x in sizes if x[1] < 44]))
    check("settings: the time pickers are 16px, so iOS does not zoom", all(x[2] >= 16 for x in sizes if x[3] == "SELECT"), str(sizes))

    p.click('[data-rem-food="off"]'); settle(p)
    check("food off: every food reminder is taken off, and it says so",
          not [x for x in pending(p) if x["id"] < 7200000] and said(p) == "Food reminder off", said(p))
    check("food off: the weigh-ins stay", len([x for x in pending(p) if x["id"] >= 7200000]) == len(sundays))
    ctx.close()

    # ================= a weigh-in still ahead today =================
    s = store(remind={"bw": {"on": True, "at": "07:00", "every": "day"}})
    ctx, p = phone(s, hour=6)
    settle(p)
    bw = [x for x in pending(p) if x["id"] >= 7200000]
    check("opened: what the log says is booked again, without asking iOS",
          [local(x["at"]) for x in bw] == [(k(n), "07:00") for n in range(14)] and p.evaluate("()=>window.__ln.asked") == 0,
          str([local(x["at"]) for x in bw][:2]))
    p.click('[data-tab="log"]'); p.wait_for_timeout(300)
    p.fill("#bwIn", "182.4"); p.click("#bwSave"); settle(p)
    bw = [x for x in pending(p) if x["id"] >= 7200000]
    check("a weight logged: today's weigh-in is taken off", [local(x["at"])[0] for x in bw] == [k(n) for n in range(1, 14)], str(bw[:1]))
    ctx.close()

    # ================= the rest timer on each set =================
    s = store(days={T: {"food": [], "updated": 1, "goal": G, "cat": "push",
                        "lifts": [{"id": "l1", "cat": "push", "movement": "Bench Press", "sets": []}]}})
    ctx, p = phone(s, native=False)
    p.click('[data-tab="gym"]'); p.wait_for_timeout(300)
    p.fill('.lift .trow.is-plan .tw', "185"); p.fill('.lift .trow.is-plan .tr', "8")
    p.click('.lift .trow.is-plan .tlog'); p.wait_for_timeout(400)
    check("by its button: a set does not start the rest timer",
          p.evaluate("()=>document.getElementById('restBtn').textContent") == "Start")
    p.click("#setBtn"); p.wait_for_timeout(300)
    p.click('[data-pick-restauto="on"]'); p.wait_for_timeout(200)
    check("on each set: chosen, saved and said",
          p.evaluate("()=>JSON.parse(localStorage['iron-ledger-v1']).restAuto") is True and said(p) == "The rest timer now starts on each set you log", said(p))
    p.click("#setDone"); p.wait_for_timeout(200)
    p.fill('.lift .trow.is-plan .tw', "185"); p.fill('.lift .trow.is-plan .tr', "8")
    p.click('.lift .trow.is-plan .tlog'); p.wait_for_timeout(2300)
    run = p.evaluate("()=>[document.getElementById('restBtn').textContent, document.getElementById('restWayT').textContent, document.getElementById('restbar').hidden]")
    check("on each set: logging one starts the rest timer, folded on its button", run[0] == "Stop" and run[1].startswith("Rest 0:0") and run[2], str(run))
    p.fill('.lift .trow.is-plan .tw', "185"); p.fill('.lift .trow.is-plan .tr', "7")
    p.click('.lift .trow.is-plan .tlog'); p.wait_for_timeout(300)
    check("on each set: the next set starts it again from 0:00",
          p.evaluate("()=>document.getElementById('restWayT').textContent") == "Rest 0:00", p.evaluate("()=>document.getElementById('restWayT').textContent"))
    ctx.close()

    check("no page errors", not errs, "; ".join(errs[:3]))
    b.close()

fails = [r for r in res if r[0] == "FAIL"]
for r in res:
    print(("  " if r[0] == "PASS" else "✕ ") + r[1] + ("" if r[0] == "PASS" else "  [" + r[2] + "]"))
print("%d passed, %d FAILED" % (len(res) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
