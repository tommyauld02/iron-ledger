"""The offline shell: does the app still run with the network cut?

Serves the repo over http on localhost (a secure context, so service workers
are allowed) with mntl-dt.html at "/", which is how GitHub Pages serves it.
Then pulls the network out from under a loaded app and asserts it still works.

A service worker that registers but caches nothing looks identical to a working
one until you are offline, so every check here runs with offline=True.
"""
import fakeai
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, threading, functools

# The Macros tab now opens on the fill-in table; the plain-words box is behind
# "Or just describe it in words". This suite is about what the resolver makes
# of a phrase, not about how it was entered, so it opens the box and types.
def words(p):
    # the words box sits folded behind Ask an agent until asked for
    if p.locator('[data-logway="estimate"][aria-expanded="false"]').count():
        p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = []
def check(n, ok, d=""): res.append(("PASS" if ok else "FAIL", n, d))


class H(SimpleHTTPRequestHandler):
    """Serves mntl-dt.html at / the way the Pages deploy does."""
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "mntl-dt.html")
        return super().translate_path(path)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % PORT

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True)
    ctx.add_init_script(fakeai.RELAY_SCRIPT)
    ctx.add_init_script(fakeai.AI_SCRIPT)
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
                      io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()).group(1)
    check("worker version tracks BUILD", ver == build, "worker=%s app=%s" % (ver, build))

    # let the shell finish precaching before the network goes away
    p.wait_for_timeout(1200)
    cached = p.evaluate("""async () => {
        const ks = await caches.keys();
        const c = await caches.open(ks.find(k => k.startsWith('iron-ledger-') && k !== 'iron-ledger-data'));
        return (await c.keys()).map(r => new URL(r.url).pathname);
    }""")
    check("shell is cached", len(cached) >= 9, "%d entries" % len(cached))
    check("fonts are cached", sum(".woff2" in c for c in cached) >= 8,
          "%d font files" % sum(".woff2" in c for c in cached))
    check("grocery brands are not downloaded at install", not any("/vendor/usda/brands-" in c for c in cached))
    # the food library and the menus went when the food finder replaced them (b63)
    check("the old food lists are not cached any more",
          not any(c.endswith("/vendor/usda/foods.js") or c.endswith("/vendor/menus/menus.js") for c in cached), str(cached))

    # Grocery brands are 9 MB, downloaded when asked for, and kept in a store
    # of their own: an update clears the old build's cache, and must not make
    # every phone download them again.
    DATA_KEYS = """async () => {
        const c = await caches.open('iron-ledger-data');
        return (await c.keys()).map(r => new URL(r.url).pathname);
    }"""
    # A pantry food, and the app pointed at the stand-in relay (tests/fakeai.py),
    # so the offline pass below can show
    # what still answers with no signal and what says it can't.
    p.evaluate("""() => {
        const s = JSON.parse(localStorage.getItem('iron-ledger-v1') || '{}');
        s.pantry = [{id: 'p1', name: 'costco protein coffee', serveQty: 1, serveUnit: 'bottle', serveG: null,
                     sCal: 130, sPro: 30, aliases: []}];
        localStorage.setItem('iron-ledger-v1', JSON.stringify(s));
    }""")
    p.reload(); p.wait_for_timeout(800)
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(400)
    p.click('[data-scanway]'); p.wait_for_timeout(400)      # Scan, in the bottom bar
    if p.locator("#scanBrands").count():
        p.click("#scanBrands")
        try: p.wait_for_selector("#scanType", timeout=40000)
        except Exception: pass
    p.wait_for_timeout(500)
    if p.locator("#scanClose").count(): p.click("#scanClose"); p.wait_for_timeout(200)
    data = p.evaluate(DATA_KEYS)
    check("grocery brands are kept in a store of their own once downloaded",
          any("/vendor/usda/brands-" in x for x in data), str(data))
    p.evaluate("""async () => {
        const r = await navigator.serviceWorker.register('sw.js?v=next-build');
        const w = r.installing || r.waiting || r.active;
        if (w.state !== 'activated') await new Promise(res => w.addEventListener('statechange', () => { if (w.state === 'activated') res(); }));
    }""")
    p.wait_for_timeout(500)
    keys = p.evaluate("async () => await caches.keys()")
    data = p.evaluate(DATA_KEYS)
    check("an update clears the old build's cache but keeps the grocery brands",
          ("iron-ledger-" + build) not in keys and "iron-ledger-next-build" in keys
          and any("/vendor/usda/brands-" in x for x in data), "%s / %s" % (keys, data))

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
    words(p); p.fill("#estText", "2 eggs"); p.wait_for_timeout(150)
    check("can type a food entry offline", p.input_value("#estText") == "2 eggs")
    # Your pantry still answers with no connection; the food finder says it
    # needs one, and the food waits as a placeholder instead of vanishing.
    p.fill("#estText", "1 costco protein coffee"); p.click("#runEst"); p.wait_for_timeout(800)
    check("your pantry answers offline",
          p.locator(".rev-item").count() == 1 and "your pantry" in p.inner_text(".review"),
          p.inner_text("#view")[:160])
    p.click("#discardEst"); p.wait_for_timeout(300)
    words(p); p.fill("#estText", "2 eggs"); p.click("#runEst"); p.wait_for_timeout(1200)
    check("the food finder says it needs a connection, and the food waits",
          # which of the two depends on whether the phone knows it is offline
          ("No connection" in p.inner_text(".review") or "reach the food finder" in p.inner_text(".review"))
          and "NEEDS NUMBERS" in p.inner_text(".review").upper(),
          p.inner_text(".review")[-240:] if p.locator(".review").count() else p.inner_text("#view")[:200])
    p.click("#discardEst"); p.wait_for_timeout(300)

    # With the brands in, the sheet asks for the camera, and the answer redraws
    # it — wiping a number typed before the answer lands. This browser has no
    # camera, so the answer is a refusal some 400 ms later, which a fixed sleep
    # here used to outlast only by luck (darkcheck lost its card to it on
    # 2026-10-17). So type once the answer is on the sheet: a message drawn,
    # and no camera view still waiting for its stream.
    p.click('[data-scanway]')
    if p.locator("#scanType").count():
        try: p.wait_for_function("""()=>{const m=document.getElementById('scanMsg'), v=document.getElementById('scanVideo');
            return !!(m && m.textContent.trim()) && (!v || !!v.srcObject);}""", timeout=10000)
        except Exception: pass      # still waiting: type anyway, and the card says whether it worked
        p.fill("#scanType", "894700010038"); p.click("#scanGo")
    try: p.wait_for_selector(".scan-card", timeout=5000)
    except Exception: pass
    check("grocery brands answer a barcode offline",
          p.locator(".scan-card").count() > 0 and "CHOBANI" in p.inner_text(".scan-card").upper(),
          p.inner_text("#scanSheet")[:160] if p.locator("#scanSheet").count() else "no scanner")

    check("no page errors", not errs, str(errs))
    ctx.close(); b.close()

srv.shutdown()
for s, n, d in res: print("%-6s %-42s %s" % (s, n, d))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
