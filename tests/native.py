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

    check("no page errors", not allerrs, str(allerrs[:3]))
    b.close()

srv.shutdown()
for s, n, det in res: print("%-6s %-58s %s" % (s, n, " / ".join(l.strip() for l in str(det).splitlines() if l.strip())[:100]))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
