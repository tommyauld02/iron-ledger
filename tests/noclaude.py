from playwright.sync_api import sync_playwright
import os, datetime

# The Macros tab now opens on the fill-in table; the plain-words box is behind
# "Or just describe it in words". This suite is about what the resolver makes
# of a phrase, not about how it was entered, so it opens the box and types.
def words(p):
    if not p.locator("#estText").count():
        p.click("#estSwap"); p.wait_for_timeout(250)
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
S={"days":{T:{"food":[{"id":"pp","cal":0,"pro":0,"note":"leftover curry","pending":True}],
              "lifts":[],"updated":1,"goal":G}},
   "moves":None,"goal":G,"region":"United States","pantry":[],"v":1}
with sync_playwright() as pw:
    b=pw.chromium.launch()
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")   # a tester with no Claude at all
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", S)
    p.reload(); p.wait_for_timeout(800)
    print("NO CLAUDE ACCOUNT, plain browser\n")
    print("  no Claude references left on screen:",
          "inside Claude" not in p.eval_on_selector("main","e=>e.textContent"))
    print("  pending chip label:", p.eval_on_selector(".pending-chip","e=>e.textContent"))
    p.click(".pending-chip"); p.wait_for_timeout(600)
    # build 18: the chip always runs the estimate, offline table included, and
    # leaves the placeholder alone if nothing can price it
    print("  tapping it opens the review:", p.locator(".review").count()==1)
    print("  placeholder is NOT thrown away:",
          p.eval_on_selector_all(".t-row","e=>e.length")==1)
    p.fill(".rev-item input >> nth=0","650"); p.fill(".rev-item input >> nth=1","35")
    p.wait_for_timeout(300)
    p.click("#commitEst"); p.wait_for_timeout(500)
    print("  numbers typed into the review:",
          p.eval_on_selector_all(".t-row .t-food .nm","e=>e.map(x=>x.textContent.trim())"))
    # estimator still works locally
    words(p); p.fill("#estText","chicken and rice"); p.click("#runEst"); p.wait_for_timeout(600)
    print("  estimator (offline table):", p.text_content(".review > header span"))
    p.click("#commitEst"); p.wait_for_timeout(400)
    print("  day total:", p.text_content(".t-total .t-cal b"), "kcal /", p.text_content(".t-total .t-pro b"), "g")
    # pantry photo button correctly absent
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
    print("  photo button hidden:", not p.evaluate("()=>!!document.getElementById('shotBtn')"))
    print("  pantry still usable:", p.evaluate("()=>!!document.getElementById('savePan')"))
    print("\n  errors:", errs if errs else "none")
    b.close()
