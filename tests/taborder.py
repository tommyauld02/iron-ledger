from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{T:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs"}],"lifts":[],"updated":1,"goal":G}},
       "moves":None,"goal":G,"region":"United States",
       "pantry":[{"id":"p","name":"protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,"sCal":130,"sPro":30,"aliases":[]}],"v":1}
with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
    p.reload(); p.wait_for_timeout(800)
    print("tab order:", p.eval_on_selector_all(".tabs button","e=>e.map(x=>x.textContent)"))
    print("header build:", p.text_content("#buildTag"))
    # every tab still routes to the right screen
    checks=[("macros","addFood"),("pantry","savePan"),("gym","addLift"),("coach","addDay"),("log","prevYear")]
    for name, marker in checks:
        p.click('.tabs button[data-tab="%s"]'%name); p.wait_for_timeout(450)
        sel = p.evaluate("n=>document.querySelector('.tabs button[data-tab='+n+']').getAttribute('aria-selected')", name)
        ok  = p.evaluate("m=>!!document.getElementById(m)", marker)
        print("  %-7s selected=%s  renders its screen=%s" % (name, sel, ok))
    print("errors:", errs if errs else "none")
    b.close()
