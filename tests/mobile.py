from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{T:{"food":[
  {"id":"r1","cal":205,"pro":4,"note":"White rice, cooked · 158 g","est":True},
  {"id":"r2","cal":489,"pro":57,"note":"Costco top sirloin · 6 oz","est":True},
  {"id":"r3","cal":190,"pro":21,"note":"Protein bar"}],
  # a finished movement too, so the folded card is measured on every phone
  "gymNote":"Hotel gym downtown — dumbbells only up to 50, no cable stack at all",
  "lifts":[{"id":"l1","cat":"back","movement":"Barbell Row","note":"Last set was really hard, grip gave out before the back did",
            "sets":[{"w":135,"r":10,"tech":"restpause"}]},
           {"id":"l2","cat":"back","movement":"Lat Pulldown","sets":[{"w":120,"r":10}],"doneAt":1,"lapMs":452000,"closed":True},
           {"id":"l3","cat":"back","movement":"Seated Cable Row","sets":[]}],
  "cardio":[{"id":"c1","type":"Incline walk on the treadmill","min":30,"dist":3.1,"cal":265,"t":1}],
  "gym":"gA","updated":1,"goal":G},
  # last time, so every card carries its set to beat, at its longest: a tag
  # on both sides of a beaten line, and one still to beat
  (datetime.date.today()-datetime.timedelta(days=3)).isoformat():{"food":[],"updated":1,"goal":G,"gym":"gA",
  "lifts":[{"id":"p1","cat":"back","movement":"Barbell Row","sets":[{"w":125,"r":10,"tech":"restpause"}]},
           {"id":"p2","cat":"back","movement":"Lat Pulldown","sets":[{"w":110,"r":10}]},
           {"id":"p3","cat":"back","movement":"Seated Cable Row","sets":[{"w":225,"r":12,"tech":"restpause"}]}]}},
 "cardioTypes":["Incline walk on the treadmill","Bike"],
 "gyms":[{"id":"gA","name":"Apartment building gym","tag":"APTGYM24"},{"id":"g24","name":"24 Hour Fitness","tag":"24"}],"gymLast":"gA",
 "moves":None,"coachOn":True,"goal":G,"region":"United States",
 # sorted and not, so the section tabs, headings and Move / Sort are measured
 "pantry":[{"id":"p1","name":"protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,
            "sCal":130,"sPro":30,"aliases":[]},
           {"id":"p2","name":"Costco rotisserie chicken salad","serveQty":1,"serveUnit":"container","serveG":None,
            "sCal":420,"sPro":38,"aliases":[],"sec":"lunch"},
           {"id":"p3","name":"Ice cream sandwich","serveQty":1,"serveUnit":"piece","serveG":None,
            "sCal":180,"sPro":3,"aliases":[],"sec":"desserts"}],"v":1}

# every device the app realistically has to fit
# 402x874 / 440x956 are the logical sizes the 16 Pro and Pro Max report; the
# 17 Pro shares the 6.3" panel and reports the same. If Tommy's phone ever
# disagrees, read window.innerWidth off the real device and correct these.
DEVICES=[("iPhone SE",320,568),("iPhone 13 mini",375,812),("iPhone 15",393,852),
         ("iPhone 17 Pro",402,874),("iPhone 17 Pro Max",440,956),
         ("iPhone 15 Pro Max",430,932),("landscape 17 Pro",874,402)]
# Macros three times: folded, then with each way in open.
TABS=["macros","macros:numbers","macros:estimate","pantry","gym","cardio","coach","log"]

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
            p.click('.tabs button[data-tab="%s"]'%t.split(":")[0]); p.wait_for_timeout(350)
            if ":" in t:
                p.click('[data-logway="%s"]'%t.split(":")[1]); p.wait_for_timeout(300)
                if not p.locator("#fCal" if t.endswith("numbers") else '[data-ef="0"]').count():
                    FAILS.append("%s: %s box not on screen to measure" % (name, t))
            if t=="coach" and p.locator("[data-openday]").count():
                p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
            # the set-to-beat lines are what could burst a narrow card, so a
            # fixture that stops painting them must say so, not pass on nothing
            if t=="gym" and p.eval_on_selector_all(".lift .beat","e=>e.length")<3:
                FAILS.append("%s: set-to-beat lines not on screen to measure" % name)
            if t=="gym" and not p.eval_on_selector_all(".day-note, .lift .lift-note","e=>e.length")>=2:
                FAILS.append("%s: notes not on screen to measure" % name)
            if t=="cardio" and not p.eval_on_selector_all(".cardio-card","e=>e.length"):
                FAILS.append("%s: no cardio session on screen to measure" % name)
            if t=="pantry" and p.eval_on_selector_all("[data-pantab]","e=>e.length")<6:
                FAILS.append("%s: pantry section tabs not on screen to measure" % name)
            # A stray "+" once turned a whole paragraph of the pantry form into
            # the word NaN, and nothing measuring sizes or colours could see it.
            # A broken expression shows up as text, so look for the text — node
            # by node: innerText runs "NaN" into the button after it as
            # "NaNSAVE TO PANTRY", and a word-boundary search then finds nothing.
            junk=p.evaluate("""()=>{const w=document.createTreeWalker(document.getElementById('view'),NodeFilter.SHOW_TEXT),bad=[];let n;
              while((n=w.nextNode())) if(/(^|[^A-Za-z])(NaN|undefined)([^A-Za-z]|$)/.test(n.nodeValue)) bad.push(n.nodeValue.trim().slice(0,30));
              return bad.join(' | ');}""")
            if junk: FAILS.append("%s: the %s tab shows %s" % (name, t, junk))
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
