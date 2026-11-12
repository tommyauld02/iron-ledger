"""Regenerate fonts/ from Google Fonts. Never hand-edit what this writes.

    python tools/make-fonts.py

Archivo is variable on two axes: weight 400-800 and width 100-125%. The
redesign's display numbers are set at 800 and 125%, and a browser can fake a
weight but never a width, so the axis has to be in the file. IBM Plex Mono is
static, 400/500/600, one file per weight.

The Chalk and Iron look (b96) adds three display faces, used large and never
for running text: Big Shoulders Display for the placard numerals, Big Shoulders
Stencil Display for stencilled labels, both variable on weight, and Caveat
Brush, static, for the one line written in chalk.

It writes the woff2 files under the names the service worker already lists,
writes fonts/fonts.css, and prints the same @font-face block that sits at the
top of mntl-dt.html. sweep fails if the two ever differ.

A family whose files are already in fonts/ is left alone, bytes and
@font-face lines both, so adding a face does not churn the ones the app has
shipped for months. Pass --refresh to fetch everything again.
"""
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "fonts")

# A current browser's user agent, or the API answers with TrueType.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
API = "https://fonts.googleapis.com/css2?family="
SUBSETS = ("latin", "latin-ext")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def faces(css):
    """[(subset, block)] from the API's CSS, which labels each block /* subset */."""
    out = []
    for m in re.finditer(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]*\})", css):
        out.append((m.group(1), m.group(2)))
    return out


def field(block, name):
    m = re.search(name + r"\s*:\s*([^;]+);", block)
    return m.group(1).strip() if m else ""


REFRESH = "--refresh" in sys.argv

# (family as the API names it, the query after it, file stem, the font-weight to declare)
DISPLAY = [
    ("Big Shoulders Display", "Big+Shoulders+Display:wght@100..900", "BigShoulders", "100 900"),
    ("Big Shoulders Stencil Display", "Big+Shoulders+Stencil+Display:wght@100..900", "BigShouldersStencil", "100 900"),
    ("Caveat Brush", "Caveat+Brush", "CaveatBrush", "400"),
]


def kept(family, names):
    """The @font-face lines already in fonts.css for a family whose files are all here."""
    if REFRESH or not all(os.path.exists(os.path.join(OUT, n)) for n in names):
        return None
    try:
        with open(os.path.join(OUT, "fonts.css"), encoding="utf-8") as f:
            lines = [l.strip() for l in f if ("font-family:'%s';" % family) in l]
    except OSError:
        return None
    return lines if len(lines) == len(names) else None


def display(family, query, stem, weight):
    names = ["%s-%s.woff2" % (stem, s) for s in SUBSETS]
    have = kept(family, names)
    if have:
        return have
    css = get(API + query + "&display=swap").decode("utf-8")
    got = {}
    for subset, block in faces(css):
        if subset in SUBSETS and subset not in got:
            got[subset] = block
    if set(got) != set(SUBSETS):
        sys.exit("%s: expected %s, got %s" % (family, SUBSETS, sorted(got)))
    out = []
    for subset in SUBSETS:
        block = got[subset]
        url = re.search(r"url\(([^)]+\.woff2)\)", block).group(1)
        name = "%s-%s.woff2" % (stem, subset)
        data = get(url)
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(data)
        print("  %-36s %6.1f KB" % (name, len(data) / 1024), file=sys.stderr)
        out.append("@font-face{font-family:'%s';font-style:normal;font-weight:%s;font-display:swap;"
                   "src:url(fonts/%s) format('woff2');unicode-range:%s}" % (family, weight, name, field(block, "unicode-range")))
    return out


def shipped():
    """Archivo and IBM Plex Mono as they already are, when nothing is being refreshed."""
    a = kept("Archivo", ["Archivo-%s.woff2" % s for s in SUBSETS])
    m = kept("IBM Plex Mono", ["IBMPlexMono-%d-%s.woff2" % (w, s) for w in (400, 500, 600) for s in SUBSETS])
    return (a + m) if a and m else None


def build():
    extra = []
    for fam in DISPLAY:
        extra += display(*fam)
    old = shipped()
    if old:
        text = "\n".join(old + extra) + "\n"
        with open(os.path.join(OUT, "fonts.css"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        sys.stdout.write(text)
        return
    blocks = []

    # Archivo: one variable file per subset, both axes.
    css = get(API + "Archivo:wdth,wght@100..125,400..800&display=swap").decode("utf-8")
    seen = set()
    for subset, block in faces(css):
        if subset not in SUBSETS or subset in seen:
            continue
        seen.add(subset)
        url = re.search(r"url\(([^)]+\.woff2)\)", block).group(1)
        name = "Archivo-%s.woff2" % subset
        data = get(url)
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(data)
        print("  %-36s %6.1f KB" % (name, len(data) / 1024), file=sys.stderr)
        blocks.append((subset, "@font-face{font-family:'Archivo';font-style:normal;font-weight:400 800;"
                               "font-stretch:100%% 125%%;font-display:swap;src:url(fonts/%s) format('woff2');"
                               "unicode-range:%s}" % (name, field(block, "unicode-range"))))
    if seen != set(SUBSETS):
        sys.exit("Archivo: expected %s, got %s" % (SUBSETS, sorted(seen)))
    order = {s: i for i, s in enumerate(SUBSETS)}
    archivo = [b for _, b in sorted(blocks, key=lambda x: order[x[0]])]

    # IBM Plex Mono: static, one file per weight and subset.
    mono = []
    for weight in (400, 500, 600):
        css = get(API + "IBM+Plex+Mono:wght@%d&display=swap" % weight).decode("utf-8")
        got = {}
        for subset, block in faces(css):
            if subset in SUBSETS and subset not in got:
                got[subset] = block
        for subset in SUBSETS:
            block = got[subset]
            url = re.search(r"url\(([^)]+\.woff2)\)", block).group(1)
            name = "IBMPlexMono-%d-%s.woff2" % (weight, subset)
            data = get(url)
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(data)
            print("  %-36s %6.1f KB" % (name, len(data) / 1024), file=sys.stderr)
            mono.append("@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:%d;"
                        "font-display:swap;src:url(fonts/%s) format('woff2');unicode-range:%s}"
                        % (weight, name, field(block, "unicode-range")))

    text = "\n".join(archivo + mono + extra) + "\n"
    with open(os.path.join(OUT, "fonts.css"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    build()
