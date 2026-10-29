"""Render the app icons from the app's own design tokens.

Icons are generated, never hand-drawn, so they cannot drift from the palette
in mntl-dt.html. Re-run after changing --ink / --ground:

    python tools/make-icons.py

Uses the Playwright Chromium that the test suites already need, so this adds
no dependency. Writes icons/ and the iPhone app's icon from the repo root.

The mark is Tommy's pick (2026-10-28): MNTL in heavy condensed capitals over
D&T in the accent, with a barbell where a rule would be. MNTL is joined the
way the old IL mark was: M and N share a stem, and the N's right stem carries
one top bar across the T to the L, whose foot runs on. D&T is set in
Anton, the condensed face Tommy picked it in, so it reads as a real "&".
All of it is drawn as shapes, not set in a font, so it needs no font file.
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
# The icon is dark, so D&T takes the dark theme's accent, the one made to
# read on ink.
ACCENT = token(src[src.index("prefers-color-scheme: dark"):], "accent", "#56B9A9")
print("tokens: ink=%s ground=%s accent=%s" % (INK, GROUND, ACCENT))

# The mark on a 220 x 175 grid. MNTL fills y 0-100 with 18-thick strokes.
# D&T sits on y 120-174: the outlines of Anton's D, & and T (SIL Open Font
# License), copied in so no font is loaded. The barbell is centred on D&T and
# ends flush with the L's foot.
MARK = """<svg viewBox="0 0 220 175" width="{w}" height="{h}">
<g fill="{ground}">
<path d="M0,100 V0 H24 L35,56 L46,0 H70 V100 H52 V42 L42,86 H28 L18,42 V100 Z"/>
<path d="M52,100 V0 H72 L98,62 V0 H116 V100 H96 L70,38 V100 Z"/>
<rect x="98" width="94" height="18"/>
<rect x="136" width="18" height="100"/>
<rect x="174" width="18" height="100"/>
<rect x="174" y="82" width="46" height="18"/></g>
<g fill="{accent}">
<path transform="translate(-2.39,174) scale(0.030682,-0.030682)" d="M78 0V1760H562Q752 1760 848 1654.5Q944 1549 944 1346V522Q944 272 856.5 136Q769 0 550 0ZM432 311H493Q590 311 590 405V1313Q590 1401 566.5 1426.5Q543 1452 471 1452H432Z"/>
<path transform="translate(31.50,174) scale(0.030682,-0.030682)" d="M386 -21Q222 -21 128.5 106Q35 233 35 456Q35 615 63.5 720Q92 825 143 895Q194 965 260 1017L252 1037Q210 1141 178.5 1235.5Q147 1330 147 1430Q147 1531 190 1609Q233 1687 309.5 1731.5Q386 1776 485 1776Q583 1776 663.5 1733.5Q744 1691 792 1606Q840 1521 840 1391Q840 1250 787.5 1155Q735 1060 630 972L726 730Q785 879 896 961L1035 744Q919 651 841 441L1017 0H677L638 95Q599 47 533.5 13Q468 -21 386 -21ZM461 1461Q461 1435 474 1384.5Q487 1334 535 1210Q554 1230 569 1273Q584 1316 584 1391Q584 1468 565.5 1499Q547 1530 517 1530Q488 1530 474.5 1508.5Q461 1487 461 1461ZM341 413Q341 235 442 235Q483 235 508 265.5Q533 296 542 329L374 738Q341 668 341 493Z"/>
<path transform="translate(68.64,174) scale(0.030682,-0.030682)" d="M229 0V1422H20V1760H790V1422H581V0Z"/></g>
<g fill="{ground}">
<rect x="101" y="144" width="119" height="6"/>
<rect x="103" y="133" width="6" height="28" rx="1.5"/>
<rect x="111" y="127" width="9" height="40" rx="1.5"/>
<rect x="121" y="140" width="4" height="14" rx="1"/>
<rect x="196" y="140" width="4" height="14" rx="1"/>
<rect x="201" y="127" width="9" height="40" rx="1.5"/>
<rect x="212" y="133" width="6" height="28" rx="1.5"/></g></svg>"""

PAGE = """<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0}}
.icon{{width:{s}px;height:{s}px;background:{ink};display:flex;
  align-items:center;justify-content:center}}
svg{{display:block}}
</style><div class="icon">{mark}</div>"""


# pad = share of the canvas left empty around the mark. Maskable icons get the
# 20% safe zone Android crops to; normal icons sit tighter.
def render(page, size, out, pad, folder="icons"):
    w = size * (1 - pad) * 0.80
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(PAGE.format(s=size, ink=INK, mark=MARK.format(
        w=round(w, 2), h=round(w * 175 / 220, 2), ground=GROUND, accent=ACCENT)))
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
