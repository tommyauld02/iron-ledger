"""The keyboard and the scroll, on every tab, as a phone does them.

The owner (b87): "when new updates drop there seem to be keyboard and scroll
bugs that come back." They came back because only Macros' two boxes were ever
typed into under a keyboard (sweep, *THE KEYBOARD*), and nothing scrolled the
other tabs at all. Written the day it found two that had been shipping:

  - Find in your pantry sits in the dock, and the dock hides while typing, so
    the field being typed in vanished mid-word.
  - The room under the page sat below the dock. Put the keyboard away near the
    foot of a page and the dock hung halfway up the screen over an empty
    stretch, on Macros, the checklist, Add movement, Choose gym and Cardio.

So every field that a person types into is tapped, a keyboard is raised (the
same stand-in for the visual viewport as sweep's, since Chromium has none),
and it must be on screen above the keyboard, uncovered, and take what is
typed. Then the keyboard goes, and the dock must be back at the bottom of the
screen — right then, and at the very end of the page. In the iPhone app
(the bridge stood in for) the page must add no room of its own.

Then every tab is scrolled from top to bottom, folded and with each box open:
the dock stays at the bottom the whole way, nothing runs off the side, and the
last thing on the page ends above the dock rather than under it.

On two phones: the owner's (402x874) and the smallest (320x568). Exits
non-zero on any failure or page error: it is a gate.
"""
import answered   # every page has said 18 or older: tests/answered.py
import rooms      # Pantry is a section of Macros since b99: tests/rooms.py
from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d
URL="file://"+d+"/mntl-dt.html"

T=datetime.date.today(); Ts=T.isoformat()
def ago(n): return (T-datetime.timedelta(days=n)).isoformat()
G={"cal":{"dir":"-","v":2200},"pro":{"dir":"+","v":180}}
# Enough on every tab that its pages run past one screen.
STORE={"days":{
  Ts:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs"},{"id":"b","cal":300,"pro":30,"note":"Chicken"}],
      "goal":G,"gym":"gA","supps":{"s1":True},
      "lifts":[{"id":"l1","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10},{"w":155,"r":8}]},
               {"id":"l2","cat":"back","movement":"Lat Pulldown","sets":[{"w":120,"r":10}]},
               {"id":"l3","cat":"back","movement":"Seated Cable Row","sets":[{"w":100,"r":12}]}],
      "cardio":[{"id":"c1","type":"Incline walk","min":30,"dist":2,"cal":250,"t":1}]},
  ago(7):{"food":[],"goal":G,"gym":"gA","workoutMs":3600000,
          "lifts":[{"id":"p1","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]}]}},
 "gyms":[{"id":"gA","name":"Apartment gym","tag":"APT"},{"id":"g24","name":"24 Hour Fitness","tag":"24"}],
 "gymLast":"gA","gymAsked":True,"week":[None,"back","legs",None,"push",None,None],
 "cardioTypes":["Incline walk","Bike"],"coachOn":True,"seen":True,
 "moves":{"back":["Barbell Row","Lat Pulldown","Seated Cable Row","Hammer Curl"]},"movesOwned":True,
 "goal":G,"region":"United States","v":1,
 "supps":[{"id":"s1","name":"Creatine","dose":"5 g"},{"id":"s2","name":"Fish oil","dose":"2 caps"}],
 "pantry":[{"id":"p%d"%i,"name":n,"serveQty":1,"serveUnit":"piece","serveG":None,"sCal":c,"sPro":pr,"aliases":[],"secs":s}
   for i,(n,c,pr,s) in enumerate([("Eggs",72,6,["breakfast"]),("Bacon",43,3,["breakfast"]),
     ("Chicken breast",165,31,["lunch","dinner"]),("Rice",205,4,["lunch"]),("Greek yogurt",100,17,["snacks"]),
     ("Protein bar",190,20,["snacks"]),("Steak",280,26,["dinner"])])]}
# A dozen check-ins on Progress (b90), so its list runs past one screen too.
for _i in range(12):
    STORE["days"].setdefault(ago(7*_i+1), {"food":[],"goal":G})["prog"]={"at":1,"note":"Week %d"%_i}

# Stamped with this build, so What's new never opens over the page. In the app
# pass the log arrives a beat later through the bridge, and the sheet could
# open after go() had looked for it and sit over every tap that followed.
import re
STORE["build"]=re.search(r'var BUILD = "([^"]+)"', open(os.path.join(os.getcwd(),"mntl-dt.html"),encoding="utf-8").read()).group(1)

# The visual viewport, stood in for and shrunk the way an iPhone's is (sweep's).
KBFAKE = """(()=>{const t=new EventTarget(); t.offsetTop=0; t.scale=1;
  Object.defineProperty(t,'height',{get(){return innerHeight-(window.__kbH||0);}});
  Object.defineProperty(window,'visualViewport',{configurable:true,get:()=>t});
  window.__kb=(h)=>{window.__kbH=h; t.dispatchEvent(new Event('resize'));};})()"""
NATIVEFAKE = """window.Capacitor={isNativePlatform:()=>true,getPlatform:()=>'ios',
  nativePromise:(p,m,o)=>{const k='__pref_'+(o&&o.key);
    if(p==='Preferences'&&m==='get') return Promise.resolve({value:sessionStorage.getItem(k)});
    if(p==='Preferences'&&m==='set'){sessionStorage.setItem(k,o.value); return Promise.resolve({});}
    if(p==='Preferences'&&m==='remove'){sessionStorage.removeItem(k); return Promise.resolve({});}
    return Promise.reject(new Error(p+'.'+m+' is not stood in for'));}};"""

# Every field a person types into: where it is, and the presses that reveal it.
# "__new" picks + New movement in the list, which is what shows its name field.
FIELDS=[
 ("macros: Log numbers",        "macros", ['#plate', '[data-logway="numbers"]'], "#fCal"),
 ("macros: Ask an agent",       "macros", ['#plate', '[data-logway="estimate"]'], "#estText"),
 ("pantry: Find in your pantry","pantry", [], "#panFind"),
 ("pantry: a new food (sheet)", "pantry", ["#panNew"], "#panName"),
 ("pantry: the checklist",      "pantry", ["#suppToggle"], "#suppNameIn"),
 ("pantry: renaming on it",     "pantry", ["#suppToggle", "[data-editsupp]"], "#suppRename"),
 ("pantry: a new section",      "pantry", ["#editPanSecs"], "#newSecName"),
 ("pantry: Build a meal",       "pantry", ["#combStart"], "#combName"),
 ("gym: a new movement",        "gym",    ['#ctxMain [data-gymway="move"]', "__new"], "#mNew"),
 ("gym: a new gym",             "gym",    ['#ctxMain [data-gymway="gym"]', "#addGymChip"], "#newGymName"),
 ("gym: a note for the day",    "gym",    ["#dayNoteAdd"], "#dayNoteIn"),
 ("gym: a note on a movement",  "gym",    ["[data-liftnote]"], "#liftNoteIn"),
 ("gym: a new split",           "gym",    ["#addSplitChip"], "#newSplitName"),
 ("gym: reps (set sheet)",      "gym",    ['[data-addset="0"]'], "#seR"),
 ("cardio: by hand",            "cardio", ["#cardioByHand"], "#cMin"),
 ("coach: renaming a day",      "coach",  ["[data-openday]", "[data-renameday]"], "#rtRename"),
 ("progress: weight (sheet)",   "progress", ["#pgNew"], "#pgW"),
 ("progress: a note (sheet)",   "progress", ["#pgNew"], "#pgNote"),
]
# Every tab, folded and with each thing that opens a long box opened.
SCREENS=[
 ("macros",                  "macros", []),
 ("macros, Log numbers open","macros", ['#plate', '[data-logway="numbers"]']),
 ("macros, Ask an agent open","macros", ['#plate', '[data-logway="estimate"]']),
 ("pantry",                  "pantry", []),
 ("pantry, list folded",     "pantry", ['[data-pantab="all"]']),
 ("pantry, checklist open",  "pantry", ["#suppToggle"]),
 ("gym",                     "gym",    []),
 ("gym, Choose gym open",    "gym",    ['#ctxMain [data-gymway="gym"]']),
 ("gym, Add movement open",  "gym",    ['#ctxMain [data-gymway="move"]']),
 ("gym, rest timer open",    "gym",    ['#ctxMain [data-gymway="rest"]']),
 ("gym, locked in (recovery)","gym",   ["#lockDay"]),
 ("cardio",                  "cardio", []),
 ("coach",                   "coach",  ["[data-openday]"]),
 ("progress",                "progress", []),
 ("log",                     "log",    []),
]
PHONES=[("17 Pro", 402, 874, 336), ("SE", 320, 568, 253)]   # name, width, height, keyboard

FIELD="""(f)=>{const e=document.querySelector(f); if(!e) return null; const r=e.getBoundingClientRect();
  const x=r.left+Math.min(24,r.width/2), y=r.top+r.height/2, hit=document.elementFromPoint(x,y);
  return {top:Math.round(r.top), bot:Math.round(r.bottom), vis:e.checkVisibility({visibilityProperty:true}),
          hit:!!hit&&(hit===e||e.contains(hit)), focused:document.activeElement===e}}"""
DOCK="""()=>{const d=document.querySelector('.dock'), r=d.getBoundingClientRect();
  return {top:Math.round(r.top), bot:Math.round(r.bottom), vis:getComputedStyle(d).visibility}}"""
HIGH="()=>document.documentElement.scrollHeight"
ROOM="()=>document.documentElement.classList.contains('kb-room')"
# The bottom of the last thing drawn in the page, against the top of the dock.
LAST="""()=>{let low=0; document.querySelectorAll('#view *').forEach(e=>{
    if(e.closest('.sheet')) return; const r=e.getBoundingClientRect();
    if(r.width&&r.height&&getComputedStyle(e).visibility!=='hidden') low=Math.max(low,r.bottom);});
  return {last:Math.round(low), dock:Math.round(document.querySelector('.dock').getBoundingClientRect().top)}}"""
WIDE="()=>document.documentElement.scrollWidth>innerWidth+1"

res=[]
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))

def opened(b, w, h, native=False):
    ctx=b.new_context(viewport={"width":w,"height":h}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;"); ctx.add_init_script(KBFAKE)
    if native: ctx.add_init_script(NATIVEFAKE)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(URL); p.wait_for_timeout(300)
    p.evaluate("""s=>{const j=JSON.stringify(s); localStorage.setItem('iron-ledger-v1',j);
                     sessionStorage.setItem('__pref_iron-ledger-v1',j);}""", STORE)
    return ctx, p, errs

def go(p, tab, steps):
    p.goto(URL); p.wait_for_timeout(700)
    p.wait_for_selector('.tabs button[data-tab="%s"]' % ("macros" if tab == "pantry" else tab), timeout=10000)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    rooms.go(p, tab); p.wait_for_timeout(350)
    for s in steps:
        if s=="__new": p.select_option("#mSel","__new"); p.wait_for_timeout(200); continue
        p.locator(s).first.click(); p.wait_for_timeout(350)
    p.evaluate("()=>document.activeElement&&document.activeElement.blur&&document.activeElement.blur()")
    p.wait_for_timeout(100)

with sync_playwright() as pw:
    b=pw.chromium.launch()
    allerrs=[]
    for phone, W, H, KB in PHONES:
        band=H-KB
        # ---------- every field, under a keyboard, on the web ----------
        ctx, p, errs = opened(b, W, H)
        for name, tab, steps, field in FIELDS:
            tag="%s, %s" % (phone, name)
            try:
                go(p, tab, steps)
                p.locator(field).scroll_into_view_if_needed(); p.wait_for_timeout(150)
                high=p.evaluate(HIGH)
                p.locator(field).tap(); p.wait_for_timeout(60)
                p.evaluate("h=>window.__kb(h)", KB); p.wait_for_timeout(800)
                f=p.evaluate(FIELD, field)
                check("keyboard (%s): the field is on screen above the keyboard" % tag,
                      bool(f) and f["vis"] and f["top"]>=0 and f["bot"]<=band,
                      f and "%s-%s, keyboard at %s, visible %s" % (f["top"], f["bot"], band, f["vis"]))
                check("keyboard (%s): nothing covers it, and it has the cursor" % tag,
                      bool(f) and f["hit"] and f["focused"], str(f))
                check("keyboard (%s): nothing runs off the side, so the page is not zoomed out" % tag,
                      not p.evaluate(WIDE), "%s wide on a %s phone" % (p.evaluate("()=>document.documentElement.scrollWidth"), W))
                check("keyboard (%s): the page never got shorter" % tag, p.evaluate(HIGH)>=high,
                      "%s then %s" % (high, p.evaluate(HIGH)))
                before=p.input_value(field)
                p.keyboard.type("12"); p.wait_for_timeout(120)
                # Wherever the tap put the caret: in a field with text in it,
                # that is inside the word on one platform's fonts and at its end
                # on another's (CI's Linux put "12" into "Creatine" mid-word).
                after=p.input_value(field)
                # A rename field that selects its name on focus is replaced instead.
                check("keyboard (%s): what is typed goes in" % tag,
                      "12" in after and (len(after)==len(before)+2 or after=="12"),
                      "%r then %r" % (before, after))
                y=p.evaluate("()=>Math.round(scrollY)")
                p.evaluate("()=>{document.activeElement.blur(); window.__kb(0);}"); p.wait_for_timeout(400)
                dk=p.evaluate(DOCK)
                check("keyboard (%s): put away, the dock is back at the bottom" % tag,
                      dk["vis"]=="visible" and dk["bot"]==H, "%s, page at %s then %s" % (dk, y, p.evaluate("()=>Math.round(scrollY)")))
                p.evaluate("()=>window.scrollTo(0, document.documentElement.scrollHeight)"); p.wait_for_timeout(400)
                dk=p.evaluate(DOCK)
                check("keyboard (%s): and still at the bottom at the very end of the page" % tag,
                      dk["bot"]==H, str(dk))
                p.evaluate("()=>window.scrollTo(0, 0)"); p.wait_for_timeout(300)
                check("keyboard (%s): the room under the page goes once scrolled away" % tag,
                      not p.evaluate(ROOM))
            except Exception as e:
                check("keyboard (%s): could be reached and typed in" % tag, False, str(e).splitlines()[0][:140])
        allerrs += errs; ctx.close()

        # ---------- in the iPhone app the WebView makes its own room ----------
        ctx, p, errs = opened(b, W, H, native=True)
        for name, tab, steps, field in FIELDS:
            tag="%s app, %s" % (phone, name)
            try:
                go(p, tab, steps)
                p.locator(field).scroll_into_view_if_needed(); p.wait_for_timeout(150)
                high=p.evaluate(HIGH)
                p.locator(field).tap(); p.wait_for_timeout(60)
                p.evaluate("h=>window.__kb(h)", KB); p.wait_for_timeout(700)
                check("keyboard (%s): no room of the page's own" % tag,
                      not p.evaluate(ROOM) and p.evaluate(HIGH)==high, "%s then %s" % (high, p.evaluate(HIGH)))
                f=p.evaluate(FIELD, field)
                check("keyboard (%s): the field stays visible, never hidden with the dock" % tag,
                      bool(f) and f["vis"], str(f))
                p.evaluate("()=>{document.activeElement.blur(); window.__kb(0);}"); p.wait_for_timeout(400)
                p.evaluate("()=>window.scrollTo(0, document.documentElement.scrollHeight)"); p.wait_for_timeout(400)
                dk=p.evaluate(DOCK)
                check("keyboard (%s): put away, the dock is at the bottom, even at the end" % tag,
                      dk["vis"]=="visible" and dk["bot"]==H, str(dk))
            except Exception as e:
                check("keyboard (%s): could be reached and typed in" % tag, False, str(e).splitlines()[0][:140])
        allerrs += errs; ctx.close()

        # ---------- every tab, scrolled from top to bottom ----------
        ctx, p, errs = opened(b, W, H)
        for name, tab, steps in SCREENS:
            tag="%s, %s" % (phone, name)
            try:
                go(p, tab, steps)
                p.evaluate("()=>window.scrollTo(0, 0)"); p.wait_for_timeout(150)
                end=p.evaluate("()=>document.documentElement.scrollHeight-innerHeight")
                off, wide, y = [], False, 0
                while True:
                    dk=p.evaluate(DOCK)
                    if dk["bot"]!=H or dk["vis"]!="visible": off.append("%d: %s" % (y, dk))
                    wide = wide or p.evaluate(WIDE)
                    if y>=end: break
                    y=min(end, y+int(H*0.6))
                    p.mouse.wheel(0, 0); p.evaluate("y=>window.scrollTo(0,y)", y); p.wait_for_timeout(120)
                check("scroll (%s): the dock stays at the bottom, top to end" % tag, not off, "; ".join(off[:3]))
                check("scroll (%s): nothing runs off the side" % tag, not wide)
                last=p.evaluate(LAST)
                check("scroll (%s): at the end, the last thing ends above the dock, not under it" % tag,
                      last["last"]<=last["dock"]+1, str(last))
            except Exception as e:
                check("scroll (%s): could be opened and scrolled" % tag, False, str(e).splitlines()[0][:140])
        allerrs += errs; ctx.close()

    for st,n,det in res: print("%-5s %-96s %s" % (st,n,det))
    f=[r for r in res if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(res)-len(f), len(f)))
    print("pageerrors:", allerrs if allerrs else "none")
    b.close()
    raise SystemExit(1 if (f or allerrs) else 0)
