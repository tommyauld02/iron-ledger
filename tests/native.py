"""The iPhone app: is the log kept in native storage, and does it survive?

Inside the Capacitor shell (ios/) the log lives in native storage rather than
the WebView's localStorage, which iOS treats as website data and may clear
when the phone runs low on space. This suite stands in for Capacitor's bridge:
window.Capacitor answers nativePromise("Preferences", ...) from a dict held
here, in Python, outside the browser. Closing the browser context is an app
restart that also wipes the WebView's own storage, and the dict is what is
left on the phone — so a log that comes back after it really came from native
storage and nowhere else.

It checks that:
- a log written in the app is in native storage, and nothing is in localStorage
- it survives a restart, with the WebView's storage gone
- a failed native write puts the save bar up, stops claiming success, and is
  sent again until it lands; a write that never lands keeps the bar up
- a log that could not be read is never written over
- a slow read: taps before the log arrives cannot write over it
- a log in the WebView's own storage (a build from before native storage) is
  carried across, not started over
- no service worker inside the app, even served over http(s) as on Android
- the label reader is still offered, though the app is not on https
- the web build never touches the bridge
- a shell without the newer plugins is never called for them
- the rest alert, haptics and quick actions (b85), with stand-ins for the plugins
- the privacy manifest (shell 1.3): Xcode bundles it, it gives Apple's reasons
  and App Privacy's answers, and every "required reason" API in the shell's
  Swift, and the plugins' where node_modules is installed, is declared
- steps from Apple Health (shell 1.4), with a stand-in for HealthSteps: the
  web and a 1.3 shell keep typing and are never asked; the card, Not now and
  Undo; Connect reads the tracker's range and fills days as Health's; a typed
  day is never written over; Health's count is followed on coming back, at
  most once a minute; a read never redraws over something half typed; Use
  Apple Health's and Stop, with Undo; a failed read changes nothing; a
  restored backup still wins a Health-filled day, and never brings the
  phone's answer; nothing from Health says where the switch is; and the
  shell asks to read steps only, says why, and is signed with HealthKit

What it cannot show: that UserDefaults survives a phone restart. That is
Apple's to keep, and is on the list Tommy runs on his iPhone (docs/ios.md).
"""
import answered   # every page has said 18 or older: tests/answered.py
import gymways    # the Gym's bottom bar opens its boxes: tests/gymways.py
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, json, datetime, threading, functools, plistlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = ROOT.replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
FILE = "file://" + d + "/mntl-dt.html"
KEY = "iron-ledger-v1"
BUILD = re.search(r'BUILD = "([^"]+)"',
                  io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()).group(1)

res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))

T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}
def fixture(note):
    return {"days": {T: {"food": [{"id": "f1", "cal": 480, "pro": 40, "note": note}],
                         "lifts": [], "updated": 1, "goal": G}},
            "moves": {}, "movesOwned": True, "goal": G, "region": "United States",
            "pantry": [], "v": 1, "build": BUILD}


class H(SimpleHTTPRequestHandler):
    """Serves mntl-dt.html at /, so a service worker could register if allowed."""
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "mntl-dt.html")
        return super().translate_path(path)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % srv.server_address[1]

# What is on the phone outside the WebView. Survives every context.
native = {"prefs": {}, "fail_set": 0, "fail_get": False, "calls": []}

def bridge(plugin, method, opts):
    native["calls"].append((plugin, method))
    if plugin != "Preferences":
        return {"error": plugin + " is not implemented"}
    key = "CapacitorStorage." + opts.get("key", "")     # the prefix the iOS plugin uses
    if method == "get":
        if native["fail_get"]: return {"error": "simulated read failure"}
        return {"value": native["prefs"].get(key)}
    if method == "set":
        if native["fail_set"] > 0:
            native["fail_set"] -= 1
            return {"error": "simulated write failure"}
        native["prefs"][key] = opts.get("value", "")
        return {}
    return {"error": method + " is not used by the app"}

def on_phone():
    return native["prefs"].get("CapacitorStorage." + KEY) or ""

def ent_hk(app):
    """The shell is signed with HealthKit, which needs both Health purpose strings."""
    p = os.path.join(app, "App.entitlements")
    return os.path.exists(p) and plistlib.load(open(p, "rb")).get("com.apple.developer.healthkit") is True

# Capacitor's iOS bridge, as far as the app uses it: isNativePlatform() and
# nativePromise(). The real one posts to WKWebView and runs plugin calls one
# after another; this one hands each call to bridge() above, in order.
BRIDGE = """(() => {
  const getDelay = %d;
  window.Capacitor = {
    isNativePlatform: () => true,
    getPlatform: () => 'ios',
    nativePromise: (plugin, method, opts) => new Promise((resolve, reject) => {
      const call = () => window.__native(plugin, method, opts || {})
        .then(r => r && r.error ? reject(new Error(r.error)) : resolve(r), reject);
      if (method === 'get' && getDelay) setTimeout(call, getDelay); else call();
    })
  };
})();"""

PHONE = {"width": 402, "height": 874}
VIEW = "() => document.getElementById('view').innerText"
BAR_UP = "() => !document.getElementById('savebar').hidden"


def open_app(b, url=BASE, get_delay=0, webview_log=None, settle=900):
    """A cold start of the iPhone app: a fresh WebView, native storage as left."""
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.expose_function("__native", bridge)
    ctx.add_init_script(BRIDGE % get_delay)
    if webview_log is not None:
        ctx.add_init_script("localStorage.getItem(%r) || localStorage.setItem(%r, %s)"
                            % (KEY, KEY, json.dumps(json.dumps(webview_log))))
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(url); p.wait_for_timeout(settle)
    for t in ("Got it", "Start"):
        try:
            p.click("text=" + t, timeout=600)
        except Exception:
            pass
    p.wait_for_timeout(200)
    return ctx, p, errs


def macros(p):
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(300)


def add_food(p, cal, note):
    macros(p)
    if p.locator('[data-logway="numbers"][aria-expanded="false"]').count():
        p.click('[data-logway="numbers"]'); p.wait_for_timeout(250)
    p.fill("#fCal", str(cal)); p.fill("#fPro", "10"); p.fill("#fNote", note)
    p.click("#addFood")


with sync_playwright() as pw:
    b = pw.chromium.launch()
    allerrs = []

    # ---- 1. first open: the log goes to native storage --------------------
    ctx, p, errs = open_app(b)
    check("the app reads its log from native storage on opening",
          ("Preferences", "get") in native["calls"], str(native["calls"][:3]))
    check("the first open writes the log to native storage", BUILD in on_phone(), on_phone()[:80])
    add_food(p, 333, "NATIVE-ONE"); p.wait_for_timeout(500)
    check("adding a food says so", p.locator(".added-flash").count() == 1)
    check("and it is in native storage", "NATIVE-ONE" in on_phone())
    check("and not in the WebView's localStorage",
          p.evaluate("k => localStorage.getItem(k)", KEY) is None,
          str(p.evaluate("k => localStorage.getItem(k)", KEY))[:60])
    check("the save bar stays down", not p.evaluate(BAR_UP))
    allerrs += errs; ctx.close()

    # ---- 2. restart, with the WebView's storage gone ----------------------
    ctx, p, errs = open_app(b)
    check("a restart starts with an empty WebView",
          p.evaluate("k => localStorage.getItem(k)", KEY) is None)
    macros(p)
    check("the log survives an app restart", "NATIVE-ONE" in p.evaluate(VIEW),
          p.evaluate(VIEW)[:200])
    add_food(p, 222, "NATIVE-TWO"); p.wait_for_timeout(500)
    allerrs += errs; ctx.close()
    ctx, p, errs = open_app(b)
    macros(p)
    v = p.evaluate(VIEW)
    check("and the next one, with both foods", "NATIVE-ONE" in v and "NATIVE-TWO" in v, v[:200])
    allerrs += errs; ctx.close()

    # ---- 3. a native write fails -----------------------------------------
    ctx, p, errs = open_app(b)
    native["fail_set"] = 1
    add_food(p, 111, "FAIL-ONE"); p.wait_for_timeout(500)
    check("a failed native write puts the save bar up", p.evaluate(BAR_UP))
    check("and takes back the ✓ it had already shown", p.locator(".added-flash").count() == 0,
          p.inner_text(".added-flash") if p.locator(".added-flash").count() else "")
    check("while the food stays on screen, real for this session", "FAIL-ONE" in p.evaluate(VIEW))
    check("the bar says nothing is being kept",
          "nothing you log now will be kept" in p.inner_text("#saveLabel"), p.inner_text("#saveLabel"))
    p.click("#backupBtn"); p.wait_for_timeout(400)
    diag = p.eval_on_selector("#diag", "e => e.textContent")
    check("the Backup panel names it", "NOT SAVING" in diag and "NativeStorageError" in diag, diag[:120])
    p.click("#closeSheet"); p.wait_for_timeout(300)
    native["fail_set"] = 99           # still failing
    add_food(p, 112, "FAIL-TWO"); p.wait_for_timeout(500)
    check("while writes fail, adding does not claim success",
          p.locator(".added-flash").count() == 0
          and p.eval_on_selector("#addFood", "e => e.textContent") == "Not saved",
          p.eval_on_selector("#addFood", "e => e.textContent"))
    check("and nothing failed got in", "FAIL-ONE" not in on_phone() and "FAIL-TWO" not in on_phone())
    native["fail_set"] = 0            # storage works again; nobody taps anything
    p.wait_for_timeout(5800)
    check("the log is sent again until native storage takes it",
          "FAIL-ONE" in on_phone() and "FAIL-TWO" in on_phone(), on_phone()[-120:])
    check("and the bar comes down by itself", not p.evaluate(BAR_UP))
    add_food(p, 113, "AFTER-FAIL"); p.wait_for_timeout(500)
    check("then adding says so again", p.locator(".added-flash").count() == 1 and "AFTER-FAIL" in on_phone())
    allerrs += errs; ctx.close()
    ctx, p, errs = open_app(b)
    macros(p); v = p.evaluate(VIEW)
    check("every food from the failing stretch survives a restart",
          all(x in v for x in ("FAIL-ONE", "FAIL-TWO", "AFTER-FAIL")), v[:240])
    allerrs += errs; ctx.close()

    # ---- 4. the log cannot be read ----------------------------------------
    native["prefs"]["CapacitorStorage." + KEY] = json.dumps(fixture("KEEP-ME"))
    before = on_phone()
    native["fail_get"] = True; native["calls"] = []
    ctx, p, errs = open_app(b)
    check("a log that cannot be read puts the bar up", p.evaluate(BAR_UP))
    check("and says the log could not be opened",
          "could not be opened" in p.inner_text("#saveLabel"), p.inner_text("#saveLabel"))
    add_food(p, 999, "OVERWRITE"); p.wait_for_timeout(500)
    check("adding does not claim success", p.locator(".added-flash").count() == 0)
    check("nothing is written over the log it could not read",
          on_phone() == before and ("Preferences", "set") not in native["calls"], str(native["calls"]))
    allerrs += errs; ctx.close()
    native["fail_get"] = False
    ctx, p, errs = open_app(b)
    macros(p)
    check("once it can be read, the log is all there", "KEEP-ME" in p.evaluate(VIEW)
          and "OVERWRITE" not in p.evaluate(VIEW), p.evaluate(VIEW)[:200])
    check("and the bar is down", not p.evaluate(BAR_UP))
    allerrs += errs; ctx.close()

    # ---- 5. a slow read: taps before the log arrives -----------------------
    native["prefs"]["CapacitorStorage." + KEY] = json.dumps(fixture("SLOW-ROW"))
    native["calls"] = []
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.expose_function("__native", bridge)
    ctx.add_init_script(BRIDGE % 1500)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE); p.wait_for_timeout(150)
    for t in ("gym", "macros", "pantry", "macros"):
        try:
            p.click('.tabs button[data-tab="%s"]' % t, timeout=300)
        except Exception:
            pass
    p.evaluate("() => { window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('pageshow')); }")
    # Settings sits in the header from the first paint, and choosing a look
    # saves at once: a real way to save before the log has arrived.
    p.click("#setBtn", timeout=500); p.wait_for_timeout(150)
    p.click('[data-pick-theme="dark"]', timeout=500); p.wait_for_timeout(150)
    p.click("#setDone", timeout=500)
    check("an early tap that saves really happened before the log arrived",
          "SLOW-ROW" not in p.evaluate("() => document.body.innerText")
          and p.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark",
          str(native["calls"]))
    check("nothing is written before the log has been read",
          ("Preferences", "set") not in native["calls"], str(native["calls"]))
    p.wait_for_timeout(2000)
    macros(p)
    check("the log arrives intact", "SLOW-ROW" in p.evaluate(VIEW) and "SLOW-ROW" in on_phone(),
          p.evaluate(VIEW)[:200])
    check("and no save bar from the early taps", not p.evaluate(BAR_UP))
    allerrs += errs; ctx.close()

    # ---- 6. a log left in the WebView's own storage -------------------------
    native["prefs"] = {}
    ctx, p, errs = open_app(b, webview_log=fixture("FROM-WEBVIEW"))
    macros(p)
    check("a log in the WebView's storage is carried across",
          "FROM-WEBVIEW" in p.evaluate(VIEW) and "FROM-WEBVIEW" in on_phone(), on_phone()[:80])
    allerrs += errs; ctx.close()

    # ---- 7. no service worker inside the app ------------------------------
    ctx, p, errs = open_app(b, settle=1500)
    regs = p.evaluate("async () => (await navigator.serviceWorker.getRegistrations()).length")
    check("no service worker inside the app, even over http(s)", regs == 0, "%d registered" % regs)
    allerrs += errs; ctx.close()
    # the same page on the web does register, or the check above proves nothing
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    p = ctx.new_page(); p.goto(BASE)
    ok = p.evaluate("async () => !!(await navigator.serviceWorker.ready).active")
    check("while the web build does register one", ok)
    ctx.close()

    # ---- 8. the label reader is still offered ------------------------------
    # The app is served from capacitor://localhost, not https; file:// is the
    # nearest a test can get to "not https". The web copy opened from disk has
    # no vendor/ beside it in practice, so it does not offer the reader.
    def label_button(p):
        p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(300)
        p.click("#panNew"); p.wait_for_timeout(300)
        return p.locator("#shotBtn").count() == 1
    native["prefs"] = {}
    ctx, p, errs = open_app(b, url=FILE)
    check("the app offers to read a label, though it is not on https", label_button(p))
    allerrs += errs; ctx.close()
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    p = ctx.new_page(); p.goto(FILE); p.wait_for_timeout(700)
    for t in ("Got it", "Start"):
        try: p.click("text=" + t, timeout=600)
        except Exception: pass
    check("while the web copy opened from disk does not", not label_button(p))
    ctx.close()

    # ---- 9. the web build never touches the bridge -------------------------
    native["calls"] = []
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.expose_function("__native", bridge)          # there, but nothing calls it
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(FILE); p.wait_for_timeout(700)
    for t in ("Got it", "Start"):
        try: p.click("text=" + t, timeout=600)
        except Exception: pass
    add_food(p, 444, "WEB-ROW"); p.wait_for_timeout(500)
    check("the web build keeps its log in localStorage",
          "WEB-ROW" in (p.evaluate("k => localStorage.getItem(k)", KEY) or ""))
    check("and never calls native storage", native["calls"] == [], str(native["calls"]))
    allerrs += errs; ctx.close()

    # ---- 10. a shell without the newer plugins ------------------------------
    native["prefs"] = {}; native["calls"] = []
    ctx, p, errs = open_app(b)
    add_food(p, 200, "OLD-SHELL"); p.wait_for_timeout(300)
    p.click('.tabs button[data-tab="gym"]'); gymways.rest(p); p.wait_for_timeout(200)
    check("a shell without the plugins is never called for them",
          {c[0] for c in native["calls"]} == {"Preferences"}, str(native["calls"][:6]))
    check("and offers no rest alert", p.locator("#restAlert").is_hidden())
    allerrs += errs; ctx.close()

    # ---- 11. rest alert, haptics, quick actions -----------------------------
    # The shell as of 1.2: the plugins answer here, in the page, and every call
    # is written down with whether `at` really is a Date, which is what iOS needs.
    PLUGINS = """(() => {
      window.__calls = []; window.__perm = 'granted';
      window.Capacitor = {
        isNativePlatform: () => true, getPlatform: () => 'ios',
        isPluginAvailable: () => true,
        nativePromise: (plugin, method, opts) => {
          opts = opts || {};
          if (plugin === 'Preferences')
            return window.__native(plugin, method, opts).then(r => {
              if (r && r.error) throw new Error(r.error); return r; });
          const n = (opts.notifications || [])[0], at = n && n.schedule && n.schedule.at;
          window.__calls.push({ plugin, method, opts: JSON.parse(JSON.stringify(opts)),
                                atIsDate: at instanceof Date, atIn: at ? (at - Date.now()) / 1000 : null });
          return Promise.resolve(method === 'requestPermissions' ? { display: window.__perm } : {});
        }
      };
    })();"""
    QUICK = "CapacitorStorage.mntl-quick-action"
    _bridge = bridge
    def bridge(plugin, method, opts):        # the suites above never remove anything
        if plugin == "Preferences" and method == "remove":
            native["prefs"].pop("CapacitorStorage." + opts.get("key", ""), None)
            return {}
        return _bridge(plugin, method, opts)

    def open_new_shell(b, width=402, fake_clock=False):
        ctx = b.new_context(viewport={"width": width, "height": 874}, has_touch=True, is_mobile=True)
        ctx.expose_function("__native", bridge)
        ctx.add_init_script(PLUGINS)
        p = ctx.new_page(); errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        if fake_clock: p.clock.install()
        p.goto(BASE); p.wait_for_timeout(900)
        for t in ("Got it", "Start"):
            try: p.click("text=" + t, timeout=500)
            except Exception: pass
        p.wait_for_timeout(200)
        return ctx, p, errs
    def calls(p, plugin, method=None):
        return p.evaluate("""([pl, m]) => window.__calls.filter(c => c.plugin === pl && (!m || c.method === m))""",
                          [plugin, method])
    def bar(p): return p.inner_text("#undobar") if p.locator("#undobar").is_visible() else ""
    def chip(p, s): return '[data-rest-alert="%d"]' % s
    def pressed(p): return p.evaluate(
        "() => [...document.querySelectorAll('#restAlert [aria-pressed=\"true\"]')].map(b => b.textContent)")

    # the rest alert
    native["prefs"] = {}
    ctx, p, errs = open_new_shell(b, fake_clock=True)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(200)
    check("no alert row until the rest clock runs", p.locator("#restAlert").is_hidden())
    gymways.rest(p); p.wait_for_timeout(200)     # one tap opens it and starts the count (b87)
    check("with the clock running the row shows, and starts on Off",
          p.locator("#restAlert").is_visible() and pressed(p) == ["Off"], str(pressed(p)))
    check("Off schedules nothing", not calls(p, "LocalNotifications", "schedule"))
    check("no permission is asked for until a time is picked", not calls(p, "LocalNotifications", "requestPermissions"))
    sizes = p.evaluate("() => [...document.querySelectorAll('#restAlert button')].map(b => { const r = b.getBoundingClientRect(); return [r.width, r.height]; })")
    check("every choice is at least 44px", len(sizes) == 5 and all(w >= 44 and h >= 44 for w, h in sizes), str(sizes))
    p.click(chip(p, 120)); p.wait_for_timeout(300)
    check("picking a time asks permission", len(calls(p, "LocalNotifications", "requestPermissions")) == 1)
    s = calls(p, "LocalNotifications", "schedule")
    n = s[-1]["opts"]["notifications"][0] if s else {}
    check("and schedules one notification", len(s) == 1, str(s)[:160])
    check("its time is a real Date, about two minutes off",
          bool(s) and s[-1]["atIsDate"] and 110 < s[-1]["atIn"] <= 120, str(s)[:160])
    check("it names a sound, or iOS plays nothing and a pocket feels nothing", n.get("sound") == "default", str(n)[:160])
    check("it stays quiet with the app open", n.get("foreground") is False, str(n)[:160])
    check("it says what is up", n.get("title") == "Rest is up: 2:00", str(n.get("title")))
    check("the pick shows and is said", pressed(p) == ["2:00"] and "buzz at 2:00" in bar(p), bar(p))
    check("the time is kept outside the log",
          native["prefs"].get("CapacitorStorage.mntl-rest-alert") == "120" and "rest-alert" not in on_phone()
          and "restAlert" not in on_phone())
    p.clock.fast_forward(121000); p.wait_for_timeout(1500)
    check("with the app open, it says rest is up", "Rest is up: 2:00" in bar(p), bar(p))
    up = [c for c in calls(p, "Haptics", "notification") if c["opts"].get("type") == "SUCCESS"]
    check("and buzzes once", len(up) == 1, str(up))
    p.clock.fast_forward(5000); p.wait_for_timeout(300)
    check("and not again", len([c for c in calls(p, "Haptics", "notification") if c["opts"].get("type") == "SUCCESS"]) == 1)
    p.click("#restBtn"); p.wait_for_timeout(200)
    check("stopping cancels the alert and folds the row",
          len(calls(p, "LocalNotifications", "cancel")) >= 2 and p.locator("#restAlert").is_hidden())
    p.click("#restBtn"); p.wait_for_timeout(200)
    check("the next rest uses the same time", pressed(p) == ["2:00"] and len(calls(p, "LocalNotifications", "schedule")) == 2)
    n_cancel = len(calls(p, "LocalNotifications", "cancel"))
    p.click('#ctxMain [data-gymway="rest"]'); p.wait_for_timeout(200)
    check("folding the rest box hides the row, and the alert stays set",
          p.locator("#restAlert").is_hidden() and len(calls(p, "LocalNotifications", "cancel")) == n_cancel)
    p.click('#ctxMain [data-gymway="rest"]'); p.wait_for_timeout(200)
    p.clock.fast_forward(150000); p.wait_for_timeout(300)
    late = len([c for c in calls(p, "Haptics", "notification") if c["opts"].get("type") == "SUCCESS"])
    check("coming back long after, it says so without a late buzz", "Rest is up" in bar(p) and late == 1, "%s %d" % (bar(p), late))
    before = len(calls(p, "LocalNotifications", "schedule"))
    p.click(chip(p, 60)); p.wait_for_timeout(300)
    check("a time already past is said, not scheduled", "next rest" in bar(p)
          and len(calls(p, "LocalNotifications", "schedule")) == before, bar(p))
    p.click(chip(p, 0)); p.wait_for_timeout(300)
    check("Off says so and is kept", "Rest alert off" in bar(p)
          and native["prefs"].get("CapacitorStorage.mntl-rest-alert") == "0", bar(p))
    p.click(chip(p, 180)); p.wait_for_timeout(300); allerrs += errs; ctx.close()
    ctx, p, errs = open_new_shell(b)
    check("a cold start cancels what the old clock left behind", len(calls(p, "LocalNotifications", "cancel")) == 1)
    p.click('.tabs button[data-tab="gym"]'); gymways.rest(p); p.wait_for_timeout(200)
    check("and remembers the time", pressed(p) == ["3:00"], str(pressed(p)))
    p.evaluate("() => { window.__perm = 'denied'; window.__calls = []; }")
    p.click(chip(p, 90)); p.wait_for_timeout(300)
    check("refused notifications are said plainly", "iPhone Settings" in bar(p), bar(p))
    check("and nothing is scheduled", not calls(p, "LocalNotifications", "schedule"))
    allerrs += errs; ctx.close()
    ctx, p, errs = open_new_shell(b, width=320)
    p.click('.tabs button[data-tab="gym"]'); gymways.rest(p); p.wait_for_timeout(200)
    over = p.evaluate("() => { const r = document.getElementById('restAlert'); return r.scrollWidth > r.clientWidth || document.documentElement.scrollWidth > innerWidth; }")
    check("the row fits a small phone", not over)
    allerrs += errs; ctx.close()

    # haptics
    native["prefs"] = {}
    ctx, p, errs = open_new_shell(b)
    p.evaluate("() => { window.__calls = []; }")
    add_food(p, 300, "BUZZ-ROW"); p.wait_for_timeout(300)
    h = calls(p, "Haptics")
    check("logging food is one light tap", len(h) == 1 and h[0]["method"] == "impact"
          and h[0]["opts"].get("style") == "LIGHT", str(h))
    p.evaluate("() => { window.__calls = []; }")
    native["fail_set"] = 99
    add_food(p, 301, "BUZZ-FAIL"); p.wait_for_timeout(400)
    add_food(p, 302, "BUZZ-FAIL2"); p.wait_for_timeout(400)
    e = [c for c in calls(p, "Haptics", "notification") if c["opts"].get("type") == "ERROR"]
    check("a failed save is one firm buzz, not one per try", len(e) == 1, str(e))
    native["fail_set"] = 0
    p.wait_for_timeout(5800)
    allerrs += errs; ctx.close()

    # quick actions
    plist = plistlib.load(open(os.path.join(ROOT, "ios", "App", "App", "Info.plist"), "rb"))
    acts = [x["UIApplicationShortcutItemType"] for x in plist.get("UIApplicationShortcutItems", [])]
    check("the icon offers the four actions, in order", acts == ["log-food", "ask-agent", "start-workout", "scan"], str(acts))
    swift = io.open(os.path.join(ROOT, "ios", "App", "App", "SceneDelegate.swift"), encoding="utf-8").read()
    check("the shell leaves the choice where the page reads it",
          '"%s"' % QUICK in swift and 'eventName: "mntlquickaction"' in swift)

    # the privacy manifest (shell 1.3). App Store Connect refuses an upload
    # whose code uses one of Apple's "required reason" APIs without a reason
    # in PrivacyInfo.xcprivacy (ITMS-91053).
    APP = os.path.join(ROOT, "ios", "App", "App")
    man_path = os.path.join(APP, "PrivacyInfo.xcprivacy")
    man = plistlib.load(open(man_path, "rb")) if os.path.exists(man_path) else {}
    pbx = io.open(os.path.join(ROOT, "ios", "App", "App.xcodeproj", "project.pbxproj"), encoding="utf-8").read()
    res_phase = re.search(r"/\* Resources \*/ = \{\s*isa = PBXResourcesBuildPhase;.*?files = \((.*?)\);", pbx, re.S)
    check("the shell has a privacy manifest that Xcode bundles", bool(man) and res_phase is not None
          and "PrivacyInfo.xcprivacy in Resources" in res_phase.group(1)
          and "path = PrivacyInfo.xcprivacy;" in pbx, man_path)
    declared = {t.get("NSPrivacyAccessedAPIType", "").replace("NSPrivacyAccessedAPICategory", ""):
                t.get("NSPrivacyAccessedAPITypeReasons", []) for t in man.get("NSPrivacyAccessedAPITypes", [])}
    # CA92.1: settings read and written by the app itself (Preferences, the
    # updater, SceneDelegate). C617.1: dates of files in the app's own
    # container (the filesystem library, the updater's bundles). E174.1: room
    # to write files (the updater checks free space before a download).
    check("it gives the reasons: its own settings, its own files' dates, room to write",
          declared == {"UserDefaults": ["CA92.1"], "FileTimestamp": ["C617.1"], "DiskSpace": ["E174.1"]},
          str(declared))
    col = man.get("NSPrivacyCollectedDataTypes", [])
    check("it declares what App Privacy says: Ask an agent's words, not linked, no tracking",
          man.get("NSPrivacyTracking") is False and man.get("NSPrivacyTrackingDomains") == []
          and len(col) == 1 and col[0].get("NSPrivacyCollectedDataType") == "NSPrivacyCollectedDataTypeOtherUserContent"
          and col[0].get("NSPrivacyCollectedDataTypeLinked") is False
          and col[0].get("NSPrivacyCollectedDataTypeTracking") is False
          and col[0].get("NSPrivacyCollectedDataTypePurposes") == ["NSPrivacyCollectedDataTypePurposeAppFunctionality"],
          str(col))
    # Every category the shell's and the plugins' own Swift uses must be
    # declared. The plugins are read from node_modules, which CI's verify job
    # does not install, so there only the shell's own code is read. The
    # filesystem plugin's library (ion-ios-filesystem) comes from Swift
    # Package Manager and is never on disk here: it reads file dates, which is
    # why FileTimestamp is declared above, and its plugin's own code says so.
    REASONED = {
        "UserDefaults": r"\b(NS)?UserDefaults\b",
        "FileTimestamp": r"creationDate|modificationDate|ModificationDate|getattrlist|\bf?l?stat\(",
        "SystemBootTime": r"systemUptime|mach_absolute_time|KERN_BOOTTIME",
        "DiskSpace": r"volumeAvailableCapacity|volumeTotalCapacity|systemFreeSize|\.systemSize\b|statv?fs\(",
        "ActiveKeyboards": r"activeInputModes",
    }
    deps = json.load(io.open(os.path.join(ROOT, "package.json"), encoding="utf-8"))["dependencies"]
    roots = [APP] + [os.path.join(ROOT, "node_modules", n, "ios") for n in deps
                     if os.path.isdir(os.path.join(ROOT, "node_modules", n, "ios"))]
    used = {}
    for r0 in roots:
        for dp, _, fs in os.walk(r0):
            if os.sep + "Tests" in dp or os.sep + "public" in dp: continue
            for f in fs:
                if not f.endswith((".swift", ".m", ".h")): continue
                src = io.open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                for cat, rx in REASONED.items():
                    if re.search(rx, src): used.setdefault(cat, set()).add(os.path.relpath(os.path.join(dp, f), ROOT))
    missing = sorted(c for c in used if c not in declared)
    check("every reasoned API the shell%s uses is declared" % (" and its plugins" if len(roots) > 1 else ""),
          not missing and "UserDefaults" in used,
          ("missing %s: %s" % (missing, sorted(used[missing[0]])[:2])) if missing
          else "%d plugin folders read; found %s" % (len(roots) - 1, sorted(used)))

    def active_tab(p): return p.evaluate("() => document.querySelector('.tabs button[aria-selected=\"true\"]').dataset.tab")
    native["prefs"] = {QUICK: "log-food"}
    ctx, p, errs = open_new_shell(b)
    check("Log food from a closed app opens Log numbers", active_tab(p) == "macros"
          and p.locator("#fCal").count() == 1, active_tab(p))
    check("and is only done once", QUICK not in native["prefs"])
    allerrs += errs; ctx.close()
    native["prefs"] = {QUICK: "ask-agent"}
    ctx, p, errs = open_new_shell(b)
    check("Ask an agent opens its box", active_tab(p) == "macros" and p.locator("#estText").count() == 1)
    allerrs += errs; ctx.close()
    native["prefs"] = {QUICK: "scan"}
    ctx, p, errs = open_new_shell(b)
    check("Scan a barcode opens the reader", active_tab(p) == "macros" and
          p.evaluate("() => /barcode/i.test(document.getElementById('view').innerText)"),
          p.evaluate(VIEW)[:120])
    allerrs += errs; ctx.close()
    native["prefs"] = {QUICK: "start-workout"}
    ctx, p, errs = open_new_shell(b)
    p.wait_for_timeout(200)
    check("Start workout opens the Gym tab", active_tab(p) == "gym", active_tab(p))
    check("and what it did is said", "Workout started" in bar(p) and p.locator("#startWorkout.wo-start").count() == 0, bar(p))
    # the app already open
    native["prefs"][QUICK] = "log-food"
    p.evaluate("() => window.dispatchEvent(new Event('mntlquickaction'))"); p.wait_for_timeout(300)
    check("from an app already running, it goes there too", active_tab(p) == "macros"
          and p.locator("#fCal").count() == 1 and QUICK not in native["prefs"], active_tab(p))
    native["prefs"][QUICK] = "start-workout"
    p.evaluate("() => { document.querySelector('.app').inert = true; window.dispatchEvent(new Event('mntlquickaction')); }")
    p.wait_for_timeout(300)
    check("nothing gets past a screen that holds the app", active_tab(p) == "macros" and QUICK not in native["prefs"], active_tab(p))
    allerrs += errs; ctx.close()

    # ---- 12. steps from Apple Health (shell 1.4) ------------------------------
    # The shell's own HealthSteps plugin, stood in for here in Python so what
    # Health holds survives a restart like the log does. It answers status,
    # connect and days the way HealthStepsPlugin.swift does: days only within
    # from..to, and only days with steps.
    HEALTH = {"days": {}, "fail": None, "calls": []}
    def health_bridge(plugin, method, opts):
        if plugin != "HealthSteps":
            return bridge(plugin, method, opts)
        HEALTH["calls"].append((method, dict(opts)))
        if method == "status": return {"available": True, "asked": False}
        if method == "connect": return {"asked": True}
        if method == "days":
            if HEALTH["fail"] == "not_asked": return {"error": "Apple Health has not been asked yet", "code": "not_asked"}
            if HEALTH["fail"]: return {"error": HEALTH["fail"]}
            return {"days": {k: v for k, v in HEALTH["days"].items() if opts["from"] <= k <= opts["to"]}}
        return {"error": method + " is not a HealthSteps method"}
    SHELL = """(() => {
      const plugins = %s;
      window.Capacitor = {
        isNativePlatform: () => true, getPlatform: () => 'ios',
        isPluginAvailable: (n) => plugins.includes(n),
        nativePromise: (plugin, method, opts) => window.__native(plugin, method, opts || {})
          .then(r => { if (r && r.error) throw Object.assign(new Error(r.error), { code: r.code }); return r; })
      };
    })();"""
    def open_shell(b, plugins, width=402):
        ctx = b.new_context(viewport={"width": width, "height": 874}, has_touch=True, is_mobile=True)
        ctx.expose_function("__native", health_bridge)
        ctx.add_init_script(SHELL % json.dumps(plugins))
        p = ctx.new_page(); errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.clock.install()
        p.goto(BASE); p.wait_for_timeout(900)
        for t in ("Got it", "Start"):
            try: p.click("text=" + t, timeout=500)
            except Exception: pass
        p.click('.tabs button[data-tab="cardio"]'); p.wait_for_timeout(300)
        return ctx, p, errs
    TD = datetime.date.today()
    def ago(n): return (TD - datetime.timedelta(days=n)).isoformat()
    def steps_log():
        f = fixture("Oats")
        f["cardioGoal"] = {"kind": "steps", "period": "week", "v": 70000}
        f["days"][ago(1)] = {"food": [], "lifts": [], "updated": 7, "steps": 7400, "stepsAt": 1}   # typed in b92
        return f
    def saved(): return json.loads(on_phone())
    def sday(k): return saved()["days"].get(k, {})
    def days_calls(): return [c for c in HEALTH["calls"] if c[0] == "days"]
    def later(p, secs=61):
        # Health is read at most once a minute, and again on coming back.
        p.clock.fast_forward(secs * 1000)
        p.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))"); p.wait_for_timeout(300)
    def sizes(p, sel):
        return p.evaluate("(s) => [...document.querySelectorAll(s)].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })", sel)
    PH = ["Preferences", "HealthSteps"]

    # the web, and a 1.3 shell, keep typing
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.add_init_script("localStorage.setItem(%r, %s)" % (KEY, json.dumps(json.dumps(steps_log()))))
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE); p.wait_for_timeout(900)
    p.click('.tabs button[data-tab="cardio"]'); p.wait_for_timeout(300)
    check("health: the web offers no Apple Health, and still types steps",
          p.locator("#hsCard").count() == 0 and p.locator("#stepsOpen").count() == 1)
    p.click("#stepsOpen"); p.wait_for_timeout(250)
    check("health: the web's steps box has no Apple Health buttons",
          p.locator("#hsFill, #hsStop, #stepsHealth").count() == 0)
    allerrs += errs; ctx.close()

    native["prefs"] = {"CapacitorStorage." + KEY: json.dumps(steps_log())}
    HEALTH["calls"] = []
    ctx, p, errs = open_shell(b, ["Preferences", "Filesystem"])
    check("health: a 1.3 shell offers no Apple Health and is never asked",
          p.locator("#hsCard").count() == 0 and not HEALTH["calls"] and p.locator("#stepsOpen").count() == 1,
          str(HEALTH["calls"][:2]))
    allerrs += errs; ctx.close()

    # shell 1.4: the card, and Not now
    ctx, p, errs = open_shell(b, PH)
    check("health: a 1.4 shell offers the card while the goal counts steps",
          p.locator("#hsCard").is_visible() and "Connect Apple Health" in p.inner_text("#hsCard"))
    check("health: nothing is read before the person says yes", not days_calls(), str(HEALTH["calls"]))
    sz = sizes(p, "#hsCard button")
    check("health: the card's buttons are at least 44px", len(sz) == 2 and all(w >= 44 and h >= 44 for w, h in sz), str(sz))
    p.click("#hsLater"); p.wait_for_timeout(250)
    check("health: Not now puts the card away, says so, and is kept",
          p.locator("#hsCard").count() == 0 and "Not now" in bar(p) and saved().get("healthSteps", {}).get("on") is False, bar(p))
    p.click("#undoBtn"); p.wait_for_timeout(250)
    check("health: Undo brings the card back", p.locator("#hsCard").count() == 1 and "healthSteps" not in saved())
    p.click("#hsLater"); p.wait_for_timeout(250)
    allerrs += errs; ctx.close()
    ctx, p, errs = open_shell(b, PH)
    check("health: after Not now, a restart shows no card", p.locator("#hsCard").count() == 0)
    p.click("#stepsOpen"); p.wait_for_timeout(250)
    check("health: the steps box still offers Apple Health", p.locator("#hsFill").is_visible())
    allerrs += errs; ctx.close()
    for w in (320,):
        native["prefs"] = {"CapacitorStorage." + KEY: json.dumps(steps_log())}
        ctx, p, errs = open_shell(b, PH, width=w)
        sz = sizes(p, "#hsCard button")
        check("health: at %dpx the card's buttons stay 44px and on screen" % w,
              len(sz) == 2 and all(h >= 44 and 44 <= wd <= w for wd, h in sz)
              and p.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), str(sz))
        allerrs += errs; ctx.close()

    # Connect: the first read
    native["prefs"] = {"CapacitorStorage." + KEY: json.dumps(steps_log())}
    HEALTH["calls"] = []
    HEALTH["days"] = {ago(0): 6000, ago(1): 6517, ago(2): 7034, ago(10): 9000, ago(80): 5000}
    ctx, p, errs = open_shell(b, PH)
    p.click("#hsConnect"); p.wait_for_timeout(500)
    dc = days_calls()
    ws = TD - datetime.timedelta(days=(TD.weekday() + 1) % 7)            # Sunday-first week
    check("health: Connect asks iOS once, then reads eight weeks up to today",
          [c[0] for c in HEALTH["calls"]].count("connect") == 1 and len(dc) == 1
          and dc[0][1] == {"from": (ws - datetime.timedelta(days=49)).isoformat(), "to": TD.isoformat()}, str(dc))
    log = saved()
    check("health: today's steps fill in, marked as Apple Health's",
          log["days"][T].get("steps") == 6000 and log["days"][T].get("stepsBy") == "health", str(log["days"][T]))
    check("health: a typed day is never written over", log["days"][ago(1)].get("steps") == 7400
          and "stepsBy" not in log["days"][ago(1)], str(log["days"][ago(1)]))
    check("health: earlier days fill in too, and nothing outside the range",
          sday(ago(2)).get("steps") == 7034 and sday(ago(10)).get("steps") == 9000 and ago(80) not in log["days"])
    check("health: filling never touches a day's updated, so a restore still wins",
          log["days"][T]["updated"] == 1 and log["days"][ago(2)]["updated"] == 0, str(log["days"][T]))
    check("health: it says what it did, and the card is gone",
          bar(p) == "Apple Health filled in steps for 3 days" and p.locator("#hsCard").count() == 0
          and log.get("healthSteps", {}).get("on") is True, bar(p))
    check("health: the lap says where today's steps came from",
          "Today’s steps come from Apple Health" in p.inner_text(".cardio-goal"), p.inner_text(".cardio-goal")[-160:])

    # Health keeps counting; a typed number still stands
    HEALTH["days"][ago(0)] = 6800; HEALTH["days"][ago(1)] = 8000
    n0 = len(days_calls())
    p.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))"); p.wait_for_timeout(300)
    check("health: coming back within a minute does not read again", len(days_calls()) == n0)
    later(p)
    check("health: coming back later follows Health's count, typed days aside",
          sday(T).get("steps") == 6800 and sday(ago(1)).get("steps") == 7400, str(sday(T)))
    wk = sum(v.get("steps", 0) for k, v in saved()["days"].items() if ws.isoformat() <= k <= T)
    check("health: and the lap adds it into the week", p.inner_text(".cardio-goal .cg-num b") == "{:,}".format(wk),
          "%s vs %s" % (p.inner_text(".cardio-goal .cg-num"), wk))

    # The steps box on a Health day
    p.click("#stepsOpen"); p.wait_for_timeout(250)
    check("health: a Health day's box starts empty and says Health's number",
          p.input_value("#stepsIn") == "" and "Apple Health says 6,800" in p.inner_text("#stepsSheet")
          and p.locator("#stepsClear").count() == 0, p.inner_text("#stepsSheet"))
    # A read that lands while something is half typed waits.
    p.fill("#stepsIn", "12"); HEALTH["days"][ago(0)] = 6900
    later(p)
    check("health: a read never redraws over a half-typed number",
          p.locator("#stepsSheet").is_visible() and p.input_value("#stepsIn") == "12" and sday(T).get("steps") == 6900)
    p.fill("#stepsIn", "9,100"); p.click("#stepsSave"); p.wait_for_timeout(250)
    check("health: typing replaces it, says so, and is the person's own",
          sday(T).get("steps") == 9100 and "stepsBy" not in sday(T)
          and "Steps for today: 9,100 (was 6,900)" in bar(p), bar(p))
    HEALTH["days"][ago(0)] = 7000
    later(p)
    check("health: Apple Health leaves a typed day alone", sday(T).get("steps") == 9100)
    check("health: and the lap says why", "You typed today’s steps" in p.inner_text(".cardio-goal"))
    p.click("#stepsOpen"); p.wait_for_timeout(250)
    check("health: the box offers Health's own number back", p.locator("#stepsHealth").is_visible()
          and "7,000" in p.inner_text("#stepsHealth"), p.inner_text("#stepsSheet"))
    p.click("#stepsHealth"); p.wait_for_timeout(250)
    check("health: Use Apple Health's puts it back, and says so",
          sday(T).get("steps") == 7000 and sday(T).get("stepsBy") == "health"
          and "7,000 from Apple Health (was 9,100)" in bar(p), bar(p))
    p.click("#undoBtn"); p.wait_for_timeout(250)
    check("health: Undo puts the typed number back as typed", sday(T).get("steps") == 9100 and "stepsBy" not in sday(T))

    # A locked phone: nothing changes, nothing breaks
    HEALTH["fail"] = "locked"; HEALTH["days"][ago(2)] = 7777
    later(p)
    check("health: a read that fails changes nothing", sday(ago(2)).get("steps") == 7034 and not errs, str(errs[:1]))
    HEALTH["fail"] = None

    # A backup brings back the day's food, never the phone's Health answer
    backup = {"days": {ago(2): {"food": [{"id": "fb", "cal": 300, "pro": 20, "note": "Restored"}], "lifts": [], "updated": 5}},
              "healthSteps": {"on": False, "at": 1}, "moves": {}, "goal": G, "pantry": [], "v": 1}
    p.click("#backupBtn"); p.wait_for_timeout(300)
    p.evaluate("t => { document.getElementById('backupText').value = t; }", json.dumps(backup))
    p.click("#restoreBtn"); p.wait_for_timeout(500)
    check("health: a restored day comes back over one Health filled",
          (sday(ago(2)).get("food") or [{}])[0].get("note") == "Restored", str(sday(ago(2)))[:120])
    check("health: and the phone's own answer stays", saved().get("healthSteps", {}).get("on") is True)
    later(p)
    check("health: then its steps fill in again", sday(ago(2)).get("steps") == 7777 and sday(ago(2)).get("stepsBy") == "health")

    # Stop, and Undo
    if p.locator("#sheet").is_visible(): p.click("#closeSheet"); p.wait_for_timeout(200)
    p.click("#stepsOpen"); p.wait_for_timeout(250)
    p.click("#hsStop"); p.wait_for_timeout(250)
    check("health: Stop says so and is kept; the numbers so far stay",
          saved()["healthSteps"]["on"] is False and "Apple Health steps off" in bar(p) and sday(ago(2)).get("steps") == 7777, bar(p))
    n0 = len(days_calls()); HEALTH["days"][ago(2)] = 8888
    later(p)
    check("health: once stopped, Health is not read", len(days_calls()) == n0 and sday(ago(2)).get("steps") == 7777)
    p.click("#stepsOpen"); p.wait_for_timeout(250)
    check("health: once stopped, the box offers it again", p.locator("#hsFill").is_visible() and p.locator("#hsStop").count() == 0)
    p.click("#stepsCancel"); p.wait_for_timeout(200)
    allerrs += errs; ctx.close()

    # Connected, a restart reads on opening and shows no card
    log = saved(); log["healthSteps"] = {"on": True, "at": 1}
    native["prefs"]["CapacitorStorage." + KEY] = json.dumps(log)
    n0 = len(days_calls())
    ctx, p, errs = open_shell(b, PH)
    check("health: connected, the app reads Health on opening, with no card",
          len(days_calls()) == n0 + 1 and p.locator("#hsCard").count() == 0 and sday(ago(2)).get("steps") == 8888)
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(300)
    allerrs += errs; ctx.close()

    # A log that says yes, on a phone iOS never asked (brought over in a
    # backup of the phone itself): the card asks again.
    log = saved(); log["healthSteps"] = {"on": True, "at": 1}
    native["prefs"]["CapacitorStorage." + KEY] = json.dumps(log)
    HEALTH["fail"] = "not_asked"
    ctx, p, errs = open_shell(b, PH)
    p.wait_for_timeout(300)
    check("health: a phone iOS never asked gets the card again",
          p.locator("#hsCard").is_visible() and "healthSteps" not in saved())
    HEALTH["fail"] = None
    allerrs += errs; ctx.close()

    # Health with nothing in it (or a no): the lap says where the switch is
    native["prefs"] = {"CapacitorStorage." + KEY: json.dumps(steps_log())}
    HEALTH["days"] = {}
    ctx, p, errs = open_shell(b, PH)
    p.click("#hsConnect"); p.wait_for_timeout(500)
    check("health: nothing from Health says so, and where to look",
          bar(p) == "No steps from Apple Health yet" and "Data Access & Devices" in p.inner_text(".cardio-goal"), bar(p))
    allerrs += errs; ctx.close()

    # the shell itself: read only, steps only, and honest about it
    info = plistlib.load(open(os.path.join(APP, "Info.plist"), "rb"))
    why = info.get("NSHealthShareUsageDescription", "")
    check("health: the shell says why it reads Health, and that it never writes",
          "step" in why and "never writes" in why, why)
    # Apple's upload wants the writing purpose string too, for any app with
    # the HealthKit entitlement, even one that never writes (Build for
    # TestFlight #11 was refused for it). Its words say so; iOS never shows
    # them, since nothing asks to write.
    upd = info.get("NSHealthUpdateUsageDescription", "")
    check("health: the writing purpose string Apple requires is there, and says nothing is written",
          "never writes" in upd and "step" in upd, upd)

    # Every purpose string Apple's upload asks for, before the upload asks.
    # App Store Connect refuses a build ("Missing purpose string in
    # Info.plist") whose code or entitlements reach protected data without
    # the matching key, and that is only found at the end of a TestFlight run.
    # So: what the shell's Swift, the plugins' (where node_modules is
    # installed), the entitlements and the page use, each against the keys it
    # needs. A new permission adds a row here.
    NEEDS = [
        (r"import HealthKit|\bHK(HealthStore|QuantityType)\b", ["NSHealthShareUsageDescription", "NSHealthUpdateUsageDescription"]),
        (r"AVCaptureDevice|getUserMedia\(\{\s*video", ["NSCameraUsageDescription"]),
        (r"getUserMedia\(\{[^}]*audio|requestRecordPermission|AVAudioRecorder", ["NSMicrophoneUsageDescription"]),
        (r"\bPHPhotoLibrary\b|\bPHAsset\b", ["NSPhotoLibraryUsageDescription"]),
        (r"\bCLLocationManager\b", ["NSLocationWhenInUseUsageDescription"]),
        (r"\bCNContactStore\b", ["NSContactsUsageDescription"]),
        (r"\bCMPedometer\b|\bCMMotionActivityManager\b", ["NSMotionUsageDescription"]),
        (r"\bCBCentralManager\b|\bCBPeripheralManager\b", ["NSBluetoothAlwaysUsageDescription"]),
        (r"\bEKEventStore\b", ["NSCalendarsFullAccessUsageDescription"]),
        (r"\bLAContext\b", ["NSFaceIDUsageDescription"]),
        (r"\bATTrackingManager\b", ["NSUserTrackingUsageDescription"]),
    ]
    srcs = {"mntl-dt.html": io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()}
    for r0 in roots:
        for dp, _, fs in os.walk(r0):
            if os.sep + "Tests" in dp or os.sep + "public" in dp: continue
            for f in fs:
                if f.endswith((".swift", ".m", ".h")):
                    srcs[os.path.relpath(os.path.join(dp, f), ROOT)] = io.open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
    srcs["App.entitlements"] = "import HealthKit" if ent_hk(APP) else ""
    needed = {}
    for rx, keys in NEEDS:
        for name, src in srcs.items():
            if re.search(rx, src):
                for k in keys: needed.setdefault(k, name)
    missing = sorted(k for k in needed if not str(info.get(k, "")).strip())
    check("every purpose string Apple's upload asks for is in Info.plist",
          not missing and "NSHealthUpdateUsageDescription" in needed and "NSCameraUsageDescription" in needed,
          ("missing %s (for %s)" % (missing, [needed[k] for k in missing])) if missing else "needs " + ", ".join(sorted(needed)))
    ent = plistlib.load(open(os.path.join(APP, "App.entitlements"), "rb"))
    check("health: the shell has the HealthKit entitlement, and no clinical records",
          ent == {"com.apple.developer.healthkit": True, "com.apple.developer.healthkit.access": []}, str(ent))
    check("health: both configurations sign with it",
          pbx.count("CODE_SIGN_ENTITLEMENTS = App/App.entitlements;") == 2)
    src_phase = re.search(r"/\* Sources \*/ = \{\s*isa = PBXSourcesBuildPhase;.*?files = \((.*?)\);", pbx, re.S).group(1)
    check("health: Xcode compiles the plugin and the view controller that registers it",
          "HealthStepsPlugin.swift in Sources" in src_phase and "MainViewController.swift in Sources" in src_phase)
    hs = io.open(os.path.join(APP, "HealthStepsPlugin.swift"), encoding="utf-8").read()
    mvc = io.open(os.path.join(APP, "MainViewController.swift"), encoding="utf-8").read()
    check("health: the plugin is the one the page asks for, and it is registered",
          'jsName = "HealthSteps"' in hs and "registerPluginInstance(HealthStepsPlugin())" in mvc
          and "MainViewController()" in swift and 'customClass="MainViewController"' in
          io.open(os.path.join(APP, "Base.lproj", "Main.storyboard"), encoding="utf-8").read())
    check("health: it asks to read steps and to share nothing",
          "requestAuthorization(toShare: [], read: [steps])" in hs
          and set(re.findall(r"HKQuantityType\(\.(\w+)\)", hs)) == {"stepCount"}
          and not re.search(r"\.save\(|HKWorkoutType|HKCategoryType|toShare: \[[^\]]", hs))
    pol = io.open(os.path.join(ROOT, "privacy.html"), encoding="utf-8").read()
    check("health: the Privacy Policy says what is read and that it stays on the phone",
          "reads your daily step count" in pol and "does not connect to Apple Health" not in pol)

    check("no page errors", not allerrs, str(allerrs[:3]))
    b.close()

srv.shutdown()
for s, n, det in res: print("%-6s %-58s %s" % (s, n, " / ".join(l.strip() for l in str(det).splitlines() if l.strip())[:100]))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
