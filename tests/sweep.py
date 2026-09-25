from playwright.sync_api import sync_playwright
import os, json, datetime
import re

# Rule 5 is 44px, measured. This suite measures controls straight after the
# action that drew them, while the cards' 0.18s slide-in is still running, so
# a box can come back 43.99998 tall from subtracting two fractional edges — it
# failed the grip once that way. A control that is genuinely too small is a
# whole pixel short (the 43px scanner button CI caught), so half a pixel of
# allowance still catches every real one.
MIN_TAP = 43.5

def words(p):
    """Open the plain-words box; it lives behind the fill-in table now."""
    if not p.locator("#estText").count():
        p.click("#estSwap"); p.wait_for_timeout(250)
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
    # "beef wellington" is deliberately absent from the table — the point of this
    # check is the fallback path, and a query the table can answer tests coverage
    # instead. "chipotle burrito bowl" used to be that query until the table grew.
    words(p);p.fill("#estText","200g chicken breast & 1 costco protein coffee & beef wellington")
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
    words(p);p.fill("#estText","white rice & 1 costco protein coffee")
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
    check("serving: weight field is 44px", gbox and gbox["height"]>=MIN_TAP,
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
    # ---------- THE WAY IN IS A TABLE, NOT A BLANK BOX ----------
    # "What did you eat?" over an empty textarea tells a first-time user
    # nothing about what it accepts. Labelled fields with examples do.
    # Committing here also closes the review the section above left open, and
    # a later check reads the corrected weight back out of the ledger.
    p.click("#commitEst"); p.wait_for_timeout(600)
    if p.locator("#estText").count(): p.click("#estSwap"); p.wait_for_timeout(300)
    check("entry: you land on a table, not a blank box",
          p.locator(".et-row").count()==1 and p.locator("#estText").count()==0)
    # the labels are set in uppercase by CSS, so compare what is on screen
    check("entry: the fields say what goes in them",
          [x.strip().upper() for x in p.locator(".et-lab").all_inner_texts()]==["AMOUNT","UNIT","FOOD"],
          str(p.locator(".et-lab").all_inner_texts()))
    check("entry: and carry an example",
          p.get_attribute('[data-ef="0"]',"placeholder")=="chicken breast",
          p.get_attribute('[data-ef="0"]',"placeholder"))
    check("entry: the food field offers what the app already knows",
          p.locator("#estFoods option").count() > 250,
          "%d suggestions" % p.locator("#estFoods option").count())
    for sel in ('[data-eq="0"]', '[data-eu="0"]', '[data-ef="0"]', "#estAddRow", "#estSwap"):
        bb=p.locator(sel).bounding_box()
        check("entry: %s clears 44px" % sel, bb and bb["height"]>=MIN_TAP,
              bb and "%dx%d"%(bb["width"],bb["height"]))

    # pressing it with nothing filled in must not read as a dead button
    p.click("#runEst"); p.wait_for_timeout(500)
    check("entry: an empty press says so rather than doing nothing",
          "Nothing to work out" in p.locator(".est").inner_text(),
          " / ".join(x.strip() for x in p.locator(".est .est-note").all_inner_texts())[:80])
    check("entry: and no review opened", p.locator(".review").count()==0)

    p.fill('[data-eq="0"]',"6"); p.select_option('[data-eu="0"]',"oz")
    p.fill('[data-ef="0"]',"chicken breast"); p.wait_for_timeout(200)
    p.click("#estAddRow"); p.wait_for_timeout(500)
    check("entry: adding a row adds a row", p.locator(".et-row").count()==2)
    check("entry: and puts you in it",
          p.evaluate("()=>document.activeElement.dataset.ef")=="1")
    check("entry: the first row survived it",
          p.input_value('[data-ef="0"]')=="chicken breast")
    p.fill('[data-eq="1"]',"1"); p.select_option('[data-eu="1"]',"cup"); p.fill('[data-ef="1"]',"white rice")
    p.click("#runEst"); p.wait_for_timeout(1400)
    foods=p.eval_on_selector_all(".rev-item .food","e=>e.map(x=>x.textContent)")
    check("entry: both rows resolve", len(foods)==2, " | ".join(foods))
    check("entry: the unit you picked is the unit it used",
          p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value)")[0]=="oz",
          str(p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value)")))
    p.click("#commitEst"); p.wait_for_timeout(800)
    check("entry: the table empties after it is logged",
          p.locator(".et-row").count()==1 and p.input_value('[data-ef="0"]')=="",
          "rows=%d first=%r" % (p.locator(".et-row").count(), p.input_value('[data-ef="0"]')))

    # removing a row, and the words box behind it
    p.fill('[data-ef="0"]',"eggs"); p.click("#estAddRow"); p.wait_for_timeout(500)
    p.fill('[data-ef="1"]',"toast"); p.wait_for_timeout(200)
    rb=p.locator("[data-erm]").first.bounding_box()
    check("entry: remove is a proper target", rb and rb["height"]>=MIN_TAP,
          rb and "%dx%d"%(rb["width"],rb["height"]))
    p.click('[data-erm="0"]'); p.wait_for_timeout(500)
    check("entry: removing a row removes the right one",
          p.locator(".et-row").count()==1 and p.input_value('[data-ef="0"]')=="toast",
          p.input_value('[data-ef="0"]'))
    p.click("#estSwap"); p.wait_for_timeout(500)
    check("entry: the words box is still there behind it",
          p.locator("#estText").count()==1 and p.locator(".et-row").count()==0)
    check("entry: and the table came with it rather than being retyped",
          p.input_value("#estText")=="toast", repr(p.input_value("#estText")))
    p.click("#estSwap"); p.wait_for_timeout(500)
    check("entry: swapping back keeps the table",
          p.input_value('[data-ef="0"]')=="toast")
    p.fill('[data-ef="0"]',""); p.wait_for_timeout(200)

    # ---------- WEIGH IT HOWEVER YOU WEIGH IT ----------
    # Grams are the basis the food table is keyed on, but a US kitchen scale
    # reads ounces and nobody is re-teaching it for this app.
    STORE = "()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    ROW = """()=>({g:document.querySelector('[data-ig]').value,
                   u:document.querySelector('[data-iu]').value,
                   cal:Number(document.querySelector('[data-ic]').value)})"""
    check("units: grams is what you get until you say otherwise",
          p.eval_on_selector("#wUnitIn","e=>e.value")=="g")
    ub=p.locator("#wUnitIn").bounding_box()
    check("units: the picker is a proper target", ub and ub["height"]>=MIN_TAP,
          ub and "%dx%d"%(ub["width"],ub["height"]))

    words(p);p.fill("#estText","200 g chicken breast"); p.click("#runEst"); p.wait_for_timeout(1200)
    r0=p.evaluate(ROW)
    check("units: a weight you typed comes back in the unit you typed", r0["u"]=="g", json.dumps(r0))
    rb=p.locator("[data-iu]").first.bounding_box()
    check("units: the row picker is a proper target", rb and rb["height"]>=MIN_TAP,
          rb and "%dx%d"%(rb["width"],rb["height"]))
    p.select_option("[data-iu]","oz"); p.wait_for_timeout(600)
    r1=p.evaluate(ROW)
    # the food did not change size, so the macros must not move
    check("units: switching converts rather than re-reads",
          r1["u"]=="oz" and abs(float(r1["g"])-7.05)<0.1 and r1["cal"]==r0["cal"],
          "%s g -> %s %s, %d kcal" % (r0["g"], r1["g"], r1["u"], r1["cal"]))
    check("units: the choice is remembered", p.evaluate(STORE).get("wunit")=="oz")
    p.fill("[data-ig]","8"); p.wait_for_timeout(500)
    r2=p.evaluate(ROW)
    check("units: a number you type is read in that unit",
          abs(r2["cal"]-374)<=6, "8 oz -> %d kcal" % r2["cal"])
    p.click("#commitEst"); p.wait_for_timeout(700)
    saved=p.evaluate("""()=>{const d=JSON.parse(localStorage.getItem('iron-ledger-v1')).days||{};
        const out=[]; for(const k of Object.keys(d)) for(const f of (d[k].food||[])) out.push(f.note||"");
        return out;}""")
    check("units: the ledger records the portion you logged, in your unit",
          any("8 oz" in n for n in saved), " | ".join(saved[-3:]))

    # it has to survive a reload, or it is a setting that resets every morning
    p.reload(); p.wait_for_timeout(1000)
    check("units: and it survives a reload", p.eval_on_selector("#wUnitIn","e=>e.value")=="oz")
    words(p);p.fill("#estText","chicken breast and white rice"); p.click("#runEst"); p.wait_for_timeout(1300)
    check("units: rows you did not weigh follow the setting",
          p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value).join(',')")=="oz,oz",
          p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value).join(',')"))
    cals=p.eval_on_selector_all("[data-ic]","e=>e.map(x=>Number(x.value))")
    p.select_option("[data-iu] >> nth=0","g"); p.wait_for_timeout(700)
    check("units: changing one row changes the rest that have no unit of their own",
          p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value).join(',')")=="g,g",
          p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value).join(',')"))
    check("units: and none of that moves a single calorie",
          p.eval_on_selector_all("[data-ic]","e=>e.map(x=>Number(x.value))")==cals,
          "%s -> %s" % (cals, p.eval_on_selector_all("[data-ic]","e=>e.map(x=>Number(x.value))")))
    p.click("#discardEst"); p.wait_for_timeout(600)

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
    # blur onto something that exists in both entry modes
    p.fill("#regionIn","Canada"); p.click(".est .eyebrow"); p.wait_for_timeout(300)
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
    check("gym: Start forgotten, the first set starts the clock",
          p.evaluate("()=>!!document.getElementById('workoutClock')"))
    check("gym: volume line", "1 set" in p.eval_on_selector(".lift-foot span","e=>e.textContent"))
    p.fill('[data-w="0"]',"185"); p.fill('[data-r="0"]',"5"); p.press('[data-r="0"]',"Enter"); p.wait_for_timeout(400)
    check("gym: Enter adds set", p.eval_on_selector_all(".set","e=>e.length")==2)
    # A tap on a set used to remove it outright — the same remove-and-add-again
    # the owner called out for movements. Now it opens an editor.
    SETS = ("()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));"
            "const k=Object.keys(s.days).sort().pop();"
            "return s.days[k].lifts[0].sets.map(x=>x.w+'x'+x.r+(x.tech?':'+x.tech:''));}")
    p.eval_on_selector_all(".set","e=>e[0].click()"); p.wait_for_timeout(400)
    check("gym: tapping a set opens it rather than removing it",
          p.evaluate("()=>!document.getElementById('setEditSheet').hidden")
          and p.eval_on_selector_all(".set","e=>e.length")==2)
    check("gym: the editor names the set",
          "set 1 of 2" in p.eval_on_selector("#seTitle","e=>e.textContent"),
          p.eval_on_selector("#seTitle","e=>e.textContent"))
    check("gym: and opens on its numbers",
          p.input_value("#seW")=="185" and p.input_value("#seR")=="6" and p.input_value("#seT")=="",
          "%s x %s %r" % (p.input_value("#seW"), p.input_value("#seR"), p.input_value("#seT")))
    small=[x for x in p.eval_on_selector_all("#setEditSheet input, #setEditSheet select, #setEditSheet button",
           "e=>e.map(b=>[b.id,Math.round(b.getBoundingClientRect().height)])") if x[1]<44]
    check("gym: every control in it clears 44px", not small, str(small))
    zoomy=p.eval_on_selector_all("#setEditSheet input, #setEditSheet select",
          "e=>e.filter(x=>parseFloat(getComputedStyle(x).fontSize)<16).map(x=>x.id)")
    check("gym: and none of its fields zoom the page", not zoomy, str(zoomy))
    p.click("#seCancel"); p.wait_for_timeout(300)
    check("gym: cancel leaves the set alone", p.evaluate(SETS)==["185x6","185x5"], str(p.evaluate(SETS)))

    p.eval_on_selector_all(".set","e=>e[0].click()"); p.wait_for_timeout(300)
    p.fill("#seR",""); p.click("#seSave"); p.wait_for_timeout(250)
    check("gym: a set with no reps is not saved, and it says why",
          p.evaluate("()=>!document.getElementById('setEditSheet').hidden")
          and "reps" in p.eval_on_selector("#seWarn","e=>e.textContent")
          and p.evaluate(SETS)[0]=="185x6")
    p.fill("#seW","190"); p.fill("#seR","7"); p.select_option("#seT","failure")
    p.click("#seSave"); p.wait_for_timeout(350)
    check("gym: a set can be changed in place",
          p.evaluate(SETS)==["190x7:failure","185x5"], str(p.evaluate(SETS)))
    check("gym: the chip shows the change",
          p.eval_on_selector_all(".set","e=>e.map(x=>x.textContent)")[0]=="190×7failure",
          str(p.eval_on_selector_all(".set","e=>e.map(x=>x.textContent)")))
    check("gym: and it offers undo", "Changed to 190×7 failure" in p.eval_on_selector("#undobar","e=>e.textContent"))
    p.click("#undoBtn"); p.wait_for_timeout(350)
    check("gym: undo puts the old numbers back", p.evaluate(SETS)==["185x6","185x5"], str(p.evaluate(SETS)))

    # Remove lives in the editor now
    p.eval_on_selector_all(".set","e=>e[0].click()"); p.wait_for_timeout(300)
    p.click("#seRemove"); p.wait_for_timeout(400)
    check("gym: delete set + undo offered", p.eval_on_selector_all(".set","e=>e.length")==1 and not p.evaluate("()=>document.getElementById('undobar').hidden"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("gym: undo set", p.eval_on_selector_all(".set","e=>e.length")==2
          and p.evaluate(SETS)==["185x6","185x5"], str(p.evaluate(SETS)))
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
    # Lock in the day folds the one movement still open, so its sets become
    # text rather than chips. Asserted with the cards on screen, because "no
    # button anywhere" also passes on an empty page. The chips-as-spans path
    # for a locked day with movements left open is checked in the laps block.
    check("gym: a locked day leaves no set you can tap",
          p.locator(".lift").count()>0 and p.locator("button.set").count()==0,
          "%d cards, %d tappable sets" % (p.locator(".lift").count(), p.locator("button.set").count()))
    ubox=p.locator("#unlockDay").bounding_box()
    check("gym: unlock is 44px", ubox and ubox["height"]>=MIN_TAP,
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

    # ---------- HOW LONG IT TOOK ----------
    REC = "k=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k]"
    check("timer: offered before you start",
          p.evaluate("()=>!!document.getElementById('startWorkout')"))
    check("timer: it sits above Today's split, not below it",
          p.evaluate("""()=>{
            const b=document.getElementById('startWorkout'), h=document.querySelector('.split-head');
            return !!b && !!h && b.getBoundingClientRect().top < h.getBoundingClientRect().top;}"""))
    sb=p.locator("#startWorkout").bounding_box()
    check("timer: start is a proper target", sb and sb["height"]>=MIN_TAP,
          sb and "%dx%d"%(sb["width"],sb["height"]))
    p.click("#startWorkout"); p.wait_for_timeout(500)
    check("timer: starting shows a clock",
          p.evaluate("()=>!!document.getElementById('workoutClock')"))
    check("timer: the start time is stored, not a counter",
          bool(p.evaluate(REC, Ts).get("workoutStart")))
    db=p.locator("#discardWorkout").bounding_box()
    check("timer: discard is a proper target", db and db["height"]>=MIN_TAP,
          db and "%dx%d"%(db["width"],db["height"]))
    # a phone suspends the app mid-session; elapsed must come from the clock,
    # not from an interval that stopped counting
    p.wait_for_timeout(2200)
    p.reload(); p.wait_for_timeout(1000)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
    ticked=p.eval_on_selector("#workoutClock","e=>e.textContent")
    check("timer: still running after a reload", ticked not in ("0:00",""), ticked)

    p.click("#lockDay"); p.wait_for_timeout(700)
    banked=p.evaluate(REC, Ts)
    check("timer: locking the day banks the time", (banked.get("workoutMs") or 0) > 0,
          "%s ms" % banked.get("workoutMs"))
    check("timer: and stops the clock", "workoutStart" not in banked)
    check("timer: the finished card reports it",
          "Took" in p.eval_on_selector(".dd-time","e=>e.textContent"),
          p.eval_on_selector(".dd-time","e=>e.textContent"))
    first=banked["workoutMs"]
    p.click("#unlockDay"); p.wait_for_timeout(600)
    check("timer: unlocking keeps the time", p.evaluate(REC, Ts).get("workoutMs")==first)
    check("timer: and offers a second session",
          "again" in p.eval_on_selector("#startWorkout","e=>e.textContent").lower(),
          p.eval_on_selector("#startWorkout","e=>e.textContent"))
    p.click("#startWorkout"); p.wait_for_timeout(1600)
    p.click("#lockDay"); p.wait_for_timeout(700)
    second=p.evaluate(REC, Ts)["workoutMs"]
    check("timer: a second session tops up rather than replacing",
          second > first, "%d -> %d ms" % (first, second))
    p.click("#unlockDay"); p.wait_for_timeout(600)

    # a mis-tap must be throwable away, with undo like everything destructive
    p.click("#startWorkout"); p.wait_for_timeout(500)
    p.click("#discardWorkout"); p.wait_for_timeout(600)
    check("timer: a running clock can be discarded",
          "workoutStart" not in p.evaluate(REC, Ts))
    check("timer: discarding offers undo",
          p.evaluate("()=>!document.getElementById('undobar').hidden"))
    p.click("#undoBtn"); p.wait_for_timeout(600)
    check("timer: undo brings the clock back",
          "workoutStart" in p.evaluate(REC, Ts))
    p.click("#discardWorkout"); p.wait_for_timeout(500)

    # A clock running for seven hours will not be banked when the day is
    # locked in, so the bar has to say so first. Locking in and silently
    # keeping nothing is rule 3 wearing a different hat.
    p.evaluate("""k=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));
                      s.days[k].workoutStart = Date.now() - 7*3600*1000;
                      delete s.days[k].workoutMs;
                      localStorage.setItem('iron-ledger-v1', JSON.stringify(s));}""", Ts)
    p.reload(); p.wait_for_timeout(1000)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
    check("timer: a clock past saving stops looking live",
          p.evaluate("()=>!!document.querySelector('.workout.is-stale')"))
    note = p.eval_on_selector_all(".wo-note", "e=>e.map(x=>x.textContent).join('')")
    check("timer: and says it will not be saved", "not be saved" in note, note)
    p.click("#lockDay"); p.wait_for_timeout(700)
    check("timer: locking in does not invent a seven hour session",
          not p.evaluate(REC, Ts).get("workoutMs"),
          "workoutMs=%s" % p.evaluate(REC, Ts).get("workoutMs"))
    check("timer: and the day keeps its lifts", len(p.evaluate(REC, Ts)["lifts"]) > 0)
    p.click("#unlockDay"); p.wait_for_timeout(600)

    # ---------- SPLITS ARE THE USER'S, NOT OURS ----------
    NAMES="()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).routine.days.map(d=>d.name)"
    check("splits: + sits in the chip row", p.evaluate("()=>!!document.getElementById('addSplitChip')"))
    ab=p.locator("#addSplitChip").bounding_box()
    check("splits: + is a proper target", ab and ab["height"]>=MIN_TAP,
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
    check("splits: rename field clears 44px", nb and nb["height"]>=MIN_TAP, nb and "%dx%d"%(nb["width"],nb["height"]))
    check("splits: remove clears 44px", rb and rb["height"]>=MIN_TAP, rb and "%dx%d"%(rb["width"],rb["height"]))
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
    FINDNOTE="n=>{const d=JSON.parse(localStorage.getItem('iron-ledger-v1')).days||{}; for(const k of Object.keys(d)) for(const f of (d[k].food||[])) if((f.note||'').indexOf(n)===0) return f; return null;}"
    before=p.evaluate(TOTAL)
    row=p.evaluate("""()=>{const b=document.querySelector('[data-addpan]');if(!b)return null;
        const it=b.closest('.pan-item');return {id:b.dataset.addpan,name:it.querySelector('.nm').textContent};}""")
    check("pantry: every good food offers +", row is not None, str(row))
    box=p.locator("[data-addpan]").first.bounding_box()
    check("pantry: + is 44px", box and box["width"]>=MIN_TAP and box["height"]>=MIN_TAP,
          box and "%dx%d"%(box["width"],box["height"]))
    p.locator("[data-addpan]").first.click(); p.wait_for_timeout(500)
    # + asks how much before it writes anything. It used to log exactly one
    # saved serving, so four slices of bacon meant pressing it four times and
    # combining the rows afterwards.
    check("pantry: + asks how much rather than logging blind",
          p.evaluate("()=>!document.getElementById('panSheet').hidden")
          and p.evaluate(TOTAL)==before,
          "rows %d -> %d"%(before, p.evaluate(TOTAL)))
    check("pantry: the sheet names the food and its saved serving",
          row["name"] in p.eval_on_selector("#panSheetName","e=>e.textContent")
          and "Saved as" in p.eval_on_selector("#panSheetSub","e=>e.textContent"),
          p.eval_on_selector("#panSheetSub","e=>e.textContent"))
    for sel in ("#panQtyDown", "#panQty", "#panQtyUp", "#panAddBtn", "#panCancel"):
        bb=p.locator(sel).bounding_box()
        check("pantry: %s clears 44px"%sel, bb and bb["height"]>=MIN_TAP,
              bb and "%dx%d"%(bb["width"],bb["height"]))
    # whatever this food is saved in, the sheet opens on one serving of it
    kcalOf=lambda t: float(re.search(r"([\d,]+) kcal", t).group(1).replace(",",""))
    startQty=float(p.input_value("#panQty"))
    one=p.eval_on_selector("#panSheetTotal","e=>e.textContent")
    p.click("#panQtyUp"); p.wait_for_timeout(300)
    up=p.eval_on_selector("#panSheetTotal","e=>e.textContent")
    check("pantry: the stepper moves the number and the total",
          float(p.input_value("#panQty"))>startQty and kcalOf(up)>kcalOf(one),
          "%s -> %s"%(one,up))
    p.click("#panQtyDown"); p.wait_for_timeout(300)
    check("pantry: back down reads the same as it started",
          p.eval_on_selector("#panSheetTotal","e=>e.textContent")==one,
          "%s vs %s"%(one, p.eval_on_selector("#panSheetTotal","e=>e.textContent")))

    # nothing eaten is not something to log, and a button that just sits there
    # reads exactly like a dead one
    p.fill("#panQty","0"); p.wait_for_timeout(300)
    check("pantry: zero cannot be added",
          p.eval_on_selector("#panAddBtn","e=>e.disabled"))
    check("pantry: and it says why rather than sitting there",
          "How many" in p.eval_on_selector("#panSheetTotal","e=>e.textContent"),
          p.eval_on_selector("#panSheetTotal","e=>e.textContent"))
    # double the serving; the calories have to double with it
    p.fill("#panQty", str(startQty*2)); p.wait_for_timeout(300)
    two=p.eval_on_selector("#panSheetTotal","e=>e.textContent")
    check("pantry: twice the amount is twice the calories",
          abs(kcalOf(two)-kcalOf(one)*2)<=2, "%s -> %s"%(one,two))

    p.click("#panAddBtn"); p.wait_for_timeout(700)
    after=p.evaluate(TOTAL)
    check("pantry: adding logs one row for the whole amount", after==before+1,
          "%d -> %d"%(before,after))
    check("pantry: and the sheet closes behind it",
          p.evaluate("()=>document.getElementById('panSheet').hidden"))
    logged=p.evaluate(FINDNOTE, row["name"])
    check("pantry: the row carries the doubled figure, not the saved one",
          bool(logged) and abs(logged["cal"]-kcalOf(one)*2)<=2,
          json.dumps(logged)+" vs one serving "+str(kcalOf(one)))
    check("pantry: the ledger records how much, not just what",
          bool(logged) and logged["note"]!=row["name"] and two.split(" \u00b7 ")[0] in logged["note"],
          "%r vs %r" % (logged and logged["note"], two))
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

    # ---------- A COUNT IS ONE OF THE THING ----------
    # Typing 4 and picking "slice" means "one serving is four slices", and
    # every line in the app then read "1 slice · 172 kcal" — a fourfold
    # overcount stated with complete confidence.
    p.fill("#panName","test rashers"); p.fill("#panServe","4")
    p.select_option("#panUnit","slice"); p.fill("#panCal","200"); p.fill("#panPro","12")
    p.click("#savePan"); p.wait_for_timeout(600)
    warn=p.evaluate("()=>{const w=document.getElementById('panWarn');return w&&!w.hidden?w.textContent:'';}")
    check("count: saving four of something says it stored one",
          "1 slice" in warn and "50" in warn, warn or "(said nothing)")
    sub=p.evaluate("()=>{const r=[...document.querySelectorAll('.pan-item')]"
                   ".find(x=>x.querySelector('.nm').textContent==='test rashers');"
                   " return r?r.querySelector('.sub').textContent:'';}")
    check("count: and the list says one slice at one slice's calories",
          "1 slice" in sub and "50 kcal" in sub, sub)
    rid=p.evaluate("()=>{const r=[...document.querySelectorAll('[data-addpan]')]"
                   ".find(b=>b.closest('.pan-item').querySelector('.nm').textContent==='test rashers');"
                   " return r?r.dataset.addpan:null;}")
    p.click('[data-addpan="%s"]'%rid); p.wait_for_timeout(500)
    p.fill("#panQty","4"); p.wait_for_timeout(300)
    check("count: four of them adds back up to what was typed",
          "200 kcal" in p.eval_on_selector("#panSheetTotal","e=>e.textContent"),
          p.eval_on_selector("#panSheetTotal","e=>e.textContent"))
    p.click("#panCancel"); p.wait_for_timeout(300)

    # a record saved before that normalising existed is still read correctly
    STALE="()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1')); s.pantry.push({id:'stale4',name:'old bacon',serveQty:4,serveUnit:'slice',serveG:null,sCal:172,sPro:12,aliases:[]}); localStorage.setItem('iron-ledger-v1', JSON.stringify(s)); return true;}"
    p.evaluate(STALE); p.reload(); p.wait_for_timeout(900)
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
    oldsub=p.evaluate("()=>{const r=[...document.querySelectorAll('.pan-item')]"
                      ".find(x=>x.querySelector('.nm').textContent==='old bacon');"
                      " return r?r.querySelector('.sub').textContent:'';}")
    check("count: an already-saved four-slice record reads as one slice too",
          "1 slice" in oldsub and "43 kcal" in oldsub, oldsub)

    # ---------- SWITCHING A UNIT CONVERTS ----------
    # Re-reading 340 g as 340 oz is nine kilos of yogurt logged in one tap.
    oid=p.evaluate("()=>{const r=[...document.querySelectorAll('[data-addpan]')]"
                   ".find(b=>b.closest('.pan-item').querySelector('.nm').textContent==='Bulk oats');"
                   " return r?r.dataset.addpan:null;}")
    p.click('[data-addpan="%s"]'%oid); p.wait_for_timeout(500)
    check("units: a weight food offers other weights",
          p.eval_on_selector_all("#panQtyUnit option","e=>e.map(x=>x.value)")==["g","oz","lb"],
          str(p.eval_on_selector_all("#panQtyUnit option","e=>e.map(x=>x.value)")))
    gq=float(p.input_value("#panQty")); gt=p.eval_on_selector("#panSheetTotal","e=>e.textContent")
    p.select_option("#panQtyUnit","oz"); p.wait_for_timeout(400)
    oq=float(p.input_value("#panQty")); ot=p.eval_on_selector("#panSheetTotal","e=>e.textContent")
    check("units: switching converts the number",
          abs(oq-gq/28.3495)<0.05, "%s g -> %s oz"%(gq,oq))
    check("units: and does not move a single calorie",
          kcalOf(ot)==kcalOf(gt), "%s -> %s"%(gt,ot))
    p.click("#panCancel"); p.wait_for_timeout(300)

    # ---------- LOG ----------
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
    check("log: 12 months render", p.eval_on_selector_all(".month","e=>e.length")==12)
    check("log: today ringed", p.eval_on_selector_all(".cal-cell.is-today","e=>e.length")==1)
    check("log: stats row", p.eval_on_selector_all(".yearstats b","e=>e.length")==4,
          " | ".join(p.eval_on_selector_all(".yearstats div","e=>e.map(x=>x.textContent)")))
    check("log: the year knows how long you trained",
          "Avg session" in " ".join(p.eval_on_selector_all(".yearstats span","e=>e.map(x=>x.textContent)")))
    yr0=p.text_content(".yearnav .y")
    p.click("#nextYear"); p.wait_for_timeout(500)
    check("log: year nav", p.text_content(".yearnav .y")!=yr0)
    p.click("#prevYear"); p.wait_for_timeout(500)
    p.eval_on_selector_all(".cal-cell.hit, .cal-cell.miss","e=>{if(e.length)e[0].click()}"); p.wait_for_timeout(500)
    check("log: tap day jumps to macros", p.evaluate("()=>document.querySelector('.tabs button[data-tab=macros]').getAttribute('aria-selected')")=="true")

    MARKS="()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1')); const k=Object.keys(s.days).sort().pop(); return s.days[k].supps||{};}"
    # ---------- THE DAILY CHECKLIST ----------
    # Creatine and a multivitamin have no calories worth logging, but whether
    # you took them is the thing you want to see across a week.
    check("checklist: nothing on macros until there is a list",
          p.locator(".supps").count()==0)
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
    for nm, ds in [("Ashwagandha","2 pills"), ("Creatine","5 g")]:
        p.fill("#suppNameIn", nm); p.fill("#suppDoseIn", ds)
        p.click("#addSupp"); p.wait_for_timeout(350)
    check("checklist: the pantry builds the list",
          p.locator(".supp-item").count()==2,
          str(p.eval_on_selector_all(".supp-item .nm","e=>e.map(x=>x.textContent)")))
    p.fill("#suppNameIn",""); p.click("#addSupp"); p.wait_for_timeout(300)
    check("checklist: a nameless one is not added",
          p.locator(".supp-item").count()==2)

    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(500)
    # Pin the day first. Earlier sections leave the cursor on whatever they
    # were looking at, and a reload snaps back to today — so ticking here and
    # asserting after a reload would be comparing two different days.
    if not p.evaluate("()=>document.getElementById('todayBtn').hidden"):
        p.click("#todayBtn"); p.wait_for_timeout(400)
    check("checklist: it appears on macros", p.locator(".supp").count()==2)
    check("checklist: under the target bar and above the add form",
          p.evaluate("()=>{const s=document.querySelector('.supps'),"
                     "g=document.querySelector('.goalbar'),e=document.querySelector('.entry');"
                     " return s.getBoundingClientRect().top>g.getBoundingClientRect().top"
                     " && s.getBoundingClientRect().top<e.getBoundingClientRect().top;}"))
    for i in range(2):
        bb=p.locator(".supp").nth(i).bounding_box()
        check("checklist: row %d is a proper target"%i, bb and bb["height"]>=MIN_TAP,
              bb and "%dx%d"%(bb["width"],bb["height"]))
    check("checklist: it starts at none taken",
          p.eval_on_selector(".supp-count","e=>e.textContent")=="0 of 2",
          p.eval_on_selector(".supp-count","e=>e.textContent"))

    # the whole reason this is patched in place instead of redrawn
    p.fill("#fCal","450"); p.fill("#fNote","half typed")
    p.locator(".supp").first.click(); p.wait_for_timeout(400)
    check("checklist: ticking does not wipe a half-typed entry",
          p.input_value("#fCal")=="450" and p.input_value("#fNote")=="half typed",
          "%r %r"%(p.input_value("#fCal"), p.input_value("#fNote")))
    check("checklist: the tick shows on the row",
          p.eval_on_selector(".supp","e=>e.classList.contains('is-on')")
          and p.eval_on_selector(".supp","e=>e.getAttribute('aria-pressed')")=="true")
    check("checklist: and the count follows it",
          p.eval_on_selector(".supp-count","e=>e.textContent")=="1 of 2",
          p.eval_on_selector(".supp-count","e=>e.textContent"))
    p.locator(".supp").first.click(); p.wait_for_timeout(350)
    check("checklist: tapping again takes it back off",
          p.eval_on_selector(".supp-count","e=>e.textContent")=="0 of 2"
          and not p.eval_on_selector(".supp","e=>e.classList.contains('is-on')"))
    p.locator(".supp").nth(0).click(); p.locator(".supp").nth(1).click(); p.wait_for_timeout(400)
    check("checklist: all of them says so",
          p.eval_on_selector(".supp-count","e=>e.classList.contains('is-done')"))
    p.reload(); p.wait_for_timeout(900)
    check("checklist: it survives a reload",
          p.eval_on_selector(".supp-count","e=>e.textContent")=="2 of 2")

    # ---------- AND IT REACHES THE CALENDAR ----------
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(700)
    check("checklist: a complete day is marked on the calendar",
          p.eval_on_selector_all(".cal-cell.supps-all","e=>e.length")==1,
          "%d marked"%p.eval_on_selector_all(".cal-cell.supps-all","e=>e.length"))
    check("checklist: the day says so in full",
          "checklist done" in p.eval_on_selector(".cal-cell.supps-all","e=>e.title"),
          p.eval_on_selector(".cal-cell.supps-all","e=>e.title"))
    tiles=p.eval_on_selector_all(".yearstats div","e=>e.map(x=>x.textContent)")
    check("checklist: the year gains two tiles, keeping the grid even",
          len(tiles)==6 and any("Checklist days" in t for t in tiles)
          and any("Best run" in t for t in tiles), " | ".join(tiles))
    check("checklist: the legend explains the mark",
          any("Checklist done" in x for x in
              p.eval_on_selector_all(".legend span","e=>e.map(y=>y.textContent)")))

    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(500)
    p.locator(".supp").first.click(); p.wait_for_timeout(350)
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
    check("checklist: missing one takes the mark away",
          p.eval_on_selector_all(".cal-cell.supps-all","e=>e.length")==0)
    check("checklist: and the day names what was missed",
          "missed Ashwagandha" in p.eval_on_selector(".cal-cell.is-today","e=>e.title"),
          p.eval_on_selector(".cal-cell.is-today","e=>e.title"))

    # ---------- RENAMING KEEPS HISTORY, REMOVING KEEPS THE NAME ----------
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
    was=p.evaluate(MARKS)
    p.locator("[data-editsupp]").first.click(); p.wait_for_timeout(400)
    rb=p.locator("#suppRename").bounding_box()
    check("checklist: the rename field is a proper target", rb and rb["height"]>=MIN_TAP,
          rb and "%dx%d"%(rb["width"],rb["height"]))
    p.fill("#suppRename","Ashwagandha KSM-66"); p.click("#suppSaveEdit"); p.wait_for_timeout(500)
    check("checklist: renaming takes",
          p.eval_on_selector_all(".supp-item .nm","e=>e.map(x=>x.textContent)")[0]=="Ashwagandha KSM-66",
          str(p.eval_on_selector_all(".supp-item .nm","e=>e.map(x=>x.textContent)")))
    check("checklist: and the days you already ticked follow it",
          p.evaluate(MARKS)==was, "%s -> %s"%(was, p.evaluate(MARKS)))

    p.locator("[data-rmsupp]").last.click(); p.wait_for_timeout(500)
    check("checklist: removing takes it off the list",
          p.locator(".supp-item").count()==1)
    check("checklist: it offers undo rather than a dialog",
          p.evaluate("()=>!document.getElementById('undobar').hidden"))
    check("checklist: and keeps the name for the days you took it",
          (p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).suppsRetired")
           or {}) != {},
          str(p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).suppsRetired")))
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
    check("checklist: a tick for something dropped is still named",
          "no longer on your list" in p.eval_on_selector(".cal-cell.is-today","e=>e.title"),
          p.eval_on_selector(".cal-cell.is-today","e=>e.title"))
    p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
    p.click("#undoBtn"); p.wait_for_timeout(500)
    check("checklist: undo puts it back",
          p.locator(".supp-item").count()==2,
          str(p.eval_on_selector_all(".supp-item .nm","e=>e.map(x=>x.textContent)")))

    # ---------- SETTINGS ----------
    # The gear lives in the header, so it has to be there whichever tab you
    # are on — a setting you can only reach from one screen is a hunt.
    ATTR="()=>[document.documentElement.getAttribute('data-theme'), document.documentElement.getAttribute('data-accent')]"
    ACC="()=>getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"
    META="()=>{const m=document.querySelector('meta[name=theme-color]');return m&&m.content;}"
    for t in ["macros","pantry","gym","coach","log"]:
        p.click('.tabs button[data-tab="%s"]'%t); p.wait_for_timeout(250)
        if not p.locator("#setBtn").is_visible():
            check("settings: the gear is on %s"%t, False); break
    else:
        check("settings: the gear is on every tab", True)
    gb=p.locator("#setBtn").bounding_box()
    check("settings: the gear is a proper target", gb and gb["width"]>=MIN_TAP and gb["height"]>=MIN_TAP,
          gb and "%dx%d"%(gb["width"],gb["height"]))
    teal=p.evaluate(ACC)
    p.click("#setBtn"); p.wait_for_timeout(400)
    check("settings: the gear opens the sheet",
          p.evaluate("()=>!document.getElementById('setSheet').hidden"))
    check("settings: it starts on the phone's own look and teal",
          p.eval_on_selector_all("#setSheet [aria-pressed=true]","e=>e.map(x=>x.textContent)")==["Match phone","Teal"],
          str(p.eval_on_selector_all("#setSheet [aria-pressed=true]","e=>e.map(x=>x.textContent)")))
    small=[x for x in p.eval_on_selector_all("#setSheet button",
           "e=>e.map(b=>[b.textContent.trim()||b.getAttribute('aria-label'),Math.round(b.getBoundingClientRect().height)])")
           if x[1]<44]
    check("settings: every control in it clears 44px", not small, str(small))

    p.click('[data-pick-theme="dark"]'); p.wait_for_timeout(300)
    check("settings: Dark takes effect at once", p.evaluate(ATTR)[0]=="dark")
    check("settings: and the status bar follows it, not the phone",
          p.evaluate(META)=="#191F1D", p.evaluate(META))
    check("settings: native controls go dark with it",
          p.evaluate("()=>document.documentElement.style.colorScheme")=="dark")
    check("settings: the choice is marked",
          p.eval_on_selector('[data-pick-theme="dark"]',"e=>e.getAttribute('aria-pressed')")=="true")

    # Each accent changes the colour on screen, and its swatch shows the colour
    # it actually applies. The palette lives twice in the CSS — once to apply,
    # once for the swatch — and this is what stops the two drifting apart.
    for th in ["light","dark"]:
        p.click('[data-pick-theme="%s"]'%th); p.wait_for_timeout(250)
        seen=set()
        for acc in ["teal","blue","violet","orange","graphite"]:
            p.click('[data-pick-accent="%s"]'%acc); p.wait_for_timeout(250)
            applied=p.evaluate(ACC)
            shown=p.evaluate("a=>getComputedStyle(document.querySelector('.sw-'+a)).getPropertyValue('--sw').trim()", acc)
            check("settings: %s %s swatch matches what it applies"%(th,acc),
                  applied.lower()==shown.lower(), "applies %s, shows %s"%(applied,shown))
            seen.add(applied.lower())
        check("settings: five %s accents are five different colours"%th, len(seen)==5, str(sorted(seen)))

    p.click('[data-pick-accent="blue"]'); p.wait_for_timeout(250)
    blue=p.evaluate(ACC)
    p.click("#setDone"); p.wait_for_timeout(300)
    check("settings: Done closes it",
          p.evaluate("()=>document.getElementById('setSheet').hidden"))
    p.reload(); p.wait_for_timeout(900)
    check("settings: the look survives a reload", p.evaluate(ATTR)==["dark","blue"], str(p.evaluate(ATTR)))
    check("settings: it lives in the log, so a backup carries it",
          p.evaluate("()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));return [s.theme,s.accent];}")==["dark","blue"])
    check("settings: and in the small key read before the first paint",
          p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-look')||'{}')")=={"theme":"dark","accent":"blue"},
          str(p.evaluate("()=>localStorage.getItem('iron-ledger-look')")))
    # Left on dark and blue on purpose: the restore below wipes the phone and
    # has to bring the look back along with everything else.

    # ---------- BACKUP / RESTORE ----------
    p.click("#backupBtn"); p.wait_for_timeout(400)
    txt=p.evaluate("()=>document.getElementById('backupText').value")
    check("backup: produces JSON", txt.startswith("{") and '"pantry"' in txt)
    check("backup: shows build", "Build" in p.text_content("#diag"))
    payload=json.loads(txt)
    # wipe and restore
    p.evaluate("()=>{document.getElementById('closeSheet').click();}"); p.wait_for_timeout(200)
    p.evaluate("()=>{localStorage.removeItem('iron-ledger-v1'); localStorage.removeItem('iron-ledger-look');}")
    p.reload(); p.wait_for_timeout(900)
    check("restore: a wiped phone starts on the default look",
          p.evaluate(ATTR)==[None,None], str(p.evaluate(ATTR)))
    p.click("#backupBtn"); p.wait_for_timeout(300)
    p.evaluate("t=>{document.getElementById('backupText').value=t;}", txt)
    p.click("#restoreBtn"); p.wait_for_timeout(600)
    after=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
    check("restore: the look comes back and is applied",
          [after.get("theme"), after.get("accent")]==["dark","blue"] and p.evaluate(ATTR)==["dark","blue"],
          "stored %s, on screen %s" % ([after.get("theme"), after.get("accent")], p.evaluate(ATTR)))
    check("restore: days come back", len(after.get("days",{}))==len(payload.get("days",{})),
          "%d of %d days" % (len(after.get("days",{})), len(payload.get("days",{}))))
    check("restore: pantry comes back", len(after.get("pantry",[]))==len(payload.get("pantry",[])),
          "%d of %d pantry items" % (len(after.get("pantry",[])), len(payload.get("pantry",[]))))
    check("restore: goal comes back", after.get("goal")==payload.get("goal"),
          "got %s" % json.dumps(after.get("goal")))
    # The routine and its movements are the part a shared plan would be made of,
    # so a backup that drops them is a backup that cannot carry one.
    check("restore: the routine comes back",
          [x["name"] for x in after.get("routine",{}).get("days",[])] ==
          [x["name"] for x in payload.get("routine",{}).get("days",[])],
          str([x["name"] for x in after.get("routine",{}).get("days",[])]))
    check("restore: each day keeps its movements",
          all(sorted(after.get("moves",{}).get(k,[])) == sorted(v)
              for k, v in (payload.get("moves") or {}).items()),
          "%d day lists" % len(payload.get("moves") or {}))
    check("restore: retired names come back",
          all(k in after.get("retired",{}) for k in (payload.get("retired") or {})),
          str(after.get("retired")))
    check("restore: region comes back", after.get("region")==payload.get("region"),
          "got %s want %s" % (after.get("region"), payload.get("region")))

    # ---------- EACH MOVEMENT'S TIME ----------
    # Its own page, on a clock the test moves by hand: a seven minute set of
    # rows takes seven minutes to the app and none to the suite, and the laps
    # come out exact rather than depending on how fast the clicks land. Pinned
    # to noon so advancing it can never cross midnight.
    LAPCLOCK = """
      const REAL = Date;
      const noon = new REAL(); noon.setHours(12, 0, 0, 0);
      let off = noon.getTime() - REAL.now();
      window.__advance = ms => { off += ms; };
      class FD extends REAL {
        constructor(...a) { if (!a.length) super(REAL.now() + off); else super(...a); }
        static now() { return REAL.now() + off; }
      }
      window.Date = FD;"""
    MIN = 60000
    LAPS = ("()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));"
            "const k=Object.keys(s.days).sort().pop();"
            "return s.days[k].lifts.map(l=>({m:l.movement,closed:!!l.closed,"
            "lap:l.lapMs===undefined?'unset':l.lapMs}));}")

    def lap_page():
        c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
        c.add_init_script("delete window.claude;"); c.add_init_script(LAPCLOCK)
        q = c.new_page()
        q.on("pageerror", lambda e: errs.append("laps: "+str(e)))
        q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(900)
        try: q.click("text=Got it", timeout=1500)
        except Exception: pass
        q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
        return c, q
    def add(q, mv):
        q.select_option("#mSel", label=mv); q.click("#addLift"); q.wait_for_timeout(300)
    def sets(q, i, n, gap):
        for _ in range(n):
            q.fill('[data-w="%d"]'%i, "95"); q.fill('[data-r="%d"]'%i, "10")
            q.click('[data-addset="%d"]'%i); q.wait_for_timeout(120)
            q.evaluate("ms=>window.__advance(ms)", gap)
    # The test clock moves by hand but also ticks with real time, and a drag
    # costs a few real seconds. Ten seconds is still far finer than any
    # distinction these checks draw, which are whole minutes apart.
    def near(ms, minutes): return ms not in (None,"unset") and abs(ms - minutes*MIN) < 10000

    c, q = lap_page()
    q.click("#startWorkout"); q.wait_for_timeout(300)
    q.evaluate("ms=>window.__advance(ms)", MIN)
    add(q, "Barbell Row")
    check("laps: no Done before there is a set to be done with",
          q.locator("[data-done]").count()==0)
    sets(q, 0, 3, 2*MIN)
    db=q.locator("[data-done]").bounding_box()
    check("laps: Done appears once there is a set", db is not None)
    check("laps: Done is a proper target", db and db["height"]>=MIN_TAP, db and "%dx%d"%(db["width"],db["height"]))
    q.click('[data-done="0"]'); q.wait_for_timeout(350)
    r=q.evaluate(LAPS)
    check("laps: the first runs from Start workout", near(r[0]["lap"], 7), "%s ms, want ~7 min" % r[0]["lap"])
    check("laps: Done folds the card", r[0]["closed"] and q.locator(".lift.is-closed").count()==1)
    check("laps: nothing left on it to hit by accident",
          q.locator(".lift.is-closed [data-w], .lift.is-closed button.set, .lift.is-closed [data-rmlift], "
                    ".lift.is-closed [data-done]").count()==0)
    check("laps: it shows the time",
          q.eval_on_selector(".lift.is-closed .lap","e=>e.textContent")=="7:00"
          or q.eval_on_selector(".lift.is-closed .lap","e=>e.textContent").startswith("7:0"),
          q.eval_on_selector(".lift.is-closed .lap","e=>e.textContent"))
    check("laps: and says so as it happens",
          "Finished Barbell Row" in q.eval_on_selector("#undobar","e=>e.textContent"),
          q.eval_on_selector("#undobar","e=>e.textContent"))
    rb=q.locator("[data-reopen]").bounding_box()
    check("laps: Reopen is a proper target", rb and rb["height"]>=MIN_TAP, rb and "%dx%d"%(rb["width"],rb["height"]))

    q.evaluate("ms=>window.__advance(ms)", MIN)
    add(q, "Lat Pulldown"); sets(q, 1, 3, 3*MIN)
    q.click('[data-done="1"]'); q.wait_for_timeout(350)
    r=q.evaluate(LAPS)
    check("laps: the next runs from the last Done, not from the start",
          near(r[1]["lap"], 10), "%s ms, want ~10 min" % r[1]["lap"])

    # a Done tapped a set early is taken back, and the real one times it
    q.evaluate("ms=>window.__advance(ms)", MIN)
    add(q, "Seated Cable Row"); sets(q, 2, 1, 2*MIN)
    q.click('[data-done="2"]'); q.wait_for_timeout(350)
    q.click("#undoBtn"); q.wait_for_timeout(350)
    r=q.evaluate(LAPS)
    check("laps: undo reopens it and forgets the time",
          not r[2]["closed"] and r[2]["lap"]=="unset" and q.locator('[data-w="2"]').count()==1, str(r[2]))
    sets(q, 2, 2, 2*MIN)
    q.click('[data-done="2"]'); q.wait_for_timeout(350)
    check("laps: the real Done takes the time again",
          near(q.evaluate(LAPS)[2]["lap"], 7), "%s ms, want ~7 min" % q.evaluate(LAPS)[2]["lap"])

    # reopening to fix a number keeps the time
    kept=q.evaluate(LAPS)[0]["lap"]
    q.click('[data-reopen="0"]'); q.wait_for_timeout(300)
    check("laps: Reopen opens it for editing",
          not q.evaluate(LAPS)[0]["closed"] and q.locator('[data-w="0"]').count()==1)
    q.evaluate("ms=>window.__advance(ms)", 5*MIN)
    q.click('[data-done="0"]'); q.wait_for_timeout(300)
    check("laps: closing it again keeps the time it had", q.evaluate(LAPS)[0]["lap"]==kept,
          "%s -> %s" % (kept, q.evaluate(LAPS)[0]["lap"]))

    # nobody taps Done on the last one before locking in
    q.evaluate("ms=>window.__advance(ms)", MIN)
    add(q, "Barbell Curl"); sets(q, 3, 3, 2*MIN)
    q.click("#lockDay"); q.wait_for_timeout(700)
    r=q.evaluate(LAPS)
    check("laps: Lock in the day times the one you were still on",
          r[3]["closed"] and near(r[3]["lap"], 12), "%s ms, want ~12 min" % r[3]["lap"])
    check("laps: a locked day offers no Reopen", q.locator("[data-reopen]").count()==0)
    q.reload(); q.wait_for_timeout(900)
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    check("laps: the times survive a reload",
          [x["lap"] for x in q.evaluate(LAPS)]==[x["lap"] for x in r])
    c.close()

    # ---------- START FORGOTTEN ----------
    # Found in the gym: Start was never pressed, so the whole session went
    # untimed. The first set of the day starts the clock now, at that set.
    DAY = ("k=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));"
           "return (s.days||{})[k]||{};}")
    c, q = lap_page()
    add(q, "Barbell Row")
    check("clock: Start is still offered before the first set", q.locator("#startWorkout").count()==1)
    sets(q, 0, 3, 2*MIN)
    rec=q.evaluate(DAY, Ts)
    check("clock: the first set starts it when Start was forgotten", bool(rec.get("workoutStart")))
    check("clock: from that set, not from whenever it is noticed",
          rec.get("workoutStart")==rec["lifts"][0]["sets"][0]["t"],
          "%s vs %s" % (rec.get("workoutStart"), rec["lifts"][0]["sets"][0].get("t")))
    check("clock: and it says so", q.evaluate("()=>!document.getElementById('undobar').hidden")
          and "first set" in q.eval_on_selector("#undoLabel","e=>e.textContent"),
          q.eval_on_selector("#undoLabel","e=>e.textContent"))
    # an Undo there would sit right above the rest timer's Start
    check("clock: with nothing on the bar to press", q.locator("#undoBtn").bounding_box() is None)
    q.click('[data-done="0"]'); q.wait_for_timeout(350)
    check("clock: the first movement's time runs from that set",
          near(q.evaluate(LAPS)[0]["lap"], 6), "%s ms, want ~6 min" % q.evaluate(LAPS)[0]["lap"])
    ub=q.locator("#undoBtn").bounding_box()
    check("clock: the next thing that can be undone gets its Undo back",
          ub is not None and ub["height"]>=MIN_TAP
          and "Finished" in q.eval_on_selector("#undoLabel","e=>e.textContent"))
    # a day already timed was decided on; a set does not reopen the question
    q.click("#lockDay"); q.wait_for_timeout(700)
    q.click("#unlockDay"); q.wait_for_timeout(500)
    add(q, "Lat Pulldown"); sets(q, 1, 1, MIN)
    check("clock: a day already timed is not restarted by a set",
          not q.evaluate(DAY, Ts).get("workoutStart"))
    # a set typed into another day is a record being filled in, not a session
    YK=(T-datetime.timedelta(days=1)).isoformat()
    q.click("#prevDay"); q.wait_for_timeout(400)
    add(q, "Barbell Row"); sets(q, 0, 1, MIN)
    yrec=q.evaluate(DAY, YK)
    check("clock: a set typed into yesterday starts no clock",
          len(yrec.get("lifts") or [])==1 and not yrec.get("workoutStart"), str(yrec.get("workoutStart")))
    c.close()

    # ---------- AND THE WAYS IT MUST NOT LIE ----------
    c, q = lap_page()
    add(q, "Barbell Row"); sets(q, 0, 1, 2*MIN)
    # the first set started the clock; Discard is how a session goes untimed
    # now, and a set after that must not quietly start it again
    q.eval_on_selector("#discardWorkout","e=>e.scrollIntoView({block:'center'})")
    q.click("#discardWorkout"); q.wait_for_timeout(350)
    sets(q, 0, 1, 2*MIN)
    check("clock: a clock thrown away stays thrown away",
          not q.evaluate(DAY, Ts).get("workoutStart") and q.locator("#startWorkout").count()==1)
    q.click('[data-done="0"]'); q.wait_for_timeout(350)
    check("laps: no clock running means no time, not a guess",
          q.evaluate(LAPS)[0]["lap"] is None
          and q.eval_on_selector(".lift.is-closed .lap","e=>e.textContent")=="not timed")

    q.click("#startWorkout"); q.wait_for_timeout(300)
    add(q, "Lat Pulldown"); add(q, "Seated Cable Row")
    for _ in range(3):
        sets(q, 1, 1, 90000); sets(q, 2, 1, 90000)
    q.click('[data-done="1"]'); q.wait_for_timeout(300)
    q.evaluate("ms=>window.__advance(ms)", 30000)
    q.click('[data-done="2"]'); q.wait_for_timeout(300)
    check("laps: a superset partner is not handed the other's time",
          q.evaluate(LAPS)[2]["lap"] is None, str(q.evaluate(LAPS)[2]))

    add(q, "T-Bar Row"); sets(q, 3, 1, 1000)
    q.evaluate("ms=>window.__advance(ms)", 7*60*MIN)
    q.click('.tabs button[data-tab="macros"]'); q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(300)
    q.click('[data-done="3"]'); q.wait_for_timeout(300)
    check("laps: a clock left running is not a seven hour set",
          q.evaluate(LAPS)[3]["lap"] is None, str(q.evaluate(LAPS)[3]))
    c.close()

    # two movements still open at lock: no telling whose time is whose
    c, q = lap_page()
    q.click("#startWorkout"); q.wait_for_timeout(300)
    add(q, "Barbell Row"); sets(q, 0, 2, 2*MIN)
    add(q, "Lat Pulldown"); sets(q, 1, 2, 2*MIN)
    q.click("#lockDay"); q.wait_for_timeout(700)
    check("laps: locking with several open times none of them",
          all(x["lap"]=="unset" for x in q.evaluate(LAPS)), str(q.evaluate(LAPS)))
    # spans, not disabled buttons — probe reads a control that does nothing as dead
    check("laps: sets on a locked day's open movements are not controls",
          q.eval_on_selector_all(".set","e=>e.length>0&&e.every(x=>x.tagName==='SPAN')"),
          "%d chips" % q.locator(".set").count())
    c.close()

    # ---------- CHANGE THE MOVEMENT, KEEP THE SETS ----------
    # Found in the gym: Barbell Curl picked when Dumbbell Curl was meant, and
    # the only fix was Remove and add again, losing the sets on the way.
    EL = ("()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));"
          "const k=Object.keys(s.days).sort().pop();"
          "return {lifts:s.days[k].lifts.map(l=>({m:l.movement,sets:l.sets.map(x=>x.w+'x'+x.r+(x.tech?':'+x.tech:''))})),"
          "moves:(s.moves.back||[])};}")
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("edit: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    q.select_option("#mSel", "Barbell Curl"); q.click("#addLift"); q.wait_for_timeout(300)
    for _ in range(2):
        q.fill('[data-w="0"]',"30"); q.fill('[data-r="0"]',"12"); q.click('[data-addset="0"]'); q.wait_for_timeout(150)
    nb=q.locator("[data-editlift]").bounding_box()
    check("edit: the name is a proper target", nb and nb["height"]>=MIN_TAP, nb and "%dx%d"%(nb["width"],nb["height"]))
    q.click("[data-editlift]"); q.wait_for_timeout(300)
    check("edit: tapping the name opens a picker on the current movement",
          q.eval_on_selector("#liftMove","e=>e.value")=="Barbell Curl")
    check("edit: the picker will not zoom the page",
          q.eval_on_selector("#liftMove","e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    small=[x for x in q.eval_on_selector_all(".lift-edit select, .lift-edit button",
           "e=>e.map(b=>[b.id,Math.round(b.getBoundingClientRect().height)])") if x[1]<44]
    check("edit: its controls clear 44px", not small, str(small))
    q.click("#liftMoveCancel"); q.wait_for_timeout(250)
    check("edit: cancel changes nothing", q.evaluate(EL)["lifts"][0]["m"]=="Barbell Curl")
    q.click("[data-editlift]"); q.wait_for_timeout(250)
    q.select_option("#liftMove","Dumbbell Curl"); q.click("#liftMoveSave"); q.wait_for_timeout(350)
    r=q.evaluate(EL)["lifts"][0]
    check("edit: the movement changes", r["m"]=="Dumbbell Curl", r["m"])
    check("edit: and the sets stay with it", r["sets"]==["30x12","30x12"], str(r["sets"]))
    check("edit: it offers undo", "Changed Barbell Curl to Dumbbell Curl" in
          q.eval_on_selector("#undobar","e=>e.textContent"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("edit: undo puts the old name back, sets and all",
          q.evaluate(EL)["lifts"][0]=={"m":"Barbell Curl","sets":["30x12","30x12"]})
    # a name typed in the editor joins the split's list; undo takes a typo back out of it
    q.click("[data-editlift]"); q.wait_for_timeout(250)
    q.select_option("#liftMove","__new"); q.fill("#liftMoveNew","Spider Curl")
    q.click("#liftMoveSave"); q.wait_for_timeout(350)
    r=q.evaluate(EL)
    check("edit: a new name can be typed", r["lifts"][0]["m"]=="Spider Curl")
    check("edit: and it joins the split's movement list", "Spider Curl" in r["moves"])
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("edit: undo takes a typed name back out of the list",
          "Spider Curl" not in q.evaluate(EL)["moves"])

    # ---------- HOW A SET WAS DONE ----------
    tb=q.locator(".tech").bounding_box()
    check("technique: the box sits beside weight and reps", tb is not None)
    check("technique: it is a proper target", tb and tb["height"]>=MIN_TAP, tb and "%dx%d"%(tb["width"],tb["height"]))
    check("technique: its picker will not zoom the page",
          q.eval_on_selector('[data-tech="0"]',"e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    check("technique: it starts on normal",
          q.eval_on_selector('[data-techshow="0"]',"e=>e.textContent")=="normal")
    q.fill('[data-w="0"]',"20"); q.fill('[data-r="0"]',"10")
    q.select_option('[data-tech="0"]',"drop"); q.wait_for_timeout(200)
    check("technique: picking one shows it",
          q.eval_on_selector('[data-techshow="0"]',"e=>e.textContent")=="drop")
    check("technique: and does not wipe weight and reps typed first",
          q.input_value('[data-w="0"]')=="20" and q.input_value('[data-r="0"]')=="10",
          "%r %r"%(q.input_value('[data-w="0"]'),q.input_value('[data-r="0"]')))
    q.click('[data-addset="0"]'); q.wait_for_timeout(300)
    check("technique: the set is stored with it",
          q.evaluate(EL)["lifts"][0]["sets"][-1]=="20x10:drop", str(q.evaluate(EL)["lifts"][0]["sets"]))
    check("technique: a normal set carries nothing extra",
          all(":" not in x for x in q.evaluate(EL)["lifts"][0]["sets"][:-1]))
    check("technique: the box goes back to normal so a tag cannot ride along",
          q.eval_on_selector('[data-techshow="0"]',"e=>e.textContent")=="normal"
          and q.eval_on_selector('[data-tech="0"]',"e=>e.value")=="")
    check("technique: the chip says which set it was",
          q.eval_on_selector_all(".set","e=>e.map(x=>x.textContent)")[-1].endswith("drop"))
    check("technique: the row still fits the phone",
          q.evaluate("()=>document.body.scrollWidth<=document.body.clientWidth"))
    q.click('[data-done="0"]'); q.wait_for_timeout(300)
    check("technique: the finished card keeps it",
          "20×10 drop" in q.eval_on_selector(".lift.is-closed .done-sets","e=>e.textContent"))
    # next session, the Last line says which set was the drop
    q.evaluate("""()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));
      const k=Object.keys(s.days).sort().pop(); const t=new Date(k+'T12:00:00');
      t.setDate(t.getDate()-1); const y=t.toISOString().slice(0,10);
      s.days[y]=JSON.parse(JSON.stringify(s.days[k])); s.days[k].lifts=[];
      localStorage.setItem('iron-ledger-v1', JSON.stringify(s));}""")
    q.reload(); q.wait_for_timeout(900)
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(300)
    q.select_option("#mSel","Barbell Curl"); q.click("#addLift"); q.wait_for_timeout(300)
    check("technique: next time, Last says which set was the drop",
          "20×10 drop" in q.eval_on_selector(".lift .last","e=>e.textContent"),
          q.eval_on_selector(".lift .last","e=>e.textContent"))
    # Most sets are just sets. Never touching the box must be the ordinary
    # path, all the way to closing the movement out.
    for _ in range(3):
        q.fill('[data-w="0"]',"30"); q.fill('[data-r="0"]',"12"); q.click('[data-addset="0"]'); q.wait_for_timeout(150)
    plain=q.evaluate(EL)["lifts"][0]["sets"]
    check("technique: sets with none chosen add like any other",
          plain==["30x12","30x12","30x12"], str(plain))
    q.click('[data-done="0"]'); q.wait_for_timeout(300)
    check("technique: and a movement with none closes out like any other",
          q.locator(".lift.is-closed").count()==1
          and q.eval_on_selector(".lift.is-closed .done-sets","e=>e.textContent")=="30×12, 30×12, 30×12",
          q.eval_on_selector(".lift.is-closed .done-sets","e=>e.textContent"))
    c.close()

    # ---------- ARRANGING: MOVE A MOVEMENT, OR SUPERSET TWO ----------
    # The Macros drag, for movements: picked up by the grip, the cards fold to
    # a line each, and where it lands decides — a card's superset zone joins
    # them, anywhere else moves it. Driven with a mouse here; tests/touch.py
    # drives the same thing with real finger events.
    ORD = ("()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));"
           "const k=Object.keys(s.days).sort().pop();"
           "return s.days[k].lifts.map(l=>l.movement+(l.ss?'*':''));}")
    def mid(q, sel):
        q.eval_on_selector(sel, "e=>e.scrollIntoView({block:'center'})"); q.wait_for_timeout(150)
        bb = q.locator(sel).bounding_box()
        return bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2
    def hold(q, i):
        x, y = mid(q, '[data-grip="%d"]' % i)
        q.mouse.move(x, y); q.mouse.down(); q.wait_for_timeout(200)
    def over(q, sel, dy=None):
        bb = q.locator(sel).bounding_box()
        q.mouse.move(bb["x"]+60, bb["y"]+(bb["height"]/2 if dy is None else dy), steps=8)
        q.wait_for_timeout(150)
    def drop(q):
        q.mouse.up(); q.wait_for_timeout(400)

    c, q = lap_page()
    add(q, "Barbell Curl")
    check("arrange: one movement has nothing to be arranged against",
          q.locator("[data-grip]").count()==0)
    add(q, "Dumbbell Curl"); add(q, "Lat Pulldown")
    for i in range(3):
        sets(q, i, 2, 1000)
    check("arrange: two or more, and each has a grip", q.locator("[data-grip]").count()==3)
    gb=q.locator('[data-grip="0"]').bounding_box()
    check("arrange: the grip is a proper target", gb and gb["width"]>=MIN_TAP and gb["height"]>=MIN_TAP,
          gb and "%dx%d"%(gb["width"],gb["height"]))
    check("arrange: the grip never scrolls the page",
          q.eval_on_selector('[data-grip="0"]',"e=>getComputedStyle(e).touchAction")=="none")
    check("arrange: there is a line saying how", q.locator(".drag-hint").count()==1)

    hold(q, 1)
    heights=q.eval_on_selector_all(".lift","e=>e.map(x=>Math.round(x.getBoundingClientRect().height))")
    check("arrange: picking one up folds every card to a line",
          q.evaluate("()=>document.body.classList.contains('arranging')") and max(heights)<=60, str(heights))
    check("arrange: nothing on a folded card can be hit",
          q.locator(".lift [data-w]:visible, .lift [data-done]:visible, .lift [data-rmlift]:visible").count()==0)
    over(q, '.lift[data-li="0"]', dy=6)
    check("arrange: where it will land is marked",
          q.eval_on_selector('.lift[data-li="0"]',"e=>e.classList.contains('drop-before')"))
    drop(q)
    check("arrange: dropping it moves it (Dumbbell Curl did go first)",
          q.evaluate(ORD)==["Dumbbell Curl","Barbell Curl","Lat Pulldown"], str(q.evaluate(ORD)))
    check("arrange: and says so", "Moved Dumbbell Curl" in q.eval_on_selector("#undobar","e=>e.textContent"))
    check("arrange: the cards unfold again",
          not q.evaluate("()=>document.body.classList.contains('arranging')")
          and q.locator('[data-w="0"]').count()==1)
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("arrange: undo puts the order back",
          q.evaluate(ORD)==["Barbell Curl","Dumbbell Curl","Lat Pulldown"], str(q.evaluate(ORD)))

    # picked up and put straight back: no change, no undo, nothing pressed
    q.evaluate("()=>{document.getElementById('undobar').hidden=true;}")
    hold(q, 2); drop(q)
    check("arrange: put straight back changes nothing and offers nothing",
          q.evaluate(ORD)==["Barbell Curl","Dumbbell Curl","Lat Pulldown"]
          and q.evaluate("()=>document.getElementById('undobar').hidden")
          and q.locator(".lift.is-closed").count()==0
          and q.evaluate("()=>document.getElementById('setEditSheet').hidden"))

    # the owner's superset: Barbell Curl dropped on Dumbbell Curl's zone
    hold(q, 0)
    zb=q.locator('[data-sszone="1"]').bounding_box()
    check("arrange: every other card offers a superset zone while one is held",
          zb is not None and q.locator(".lift:not(.lifted) .ss-zone:visible").count()==2)
    q.mouse.move(zb["x"]+zb["width"]/2, zb["y"]+zb["height"]/2, steps=8); q.wait_for_timeout(150)
    check("arrange: the zone under the finger lights up",
          q.eval_on_selector('[data-sszone="1"]',"e=>getComputedStyle(e).borderStyle")=="solid")
    drop(q)
    check("arrange: dropped on the zone, the two are a superset",
          q.evaluate(ORD)==["Dumbbell Curl*","Barbell Curl*","Lat Pulldown"], str(q.evaluate(ORD)))
    check("arrange: drawn as one bracket", q.locator(".ss-group").count()==1
          and q.locator(".ss-group .lift").count()==2)
    check("arrange: and says so",
          "Barbell Curl supersetted with Dumbbell Curl" in q.eval_on_selector("#undobar","e=>e.textContent"))
    check("arrange: the how-to line goes once it has been done", q.locator(".drag-hint").count()==0)
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("arrange: undo takes the superset apart and the order back",
          q.evaluate(ORD)==["Barbell Curl","Dumbbell Curl","Lat Pulldown"], str(q.evaluate(ORD)))
    hold(q, 0)
    zb=q.locator('[data-sszone="1"]').bounding_box()
    q.mouse.move(zb["x"]+zb["width"]/2, zb["y"]+zb["height"]/2, steps=8); q.wait_for_timeout(150); drop(q)

    # dropped between two members, it joins them; dropped outside, it leaves
    hold(q, 2)
    over(q, '.lift[data-li="1"]', dy=6)
    drop(q)
    check("arrange: dropped between two members, it joins the superset",
          q.evaluate(ORD)==["Dumbbell Curl*","Lat Pulldown*","Barbell Curl*"], str(q.evaluate(ORD)))
    # Order inside a superset is the point of it — which one came first — so
    # a member dropped next to another member of its own superset stays in it.
    # That is what lets the order inside a two-movement superset be swapped.
    hold(q, 2)
    over(q, '.lift[data-li="0"]', dy=6)
    drop(q)
    check("arrange: the order inside a superset can be changed without breaking it",
          q.evaluate(ORD)==["Barbell Curl*","Dumbbell Curl*","Lat Pulldown*"], str(q.evaluate(ORD)))
    # ...and one dropped away from its superset leaves it
    add(q, "Hammer Curl")
    hold(q, 0)
    last=q.locator('.lift[data-li="3"]').bounding_box()
    q.mouse.move(last["x"]+60, last["y"]+last["height"]-4, steps=8); q.wait_for_timeout(150); drop(q)
    check("arrange: dropped away from its superset, a member leaves it",
          q.evaluate(ORD)==["Dumbbell Curl*","Lat Pulldown*","Hammer Curl","Barbell Curl"], str(q.evaluate(ORD)))
    c.close()

    # ---------- A SUPERSET IS FINISHED, AND TIMED, AS ONE ----------
    c, q = lap_page()
    q.click("#startWorkout"); q.wait_for_timeout(300)
    add(q, "Dumbbell Curl"); add(q, "Barbell Curl")
    hold(q, 1)
    zb=q.locator('[data-sszone="0"]').bounding_box()
    q.mouse.move(zb["x"]+zb["width"]/2, zb["y"]+zb["height"]/2, steps=8); q.wait_for_timeout(150); drop(q)
    check("superset: no Done on its members", q.locator(".ss-group [data-done]").count()==0)
    check("superset: and nothing to finish until there is a set", q.locator("[data-ssdone]").count()==0)
    for _ in range(3):
        sets(q, 0, 1, 90000); sets(q, 1, 1, 90000)
    db=q.locator("[data-ssdone]").bounding_box()
    check("superset: one Done for the whole superset", db is not None and db["height"]>=MIN_TAP,
          db and "%dx%d"%(db["width"],db["height"]))
    q.click("[data-ssdone]"); q.wait_for_timeout(350)
    r=q.evaluate(LAPS)
    check("superset: both close together", all(x["closed"] for x in r[:2]))
    check("superset: timed as one — six alternating sets, one time",
          near(r[0]["lap"], 9) and r[1]["lap"] is None, str([x["lap"] for x in r]))
    check("superset: the time sits on the bracket, not on a member",
          q.eval_on_selector(".ss-group .ss-head .lap","e=>e.textContent").startswith("9:0")
          and q.locator(".ss-group .lift .lap").count()==0,
          q.eval_on_selector(".ss-group .ss-head .lap","e=>e.textContent"))
    kept=[x["lap"] for x in r]
    q.click("[data-ssreopen]"); q.wait_for_timeout(300)
    check("superset: reopened for a fix, the time is kept",
          [x["lap"] for x in q.evaluate(LAPS)]==kept and q.locator("[data-ssdone]").count()==1)
    q.click("[data-sssplit]"); q.wait_for_timeout(300)
    check("superset: Split takes the bracket away", q.locator(".ss-group").count()==0)
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("superset: and undo puts it back", q.locator(".ss-group").count()==1)
    q.click('[data-rmlift="1"]'); q.wait_for_timeout(300)
    check("superset: removing a member leaves no superset of one", q.locator(".ss-group").count()==0)
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("superset: undo brings the member back into the superset", q.locator(".ss-group").count()==1)
    # nobody taps Done before locking in — a superset still open is one unit
    add(q, "Lat Pulldown")
    q.click('[data-ssdone]'); q.wait_for_timeout(300)
    sets(q, 2, 2, 2*MIN)
    q.click("#lockDay"); q.wait_for_timeout(700)
    r=q.evaluate(LAPS)
    check("superset: Lock in the day still times the one you were on", r[2]["closed"] and r[2]["lap"] not in (None,"unset"),
          str(r[2]))
    c.close()

    c, q = lap_page()
    q.click("#startWorkout"); q.wait_for_timeout(300)
    add(q, "Dumbbell Curl"); add(q, "Barbell Curl")
    hold(q, 1)
    zb=q.locator('[data-sszone="0"]').bounding_box()
    q.mouse.move(zb["x"]+zb["width"]/2, zb["y"]+zb["height"]/2, steps=8); q.wait_for_timeout(150); drop(q)
    for _ in range(2):
        sets(q, 0, 1, MIN); sets(q, 1, 1, MIN)
    q.click("#lockDay"); q.wait_for_timeout(700)
    r=q.evaluate(LAPS)
    check("superset: locking with only a superset open times it as the one unit",
          all(x["closed"] for x in r) and near(r[0]["lap"], 4) and r[1]["lap"] is None,
          str([x["lap"] for x in r]))
    check("superset: a locked day offers no grip, no Split, no Reopen",
          q.locator("[data-grip], [data-sssplit], [data-ssreopen]").count()==0)
    c.close()

    # ---------- REST BETWEEN SETS ----------
    # Start, stop, nothing kept. On a clock the test moves by hand.
    c, q = lap_page()
    RB = "()=>!document.getElementById('restbar').hidden"
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(250)
    check("rest: not on the other tabs", not q.evaluate(RB))
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(250)
    check("rest: on the gym tab", q.evaluate(RB))
    bb=q.locator("#restBtn").bounding_box(); tb=q.locator(".tabs").bounding_box()
    check("rest: a proper target", bb["height"]>=MIN_TAP and bb["width"]>=MIN_TAP, "%dx%d"%(bb["width"],bb["height"]))
    check("rest: docked above the tab bar, under the thumb", bb["y"]+bb["height"] <= tb["y"]+1)
    logged=q.evaluate("()=>localStorage.getItem('iron-ledger-v1')")
    q.click("#restBtn"); q.wait_for_timeout(200)
    q.evaluate("ms=>window.__advance(ms)", 95000); q.wait_for_timeout(1300)
    clk=q.eval_on_selector("#restClock","e=>e.textContent")
    check("rest: counts from the tap", clk in ("1:35","1:36","1:37"), clk)
    check("rest: and offers the way out", q.eval_on_selector("#restBtn","e=>e.textContent")=="Stop")
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(200)
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(1200)
    check("rest: a look at another tab does not lose it",
          q.eval_on_selector("#restClock","e=>e.textContent") not in ("0:00",""))
    q.click("#restBtn"); q.wait_for_timeout(250)
    check("rest: Stop resets it", q.eval_on_selector("#restClock","e=>e.textContent")=="0:00"
          and q.eval_on_selector("#restBtn","e=>e.textContent")=="Start")
    check("rest: and nothing about it is kept",
          q.evaluate("()=>localStorage.getItem('iron-ledger-v1')")==logged)

    # ---------- TAKE A MOVEMENT OFF THE LIST ----------
    OPTS="()=>[...document.querySelectorAll('#mSel option')].map(o=>o.value)"
    q.select_option("#mSel","Hammer Curl")
    mb=q.locator("#mDrop").bounding_box()
    check("list: the minus is a proper target", mb["height"]>=MIN_TAP and mb["width"]>=MIN_TAP, "%dx%d"%(mb["width"],mb["height"]))
    q.click("#mDrop"); q.wait_for_timeout(300)
    check("list: it takes the chosen movement off", "Hammer Curl" not in q.evaluate(OPTS))
    check("list: and says so", "Took Hammer Curl off" in q.eval_on_selector("#undobar","e=>e.textContent"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("list: undo puts it back", "Hammer Curl" in q.evaluate(OPTS))
    q.select_option("#mSel","__new"); q.wait_for_timeout(150)
    check("list: with New movement chosen there is nothing to take off",
          q.eval_on_selector("#mDrop","e=>e.disabled"))
    c.close()

    # ---------- A MEAL EATEN OFTEN, SAVED ----------
    c, q = lap_page()
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    if not q.locator("#estText").count(): q.click("#estSwap"); q.wait_for_timeout(200)
    q.fill("#estText","chicken breast and white rice"); q.click("#runEst"); q.wait_for_timeout(1200)
    sb=q.locator("#estSave").bounding_box()
    check("meal: the estimate offers to save it", sb is not None and sb["height"]>=MIN_TAP,
          sb and "%dx%d"%(sb["width"],sb["height"]))
    q.click("#estSave"); q.wait_for_timeout(300)
    nb=q.locator("#estSaveName").bounding_box()
    check("meal: its name field is a proper target", nb and nb["height"]>=MIN_TAP)
    check("meal: and will not zoom the page",
          q.eval_on_selector("#estSaveName","e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    q.fill("#estSaveName","Usual lunch"); q.click("#estSaveGo"); q.wait_for_timeout(400)
    pan=q.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry")
    saved=[x for x in pan if x["name"]=="Usual lunch"]
    check("meal: it goes in the pantry as a meal, parts and all",
          len(saved)==1 and saved[0]["serveUnit"]=="meal" and len(saved[0]["items"])==2
          and saved[0]["sCal"]==sum(x["cal"] for x in saved[0]["items"]),
          str(saved[0] if saved else pan))
    check("meal: it says so", "Saved “Usual lunch” in your pantry" in q.eval_on_selector("#undobar","e=>e.textContent"))
    check("meal: and the estimate is still open to log today", q.locator(".review").count()==1)
    q.click("#estSave"); q.wait_for_timeout(250)
    q.fill("#estSaveName","usual LUNCH"); q.click("#estSaveGo"); q.wait_for_timeout(400)
    pan=q.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry")
    check("meal: saving the same name again updates it rather than doubling it",
          len([x for x in pan if x["name"].lower()=="usual lunch"])==1
          and "Updated" in q.eval_on_selector("#undobar","e=>e.textContent"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    pan=q.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry")
    check("meal: undoing the update puts the first one back",
          [x["name"] for x in pan]==["Usual lunch"], str([x["name"] for x in pan]))
    q.click("#discardEst"); q.wait_for_timeout(300)

    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(400)
    check("meal: the pantry says what it is",
          q.eval_on_selector(".pan-item .sub","e=>e.textContent").startswith("Meal of 2"),
          q.eval_on_selector(".pan-item .sub","e=>e.textContent"))
    q.click("[data-addpan]"); q.wait_for_timeout(300)
    q.click("#panQtyUp"); q.wait_for_timeout(200)
    q.click("#panAddBtn"); q.wait_for_timeout(400)
    food=q.evaluate("()=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1'));"
                    "return s.days[Object.keys(s.days).sort().pop()].food;}")
    check("meal: logged twice over, it lands as a meal with every part doubled",
          len(food)==1 and len(food[0].get("items",[]))==2
          and sum(x["cal"] for x in food[0]["items"])==2*saved[0]["sCal"],
          str(food)[:160])
    # a meal already in the day can be saved as well
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    q.locator(".meal-open").first.click(); q.wait_for_timeout(300)
    check("meal: one already in the day offers to be saved",
          q.locator("[data-savemeal]").count()==1)
    c.close()

    # ---------- AGAINST LAST TIME ----------
    T0=datetime.date.today(); PREV=(T0-datetime.timedelta(days=4)).isoformat(); NOW=T0.isoformat()
    GG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    CMP={"days":{
        PREV:{"food":[],"updated":1,"goal":GG,"workoutMs":58*60000,
              "lifts":[{"id":"a","cat":"back","movement":"Barbell Row","lapMs":420000,
                        "sets":[{"w":135,"r":10},{"w":135,"r":10}]},
                       {"id":"b","cat":"back","movement":"Lat Pulldown",
                        "sets":[{"w":140,"r":10},{"w":140,"r":10},{"w":140,"r":10}]}]},
        NOW:{"food":[],"updated":1,"goal":GG,"workoutMs":62*60000,
             "lifts":[{"id":"c","cat":"back","movement":"Barbell Row","lapMs":390000,
                       "sets":[{"w":145,"r":10},{"w":145,"r":10}]},
                      {"id":"d","cat":"back","movement":"Lat Pulldown",
                       "sets":[{"w":130,"r":10},{"w":130,"r":10}]},
                      {"id":"e","cat":"back","movement":"Face Pull","sets":[{"w":40,"r":15}]}]}},
        "moves":None,"goal":GG,"region":"United States","pantry":[],"v":1}
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("compare: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", CMP)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    cb=q.locator("#openCompare").bounding_box()
    check("compare: offered once there are sets", cb is not None and cb["height"]>=MIN_TAP)
    q.click("#openCompare"); q.wait_for_timeout(400)
    body=q.eval_on_selector("#cmpBody","e=>e.innerText")
    rows=q.evaluate("""()=>[...document.querySelectorAll('#cmpBody .cmp-card')].map(c=>({
        h:(c.querySelector('h3')||{}).textContent||'session',
        r:[...c.querySelectorAll('.cmp-row')].map(x=>[x.querySelector('.cmp-l').textContent,
            x.querySelector('.cmp-d').className.replace('cmp-d ','')])}))""")
    sess=dict(rows[0]["r"]); row=dict(rows[1]["r"]); pull=dict(rows[2]["r"])
    check("compare: against the last session of the same split", "against" in body and "Back" in body, body[:90])
    check("compare: more movements reads as up", sess.get("Movements")=="up", str(sess))
    check("compare: a longer session is green, as asked", sess.get("Time")=="up", str(sess))
    check("compare: a heavier top set is green", row.get("Top weight · lb")=="up", str(row))
    check("compare: the same number of sets is neither", row.get("Sets")=="same", str(row))
    check("compare: a lighter one is red", pull.get("Top weight · lb")=="down", str(pull))
    check("compare: a time missing on either side is not compared",
          pull.get("Time")=="same" and "not compared" in body)
    check("compare: a first time says so", "First time" in body)
    check("compare: up and down read in the macro colours",
          q.evaluate("""()=>{const t=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
            const rgb=h=>{h=h.replace('#','');return 'rgb('+[0,2,4].map(i=>parseInt(h.substr(i,2),16)).join(', ')+')';};
            const up=document.querySelector('.cmp-d.up'), dn=document.querySelector('.cmp-d.down');
            return getComputedStyle(up).color===rgb(t('--hit')) && getComputedStyle(dn).color===rgb(t('--miss'));}"""))
    q.click("#cmpDone"); q.wait_for_timeout(250)
    check("compare: Done closes it", q.evaluate("()=>document.getElementById('cmpSheet').hidden"))
    c.close()

    # ---------- THE SET TO BEAT ----------
    # Asked for from the gym: starting a movement, what was the best last time,
    # so there is a number to pass. Last time's top set — the heaviest, the
    # most reps at that weight breaking a tie, never a warm-up.
    BEAT={"days":{PREV:{"food":[],"updated":1,"goal":GG,"workoutMs":50*60000,
              "lifts":[{"id":"a","cat":"back","movement":"Barbell Row","sets":[
                          {"w":185,"r":5,"tech":"warmup"},{"w":135,"r":10},{"w":145,"r":6},{"w":145,"r":8}]},
                       {"id":"b","cat":"back","movement":"Lat Pulldown","sets":[
                          {"w":120,"r":12,"tech":"restpause"}]}]}},
          "moves":None,"goal":GG,"region":"United States","pantry":[],"v":1}
    BL="()=>[...document.querySelectorAll('.lift')].map(x=>{const b=x.querySelector('.beat');return b?b.textContent:'';})"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("beat: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", BEAT)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    def lift_set(i, w, r):
        q.fill('[data-w="%d"]'%i, w); q.fill('[data-r="%d"]'%i, r)
        q.click('[data-addset="%d"]'%i); q.wait_for_timeout(250)
    q.select_option("#mSel","Barbell Row"); q.click("#addLift"); q.wait_for_timeout(300)
    check("beat: a movement opens on last time's top set",
          q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    check("beat: the heaviest set, and never the warm-up", "185" not in q.evaluate(BL)[0])
    lift_set(0, "145", "8")
    check("beat: matching it is not beating it", q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    lift_set(0, "150", "7")
    check("beat: more weight for fewer reps is a trade, not a win",
          q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    lift_set(0, "145", "9")
    check("beat: one more rep at the same weight beats it",
          q.evaluate(BL)[0]=="↑ Beaten · 145×9 over 145×8", q.evaluate(BL)[0])
    check("beat: and it reads in the macro green",
          q.evaluate("""()=>{const h=getComputedStyle(document.documentElement).getPropertyValue('--hit').trim().replace('#','');
            const rgb='rgb('+[0,2,4].map(i=>parseInt(h.substr(i,2),16)).join(', ')+')';
            return getComputedStyle(document.querySelector('.beat.is-beaten b')).color===rgb;}"""))
    q.click('[data-done="0"]'); q.wait_for_timeout(350)
    check("beat: the folded card keeps it", "Beaten" in q.evaluate(BL)[0], q.evaluate(BL)[0])
    q.select_option("#mSel","Lat Pulldown"); q.click("#addLift"); q.wait_for_timeout(300)
    check("beat: a tag rides along with the number",
          q.evaluate(BL)[1]=="To beat · 120×12 rest-pause", q.evaluate(BL)[1])
    q.select_option("#mSel","Barbell Curl"); q.click("#addLift"); q.wait_for_timeout(300)
    check("beat: a first time has nothing to pass", q.evaluate(BL)[2]=="", q.evaluate(BL)[2])
    lift_set(1, "100", "10"); lift_set(2, "60", "10")
    q.eval_on_selector("#lockDay","e=>e.scrollIntoView({block:'center'})")
    q.click("#lockDay"); q.wait_for_timeout(700)
    check("beat: a finished day does not nag about one it did not beat",
          "To beat" not in "".join(q.evaluate(BL)) and "Beaten" in q.evaluate(BL)[0], str(q.evaluate(BL)))
    c.close()

    print("%-6s %-42s %s" % ("","FEATURE","DETAIL"))
    for st,name,detail in results:
        print("%-6s %-42s %s" % (st,name,detail))
    fails=[r for r in results if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(results)-len(fails), len(fails)))
    print("pageerrors:", errs if errs else "none")
    b.close()

    # A suite that prints FAIL and exits 0 cannot gate anything — verify.sh
    # says ALL SUITES PASSED and CI deploys anyway. Page errors count too: a
    # thrown exception is what leaves the buttons after it dead and silent.
    _bad = sum(1 for r in results if r[0] == "FAIL")
    raise SystemExit(1 if (_bad or errs) else 0)
