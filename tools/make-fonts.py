"""Regenerate fonts/ from Google Fonts. Never hand-edit what this writes.

    python tools/make-fonts.py

Archivo is variable on two axes: weight 400-800 and width 100-125%. The
redesign's display numbers are set at 800 and 125%, and a browser can fake a
weight but never a width, so the axis has to be in the file. IBM Plex Mono is
static, 400/500/600, one file per weight.

It writes the woff2 files under the names the service worker already lists,
writes fonts/fonts.css, and prints the same @font-face block that sits at the
top of iron-ledger.html. sweep fails if the two ever differ.
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


def build():
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

    text = "\n".join(archivo + mono) + "\n"
    with open(os.path.join(OUT, "fonts.css"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    build()
