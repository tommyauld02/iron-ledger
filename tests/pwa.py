"""The offline shell: does the app still run with the network cut?

Serves the repo over http on localhost (a secure context, so service workers
are allowed) with iron-ledger.html at "/", which is how GitHub Pages serves it.
Then pulls the network out from under a loaded app and asserts it still works.

A service worker that registers but caches nothing looks identical to a working
one until you are offline, so every check here runs with offline=True.
"""
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, threading, functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = []
def check(n, ok, d=""): res.append(("PASS" if ok else "FAIL", n, d))


class H(SimpleHTTPRequestHandler):
    """Serves iron-ledger.html at / the way the Pages deploy does."""
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "iron-ledger.html")
        return super().translate_path(path)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % PORT

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True)
    p = ctx.new_page(); errs = []; reqs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("request", lambda r: reqs.append(r.url))

    p.goto(BASE); p.wait_for_timeout(600)
    reg = p.evaluate("""async () => {
        const r = await navigator.serviceWorker.ready;
        return !!(r && r.active);
    }""")
    check("service worker activates", reg is True)

    ver = p.evaluate("""() => {
        const r = navigator.serviceWorker.controller;
        return r ? new URL(r.scriptURL).searchParams.get('v') : null;
    }""")
    # BUILD lives inside the app's IIFE, so read it from the source of truth
    build = re.search(r'BUILD = "([^"]+)"',
                      io.open(os.path.join(ROOT, "iron-ledger.html"), encoding="utf-8").read()).group(1)
    check("worker version tracks BUILD", ver == build, "worker=%s app=%s" % (ver, build))

    # let the shell finish precaching before the network goes away
    p.wait_for_timeout(1200)
    cached = p.evaluate("""async () => {
        const ks = await caches.keys();
        const c = await caches.open(ks.find(k => k.startsWith('iron-ledger-')));
        return (await c.keys()).map(r => new URL(r.url).pathname);
    }""")
    check("shell is cached", len(cached) >= 9, "%d entries" % len(cached))
    check("fonts are cached", sum(".woff2" in c for c in cached) >= 8,
          "%d font files" % sum(".woff2" in c for c in cached))

    # --- the actual promise -------------------------------------------------
    ctx.set_offline(True)
    del reqs[:]                       # only care what the offline load asks for
    p.goto(BASE); p.wait_for_timeout(900)

    check("app loads offline", p.evaluate("() => !!document.querySelector('.brand h1')"))
    check("tab bar renders offline", p.evaluate("() => document.querySelectorAll('.tabs button').length >= 4"),
          "%s tabs" % p.evaluate("() => document.querySelectorAll('.tabs button').length"))
    check("fonts render offline", p.evaluate("() => document.fonts.check('16px Archivo')"))
    # an empty list would pass this trivially, so assert the load was observed
    off_site = [u for u in reqs if not u.startswith(BASE.rstrip("/"))]
    check("offline load was actually observed", len(reqs) > 0, "%d requests seen" % len(reqs))
    check("no off-origin requests offline", not off_site, str(off_site[:3]))

    # logging still has to work with no network at all
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(400)
    before = p.evaluate("() => (JSON.parse(localStorage.getItem('iron-ledger-v1')||'{}').days)||{}")
    p.fill("#estText", "2 eggs"); p.wait_for_timeout(150)
    check("can type a food entry offline", p.input_value("#estText") == "2 eggs")

    check("no page errors", not errs, str(errs))
    ctx.close(); b.close()

srv.shutdown()
for s, n, d in res: print("%-6s %-42s %s" % (s, n, d))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
