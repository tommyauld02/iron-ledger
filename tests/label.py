"""Reading a nutrition panel on the phone, where there is no Claude.

Inside the Claude viewer the sample capability reads the panel (photo2 covers
that path). On the hosted copy there is no capability at all, so the panel is
read on the device with Tesseract, fetched lazily on first use.

Two things this has to keep proving:

  - the calorie figure is found by how it is *printed*, not by reading order.
    OCR splits the big "190" into separate digit-words and scatters them
    through the text; a plain text scan pulled 609 out of a blurred panel,
    which is the kind of confident wrong number rule 3 exists to prevent.
  - nothing it fails to read is guessed. A panel carries plenty of numbers
    larger than the calories — sodium in mg, carbs, every % daily value — so
    "take the biggest number" would log sodium.
"""
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, datetime, threading, functools, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))


class H(SimpleHTTPRequestHandler):
    def translate_path(self, p0):
        p = p0.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "iron-ledger.html")
        return super().translate_path(p0)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % PORT

T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2400}, "pro": {"dir": "+", "v": 180}}
STORE = {"days": {T: {"food": [], "lifts": [], "updated": 1, "goal": G}}, "moves": None,
         "goal": G, "region": "United States", "pantry": [], "v": 1}

VENDOR = os.path.join(ROOT, "vendor", "tesseract")
need = ["tesseract.min.js", "worker.min.js", "tesseract-core-simd-lstm.wasm.js",
        "eng.traineddata.gz"]
missing = [f for f in need if not os.path.exists(os.path.join(VENDOR, f))]
if missing:
    print("SKIPPED  the label reader needs vendor/tesseract/")
    print("         missing: %s" % ", ".join(missing))
    print("         see CLAUDE.md — they are downloaded, not written by hand")
    raise SystemExit(77)


def settle(p, limit=40):
    """OCR takes a moment; wait for the form rather than a fixed sleep."""
    for _ in range(limit):
        p.wait_for_timeout(500)
        if p.evaluate("() => !document.querySelector('.working')") and \
           p.evaluate("() => !!document.getElementById('panCal')"):
            return True
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- the phone: no Claude, so the panel is read on the device ----------
    ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE); p.wait_for_timeout(800)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(1200)
    try:
        p.click("text=Got it", timeout=2500)
    except Exception:
        pass
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(700)
    check("the reader is offered with no Claude present",
          p.evaluate("() => !!document.getElementById('shotBtn')"))

    for img, label in [("tests/label-panel.png", "a clean panel"),
                       ("tests/label-photo.png", "a tilted, blurred photo")]:
        t0 = time.time()
        p.set_input_files("#shotFile", img)
        ok = settle(p)
        vals = p.evaluate("() => [panServe.value, panUnit.value, panCal.value, panPro.value]")
        check("reads %s" % label,
              ok and vals[0] == "60" and vals[1] == "g" and vals[2] == "190" and vals[3] == "21",
              "%s in %.1fs" % (vals, time.time() - t0))

    # the name is front-of-pack branding, not panel text — it must stay blank
    # rather than being invented
    check("it does not invent a product name",
          p.evaluate("() => panName.value") == "",
          p.evaluate("() => panName.value"))

    # something that is not a label must fail visibly, not fill the form
    p.set_input_files("#shotFile", "icons/icon-512.png")
    settle(p)
    filled = p.evaluate("() => panCal.value + '/' + panPro.value")
    said = p.evaluate("""() => {const n = [...document.querySelectorAll('.est-note')]
        .map(x => x.textContent).join(' '); return n;}""")
    check("a photo that is not a panel says so", "ouldn" in said or "fill in" in said, said[:70])
    check("and does not put numbers in the form from nowhere",
          filled in ("/", "190/21"), filled)   # unchanged or cleared, never invented

    check("no page errors while scanning", not errs, str(errs[:2]))

    # the worker keeps the reader, so the second scan needs no network
    cached = p.evaluate("""async () => {
        const ks = await caches.keys();
        for (const k of ks) {
          const c = await caches.open(k);
          const rs = await c.keys();
          if (rs.some(r => r.url.indexOf('vendor/tesseract') > -1)) return true;
        }
        return false;}""")
    check("the reader is kept for offline use", cached is True,
          "service worker cached vendor/tesseract" if cached else "not cached yet")
    ctx.close()

    # ---- the artifact copy has no vendor/, so it must not offer the button --
    dist = os.path.join(ROOT, "dist", "iron-ledger.artifact.html")
    if os.path.exists(dist):
        import io as _io
        src = _io.open(dist, encoding="utf-8").read()
        check("the artifact copy carries no manifest link, so no on-device reader",
              '<link rel="manifest"' not in src)
    b.close()

srv.shutdown()
for s, n, det in res: print("%-6s %-52s %s" % (s, n, det))
_bad = sum(1 for r in res if r[0] == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - _bad, _bad))
raise SystemExit(1 if _bad else 0)
