"""The food finder, from the app's side: what is sent, and who answers.

The owner replaced the lists the app shipped (the built-in table, USDA's
library, the chains' menus) with a free AI, and wanted it to work with nothing
to set up (b63): the app asks a relay (relay/worker.js) that holds the key.
The behaviour a person sees is walked in sweep and the relay is tested in
tests/relay.py; this is the contract between them, the part a slip in would
cost a key, privacy or a wrong number:

  - the app holds no key, and sends none: only the words and the country go;
  - nothing from the log goes with them;
  - the pantry answers first, and a meal it knows sends nothing;
  - with no relay and no Claude nothing leaves the phone at all;
  - the relay is the base; Claude answers only when it is out of reach.

The relay is tests/fakeai.py, here as everywhere; nothing is sent anywhere.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
import os, io, re, json, datetime
import fakeai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = ROOT.replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}
SECRET_NOTE = "dinner at grandma's flat 4b"         # a note in the log that must never be sent
STORE = {"days": {T: {"food": [{"id": "f1", "cal": 400, "pro": 30, "note": SECRET_NOTE},
                               {"id": "f2", "cal": 0, "pro": 0, "note": "2 eggs", "pending": True}],
                      "lifts": [], "updated": 1, "goal": G}},
         "moves": None, "goal": G, "region": "Canada", "seen": True, "v": 1,
         "pantry": [{"id": "p1", "name": "costco protein coffee", "serveQty": 1, "serveUnit": "bottle",
                     "serveG": None, "sCal": 130, "sPro": 30, "aliases": []}]}
CLAUDE = """
window.claude={use:function(n){
 if(n==='sample'){var f=function(){};
  f.json=function(p){window.__claudeAsked=(window.__claudeAsked||0)+1;
    return Promise.resolve({items:[{food:'Beef wellington',amount:'1 slice',grams:250,calories:675,protein:33,carbs:38,fat:44,basis:'rough'}],note:''});};
  f.limits=function(){return Promise.resolve({});};
  return Promise.resolve(f);}
 return Promise.resolve(null);}};
"""
SRC = io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()
res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))

ROWS = "()=>[...document.querySelectorAll('.rev-item')].map(x=>x.querySelector('.food').textContent+' | '+x.querySelector('.src-tag').textContent)"

# ---- the app itself ------------------------------------------------------
relay_url = re.search(r'var RELAY_URL = "([^"]*)";', SRC)
check("the app holds no key of any kind",
      not re.search(r"AIza[0-9A-Za-z_-]{20,}|sk-or-[0-9A-Za-z_-]{20,}|nvapi-[0-9A-Za-z_-]{20,}|Bearer ", SRC))
check("the relay it asks is the owner's Cloudflare Worker, over https",
      relay_url and re.match(r"^https://iron-ledger-finder\.[a-z0-9-]+\.workers\.dev/find$", relay_url.group(1)),
      relay_url and relay_url.group(1))
check("the loading line says it is finding the numbers", "Finding the numbers for" in SRC)


def page(b, relay=True, claude=False, reply=None, log=None, size=(402, 874)):
    ctx = b.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=True, is_mobile=True)
    ctx.add_init_script(CLAUDE if claude else "delete window.claude;")
    if relay is not None:                                # None: the app as it is, opened from disk
        ctx.add_init_script(fakeai.RELAY_SCRIPT if relay else fakeai.NO_RELAY_SCRIPT)
    ctx.add_init_script(fakeai.AI_SCRIPT)                # Ask an agent already allowed
    fakeai.install(ctx, reply=reply, log=log)
    p = ctx.new_page(); errs = []; offsite = []; heads = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    def seen(r):
        if not r.url.startswith("file:") and not r.url.startswith("data:"):
            offsite.append(r.url); heads.append(r.headers)
    p.on("request", seen)
    p.goto("file://" + d + "/mntl-dt.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(800)
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(250)
    return ctx, p, errs, offsite, heads


def words(p, text, wait=900):
    if p.locator("#discardEst").count(): p.click("#discardEst"); p.wait_for_timeout(250)
    if p.locator('[data-logway="estimate"][aria-expanded="false"]').count():
        p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
    p.fill("#estText", text); p.click("#runEst"); p.wait_for_timeout(wait)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    allerrs = []

    # ---- what is sent ----------------------------------------------------
    asked = []
    ctx, p, errs, offsite, heads = page(b, log=asked)
    words(p, "1 costco protein coffee")
    check("a meal the pantry knows sends nothing", not asked and p.locator(".rev-item").count() == 1, str(asked[:1]))
    words(p, "6 oz chicken breast and 1 costco protein coffee")
    check("the rest goes to the relay, one POST", len(asked) == 1 and asked[0]["url"] == fakeai.RELAY, str([a["url"] for a in asked]))
    words(p, "banana")
    q = asked[-1]
    check("what is sent is the food as typed and the country chosen — nothing else",
          sorted(q["body"]) == ["food", "region"] and q["food"] == "banana" and q["region"] == "Canada", json.dumps(q["body"]))
    check("and nothing from the log goes with it",
          SECRET_NOTE not in json.dumps(q["body"]) and "costco" not in json.dumps(q["body"]), json.dumps(q["body"]))
    check("no key and no sign-in go with it either",
          heads and not any("authorization" in h or "cookie" in h for h in heads), str([sorted(h) for h in heads[-1:]]))

    # pantry and finder together, in the order typed — and when the finder
    # fails, the pantry's rows stay and only the rest waits
    words(p, "6 oz chicken breast & 1 costco protein coffee & banana")
    check("a mixed meal reads in the order it was typed, the pantry's row in its place",
          p.evaluate(ROWS) == ["Chicken breast | AI \u00b7 typical", "costco protein coffee | your pantry", "Banana | AI \u00b7 typical"],
          str(p.evaluate(ROWS)))
    allerrs += errs; ctx.close()
    ctx, p, errs, offsite, heads = page(b, reply=lambda q: (429, {"error": "busy"}), log=asked)
    words(p, "6 oz chicken breast & 1 costco protein coffee & banana")
    check("when the finder can't answer, the pantry's row is kept and the rest wait, in order",
          p.evaluate(ROWS) == ["6 oz chicken breast | needs numbers", "costco protein coffee | your pantry", "banana | needs numbers"]
          and "busy" in p.inner_text(".review"), str(p.evaluate(ROWS)))
    allerrs += errs; ctx.close()
    ctx, p, errs, offsite, heads = page(b, log=asked)
    words(p, "banana")                                  # a review open, as the steps below expect

    # a placeholder already in the ledger is answered by the finder too
    p.click("#discardEst"); p.wait_for_timeout(250)
    p.locator("[data-est]").first.click(); p.wait_for_timeout(900)
    check("a waiting row's Tap to estimate asks the finder about just that row",
          p.evaluate(ROWS) == ["Eggs | AI · typical"] and asked[-1]["food"] == "2 eggs", str(p.evaluate(ROWS)))
    p.click("#commitEst"); p.wait_for_timeout(400)
    food = p.evaluate("t=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[t].food", T)
    check("and its answer takes the placeholder's place",
          len(food) == 2 and food[1].get("cal") == 143 and not food[1].get("pending") and food[1].get("est") is True,
          json.dumps(food)[:200])

    # a row logged as the wrong food: corrected by name, and the new name looked up
    p.locator("[data-editrow]").nth(1).click(); p.wait_for_timeout(300)
    p.fill("#reName", "Banana · 1 medium"); p.click("#reFind"); p.wait_for_timeout(900)
    check("edit: Look up this name asks the finder about the new name, amount first",
          p.evaluate(ROWS) == ["Banana | AI · typical"] and asked[-1]["food"] == "1 medium Banana",
          "%s · asked %r" % (p.evaluate(ROWS), asked[-1]["food"]))
    p.click("#commitEst"); p.wait_for_timeout(400)
    food = p.evaluate("t=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[t].food", T)
    check("edit: and its answer takes the old row's place",
          len(food) == 2 and food[1].get("note", "").startswith("Banana") and food[1].get("est") is True
          and food[0].get("note") == SECRET_NOTE, json.dumps(food)[:200])
    allerrs += errs; ctx.close()

    # ---- who answers -----------------------------------------------------
    ctx, p, errs, offsite, _ = page(b, relay=None)
    words(p, "beef wellington")
    check("a copy opened from disk doesn't try the relay, which would refuse it",
          not offsite and p.evaluate(ROWS) == ["beef wellington | needs numbers"], str(offsite[:2]))
    allerrs += errs; ctx.close()

    ctx, p, errs, offsite, _ = page(b, relay=False)
    words(p, "beef wellington")
    check("with no finder at all the food waits, and says why",
          p.evaluate(ROWS) == ["beef wellington | needs numbers"] and "isn’t available in this copy" in p.inner_text(".review"),
          str(p.evaluate(ROWS)))
    if p.locator("#discardEst").count(): p.click("#discardEst"); p.wait_for_timeout(250)
    check("the form says so too", "isn’t available in this copy" in p.inner_text(".est .est-note"),
          p.inner_text(".est .est-note")[:120] if p.locator(".est .est-note").count() else "")
    check("and nothing left the phone at all, from opening the app to here", not offsite, str(offsite[:3]))
    allerrs += errs; ctx.close()

    asked = []
    ctx, p, errs, _, _ = page(b, claude=True, log=asked)
    words(p, "beef wellington")
    check("inside Claude with the relay in reach, the free AI is still the one asked",
          p.evaluate(ROWS) == ["Beef wellington | AI · rough guess"] and len(asked) == 1
          and not p.evaluate("()=>window.__claudeAsked"), str(p.evaluate(ROWS)))
    allerrs += errs; ctx.close()

    ctx, p, errs, _, _ = page(b, claude=True, reply=lambda q: "abort")
    words(p, "beef wellington")
    check("with the relay out of reach, as inside a published artifact, Claude answers",
          p.evaluate(ROWS) == ["Beef wellington | estimated · rough guess"] and p.evaluate("()=>window.__claudeAsked") == 1,
          str(p.evaluate(ROWS)))
    allerrs += errs; ctx.close()

    ctx, p, errs, _, _ = page(b, claude=True, reply=lambda q: (429, {"error": "busy"}))
    words(p, "beef wellington")
    check("but a busy relay is said so, not quietly swapped for Claude",
          "busy" in p.inner_text(".review") and not p.evaluate("()=>window.__claudeAsked"), p.inner_text(".review")[:120])
    allerrs += errs; ctx.close()

    # ---- the small phone -------------------------------------------------
    for w, h in [(360, 800), (402, 874)]:
        ctx, p, errs, _, _ = page(b, size=(w, h), reply=lambda q: (429, {"error": "busy"}) if "lasagne" in q["food"] else None)
        for what, text in [("an answer", "6 oz chicken breast & 1 costco protein coffee"),
                           ("a row left waiting", "1 costco protein coffee & lasagne")]:
            words(p, text)
            sizes = p.eval_on_selector_all(".review button, .review input, .review select",
                "e=>e.filter(x=>x.getClientRects().length).map(x=>[x.textContent.trim().slice(0,16)||x.tagName, Math.round(x.getBoundingClientRect().height), x.tagName==='INPUT'||x.tagName==='SELECT'?parseFloat(getComputedStyle(x).fontSize):99])")
            bad = [s for s in sizes if s[1] < 43.5 or s[2] < 16]
            check("%dx%d: a review with %s has nothing under 44px or zooming" % (w, h, what),
                  sizes and not bad and p.locator(".review").count() == 1, str(bad[:3]) if bad else "%d controls" % len(sizes))
            check("%dx%d: and no sideways scroll" % (w, h) + (" (%s)" % what),
                  p.evaluate("()=>document.documentElement.scrollWidth") <= w)
        allerrs += errs; ctx.close()

    b.close()

for s, n, x in res: print("%-6s %-66s %s" % (s, n, str(x)[:90]))
bad = sum(1 for r in res if r[0] == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
print("pageerrors:", allerrs or "none")
raise SystemExit(1 if (bad or allerrs) else 0)
