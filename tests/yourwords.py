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
STORE={"days":{T:{"food":[],"lifts":[],"updated":1,"goal":G}},"moves":None,"goal":G,
       "region":"United States","pantry":[],"v":1}
QUERIES=[
 "6 ounces of top sirloin",
 "6 oz top sirloin and 200 grams of white rice",
 "white rice",
 "a steak and some rice",
 "two eggs, toast and a coffee",
 "chicken and rice",
]
with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")   # offline, as on his home screen
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(800)
    print("OFFLINE (home screen) — typed into the 'Don't know the numbers?' box:\n")
    for q in QUERIES:
        words(p); p.fill("#estText", q); p.click("#runEst"); p.wait_for_timeout(600)
        rows=p.eval_on_selector_all(".rev-item",
          "e=>{const amt=x=>{const g=x.querySelector('[data-ig]'),t=x.querySelector('.amt');if(!g) return t.textContent.trim();const pre=t.querySelector('.pre'),u=t.querySelector('[data-iu]'),s=t.querySelector('.src-tag');return ((pre?pre.textContent:'')+g.value+' '+(u?u.value:'')+' '+(s?s.textContent:'')).trim();};return e.map(x=>x.querySelector('.food').textContent+': '+x.querySelector('[data-ic]').value+' kcal, '+x.querySelector('[data-ip]').value+' g  ('+amt(x)+')');}")
        total=p.evaluate("()=>{const h=document.querySelector('.review > header span');return h?h.textContent:'—';}")
        print('  "%s"' % q)
        for r in rows: print("      "+r)
        print("      TOTAL: %s\n" % total)
        if rows: p.click("#discardEst"); p.wait_for_timeout(250)
    print("errors:", errs if errs else "none")
    b.close()
