from playwright.sync_api import sync_playwright
import io, os, json, datetime
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
    # the estimate sits folded behind "Don't know the numbers" until asked for
    if p.locator('[data-logway="estimate"][aria-expanded="false"]').count():
        p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
    if not p.locator("#estText").count():
        p.click("#estSwap"); p.wait_for_timeout(250)
def way(p, w):
    """Open one of the ways in under the checklist; they start folded."""
    if p.locator('[data-logway="%s"][aria-expanded="false"]' % w).count():
        p.click('[data-logway="%s"]' % w); p.wait_for_timeout(250)

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
# A set is logged in the set sheet: every part of a card's entry row — lb,
# reps, the technique box and Set — opens it, and typing happens there.
def log_set(pg, i, w, r, tech=None, wait=300):
    pg.click('[data-addset="%d"]' % i); pg.wait_for_timeout(150)
    pg.fill("#seW", str(w)); pg.fill("#seR", str(r))
    if tech is not None: pg.select_option("#seT", tech)
    pg.click("#seSave"); pg.wait_for_timeout(wait)

# Movements are the owner's own names now: a split's list starts empty and
# holds what he has named. Pick one if the list has it, otherwise name it.
def add_movement(pg, name, wait=300):
    have = pg.eval_on_selector_all("#mSel option", "e=>e.map(o=>o.value)")
    if name in have:
        pg.select_option("#mSel", name)
    else:
        pg.select_option("#mSel", "__new"); pg.fill("#mNew", name)
    pg.click("#addLift"); pg.wait_for_timeout(wait)

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
    way(p, "numbers")
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
    way(p, "estimate")
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
    way(p, "estimate")
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
    way(p, "estimate")
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
    way(p, "estimate")
    p.fill("#regionIn","Canada"); p.eval_on_selector("#regionIn","e=>e.blur()"); p.wait_for_timeout(300)
    check("macros: region persists", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).region")=="Canada")

    # ---------- GYM ----------
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
    p.eval_on_selector_all(".cat","e=>e[1].click()"); p.wait_for_timeout(350)
    check("gym: category switch", p.evaluate("()=>document.querySelectorAll('.cat')[1].getAttribute('aria-pressed')")=="true")
    p.eval_on_selector_all(".cat","e=>e[0].click()"); p.wait_for_timeout(350)
    add_movement(p, "Barbell Row", wait=400)
    check("gym: add movement", p.eval_on_selector_all(".lift","e=>e.length")==1)
    last=p.eval_on_selector(".lift .last","e=>e.textContent")
    check("gym: last-session lookup", "135" in last, last.strip())
    log_set(p, 0, 185, 6, wait=400)
    check("gym: add set", p.eval_on_selector_all(".set","e=>e.length")==1)
    check("gym: Start forgotten, the first set starts the clock",
          p.evaluate("()=>!!document.getElementById('workoutClock')"))
    check("gym: volume line", "1 set" in p.eval_on_selector(".lift-foot span","e=>e.textContent"))
    p.click('[data-r="0"]'); p.wait_for_timeout(200)
    check("gym: tapping reps opens the set sheet, ready on the reps",
          not p.evaluate("()=>document.getElementById('setEditSheet').hidden")
          and p.evaluate("()=>document.activeElement.id")=="seR"
          and p.eval_on_selector("#seSave","e=>e.textContent")=="Add set")
    check("gym: it opens on the weight of the set before", p.input_value("#seW")=="185")
    p.fill("#seR","5"); p.press("#seR","Enter"); p.wait_for_timeout(400)
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
    # only what is on screen: the Edit row is closed until asked for, and a
    # hidden control measures 0 tall without meaning anything
    shown=p.eval_on_selector_all("#setEditSheet input, #setEditSheet select, #setEditSheet button",
           "e=>e.filter(b=>b.getClientRects().length).map(b=>[b.id,Math.round(b.getBoundingClientRect().height)])")
    small=[x for x in shown if x[1]<44]
    check("gym: every control in it clears 44px", len(shown)>=5 and not small, str(small or shown))
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
    check("checklist: under the target bar and above the ways to add food",
          p.evaluate("()=>{const s=document.querySelector('.supps'),"
                     "g=document.querySelector('.goalbar'),e=document.querySelector('.log-ways');"
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
    way(p, "numbers")
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
    for t in ["macros","pantry","gym","cardio","log"]:
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
          p.eval_on_selector_all("#setSheet [aria-pressed=true]","e=>e.map(x=>x.textContent)")==["Match phone","Teal","In place","Hidden"],
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

    # ---------- THE COACH TAB ----------
    # Put away until it is wanted: it is for writing a routine for someone
    # else, which the owner is not doing yet. Off unless switched on, from
    # Settings, and nothing in it is lost either way.
    TABSHOWN="()=>[...document.querySelectorAll('.tabs button')].filter(b=>b.getClientRects().length).map(b=>b.dataset.tab)"
    ROUTINE="()=>JSON.stringify(JSON.parse(localStorage.getItem('iron-ledger-v1')).routine)"
    check("coach tab: put away on a phone that never chose",
          p.evaluate(TABSHOWN)==["macros","pantry","gym","cardio","log"], str(p.evaluate(TABSHOWN)))
    tw=p.eval_on_selector_all(".tabs button","e=>e.filter(b=>b.getClientRects().length).map(b=>b.getBoundingClientRect().width)")
    bw=p.evaluate("()=>document.querySelector('.tabs').clientWidth")
    check("coach tab: the five left share the whole bar, evenly",
          len(tw)==5 and max(tw)-min(tw)<=1 and abs(sum(tw)-bw)<=2, "%s of %s" % ([round(x) for x in tw], bw))
    p.click("#setBtn"); p.wait_for_timeout(300)
    check("coach tab: Settings has the switch, on Hidden",
          p.eval_on_selector('[data-pick-coach="off"]',"e=>e.getAttribute('aria-pressed')")=="true")
    p.click('[data-pick-coach="on"]'); p.wait_for_timeout(300)
    check("coach tab: Shown puts it back at once, in its place",
          p.evaluate(TABSHOWN)==["macros","pantry","gym","cardio","coach","log"]
          and p.eval_on_selector('[data-pick-coach="on"]',"e=>e.getAttribute('aria-pressed')")=="true",
          str(p.evaluate(TABSHOWN)))
    check("coach tab: and the choice is saved",
          p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).coachOn")==True)
    p.click("#setDone"); p.wait_for_timeout(200)
    rt=p.evaluate(ROUTINE)
    p.click('.tabs button[data-tab="coach"]'); p.wait_for_timeout(400)
    ndays=len(json.loads(rt)["days"]) if rt and rt!="null" else 3
    check("coach tab: it opens on the routine, as it was",
          p.locator(".rt-day").count()==ndays, "%d cards, %d days" % (p.locator(".rt-day").count(), ndays))
    p.click("#setBtn"); p.wait_for_timeout(300)
    p.click('[data-pick-coach="off"]'); p.wait_for_timeout(300)
    check("coach tab: hidden while standing on it lands on Gym, not on nothing",
          p.evaluate("()=>document.querySelector('.tabs [aria-selected=true]').dataset.tab")=="gym"
          and "coach" not in p.evaluate(TABSHOWN) and p.locator("#addLift").count()==1)
    check("coach tab: and the routine is untouched", p.evaluate(ROUTINE)==rt)
    p.click('[data-pick-coach="on"]'); p.wait_for_timeout(300)
    p.click("#setDone"); p.wait_for_timeout(200)
    p.reload(); p.wait_for_timeout(900)
    check("coach tab: the choice survives a reload", "coach" in p.evaluate(TABSHOWN))
    # Left Shown, on dark and blue, on purpose: the restore below wipes the
    # phone and has to bring all of it back along with everything else.

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
    check("restore: and with Coach put away", "coach" not in p.evaluate(TABSHOWN))
    p.click("#backupBtn"); p.wait_for_timeout(300)
    p.evaluate("t=>{document.getElementById('backupText').value=t;}", txt)
    p.click("#restoreBtn"); p.wait_for_timeout(600)
    after=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
    check("restore: the look comes back and is applied",
          [after.get("theme"), after.get("accent")]==["dark","blue"] and p.evaluate(ATTR)==["dark","blue"],
          "stored %s, on screen %s" % ([after.get("theme"), after.get("accent")], p.evaluate(ATTR)))
    check("restore: the Coach tab comes back as it was",
          after.get("coachOn")==True and "coach" in p.evaluate(TABSHOWN), str(p.evaluate(TABSHOWN)))
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
        add_movement(q, mv)
    def sets(q, i, n, gap):
        for _ in range(n):
            log_set(q, i, 95, 10, wait=120)
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
    # a list the way an owner builds one: both curls, named by him
    q.evaluate("""()=>localStorage.setItem('iron-ledger-v1',JSON.stringify({days:{},moves:{back:['Barbell Curl','Dumbbell Curl']},movesOwned:true,
        goal:{cal:{dir:'-',v:2000},pro:{dir:'+',v:150}},region:'United States',pantry:[],v:1}))""")
    q.reload(); q.wait_for_timeout(900)
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    q.select_option("#mSel", "Barbell Curl"); q.click("#addLift"); q.wait_for_timeout(300)
    for _ in range(2):
        log_set(q, 0, 30, 12, wait=150)
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
    tb=q.locator('[data-techopen="0"]').bounding_box()
    check("technique: the box sits beside weight and reps", tb is not None)
    check("technique: it is a proper target", tb and tb["height"]>=MIN_TAP, tb and "%dx%d"%(tb["width"],tb["height"]))
    check("technique: it reads normal", q.eval_on_selector('[data-techopen="0"]',"e=>e.textContent")=="normal")
    q.click('[data-techopen="0"]'); q.wait_for_timeout(250)
    check("technique: tapping it opens the set sheet on its picker",
          q.evaluate("()=>document.activeElement.id")=="seT")
    check("technique: the picker will not zoom the page, and starts on normal",
          q.eval_on_selector("#seT","e=>parseFloat(getComputedStyle(e).fontSize)")>=16 and q.input_value("#seT")=="")
    q.fill("#seW","20"); q.fill("#seR","10"); q.select_option("#seT","drop")
    q.click("#seSave"); q.wait_for_timeout(300)
    check("technique: the set is stored with it",
          q.evaluate(EL)["lifts"][0]["sets"][-1]=="20x10:drop", str(q.evaluate(EL)["lifts"][0]["sets"]))
    check("technique: a normal set carries nothing extra",
          all(":" not in x for x in q.evaluate(EL)["lifts"][0]["sets"][:-1]))
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("technique: the next set starts on normal so a tag cannot ride along", q.input_value("#seT")=="")
    q.click("#seCancel"); q.wait_for_timeout(200)
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
    add_movement(q, "Barbell Curl")
    check("technique: next time, Last says which set was the drop",
          "20×10 drop" in q.eval_on_selector(".lift .last","e=>e.textContent"),
          q.eval_on_selector(".lift .last","e=>e.textContent"))
    # Most sets are just sets. Never touching the box must be the ordinary
    # path, all the way to closing the movement out.
    for _ in range(3):
        log_set(q, 0, 30, 12, wait=150)
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
    add_movement(q, "Hammer Curl")
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
    words(q)
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
          q.locator("[data-savemealsec]").count()==1)
    # a picker, not a button: choosing where it goes is the save
    q.select_option("[data-savemealsec]", "dinner"); q.wait_for_timeout(400)
    pan=q.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry")
    check("meal: saving it from the day files it where it was put",
          any(x.get("secs")==["dinner"] and x.get("items") for x in pan)
          and "under Dinner" in q.eval_on_selector("#undoLabel","e=>e.textContent"),
          q.eval_on_selector("#undoLabel","e=>e.textContent"))
    c.close()

    # ---------- THE PANTRY IN SECTIONS ----------
    # Asked for once the pantry grew: Breakfast, Lunch, Dinner, Snacks and
    # Desserts as tabs. Then, once sorting began: protein coffee is breakfast
    # *and* a snack. So a food is in as many sections as it is eaten at, or
    # none, and All is every food in one list, the way the pantry always was.
    def pitem(i, name, cal, pro, unit="bottle", **kw):
        x={"id":i,"name":name,"serveQty":1,"serveUnit":unit,"serveG":None,"sCal":cal,"sPro":pro,"aliases":[]}
        x.update(kw)
        return x
    SG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    SECS={"days":{},"moves":None,"goal":SG,"region":"United States","v":1,"pantry":[
        pitem("p1","Costco protein coffee",130,30),
        pitem("p2","Eggs",72,6,"egg",sec="breakfast"),                 # how b45 stored its one
        pitem("p3","Bacon",43,3,"slice",secs=["breakfast"]),
        pitem("p4","Protein bar",190,20,"bar",secs=["snacks","brunch"]),   # an id this build does not know
        pitem("p5","Ice cream sandwich",180,3,"piece",secs=["desserts"])]}
    PANS=("()=>Object.fromEntries(JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry"
          ".map(x=>[x.name,(x.secs||(x.sec?[x.sec]:[])).join('+')]))")
    TABS="()=>[...document.querySelectorAll('[data-pantab]')].map(b=>b.textContent+(b.getAttribute('aria-pressed')==='true'?'*':''))"
    SHOWN=("()=>[...document.querySelectorAll('.pan-item .nm')].map(e=>e.childNodes[0].textContent+"
           "(e.querySelector('.tags')?' ['+e.querySelector('.tags').textContent+']':''))")
    CHOSEN=("a=>[...document.querySelectorAll('['+a+'][aria-pressed=true]')].map(b=>b.getAttribute(a))")
    SAYS=("()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent")
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("sections: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", SECS)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(400)
    check("sections: tabs for All and the five, with how many are in each",
          q.evaluate(TABS)==["All 5*","Breakfast 2","Lunch","Dinner","Snacks 1","Desserts 1"],
          str(q.evaluate(TABS)))
    check("sections: All is every food in one list, each naming its meals",
          q.evaluate(SHOWN)==["Bacon [Breakfast]","Costco protein coffee","Eggs [Breakfast]",
                              "Ice cream sandwich [Desserts]","Protein bar [Snacks]"],
          str(q.evaluate(SHOWN)))
    check("sections: a food with none is simply in All, not flagged",
          q.evaluate(PANS)["Costco protein coffee"]=="" and q.locator(".pan-hint").count()==0)
    check("sections: what b45 saved still counts", q.evaluate(PANS)["Eggs"]=="breakfast")

    # a food's meals, changed from its own row
    q.click('[data-panmeals="p1"]'); q.wait_for_timeout(250)
    check("sections: Meals opens the five on the food's own row",
          q.locator("[data-pansecfor]").count()==5 and q.evaluate(CHOSEN, "data-pansecfor")==[])
    q.click('[data-pansecfor="breakfast"]'); q.wait_for_timeout(250)
    q.click('[data-pansecfor="snacks"]'); q.wait_for_timeout(250)
    check("sections: one food can be in more than one", q.evaluate(PANS)["Costco protein coffee"]=="breakfast+snacks"
          and q.evaluate(CHOSEN, "data-pansecfor")==["breakfast","snacks"], q.evaluate(PANS)["Costco protein coffee"])
    check("sections: and each change says so", q.evaluate(SAYS)=="Added Costco protein coffee to Snacks", q.evaluate(SAYS))
    check("sections: counted in each", "Breakfast 3" in q.evaluate(TABS) and "Snacks 2" in q.evaluate(TABS), str(q.evaluate(TABS)))
    small=q.evaluate("""()=>[...document.querySelectorAll('[data-pantab],[data-pansec],[data-pansecfor],[data-panmeals],#panEditDone')]
        .filter(e=>{const r=e.getBoundingClientRect();return r.width&&(r.height<43.5||r.width<43.5);})
        .map(e=>e.textContent.trim()+' '+Math.round(e.getBoundingClientRect().height))""")
    check("sections: every tab, choice, Meals and Done is a proper target", not small, str(small))
    q.click("#panEditDone"); q.wait_for_timeout(250)
    check("sections: Done closes it", q.locator("[data-pansecfor]").count()==0)

    q.click('[data-pantab="snacks"]'); q.wait_for_timeout(300)
    check("sections: a section's tab shows every food eaten then",
          q.evaluate(SHOWN)==["Costco protein coffee [Breakfast and Snacks]","Protein bar [Snacks]"], str(q.evaluate(SHOWN)))
    q.click('[data-panmeals="p4"]'); q.wait_for_timeout(250)
    q.click('[data-pansecfor="snacks"]'); q.wait_for_timeout(250)
    check("sections: taken out of the section on show, it stays in view until Done",
          "Protein bar" in q.evaluate(SHOWN), str(q.evaluate(SHOWN)))
    check("sections: an id this build does not know is kept, not lost", q.evaluate(PANS)["Protein bar"]=="brunch")
    q.click("#panEditDone"); q.wait_for_timeout(250)
    check("sections: and goes once the choosing is done", "Protein bar" not in q.evaluate(SHOWN), str(q.evaluate(SHOWN)))

    q.click('[data-pantab="dinner"]'); q.wait_for_timeout(300)
    check("sections: an empty one says how to fill it",
          "Tap Meals on a food" in q.eval_on_selector_all("section .empty","e=>e.map(x=>x.textContent).join(' ')"))
    check("sections: standing in it, a new food starts out filed there", q.evaluate(CHOSEN, "data-pansec")==["dinner"])
    q.fill("#panName","Turkey chili"); q.fill("#panServe","1"); q.fill("#panCal","380"); q.fill("#panPro","30")
    q.click('[data-pansec="lunch"]'); q.wait_for_timeout(100)
    check("sections: more than one can be chosen when saving, and what was typed stays",
          q.evaluate(CHOSEN, "data-pansec")==["lunch","dinner"] and q.input_value("#panName")=="Turkey chili")
    q.click("#savePan"); q.wait_for_timeout(400)
    check("sections: it is saved in every one chosen", q.evaluate(PANS).get("Turkey chili")=="lunch+dinner")
    check("sections: and says where it went", q.evaluate(SAYS)=="Saved Turkey chili under Lunch and Dinner", q.evaluate(SAYS))
    check("sections: the list keeps showing a section it went into", "Dinner 1*" in q.evaluate(TABS), str(q.evaluate(TABS)))
    q.click('[data-pantab="snacks"]'); q.wait_for_timeout(300)
    q.fill("#panName","Rice cakes"); q.fill("#panServe","1"); q.fill("#panCal","35"); q.fill("#panPro","1")
    q.click('[data-pansec="snacks"]'); q.wait_for_timeout(100)
    check("sections: a press on a chosen one takes it off", q.evaluate(CHOSEN, "data-pansec")==[])
    q.click("#savePan"); q.wait_for_timeout(400)
    check("sections: saved with none, it lives in All and the list goes there",
          q.evaluate(PANS).get("Rice cakes")=="" and q.evaluate(TABS)[0].endswith("*")
          and q.evaluate(SAYS)=="Saved Rice cakes to your pantry", "%s | %s" % (q.evaluate(TABS), q.evaluate(SAYS)))
    q.reload(); q.wait_for_timeout(900)
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(300)
    check("sections: they are kept, not just drawn",
          q.evaluate(PANS)["Costco protein coffee"]=="breakfast+snacks" and q.evaluate(TABS)[0]=="All 7*", str(q.evaluate(TABS)))

    # the estimate's save row asks the same question
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    words(q)
    q.fill("#estText","chicken breast and white rice"); q.click("#runEst"); q.wait_for_timeout(1200)
    q.click("#estSave"); q.wait_for_timeout(300)
    q.fill("#estSaveName","Usual lunch")
    q.click('[data-estsec="lunch"]'); q.click('[data-estsec="dinner"]'); q.wait_for_timeout(100)
    small=q.evaluate("""()=>[...document.querySelectorAll('[data-estsec]')]
        .filter(e=>{const r=e.getBoundingClientRect();return r.height<43.5||r.width<43.5;}).map(e=>e.textContent)""")
    check("sections: saving a meal offers them too, as proper targets",
          q.locator("[data-estsec]").count()==5 and not small, str(small))
    check("sections: and choosing does not wipe the name", q.input_value("#estSaveName")=="Usual lunch")
    q.click("#estSaveGo"); q.wait_for_timeout(400)
    check("sections: the meal is filed in each one chosen",
          q.evaluate(PANS).get("Usual lunch")=="lunch+dinner" and "under Lunch and Dinner" in q.evaluate(SAYS), q.evaluate(SAYS))
    q.click("#estSave"); q.wait_for_timeout(300)
    q.fill("#estSaveName","Usual lunch"); q.click("#estSaveGo"); q.wait_for_timeout(400)
    check("sections: saved over with none chosen, it keeps the ones it had",
          q.evaluate(PANS).get("Usual lunch")=="lunch+dinner" and "Updated" in q.evaluate(SAYS), q.evaluate(SAYS))
    c.close()

    # ---------- UNDO, AND UNDO AGAIN ----------
    # Found using b45: sorting several foods, only the last could be taken
    # back, and only for nine seconds. Now each Undo goes one further back,
    # for as long as the changes keep coming one after another, and only a
    # change that cannot be undone ends the run. Looking at another tab hides
    # the bar; coming back brings it back.
    UND={"days":{Ts:{"food":[{"id":"f1","cal":300,"pro":20,"note":"Toast"},
                            {"id":"f2","cal":500,"pro":40,"note":"Steak"},
                            {"id":"f3","cal":200,"pro":5,"note":"Chips"}],"updated":1,"goal":SG}},
         "moves":None,"goal":SG,"region":"United States","v":1,"pantry":[
            pitem("p1","Costco protein coffee",130,30)]}
    NOTES="k=>((JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k]||{}).food||[]).map(f=>f.note)"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("undo: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", UND)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    for _ in range(3):
        q.eval_on_selector_all(".t-del","e=>e[0].click()"); q.wait_for_timeout(250)
    check("undo: three deletes in a row", q.evaluate(NOTES, Ts)==[] and q.evaluate(SAYS)=="Removed Chips",
          "%s | %s" % (q.evaluate(NOTES, Ts), q.evaluate(SAYS)))
    q.click("#undoBtn"); q.wait_for_timeout(250)
    check("undo: the first press takes back the last", q.evaluate(NOTES, Ts)==["Chips"], str(q.evaluate(NOTES, Ts)))
    check("undo: and the bar moves on to the one before", q.evaluate(SAYS)=="Removed Steak", q.evaluate(SAYS))
    q.click("#undoBtn"); q.wait_for_timeout(250)
    check("undo: a second press goes one further back", q.evaluate(NOTES, Ts)==["Steak","Chips"], str(q.evaluate(NOTES, Ts)))
    q.wait_for_timeout(9600)
    check("undo: what is left to undo does not time out", q.evaluate(SAYS)=="Removed Toast", q.evaluate(SAYS))
    q.click("#undoBtn"); q.wait_for_timeout(250)
    check("undo: all the way back, and the bar goes with the last of it",
          q.evaluate(NOTES, Ts)==["Toast","Steak","Chips"] and q.evaluate(SAYS)=="", str(q.evaluate(NOTES, Ts)))
    q.eval_on_selector_all(".t-del","e=>e[0].click()"); q.wait_for_timeout(250)
    way(q, "numbers")
    q.fill("#fCal","100"); q.fill("#fPro","10"); q.fill("#fNote","Apple"); q.click("#addFood"); q.wait_for_timeout(400)
    check("undo: a change that cannot be undone ends the run", q.evaluate(SAYS)=="", q.evaluate(SAYS))
    q.eval_on_selector_all(".t-del","e=>e[0].click()"); q.wait_for_timeout(250)
    gone=q.evaluate(SAYS)
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(300)
    check("undo: another screen does not show it", q.evaluate(SAYS)=="", q.evaluate(SAYS))
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    check("undo: back where it was made, it can still be taken back",
          gone.startswith("Removed") and q.evaluate(SAYS)==gone, "%s -> %s" % (gone, q.evaluate(SAYS)))
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(300)
    q.fill("#suppNameIn","Zinc"); q.click("#addSupp"); q.wait_for_timeout(300)
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    check("undo: a change that cannot be undone ends it, wherever it was made", q.evaluate(SAYS)=="", q.evaluate(SAYS))
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
    # so there is a number to pass. Judged by the owner's own exchange rate:
    # five pounds is worth one rep, so 150x7 and 145x8 are the same set, and
    # 145x10 beats 150x7. Never a warm-up.
    BEAT={"days":{PREV:{"food":[],"updated":1,"goal":GG,"workoutMs":50*60000,
              "lifts":[{"id":"a","cat":"back","movement":"Barbell Row","sets":[
                          {"w":185,"r":5,"tech":"warmup"},{"w":135,"r":10},{"w":145,"r":6},{"w":145,"r":8}]},
                       {"id":"b","cat":"back","movement":"Lat Pulldown","sets":[
                          {"w":120,"r":12,"tech":"restpause"}]},
                       {"id":"c","cat":"back","movement":"Dumbbell Curl","sets":[
                          {"w":30,"r":12},{"w":35,"r":6}]},
                       {"id":"e","cat":"back","movement":"T-Bar Row","sets":[{"w":150,"r":7}]},
                       {"id":"f","cat":"back","movement":"Seated Cable Row","sets":[{"w":100,"r":10},{"w":100,"r":10}]}]}},
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
        log_set(q, i, w, r, wait=250)
    def add_move(mv):
        add_movement(q, mv)
    add_move("Barbell Row")
    # 135x10 and 145x8 are worth the same; the heavier is the one on the bar
    check("beat: a movement opens on last time's best set",
          q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    check("beat: and never the warm-up, however heavy", "185" not in q.evaluate(BL)[0])
    # every way past it, as the owner put it: the next tier of weight, a rep, or
    # a set — 135x10 is worth a 145x8 by the rule, so last time had two
    WAYS="()=>[...document.querySelectorAll('.lift')].map(x=>{const w=x.querySelector('.beat-ways');return w?w.textContent:'';})"
    check("beat: it names every way past it: heavier, a rep, or a set",
          q.evaluate(WAYS)[0]=="+5 lb 150×8 · +1 rep 145×9 · +1 set a 3rd set of 145×8", q.evaluate(WAYS)[0])
    lift_set(0, "145", "8")
    check("beat: matching it is not beating it", q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    lift_set(0, "150", "7")
    check("beat: five pounds is worth a rep, so 150×7 only matches 145×8",
          q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    lift_set(0, "145", "9")
    check("beat: one more rep at the same weight beats it",
          q.evaluate(BL)[0]=="↑ Beaten · 145×9 over 145×8", q.evaluate(BL)[0])
    check("beat: and the ways go once it is beaten", q.evaluate(WAYS)[0]=="", q.evaluate(WAYS)[0])
    check("beat: and it reads in the macro green",
          q.evaluate("""()=>{const h=getComputedStyle(document.documentElement).getPropertyValue('--hit').trim().replace('#','');
            const rgb='rgb('+[0,2,4].map(i=>parseInt(h.substr(i,2),16)).join(', ')+')';
            return getComputedStyle(document.querySelector('.beat.is-beaten b')).color===rgb;}"""))
    q.click('[data-done="0"]'); q.wait_for_timeout(350)
    check("beat: the folded card keeps it", "Beaten" in q.evaluate(BL)[0], q.evaluate(BL)[0])
    add_move("Lat Pulldown")
    check("beat: a tag rides along with the number",
          q.evaluate(BL)[1]=="To beat · 120×12 rest-pause", q.evaluate(BL)[1])
    add_move("Barbell Curl")
    check("beat: a first time has nothing to pass", q.evaluate(BL)[2]=="", q.evaluate(BL)[2])
    add_move("Dumbbell Curl")
    check("beat: reps count too, so 30×12 is last time's best, not the heavier 35×6",
          q.evaluate(BL)[3]=="To beat · 30×12", q.evaluate(BL)[3])
    add_move("T-Bar Row")
    lift_set(4, "145", "8")
    check("beat: 145×8 against 150×7 is the same set", q.evaluate(BL)[4]=="To beat · 150×7", q.evaluate(BL)[4])
    lift_set(4, "145", "10")
    check("beat: and 145×10 beats 150×7, the owner's own example",
          q.evaluate(BL)[4]=="↑ Beaten · 145×10 over 150×7", q.evaluate(BL)[4])
    add_move("Seated Cable Row")
    check("beat: an extra set is offered at last time's level",
          q.evaluate(WAYS)[5].endswith("+1 set a 3rd set of 100×10"), q.evaluate(WAYS)[5])
    lift_set(5, "100", "10"); lift_set(5, "100", "10")
    check("beat: matching last time's two sets is still to beat", q.evaluate(BL)[5]=="To beat · 100×10", q.evaluate(BL)[5])
    lift_set(5, "95", "11")       # worth the same as 100x10 by the rule, so a set at that level
    check("beat: a third set at that level beats it",
          q.evaluate(BL)[5]=="↑ Beaten · a 3rd set of 100×10", q.evaluate(BL)[5])
    lift_set(1, "100", "10"); lift_set(2, "60", "10"); lift_set(3, "25", "10")
    q.eval_on_selector("#lockDay","e=>e.scrollIntoView({block:'center'})")
    q.click("#lockDay"); q.wait_for_timeout(700)
    check("beat: a finished day does not nag about one it did not beat",
          "To beat" not in "".join(q.evaluate(BL)) and "Beaten" in q.evaluate(BL)[0]
          and "Beaten" in q.evaluate(BL)[4], str(q.evaluate(BL)))
    c.close()

    # ---------- NOTES ----------
    # Asked for from the gym: a note for the day — at home, a hotel gym — and
    # one on a movement — the last set was really hard. Both come back next
    # time on that movement's Last line, where the number is read again.
    NT=datetime.date.today(); NP=(NT-datetime.timedelta(days=3)).isoformat()
    NG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    NOTESTORE={"days":{NP:{"food":[],"updated":1,"goal":NG,"gymNote":"Hotel gym, dumbbells only","workoutMs":40*60000,
                           "lifts":[{"id":"a","cat":"back","movement":"Barbell Curl","note":"Last set was really hard",
                                     "sets":[{"w":60,"r":10},{"w":60,"r":8}]}]}},
               "moves":None,"goal":NG,"region":"United States","pantry":[],"v":1}
    NDAY="k=>(JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k]||{})"
    NSAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("notes: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", NOTESTORE)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    nb=q.locator("#dayNoteAdd").bounding_box()
    check("notes: a note for the day is offered, as a proper target",
          nb is not None and nb["height"]>=MIN_TAP, nb and "%dx%d"%(nb["width"],nb["height"]))
    check("notes: it sits under the clock, above the split",
          q.evaluate("""()=>{const n=document.getElementById('dayNoteAdd'), h=document.querySelector('.split-head');
            return n.getBoundingClientRect().top < h.getBoundingClientRect().top;}"""))
    q.click("#dayNoteAdd"); q.wait_for_timeout(250)
    check("notes: its field is ready to type in, and will not zoom the page",
          q.evaluate("()=>document.activeElement&&document.activeElement.id")=="dayNoteIn"
          and q.eval_on_selector("#dayNoteIn","e=>parseFloat(getComputedStyle(e).fontSize)")>=16
          and q.locator("#dayNoteIn").bounding_box()["height"]>=MIN_TAP)
    q.fill("#dayNoteIn","Training at home"); q.press("#dayNoteIn","Enter"); q.wait_for_timeout(300)
    check("notes: the day's note is kept on the day", q.evaluate(NDAY, Ts).get("gymNote")=="Training at home")
    check("notes: and shown, and said", "Training at home" in q.eval_on_selector(".day-note","e=>e.textContent")
          and q.evaluate(NSAYS)=="Added a note for the day", q.evaluate(NSAYS))

    add_movement(q, "Barbell Curl")
    last=q.eval_on_selector(".lift .last","e=>e.textContent")
    check("notes: last time's day note comes back beside its date", "(Hotel gym, dumbbells only)" in last, last)
    check("notes: and last time's note on the movement beside its sets", "\u201cLast set was really hard\u201d" in last, last)
    lb=q.locator("[data-liftnote]").bounding_box()
    check("notes: a movement offers a note, as a proper target", lb is not None and lb["height"]>=MIN_TAP)
    log_set(q, 0, 60, 11)
    q.click("[data-liftnote]"); q.wait_for_timeout(250)
    check("notes: its field will not zoom the page either",
          q.eval_on_selector("#liftNoteIn","e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    q.fill("#liftNoteIn","Grip gave out on the last set"); q.click("#liftNoteSave"); q.wait_for_timeout(300)
    check("notes: the movement's note is kept on the movement",
          q.evaluate(NDAY, Ts)["lifts"][0].get("note")=="Grip gave out on the last set")
    check("notes: and shown on its card, and said",
          "Grip gave out" in q.eval_on_selector(".lift-note","e=>e.textContent")
          and q.evaluate(NSAYS)=="Added a note on Barbell Curl", q.evaluate(NSAYS))
    q.click('[data-done="0"]'); q.wait_for_timeout(300)
    check("notes: a folded card keeps its note",
          q.eval_on_selector_all(".lift-note-done","e=>e.map(x=>x.textContent)")==["\u201cGrip gave out on the last set\u201d"])

    q.eval_on_selector("#dayNoteEdit","e=>e.scrollIntoView({block:'center'})"); q.click("#dayNoteEdit"); q.wait_for_timeout(250)
    check("notes: editing starts from what is there", q.input_value("#dayNoteIn")=="Training at home")
    q.fill("#dayNoteIn","Home gym"); q.click("#dayNoteSave"); q.wait_for_timeout(300)
    check("notes: a change says so", q.evaluate(NDAY, Ts).get("gymNote")=="Home gym"
          and q.evaluate(NSAYS)=="Changed the note for the day", q.evaluate(NSAYS))
    q.click("#dayNoteEdit"); q.wait_for_timeout(250)
    q.fill("#dayNoteIn",""); q.click("#dayNoteSave"); q.wait_for_timeout(300)
    check("notes: saved empty, the note is taken away, and says so",
          "gymNote" not in q.evaluate(NDAY, Ts) and q.evaluate(NSAYS)=="Removed the note for the day"
          and q.locator("#dayNoteAdd").count()==1, q.evaluate(NSAYS))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("notes: undo brings it back", q.evaluate(NDAY, Ts).get("gymNote")=="Home gym")
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("notes: and once more takes back the change before", q.evaluate(NDAY, Ts).get("gymNote")=="Training at home")

    q.click("#dayNoteEdit"); q.wait_for_timeout(250)
    q.fill("#dayNoteIn","Nothing to keep"); q.click("#dayNoteCancel"); q.wait_for_timeout(250)
    check("notes: Cancel keeps what was there", q.evaluate(NDAY, Ts).get("gymNote")=="Training at home")

    q.eval_on_selector("#lockDay","e=>e.scrollIntoView({block:'center'})"); q.click("#lockDay"); q.wait_for_timeout(700)
    check("notes: a finished day's note can still be written", q.locator("#dayNoteEdit").count()==1)
    check("notes: its movements' notes are read, not edited",
          q.locator("[data-liftnote]").count()==0 and "Grip gave out" in q.eval_on_selector(".lift","e=>e.textContent"))
    q.click("#openCompare") if q.locator("#openCompare").count() else None
    q.wait_for_timeout(300)
    check("notes: the comparison names what the other day was",
          "\u201cHotel gym, dumbbells only\u201d" in q.eval_on_selector(".cmp-sub","e=>e.textContent"),
          q.eval_on_selector(".cmp-sub","e=>e.textContent"))
    q.click("#cmpDone"); q.wait_for_timeout(200)
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    check("notes: and so does the calendar",
          q.evaluate("()=>[...document.querySelectorAll('.cal-cell')].some(x=>(x.title||'').includes('\u201cHotel gym, dumbbells only\u201d'))"))
    q.reload(); q.wait_for_timeout(900)
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    check("notes: they are kept, not just drawn",
          "Training at home" in q.eval_on_selector(".day-note","e=>e.textContent")
          and "Grip gave out" in q.eval_on_selector(".lift","e=>e.textContent"))
    c.close()

    # ---------- A SPECIAL DAY ----------
    # Asked for from home: two pairs of dumbbells, no machines, so no Back /
    # Bi / Tri day — biceps and shoulders instead. A day outside the routine,
    # whose lifts still count: 25 lb hammer curls at home are the hammer curls
    # to beat at the gym next time. Yoga, or a friend's workout, the same.
    SPT=datetime.date.today(); SGYM=(SPT-datetime.timedelta(days=5)).isoformat(); SHOME=(SPT-datetime.timedelta(days=2)).isoformat()
    SPG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    SPBASE={"days":{SGYM:{"food":[],"updated":1,"goal":SPG,"workoutMs":60*60000,
               "lifts":[{"id":"g1","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]},
                        {"id":"g2","cat":"back","movement":"Hammer Curl","sets":[{"w":35,"r":10},{"w":35,"r":9}]}]}},
            "moves":{"back":["Barbell Row","Hammer Curl","Barbell Curl"],"push":["Lateral Raise","Bench Press"],"legs":["Back Squat"]},"movesOwned":True,"coachOn":True,"goal":SPG,"region":"United States","pantry":[],"v":1}
    SPDAY="k=>(JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k]||{})"
    SPMOVES="()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).moves"
    def sp_page(store):
        c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
        c.add_init_script("delete window.claude;")
        q = c.new_page(); q.on("pageerror", lambda e: errs.append("special: "+str(e)))
        q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
        q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
        q.reload(); q.wait_for_timeout(900)
        try: q.click("text=Got it", timeout=1500)
        except Exception: pass
        q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
        return c, q
    c, q = sp_page(SPBASE)
    sb=q.locator('[data-cat="special"]').bounding_box()
    check("special: a Special day sits after the splits, a proper target",
          sb is not None and sb["height"]>=MIN_TAP
          and q.eval_on_selector_all(".cats .cat","e=>e.map(x=>x.dataset.cat||x.id)")[-2:]==["special","addSplitChip"])
    q.click('[data-cat="special"]'); q.wait_for_timeout(300)
    groups=q.eval_on_selector_all("#mSel optgroup","e=>e.map(g=>g.label)")
    check("special: it offers every split's movements, grouped by split",
          groups==["Back / Bi / Rear Delt","Chest / Shoulder / Tri","Legs"], str(groups))
    q.select_option("#mSel","Hammer Curl")
    check("special: a split's movement cannot be taken off from here", q.eval_on_selector("#mDrop","e=>e.disabled"))
    q.click("#addLift"); q.wait_for_timeout(300)
    last=q.eval_on_selector(".lift .last","e=>e.textContent")
    # The date as the app writes it ("Oct 1"), worked out rather than assumed:
    # this said "Sep" when it was written, and failed the day five days back
    # crossed into October.
    gd=datetime.date.fromisoformat(SGYM); gday="%s %d" % (gd.strftime("%b"), gd.day)
    check("special: the movement's last time is found wherever it was", ("Last · "+gday) in last and "35×10" in last, last)
    log_set(q, 0, 25, 20)
    check("special: and home dumbbells can beat it, by the same rule",
          q.eval_on_selector(".lift .beat","e=>e.textContent")=="↑ Beaten · 25×20 over 35×10",
          q.eval_on_selector(".lift .beat","e=>e.textContent"))
    q.select_option("#mSel","Lateral Raise"); q.click("#addLift"); q.wait_for_timeout(300)
    lifts=q.evaluate(SPDAY, Ts)["lifts"]
    check("special: movements from two splits on one day, logged as a special day",
          [(x["movement"],x["cat"]) for x in lifts]==[("Hammer Curl","special"),("Lateral Raise","special")], str(lifts))
    mv=q.evaluate(SPMOVES)
    check("special: borrowing them leaves the splits' lists as they were",
          not mv.get("special") and "Hammer Curl" in mv["back"])
    q.select_option("#mSel","__new"); q.fill("#mNew","Band pull-apart"); q.click("#addLift"); q.wait_for_timeout(300)
    check("special: a new one is kept as the special day's own", q.evaluate(SPMOVES).get("special")==["Band pull-apart"])
    q.select_option("#mSel","Band pull-apart")
    check("special: and only its own can be taken off here", not q.eval_on_selector("#mDrop","e=>e.disabled"))
    q.click('[data-editlift="0"]'); q.wait_for_timeout(250)
    check("special: changing a movement on it offers every movement",
          q.eval_on_selector_all("#liftMove option","e=>e.map(o=>o.value)").count("Bench Press")==1
          and "Hammer Curl" in q.eval_on_selector_all("#liftMove option","e=>e.map(o=>o.value)"))
    q.click("#liftMoveCancel"); q.wait_for_timeout(200)
    q.click("#openCompare"); q.wait_for_timeout(300)
    body=q.eval_on_selector("#cmpBody","e=>e.innerText")
    check("special: it is compared movement by movement, not as a split's session",
          "movement by movement" in body and "This session against" not in body and "Hammer Curl" in body, body[:120])
    q.click("#cmpDone"); q.wait_for_timeout(200)
    q.click("#editSplits"); q.wait_for_timeout(250)
    check("special: it is not one of the splits to rename or remove",
          q.eval_on_selector_all(".split-name","e=>e.map(x=>x.value)")==["Back / Bi / Rear Delt","Chest / Shoulder / Tri","Legs"])
    q.click("#editSplits"); q.wait_for_timeout(200)
    q.click('.tabs button[data-tab="coach"]'); q.wait_for_timeout(300)
    check("special: nor one of the routine's days", "Special" not in q.eval_on_selector("#view","e=>e.textContent"))
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    check("special: the calendar says what the day was",
          "Special · 1 sets" in q.eval_on_selector(".cal-cell.is-today","e=>e.title"), q.eval_on_selector(".cal-cell.is-today","e=>e.title"))
    c.close()

    # two days later, back at the gym: the home session is the one to beat
    later=json.loads(json.dumps(SPBASE))
    later["days"][SHOME]={"food":[],"updated":1,"goal":SPG,"gymNote":"At home, dumbbells only",
        "lifts":[{"id":"h1","cat":"special","movement":"Hammer Curl","sets":[{"w":25,"r":20}]}]}
    c, q = sp_page(later)
    q.click('[data-cat="back"]'); q.wait_for_timeout(300)
    q.select_option("#mSel","Hammer Curl"); q.click("#addLift"); q.wait_for_timeout(300)
    last=q.eval_on_selector(".lift .last","e=>e.textContent")
    check("special: back at the gym, the home session is last time", "(At home, dumbbells only)" in last and "25×20" in last, last)
    check("special: and the number to beat", q.eval_on_selector(".lift .beat","e=>e.textContent")=="To beat · 25×20")
    check("special: with a way past it that does not need the heavier dumbbells",
          "+1 rep 25×21" in q.eval_on_selector(".lift .beat-ways","e=>e.textContent")
          and "a 2nd set of 25×20" in q.eval_on_selector(".lift .beat-ways","e=>e.textContent"),
          q.eval_on_selector(".lift .beat-ways","e=>e.textContent"))
    log_set(q, 0, 35, 11)
    q.click("#openCompare"); q.wait_for_timeout(300)
    body=q.eval_on_selector("#cmpBody","e=>e.innerText")
    gymdate=q.evaluate("k=>new Date(k+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})", SGYM)
    homedate=q.evaluate("k=>new Date(k+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})", SHOME)
    check("special: the session is set against the last real back day, not the home one",
          ("This session against " + gymdate) in body, body[:120])
    check("special: while the movement is set against the home one", ("against " + homedate) in body, body[-160:])
    c.close()

    # yoga: nothing lifted, only a clock — still a session to lock in
    c, q = sp_page(SPBASE)
    q.click('[data-cat="special"]'); q.wait_for_timeout(200)
    q.click("#startWorkout"); q.wait_for_timeout(1300)
    check("special: a clock alone is enough to lock the day in", q.locator("#lockDay").count()==1)
    q.click("#lockDay"); q.wait_for_timeout(500)
    check("special: and it banks the time", (q.evaluate(SPDAY, Ts).get("workoutMs") or 0) > 0)
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    check("special: the calendar calls it a session, not no gym",
          "session ·" in q.eval_on_selector(".cal-cell.is-today","e=>e.title"), q.eval_on_selector(".cal-cell.is-today","e=>e.title"))
    c.close()

    # ---------- THE SECTIONS ARE YOURS ----------
    # Asked for next: someone who never eats breakfast should be able to take
    # it away, and anyone should be able to rename one or add their own.
    YG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    def yitem(i, name, cal, pro, unit="bottle", **kw):
        x={"id":i,"name":name,"serveQty":1,"serveUnit":unit,"serveG":None,"sCal":cal,"sPro":pro,"aliases":[]}
        x.update(kw)
        return x
    YOURS={"days":{Ts:{"food":[{"id":"m1","note":"Chicken and rice","items":[
                {"id":"i1","cal":284,"pro":53,"note":"Chicken breast"},{"id":"i2","cal":205,"pro":4,"note":"White rice"}]}],
             "updated":1,"goal":YG}},
           "moves":None,"goal":YG,"region":"United States","v":1,"pantry":[
             yitem("p1","Eggs",72,6,"egg",secs=["breakfast"]),
             yitem("p2","Ice cream sandwich",180,3,"piece",secs=["desserts"])]}
    YTABS="()=>[...document.querySelectorAll('[data-pantab]')].map(b=>b.textContent)"
    YST="()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    YSAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("yours: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", YOURS)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(400)
    eb=q.locator("#editPanSecs").bounding_box()
    check("yours: Edit sections is offered, a proper target", eb is not None and eb["height"]>=MIN_TAP)
    check("yours: nothing is written until something changes", q.evaluate(YST).get("panSecs") is None)
    q.click("#editPanSecs"); q.wait_for_timeout(250)
    check("yours: each section is a name to change",
          q.eval_on_selector_all("[data-secname]","e=>e.map(x=>x.value)")==["Breakfast","Lunch","Dinner","Snacks","Desserts"])
    small=q.evaluate("""()=>[...document.querySelectorAll('[data-secname],[data-rmsec],#newSecName,#addSec')]
        .filter(e=>{const r=e.getBoundingClientRect();return r.height<43.5||r.width<43.5;}).map(e=>e.id||e.textContent)""")
    zoomy=q.evaluate("()=>[...document.querySelectorAll('[data-secname],#newSecName')].filter(e=>parseFloat(getComputedStyle(e).fontSize)<16).length")
    check("yours: every field and button is a proper target, and none zooms the page", not small and not zoomy, str(small))
    q.fill('[data-secname="breakfast"]',"Brunch"); q.press('[data-secname="breakfast"]',"Tab"); q.wait_for_timeout(250)
    check("yours: renaming keeps the section, so its foods follow",
          q.evaluate(YST)["panSecs"][0]=={"id":"breakfast","name":"Brunch"}
          and q.evaluate(YST)["pantry"][0].get("secs")==["breakfast"])
    q.fill('[data-secname="lunch"]',"   "); q.press('[data-secname="lunch"]',"Tab"); q.wait_for_timeout(250)
    check("yours: an empty name is not a name", q.evaluate(YST)["panSecs"][1]["name"]=="Lunch")
    q.click('[data-rmsec="desserts"]'); q.wait_for_timeout(250)
    check("yours: taking one away says its foods stay",
          q.evaluate(YSAYS)=="Took away Desserts \u2014 its foods are still in All", q.evaluate(YSAYS))
    q.fill("#newSecName","Pre-workout"); q.press("#newSecName","Enter"); q.wait_for_timeout(250)
    check("yours: a new one is added, and says so",
          q.evaluate(YST)["panSecs"][-1]["name"]=="Pre-workout" and q.evaluate(YSAYS)=="Added Pre-workout")
    check("yours: ready for the next", q.evaluate("()=>document.activeElement&&document.activeElement.id")=="newSecName")
    q.click("#editPanSecs"); q.wait_for_timeout(250)
    check("yours: the tabs are the sections as they now stand",
          q.evaluate(YTABS)==["All 2","Brunch 1","Lunch","Dinner","Snacks","Pre-workout"], str(q.evaluate(YTABS)))
    check("yours: the food from a section taken away is still in All",
          "Ice cream sandwich" in q.eval_on_selector_all(".pan-item .nm","e=>e.map(x=>x.childNodes[0].textContent)"))
    check("yours: and the form offers the new one",
          q.eval_on_selector_all("[data-pansec]","e=>e.map(x=>x.textContent)")==["Brunch","Lunch","Dinner","Snacks","Pre-workout"])
    q.click("#undoBtn"); q.wait_for_timeout(250); q.click("#undoBtn"); q.wait_for_timeout(250)
    check("yours: undo takes the new one back, then brings the old one back with its food",
          q.evaluate(YTABS)==["All 2","Brunch 1","Lunch","Dinner","Snacks","Desserts 1"], str(q.evaluate(YTABS)))
    q.click("#editPanSecs"); q.wait_for_timeout(250)
    while q.locator("[data-rmsec]").count():
        q.locator("[data-rmsec]").first.click(); q.wait_for_timeout(200)
    q.click("#editPanSecs"); q.wait_for_timeout(250)
    check("yours: with none at all there are no tabs, no choices and no Meals",
          q.evaluate(YTABS)==[] and q.locator("[data-pansec]").count()==0 and q.locator("[data-panmeals]").count()==0)
    check("yours: and every food is kept", len(q.evaluate(YST)["pantry"])==2)
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    q.locator(".meal-open").first.click(); q.wait_for_timeout(300)
    q.click("[data-savemealnow]"); q.wait_for_timeout(300)
    check("yours: a meal in the day can still be saved, with nothing to choose",
          any(x["name"]=="Chicken and rice" for x in q.evaluate(YST)["pantry"]) and "in your pantry" in q.evaluate(YSAYS))
    q.reload(); q.wait_for_timeout(900)
    check("yours: they are kept, not just drawn", q.evaluate(YST)["panSecs"]==[])
    c.close()

    # ---------- THE SET SHEET ----------
    # Asked for from real use: the sheet that changes a set lets you focus on
    # the one thing you are doing, so logging a set happens there too, and the
    # movement can be changed from it with Edit.
    SSG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    SSP=(datetime.date.today()-datetime.timedelta(days=8)).isoformat()
    SHEETSTORE={"days":{SSP:{"food":[],"updated":1,"goal":SSG,"lifts":[{"id":"a","cat":"back","movement":"Barbell Curl",
                 "sets":[{"w":45,"r":15},{"w":45,"r":15},{"w":45,"r":15}]}]}},
                "moves":{"back":["Barbell Curl","Dumbbell Curl"]},"movesOwned":True,"goal":SSG,"region":"United States","pantry":[],"v":1}
    SSDAY="k=>(JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k]||{})"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("sheet: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", SHEETSTORE)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    add_movement(q, "Barbell Curl")
    small=q.evaluate("""()=>[...document.querySelectorAll('.setadd > *')]
        .filter(e=>{const r=e.getBoundingClientRect();return r.height<43.5||r.width<43.5;}).map(e=>e.textContent)""")
    check("sheet: the entry row keeps its four parts, each a proper target",
          q.eval_on_selector_all(".setadd > *","e=>e.map(x=>x.textContent)")==["lb","reps","normal","Set"] and not small, str(small))
    q.click('[data-w="0"]'); q.wait_for_timeout(250)
    check("sheet: tapping lb opens it, ready on the weight",
          q.evaluate("()=>document.activeElement.id")=="seW"
          and q.eval_on_selector("#seTitle","e=>e.textContent")=="Barbell Curl · set 1")
    check("sheet: with the number to beat, since the card is behind it",
          q.eval_on_selector("#seGoal","e=>e.textContent")=="To beat · 45×15"
          and "+1 rep 45×16" in q.eval_on_selector("#seWays","e=>e.textContent"))
    check("sheet: nothing to remove on a set not yet logged", q.locator("#seRemove").is_hidden())
    q.fill("#seW","35"); q.click("#seSave"); q.wait_for_timeout(250)
    check("sheet: reps are asked for, and nothing is logged without them",
          "reps" in q.eval_on_selector("#seWarn","e=>e.textContent") and not q.evaluate(SSDAY, Ts)["lifts"][0]["sets"])
    q.fill("#seR","20"); q.press("#seR","Enter"); q.wait_for_timeout(350)
    check("sheet: Add set logs it and the sheet goes",
          [(x["w"],x["r"]) for x in q.evaluate(SSDAY, Ts)["lifts"][0]["sets"]]==[(35,20)]
          and q.evaluate("()=>document.getElementById('setEditSheet').hidden"))
    check("sheet: the card says what it did", q.eval_on_selector(".lift .beat","e=>e.textContent")=="↑ Beaten · 35×20 over 45×15")
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("sheet: the next set opens on the weight just used, and says it is set 2",
          q.input_value("#seW")=="35" and q.eval_on_selector("#seTitle","e=>e.textContent")=="Barbell Curl · set 2")
    eb=q.locator("#seMoveBtn").bounding_box()
    check("sheet: Edit sits beside the title, a proper target", eb is not None and eb["height"]>=MIN_TAP)
    q.click("#seMoveBtn"); q.wait_for_timeout(200)
    check("sheet: Edit offers the split's movements, and a new one",
          "Dumbbell Curl" in q.eval_on_selector_all("#seMove option","e=>e.map(o=>o.value)")
          and q.eval_on_selector_all("#seMove option","e=>e.map(o=>o.value)")[-1]=="__new"
          and q.eval_on_selector("#seMove","e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    erow=q.eval_on_selector_all("#seMoveRow select, #seMoveRow button",
         "e=>e.filter(b=>b.getClientRects().length).map(b=>[b.id,Math.round(b.getBoundingClientRect().height)])")
    check("sheet: and the open Edit row clears 44px everywhere",
          len(erow)==3 and all(h>=MIN_TAP for _,h in erow), str(erow))
    q.select_option("#seMove","Dumbbell Curl"); q.click("#seMoveSave"); q.wait_for_timeout(300)
    check("sheet: changing it keeps the sets and stays in the sheet",
          q.evaluate(SSDAY, Ts)["lifts"][0]["movement"]=="Dumbbell Curl"
          and len(q.evaluate(SSDAY, Ts)["lifts"][0]["sets"])==1
          and not q.evaluate("()=>document.getElementById('setEditSheet').hidden")
          and q.eval_on_selector("#seTitle","e=>e.textContent")=="Dumbbell Curl · set 2")
    q.click("#seMoveBtn"); q.wait_for_timeout(200)
    q.select_option("#seMove","__new"); q.wait_for_timeout(100)
    q.fill("#seMoveNew","Spider Curl"); q.click("#seMoveSave"); q.wait_for_timeout(300)
    check("sheet: a new name can be typed there too",
          q.evaluate(SSDAY, Ts)["lifts"][0]["movement"]=="Spider Curl"
          and "Spider Curl" in q.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).moves.back"))
    q.click("#seCancel"); q.wait_for_timeout(200)
    q.click("#undoBtn"); q.wait_for_timeout(250)
    check("sheet: undo takes the name back, and the typed one off the list",
          q.evaluate(SSDAY, Ts)["lifts"][0]["movement"]=="Dumbbell Curl"
          and "Spider Curl" not in q.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).moves.back"))
    log_set(q, 0, 35, 12)
    check("sheet: the next set goes on the movement as it is now named",
          len(q.evaluate(SSDAY, Ts)["lifts"][0]["sets"])==2 and q.evaluate(SSDAY, Ts)["lifts"][0]["movement"]=="Dumbbell Curl")
    q.eval_on_selector_all(".lift .set","e=>e[0].click()"); q.wait_for_timeout(250)
    check("sheet: a logged set still opens to change, with Edit and Remove",
          q.eval_on_selector("#seSave","e=>e.textContent")=="Save" and q.locator("#seRemove").is_visible()
          and q.locator("#seMoveBtn").is_visible()
          and q.eval_on_selector("#seTitle","e=>e.textContent")=="Dumbbell Curl · set 1 of 2")
    q.click("#seCancel"); q.wait_for_timeout(200)
    c.close()

    # ---------- YOUR OWN NAMES ----------
    # Asked for from real use: scrolling past a dozen built-in names to find
    # one's own. A new phone starts with empty lists; an existing one loses
    # only the starting names never logged, and says so once.
    OG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    OP=(datetime.date.today()-datetime.timedelta(days=6)).isoformat()
    OLDLISTS={"back":["Barbell Row","Lat Pulldown","Seated Cable Row","Pull-Up","T-Bar Row","Straight-Arm Pulldown",
                      "Face Pull","Rear Delt Fly","Shrug","Barbell Curl","Dumbbell Curl","Hammer Curl","Preacher Curl",
                      "Meadows Row"],
              "push":["Bench Press","Incline DB Press","Cable Fly","Dip","Overhead Press","DB Shoulder Press",
                      "Lateral Raise","Cable Lateral Raise","Triceps Pushdown","Skullcrusher","Overhead Triceps Ext",
                      "Close-Grip Bench"],
              "legs":["Back Squat","Front Squat","Hack Squat","Leg Press","Romanian Deadlift","Leg Curl","Leg Extension",
                      "Walking Lunge","Bulgarian Split Squat","Hip Thrust","Standing Calf Raise"]}
    OWNSTORE={"days":{OP:{"food":[],"updated":1,"goal":OG,"lifts":[
                {"id":"a","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]},
                {"id":"b","cat":"special","movement":"Lateral Raise","sets":[{"w":20,"r":15}]}]}},
              "moves":OLDLISTS,"goal":OG,"region":"United States","pantry":[],"v":1}
    OWNMOVES="()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).moves"
    OSAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("own: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(500)
    check("own: a new phone starts with nothing on any list",
          all(not v for v in q.evaluate(OWNMOVES).values()) if q.evaluate("()=>!!localStorage.getItem('iron-ledger-v1')") else True)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    check("own: with nothing named yet, the field to name one is simply there",
          q.locator("#mNew").is_visible() and q.eval_on_selector_all("#mSel option","e=>e.map(o=>o.value)")==["__new"])
    check("own: and it will not zoom the page",
          q.eval_on_selector("#mNew","e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    q.fill("#mNew","Cable Curl (rope)"); q.press("#mNew","Enter"); q.wait_for_timeout(350)
    check("own: Enter adds it, named exactly as typed",
          q.eval_on_selector(".lift h3","e=>e.textContent").startswith("Cable Curl (rope)"))
    check("own: and it is on the list from then on",
          q.eval_on_selector_all("#mSel option","e=>e.map(o=>o.value)")==["Cable Curl (rope)","__new"])

    # a phone that had the old lists
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", OWNSTORE)
    q.reload(); q.wait_for_timeout(900)
    mv=q.evaluate(OWNMOVES)
    check("own: the starting names never logged are taken off",
          mv["back"]==["Barbell Row","Meadows Row"] and mv["push"]==["Lateral Raise"] and mv["legs"]==[], str(mv))
    check("own: a name the owner typed stays, and so does any he trained, on any split",
          "Meadows Row" in mv["back"] and "Lateral Raise" in mv["push"])
    check("own: it says how many, once",
          q.evaluate(OSAYS)=="Took off 34 starting movements you never used", q.evaluate(OSAYS))
    check("own: the history is untouched",
          [l["movement"] for l in q.evaluate("k=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days[k].lifts", OP)]==["Barbell Row","Lateral Raise"])
    q.reload(); q.wait_for_timeout(900)
    check("own: and it is done once, not every time", q.evaluate(OSAYS)=="" and q.evaluate(OWNMOVES)==mv)
    c.close()

    # ---------- WHERE YOU TRAIN ----------
    # Asked for from real use: the fly at the apartment gym goes 150 for
    # reps, the one at 24 Hour Fitness 110. One target for both is wrong at
    # both. A day carries its gym, a movement's target is the last time *at
    # that gym*, and a dumbbell movement can take its numbers from every gym.
    GG2={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    GA=(datetime.date.today()-datetime.timedelta(days=10)).isoformat()
    GB=(datetime.date.today()-datetime.timedelta(days=5)).isoformat()
    GYMSTORE={"days":{
        GA:{"food":[],"updated":1,"goal":GG2,"lifts":[
            {"id":"a1","cat":"back","movement":"Pec Fly","sets":[{"w":150,"r":10},{"w":150,"r":9}]},
            {"id":"a2","cat":"back","movement":"Dumbbell Curl","sets":[{"w":30,"r":12}]}]},
        GB:{"food":[],"updated":1,"goal":GG2,"lifts":[
            {"id":"b1","cat":"back","movement":"Pec Fly","sets":[{"w":110,"r":10}]}]}},
        "moves":{"back":["Pec Fly","Dumbbell Curl"]},"movesOwned":True,"goal":GG2,"region":"United States","pantry":[],"v":1}
    GST="()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    GSAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("gyms: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", GYMSTORE)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    ab=q.locator("#addGymFirst").bounding_box()
    check("gyms: with none yet, one quiet button near the top to add where you train",
          ab is not None and ab["height"]>=MIN_TAP and q.locator(".gymtag").count()==0)
    q.click("#addGymFirst"); q.wait_for_timeout(300)
    check("gyms: it opens on the name, ready to type",
          q.evaluate("()=>document.activeElement.id")=="newGymName")
    q.fill("#newGymName","Apartment gym"); q.fill("#newGymTag","APT"); q.click("#saveGym"); q.wait_for_timeout(300)
    st=q.evaluate(GST)
    APT=st["gyms"][0]["id"] if st.get("gyms") else None
    check("gyms: Add keeps the name and the tag you chose",
          [(g["name"],g["tag"]) for g in st.get("gyms",[])]==[("Apartment gym","APT")])
    check("gyms: the first one is where today is, and it says so",
          st.get("gymLast")==APT and q.evaluate(GSAYS)=="Added Apartment gym \u2014 training there today", q.evaluate(GSAYS))
    q.fill("#newGymName","24 Hour Fitness"); q.fill("#newGymTag","24"); q.press("#newGymTag","Enter"); q.wait_for_timeout(300)
    st=q.evaluate(GST)
    G24=st["gyms"][1]["id"] if len(st.get("gyms",[]))>1 else None
    check("gyms: Enter adds the next, and today stays where it was",
          len(st["gyms"])==2 and st["gyms"][1]["tag"]=="24" and st["gymLast"]==APT)
    rows=q.eval_on_selector_all(".gym-row input, .gym-row button, .gym-new input, .gym-new button",
         "e=>e.filter(x=>x.getClientRects().length).map(x=>[x.tagName,Math.round(x.getBoundingClientRect().height),parseFloat(getComputedStyle(x).fontSize)])")
    check("gyms: every control in the editor clears 44px and no field zooms the page",
          len(rows)==9 and all(h>=MIN_TAP for _,h,_ in rows) and all(f>=16 for n,_,f in rows if n=="INPUT"), str(rows))
    q.set_viewport_size({"width":320,"height":700}); q.wait_for_timeout(200)
    check("gyms: the editor fits a 320px phone",
          q.evaluate("()=>document.documentElement.scrollWidth")<=320, str(q.evaluate("()=>document.documentElement.scrollWidth")))
    q.set_viewport_size({"width":402,"height":874}); q.wait_for_timeout(200)
    q.click("#editGyms"); q.wait_for_timeout(300)
    check("gyms: Done shows them as choices, today's chosen",
          q.eval_on_selector_all("[data-gym]","e=>e.map(x=>[x.textContent,x.getAttribute('aria-pressed')])")
          ==[["APTApartment gym","true"],["2424 Hour Fitness","false"]],
          str(q.eval_on_selector_all("[data-gym]","e=>e.map(x=>[x.textContent,x.getAttribute('aria-pressed')])")))
    check("gyms: and asks once where the earlier workouts were",
          q.eval_on_selector_all("[data-gymask]","e=>e.map(x=>x.textContent)")==["At Apartment gym","At 24 Hour Fitness","Leave them unmarked"])
    q.click('[data-gymask="%s"]' % APT); q.wait_for_timeout(300)
    st=q.evaluate(GST)
    check("gyms: answering marks every earlier workout, and says how many",
          st["days"][GA].get("gym")==APT and st["days"][GB].get("gym")==APT and st.get("gymAsked")
          and q.evaluate(GSAYS)=="Marked 2 earlier workouts as Apartment gym", q.evaluate(GSAYS))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    st=q.evaluate(GST)
    check("gyms: undo takes the marks off and asks again",
          not st["days"][GA].get("gym") and not st["days"][GB].get("gym") and q.locator("[data-gymask]").count()==3)
    q.click('[data-gymask="%s"]' % APT); q.wait_for_timeout(300)
    check("gyms: and it is not asked a second time", q.locator("[data-gymask]").count()==0)

    # the 24 Hour Fitness day was marked wrong: put it right from that day
    for _ in range(5): q.click("#prevDay"); q.wait_for_timeout(150)
    check("gyms: a past day shows where it was", q.eval_on_selector('[data-gym="%s"]' % APT, "e=>e.getAttribute('aria-pressed')")=="true")
    q.click('[data-gym="%s"]' % G24); q.wait_for_timeout(300)
    st=q.evaluate(GST)
    check("gyms: a past day is put right on its own, without moving today",
          st["days"][GB]["gym"]==G24 and st["gymLast"]==APT and "was at 24 Hour Fitness" in q.evaluate(GSAYS), q.evaluate(GSAYS))
    for _ in range(5): q.click("#nextDay"); q.wait_for_timeout(150)

    add_movement(q, "Pec Fly")
    check("gyms: logging today writes down where", q.evaluate(GST)["days"][Ts].get("gym")==APT)
    check("gyms: the movement wears the gym's tag beside its name",
          q.eval_on_selector(".lift h3 .gymtag","e=>e.textContent")=="APT")
    check("gyms: and its target is the last time at this gym, not the last time anywhere",
          q.eval_on_selector(".lift .beat","e=>e.textContent")=="To beat · 150×10"
          and q.eval_on_selector(".lift .last","e=>e.textContent").startswith("Last at APT · "),
          q.eval_on_selector(".lift .beat","e=>e.textContent"))
    q.click('[data-gym="%s"]' % G24); q.wait_for_timeout(300)
    check("gyms: training somewhere else changes the target to that gym's",
          q.eval_on_selector(".lift .beat","e=>e.textContent")=="To beat · 110×10"
          and q.eval_on_selector(".lift h3 .gymtag","e=>e.textContent")=="24")
    check("gyms: says so, and tomorrow starts there",
          q.evaluate(GSAYS)=="Training at 24 Hour Fitness \u2014 targets from there" and q.evaluate(GST)["gymLast"]==G24,
          q.evaluate(GSAYS))
    add_movement(q, "Dumbbell Curl")
    last1=q.eval_on_selector_all(".lift .last","e=>e.map(x=>x.textContent)")[1]
    check("gyms: never done here: the other gym's numbers, as a reference and not a target",
          last1.startswith("First time at 24. At APT, ") and last1.endswith("30×12 · not a target here")
          and q.eval_on_selector_all(".lift","e=>e[1].querySelectorAll('.beat').length")==0, last1)
    q.click('[data-w="1"]'); q.wait_for_timeout(250)
    check("gyms: the set sheet says which numbers it answers to",
          q.locator("#seGym").is_visible()
          and q.eval_on_selector_all("#seGymSeg button","e=>e.map(x=>[x.textContent,x.getAttribute('aria-pressed')])")
             ==[["24 only","true"],["Every gym","false"]]
          and q.eval_on_selector("#seGoal","e=>e.textContent")=="First time at 24 \u2014 nothing to beat here yet")
    sb=q.eval_on_selector_all("#seGymSeg button","e=>e.map(x=>x.getBoundingClientRect().height)")
    check("gyms: both choices are proper targets", all(h>=MIN_TAP for h in sb), str(sb))
    q.click('[data-seshare="on"]'); q.wait_for_timeout(300)
    check("gyms: a dumbbell is the same everywhere: Every gym brings the target in",
          q.eval_on_selector("#seGoal","e=>e.textContent")=="To beat · 30×12"
          and q.evaluate(GST).get("gymShared",{}).get("Dumbbell Curl")==True)
    check("gyms: and the card behind says so too",
          q.eval_on_selector_all(".lift h3 .gymtag","e=>e.map(x=>x.textContent)")==["24","every gym"])
    q.click("#seCancel"); q.wait_for_timeout(200)
    log_set(q, 0, 110, 11)
    q.click("#openCompare"); q.wait_for_timeout(300)
    body=q.eval_on_selector("#cmpBody","e=>e.innerText")
    check("gyms: compared with the last session at the same gym",
          ("This session against %s at 24" % q.evaluate("k=>new Date(k+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})", GB)) in body, body[:140])
    q.click("#cmpDone"); q.wait_for_timeout(200)

    # changing a gym: the history follows by id
    q.click("#editGyms"); q.wait_for_timeout(250)
    q.fill('[data-gymtag="%s"]' % G24, "24HR")
    q.eval_on_selector('[data-gymtag="%s"]' % G24, "e=>e.dispatchEvent(new Event('change'))")
    q.fill('[data-gymname="%s"]' % APT, "")
    q.eval_on_selector('[data-gymname="%s"]' % APT, "e=>e.dispatchEvent(new Event('change'))")
    check("gyms: an emptied name is not a gym, and it comes back",
          q.input_value('[data-gymname="%s"]' % APT)=="Apartment gym")
    q.fill('[data-gymname="%s"]' % APT, "Apartment")
    q.eval_on_selector('[data-gymname="%s"]' % APT, "e=>e.dispatchEvent(new Event('change'))")
    q.click("#editGyms"); q.wait_for_timeout(250)
    check("gyms: a new tag shows at once on today's movements",
          q.eval_on_selector(".lift h3 .gymtag","e=>e.textContent")=="24HR")
    check("gyms: and a new name on its choice",
          q.eval_on_selector('[data-gym="%s"]' % APT, "e=>e.textContent")=="APTApartment")

    # removing one: undo, and the days trained there still say where
    q.click("#editGyms"); q.wait_for_timeout(250)
    q.click('[data-rmgym="%s"]' % G24); q.wait_for_timeout(300)
    st=q.evaluate(GST)
    check("gyms: Remove offers undo and remembers the name",
          [g["id"] for g in st["gyms"]]==[APT] and st.get("gymsRetired",{}).get(G24,{}).get("name")=="24 Hour Fitness"
          and q.evaluate(GSAYS)=="Removed 24 Hour Fitness" and st["days"][GB]["gym"]==G24)
    q.click("#editGyms"); q.wait_for_timeout(250)
    check("gyms: a day trained there says so, rather than being relabelled",
          "Trained at 24 Hour Fitness \u2014 a gym you no longer train at." in q.eval_on_selector("#view","e=>e.textContent"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("gyms: undo puts it back where it was",
          [g["id"] for g in q.evaluate(GST)["gyms"]]==[APT, G24] and q.locator('[data-gym="%s"][aria-pressed=true]' % G24).count()==1)
    q.click("#editGyms"); q.wait_for_timeout(250)
    q.click('[data-rmgym="%s"]' % G24); q.wait_for_timeout(300)
    q.click("#editGyms"); q.wait_for_timeout(250)
    for _ in range(5): q.click("#prevDay"); q.wait_for_timeout(150)
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(500)
    tt=q.eval_on_selector('[data-go="%s"]' % GB, "e=>e.title")
    check("gyms: and the calendar names it, as a gym no longer trained at",
          "at 24 Hour Fitness \u2014 a gym you no longer train at" in tt, tt)
    tt=q.eval_on_selector('[data-go="%s"]' % GA, "e=>e.title")
    check("gyms: a renamed gym's days follow the new name", "at Apartment" in tt and "Apartment gym" not in tt, tt)

    # it all travels with a backup
    q.click("#backupBtn"); q.wait_for_timeout(300)
    gtxt=q.evaluate("()=>document.getElementById('backupText').value")
    q.click("#closeSheet"); q.wait_for_timeout(200)
    before=q.evaluate(GST)
    q.evaluate("()=>localStorage.removeItem('iron-ledger-v1')")
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click("#backupBtn"); q.wait_for_timeout(300)
    q.evaluate("t=>{document.getElementById('backupText').value=t;}", gtxt)
    q.click("#restoreBtn"); q.wait_for_timeout(600)
    after=q.evaluate(GST)
    check("gyms: a restore brings back the gyms, the removed one's name, and what is shared",
          after.get("gyms")==before.get("gyms") and after.get("gymsRetired")==before.get("gymsRetired")
          and after.get("gymShared")==before.get("gymShared") and after["days"][GB].get("gym")==G24,
          "%s / %s" % (after.get("gyms"), after.get("gymsRetired")))
    c.close()

    # ---------- COMBINE FOODS INTO ONE ----------
    # Asked for from real use: a shake made every night from three foods in
    # the pantry, logged one at a time. Combining saves them as one meal under
    # its own name, and the three stay exactly as they were.
    CG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    CPAN=[{"id":"pw","name":"Protein powder","serveQty":1,"serveUnit":"scoop","serveG":None,"sCal":120,"sPro":24,"aliases":[]},
          {"id":"mk","name":"Whole milk","serveQty":1,"serveUnit":"cup","serveG":None,"sCal":150,"sPro":8,"aliases":[],"secs":["snacks"]},
          {"id":"bn","name":"Banana","serveQty":1,"serveUnit":"piece","serveG":None,"sCal":105,"sPro":1,"aliases":[]}]
    CSTORE={"days":{},"moves":{},"movesOwned":True,"goal":CG,"region":"United States","pantry":CPAN,"v":1}
    CST="()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    CSAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("combine: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", CSTORE)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(400)
    cb=q.locator("#combStart").bounding_box()
    check("combine: the pantry offers it, as a proper target", cb is not None and cb["height"]>=MIN_TAP)
    q.click("#combStart"); q.wait_for_timeout(300)
    check("combine: it opens a draft at the top of the list, with a name field that will not zoom",
          q.locator(".combine").is_visible()
          and q.eval_on_selector("#combName","e=>parseFloat(getComputedStyle(e).fontSize)")>=16)
    q.click("#combSave"); q.wait_for_timeout(250)
    check("combine: Save with nothing in it says why, rather than doing nothing",
          q.eval_on_selector("#combWarn","e=>e.textContent")=="Add at least two foods to combine.")
    q.click('[data-addpan="pw"]'); q.wait_for_timeout(250)
    check("combine: + asks how much, and says where it is going",
          q.eval_on_selector("#panAddBtn","e=>e.textContent")=="Add to the mix"
          and "Going into the combination" in q.eval_on_selector("#panSheetSub","e=>e.textContent"))
    q.click("#panQtyUp"); q.wait_for_timeout(100)
    q.click("#panAddBtn"); q.wait_for_timeout(300)
    check("combine: in it goes, and it says so where the thumb is",
          q.evaluate(CSAYS)=="Added Protein powder · 2 scoops \u2014 1 food in the combination", q.evaluate(CSAYS))
    check("combine: and nothing is logged to the day", not (q.evaluate(CST)["days"].get(Ts) or {}).get("food"))
    for pid in ["mk","bn"]:
        q.click('[data-addpan="%s"]' % pid); q.wait_for_timeout(250)
        q.click("#panAddBtn"); q.wait_for_timeout(300)
    PARTS="()=>[...document.querySelectorAll('.comb-part .nm')].map(e=>e.textContent)"
    check("combine: each food is listed with how much",
          q.evaluate(PARTS)==["Protein powder · 2 scoops","Whole milk · 1 cup","Banana · 1 piece"], str(q.evaluate(PARTS)))
    check("combine: with the total",
          q.eval_on_selector(".comb-total","e=>e.textContent")=="Together · 495 kcal · 57 g protein",
          q.eval_on_selector(".comb-total","e=>e.textContent"))
    tb=q.eval_on_selector_all(".comb-part button","e=>e.map(x=>x.getBoundingClientRect().height)")
    check("combine: Take out is a proper target on every food", len(tb)==3 and all(h>=MIN_TAP for h in tb), str(tb))
    q.click('[data-combout="2"]'); q.wait_for_timeout(250)
    check("combine: Take out takes just that one", q.evaluate(PARTS)==["Protein powder · 2 scoops","Whole milk · 1 cup"])
    q.click('[data-addpan="bn"]'); q.wait_for_timeout(250)
    q.click("#panAddBtn"); q.wait_for_timeout(300)
    q.click("#combSave"); q.wait_for_timeout(250)
    check("combine: no name, no save — and it says so",
          q.eval_on_selector("#combWarn","e=>e.textContent").startswith("Give it a name")
          and q.evaluate("()=>document.activeElement.id")=="combName")
    q.fill("#combName","protein powder"); q.click("#combSave"); q.wait_for_timeout(250)
    check("combine: a food's own name is refused, because saving would replace that food",
          "already have a food called Protein powder" in q.eval_on_selector("#combWarn","e=>e.textContent")
          and len(q.evaluate(CST)["pantry"])==3)
    q.fill("#combName","Night time shake")
    q.set_viewport_size({"width":320,"height":700}); q.wait_for_timeout(200)
    check("combine: the draft fits a 320px phone",
          q.evaluate("()=>document.documentElement.scrollWidth")<=320, str(q.evaluate("()=>document.documentElement.scrollWidth")))
    q.set_viewport_size({"width":402,"height":874}); q.wait_for_timeout(200)
    q.click('[data-combsec="snacks"]'); q.wait_for_timeout(100)
    q.click("#combSave"); q.wait_for_timeout(350)
    pan=q.evaluate(CST)["pantry"]
    shake=[x for x in pan if x["name"]=="Night time shake"]
    check("combine: saved as one meal, under its own name and section",
          len(shake)==1 and shake[0]["serveUnit"]=="meal" and shake[0]["sCal"]==495 and shake[0]["sPro"]==57
          and [i["note"] for i in shake[0]["items"]]==["Protein powder · 2 scoops","Whole milk · 1 cup","Banana · 1 piece"]
          and shake[0].get("secs")==["snacks"], str(shake))
    check("combine: and the three foods are exactly as they were",
          [x for x in pan if x["name"]!="Night time shake"]==CPAN)
    check("combine: it says what it did, with undo",
          q.evaluate(CSAYS)=="Saved \u201cNight time shake\u201d under Snacks" and q.locator("#undoBtn").is_visible(),
          q.evaluate(CSAYS))
    check("combine: and the draft is put away", q.locator(".combine").count()==0 and q.locator("#combStart").count()==1)
    sid=shake[0]["id"] if shake else ""
    q.click('[data-addpan="%s"]' % sid); q.wait_for_timeout(250)
    check("combine: logging it again is the ordinary sheet", q.eval_on_selector("#panAddBtn","e=>e.textContent")=="Add to ledger")
    q.click("#panAddBtn"); q.wait_for_timeout(300)
    food=(q.evaluate(CST)["days"].get(Ts) or {}).get("food") or []
    check("combine: one tap logs the shake as a meal, its parts inside",
          len(food)==1 and food[0].get("note")=="Night time shake" and len(food[0].get("items",[]))==3, str(food))

    # Cancel can be taken back: a draft took taps to build
    q.click("#combStart"); q.wait_for_timeout(250)
    q.click('[data-addpan="pw"]'); q.wait_for_timeout(250)
    q.click("#panAddBtn"); q.wait_for_timeout(300)
    q.click("#combCancel"); q.wait_for_timeout(250)
    check("combine: Cancel puts it away, and offers it back",
          q.locator(".combine").count()==0 and q.evaluate(CSAYS)=="Put the combination away")
    q.click("#undoBtn"); q.wait_for_timeout(250)
    check("combine: undo brings the draft back as it was", q.evaluate(PARTS)==["Protein powder · 1 scoop"])
    c.close()

    # ---------- THE WAYS IN ARE FOLDED ----------
    # Asked for from real use: two whole forms under the checklist made the
    # Macros screen twice the height of a phone. They are buttons now, named
    # for what they are for, and each opens its box right under it.
    FG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    FSTORE={"days":{Ts:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs"},
                                 {"id":"b","cal":0,"pro":0,"note":"chicken breast","pending":True}],
                        "lifts":[],"updated":1,"goal":FG,"supps":{}}},
            "supps":[{"id":"s1","name":"Creatine","dose":"5 g"}],
            "moves":{},"movesOwned":True,"goal":FG,"region":"United States","pantry":[],"v":1,"seen":True}
    WAYS="()=>[...document.querySelectorAll('[data-logway]')].map(b=>[b.dataset.logway,b.getAttribute('aria-expanded')])"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("ways: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", FSTORE)
    q.reload(); q.wait_for_timeout(900)
    check("ways: both start folded, and neither form is on the page",
          q.evaluate(WAYS)==[["numbers","false"],["estimate","false"]]
          and q.locator("#fCal").count()==0 and q.locator("#runEst").count()==0, str(q.evaluate(WAYS)))
    check("ways: each says what it is for",
          q.inner_text('[data-logway="numbers"]').startswith("Log calories / protein")
          and q.inner_text('[data-logway="estimate"]').startswith("Don\u2019t know the numbers"))
    wb=q.eval_on_selector_all("[data-logway]","e=>e.map(x=>x.getBoundingClientRect().height)")
    check("ways: both are proper targets", len(wb)==2 and all(h>=MIN_TAP for h in wb), str(wb))
    # Not "the day fits on the phone": that depends on how much is logged and
    # on the platform's fonts — Linux CI drew this fixture 21px taller than
    # Windows. What folding owns is how little it leaves, and what it saves.
    WAYSPAN="()=>{const b=[...document.querySelectorAll('[data-logway]')].map(x=>x.getBoundingClientRect());return Math.round(b[1].bottom-b[0].top);}"
    check("ways: folded, the forms are down to two buttons",
          q.evaluate(WAYSPAN)<=170, "%spx" % q.evaluate(WAYSPAN))
    folded_h=q.evaluate("()=>document.documentElement.scrollHeight")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    open_h=q.evaluate("()=>document.documentElement.scrollHeight")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: and folding takes most of a screen off the page",
          open_h-folded_h>=400, "%s folded, %s open" % (folded_h, open_h))
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(300)
    check("ways: Log calories / protein opens its box, ready to type",
          q.evaluate(WAYS)[0]==["numbers","true"] and q.evaluate("()=>document.activeElement.id")=="fCal")
    check("ways: and its box sits right under its own button",
          q.evaluate("()=>document.querySelector('[data-logway=numbers]').nextElementSibling.id")=="wayNumbers")
    q.fill("#fCal","300"); q.fill("#fPro","25"); q.fill("#fNote","Yogurt"); q.click("#addFood"); q.wait_for_timeout(400)
    check("ways: adding says so, and the box stays open for the next one",
          "Added Yogurt" in q.inner_text(".added-flash") and q.locator("#fCal").count()==1)
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: one open at a time — the other folds",
          q.evaluate(WAYS)==[["numbers","false"],["estimate","true"]] and q.locator("#fCal").count()==0
          and q.evaluate("()=>document.activeElement.dataset.eq")=="0")
    check("ways: the confirmation still shows with the numbers box folded",
          q.locator(".added-flash").count()==1)
    q.fill('[data-ef="0"]',"toast")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: pressing the open one folds it", q.evaluate(WAYS)==[["numbers","false"],["estimate","false"]])
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: and what was typed is still there when it opens again", q.input_value('[data-ef="0"]')=="toast")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    # a row waiting on numbers: its button must not land in a folded box
    q.click('[data-est="b"]'); q.wait_for_timeout(900)
    check("ways: a waiting row's button opens its answer even with everything folded",
          q.locator("#commitEst").count()==1 and q.evaluate(WAYS)[1]==["estimate","true"], str(q.evaluate(WAYS)))
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: folding puts the review aside", q.locator("#commitEst").count()==0)
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: and opening brings it back, not lost", q.locator("#commitEst").count()==1)
    c.close()

    # ---------- HOW THE WAYS IN OPEN ----------
    # The owner could not choose from pictures between a box opening in place,
    # a pop-up like the set sheet, and a mix of the two, and asked to try
    # each. Settings -> Adding food opens.
    LG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    LSTORE={"days":{Ts:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs"},
                                 {"id":"b","cal":0,"pro":0,"note":"chicken breast","pending":True}],
                        "lifts":[],"updated":1,"goal":LG}},
            "moves":{},"movesOwned":True,"goal":LG,"region":"United States","pantry":[],"v":1,"seen":True}
    LST="()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    SHEETS="()=>[...document.querySelectorAll('[data-waysheet]')].map(x=>x.dataset.waysheet)"
    INLINE="()=>[!!document.querySelector('.log-ways #wayNumbers'),!!document.querySelector('.log-ways #wayEstimate')]"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("opens: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", LSTORE)
    q.reload(); q.wait_for_timeout(900)
    def pick(mode):
        q.click("#setBtn"); q.wait_for_timeout(250)
        q.click('[data-pick-logopen="%s"]' % mode); q.wait_for_timeout(250)
        q.click("#setDone"); q.wait_for_timeout(250)
    q.click("#setBtn"); q.wait_for_timeout(250)
    check("opens: Settings offers in place, pop-up and mix, starting in place",
          q.eval_on_selector_all("[data-pick-logopen]","e=>e.map(x=>[x.textContent,x.getAttribute('aria-pressed')])")
          ==[["In place","true"],["Pop-up","false"],["Mix","false"]])
    check("opens: and says what the choice does",
          q.inner_text("#setLogOpenHint")=="Each box opens right under its button on the Macros screen.")
    q.click('[data-pick-logopen="popup"]'); q.wait_for_timeout(250)
    check("opens: choosing says what it does instead, and is kept",
          q.inner_text("#setLogOpenHint").startswith("Each box slides up")
          and q.evaluate(LST).get("logOpen")=="popup")
    q.click("#setDone"); q.wait_for_timeout(250)

    # pop-up
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(300)
    check("opens: pop-up — Log calories / protein slides up, ready to type",
          q.evaluate(SHEETS)==["numbers"] and q.evaluate(INLINE)==[False,False]
          and q.evaluate("()=>document.activeElement.id")=="fCal")
    sb=q.eval_on_selector_all('[data-waysheet] input, [data-waysheet] button',
        "e=>e.filter(x=>x.getClientRects().length).map(x=>[x.id||x.textContent,Math.round(x.getBoundingClientRect().height),x.tagName=='INPUT'?parseFloat(getComputedStyle(x).fontSize):16])")
    check("opens: everything in it is a proper target and no field zooms",
          len(sb)>=5 and all(h>=MIN_TAP and f>=16 for _,h,f in sb), str(sb))
    q.click('[data-wayclose="numbers"]'); q.wait_for_timeout(250)
    check("opens: Cancel puts it away", q.evaluate(SHEETS)==[] and q.locator("#fCal").count()==0)
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(250)
    q.mouse.click(200, 120); q.wait_for_timeout(250)
    check("opens: so does a tap on the dimmed page", q.evaluate(SHEETS)==[])
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(250)
    q.fill("#fCal","300"); q.fill("#fPro","25"); q.fill("#fNote","Yogurt"); q.click("#addFood"); q.wait_for_timeout(400)
    check("opens: adding goes in, the pop-up goes, and the page says so",
          q.evaluate(SHEETS)==[] and "Added Yogurt" in q.inner_text(".added-flash")
          and any(f.get("note")=="Yogurt" for f in q.evaluate(LST)["days"][Ts]["food"]))
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("opens: pop-up — Don't know the numbers slides up too",
          q.evaluate(SHEETS)==["estimate"] and q.evaluate("()=>document.activeElement.dataset.eq")=="0")
    q.fill('[data-ef="0"]',"white rice"); q.click("#runEst"); q.wait_for_timeout(1000)
    check("opens: its review stays in the pop-up", q.locator('[data-waysheet] #commitEst').count()==1)
    q.click('[data-wayclose="estimate"]'); q.wait_for_timeout(250)
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(250)
    check("opens: Close puts the review aside, not away", q.locator('[data-waysheet] #commitEst').count()==1)
    q.click("#commitEst"); q.wait_for_timeout(400)
    check("opens: adding from the review closes it and says what went in",
          q.evaluate(SHEETS)==[] and q.inner_text(".added-flash").startswith("✓ Added"), q.inner_text(".added-flash"))
    q.click('[data-est="b"]'); q.wait_for_timeout(900)
    check("opens: a waiting row's button pops its answer up", q.locator('[data-waysheet] #commitEst').count()==1)
    q.set_viewport_size({"width":320,"height":640}); q.wait_for_timeout(200)
    check("opens: the pop-up fits a 320px phone",
          q.evaluate("()=>document.documentElement.scrollWidth")<=320)
    q.set_viewport_size({"width":402,"height":874}); q.wait_for_timeout(200)
    q.click('[data-wayclose="estimate"]'); q.wait_for_timeout(250)

    # mix
    pick("mix")
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(250)
    check("opens: mix — the numbers pop up", q.evaluate(SHEETS)==["numbers"])
    q.click('[data-wayclose="numbers"]'); q.wait_for_timeout(250)
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(250)
    check("opens: mix — the estimate opens in place", q.evaluate(SHEETS)==[] and q.evaluate(INLINE)==[False,True])

    # a box already open changes at once
    pick("popup")
    check("opens: changing it with a box open shows the box the new way",
          q.evaluate(SHEETS)==["estimate"] and q.evaluate(INLINE)==[False,False])
    q.click('[data-wayclose="estimate"]'); q.wait_for_timeout(250)
    q.reload(); q.wait_for_timeout(900)
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(250)
    check("opens: the choice survives a reload", q.evaluate(SHEETS)==["numbers"])
    q.click('[data-wayclose="numbers"]'); q.wait_for_timeout(250)
    pick("inplace")
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(250)
    check("opens: and in place is in place again", q.evaluate(SHEETS)==[] and q.evaluate(INLINE)==[True,False])
    c.close()

    # ---------- TEAL MEANS YOU CAN TAP IT ----------
    # Asked for from real use: which small words are buttons? Twenty kinds were
    # the same grey as the labels around them. The rule now runs both ways, and
    # this walks the screens to hold it: a button with no box of its own is
    # teal (or carries a teal marker — a name with its ▾ or "tap to open"), and
    # teal text is never something that cannot be pressed.
    TG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    TSTORE={"days":{Ts:{"updated":1,"goal":TG,"supps":{"s1":True},"gymNote":"Hotel gym",
        "food":[{"id":"m1","note":"","items":[{"id":"i1","cal":330,"pro":52,"note":"Chicken breast"},
                                               {"id":"i2","cal":215,"pro":4,"note":"White rice"}]},
                {"id":"f1","cal":130,"pro":30,"note":"Protein coffee"}],
        "lifts":[{"id":"l1","cat":"back","movement":"Dumbbell Curl","ss":"g1","sets":[{"w":30,"r":12}]},
                 {"id":"l2","cat":"back","movement":"Barbell Curl","ss":"g1","sets":[{"w":60,"r":10}]},
                 {"id":"l3","cat":"back","movement":"Barbell Row","note":"Grip gave out","sets":[{"w":135,"r":10}]},
                 {"id":"l4","cat":"back","movement":"Lat Pulldown","sets":[{"w":120,"r":10}],"doneAt":1,"lapMs":300000,"closed":True}]}},
        "supps":[{"id":"s1","name":"Creatine","dose":"5 g"},{"id":"s2","name":"Zinc","dose":"50 mg"}],
        "pantry":[{"id":"p1","name":"Eggs","serveQty":1,"serveUnit":"egg","serveG":None,"sCal":72,"sPro":6,"aliases":[],"secs":["breakfast","dinner"]},
                  {"id":"p2","name":"Protein coffee","serveQty":1,"serveUnit":"bottle","serveG":None,"sCal":130,"sPro":30,"aliases":[]}],
        "moves":{"back":["Dumbbell Curl","Barbell Curl","Barbell Row","Lat Pulldown"]},"movesOwned":True,
        "coachOn":True,"goal":TG,"region":"United States","v":1,"seen":True}
    TEALJS=r"""()=>{const t=document.createElement('i');t.style.color='var(--accent)';document.body.appendChild(t);
      const acc=getComputedStyle(t).color;t.remove();return acc;}"""
    BARE=r"""(acc)=>{const out=[];
      document.querySelectorAll('main button, main [role=button]').forEach(el=>{
        const r=el.getBoundingClientRect(),s=getComputedStyle(el);
        if(!r.width||!r.height||s.display==='none'||s.visibility==='hidden'||el.classList.contains('cal-cell')) return;
        const filled=s.backgroundColor!=='rgba(0, 0, 0, 0)'&&s.backgroundColor!=='transparent';
        const border=parseFloat(s.borderTopWidth)+parseFloat(s.borderLeftWidth)>0&&s.borderTopColor!=='rgba(0, 0, 0, 0)'&&s.borderStyle!=='none';
        if(filled||border) return;
        const marked=s.color===acc||[...el.querySelectorAll('*')].some(c=>getComputedStyle(c).color===acc&&c.textContent.trim());
        out.push([(el.innerText||el.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim().slice(0,24),marked]);});
      return out;}"""
    STRAY=r"""(acc)=>{const out=[];
      document.querySelectorAll('.topbar *, main *').forEach(el=>{
        if(![...el.childNodes].some(n=>n.nodeType===3&&n.nodeValue.trim())) return;
        const s=getComputedStyle(el),r=el.getBoundingClientRect();
        if(!r.width||s.display==='none'||s.visibility==='hidden'||s.color!==acc) return;
        if(el.closest('button,a,label,select,input,textarea,[role=button],[data-tab]')) return;
        out.push(el.textContent.trim().replace(/\s+/g,' ').slice(0,30));});
      return out;}"""
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("teal: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", TSTORE)
    q.reload(); q.wait_for_timeout(900)
    acc=q.evaluate(TEALJS)
    bare_all, stray_all = [], []
    for t in ["macros","gym","pantry","cardio","coach","log"]:
        q.click('.tabs button[data-tab="%s"]'%t); q.wait_for_timeout(400)
        if t=="macros": q.click(".meal-open"); q.wait_for_timeout(300)
        if t=="coach" and q.locator("[data-openday]").count(): q.locator("[data-openday]").first.click(); q.wait_for_timeout(300)
        bare_all += [(t,)+tuple(x) for x in q.evaluate(BARE, acc)]
        stray_all += [(t,x) for x in q.evaluate(STRAY, acc)]
    check("teal: the walk met the small buttons it is about",
          sum(1 for x in bare_all if x[0] in ("macros","gym","pantry"))>=12, str(len(bare_all)))
    check("teal: every button without a box of its own is teal, or carries a teal marker",
          all(m for _,_,m in bare_all), str([x for x in bare_all if not x[2]][:6]))
    check("teal: and nothing teal is a word that cannot be pressed", not stray_all, str(stray_all[:6]))

    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(400)
    row=q.evaluate("""()=>{const r=document.querySelector('.supp-item'),b=n=>r.querySelector(n).getBoundingClientRect();
      const btns=[...r.querySelectorAll('button')].map(x=>x.getBoundingClientRect());
      return {nmLeft:b('.nm').left, btnLeft:Math.min(...btns.map(x=>x.left)), nmTop:b('.nm').top, doseTop:b('.dose').top,
              doseLeft:b('.dose').left};}""")
    check("teal: a checklist row reads name first, its buttons beside it",
          row["nmLeft"]<row["btnLeft"] and row["nmTop"]<row["doseTop"] and abs(row["doseLeft"]-row["nmLeft"])<2, str(row))

    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    eb=q.locator("#editSplits").bounding_box()
    q.mouse.move(eb["x"]+eb["width"]/2, eb["y"]+eb["height"]/2); q.mouse.down(); q.wait_for_timeout(80)
    pressed=q.eval_on_selector("#editSplits","e=>parseFloat(getComputedStyle(e).opacity)")
    q.mouse.up(); q.wait_for_timeout(200)
    check("teal: a button shows it is being pressed", pressed<1, str(pressed))
    # Chromium applies :active with or without it, so only the source can say
    check("teal: and the touch hook iOS needs for that is there (checked in the source)",
          'document.addEventListener("touchstart"' in io.open("iron-ledger.html", encoding="utf-8").read())
    c.close()

    # ---------- CARDIO ----------
    # Asked for by Nygle, a tester: a tab of its own where Coach used to sit,
    # shaped like the Gym tab but simple. Start a timed session or add one,
    # named your own way; a goal by the day, week or month in minutes,
    # distance, calories or sessions; Finish with confetti; and a tracker on
    # the Log tab.
    CG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    CSTORE={"days":{}, "moves":{},"movesOwned":True,"goal":CG,"region":"United States","pantry":[],"v":1,"seen":True}
    CST="()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    CSAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
    CARDS="()=>[...document.querySelectorAll('.cardio-card')].map(c=>c.querySelector('h3').textContent+' | '+c.querySelector('.lift-foot span').textContent)"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("cardio: "+str(e)))
    q.goto("file://"+d+"/iron-ledger.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", CSTORE)
    q.reload(); q.wait_for_timeout(900)
    tabs=q.eval_on_selector_all(".tabs button","e=>e.filter(b=>b.getClientRects().length).map(b=>b.dataset.tab)")
    check("cardio: a tab of its own, between Gym and Log", tabs==["macros","pantry","gym","cardio","log"], str(tabs))
    q.click('.tabs button[data-tab="cardio"]'); q.wait_for_timeout(400)
    check("cardio: no rest timer here", q.evaluate("()=>document.getElementById('restbar').hidden"))
    check("cardio: an empty day says what to do", "Start a session above" in q.inner_text("#view"))
    check("cardio: the goal starts at 150 minutes a week",
          q.inner_text(".cardio-goal .cg-num")=="0 of 150 min" and q.inner_text(".cardio-goal .eyebrow")=="THIS WEEK")
    q.click("#cardioStart"); q.wait_for_timeout(250)
    check("cardio: Start asks what it is, and with nothing named yet the name field is ready",
          q.locator("#cPickNew").is_visible() and q.evaluate("()=>document.activeElement.id")=="cPickNew")
    q.fill("#cPickNew","Incline walk"); q.press("#cPickNew","Enter"); q.wait_for_timeout(300)
    check("cardio: a running clock, named, with Stop and Discard",
          q.inner_text(".workout .wo-label").upper()=="INCLINE WALK" and q.locator("#cardioStop").count()==1
          and q.locator("#cardioDiscard").count()==1 and q.evaluate(CST).get("cardioTypes")==["Incline walk"])
    q.click("#cardioStop"); q.wait_for_timeout(300)
    check("cardio: stopped under a minute, nothing is logged — and it says so",
          q.evaluate(CSAYS)=="Under a minute, so nothing was logged" and q.locator(".cardio-card").count()==0)
    q.click("#cardioStart"); q.wait_for_timeout(250); q.click("#cPickGo"); q.wait_for_timeout(300)
    q.evaluate("k=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1')); s.days[k].cardioStart=Date.now()-25*60000-5000; localStorage.setItem('iron-ledger-v1',JSON.stringify(s));}", Ts)
    q.reload(); q.wait_for_timeout(900); q.click('.tabs button[data-tab="cardio"]'); q.wait_for_timeout(400)
    check("cardio: the clock is a timestamp, so it is right after the app was away",
          q.inner_text("#cardioClock").startswith("25:"), q.inner_text("#cardioClock"))
    q.click("#cardioStop"); q.wait_for_timeout(300)
    check("cardio: Stop logs the session with its minutes, and says so",
          q.evaluate(CARDS)==["Incline walk | 25 min"] and q.evaluate(CSAYS)=="Logged Incline walk · 25 min", q.evaluate(CSAYS))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("cardio: undo puts the clock back running", q.locator("#cardioClock").count()==1 and q.locator(".cardio-card").count()==0)
    q.click("#cardioDiscard"); q.wait_for_timeout(300)
    check("cardio: Discard throws it away, with undo", q.locator("#cardioClock").count()==0 and q.evaluate(CSAYS)=="Discarded the running cardio clock")
    q.click("#undoBtn"); q.wait_for_timeout(300); q.click("#cardioStop"); q.wait_for_timeout(300)

    # adding by hand
    q.click("#cAdd"); q.wait_for_timeout(200)
    check("cardio: Add with no minutes says so, and adds nothing",
          q.inner_text("#cHint")=="How many minutes?" and len(q.evaluate(CARDS))==1)
    q.select_option("#cSel","__new"); q.fill("#cNew","Bike"); q.fill("#cMin","20"); q.fill("#cCal","180"); q.click("#cAdd"); q.wait_for_timeout(300)
    check("cardio: a new type, minutes and calories go in, and it says so",
          q.evaluate(CARDS)==["Incline walk | 25 min","Bike | 20 min · 180 kcal"] and q.evaluate(CSAYS)=="Added Bike · 20 min · 180 kcal"
          and q.evaluate(CST)["cardioTypes"]==["Incline walk","Bike"], str(q.evaluate(CARDS)))
    check("cardio: the next add opens on the type just used", q.input_value("#cSel")=="Bike")
    q.fill("#cMin","30"); q.fill("#cDist","3.1"); q.select_option("#cSel","Incline walk"); q.click("#cAdd"); q.wait_for_timeout(300)
    check("cardio: distance rides along", q.evaluate(CARDS)[2]=="Incline walk | 30 min · 3.1 mi")
    fields=q.eval_on_selector_all("#cardioAdd input, #cardioAdd select, #cardioAdd button",
          "e=>e.filter(x=>x.getClientRects().length).map(x=>[x.id,Math.round(x.getBoundingClientRect().height),x.tagName=='BUTTON'?16:parseFloat(getComputedStyle(x).fontSize)])")
    check("cardio: every control in the form clears 44px and no field zooms",
          len(fields)>=6 and all(h>=MIN_TAP and f>=16 for _,h,f in fields), str(fields))
    q.click('[data-cedit]'); q.wait_for_timeout(250)
    q.fill("#ceMin","27"); q.fill("#ceDist","2.6"); q.click("#ceSave"); q.wait_for_timeout(300)
    check("cardio: Change keeps the session and changes its numbers",
          q.evaluate(CARDS)[0]=="Incline walk | 27 min · 2.6 mi" and q.evaluate(CSAYS)=="Changed Incline walk to 27 min · 2.6 mi")
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("cardio: and undo puts them back", q.evaluate(CARDS)[0]=="Incline walk | 25 min")
    q.locator("[data-crm]").nth(2).click(); q.wait_for_timeout(300)
    check("cardio: Remove offers undo", len(q.evaluate(CARDS))==2 and q.evaluate(CSAYS).startswith("Removed Incline walk"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("cardio: and undo puts it back where it was", q.evaluate(CARDS)[2]=="Incline walk | 30 min · 3.1 mi")
    q.select_option("#cSel","Bike"); q.click("#cDrop"); q.wait_for_timeout(300)
    check("cardio: the minus takes a type off the list, not off the sessions",
          q.evaluate(CST)["cardioTypes"]==["Incline walk"] and "Bike | 20 min · 180 kcal" in q.evaluate(CARDS))
    q.click("#undoBtn"); q.wait_for_timeout(300)

    # the goal
    check("cardio: the week counts what was logged",
          q.inner_text(".cardio-goal .cg-num")=="75 of 150 min" and "3 sessions so far" in q.inner_text(".cg-left"), q.inner_text(".cardio-goal"))
    q.click("#cgOpen"); q.wait_for_timeout(250)
    check("cardio: the goal can count minutes, distance, calories or sessions, by the day, week or month",
          q.eval_on_selector_all("[data-cgkind]","e=>e.map(x=>x.textContent)")==["Minutes","Distance","Calories","Sessions"]
          and q.eval_on_selector_all("[data-cgperiod]","e=>e.map(x=>x.textContent)")==["Daily","Weekly","Monthly"])
    q.click('[data-cgkind="cal"]'); q.click('[data-cgperiod="day"]'); q.wait_for_timeout(100)
    check("cardio: a new pairing starts on its own number, not this one re-read",
          q.input_value("#cgVal")=="300" and q.inner_text("#cgValLab").upper()=="CALORIES A DAY")
    q.fill("#cgVal","0"); q.click("#cgSave"); q.wait_for_timeout(200)
    check("cardio: a goal of nothing is refused, and says why", q.inner_text("#cgHint").startswith("A goal needs"))
    q.fill("#cgVal","250"); q.click("#cgSave"); q.wait_for_timeout(300)
    check("cardio: a daily calories goal, counted",
          q.inner_text(".cardio-goal .eyebrow")=="TODAY" and q.inner_text(".cardio-goal .cg-num")=="180 of 250 kcal"
          and q.evaluate(CSAYS)=="Cardio goal: 250 kcal a day", q.inner_text(".cardio-goal"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("cardio: and undo puts the old goal back", q.inner_text(".cardio-goal .cg-num")=="75 of 150 min")
    q.click("#cgOpen"); q.wait_for_timeout(250); q.click('[data-cgkind="dist"]'); q.click('[data-cgperiod="month"]'); q.fill("#cgVal","3"); q.click("#cgSave"); q.wait_for_timeout(300)
    check("cardio: met, it says so in green",
          q.inner_text(".cardio-goal .cg-num")=="3.1 of 3 mi" and q.inner_text(".cg-left").startswith("✓ Goal met")
          and q.eval_on_selector(".cg-left","e=>e.classList.contains('is-met')"), q.inner_text(".cardio-goal"))
    q.click("#cgOpen"); q.wait_for_timeout(250); q.click('[data-cgkind="min"]'); q.click('[data-cgperiod="week"]'); q.click("#cgSave"); q.wait_for_timeout(300)

    # finished
    q.click("#cardioFinish"); q.wait_for_timeout(300)
    check("cardio: Finish shows the day complete, with confetti",
          q.inner_text(".daydone .dd-title").upper()=="CARDIO COMPLETE" and q.locator(".confetti").count()==1
          and q.locator("#cardioAdd").count()==0 and q.locator("[data-crm]").count()==0)
    check("cardio: and it is kept", q.evaluate(CST)["days"][Ts].get("cardioDone")==True)
    q.click("#cardioUnlock"); q.wait_for_timeout(300)
    check("cardio: Unlock opens it again", q.locator("#cardioAdd").count()==1)

    # a clock left running is not a session
    q.evaluate("k=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1')); s.days[k].cardioStart=Date.now()-7*3600000; s.days[k].cardioType='Bike'; localStorage.setItem('iron-ledger-v1',JSON.stringify(s));}", Ts)
    q.reload(); q.wait_for_timeout(900); q.click('.tabs button[data-tab="cardio"]'); q.wait_for_timeout(400)
    check("cardio: a clock left running for hours says it will not be logged",
          q.inner_text(".workout .wo-label").upper()=="LEFT RUNNING" and q.locator("#cardioStop").count()==0)
    q.click("#cardioDiscard"); q.wait_for_timeout(300)

    q.set_viewport_size({"width":320,"height":640}); q.click("#cgOpen"); q.wait_for_timeout(250)
    check("cardio: the tab fits a 320px phone, goal editor open",
          q.evaluate("()=>document.documentElement.scrollWidth")<=320)
    q.click("#cgCancel"); q.set_viewport_size({"width":402,"height":874}); q.wait_for_timeout(200)

    # the Log tab
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(500)
    track=q.inner_text(".cardio-track") if q.locator(".cardio-track").count() else ""
    check("log: a cardio tracker, the last eight weeks against the goal",
          "LAST 8 WEEKS" in track.upper() and q.locator(".ct-bar").count()==8 and q.locator(".ct-goal").count()==1, track[:80])
    check("log: and the year's cardio in tiles", "CARDIO DAYS" in track.upper() and "WEEKS ON GOAL" in track.upper())
    tt=q.eval_on_selector('[data-go="%s"]' % Ts, "e=>e.title")
    check("log: a day's title names its cardio", "cardio · Incline walk, Bike, Incline walk · 75 min · 180 kcal" in tt, tt)

    # it travels with a backup
    q.click("#backupBtn"); q.wait_for_timeout(300)
    ctxt=q.evaluate("()=>document.getElementById('backupText').value")
    q.click("#closeSheet"); q.wait_for_timeout(200)
    q.evaluate("()=>localStorage.removeItem('iron-ledger-v1')"); q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click("#backupBtn"); q.wait_for_timeout(300)
    q.evaluate("t=>{document.getElementById('backupText').value=t;}", ctxt)
    q.click("#restoreBtn"); q.wait_for_timeout(600)
    after=q.evaluate(CST)
    check("cardio: a restore brings back the sessions, the types and the goal",
          len(after["days"][Ts].get("cardio",[]))==3 and after.get("cardioTypes")==["Incline walk","Bike"]
          and after.get("cardioGoal",{}).get("kind")=="min")
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
