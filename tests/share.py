"""Handing someone a routine.

The Coach tab exists so somebody else can set a routine for the owner. The
trap, written up in CLAUDE.md before any of this was built, is day ids:
DEFAULT_ROUTINE uses fixed ones — back, push, legs — so two people who never
renamed their days hold *the same ids for different days*. Importing under
those ids relabels the recipient's own history, which is rule 7 broken with
nothing to show for it.

The export therefore carries no ids at all and the importer mints fresh ones,
so a collision is not defended against, it cannot happen. This suite proves
that with two stores that deliberately collide.
"""
from playwright.sync_api import sync_playwright
import os, base64, json, datetime

d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}
res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))


def store(days=None, moves=None, lifts=None):
    s = {"days": {T: {"food": [], "lifts": lifts or [], "updated": 1, "goal": G}},
         "moves": moves, "goal": G, "region": "United States", "pantry": [], "v": 1}
    if days: s["routine"] = {"name": "My split", "days": days}
    return s


# someone else's routine, using the very ids a default install already has
THEIRS = store(
    days=[{"id": "back", "name": "Bro Upper A", "short": "Bro Upper A"},
          {"id": "push", "name": "Bro Upper B", "short": "Bro Upper B"},
          {"id": "legs", "name": "Bro Lower", "short": "Bro Lower"}],
    moves={"back": ["Meadows Row", "Chin-Up"], "push": ["Incline Press"], "legs": ["Hack Squat"]})

# mine: a stock routine with a workout already logged under my "back"
MINE = store(lifts=[{"id": "l1", "cat": "back", "movement": "Barbell Row",
                     "sets": [{"w": 135, "r": 10}]}])

with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- they share ------------------------------------------------------
    ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
    p = ctx.new_page()
    p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(500)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", THEIRS)
    p.reload(); p.wait_for_timeout(1000)
    try:
        p.click("text=Got it", timeout=2000)
    except Exception:
        pass
    p.click('.tabs button[data-tab="coach"]'); p.wait_for_timeout(500)
    p.click("#shareRoutine"); p.wait_for_timeout(500)
    code = p.input_value("#routineCode")
    check("sharing produces a code", code.startswith("ILROUTINE1:"), code[:30])
    box = p.locator("#routineCode").bounding_box()
    check("the code box does not trigger the iOS zoom",
          p.eval_on_selector("#routineCode", "e => parseFloat(getComputedStyle(e).fontSize)") >= 16)

    payload = json.loads(base64.b64decode(code.split(":", 1)[1]).decode("utf-8"))
    check("the code carries the days", len(payload.get("days", [])) == 3,
          str([x.get("name") for x in payload.get("days", [])]))
    check("and what is in each of them",
          sum(len(x.get("moves", [])) for x in payload["days"]) == 4)
    # the whole design rests on this: no ids travel, so none can collide
    check("and no ids at all", not any("id" in x for x in payload["days"]),
          str(payload["days"][0]))
    # "days" in the payload means training days, not the log. What must not be
    # in here is anything you ate, lifted, saved or aimed at.
    blob = json.dumps(payload)
    leaked = [k for k in ("food", "lifts", "pantry", "goal", "region", "retired", "lastBackupAt")
              if k in blob] + ([T] if T in blob else [])
    check("and nothing from the log or the phone", not leaked,
          "leaked: %s" % ", ".join(leaked) if leaked else "keys: " + ", ".join(sorted(payload.keys())))
    ctx.close()

    # ---- I load it, and my history must not move ------------------------
    ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(500)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", MINE)
    p.reload(); p.wait_for_timeout(1000)
    try:
        p.click("text=Got it", timeout=2000)
    except Exception:
        pass
    p.click('.tabs button[data-tab="coach"]'); p.wait_for_timeout(400)

    # a code that is not a code has to say so, not sit there doing nothing
    p.click("#loadRoutine"); p.wait_for_timeout(450)
    p.fill("#routineCode", "here is my routine mate"); p.click("#applyRoutine"); p.wait_for_timeout(450)
    said = p.evaluate("() => {const m = document.getElementById('shareMsg'); return m ? m.textContent : '';}")
    check("junk in the box is refused out loud", "ILROUTINE1" in said, said[:60])
    check("and nothing was added",
          len(p.evaluate("() => JSON.parse(localStorage.getItem('iron-ledger-v1')).routine.days")) == 3)

    p.fill("#routineCode", code); p.click("#applyRoutine"); p.wait_for_timeout(700)
    days = p.evaluate("() => JSON.parse(localStorage.getItem('iron-ledger-v1')).routine.days")
    names = [x["name"] for x in days]
    ids = [x["id"] for x in days]
    check("their days are added, not swapped in", len(days) == 6, str(names))
    check("mine are still first and unchanged", names[:3] == [
          "Back / Bi / Rear Delt", "Chest / Shoulder / Tri", "Legs"], str(names[:3]))
    check("every id is unique", len(set(ids)) == len(ids), str(ids))
    check("theirs arrived with fresh ids", all(i.startswith("d") for i in ids[3:]), str(ids[3:]))
    moves = p.evaluate("() => JSON.parse(localStorage.getItem('iron-ledger-v1')).moves")
    check("their movements came with them",
          sum(len(moves.get(i, [])) for i in ids[3:]) == 4,
          str([(x["name"], len(moves.get(x["id"], []))) for x in days[3:]]))
    check("my own day's movements are untouched", len(moves.get("back", [])) > 0)

    # rule 7, the whole point
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
    body = p.eval_on_selector(".lift .body", "e => e.textContent.replace(/\\s+/g, ' ')")
    check("my workout is not relabelled as theirs", "Bro Upper" not in body, body[:60])
    check("and is not orphaned either", "no longer train" not in body, body[:60])

    p.click('.tabs button[data-tab="coach"]'); p.wait_for_timeout(400)
    check("loading offers undo", p.evaluate("() => !document.getElementById('undobar').hidden"))
    p.click("#undoBtn"); p.wait_for_timeout(600)
    after = p.evaluate("() => JSON.parse(localStorage.getItem('iron-ledger-v1')).routine.days.map(x => x.name)")
    check("undo takes their days back out", after == names[:3], str(after))
    check("no page errors", not errs, str(errs[:2]))
    ctx.close()
    b.close()

for s, n, det in res: print("%-6s %-48s %s" % (s, n, det))
_bad = sum(1 for r in res if r[0] == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - _bad, _bad))
raise SystemExit(1 if _bad else 0)
