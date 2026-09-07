from playwright.sync_api import sync_playwright
import os, json, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d
T=datetime.date.today(); Ts=T.isoformat()
Y=(T-datetime.timedelta(days=2)).isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{
  Y:{"food":[{"id":"y1","cal":1800,"pro":160,"note":"Whole day"}],
     "lifts":[{"id":"yl","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10},{"w":135,"r":10},{"w":145,"r":8}]}],
     "updated":1,"goal":G}},
  "moves":None,"goal":G,"region":"United States",
  "pantry":[{"id":"p1","name":"costco protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,"sCal":130,"sPro":30,"aliases":[]}],
  "v":1}

SAMPLE_STUB = """
window.claude={use:function(n){
 if(n==='sample'){var f=function(){};
  f.json=function(p){return Promise.resolve({items:[{food:'Chipotle burrito bowl',amount:'1 bowl',calories:700,protein:45}],note:'Assumed chicken, rice, beans.'});};
  f.limits=function(){return Promise.resolve({maxPromptBytes:65536,images:{maxCount:4,maxInputBytes:2e7,mediaTypes:['image/jpeg']}});};
  return Promise.resolve(f);}
 return Promise.resolve(null);}};
"""

results=[]
def check(name, ok, detail=""):
    results.append((("PASS" if ok else "FAIL"), name, detail))

with sync_playwright() as pw:
    b=pw.chromium.launch()
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True); ctx.add_init_script(SAMPLE_STUB)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(400)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
    p.reload(); p.wait_for_timeout(1200)

    # ---------- MACROS ----------
    p.fill("#fCal","250"); p.fill("#fPro","25"); p.fill("#fNote","Yogurt")
    p.click("#addFood"); p.wait_for_timeout(400)
    check("macros: manual add", p.eval_on_selector_all(".t-row","e=>e.length")==1)
    check("macros: confirmation shown", p.evaluate("()=>!!document.querySelector('.added-flash')"))

    p.fill("#fCal","100"); p.fill("#fPro","5"); p.press("#fPro","Enter"); p.wait_for_timeout(400)
    check("macros: Enter submits", p.eval_on_selector_all(".t-row","e=>e.length")==2)

    p.eval_on_selector_all(".t-del","e=>e[1].click()"); p.wait_for_timeout(400)
    check("macros: delete row", p.eval_on_selector_all(".t-row","e=>e.length")==1)
    check("macros: undo bar appears", p.evaluate("()=>!document.getElementById('undobar').hidden"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("macros: undo restores", p.eval_on_selector_all(".t-row","e=>e.length")==2)

    # goal editor
    p.click("#openGoal"); p.wait_for_timeout(300)
    check("macros: goal editor opens", p.evaluate("()=>!!document.getElementById('gCal')"))
    p.eval_on_selector_all("#dirCal button","e=>e[0].click()")   # switch cal to "+ Above"
    p.fill("#gCal","2500"); p.fill("#gPro","180")
    p.click("#saveGoal"); p.wait_for_timeout(400)
    gt = p.text_content("#openGoal")
    check("macros: goal saves w/ direction", "+2,500" in gt and "+180" in gt, gt.strip())
    p.click("#openGoal"); p.wait_for_timeout(250); p.click("#cancelGoal"); p.wait_for_timeout(300)
    check("macros: goal cancel", p.evaluate("()=>!document.getElementById('gCal')"))

    # estimator: table + pantry + claude fallback in one
    p.fill("#estText","200g chicken breast & 1 costco protein coffee & chipotle burrito bowl")
    p.click("#runEst"); p.wait_for_timeout(1200)
    rows=p.eval_on_selector_all(".rev-item",
      "e=>e.map(x=>x.querySelector('.food').textContent+'|'+x.querySelector('.amt').textContent.trim())")
    srcs=" ".join(rows)
    check("estimator: table match", "built-in reference" in srcs)
    check("estimator: pantry match", "your pantry" in srcs)
    check("estimator: claude fallback", "estimated" in srcs, " / ".join(rows))
    before=p.eval_on_selector_all(".t-row","e=>e.length")
    p.click("#commitEst"); p.wait_for_timeout(500)
    check("estimator: commit adds rows", p.eval_on_selector_all(".t-row","e=>e.length")==before+3)

    # ---------- correcting an assumed portion ----------
    # A typical serving is a guess about your plate, so the weight is a field.
    p.fill("#estText","white rice & 1 costco protein coffee")
    p.click("#runEst"); p.wait_for_timeout(1200)
    SNAP="""()=>[...document.querySelectorAll('.rev-item')].map(x=>({
        food:x.querySelector('.food').textContent,
        g:(x.querySelector('[data-ig]')||{}).value||null,
        cal:Number(x.querySelector('[data-ic]').value),
        pro:Number(x.querySelector('[data-ip]').value),
        tag:x.querySelector('.src-tag').textContent}))"""
    was=p.evaluate(SNAP)
    rice=[r for r in was if r["g"]][0]
    check("serving: assumed portion is editable", rice["g"] is not None, json.dumps(rice))
    check("serving: a count from the pantry is not",
          any(r["g"] is None for r in was), json.dumps([r for r in was if r["g"] is None]))
    gbox=p.locator("[data-ig]").first.bounding_box()
    check("serving: weight field is 44px", gbox and gbox["height"]>=44,
          gbox and "%dx%d"%(gbox["width"],gbox["height"]))

    g0=float(rice["g"]); c0=rice["cal"]; p0=rice["pro"]
    p.fill('[data-ig="0"]', str(int(g0*2))); p.wait_for_timeout(400)
    now=p.evaluate(SNAP)[0]
    check("serving: doubling the weight doubles the macros",
          abs(now["cal"]-c0*2)<=2 and abs(now["pro"]-p0*2)<=2,
          "%s/%s -> %s/%s" % (c0,p0,now["cal"],now["pro"]))
    check("serving: it stops calling itself a typical serving",
          now["tag"]!="typical serving", now["tag"])
    rowsum=sum(r["cal"] for r in p.evaluate(SNAP))
    head=p.eval_on_selector(".review > header span","e=>e.textContent").replace(",","")
    check("serving: the running total follows", ("%d kcal"%rowsum) in head,
          "rows=%d head=%r" % (rowsum, head))
    p.click("#commitEst"); p.wait_for_timeout(600)
    # the note is built from `amount`; if that does not move with the weight the
    # ledger permanently records a portion you never logged
    notes=p.evaluate("""()=>{const d=JSON.parse(localStorage.getItem('iron-ledger-v1')).days||{};
        const out=[]; for(const k of Object.keys(d)) for(const f of (d[k].food||[])) out.push(f.note||"");
        return out;}""")
    check("serving: the ledger records the corrected weight",
          any(("%d g"%int(g0*2)) in n for n in notes),
          " | ".join(notes[-3:]))

    # date nav
    p.click("#prevDay"); p.wait_for_timeout(350)
    d1=p.text_content("#dateFull")
    p.click("#nextDay"); p.wait_for_timeout(350)
    check("macros: date arrows", d1!=p.text_content("#dateFull"))
    p.click("#prevDay"); p.wait_for_timeout(300)
    check("macros: 'back to today' visible off-today", p.evaluate("()=>!document.getElementById('todayBtn').hidden"))
    p.click("#todayBtn"); p.wait_for_timeout(350)
    check("macros: back to today works", p.evaluate("()=>document.getElementById('todayBtn').hidden"))

    # region persists
    p.fill("#regionIn","Canada"); p.click("#estText"); p.wait_for_timeout(300)
    check("macros: region persists", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).region")=="Canada")

    # ---------- GYM ----------
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
    p.eval_on_selector_all(".cat","e=>e[1].click()"); p.wait_for_timeout(350)
    check("gym: category switch", p.evaluate("()=>document.querySelectorAll('.cat')[1].getAttribute('aria-pressed')")=="true")
    p.eval_on_selector_all(".cat","e=>e[0].click()"); p.wait_for_timeout(350)
    p.select_option("#mSel","Barbell Row"); p.click("#addLift"); p.wait_for_timeout(400)
    check("gym: add movement", p.eval_on_selector_all(".lift","e=>e.length")==1)
    last=p.eval_on_selector(".lift .last","e=>e.textContent")
    check("gym: last-session lookup", "135" in last, last.strip())
    p.fill('[data-w="0"]',"185"); p.fill('[data-r="0"]',"6")
    p.click('[data-addset="0"]'); p.wait_for_timeout(400)
    check("gym: add set", p.eval_on_selector_all(".set","e=>e.length")==1)
    check("gym: volume line", "1 set" in p.eval_on_selector(".lift-foot span","e=>e.textContent"))
    p.fill('[data-w="0"]',"185"); p.fill('[data-r="0"]',"5"); p.press('[data-r="0"]',"Enter"); p.wait_for_timeout(400)
    check("gym: Enter adds set", p.eval_on_selector_all(".set","e=>e.length")==2)
    p.eval_on_selector_all(".set","e=>e[0].click()"); p.wait_for_timeout(400)
    check("gym: delete set + undo offered", p.eval_on_selector_all(".set","e=>e.length")==1 and not p.evaluate("()=>document.getElementById('undobar').hidden"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("gym: undo set", p.eval_on_selector_all(".set","e=>e.length")==2)
    # custom movement
    p.select_option("#mSel","__new"); p.wait_for_timeout(200)
    p.fill("#mNew","Meadows Row"); p.click("#addLift"); p.wait_for_timeout(400)
    check("gym: custom movement", p.eval_on_selector_all(".lift","e=>e.length")==2)
    check("gym: custom movement remembered",
          "Meadows Row" in p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).moves.back"))
    p.eval_on_selector_all("[data-rmlift]","e=>e[1].click()"); p.wait_for_timeout(400)
    check("gym: remove movement", p.eval_on_selector_all(".lift","e=>e.length")==1)
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("gym: undo movement", p.eval_on_selector_all(".lift","e=>e.length")==2)

    # the form belongs under the movements: the list reads in training order and
    # the next thing to add is the next thing on screen
    check("gym: add-movement sits below the movements", p.evaluate("""()=>{
        const g=document.querySelector('.liftgroup'), f=document.getElementById('addLift');
        return !!(g&&f&&(g.compareDocumentPosition(f)&Node.DOCUMENT_POSITION_FOLLOWING));}"""))

    # ---------- LOCK IN ----------
    check("gym: lock offered once something is logged",
          p.evaluate("()=>!!document.getElementById('lockDay')"))
    p.click("#lockDay"); p.wait_for_timeout(500)
    check("gym: lock is stored on the day",
          p.evaluate("k=>!!JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k].gymLocked", Ts))
    check("gym: locked says the day is done",
          "complete" in p.eval_on_selector(".daydone .dd-title","e=>e.textContent").lower(),
          p.eval_on_selector(".daydone .dd-title","e=>e.textContent"))
    stats=p.eval_on_selector_all(".daydone .dd-stats div","e=>e.map(x=>x.textContent)")
    check("gym: the finished card totals the day", len(stats)==4, " | ".join(stats))
    # transient by design: the card persists, the confetti is only the moment
    check("gym: confetti fired on the tap and cleans itself up",
          p.evaluate("()=>document.querySelectorAll('.confetti i').length")>0,
          "%d pieces" % p.evaluate("()=>document.querySelectorAll('.confetti i').length"))
    check("gym: confetti cannot swallow a tap",
          p.evaluate("()=>{const c=document.querySelector('.confetti');return !c||getComputedStyle(c).pointerEvents==='none';}"))
    check("gym: locked hides the add form", p.evaluate("()=>!document.getElementById('addLift')"))
    check("gym: locked hides set entry", p.eval_on_selector_all("[data-addset]","e=>e.length")==0)
    check("gym: locked hides remove", p.eval_on_selector_all("[data-rmlift]","e=>e.length")==0)
    # spans, not disabled buttons — probe reads a control that does nothing as dead
    check("gym: locked set chips are not controls",
          p.eval_on_selector_all(".set","e=>e.length>0&&e.every(x=>x.tagName==='SPAN')"))
    ubox=p.locator("#unlockDay").bounding_box()
    check("gym: unlock is 44px", ubox and ubox["height"]>=44,
          ubox and "%dx%d"%(ubox["width"],ubox["height"]))
    p.reload(); p.wait_for_timeout(900)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
    check("gym: still finished after a reload", p.eval_on_selector_all(".daydone","e=>e.length")==1)
    check("gym: the celebration does not replay on reopen",
          p.eval_on_selector_all(".confetti","e=>e.length")==0)
    liftsWere=p.evaluate("k=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k].lifts.map(l=>l.sets.length)", Ts)
    p.click("#unlockDay"); p.wait_for_timeout(500)
    check("gym: unlock restores editing", p.evaluate("()=>!!document.getElementById('addLift')"))
    check("gym: locking never touched the sets",
          p.evaluate("k=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k].lifts.map(l=>l.sets.length)", Ts)==liftsWere,
          str(liftsWere))

    # ---------- SPLITS ARE THE USER'S, NOT OURS ----------
    NAMES="()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).routine.days.map(d=>d.name)"
    check("splits: + sits in the chip row", p.evaluate("()=>!!document.getElementById('addSplitChip')"))
    ab=p.locator("#addSplitChip").bounding_box()
    check("splits: + is a proper target", ab and ab["height"]>=44,
          ab and "%dx%d"%(ab["width"],ab["height"]))
    n0=len(p.evaluate(NAMES))
    p.click("#addSplitChip"); p.wait_for_timeout(400)
    p.fill("#newSplitName","Walk"); p.press("#newSplitName","Enter"); p.wait_for_timeout(600)
    check("splits: add a split", p.evaluate(NAMES)[-1]=="Walk", str(p.evaluate(NAMES)))
    check("splits: lands on the one you just made",
          "Walk" in p.eval_on_selector(".cat[aria-pressed=true]","e=>e.textContent"))
    # a new split is a blank canvas: nothing assumed about what goes in it
    check("splits: a new split starts empty",
          p.eval_on_selector_all("#mSel option","e=>e.length")==1,
          str(p.eval_on_selector_all("#mSel option","e=>e.map(x=>x.textContent)")))
    p.select_option("#mSel","__new"); p.wait_for_timeout(250)
    p.fill("#mNew","Evening walk"); p.click("#addLift"); p.wait_for_timeout(500)
    check("splits: anything you do counts as a movement",
          "Evening walk" in p.evaluate("k=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k].lifts.map(l=>l.movement)", Ts))

    p.click("#editSplits"); p.wait_for_timeout(500)
    check("splits: edit gives a row per split",
          p.eval_on_selector_all(".split-row","e=>e.length")==n0+1)
    nb=p.locator(".split-name").first.bounding_box()
    rb=p.locator(".split-rm").first.bounding_box()
    check("splits: rename field clears 44px", nb and nb["height"]>=44, nb and "%dx%d"%(nb["width"],nb["height"]))
    check("splits: remove clears 44px", rb and rb["height"]>=44, rb and "%dx%d"%(rb["width"],rb["height"]))
    first=p.locator("[data-splitname]").first
    first.fill("Bi / Tri / RD"); first.dispatch_event("change"); p.wait_for_timeout(500)
    check("splits: rename sticks", p.evaluate(NAMES)[0]=="Bi / Tri / RD", str(p.evaluate(NAMES)))
    # an empty name is not a split; the field must snap back, not blank it
    first=p.locator("[data-splitname]").first
    first.fill("   "); first.dispatch_event("change"); p.wait_for_timeout(400)
    check("splits: an empty name is refused", p.evaluate(NAMES)[0]=="Bi / Tri / RD", str(p.evaluate(NAMES)))

    p.locator("[data-rmsplit]").first.click(); p.wait_for_timeout(600)
    check("splits: remove drops it", "Bi / Tri / RD" not in p.evaluate(NAMES), str(p.evaluate(NAMES)))
    check("splits: remove offers undo, never a dialog",
          p.evaluate("()=>!document.getElementById('undobar').hidden"))
    # rule 7: the workouts logged under it keep the name they were logged under
    check("splits: the deleted name is remembered",
          "Bi / Tri / RD" in str(p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).retired")),
          str(p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).retired")))
    p.click("#editSplits"); p.wait_for_timeout(500)
    body=p.eval_on_selector_all(".lift .body","e=>e.map(x=>x.textContent).join(' ')")
    check("splits: old workouts are not relabelled",
          "no longer train" in body and "Bi / Tri / RD" in body, body[:90])
    p.click("#undoBtn"); p.wait_for_timeout(600)
    check("splits: undo brings it back", "Bi / Tri / RD" in p.evaluate(NAMES), str(p.evaluate(NAMES)))

    # ---------- PANTRY ----------
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
    check("pantry: photo button (sample avail)", p.evaluate("()=>!!document.getElementById('shotBtn')"))
    p.fill("#panName","Quest bar"); p.fill("#panServe","1"); p.select_option("#panUnit","bar")
    p.fill("#panCal","200"); p.fill("#panPro","21"); p.click("#savePan"); p.wait_for_timeout(400)
    check("pantry: add count-unit food", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==2)
    p.fill("#panName","Bulk oats"); p.fill("#panServe","40"); p.select_option("#panUnit","g")
    p.fill("#panCal","150"); p.fill("#panPro","5"); p.click("#savePan"); p.wait_for_timeout(400)
    check("pantry: add weight-unit food", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==3)
    p.fill("#panName","Bad entry"); p.fill("#panServe","1"); p.select_option("#panUnit","g")
    p.fill("#panCal","200"); p.fill("#panPro","20"); p.click("#savePan"); p.wait_for_timeout(400)
    check("pantry: rejects impossible density",
          p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==3 and
          p.evaluate("()=>{const w=document.getElementById('panWarn');return w&&!w.hidden;}"))
    n0=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")
    p.eval_on_selector_all("[data-rmpan]","e=>e[0].click()"); p.wait_for_timeout(400)
    check("pantry: remove", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==n0-1)
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("pantry: undo remove", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==n0)

    # ---------- PANTRY -> MACROS, one tap ----------
    check("pantry: wording", p.eval_on_selector('label[for="panName"]',"e=>e.textContent.strip?e.textContent:e.textContent")=="Type and save it")
    # count across every day: earlier steps move the cursor, so pinning this to
    # today's key would silently measure a day the tap never touched
    TOTAL="""()=>{const d=JSON.parse(localStorage.getItem('iron-ledger-v1')).days||{};
        return Object.keys(d).reduce((n,k)=>n+((d[k].food||[]).length),0);}"""
    LASTADDED="""n=>{const d=JSON.parse(localStorage.getItem('iron-ledger-v1')).days||{};
        for(const k of Object.keys(d)) for(const f of (d[k].food||[])) if(f.note===n) return f;
        return null;}"""
    before=p.evaluate(TOTAL)
    row=p.evaluate("""()=>{const b=document.querySelector('[data-addpan]');if(!b)return null;
        const it=b.closest('.pan-item');return {id:b.dataset.addpan,name:it.querySelector('.nm').textContent};}""")
    check("pantry: every good food offers +", row is not None, str(row))
    box=p.locator("[data-addpan]").first.bounding_box()
    check("pantry: + is 44px", box and box["width"]>=44 and box["height"]>=44,
          box and "%dx%d"%(box["width"],box["height"]))
    p.locator("[data-addpan]").first.click(); p.wait_for_timeout(400)
    after=p.evaluate(TOTAL)
    check("pantry: + logs one row to the day", after==before+1, "%d -> %d"%(before,after))
    logged=p.evaluate(LASTADDED, row["name"])
    check("pantry: + carries the food's own numbers",
          bool(logged) and logged.get("note")==row["name"] and logged.get("cal") and logged.get("pro"),
          json.dumps(logged))
    # rule 3: the row lands on a tab you cannot see, so the button must speak
    check("pantry: + confirms visibly",
          p.eval_on_selector('[data-addpan="%s"]'%row["id"], "e=>e.classList.contains('is-done')"))
    p.wait_for_timeout(1500)
    check("pantry: + goes back to +",
          p.eval_on_selector('[data-addpan="%s"]'%row["id"], "e=>e.textContent")=="+")
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(400)
    check("pantry: the row really is on macros",
          p.evaluate("n=>[...document.querySelectorAll('.t-row')].some(r=>r.textContent.includes(n))", row["name"]))
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(400)

    # ---------- LOG ----------
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
    check("log: 12 months render", p.eval_on_selector_all(".month","e=>e.length")==12)
    check("log: today ringed", p.eval_on_selector_all(".cal-cell.is-today","e=>e.length")==1)
    check("log: stats row", p.eval_on_selector_all(".yearstats b","e=>e.length")==3)
    yr0=p.text_content(".yearnav .y")
    p.click("#nextYear"); p.wait_for_timeout(500)
    check("log: year nav", p.text_content(".yearnav .y")!=yr0)
    p.click("#prevYear"); p.wait_for_timeout(500)
    p.eval_on_selector_all(".cal-cell.hit, .cal-cell.miss","e=>{if(e.length)e[0].click()}"); p.wait_for_timeout(500)
    check("log: tap day jumps to macros", p.evaluate("()=>document.querySelector('.tabs button[data-tab=macros]').getAttribute('aria-selected')")=="true")

    # ---------- BACKUP / RESTORE ----------
    p.click("#backupBtn"); p.wait_for_timeout(400)
    txt=p.evaluate("()=>document.getElementById('backupText').value")
    check("backup: produces JSON", txt.startswith("{") and '"pantry"' in txt)
    check("backup: shows build", "Build" in p.text_content("#diag"))
    payload=json.loads(txt)
    # wipe and restore
    p.evaluate("()=>{document.getElementById('closeSheet').click();}"); p.wait_for_timeout(200)
    p.evaluate("()=>localStorage.removeItem('iron-ledger-v1')")
    p.reload(); p.wait_for_timeout(900)
    p.click("#backupBtn"); p.wait_for_timeout(300)
    p.evaluate("t=>{document.getElementById('backupText').value=t;}", txt)
    p.click("#restoreBtn"); p.wait_for_timeout(600)
    after=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
    check("restore: days come back", len(after.get("days",{}))==len(payload.get("days",{})),
          "%d of %d days" % (len(after.get("days",{})), len(payload.get("days",{}))))
    check("restore: pantry comes back", len(after.get("pantry",[]))==len(payload.get("pantry",[])),
          "%d of %d pantry items" % (len(after.get("pantry",[])), len(payload.get("pantry",[]))))
    check("restore: goal comes back", after.get("goal")==payload.get("goal"),
          "got %s" % json.dumps(after.get("goal")))
    check("restore: region comes back", after.get("region")==payload.get("region"),
          "got %s want %s" % (after.get("region"), payload.get("region")))

    print("%-6s %-42s %s" % ("","FEATURE","DETAIL"))
    for st,name,detail in results:
        print("%-6s %-42s %s" % (st,name,detail))
    fails=[r for r in results if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(results)-len(fails), len(fails)))
    print("pageerrors:", errs if errs else "none")
    b.close()
