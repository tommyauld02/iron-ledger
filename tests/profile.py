"""The profile, and the birth date that is its first question, on a phone.

Asked for by Tommy (2026-10-28): one screen for name, birth date, gender,
weight and the goals for every tab, and a second chance at the birth date.
The age check used to be two buttons, and one wrong tap on "I'm under 18"
shut a phone out for good, its log behind it. Since b81 it asks for a birth
date, says an under-18 date back before it counts, and the sorry screen lets
the date be entered again, as many times as it takes.

Like tests/agecheck.py, this suite answers the age check itself, so it does
not import answered. It checks that:
- a birth date that can't be right says what is wrong, and nothing is saved
- under 18 is said back first (Is that right?); Change the date keeps it to fix
- the second chance: a phone that said under 18 (b79's button or a date) gets
  in with an adult date, as many tries as it takes, its log untouched
- nothing reaches Google's AI (the stand-in relay counts every request) until
  both answers are yes: under 18, no request at all; 18 or older, Ask an
  agent still asks before its first send
- after a first yes: About you, then Your goals, each skippable; the goals
  come from the calculator when none was set; Save keeps every one of them
  where the tabs read it, logs the weight as today's weigh-in, and has Undo
- Gender Other asks which equation the calculator uses; lb and kg convert
- Settings, You: who and the goals in force, and Edit opens the same screen;
  Cancel changes nothing; the target editor and its calculator read the same
  profile and never overwrite it
- a birth date changed to under 18 goes to the age check, said back first
- workouts a week on the Gym tab, a goal weight on the Log tab
- a restore keeps this phone's birth date and brings the goals back
- the iPhone app keeps the profile in native storage, with the log
- 44px targets, 16px fields, contrast in light and dark, no sideways scroll
"""
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, json, datetime, threading, functools, sys
import fakeai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = ROOT.replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
FILE = "file://" + d + "/mntl-dt.html"
KEY = "iron-ledger-v1"
SRC = io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()
BUILD = re.search(r'BUILD = "([^"]+)"', SRC).group(1)
PHONE = {"width": 393, "height": 852}
SMALL = {"width": 320, "height": 640}
TODAY = datetime.date.today()
T = TODAY.isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}
LB_KG = 0.45359237

res = []
errs = []
def check(n, ok, det=""):
    res.append(("PASS" if ok else "FAIL", n, det))


def age_on(y, m, dd):
    a = TODAY.year - y
    return a - 1 if (TODAY.month, TODAY.day) < (m, dd) else a


class H(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "mntl-dt.html")
        return super().translate_path(path)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]


def fixture(consent=None, **more):
    s = {"days": {T: {"food": [{"id": "f1", "cal": 480, "pro": 40, "note": "Eggs and oats"}], "lifts": [], "updated": 1, "goal": G}},
         "moves": {}, "movesOwned": True, "goal": G, "region": "United States",
         "pantry": [], "v": 1, "build": BUILD, "seen": True}
    if consent is not None:
        s["consent"] = consent
    s.update(more)
    return s


def open_phone(b, stored=None, size=PHONE, scheme=None, relay=False, asked=None, extra=None):
    ctx = b.new_context(viewport=size, has_touch=True, is_mobile=True, color_scheme=scheme or "light")
    ctx.add_init_script("delete window.claude;")
    if relay:
        fakeai.phone(ctx, log=asked, allowed=False)
    if stored is not None:
        # written once, before the app's first open: a reload keeps what the app
        # saved. A reload can read storage as empty for a moment on file:// and
        # under load (docs/testing.md), so "if it is empty" alone would seed again.
        ctx.add_init_script("if (location.protocol !== 'about:' && !window.name) { window.name = 'seeded'; "
                            "localStorage.getItem(%r) || localStorage.setItem(%r, %s) }"
                            % (KEY, KEY, json.dumps(json.dumps(stored))))
    if extra:
        extra(ctx)
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append(str(e)))
    hits = []
    p.on("request", lambda r: hits.append(r.method + " " + r.url) if r.url.startswith(fakeai.RELAY) else None)
    p.goto(BASE)
    p.wait_for_timeout(700)
    return ctx, p, hits


def text(p, sel):
    return p.evaluate("s => { const e = document.querySelector(s); return e ? e.innerText : '' }", sel)
def shown(p, sel):
    return p.evaluate("s => { const e = document.querySelector(s); return !!e && e.getClientRects().length > 0 }", sel)
def saved(p):
    return p.evaluate("k => { try { return JSON.parse(localStorage.getItem(k)) } catch (e) { return null } }", KEY) or {}
def bar(p):
    return p.evaluate("() => document.getElementById('undobar').hidden ? '' : document.getElementById('undoLabel').textContent")


def born(p, y="1992", m="3", dd="14"):
    p.select_option("#dobM", m); p.fill("#dobD", dd); p.fill("#dobY", y)
    p.click("#ageGo"); p.wait_for_timeout(400)


def ask_agent(p, words="6 oz sirloin"):
    if not shown(p, "#estText"):
        p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
    p.fill("#estText", words)
    p.click("#runEst"); p.wait_for_timeout(500)


TARGETS = """sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length && !e.disabled).map(e => {
  e.scrollIntoView({ block: 'center' });
  const r = e.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { t: (e.innerText || e.getAttribute('aria-label') || e.id || '').trim().slice(0, 30),
           w: Math.round(r.width), h: Math.round(r.height), reached: !!hit && (hit === e || e.contains(hit)) };
})"""

def targets(p, sel, what):
    got = p.evaluate(TARGETS, sel)
    small = [x for x in got if x["w"] < 44 or x["h"] < 44]
    blocked = [x["t"] for x in got if not x["reached"]]
    check("%s: every control is 44px or more (%d)" % (what, len(got)), got and not small, small)
    check("%s: a tap at each control's centre reaches it" % what, got and not blocked, blocked)


def fields16(p, scope, what):
    small = p.evaluate("""s => [...document.querySelectorAll(s + ' input, ' + s + ' select')]
        .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.id)""", scope)
    check("%s: every field is 16px or more, so iOS doesn't zoom" % what, not small, small)


CONTRAST = """sel => {
  const lum = c => { const m = c.match(/[\\d.]+/g); if (!m) return null;
    const [r, g, b] = m.slice(0, 3).map(n => { n /= 255; return n <= .03928 ? n / 12.92 : Math.pow((n + .055) / 1.055, 2.4); });
    return .2126 * r + .7152 * g + .0722 * b; };
  const bad = []; let n = 0;
  document.querySelectorAll(sel).forEach(el => {
    if (!el.getClientRects().length || el.disabled) return;
    const own = [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim());
    if (!own) return;
    n++;
    const s = getComputedStyle(el); let p = el, bg = null;
    while (p && p !== document.documentElement) { const c = getComputedStyle(p).backgroundColor;
      if (c && !c.includes('rgba(0, 0, 0, 0)')) { bg = c; break; } p = p.parentElement; }
    const f = lum(s.color), b = lum(bg || 'rgb(255,255,255)');
    const ratio = (Math.max(f, b) + .05) / (Math.min(f, b) + .05);
    const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
    if (ratio < need) bad.push(el.innerText.trim().slice(0, 30) + ' ' + ratio.toFixed(2));
  });
  return { n, bad };
}"""

def contrast(p, sel, what):
    got = p.evaluate(CONTRAST, sel)
    check("%s: every line reads at 4.5:1 or better (%d measured)" % (what, got["n"]), got["n"] > 2 and not got["bad"], got["bad"])


def no_sideways(p, what):
    check("%s: no sideways scroll" % what, p.evaluate(
        "() => document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll('#profCard, #ageGate .agecard')].every(e => e.scrollWidth <= e.clientWidth + 1)"))


with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- a birth date that can't be right says what is wrong ----
    ctx, p, hits = open_phone(b)
    p.click("#ageGo"); p.wait_for_timeout(200)
    check("bad date: empty asks for all three", "Enter the month, the day, and all four digits of the year." in text(p, "#ageErr"), text(p, "#ageErr"))
    born(p, y="1990", m="2", dd="30")
    check("bad date: February 30 is named", "There’s no February 30" in text(p, "#ageErr"), text(p, "#ageErr"))
    born(p, y=str(TODAY.year + 1))
    check("bad date: a date to come is caught", "hasn’t happened yet" in text(p, "#ageErr"), text(p, "#ageErr"))
    born(p, y="1850")
    check("bad date: 1850 is checked", "Check the year." in text(p, "#ageErr"), text(p, "#ageErr"))
    born(p, y="92")
    check("bad date: a two-digit year asks for four", "all four digits" in text(p, "#ageErr"), text(p, "#ageErr"))
    check("bad date: still the question, and nothing saved", shown(p, "#ageAsk") and saved(p) == {}, saved(p))

    # ---- under 18 is said back before it counts ----
    born(p, y="2010")
    words = text(p, "#ageCheck")
    check("Is that right?: the date and the age it makes, before anything is kept",
          shown(p, "#ageCheck") and "March 14, 2010" in words and ("makes you %d." % age_on(2010, 3, 14)) in words
          and "under 18 the app stays closed" in words and saved(p) == {}, words)
    check("Is that right?: named by its own heading",
          p.evaluate("() => document.getElementById('ageGate').getAttribute('aria-labelledby')") == "checkTitle")
    p.click("#ageFix"); p.wait_for_timeout(200)
    check("Change the date: back to the question with the date still in it, to fix",
          shown(p, "#ageAsk") and p.input_value("#dobY") == "2010" and p.input_value("#dobM") == "3")
    p.fill("#dobY", "1992"); p.click("#ageGo"); p.wait_for_timeout(400)
    check("fixed: in, with no no ever kept", shown(p, "#profGate") and (saved(p).get("consent") or {}).get("adult") is True)
    ctx.close()

    # ---- the second chance: a phone that said under 18, with a log on it ----
    asked = []
    old = fixture({"adult": False})          # b79's "I'm under 18", tapped by mistake
    ctx, p, hits = open_phone(b, stored=old, relay=True, asked=asked)
    check("second chance: the sorry screen, with a way to enter the date", shown(p, "#ageNo") and shown(p, "#ageAgain"))
    p.click("#ageAgain"); p.wait_for_timeout(200)
    check("Enter it again: the question, from empty", shown(p, "#ageAsk") and p.input_value("#dobY") == "" and p.input_value("#dobM") == "")
    born(p, y="2011"); p.click("#ageSure"); p.wait_for_timeout(300)
    check("under 18 again: the sorry screen again, still with its button", shown(p, "#ageNo") and shown(p, "#ageAgain"))
    for i in range(3):                       # any number of tries
        p.click("#ageAgain"); p.wait_for_timeout(150)
        born(p, y="2013"); p.click("#ageSure"); p.wait_for_timeout(200)
    check("any number of tries: still offered after five", shown(p, "#ageAgain"))
    p.reload(); p.wait_for_timeout(700)
    check("relaunched under 18: the sorry screen, the app out of reach",
          shown(p, "#ageNo") and p.evaluate("() => document.querySelector('.app').inert === true"))
    check("under 18, all of it: nothing reached the relay", not hits, hits)
    s = saved(p)
    check("under 18, all of it: only the no is kept, no date", s.get("consent") == {"adult": False}
          and "2011" not in json.dumps(s) and "2013" not in json.dumps(s), s.get("consent"))
    p.click("#ageAgain"); p.wait_for_timeout(150)
    born(p)
    check("an adult date at last: the profile follows", shown(p, "#profGate") and text(p, "#profTitle") == "About you")
    p.click("#pfSkip"); p.wait_for_timeout(300)
    s = saved(p)
    c = s.get("consent") or {}
    check("an adult date at last: in, adult, with the Terms agreed",
          not shown(p, "#ageGate") and "Eggs and oats" in text(p, "#view") and c.get("adult") is True and c.get("terms"))
    check("an adult date at last: the log is exactly as it was", s.get("days") == old["days"], s.get("days"))
    check("an adult date at last: the birth date is in the profile", (s.get("profile") or {}).get("dob") == "1992-03-14")
    check("an adult date at last: still nothing sent to the relay", not hits, hits)
    ask_agent(p)
    check("18 or older but no AI yes: Ask an agent asks first, and sends nothing", shown(p, "#aiSheet") and not hits, hits)
    p.click("#aiYes"); p.wait_for_timeout(900)
    check("both yeses: only then does a question go", len(asked) == 1, asked)
    ctx.close()

    # ---- after a first yes: About you, then Your goals ----
    ctx, p, hits = open_phone(b)
    born(p)
    check("setup: about you, 1 of 2", "Set up · 1 of 2".upper() in text(p, "#profCard").upper() and text(p, "#profTitle") == "About you")
    check("setup: the birth date just given, with the age", ("March 14, 1992 · %d" % age_on(1992, 3, 14)) in text(p, ".pf-dob"), text(p, ".pf-dob"))
    check("setup: the app behind it can't be reached", p.evaluate("() => document.querySelector('.app').inert === true"))
    targets(p, "#profCard button, #profCard input, #profCard select", "About you")
    fields16(p, "#profCard", "About you")
    contrast(p, "#profCard *", "About you, light")
    p.fill("#pfName", "Sam")
    p.click('[data-pfsex="o"]'); p.wait_for_timeout(100)
    check("Other: asks which equation the estimate uses", shown(p, "[data-pfcalc]") and "two equations" in text(p, "#pfCalcK"))
    p.click('[data-pfcalc="f"]'); p.wait_for_timeout(100)
    p.fill("#pfWt", "181"); p.fill("#pfFt", "5"); p.fill("#pfIn", "10")
    p.click('[data-pfunit="kg"]'); p.wait_for_timeout(100)
    check("lb to kg: the weight and height are converted, not re-read",
          p.input_value("#pfWt") == "82.1" and p.input_value("#pfCm") == "178", (p.input_value("#pfWt"), p.input_value("#pfCm")))
    check("lb to kg: what was typed stays", p.input_value("#pfName") == "Sam")
    p.fill("#pfWt", "82"); p.fill("#pfCm", "178")
    p.fill("#pfCm", "300"); p.click("#pfNext"); p.wait_for_timeout(200)
    check("a height that can't be right: said, and not on to the goals",
          "Check your height" in text(p, "#pfErr") and text(p, "#profTitle") == "About you", text(p, "#pfErr"))
    p.fill("#pfCm", "178")
    p.select_option("#pfAct", "1.375")
    p.click("#pfNext"); p.wait_for_timeout(300)
    check("setup: your goals, 2 of 2", text(p, "#profTitle") == "Your goals")
    age = age_on(1992, 3, 14)
    bmr = 10 * 82 + 6.25 * 178 - 5 * age - 161
    cal = max(1200, round((bmr * 1.375 - 500) / 10) * 10)
    pro = round(82 / LB_KG / 5) * 5
    check("no target set yet: the calculator's numbers are filled in, with the working shown",
          p.input_value("#pfCal") == str(cal) and p.input_value("#pfPro") == str(pro)
          and "You burn about" in text(p, "#pfCalc") and "Estimates only, not medical advice." in text(p, "#profCard"),
          (p.input_value("#pfCal"), p.input_value("#pfPro"), cal, pro))
    targets(p, "#profCard button, #profCard input, #profCard select", "Your goals")
    fields16(p, "#profCard", "Your goals")
    contrast(p, "#profCard *", "Your goals, light")
    p.click('[data-pfwater="on"]'); p.wait_for_timeout(100)
    p.fill("#pfWater", "80")
    p.fill("#pfGym", "9"); p.click("#pfSave"); p.wait_for_timeout(200)
    check("workouts a week over 7: said, nothing saved", "1 to 7" in text(p, "#pfErr") and shown(p, "#profGate") and not saved(p).get("gymGoal"))
    p.fill("#pfGym", "3")
    p.click('[data-pfkind="sessions"]'); p.wait_for_timeout(100)
    check("cardio: a new kind starts from its own number", p.input_value("#pfCv") == "3", p.input_value("#pfCv"))
    p.fill("#pfCv", "4")
    p.fill("#pfBwGoal", "78")
    p.click("#pfSave"); p.wait_for_timeout(500)
    check("Save and start: the app, and it says so with Undo", not shown(p, "#profGate") and "You’re all set" in bar(p)
          and shown(p, "#undoBtn"), bar(p))
    s = saved(p)
    pr = s.get("profile") or {}
    check("saved: who — name, birth date, gender and its equation, height, activity",
          pr.get("name") == "Sam" and pr.get("dob") == "1992-03-14" and pr.get("sex") == "o" and pr.get("calcSex") == "f"
          and pr.get("cm") == 178 and pr.get("act") == "1.375" and pr.get("setup") is True and "age" not in pr, pr)
    check("saved: the weight as today's weigh-in, in pounds", abs(((s.get("days") or {}).get(T) or {}).get("bw", 0) - round(82 / LB_KG, 1)) < 0.05,
          ((s.get("days") or {}).get(T) or {}).get("bw"))
    check("saved: calories and protein from today on", s.get("goal") == {"cal": {"dir": "-", "v": cal}, "pro": {"dir": "+", "v": pro}}
          and s["days"][T].get("goal") == s.get("goal"), s.get("goal"))
    check("saved: water shown, 80 oz", s.get("waterOn") is True and abs(s.get("waterGoalMl", 0) - 80 * 29.5735) < 1, s.get("waterGoalMl"))
    check("saved: 3 workouts a week, 4 sessions a week, a goal weight in pounds",
          s.get("gymGoal") == 3 and s.get("cardioGoal") == {"kind": "sessions", "period": "week", "v": 4}
          and abs(s.get("bwGoal", 0) - round(78 / LB_KG, 1)) < 0.05 and s.get("bwUnit") == "kg", (s.get("gymGoal"), s.get("cardioGoal"), s.get("bwGoal")))
    check("saved: nothing about the person in consent", set(s.get("consent") or {}) == {"adult", "terms", "termsAt"}, s.get("consent"))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    s = saved(p)
    check("Undo: every goal and the profile back as they were",
          s.get("goal") == G and "goal" not in s["days"].get(T, {})
          and not s.get("gymGoal") and not s.get("bwGoal") and not s.get("cardioGoal") and not s.get("waterOn")
          and (s.get("profile") or {}) == {"dob": "1992-03-14"} and "bw" not in s["days"].get(T, {}), s)
    ctx.close()

    # ---- the goals on the tabs, and Settings ----
    wk = TODAY - datetime.timedelta(days=(TODAY.weekday() + 1) % 7)       # this week's Sunday
    days = {}
    for i in (0, 1):
        k = (wk + datetime.timedelta(days=i)).isoformat()
        days[k] = {"food": [], "lifts": [{"id": "l%d" % i, "movement": "Bench Press", "sets": [{"w": 135, "r": 8}]}], "updated": 1, "goal": G}
    days.setdefault(T, {"food": [], "lifts": [], "updated": 1, "goal": G})["bw"] = 182
    stored = fixture({"adult": True, "terms": re.search(r'var TERMS = "([^"]+)"', SRC).group(1), "termsAt": 1},
                     profile={"name": "Tommy", "dob": "1992-03-14", "sex": "m", "ft": "5", "inch": "11", "act": "1.55", "aim": "-500", "setup": True},
                     gymGoal=2, bwGoal=175)
    stored["days"] = days
    ctx, p, hits = open_phone(b, stored=stored)
    p.click('[data-tab="gym"]'); p.wait_for_timeout(300)
    check("Gym: this week's workouts against the goal", text(p, "#gymGoal") == "This week: 2 of 2 workouts · done"
          and p.evaluate("() => document.getElementById('gymGoal').classList.contains('is-met')"), text(p, "#gymGoal"))
    p.click('[data-tab="log"]'); p.wait_for_timeout(300)
    check("Log: the goal weight beside the trend", text(p, "#bwGoal") == "Goal 175.0 lb · 7.0 lb to go on the trend", text(p, "#bwGoal"))
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("Settings, You: who", text(p, "#setWho") == "Tommy · %d · Male · 182.0 lb" % age_on(1992, 3, 14), text(p, "#setWho"))
    check("Settings, You: the goals in force", text(p, "#setWhoGoals").startswith("2,000 kcal · 150 g protein · 2 workouts a week · 150 min cardio a week")
          and "goal weight 175.0 lb" in text(p, "#setWhoGoals"), text(p, "#setWhoGoals"))
    targets(p, "#setProfile", "Settings, You")
    p.click("#setProfile"); p.wait_for_timeout(300)
    check("Edit profile & goals: the same screen, all on one page, on what is in force",
          shown(p, "#profGate") and text(p, "#profTitle") == "You" and p.input_value("#pfName") == "Tommy"
          and p.input_value("#pfGym") == "2" and p.input_value("#pfCal") == "2000" and shown(p, "#pfCancel"))
    targets(p, "#profCard button, #profCard input, #profCard select", "Edit profile")
    fields16(p, "#profCard", "Edit profile")
    contrast(p, "#profCard *", "Edit profile, light")
    before = saved(p)
    p.fill("#pfName", "Somebody else"); p.click("#pfCancel"); p.wait_for_timeout(300)
    check("Cancel: back to Settings, nothing changed", shown(p, "#setSheet") and not shown(p, "#profGate") and saved(p) == before)
    p.click("#setProfile"); p.wait_for_timeout(300)
    check("opened again: what is kept, not what was typed and cancelled", p.input_value("#pfName") == "Tommy")
    p.fill("#pfGym", "4"); p.fill("#pfCal", "2300")
    p.click("#pfSave"); p.wait_for_timeout(400)
    s = saved(p)
    check("Save: closed, and it says so", not shown(p, "#profGate") and not shown(p, "#setSheet") and "Saved your profile and goals" in bar(p), bar(p))
    check("Save: the goals the tabs read", s.get("gymGoal") == 4 and s["goal"]["cal"]["v"] == 2300 and s["days"][T]["goal"]["cal"]["v"] == 2300)
    check("Save: the days already logged keep their target", all(s["days"][k]["goal"] == G for k in s["days"] if k != T))
    check("Save: an unchanged weight logs nothing new", s["days"][T].get("bw") == 182)
    p.click('[data-tab="gym"]'); p.wait_for_timeout(300)
    check("Gym: the new goal at once", text(p, "#gymGoal") == "This week: 2 of 4 workouts · 2 to go", text(p, "#gymGoal"))
    # the target editor and its calculator read the same profile and keep it
    p.click('[data-tab="macros"]'); p.wait_for_timeout(300)
    if shown(p, "#dismissWelcome"):
        p.click("#dismissWelcome"); p.wait_for_timeout(200)
    p.evaluate("() => { const b = document.querySelector('.goaledit-open') || document.getElementById('openGoal'); if (b) b.click(); }")
    p.wait_for_timeout(300)
    check("target editor: the profile's calories", shown(p, "#gCal") and p.input_value("#gCal") == "2300", shown(p, "#gCal"))
    if shown(p, "#gcOpen"):
        p.click("#gcOpen"); p.wait_for_timeout(300)
        check("calculator: its age from the birth date, its sex from the profile",
              p.input_value("#gcAge") == str(age_on(1992, 3, 14))
              and p.evaluate("() => document.querySelector('[data-gcsex=m]').getAttribute('aria-pressed')") == "true")
        p.click("#gcUse"); p.wait_for_timeout(300)
        pr = saved(p).get("profile") or {}
        check("calculator's Use: into the profile, not over it", pr.get("name") == "Tommy" and pr.get("dob") == "1992-03-14" and pr.get("setup"), pr)
    else:
        check("calculator: reachable from the target editor", False, "no #gcOpen")
    ctx.close()

    # ---- a birth date changed to under 18, from the profile ----
    asked = []
    stored2 = fixture({"adult": True, "terms": re.search(r'var TERMS = "([^"]+)"', SRC).group(1), "termsAt": 1, "ai": True, "aiAt": 1},
                      profile={"name": "Tommy", "dob": "1992-03-14", "sex": "m", "setup": True})
    ctx, p, hits = open_phone(b, stored=stored2, relay=True, asked=asked)
    p.click("#setBtn"); p.wait_for_timeout(200); p.click("#setProfile"); p.wait_for_timeout(300)
    p.click("#pfDobOpen"); p.wait_for_timeout(100)
    check("Change: the date opens to edit, holding the one kept", p.input_value("#pfDy") == "1992" and p.input_value("#pfDm") == "3")
    p.fill("#pfDy", "2012"); p.click("#pfSave"); p.wait_for_timeout(400)
    check("changed to under 18: the age check, said back first", shown(p, "#ageCheck") and "makes you" in text(p, "#ageCheck") and not shown(p, "#profGate"))
    check("changed to under 18: not kept until it is confirmed", (saved(p).get("profile") or {}).get("dob") == "1992-03-14")
    p.click("#ageFix"); p.wait_for_timeout(200)
    check("Change the date: the date it was changed to, to fix", p.input_value("#dobY") == "2012")
    p.fill("#dobY", "1991"); p.click("#ageGo"); p.wait_for_timeout(400)
    s = saved(p)
    check("fixed: back in the app, the new date kept, no profile again", not shown(p, "#ageGate") and not shown(p, "#profGate")
          and s["profile"]["dob"] == "1991-03-14" and s["consent"]["adult"] is True and s["consent"].get("ai") is True)
    p.click("#setBtn"); p.wait_for_timeout(200); p.click("#setProfile"); p.wait_for_timeout(300)
    p.click("#pfDobOpen"); p.fill("#pfDy", "2012"); p.click("#pfSave"); p.wait_for_timeout(400)
    p.click("#ageSure"); p.wait_for_timeout(400)
    s = saved(p)
    check("confirmed under 18: the sorry screen over the app", shown(p, "#ageNo") and p.evaluate("() => document.querySelector('.app').inert === true"))
    check("confirmed under 18: the no kept; the AI yes, the Terms and the birth date gone",
          s.get("consent") == {"adult": False} and "dob" not in (s.get("profile") or {}), (s.get("consent"), s.get("profile")))
    check("confirmed under 18: the name and log stay", (s.get("profile") or {}).get("name") == "Tommy" and s["days"] == stored2["days"])
    check("confirmed under 18: nothing went to the relay", not hits, hits)
    ctx.close()

    # ---- a restore keeps this phone's birth date and brings the goals back ----
    stored3 = fixture({"adult": True, "terms": re.search(r'var TERMS = "([^"]+)"', SRC).group(1), "termsAt": 1},
                      profile={"dob": "1992-03-14", "setup": True})
    ctx, p, hits = open_phone(b, stored=stored3)
    backup = fixture(None, profile={"name": "Tommy", "sex": "m", "setup": True}, gymGoal=5, bwGoal=170)
    p.click("#backupBtn"); p.wait_for_timeout(200)
    p.fill("#backupText", json.dumps(backup)); p.click("#restoreBtn"); p.wait_for_timeout(300)
    s = saved(p)
    check("restore: the profile comes back, with this phone's birth date",
          (s.get("profile") or {}).get("name") == "Tommy" and s["profile"].get("dob") == "1992-03-14", s.get("profile"))
    check("restore: workouts a week and the goal weight come back", s.get("gymGoal") == 5 and s.get("bwGoal") == 170)
    ctx.close()

    # ---- the iPhone app: the profile in native storage, with the log ----
    prefs = {}
    def bridge(plugin, method, opts):
        if plugin == "CapacitorUpdater":
            return {"native": "1.0", "bundles": []} if method in ("current", "list") else {}
        if plugin != "Preferences":
            return {"error": "no such plugin"}
        k = "CapacitorStorage." + opts.get("key", "")
        if method == "get": return {"value": prefs.get(k)}
        if method == "set": prefs[k] = opts.get("value", ""); return {}
        return {"error": "unused"}
    BRIDGE = """window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'ios',
      isPluginAvailable: n => n === 'CapacitorUpdater',
      nativePromise: (pl, m, o) => window.__native(pl, m, o || {}).then(r => { if (r && r.error) throw new Error(r.error); return r; }) };"""
    def native(ctx):
        ctx.expose_function("__native", bridge)
        ctx.add_init_script(BRIDGE)
        ctx.route("**/live/manifest.json", lambda r: r.fulfill(status=404, body=""))
    ctx, p, hits = open_phone(b, extra=native)
    born(p)
    p.fill("#pfName", "Tommy"); p.click('[data-pfsex="m"]'); p.click("#pfNext"); p.wait_for_timeout(200)
    p.fill("#pfGym", "4"); p.click("#pfSave"); p.wait_for_timeout(600)
    v = prefs.get("CapacitorStorage." + KEY)
    on = json.loads(v) if v else {}
    check("iPhone app: the profile and goals are in native storage", (on.get("profile") or {}).get("name") == "Tommy"
          and on["profile"].get("dob") == "1992-03-14" and on.get("gymGoal") == 4, on.get("profile"))
    check("iPhone app: and not in the WebView's localStorage", p.evaluate("k => localStorage.getItem(k)", KEY) is None)
    ctx.close()
    ctx, p, hits = open_phone(b, extra=native)
    check("iPhone app: a relaunch goes straight in, with the profile", not shown(p, "#ageGate") and not shown(p, "#profGate") and shown(p, ".tabs"))
    ctx.close()

    # ---- a small phone, and dark ----
    ctx, p, hits = open_phone(b, size=SMALL)
    targets(p, "#ageAsk button, #ageAsk select, #ageAsk input", "age check at 320px")
    no_sideways(p, "age check at 320px")
    born(p)
    p.click('[data-pfsex="o"]'); p.wait_for_timeout(100)
    targets(p, "#profCard button, #profCard input, #profCard select", "About you at 320px")
    no_sideways(p, "About you at 320px")
    p.click("#pfNext"); p.wait_for_timeout(200)
    p.click('[data-pfwater="on"]'); p.wait_for_timeout(100)
    targets(p, "#profCard button, #profCard input, #profCard select", "Your goals at 320px")
    no_sideways(p, "Your goals at 320px")
    ctx.close()
    ctx, p, hits = open_phone(b, scheme="dark")
    born(p, y="2012")
    contrast(p, "#ageCheck *", "Is that right?, dark")
    p.click("#ageFix"); p.fill("#dobY", "1992"); p.click("#ageGo"); p.wait_for_timeout(400)
    p.click('[data-pfsex="o"]'); p.wait_for_timeout(100)
    contrast(p, "#profCard *", "About you, dark")
    p.click("#pfNext"); p.wait_for_timeout(200)
    contrast(p, "#profCard *", "Your goals, dark")
    ctx.close()

    b.close()

# ---- read off the source ----
check("What's new has this build", '{ b: "%s"' % BUILD in SRC)
check("relayFind still refuses without both answers before it does anything else",
      re.search(r"function relayFind\(text\) \{\s*if \(!grownUp\(\) \|\| !aiOn\(\)\) return Promise\.reject", SRC) is not None)
check("the calculator saves into the profile, never over it", "store.profile = pr" not in SRC)

for st, n, det in res:
    print("%s  %s%s" % (st, n, ("   " + str(det)[:300]) if st == "FAIL" and det != "" else ""))
bad = [r for r in res if r[0] == "FAIL"]
print("\n%d passed, %d FAILED" % (len(res) - len(bad), len(bad)))
print("pageerrors:", errs if errs else "none")
sys.exit(1 if bad or errs else 0)
