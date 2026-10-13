"""Build the offline food library from USDA FoodData Central.

The library is generated, never hand-edited, like the icons. It is the answer
to "how do I find the numbers for something the built-in table does not know,
without going on the internet": USDA's own data, public domain, shipped with
the app and searched on the phone.

    python tools/make-foods.py

Three USDA sets go in, each for what it is good at:

  Foundation  (2026)  everyday ingredients, analysed recently
  SR Legacy   (2018)  the long tail: every cut of meat raw and cooked, brands,
                      and a fast-food group (McDonald's, Wendy's, Applebee's...)
  FNDDS       (2024)  foods as people actually eat them: mixed dishes, home
                      cooking, restaurant-style plates, each with typical
                      portions ("1 item", "1 cup")

Only what the app uses is kept: the name, calories and protein per 100 g, and
up to four portions with their gram weights. That turns ~270 MB of JSON into a
1.5 MB file, about 0.3 MB as Pages serves it gzipped, which the service worker
caches at install, so lookups work offline from the first one.

It is written as a script that sets window.IRON_LEDGER_FOODS rather than as
JSON, because a page opened from disk cannot fetch() a file next to it, and
the suites open the app from disk. A <script> tag loads either way.

Downloads are cached in tools/.usda-cache/ (ignored by git). Writes
vendor/usda/foods.js from the repo root. No dependencies beyond Python.
"""
import io, json, os, sys, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", ".usda-cache")
OUT = os.path.join(ROOT, "vendor", "usda", "foods.js")
BASE = "https://fdc.nal.usda.gov/fdc-datasets/"

# code, file, the key the foods sit under, and the year shown beside a result
SETS = [
    ("f", "FoodData_Central_foundation_food_json_2026-04-30.zip", "FoundationFoods", "2026"),
    ("s", "FoodData_Central_sr_legacy_food_json_2018-04.zip", "SRLegacyFoods", "2018"),
    ("n", "FoodData_Central_survey_food_json_2024-10-31.zip", "SurveyFoods", "2024"),
]


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        print("downloading", name)
        urllib.request.urlretrieve(BASE + name, path)
    return path


def per100(food):
    """kcal and protein per 100 g. Energy is listed in kJ as well as kcal in
    the legacy set, so it is chosen by unit, never by name alone; Foundation
    foods often carry only the Atwater figures, which are kcal too."""
    kcal = {}
    protein = None
    for n in food.get("foodNutrients") or []:
        if not isinstance(n, dict):
            continue
        nut = n.get("nutrient") or {}
        num, unit, amt = nut.get("number"), (nut.get("unitName") or "").lower(), n.get("amount")
        if amt is None:
            continue
        if num in ("208", "958", "957") and unit == "kcal":
            kcal[num] = amt
        elif num == "203":
            protein = amt
    k = kcal.get("208", kcal.get("958", kcal.get("957")))
    return k, protein


def portions(food):
    """Up to four real portions, as (label, grams). A weight of zero means
    USDA had none for it, so it is left out rather than offered."""
    out, seen = [], set()
    for p in food.get("foodPortions") or []:
        if not isinstance(p, dict):
            continue
        g = p.get("gramWeight") or 0
        if g <= 0:
            continue
        desc = (p.get("portionDescription") or "").strip()
        if not desc or desc == "Quantity not specified":
            amt = p.get("amount")
            unit = ((p.get("measureUnit") or {}).get("name") or "").strip()
            mod = (p.get("modifier") or "").strip()
            if mod.isdigit():
                mod = ""
            if unit in ("undetermined", ""):
                unit = ""
            if unit == "RACC":
                unit, mod = "serving", ""
            words = " ".join(x for x in (unit, mod) if x)
            if not words:
                continue
            desc = ("%g " % amt if amt else "1 ") + words
        if desc in seen:
            continue
        seen.add(desc)
        out.append([desc, round(g, 1)])
        if len(out) == 4:
            break
    return out


def main():
    foods, counts = [], {}
    for code, name, key, year in SETS:
        z = zipfile.ZipFile(fetch(name))
        data = json.loads(z.read(z.namelist()[0]))
        n = 0
        for f in data[key]:
            if not isinstance(f, dict) or not f.get("description"):
                continue                       # the odd empty record in USDA's files
            k, p = per100(f)
            if k is None or p is None:
                continue
            foods.append([f["description"].strip(), code, round(k, 1), round(p, 1), portions(f)])
            n += 1
        counts[code] = n
        print("%s: %d foods" % (name, n))
    lib = {
        "about": "USDA FoodData Central, public domain (https://fdc.nal.usda.gov). "
                 "Generated by tools/make-foods.py; do not edit by hand.",
        "sets": {code: year for code, _, _, year in SETS},
        "foods": foods,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        fh.write("/* Generated by tools/make-foods.py from USDA FoodData Central (public domain). Do not edit. */\n")
        fh.write("window.IRON_LEDGER_FOODS=")
        json.dump(lib, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print("wrote %s: %d foods, %.1f MB" % (os.path.relpath(OUT, ROOT), len(foods), os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    sys.exit(main())
