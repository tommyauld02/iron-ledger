from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{T:{"food":[
  {"id":"r1","cal":205,"pro":4,"note":"White rice, cooked · 158 g","est":True},
  {"id":"r2","cal":489,"pro":57,"note":"Costco top sirloin · 6 oz","est":True},
  {"id":"r3","cal":190,"pro":21,"note":"Protein bar"}],
  # a finished movement too, so the folded card is measured on every phone
  "lifts":[{"id":"l1","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]},
           {"id":"l2","cat":"back","movement":"Lat Pulldown","sets":[{"w":120,"r":10}],"doneAt":1,"lapMs":452000,"closed":True}],
  "updated":1,"goal":G}},
 "moves":None,"goal":G,"region":"United States",
 "pantry":[{"id":"p1","name":"protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,
            "sCal":130,"sPro":30,"aliases":[]}],"v":1}

# every device the app realistically has to fit
# 402x874 / 440x956 are the logical sizes the 16 Pro and Pro Max report; the
# 17 Pro shares the 6.3" panel and reports the same. If Tommy's phone ever
# disagrees, read window.innerWidth off the real device and correct these.
DEVICES=[("iPhone SE",320,568),("iPhone 13 mini",375,812),("iPhone 15",393,852),
         ("iPhone 17 Pro",402,874),("iPhone 17 Pro Max",440,956),
         ("iPhone 15 Pro Max",430,932),("landscape 17 Pro",874,402)]
TABS=["macros","pantry","gym","coach","log"]

# iOS zooms the page whenever you focus a field smaller than 16px, and never zooms back
ZOOM="""()=>{const bad=[];
  document.querySelectorAll('input,select,textarea').forEach(e=>{
    const r=e.getBoundingClientRect(); if(!r.width&&!r.height) return;
    const fs=parseFloat(getComputedStyle(e).fontSize);
    if(fs<16) bad.push((e.id||e.className||e.tagName)+' '+fs+'px');});
  return bad;}"""
OVERFLOW="""()=>{const bad=[];
  document.querySelectorAll('#view *,.topbar *,.tabs *').forEach(e=>{
    const r=e.getBoundingClientRect();
    if(r.width&&(r.left<-1||r.right>window.innerWidth+1))
      bad.push((e.className||e.tagName)+' '+Math.round(r.left)+'..'+Math.round(r.right));});
  return bad.slice(0,6);}"""
SMALL="""()=>{const bad=[];
  document.querySelectorAll('button,select,input[type=file],[role=button]').forEach(b=>{
    const r=b.getBoundingClientRect();
    if(r.width&&r.height&&(r.height<44||r.width<44)&&!b.className.includes('cal-cell'))
      bad.push((b.id||b.className||'btn')+' '+Math.round(r.width)+'x'+Math.round(r.height));});
  return [...new Set(bad)];}"""

FAILS=[]

with sync_playwright() as pw:
    b=pw.chromium.launch()
    print("=== fit and field sizes, per device ===")
    for name,w,h in DEVICES:
        ctx=b.new_context(viewport={"width":w,"height":h}, has_touch=True, is_mobile=True,
                          device_scale_factor=3)
        p=ctx.new_page(); errs=[]
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(250)
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
        p.reload(); p.wait_for_timeout(700)
        zoom=set(); over=[]; small=set()
        for t in TABS:
            p.click('.tabs button[data-tab="%s"]'%t); p.wait_for_timeout(350)
            if t=="coach" and p.locator("[data-openday]").count():
                p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
            for x in p.evaluate(ZOOM): zoom.add(x)
            for x in p.evaluate(SMALL): small.add(x)
            o=p.evaluate(OVERFLOW)
            if o: over.append(t+": "+"; ".join(o))
        hscroll=p.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
        # Rules 4 and 5 are enforced here. Reporting them and exiting 0 made
        # this a report, not a gate.
        if hscroll: FAILS.append("%s: page scrolls sideways" % name)
        if over:    FAILS.append("%s: off-screen %s" % (name, "; ".join(over)[:80]))
        if small:   FAILS.append("%s: under 44px %s" % (name, "; ".join(sorted(small))[:80]))
        if zoom:    FAILS.append("%s: iOS-zoom fields %s" % (name, "; ".join(sorted(zoom))[:80]))
        if errs:    FAILS.append("%s: page errors %s" % (name, str(errs[:2])[:80]))
        print("\n  %-18s %dx%d" % (name,w,h))
        print("     horizontal scroll:", "YES — BAD" if hscroll else "no")
        print("     off-screen:", over or "none")
        print("     under 44px:", sorted(small) or "none")
        print("     fields that trigger iOS zoom:", sorted(zoom) or "none")
        print("     errors:", errs or "none")
        ctx.close()
    b.close()

print('\n' + "=== VERDICT ===")
for x in FAILS: print("  FAIL", x)
print("  %d device/size combinations, %d problems" % (len(DEVICES), len(FAILS)))
raise SystemExit(1 if FAILS else 0)
