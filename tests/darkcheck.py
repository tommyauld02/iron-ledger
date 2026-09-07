from playwright.sync_api import sync_playwright
import os, datetime, json
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{T:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs and oats"}],
                  "lifts":[{"id":"l","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]}],
                  "updated":1,"goal":G}},
       "moves":None,"goal":G,"region":"United States",
       "pantry":[{"id":"p","name":"protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,"sCal":130,"sPro":30,"aliases":[]}],"v":1}
LOW = """() => {
  const bad = [];
  const lum = c => { const m=c.match(/\\d+/g); if(!m) return null;
    const [r,g,b]=m.slice(0,3).map(n=>{n/=255; return n<=.03928? n/12.92 : Math.pow((n+.055)/1.055,2.4);});
    return .2126*r+.7152*g+.0722*b; };
  document.querySelectorAll('main *, .topbar *, .tabs *, .undobar *').forEach(el=>{
    if(!el.textContent.trim() || el.children.length) return;
    const s=getComputedStyle(el); const f=lum(s.color);
    let p=el, bgc=null;
    while(p && p!==document.documentElement){ const c=getComputedStyle(p).backgroundColor;
      if(c && !c.includes('rgba(0, 0, 0, 0)')){ bgc=c; break; } p=p.parentElement; }
    const bl=lum(bgc||'rgb(255,255,255)');
    if(f===null||bl===null) return;
    const ratio=(Math.max(f,bl)+.05)/(Math.min(f,bl)+.05);
    const size=parseFloat(s.fontSize), bold=parseInt(s.fontWeight)>=700;
    const need=(size>=24||(size>=18.66&&bold))?3:4.5;
    if(ratio<need) bad.push(el.textContent.trim().slice(0,28)+' | '+ratio.toFixed(2)+':1 need '+need);
  });
  return [...new Set(bad)];
}"""
FAILS=[]

with sync_playwright() as pw:
    b=pw.chromium.launch()
    for scheme in ["light","dark"]:
        ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True, color_scheme=scheme)
        ctx.add_init_script("delete window.claude;")
        p=ctx.new_page(); errs=[]
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(400)
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
        p.reload(); p.wait_for_timeout(800)
        print("\n=== %s ===" % scheme.upper())
        for tab in ["macros","gym","pantry","coach","log"]:
            p.click('.tabs button[data-tab="%s"]'%tab); p.wait_for_timeout(450)
            # the Coach library only exists once a day card is open
            if tab=="coach" and p.locator("[data-openday]").count():
                p.locator("[data-openday]").first.click(); p.wait_for_timeout(400)
            low=p.evaluate(LOW)
            print("  %-8s contrast issues: %s" % (tab, low if low else "none"))
            if low: FAILS.append("%s/%s: %s" % (scheme, tab, str(low)[:90]))
            bg=p.evaluate("()=>getComputedStyle(document.body).backgroundColor")
            if tab=="macros": print("  body bg:", bg)
        print("  errors:", errs if errs else "none")
        if errs: FAILS.append("%s: page errors %s" % (scheme, str(errs[:2])[:80]))
        ctx.close()
    b.close()

print('\n' + "=== VERDICT ===")
for x in FAILS: print("  FAIL", x)
print("  %d contrast problems" % len(FAILS))
raise SystemExit(1 if FAILS else 0)
