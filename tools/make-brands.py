"""Build the grocery-brand library from USDA FoodData Central's Branded Foods.

The second half of the offline food library (tools/make-foods.py is the
first): products as sold, by brand — Kirkland, Great Value, Chobani — with the
serving their label states and the barcode number printed on the package.
Public domain, generated, never hand-edited.

    python tools/make-brands.py

USDA ships ~3 GB of CSV for this, with every version of every product ever
submitted. Kept: products sold in the United States and not discontinued, one
per barcode (the newest submission), with calories and protein per 100 g and
the label serving. That is written to vendor/usda/brands-<release>.js — the
release is in the name, so a phone that has it never downloads it again until
USDA's data actually changes, however many app builds come in between.

The file is a script setting window.IRON_LEDGER_BRANDS, because a page
opened from disk cannot fetch() a file beside it.

Columns, to keep it small: [name, brand, kcal/100 g, protein/100 g,
serving grams, serving words, barcode]. Downloads are cached in
tools/.usda-cache/ (ignored by git). No dependencies beyond Python.
"""
import csv, io, json, os, re, sys, unicodedata, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", ".usda-cache")
RELEASE = "2026-04-30"
NAME = "FoodData_Central_branded_food_csv_%s.zip" % RELEASE
URL = "https://fdc.nal.usda.gov/fdc-datasets/" + NAME
OUT = os.path.join(ROOT, "vendor", "usda", "brands-%s.js" % RELEASE)
KCAL, PROTEIN, CARB, FAT = "1008", "1003", "1005", "1004"

csv.field_size_limit(1 << 30)


def rows(z, suffix):
    name = [n for n in z.namelist() if n.endswith("/" + suffix) or n == suffix][0]
    with z.open(name) as fh:
        r = csv.reader(io.TextIOWrapper(fh, encoding="utf-8", newline=""))
        head = next(r)
        for row in r:
            yield dict(zip(head, row))


def tidy(s):
    """USDA's branded names are mostly in capitals. Make them readable without
    pretending to know a brand's own styling: words of capitals become
    Capitalised, anything already mixed-case is left as it is."""
    s = " ".join(s.split())
    if s.upper() != s:
        return s
    return " ".join(w.capitalize() if w.isalpha() and len(w) > 2 else w.lower() if w.isalpha() else w
                    for w in s.split(" "))


def ascii_only(s):
    """Plain ASCII, so the phone holds the search text at one byte a letter:
    a single accented letter anywhere makes a browser store the whole 30 MB
    string at two. Jalapeño reads as Jalapeno, which is how people type it."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch if ord(ch) < 128 else " " for ch in s if not unicodedata.combining(ch))


def tidy_name(s):
    """USDA appends the flavour to many names even when the name already says
    it — "Protein Bar, Cookies & Cream" was filed as "Cookies & Cream Protein
    Bar, Cookies & Cream". A trailing part whose words are all said earlier
    is dropped; "Greek Yogurt, Blueberry" keeps its blueberry."""
    s = " ".join(ascii_only(s).replace('""', '"').split())
    while ", " in s:
        head, tail = s.rsplit(", ", 1)
        said = set(re.findall(r"[a-z0-9]+", head.lower()))
        words = re.findall(r"[a-z0-9]+", tail.lower())
        if words and all(w in said for w in words):
            s = head
        else:
            break
    return s


# The label's own serving words, as USDA has them, are often in capitals and
# in its unit codes: "5.3 ONZ", "11.5 OZA", "1 cup (140g) Per 1 cup serving".
UNIT_CODES = [(r"\bonz\b", "oz"), (r"\boza\b", "fl oz"), (r"\bgrm\b", "g"), (r"\bmlt\b", "ml")]


def tidy_serving(s):
    s = " ".join(ascii_only(s).split())
    if s.upper() == s:
        s = s.lower()
    for a, b in UNIT_CODES:
        s = re.sub(a, b, s, flags=re.I)
    s = re.sub(r"\s*\bper\b.*$", "", s, flags=re.I)              # "Per 1 cup serving"
    s = re.sub(r"\s*\|?\s*\babout\b\s*$", "", s, flags=re.I)       # a dangling "ABOUT"
    s = re.sub(r"\s*\(\s*\d+(\.\d+)?\s*g\s*\)", "", s)             # "(140g)": the grams are shown anyway
    return s.strip(" ,;|")


def main():
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, NAME)
    if not os.path.exists(path):
        print("downloading", NAME, "(~450 MB)")
        urllib.request.urlretrieve(URL, path)
    z = zipfile.ZipFile(path)

    # 1. which products: US, not discontinued, newest submission per barcode
    best = {}
    for r in rows(z, "branded_food.csv"):
        if r.get("market_country") not in ("United States", ""):
            continue
        if (r.get("discontinued_date") or "").strip():
            continue
        upc = (r.get("gtin_upc") or "").strip().lstrip("0")
        if not upc.isdigit():
            continue
        when = r.get("available_date") or r.get("modified_date") or ""
        if upc in best and best[upc][0] >= when:
            continue
        try:
            sg = float(r.get("serving_size") or 0)
        except ValueError:
            sg = 0
        unit = (r.get("serving_size_unit") or "").lower()
        if unit not in ("g", "grm", "ml", "mlt"):
            sg = 0
        brand = (r.get("brand_name") or "").strip() or (r.get("brand_owner") or "").strip()
        best[upc] = (when, r["fdc_id"], brand, round(sg, 1),
                     (r.get("household_serving_fulltext") or "").strip(), unit in ("ml", "mlt"))
    keep = {v[1]: upc for upc, v in best.items()}
    print("products kept:", len(keep))

    # 2. their numbers
    num = {}
    for r in rows(z, "food_nutrient.csv"):
        f = r["fdc_id"]
        if f in keep and r["nutrient_id"] in (KCAL, PROTEIN, CARB, FAT):
            try:
                num.setdefault(f, {})[r["nutrient_id"]] = float(r["amount"])
            except ValueError:
                pass
    # 3. their names
    names = {}
    for r in rows(z, "food.csv"):
        if r["fdc_id"] in keep:
            names[r["fdc_id"]] = r["description"]

    out = []
    for upc, (_, fid, brand, sg, words, ml) in best.items():
        n = num.get(fid, {})
        if KCAL not in n or PROTEIN not in n or fid not in names:
            continue
        k, p = n[KCAL], n[PROTEIN]
        if k < 0 or k > 950 or p < 0 or p > 100:        # impossible per 100 g: skip, never guess
            continue
        serving = tidy_serving(words) if words else ""
        if ml and sg and "ml" not in serving.lower():
            serving = (serving or "1 serving") + " (%g ml)" % sg
        c, fa = n.get(CARB), n.get(FAT)
        c = None if c is None or c < 0 or c > 100 else round(c, 1)
        fa = None if fa is None or fa < 0 or fa > 100 else round(fa, 1)
        out.append([tidy_name(tidy(names[fid])), " ".join(ascii_only(tidy(brand)).split()), round(k, 1), round(p, 1), sg, serving, upc, c, fa])

    # One product in several pack sizes has one set of numbers: keep it once,
    # with every barcode it is sold under, so a scan of any of them finds it.
    merged = {}
    for name, brand, k, p, sg, serving, upc, c, fa in out:
        key = (brand.lower(), name.lower(), k, p)
        if key in merged:
            merged[key][6].append(upc)
            if not merged[key][4] and sg:
                merged[key][4], merged[key][5] = sg, serving
        else:
            merged[key] = [name, brand, k, p, sg, serving, [upc], c, fa]
    items = sorted(merged.values(), key=lambda x: (x[1].lower(), x[0].lower()))

    # Columns, not records: a phone keeps one long string per column rather
    # than half a million small arrays, and searches the text column with the
    # browser's own indexOf. The text column is lowercase "brand|name", one
    # product per line; the app capitalises it for display.
    lib = {
        "about": "USDA FoodData Central Branded Foods, release %s, public domain (https://fdc.nal.usda.gov). "
                 "Generated by tools/make-brands.py; do not edit by hand." % RELEASE,
        "release": RELEASE,
        "count": len(items),
        "text": "\n".join("%s|%s" % (x[1].lower().replace("|", " ").replace("\n", " "),
                                     x[0].lower().replace("|", " ").replace("\n", " ")) for x in items),
        "k": [x[2] for x in items],
        "p": [x[3] for x in items],
        "sg": [x[4] for x in items],
        "serving": "\n".join(x[5].replace("\n", " ") for x in items),
        "upc": "\n".join(" ".join(x[6]) for x in items),
        # carbohydrate and fat per 100 g; -1 where the label gave none
        "c": [-1 if x[7] is None else x[7] for x in items],
        "f": [-1 if x[8] is None else x[8] for x in items],
    }
    out = items
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        fh.write("/* Generated by tools/make-brands.py from USDA FoodData Central (public domain). Do not edit. */\n")
        fh.write("window.IRON_LEDGER_BRANDS=")
        json.dump(lib, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print("wrote %s: %d products, %.1f MB" % (os.path.relpath(OUT, ROOT), len(out), os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    sys.exit(main())
