"""Render the app icons from the app's own design tokens.

Icons are generated, never hand-drawn, so they cannot drift from the palette
in iron-ledger.html. Re-run after changing --ink / --ground / --accent:

    python tools/make-icons.py

Uses the Playwright Chromium that the test suites already need, so this adds
no dependency. Writes icons/ from the repo root.
"""
import os, io, re
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def token(css, name, fallback):
    m = re.search(r"--%s:\s*(#[0-9A-Fa-f]{3,8})\s*;" % name, css)
    return m.group(1) if m else fallback


src = io.open(os.path.join(ROOT, "iron-ledger.html"), encoding="utf-8").read()
INK = token(src, "ink", "#141A19")
GROUND = token(src, "ground", "#E9EBE8")
ACCENT = token(src, "accent", "#0B6E63")
print("tokens: ink=%s ground=%s accent=%s" % (INK, GROUND, ACCENT))

# pad = share of the canvas left empty around the mark. Maskable icons get the
# 20% safe zone Android crops to; normal icons sit tighter.
PAGE = """<!doctype html><meta charset="utf-8"><style>
@font-face{{font-family:'Archivo';font-weight:400 700;
  src:url('{root}/fonts/Archivo-latin.woff2') format('woff2')}}
html,body{{margin:0}}
.icon{{width:{s}px;height:{s}px;background:{ink};display:flex;
  flex-direction:column;align-items:center;justify-content:center;
  gap:{gap}px;font-family:'Archivo',sans-serif}}
/* letter-spacing also lands after the L, which would shove the glyphs left
   of centre; the negative margin takes that trailing space back off. */
.mono{{font-weight:700;font-size:{fs}px;letter-spacing:.10em;color:{ground};
  margin-right:-.10em;line-height:1}}
.rule{{width:{rw}px;height:{rh}px;background:{accent}}}
</style><div class="icon"><div class="mono">IL</div><div class="rule"></div></div>"""


def render(page, size, out, pad):
    inner = size * (1 - pad)
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(PAGE.format(
        root="file:///" + ROOT.replace("\\", "/").lstrip("/"),
        s=size, ink=INK, ground=GROUND, accent=ACCENT,
        fs=round(inner * 0.54), gap=round(inner * 0.055),
        rw=round(inner * 0.50), rh=max(2, round(inner * 0.030))))
    page.wait_for_timeout(250)
    page.locator(".icon").screenshot(path=os.path.join(ROOT, "icons", out))
    print("  icons/%-28s %dx%d" % (out, size, size))


os.makedirs(os.path.join(ROOT, "icons"), exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(device_scale_factor=1)
    render(pg, 512, "icon-512.png", 0.16)
    render(pg, 192, "icon-192.png", 0.16)
    # iOS never rounds the artwork itself, it masks the square it is given
    render(pg, 180, "apple-touch-icon.png", 0.16)
    # Android crops maskable icons to a circle: keep the mark inside 80%
    render(pg, 512, "icon-512-maskable.png", 0.30)
    b.close()
print("done")
