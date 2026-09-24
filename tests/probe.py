from playwright.sync_api import sync_playwright
import os, json, datetime, hashlib
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today(); Ts=T.isoformat(); Y=(T-datetime.timedelta(days=1)).isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
STORE={"days":{
  Y:{"food":[{"id":"y1","cal":1800,"pro":160,"note":"Yesterday"}],
     "lifts":[{"id":"yl","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]}],"updated":1,"goal":G},
  Ts:{"food":[{"id":"t1","cal":520,"pro":46,"note":"Eggs"},
              {"id":"t2","cal":0,"pro":0,"note":"leftover curry","pending":True}],
      "lifts":[{"id":"tl","cat":"back","movement":"Barbell Row","sets":[{"w":185,"r":6},{"w":185,"r":5}]}],
      "updated":2,"goal":G}},
  "moves":None,"goal":G,"region":"United States",
  "pantry":[{"id":"p1","name":"protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,"sCal":130,"sPro":30,"aliases":[]},
            {"id":"p2","name":"legacy bad","k":13000,"p":3000,"servingG":1,"aliases":[]}],"v":1}
STUB="""window.claude={use:function(n){
 if(n==='sample'){var f=function(){};
  f.json=function(){return Promise.resolve({items:[{food:'Burrito bowl',amount:'1 bowl',calories:700,protein:45}],note:''});};
  f.limits=function(){return Promise.resolve({maxPromptBytes:65536,images:{maxCount:4,maxInputBytes:2e7,mediaTypes:['image/jpeg']}});};
  return Promise.resolve(f);} return Promise.resolve(null);}};"""

SNAP="""()=>JSON.stringify({dom:document.querySelector('.app').innerHTML.length,
  txt:document.querySelector('main').textContent,
  ls:localStorage.getItem('iron-ledger-v1'),
  undo:document.getElementById('undobar').hidden,
  // every sheet, not just Backup's: the quantity, settings and set editors
  // are all sheets now, and a control that opens one is not a dead control
  sheet:[...document.querySelectorAll('.sheet')].map(x=>x.hidden?0:1).join(''),
  tab:[...document.querySelectorAll('.tabs button')].map(b=>b.getAttribute('aria-selected')).join(''),
  date:document.getElementById('dateFull').textContent})"""

# element, how to reach it, expected effect
PROBES=[
 ("macros","#backupBtn","opens backup sheet",None),
 ("macros","#prevDay","previous day",None),
 ("macros","#nextDay","next day",None),
 ("macros",".t-del:nth-of-type(1)","delete a row",None),
 ("macros","#openGoal","open target editor",None),
 ("macros","#addFood","add entry",[("#fCal","300"),("#fPro","30")]),
 ("macros","#runEst","run estimate",[('[data-eq="0"]',"200"),('[data-ef="0"]',"chicken breast")]),
 ("macros",".pending-chip","resolve pending entry",None),
 ("gym",".cat:nth-child(2)","switch split",None),
 ("gym",".cat:nth-child(3)","switch split (legs)",None),
 ("gym","#addLift","add movement",None),
 ("gym",'[data-addset="0"]',"add a set",[('[data-w="0"]',"200"),('[data-r="0"]',"5")]),
 ("gym",".set","open a set to change it",None),
 ("gym","[data-rmlift]","remove movement",None),
 ("pantry","#shotBtn","open label photo picker",None),
 ("pantry","#savePan","save pantry food",[("#panName","Test bar"),("#panServe","1"),("#panCal","200"),("#panPro","20")]),
 ("pantry","[data-rmpan]","remove pantry food",None),
 ("pantry","[data-fixpan]","fix legacy pantry entry",None),
 ("log","#prevYear","previous year",None),
 ("log","#nextYear","next year",None),
 ("log",".cal-cell.hit, .cal-cell.miss","tap a logged day",None),
]
rows=[]
with sync_playwright() as pw:
    b=pw.chromium.launch()
    for tab, sel, what, fills in PROBES:
        ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True); ctx.add_init_script(STUB)
        p=ctx.new_page(); errs=[]
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", STORE)
        p.reload(); p.wait_for_timeout(900)
        if tab!="macros":
            p.click('.tabs button[data-tab="%s"]'%tab); p.wait_for_timeout(500)
        note=""
        try:
            if fills:
                for s2,v in fills: p.fill(s2,v)
                p.wait_for_timeout(150)
            el=p.query_selector(sel)
            if not el:
                rows.append(("MISSING",tab,sel,what,"element not present")); ctx.close(); continue
            before=p.evaluate(SNAP)
            el.click(); p.wait_for_timeout(700)
            after=p.evaluate(SNAP)
            changed = before!=after
            if not changed:
                rows.append(("DEAD",tab,sel,what,"click produced no change"))
            else:
                bj,aj=json.loads(before),json.loads(after)
                bits=[]
                if bj["ls"]!=aj["ls"]: bits.append("data saved")
                if bj["txt"]!=aj["txt"]: bits.append("screen updated")
                if bj["undo"]!=aj["undo"]: bits.append("undo offered")
                if bj["sheet"]!=aj["sheet"]: bits.append("sheet opened")
                if bj["tab"]!=aj["tab"]: bits.append("tab changed")
                if bj["date"]!=aj["date"]: bits.append("date changed")
                rows.append(("OK",tab,sel,what,", ".join(bits)))
            if errs: rows.append(("ERROR",tab,sel,what,errs[0][:80]))
        except Exception as ex:
            rows.append(("THREW",tab,sel,what,str(ex).split("\n")[0][:80]))
        ctx.close()
    b.close()

print("%-8s %-7s %-30s %s" % ("RESULT","TAB","WHAT IT SHOULD DO","OBSERVED"))
for r in rows: print("%-8s %-7s %-30s %s" % (r[0],r[1],r[3],r[4]))
bad=[r for r in rows if r[0] not in ("OK",)]
print("\n%d responded, %d need a look" % (len(rows)-len(bad), len(bad)))
