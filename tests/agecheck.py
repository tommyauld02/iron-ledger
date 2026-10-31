"""The age check and Ask an agent's permission, answered the way a person would.

Decided 2026-10-28: the whole app is 18+, because Gemini's terms are for
adults, and Ask an agent asks before it first sends anything to Google's AI
(App Review 5.1.2(i)). Every other suite opens past both (tests/answered.py,
fakeai.phone); this one is the suite that answers them, on a phone.

It checks that:
- a first open shows the age check before anything else, with the approved
  words, the links to the terms, privacy policy and support, and nothing of
  the app reachable behind it; nothing is saved until it is answered. Since
  b81 it asks for a birth date (tests/profile.py has the date's own checks:
  bad dates, Is that right?, the second chance, the profile after it)
- an incomplete check (the app closed on the screen) asks again next time
- 18 or older: the profile follows, then the app; the answer and the Terms are
  kept in consent and the birth date in the profile; not asked again
- under 18: the sorry screen, the links, no way into the app but entering the
  date again, and the same screen on a relaunch; only the no is kept, no
  date; nothing goes anywhere
- an existing install with a log is asked once, What's new waits behind the
  check, and the log is untouched whichever way it is answered
- the web build served over http, and the iPhone app, whose answer is kept in
  native storage with the log, and whose live update is told the build started
  while the check is still up
- Ask an agent: the sheet before the first send, its words, Not now sends
  nothing and says so, Allow and ask sends {food, region} and nothing else
- a pending row's Tap to estimate and Find it again go through the same sheet
- withdrawing in Settings stops sends at once, including one on its way
- no request reaches the relay without both answers (tests/fakeai.py stands in
  for it, and every request to its address is counted, preflights included)
- the yes keeps which version of the Terms of Use was agreed to, and when;
  Settings shows the date; a later version asks an adult once more (#termsAsk),
  and a b79 yes without a version counts as the first published one
- 44px targets, and the screens' contrast in light and dark

What it cannot show: that the person is 18. The check is self-declared — a
child can type another year. It records an answer; it is not proof of age.
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
TERMS = re.search(r'var TERMS = "([^"]+)"', SRC).group(1)
PAGES = "https://tommyauld02.github.io/iron-ledger/"
PHONE = {"width": 393, "height": 852}
SMALL = {"width": 320, "height": 640}
T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}

res = []
errs = []
def check(n, ok, det=""):
    res.append(("PASS" if ok else "FAIL", n, det))


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

ASK_WORDS = [
    "MNTL D&T",
    "When were you born?",
    "MNTL D&T is for adults, 18 or older. Your birth date stays on this phone — the app also uses it to work out your calories.",
    "Continue",
    "By continuing you agree to the Terms of Use and Privacy Policy.",
]
NO_WORDS = [
    "Sorry, MNTL D&T is for adults",
    "You need to be 18 or older to use it. Nothing has been saved about you, and nothing was sent anywhere.",
    "Wrong birth date? Enter it again",
    "Questions? The privacy policy and support page are below.",
]
AI_WORDS = [
    "Ask an agent uses Google’s AI",
    "To estimate a food, MNTL D&T sends what you type and your country to Google Gemini, through our relay. Nothing else from your log is sent.",
    "Google’s free service may keep it, use it to improve its products, and have people review it. Don’t include personal information.",
    "Allow and ask",
    "Not now",
    "Logging, the pantry, barcodes and labels all work without it. You can change this any time in Settings.",
    "Privacy Policy",
]
LINKS = {"Terms of Use": PAGES + "terms.html", "Privacy Policy": PAGES + "privacy.html",
         "Support": PAGES + "support.html", "mntldntsupport@gmail.com": "mailto:mntldntsupport@gmail.com"}


def agreed(c, **more):
    """The yes to the age check: adult, the version of the Terms agreed to and
    when, and whatever else is named — nothing more."""
    c = dict(c or {})
    at = c.pop("termsAt", None)
    return c.pop("terms", None) == TERMS and isinstance(at, (int, float)) and c == dict(adult=True, **more)


def fixture(build="2026-10-26.78", consent=None, pending=False):
    food = [{"id": "f1", "cal": 480, "pro": 40, "note": "Eggs and oats"}]
    if pending:
        food.append({"id": "w1", "cal": 0, "pro": 0, "note": "6 oz sirloin", "pending": True})
    s = {"days": {T: {"food": food, "lifts": [], "updated": 1, "goal": G}},
         "moves": {}, "movesOwned": True, "goal": G, "region": "United States",
         "pantry": [], "v": 1, "build": build, "seen": True}
    if consent is not None:
        s["consent"] = consent
    return s


def open_phone(b, url=FILE, stored=None, relay=False, size=PHONE, asked=None, scheme=None, extra=None):
    ctx = b.new_context(viewport=size, has_touch=True, is_mobile=True, color_scheme=scheme or "light")
    ctx.add_init_script("delete window.claude;")
    if relay:
        fakeai.phone(ctx, log=asked, allowed=False)      # nobody has said yes here
    if stored is not None:
        # written before the app's first open only: a reload keeps what the app saved
        ctx.add_init_script("localStorage.getItem(%r) || localStorage.setItem(%r, %s)"
                            % (KEY, KEY, json.dumps(json.dumps(stored))))
    if extra:
        extra(ctx)
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append(str(e)))
    hits = []
    p.on("request", lambda r: hits.append(r.method + " " + r.url) if r.url.startswith(fakeai.RELAY) else None)
    p.goto(url)
    p.wait_for_timeout(700)
    return ctx, p, hits


def text(p, sel):
    return p.evaluate("s => { const e = document.querySelector(s); return e ? e.innerText : '' }", sel)
def shown(p, sel):
    return p.evaluate("s => { const e = document.querySelector(s); return !!e && e.getClientRects().length > 0 }", sel)
def saved(p):
    return p.evaluate("k => { try { return JSON.parse(localStorage.getItem(k)) } catch (e) { return null } }", KEY)
def bar(p):
    return p.evaluate("() => document.getElementById('undobar').hidden ? '' : document.getElementById('undoLabel').textContent")


TARGETS = """sel => [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length).map(e => {
  e.scrollIntoView({ block: 'center' });            // a sheet scrolls; tap it where a thumb would
  const r = e.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { t: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30),
           w: Math.round(r.width), h: Math.round(r.height), reached: !!hit && (hit === e || e.contains(hit)) };
})"""

def targets(p, sel, what):
    got = p.evaluate(TARGETS, sel)
    small = [x for x in got if x["w"] < 44 or x["h"] < 44]
    blocked = [x["t"] for x in got if not x["reached"]]
    check("%s: every control is 44px or more (%d)" % (what, len(got)), got and not small, small)
    check("%s: a tap at each control's centre reaches it" % what, got and not blocked, blocked)


def links(p, scope, what):
    got = p.evaluate("""s => [...document.querySelectorAll(s + ' a')].filter(a => a.getClientRects().length)
                         .map(a => [a.innerText.trim(), a.href])""", scope)
    have = dict(got)
    check("%s: links to the terms, privacy policy, support and the support email" % what,
          all(have.get(k) == v for k, v in LINKS.items()), got)


CONTRAST = """sel => {
  const lum = c => { const m = c.match(/[\\d.]+/g); if (!m) return null;
    const [r, g, b] = m.slice(0, 3).map(n => { n /= 255; return n <= .03928 ? n / 12.92 : Math.pow((n + .055) / 1.055, 2.4); });
    return .2126 * r + .7152 * g + .0722 * b; };
  const bad = []; let n = 0;
  document.querySelectorAll(sel).forEach(el => {
    if (!el.getClientRects().length) return;
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


def tap(p, sel, wait=300):
    """Taps a control that ought to be on screen. One that isn't is left to
    the checks to name, rather than stopping the suite on a timeout."""
    if shown(p, sel):
        p.click(sel); p.wait_for_timeout(wait)


def born(p, y="1992", m="3", d="14"):
    """Answers the age check with a birth date, the way a person would."""
    p.select_option("#dobM", m); p.fill("#dobD", d); p.fill("#dobY", y)
    p.click("#ageGo"); p.wait_for_timeout(400)


def adult(p):
    """18 or older, and past the profile that follows a first yes."""
    born(p)
    if shown(p, "#pfSkip"):
        p.click("#pfSkip"); p.wait_for_timeout(300)


def under18(p):
    """A date under 18, said back, and confirmed."""
    born(p, y="2012")
    if shown(p, "#ageSure"):
        p.click("#ageSure"); p.wait_for_timeout(400)


def ask_agent(p, words="6 oz sirloin"):
    if shown(p, "#discardEst"):                          # a review open from the last one
        p.click("#discardEst"); p.wait_for_timeout(250)
    if not shown(p, "#estText"):
        p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
    p.fill("#estText", words)
    p.click("#runEst"); p.wait_for_timeout(500)


with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- a first open, on the web build opened from disk ----
    ctx, p, hits = open_phone(b)
    check("first open: the age check is on screen", shown(p, "#ageAsk"))
    words = text(p, "#ageAsk")
    missing = [w for w in ASK_WORDS if w not in words]
    check("first open: the approved words, every one", not missing, missing)
    links(p, "#ageAsk", "age check")
    check("first open: nothing of the app is drawn behind it", p.evaluate("() => document.getElementById('view').innerHTML.trim() === ''"))
    check("first open: the app behind it can't be reached (inert)", p.evaluate("() => document.querySelector('.app').inert === true"))
    behind = p.evaluate("""() => { const t = document.querySelector('.tabs'); const r = t.getBoundingClientRect();
                             const h = document.elementFromPoint(r.left + r.width / 2, Math.min(r.top + r.height / 2, innerHeight - 2));
                             return !!h && !!h.closest('#ageGate'); }""")
    check("first open: a tap where the tab bar is lands on the age check", behind)
    check("first open: nothing is saved before it is answered", saved(p) is None, saved(p))
    check("first open: What's new is not shown to a new phone", not shown(p, "#newsSheet"))
    targets(p, "#ageAsk button, #ageAsk a", "age check")
    check("first open: the birth date's boxes are 16px or more, so iOS doesn't zoom", p.evaluate(
        "() => [...document.querySelectorAll('#ageAsk input, #ageAsk select')].every(e => parseFloat(getComputedStyle(e).fontSize) >= 16)"))
    contrast(p, "#ageAsk *", "age check, light")

    # closed on the screen, opened again
    p.reload(); p.wait_for_timeout(700)
    check("an incomplete check asks again on the next open", shown(p, "#ageAsk") and not shown(p, "#ageNo"))
    check("an incomplete check saved nothing", saved(p) is None, saved(p))

    # 18 or older
    born(p)
    check("18 or older: the age check goes", not shown(p, "#ageGate"))
    check("18 or older: the profile follows a first yes", shown(p, "#profGate") and text(p, "#profTitle") == "About you")
    p.click("#pfSkip"); p.wait_for_timeout(300)
    check("18 or older: the app opens on the tour", shown(p, ".welcome") and shown(p, ".tabs"))
    check("18 or older: the app is reachable again", p.evaluate("() => document.querySelector('.app').inert === false"))
    check("18 or older: it says where the profile is", "Settings" in bar(p), bar(p))
    s = saved(p) or {}
    check("18 or older: the answer is kept — adult: true, with the Terms' version and when",
          agreed(s.get("consent")), s.get("consent"))
    check("18 or older: the birth date is kept in the profile, and only there",
          (s.get("profile") or {}).get("dob") == "1992-03-14" and json.dumps(s).count("1992-03-14") == 1, s.get("profile"))
    p.reload(); p.wait_for_timeout(700)
    check("18 or older: a relaunch goes straight into the app", not shown(p, "#ageGate") and shown(p, ".tabs"))
    check("18 or older: no request to the relay", not hits, hits)
    ctx.close()

    # dark, before answering
    ctx, p, hits = open_phone(b, scheme="dark")
    contrast(p, "#ageAsk *", "age check, dark")
    born(p, y="2012")
    contrast(p, "#ageCheck *", "Is that right?, dark")
    p.click("#ageSure"); p.wait_for_timeout(400)
    contrast(p, "#ageNo *", "sorry screen, dark")
    ctx.close()

    # ---- under 18, on a first open ----
    ctx, p, hits = open_phone(b, size=SMALL)
    targets(p, "#ageAsk button, #ageAsk a", "age check at 320px")
    check("age check at 320px: no sideways scroll", p.evaluate("() => document.documentElement.scrollWidth <= innerWidth"))
    born(p, y="2012")
    check("under 18: said back before it counts", shown(p, "#ageCheck") and not shown(p, "#ageNo"))
    targets(p, "#ageCheck button, #ageCheck a", "Is that right? at 320px")
    contrast(p, "#ageCheck *", "Is that right?, light")
    p.click("#ageSure"); p.wait_for_timeout(400)
    check("under 18: the sorry screen", shown(p, "#ageNo") and not shown(p, "#ageAsk"))
    words = text(p, "#ageNo")
    missing = [w for w in NO_WORDS if w not in words]
    check("under 18: the approved words, every one", not missing, missing)
    links(p, "#ageNo", "sorry screen")
    check("under 18: one button on it, to enter the date again — no other way into the app",
          p.evaluate("() => [...document.querySelectorAll('#ageNo button')].map(b => b.id)") == ["ageAgain"])
    check("under 18: the app stays out of reach", p.evaluate("() => document.querySelector('.app').inert === true")
          and p.evaluate("() => document.getElementById('view').innerHTML.trim() === ''"))
    targets(p, "#ageNo a, #ageNo button", "sorry screen at 320px")
    contrast(p, "#ageNo *", "sorry screen, light")
    s = saved(p) or {}
    check("under 18: only the answer is kept — adult: false", s.get("consent") == {"adult": False}, s.get("consent"))
    check("under 18: no birth date anywhere in the log", "2012" not in json.dumps(s) and not (s.get("profile") or {}).get("dob"), s.get("profile"))
    p.reload(); p.wait_for_timeout(700)
    check("under 18: a relaunch shows the same sorry screen, not the question",
          shown(p, "#ageNo") and not shown(p, "#ageAsk"))
    check("under 18: nothing went anywhere", not hits, hits)
    ctx.close()

    # ---- an existing install, with a log, from the build before ----
    old = fixture()
    ctx, p, hits = open_phone(b, stored=old)
    check("existing install: asked once, on the next open", shown(p, "#ageAsk"))
    check("existing install: What's new waits behind the check", not shown(p, "#newsSheet"))
    check("existing install: nothing written before it is answered", saved(p) == old)
    born(p)
    check("existing install: the profile first, What's new waiting behind it", shown(p, "#profGate") and not shown(p, "#newsSheet"))
    p.click("#pfSkip"); p.wait_for_timeout(300)
    check("existing install: What's new follows, with this build", shown(p, "#newsSheet") and ("b" + BUILD.split(".")[1]).upper() in text(p, "#newsBody").upper(),
          text(p, "#newsBody")[:80])
    p.click("#newsDone"); p.wait_for_timeout(200)
    s = saved(p) or {}
    check("existing install: the log is untouched", s.get("days") == old["days"] and s.get("build") == BUILD)
    check("existing install: the answer is added beside it", agreed(s.get("consent")), s.get("consent"))
    p.reload(); p.wait_for_timeout(700)
    check("existing install: not asked again", not shown(p, "#ageGate") and not shown(p, "#newsSheet")
          and "Eggs and oats" in text(p, "#view"))
    ctx.close()

    ctx, p, hits = open_phone(b, stored=old)
    under18(p)
    said = text(p, "#ageNo")
    check("existing install, under 18: it doesn't claim nothing was saved",
          "What you logged before stays on this phone, and nothing was sent anywhere." in said
          and "Nothing has been saved about you" not in said, said)
    s = saved(p) or {}
    check("existing install, under 18: the log is still there, untouched", s.get("days") == old["days"])
    ctx.close()

    # ---- the web build, served over http as on Pages ----
    ctx, p, hits = open_phone(b, url=BASE)
    check("web over http: the age check before anything else", shown(p, "#ageAsk"))
    adult(p)
    check("web over http: the answer is in localStorage", agreed((saved(p) or {}).get("consent")))
    p.reload(); p.wait_for_timeout(700)
    check("web over http: not asked again", not shown(p, "#ageGate"))
    ctx.close()

    # ---- the iPhone app: the answer lives in native storage, with the log ----
    prefs = {}; calls = []
    def bridge(plugin, method, opts):
        calls.append((plugin, method))
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
    def on_phone():
        v = prefs.get("CapacitorStorage." + KEY)
        return json.loads(v) if v else None
    ctx, p, hits = open_phone(b, url=BASE, extra=native)
    check("iPhone app: the age check on a first open", shown(p, "#ageAsk"))
    check("iPhone app: the live update is told the build started, with the check still up",
          ("CapacitorUpdater", "notifyAppReady") in calls, calls)
    check("iPhone app: nothing in native storage before it is answered", on_phone() is None)
    adult(p)
    check("iPhone app: the answer is in native storage", agreed((on_phone() or {}).get("consent")))
    check("iPhone app: and not in the WebView's localStorage", saved(p) is None, saved(p))
    ctx.close()
    ctx, p, hits = open_phone(b, url=BASE, extra=native)      # a cold start, the WebView's storage gone
    check("iPhone app: a relaunch goes straight in", not shown(p, "#ageGate") and shown(p, ".tabs"))
    ctx.close()

    # ---- Ask an agent asks before it first sends ----
    asked = []
    ctx, p, hits = open_phone(b, relay=True, asked=asked)
    adult(p)
    p.click("#dismissWelcome"); p.wait_for_timeout(200)
    ask_agent(p)
    check("Ask an agent: the permission sheet before anything is sent", shown(p, "#aiSheet"))
    words = text(p, "#aiSheet")
    missing = [w for w in AI_WORDS if w not in words.replace("\n", " ") and w not in words]
    check("Ask an agent: the approved words, every one", not missing, missing)
    check("Ask an agent: what is sent is in bold", p.evaluate(
        "() => [...document.querySelectorAll('#aiSheet strong')].map(e => e.innerText).join('|')") == "what you type|your country")
    check("Ask an agent: its Privacy Policy link", p.evaluate(
        "() => document.querySelector('#aiSheet a').href") == PAGES + "privacy.html")
    check("Ask an agent: no request has gone to the relay yet", not hits, hits)
    targets(p, "#aiSheet button, #aiSheet a", "permission sheet")
    contrast(p, "#aiSheet *", "permission sheet, light")
    tap(p, "#aiNo", 400)
    check("Not now: the sheet goes", not shown(p, "#aiSheet"))
    check("Not now: nothing was sent", not hits and not asked, hits)
    check("Not now: it says nothing was sent, where the answer would be",
          "Nothing was sent" in text(p, "#view"), text(p, "#view")[-300:])
    check("Not now: kept as a no, with no date", agreed((saved(p) or {}).get("consent"), ai=False),
          (saved(p) or {}).get("consent"))
    # the food waits as a placeholder; Find it again asks again
    if shown(p, "[data-reask]"):
        p.click("[data-reask]"); p.wait_for_timeout(400)
        check("Find it again: the sheet again, rather than a send", shown(p, "#aiSheet") and not hits, hits)
        tap(p, "#aiNo", 300)
        check("Find it again, Not now: still nothing sent", not hits, hits)
    else:
        check("Find it again: the placeholder offers it", False, "no [data-reask] on screen")
    ask_agent(p)
    check("asked again: the sheet comes back", shown(p, "#aiSheet") and not hits)
    tap(p, "#aiYes", 900)
    check("Allow and ask: the question goes, once", len(asked) == 1, asked)
    check("Allow and ask: only the words and the country are sent",
          asked and set(asked[0]["body"].keys()) == {"food", "region"} and asked[0]["body"]["food"] == "6 oz sirloin", asked and asked[0]["body"])
    check("Allow and ask: the answer comes back to review", "Sirloin" in text(p, "#view"))
    check("Allow and ask: it says so", "Ask an agent is on" in bar(p), bar(p))
    c = (saved(p) or {}).get("consent") or {}
    check("Allow and ask: kept as a yes, with when", c.get("ai") is True and isinstance(c.get("aiAt"), (int, float))
          and set(c) == {"adult", "ai", "aiAt", "terms", "termsAt"}, c)
    n = len(asked)
    ask_agent(p, "2 eggs")
    check("once allowed, it doesn't ask every time", not shown(p, "#aiSheet") and len(asked) == n + 1)

    # withdrawn in Settings: nothing more is sent
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("Settings: Ask an agent shows On, and when it was allowed",
          p.evaluate("() => document.querySelector('[data-pick-ai=on]').getAttribute('aria-pressed')") == "true"
          and text(p, "#setAiHint").startswith("Allowed on"), text(p, "#setAiHint"))
    links(p, "#setSheet", "Settings")
    check("Settings: when the Terms of Use were agreed to",
          text(p, "#setTermsHint").startswith("You agreed to the Terms of Use on"), text(p, "#setTermsHint"))
    targets(p, "#setAi button, #setSheet .ag-links a", "Settings")
    p.click('[data-pick-ai="off"]'); p.wait_for_timeout(300)
    check("withdrawn: Settings shows Off and says nothing is sent",
          p.evaluate("() => document.querySelector('[data-pick-ai=off]').getAttribute('aria-pressed')") == "true"
          and "nothing is sent" in text(p, "#setAiHint"), text(p, "#setAiHint"))
    check("withdrawn: kept as a no, the date gone", agreed((saved(p) or {}).get("consent"), ai=False))
    p.click("#setDone"); p.wait_for_timeout(200)
    check("withdrawn: it says so", "Ask an agent is off" in bar(p), bar(p))
    n = len(hits)
    ask_agent(p, "1 banana")
    check("withdrawn: Ask an agent asks again instead of sending", shown(p, "#aiSheet") and len(hits) == n, hits[n:])
    tap(p, "#aiNo", 300)
    check("withdrawn, Not now: nothing sent", len(hits) == n, hits[n:])
    # On again from Settings goes through the same sheet
    p.click("#setBtn"); p.wait_for_timeout(300)
    p.click('[data-pick-ai="on"]'); p.wait_for_timeout(300)
    check("On in Settings: the same permission sheet, with Allow", shown(p, "#aiSheet")
          and p.evaluate("() => document.getElementById('aiYes').textContent") == "Allow")
    tap(p, "#aiYes", 300)
    check("On in Settings: on, with a date, and nothing sent by it",
          ((saved(p) or {}).get("consent") or {}).get("ai") is True and len(hits) == n
          and text(p, "#setAiHint").startswith("Allowed on"))
    ctx.close()

    # ---- the Terms change: asked once more, of an adult ----
    TERMS_WORDS = ["The Terms of Use have changed",
                   "Have a look at them below, then agree to keep using the app. Your log stays as it is.",
                   "I agree"]
    older = fixture(BUILD, {"adult": True, "terms": "2000-01-01", "termsAt": 1})
    ctx, p, hits = open_phone(b, stored=older)
    check("Terms changed: asked before anything else", shown(p, "#termsAsk") and not shown(p, "#ageAsk") and not shown(p, "#ageNo"))
    words = text(p, "#termsAsk")
    missing = [w for w in TERMS_WORDS if w not in words]
    check("Terms changed: the words, every one", not missing, missing)
    links(p, "#termsAsk", "Terms changed")
    check("Terms changed: no under-18 button — that was answered",
          p.evaluate("() => document.querySelectorAll('#termsAsk button').length") == 1)
    check("Terms changed: the app behind it can't be reached", p.evaluate("() => document.querySelector('.app').inert === true"))
    check("Terms changed: the dialog is named by its own heading",
          p.evaluate("() => document.getElementById('ageGate').getAttribute('aria-labelledby')") == "termsTitle")
    check("Terms changed: nothing written before it is answered", saved(p) == older)
    targets(p, "#termsAsk button, #termsAsk a", "Terms changed")
    contrast(p, "#termsAsk *", "Terms changed, light")
    p.click("#termsYes"); p.wait_for_timeout(500)
    check("Terms changed, I agree: the screen goes and the app opens", not shown(p, "#ageGate") and "Eggs and oats" in text(p, "#view"))
    check("Terms changed, I agree: it says so", "agreed to the new Terms of Use" in bar(p), bar(p))
    s = saved(p) or {}
    check("Terms changed, I agree: this version, with a new date, the log untouched",
          agreed(s.get("consent")) and s["consent"]["termsAt"] > 1 and s.get("days") == older["days"], s.get("consent"))
    p.reload(); p.wait_for_timeout(700)
    check("Terms changed: not asked again", not shown(p, "#ageGate"))
    ctx.close()
    ctx, p, hits = open_phone(b, stored=older, scheme="dark")
    contrast(p, "#termsAsk *", "Terms changed, dark")
    ctx.close()
    # a yes from b79, before versions were kept, is the first published version
    ctx, p, hits = open_phone(b, stored=fixture(BUILD, {"adult": True}))
    check("a b79 yes, with no version: not asked again", not shown(p, "#ageGate") and "Eggs and oats" in text(p, "#view"))
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("a b79 yes: Settings shows no agreed date rather than one made up", text(p, "#setTermsHint") == "", text(p, "#setTermsHint"))
    ctx.close()

    # dark: the permission sheet
    ctx, p, hits = open_phone(b, relay=True, scheme="dark", stored=fixture(BUILD, {"adult": True}))
    ask_agent(p)
    contrast(p, "#aiSheet *", "permission sheet, dark")
    ctx.close()

    # ---- a pending row's Tap to estimate goes through the same sheet ----
    asked = []
    ctx, p, hits = open_phone(b, relay=True, asked=asked, stored=fixture(BUILD, {"adult": True}, pending=True))
    p.click('[data-est="w1"]'); p.wait_for_timeout(400)
    check("Tap to estimate: the permission sheet, nothing sent", shown(p, "#aiSheet") and not hits, hits)
    tap(p, "#aiNo", 300)
    check("Tap to estimate, Not now: nothing sent, and it says so", not hits and "Nothing was sent" in text(p, "#view"))
    ctx.close()

    # ---- the age answer is needed too: a stored AI yes without it sends nothing ----
    ctx, p, hits = open_phone(b, relay=True, stored=fixture(BUILD, {"ai": True, "aiAt": 1}, pending=True))
    check("AI yes but no age answer: the age check, first", shown(p, "#ageAsk"))
    under18(p)
    check("AI yes but under 18: the AI yes is dropped, and nothing is sent",
          (saved(p) or {}).get("consent") == {"adult": False} and not hits, (saved(p) or {}).get("consent"))
    ctx.close()

    # ---- withdrawn while a question is on its way: called back ----
    held = []
    def hold(ctx):
        def h(route):
            if route.request.method == "OPTIONS":
                route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "POST, OPTIONS"})
            else:
                held.append(route)
        ctx.route(fakeai.RELAY, h)
    ctx, p, hits = open_phone(b, relay=True, extra=hold,
                              stored=fixture(BUILD, {"adult": True, "ai": True, "aiAt": 1}))
    ask_agent(p)
    p.wait_for_timeout(400)
    check("on its way: the question is out", len(held) == 1 and "Finding the numbers" in text(p, "#view"), len(held))
    p.click("#setBtn"); p.wait_for_timeout(200)
    p.click('[data-pick-ai="off"]'); p.wait_for_timeout(400)
    p.click("#setDone"); p.wait_for_timeout(200)
    try:
        held[0].fulfill(status=200, body=json.dumps(fakeai.answer("6 oz sirloin")), content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"})
    except Exception:
        pass                                             # already called back by the app
    p.wait_for_timeout(500)
    v = text(p, "#view")
    check("withdrawn mid-question: the answer is not used, and it says nothing was sent",
          "Nothing was sent" in v and "Sirloin" not in v, v[-300:])
    ctx.close()

    b.close()

# ---- read off the source: one way to the relay, and it refuses first ----
check("one fetch to the relay in the whole app", SRC.count("fetch(RELAY") == 1)
check("relayFind refuses without both answers before it does anything else",
      re.search(r"function relayFind\(text\) \{\s*if \(!grownUp\(\) \|\| !aiOn\(\)\) return Promise\.reject", SRC) is not None)
check("What's new has this build", '{ b: "%s"' % BUILD in SRC)
check("the goal calculator says its numbers are estimates, not medical advice",
      "Estimates only, not medical advice." in SRC)
check("Ask an agent's answers say they can be wrong",
      "AI answers can be wrong; check the label where there is one." in SRC)

for st, n, det in res:
    print("%s  %s%s" % (st, n, ("   " + str(det)[:200]) if st == "FAIL" and det != "" else ""))
bad = [r for r in res if r[0] == "FAIL"]
print("\n%d passed, %d FAILED" % (len(res) - len(bad), len(bad)))
print("pageerrors:", errs if errs else "none")
sys.exit(1 if bad or errs else 0)
