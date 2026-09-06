from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd(); T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
S={"days":{T:{"food":[],"lifts":[],"updated":1,"goal":G}},"moves":None,"goal":G,
   "region":"United States","pantry":[],"v":1}
with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", S)
    p.reload(); p.wait_for_timeout(800)
    p.fill("#estText","chicken and rice"); p.click("#runEst"); p.wait_for_timeout(700)
    # edit an assumed number before committing, the way he would
    p.fill('[data-ic="1"]',"410"); p.fill('[data-ip="1"]',"8"); p.wait_for_timeout(200)
    print("header after editing rice up:", p.text_content(".review > header span"))
    p.click("#commitEst"); p.wait_for_timeout(600)
    print("committed rows:", p.eval_on_selector_all(".t-row .t-food .nm","e=>e.map(x=>x.textContent.trim())"))
    print("day total:", p.text_content(".t-total .t-cal b"), "kcal /", p.text_content(".t-total .t-pro b"), "g")
    print("verdict colour on calendar:")
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
    print("   today is", "MISS" if p.eval_on_selector_all(".cal-cell.is-today.miss","e=>e.length") else ("HIT" if p.eval_on_selector_all(".cal-cell.is-today.hit","e=>e.length") else "neutral"))
    print("errors:", errs if errs else "none")
    b.close()
