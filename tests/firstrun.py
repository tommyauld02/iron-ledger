from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
with sync_playwright() as pw:
    b=pw.chromium.launch()
    # brand new tester: nothing stored at all
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True); ctx.add_init_script("delete window.claude;")
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(900)
    print("fresh install shows tour:", p.evaluate("()=>!!document.querySelector('.welcome')"))
    print("  header:", p.text_content("#buildTag"))
    p.click("#dismissWelcome"); p.wait_for_timeout(400)
    print("dismissed, and stays dismissed after reload:", end=" ")
    p.reload(); p.wait_for_timeout(800)
    print(not p.evaluate("()=>!!document.querySelector('.welcome')"))
    # they can still log straight away
    p.fill("#fCal","400"); p.fill("#fPro","30"); p.fill("#fNote","Test meal")
    p.click("#addFood"); p.wait_for_timeout(400)
    print("tester can log:", p.eval_on_selector_all(".t-row","e=>e.length")==1)
    ctx.close()

    # existing user (Tommy) must never see it
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True); ctx.add_init_script("delete window.claude;")
    p=ctx.new_page(); p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))",
      {"days":{T:{"food":[{"id":"a","cal":500,"pro":40,"note":"Eggs"}],"lifts":[],"updated":1,"goal":G}},
       "moves":None,"goal":G,"region":"United States","pantry":[],"v":1})
    p.reload(); p.wait_for_timeout(800)
    print("existing user sees tour:", p.evaluate("()=>!!document.querySelector('.welcome')"), "(should be False)")
    print("errors:", errs if errs else "none")
    b.close()
