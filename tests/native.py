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

What it cannot show: that UserDefaults survives a phone restart. That is
Apple's to keep, and is on the list Tommy runs on his iPhone (docs/ios.md).
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, json, datetime, threading, functools

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

    check("no page errors", not allerrs, str(allerrs[:3]))
    b.close()

srv.shutdown()
for s, n, det in res: print("%-6s %-58s %s" % (s, n, " / ".join(l.strip() for l in str(det).splitlines() if l.strip())[:100]))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
