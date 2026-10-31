"""The public pages App Store Connect links to: privacy, support and terms.

Apple checks that the Privacy Policy URL and Support URL open, and a reviewer
reads them on a phone. So every page is opened here as a phone, in light and
dark: each links to the other two and back to the app, nothing is left in
[brackets] from the drafts, every link is a 44px press that lands on the link,
the text keeps its contrast, and nothing scrolls sideways.

Served over http with mntl-dt.html at "/", as Pages serves it, because the
service worker is the other half of this: it caches the app's document as
"./", and before these pages existed it cached *any* page that way, so one
visit to the privacy policy would have made it the app's offline copy.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, threading, datetime, functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["privacy.html", "support.html", "terms.html"]
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


# The deploy has to copy them, or the URLs in App Store Connect are 404s.
wf = io.open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8").read()
for f in PAGES:
    check("%s exists" % f, os.path.exists(os.path.join(ROOT, f)))
    check("the deploy copies %s" % f, f in wf.split("Assemble the site", 1)[-1].split("- uses:", 1)[0])

# The app records TERMS as the version of the Terms someone agreed to, and it is
# the effective date of the Terms as published, so the two must say the same.
app = io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()
version = re.search(r'var TERMS = "(\d{4}-\d\d-\d\d)"', app).group(1)
when = datetime.date.fromisoformat(version)
stated = "Effective date: %s %d, %d" % (when.strftime("%B"), when.day, when.year)
check("the Terms state the date the app records", stated in io.open(os.path.join(ROOT, "terms.html"), encoding="utf-8").read(), stated)

srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % PORT

# Relative luminance contrast of two computed rgb() colours.
CONTRAST = """(pair) => {
  const lum = c => { const v = c.match(/[\\d.]+/g).slice(0, 3).map(Number).map(x => {
    x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); });
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const a = lum(pair[0]), b = lum(pair[1]);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
}"""

# Every link: its box (padding included), and whether a press at its middle
# reaches it rather than whatever is drawn on top.
LINKS = """() => [...document.querySelectorAll('a')].map(a => {
  const r = a.getBoundingClientRect();
  const parts = [...a.getClientRects()].map(q => [q.width, q.height]);
  a.scrollIntoView({block: 'center'});
  const q = a.getClientRects()[0];
  const hit = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
  return {text: a.textContent.trim(), href: a.getAttribute('href'), w: r.width, h: r.height,
          parts, reached: !!hit && (hit === a || a.contains(hit))};
})"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    for scheme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 375, "height": 812}, has_touch=True, is_mobile=True,
                            color_scheme=scheme, service_workers="block")
        p = ctx.new_page(); errs = []; offsite = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.on("request", lambda r: offsite.append(r.url) if not r.url.startswith(BASE) else None)
        for f in PAGES:
            tag = "%s (%s)" % (f, scheme)
            p.goto(BASE + f); p.wait_for_load_state("networkidle")
            text = p.inner_text("body")
            check("%s has no [placeholders] left" % tag, "[" not in text and "]" not in text,
                  [l for l in text.splitlines() if "[" in l or "]" in l][:3])
            hrefs = p.eval_on_selector_all("a", "as => as.map(a => a.getAttribute('href'))")
            others = [g for g in PAGES if g != f]
            check("%s links to %s" % (tag, " and ".join(others)), all(g in hrefs for g in others))
            check("%s links back to the app" % tag, "./" in hrefs)
            check("%s marks itself as the current page" % tag,
                  p.locator('nav a[aria-current="page"][href="%s"]' % f).count() == 2)
            check("%s gives the support email" % tag, "mailto:mntldntsupport@gmail.com" in hrefs)
            if f != "support.html":
                check("%s states its effective date" % tag, "Effective date:" in text)

            small = []; missed = []
            for l in p.evaluate(LINKS):
                if l["h"] < 44 or l["w"] < 44 or any(h < 44 for _, h in l["parts"]):
                    small.append("%s %.0fx%.0f" % (l["text"][:24], l["w"], l["h"]))
                if not l["reached"]: missed.append(l["text"][:24])
            check("%s: every link is at least 44px" % tag, not small, small[:4])
            check("%s: a press on every link reaches it" % tag, not missed, missed[:4])

            sideways = p.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            check("%s does not scroll sideways at phone width" % tag, sideways <= 0, "%dpx" % sideways)
            p.set_viewport_size({"width": 320, "height": 640})
            sideways = p.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            check("%s does not scroll sideways at 320px" % tag, sideways <= 0, "%dpx" % sideways)
            p.set_viewport_size({"width": 375, "height": 812})

            check("%s uses the app's own fonts" % tag,
                  p.evaluate("() => document.fonts.check(\"17px Archivo\") && [...document.fonts].some(f => f.family.includes('Archivo') && f.status === 'loaded')"))
            bg = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
            check("%s is drawn in the %s theme" % (tag, scheme),
                  bg == ("rgb(242, 244, 241)" if scheme == "light" else "rgb(14, 18, 17)"), bg)
            # every visible piece of text against the surface it sits on
            pairs = p.evaluate("""() => {
              const out = [], seen = new Set();
              const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
              for (let n; (n = walk.nextNode());) {
                if (!n.textContent.trim()) continue;
                const el = n.parentElement, cs = getComputedStyle(el);
                let s = el, bg = 'rgba(0, 0, 0, 0)';
                while (s && (bg = getComputedStyle(s).backgroundColor) === 'rgba(0, 0, 0, 0)') s = s.parentElement;
                const k = cs.color + '|' + bg;
                if (!seen.has(k)) { seen.add(k); out.push([cs.color, bg, n.textContent.trim().slice(0, 20)]); }
              }
              return out; }""")
            low = []
            for fg, bgc, t in pairs:
                r = p.evaluate(CONTRAST, [fg, bgc])
                if r < 4.5: low.append("%s %.2f" % (t, r))
            check("%s: all text keeps 4.5:1 contrast" % tag, not low, low[:4])
        check("pages load nothing from another site (%s)" % scheme, not offsite, offsite[:3])
        check("no page errors (%s)" % scheme, not errs, str(errs))
        ctx.close()

    # The app's own theme choice carries over: dark chosen in the app, phone in light.
    ctx = b.new_context(viewport={"width": 375, "height": 812}, has_touch=True, is_mobile=True,
                        color_scheme="light", service_workers="block")
    ctx.add_init_script("localStorage.setItem('iron-ledger-look', JSON.stringify({theme: 'dark'}))")
    p = ctx.new_page(); p.goto(BASE + "privacy.html")
    check("a phone set to dark in the app gets dark pages",
          p.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(14, 18, 17)")
    ctx.close()

    # The service worker must keep the app as its offline copy after a visit here.
    ctx = b.new_context(viewport={"width": 375, "height": 812}, has_touch=True, is_mobile=True)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE); p.wait_for_timeout(600)
    p.evaluate("async () => { await navigator.serviceWorker.ready; }")
    p.reload(); p.wait_for_timeout(1500)       # the worker now controls the page
    controlled = p.evaluate("() => !!navigator.serviceWorker.controller")
    for f in PAGES:
        p.goto(BASE + f); p.wait_for_timeout(400)
    ctx.set_offline(True)
    p.goto(BASE); p.wait_for_timeout(800)
    check("the worker controls the app", controlled)
    check("offline, the app still opens after the pages were visited",
          "privacy" not in p.title().lower() and p.locator("#view").count() == 1, p.title())
    ctx.set_offline(False)
    check("no page errors (service worker)", not errs, str(errs))
    ctx.close()
    b.close()

srv.shutdown()
for s, n, d in res: print("%-6s %-62s %s" % (s, n, d))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
