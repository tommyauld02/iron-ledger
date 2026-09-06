from playwright.sync_api import sync_playwright
import os, json, datetime
d=os.getcwd(); T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{T:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs and oats"},
                          {"id":"b","cal":200,"pro":20,"note":"Protein bar"}],
                  "lifts":[{"id":"l1","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10},{"w":155,"r":8}]}],
                  "updated":1,"goal":G}},
       "moves":None,"goal":G,"region":"United States",
       "pantry":[{"id":"p1","name":"costco protein coffee","serveQty":1,"serveUnit":"bottle",
                  "serveG":None,"sCal":130,"sPro":30,"aliases":[]}],"v":1}
MEASURE=open('audit.py').read().split('MEASURE = """')[1].split('"""')[0]

with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(400)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", store)
    p.reload(); p.wait_for_timeout(800)

    print("=== REMAINING SMALL TARGETS ===")
    bad=[]
    for tab in ["macros","gym","pantry","coach","log"]:
        p.click('.tabs button[data-tab="%s"]'%tab); p.wait_for_timeout(450)
        # the Coach library only exists once a day card is open
        if tab=="coach" and p.locator("[data-openday]").count():
            p.locator("[data-openday]").first.click(); p.wait_for_timeout(400)
        for c in p.evaluate(MEASURE):
            if c["small"] and "cal-cell" not in c["id"]:
                bad.append("  %-8s %-22s %dx%d" % (tab, c["id"][:22], c["w"], c["h"]))
    print("\n".join(sorted(set(bad))) or "  none")

    print("\n=== UNDO ===")
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(400)
    p.eval_on_selector_all(".t-del","els=>els[1].click()"); p.wait_for_timeout(400)
    print("  after deleting food row:", p.eval_on_selector_all(".t-row","e=>e.length"), "rows |",
          "bar:", p.text_content("#undoLabel"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    print("  after undo:", p.eval_on_selector_all(".t-row","e=>e.length"), "rows |",
          "order preserved:", p.eval_on_selector_all(".t-row .t-food .nm","e=>e.map(x=>x.textContent.trim())"))

    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(450)
    p.eval_on_selector_all(".set","els=>els[0].click()"); p.wait_for_timeout(400)
    print("  set deleted →", p.text_content("#undoLabel"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    print("  sets restored:", p.eval_on_selector_all(".set","e=>e.map(x=>x.textContent)"))
    p.click("[data-rmlift]"); p.wait_for_timeout(400)
    print("  movement deleted →", p.text_content("#undoLabel"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    print("  movement restored:", p.eval_on_selector_all(".lift h3","e=>e.map(x=>x.textContent)"))

    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(450)
    p.click("[data-rmpan]"); p.wait_for_timeout(400)
    print("  pantry deleted →", p.text_content("#undoLabel"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    print("  pantry restored:", p.evaluate("() => JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length"), "item")
    print("\npageerrors:", errs if errs else "none")
    b.close()
