"""Render the app icons from the app's own design tokens.

Icons are generated, never hand-drawn, so they cannot drift from the palette
in mntl-dt.html. Re-run after changing --ink / --ground:

    python tools/make-icons.py

Uses the Playwright Chromium that the test suites already need, so this adds
no dependency. Writes icons/ and the iPhone app's icon from the repo root.

The mark is Tommy's sketch (2026-10-20): a Roman II with the top-right corner
gone, so it reads as an I and an L sharing one base. The left stem keeps the
top bar's overhang (the I); the base runs on past the right stem (the L's
foot). Even strokes, square ends, no accent colour.
"""
import os, io, re
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def token(css, name, fallback):
    m = re.search(r"--%s:\s*(#[0-9A-Fa-f]{3,8})\s*;" % name, css)
    return m.group(1) if m else fallback


src = io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()
INK = token(src, "ink", "#141A19")
GROUND = token(src, "ground", "#E9EBE8")
print("tokens: ink=%s ground=%s" % (INK, GROUND))

# The mark on a 58 x 40 grid, strokes 8 thick: top bar, the two stems, the base.
MARK = """<svg viewBox="0 0 58 40" width="{w}" height="{h}" fill="{ground}">
<rect x="0" y="0" width="42.5" height="8"/>
<rect x="15" y="0" width="8" height="40"/>
<rect x="34.5" y="0" width="8" height="40"/>
<rect x="0" y="32" width="58" height="8"/></svg>"""

PAGE = """<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0}}
.icon{{width:{s}px;height:{s}px;background:{ink};display:flex;
  align-items:center;justify-content:center}}
svg{{display:block}}
</style><div class="icon">{mark}</div>"""


# pad = share of the canvas left empty around the mark. Maskable icons get the
# 20% safe zone Android crops to; normal icons sit tighter.
def render(page, size, out, pad, folder="icons"):
    w = size * (1 - pad) * 0.69
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(PAGE.format(s=size, ink=INK, mark=MARK.format(
        w=round(w, 2), h=round(w * 40 / 58, 2), ground=GROUND)))
    page.locator(".icon").screenshot(path=os.path.join(ROOT, folder, out))
    print("  %s/%-28s %dx%d" % (folder.replace(os.sep, "/"), out, size, size))


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
    # The iPhone app (ios/, Capacitor): one 1024 square, from which Xcode makes
    # every size. The App Store refuses an icon with an alpha channel, and a
    # screenshot of this opaque square has none.
    render(pg, 1024, "AppIcon-512@2x.png", 0.16,
           folder=os.path.join("ios", "App", "App", "Assets.xcassets", "AppIcon.appiconset"))
    b.close()
print("done")
