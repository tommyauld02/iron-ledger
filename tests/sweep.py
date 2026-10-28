import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
import io, os, json, datetime, calendar
import re
import fakeai

# Ledger rows open on their name, and Remove is inside the open row.
def del_row(pg, i=0):
    r = pg.locator(".t-row").nth(i)
    r.locator("[data-editrow], [data-openmeal]").first.click(); pg.wait_for_timeout(200)
    pg.locator(".t-row .t-del").first.click()

# Cardio's by-hand form is a sheet behind Log a session by hand.
def by_hand(pg):
    if not pg.locator("#cSel").count():
        pg.click("#cardioByHand"); pg.wait_for_timeout(250)

# Pantry's new-food form is a sheet behind + New in the bottom bar.
def pan_new(pg):
    if not pg.locator("#panName").count() or not pg.locator("#panName").is_visible():
        if not pg.locator("#panNew").count():
            pg.click('.tabs button[data-tab="pantry"]'); pg.wait_for_timeout(300)
        pg.click("#panNew"); pg.wait_for_timeout(200)

# Pantry rows open on tap; Remove is inside.
def rm_pan(pg, i=0):
    if pg.locator("#panNewClose").count():
        pg.click("#panNewClose"); pg.wait_for_timeout(200)
    pg.locator("[data-panmeals]").nth(i).click(); pg.wait_for_timeout(200)
    pg.locator("[data-rmpan]").first.click()

# Rule 5 is 44px, measured. This suite measures controls straight after the
# action that drew them, while the cards' 0.18s slide-in is still running, so
# a box can come back 43.99998 tall from subtracting two fractional edges — it
# failed the grip once that way. A control that is genuinely too small is a
# whole pixel short (the 43px scanner button CI caught), so half a pixel of
# allowance still catches every real one.
MIN_TAP = 43.5

def words(p):
    """Open the plain-words box, Ask an agent."""
    # the words box sits folded behind Ask an agent until asked for
    if p.locator('[data-logway="estimate"][aria-expanded="false"]').count():
        p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
# A UPC-A barcode as an SVG, for the scanner to read from a "photo".
_UPC_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
def upca_svg(code, mod=3, h=120):
    code = code.zfill(12)
    bits = "101" + "".join(_UPC_L[int(c)] for c in code[:6]) + "01010" + \
           "".join("".join("1" if b == "0" else "0" for b in _UPC_L[int(c)]) for c in code[6:]) + "101"
    q = 12; w = (len(bits) + 2 * q) * mod
    rects = "".join('<rect x="%d" y="10" width="%d" height="%d"/>' % ((q + i) * mod, mod, h)
                    for i, b in enumerate(bits) if b == "1")
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><rect width="100%%" height="100%%" fill="#fff"/>'
            '<g fill="#000">%s</g></svg>' % (w, h + 20, rects))
# every visible control in a part of the page: 44px tall, and inputs that will not zoom iOS
SIZES = """(sel)=>[...document.querySelectorAll(sel+' button, '+sel+' input:not([type=file]), '+sel+' select, '+sel+' label.btn')]
  .filter(x=>x.getClientRects().length && getComputedStyle(x).visibility!=='hidden')
  .map(x=>[x.id||x.textContent.trim().slice(0,24), Math.round(x.getBoundingClientRect().height), x.tagName==='INPUT'||x.tagName==='SELECT' ? parseFloat(getComputedStyle(x).fontSize) : 99])"""
def sizes_ok(p, sel):
    got = p.evaluate(SIZES, sel)
    bad = [g for g in got if g[1] < MIN_TAP or g[2] < 16]
    return (len(got) > 0 and not bad), (str(bad[:4]) if bad else "%d controls" % len(got))

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
    # The phone has a food finder key; its questions are answered by the
    # suites' stand-in, never sent anywhere (tests/fakeai.py).
    asked=[]; fakeai.phone(ctx, log=asked)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/mntl-dt.html"); p.wait_for_timeout(400)
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

    del_row(p, 1); p.wait_for_timeout(400)
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

    # estimator: pantry first, the food finder for the rest, in one
    # "beef wellington" is a dish the stand-in can only guess at, so its row
    # has to say so rather than pass for a known figure.
    words(p);p.fill("#estText","200g chicken breast & 1 costco protein coffee & beef wellington")
    p.click("#runEst"); p.wait_for_timeout(1200)
    rows=p.eval_on_selector_all(".rev-item",
      "e=>e.map(x=>x.querySelector('.food').textContent+'|'+x.querySelector('.amt').textContent.trim())")
    srcs=" ".join(rows)
    check("estimator: the finder answers what the pantry doesn't", srcs.count("AI ·") == 2, " / ".join(rows))
    check("estimator: pantry match", "your pantry" in srcs)
    check("estimator: a guess is labelled a guess", "rough guess" in srcs, " / ".join(rows))
    check("estimator: only what the pantry didn't know was asked about",
          asked and "costco" not in asked[-1]["food"] and "beef wellington" in asked[-1]["food"],
          asked and asked[-1]["food"])
    check("estimator: only the food and the country go to the relay, with no key",
          asked and sorted(asked[-1]["body"])==["food","region"] and asked[-1]["url"]==fakeai.RELAY)
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
    check("serving: the portion words go once the weight is yours",
          p.eval_on_selector(".rev-item .amt .pre", "e=>e.textContent") == "",
          p.eval_on_selector(".rev-item .amt .pre", "e=>e.textContent"))
    rowsum=sum(r["cal"] for r in p.evaluate(SNAP))
    head=p.eval_on_selector(".review > header span","e=>e.textContent").replace(",","")
    check("serving: the running total follows", ("%d kcal"%rowsum) in head,
          "rows=%d head=%r" % (rowsum, head))
    # ---------- ASK AN AGENT IS ONE WORDS BOX ----------
    # b71: the tabs went. Have the measurements built the same sentence the
    # words box does and sent it to the same place, and Scan a barcode has its
    # own button in the bottom bar, so Ask an agent opens straight on the box.
    # Committing here also closes the review the section above left open, and
    # a later check reads the corrected weight back out of the ledger.
    p.click("#commitEst"); p.wait_for_timeout(600)
    way(p, "estimate")
    check("entry: Ask an agent opens on the words box, with no tabs and no table",
          p.locator("#estText").count()==1 and p.locator("[data-esttab], [data-ef], [data-eq]").count()==0)
    check("entry: the box says what it is for",
          p.inner_text('label[for="estText"]').strip().upper()=="WHAT DID YOU EAT?",
          p.inner_text('label[for="estText"]') if p.locator('label[for="estText"]').count() else "no label")
    check("entry: and carries an example of the shorthand",
          "6 oz sirloin" in (p.get_attribute("#estText","placeholder") or ""),
          p.get_attribute("#estText","placeholder"))
    for sel in ("#estText", "#runEst"):
        bb=p.locator(sel).bounding_box()
        check("entry: %s clears 44px" % sel, bb and bb["height"]>=MIN_TAP,
              bb and "%dx%d"%(bb["width"],bb["height"]))

    # pressing it with nothing filled in must not read as a dead button
    p.click("#runEst"); p.wait_for_timeout(500)
    check("entry: an empty press says so rather than doing nothing",
          "Nothing to work out" in p.locator(".est").inner_text(),
          " / ".join(x.strip() for x in p.locator(".est .est-note").all_inner_texts())[:80])
    check("entry: and no review opened", p.locator(".review").count()==0)

    p.fill("#estText","6 oz chicken breast & 1 cup white rice")
    p.click("#runEst"); p.wait_for_timeout(1400)
    foods=p.eval_on_selector_all(".rev-item .food","e=>e.map(x=>x.textContent)")
    check("entry: both foods resolve", len(foods)==2, " | ".join(foods))
    check("entry: the unit you typed is the unit it used",
          p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value)")[0]=="oz",
          str(p.eval_on_selector_all("[data-iu]","e=>e.map(x=>x.value)")))
    p.click("#commitEst"); p.wait_for_timeout(800)
    check("entry: the box empties after it is logged",
          p.locator("#estText").count()==1 and p.input_value("#estText")=="",
          repr(p.input_value("#estText")) if p.locator("#estText").count() else "no box")

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
    lrows=p.eval_on_selector_all(".lift .lastset","e=>e.map(x=>x.textContent)")
    check("gym: last-session lookup", len(lrows)==3 and "135×10" in lrows[0] and "145×8" in lrows[2], str(lrows))
    check("gym: and the Last line is where and when, without the sets", last.startswith("Last · ") and "135" not in last, last.strip())
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
    # Last time had a set 2 (135×10), so that is what it opens on now; the
    # weight of the set before is what it opens on once last time is used up
    # (checked under LAST TIME, SET BY SET). 185 is typed so the rest of this
    # walk keeps its numbers.
    check("gym: it opens on last time's next set, 135×10", p.input_value("#seW")=="135" and p.input_value("#seR")=="10",
          "%s×%s" % (p.input_value("#seW"), p.input_value("#seR")))
    p.fill("#seW","185"); p.fill("#seR","5"); p.press("#seR","Enter"); p.wait_for_timeout(400)
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
    pan_new(p)
    check("pantry: photo button (sample avail)", p.evaluate("()=>!!document.getElementById('shotBtn')"))
    pan_new(p); p.fill("#panName","Quest bar"); p.fill("#panServe","1"); p.select_option("#panUnit","bar")
    p.fill("#panCal","200"); p.fill("#panPro","21"); p.click("#savePan"); p.wait_for_timeout(400)
    check("pantry: add count-unit food", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==2)
    pan_new(p); p.fill("#panName","Bulk oats"); p.fill("#panServe","40"); p.select_option("#panUnit","g")
    p.fill("#panCal","150"); p.fill("#panPro","5"); p.click("#savePan"); p.wait_for_timeout(400)
    check("pantry: add weight-unit food", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==3)
    pan_new(p); p.fill("#panName","Bad entry"); p.fill("#panServe","1"); p.select_option("#panUnit","g")
    p.fill("#panCal","200"); p.fill("#panPro","20"); p.click("#savePan"); p.wait_for_timeout(400)
    check("pantry: rejects impossible density",
          p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==3 and
          p.evaluate("()=>{const w=document.getElementById('panWarn');return w&&!w.hidden;}"))
    n0=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")
    rm_pan(p, 0); p.wait_for_timeout(400)
    check("pantry: remove", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==n0-1)
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("pantry: undo remove", p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry.length")==n0)

    # ---------- PANTRY -> MACROS, one tap ----------
    pan_new(p)
    check("pantry: wording", p.eval_on_selector('label[for="panName"]',"e=>e.textContent.strip?e.textContent:e.textContent")=="Type and save it")
    p.click("#panNewClose"); p.wait_for_timeout(250)
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
    pan_new(p); p.fill("#panName","test rashers"); p.fill("#panServe","4")
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
    p.click("#panNewClose"); p.wait_for_timeout(250)
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
    p.eval_on_selector_all(".cal-cell.hit, .cal-cell.miss","e=>{if(e.length)e[0].click()}"); p.wait_for_timeout(400)
    check("log: a tap on a day peeks at it first", p.locator("#peekSheet .pk-row").count()>=1,
          str(p.locator("#peekSheet").count()))
    p.click("#peekOpen"); p.wait_for_timeout(500)
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
                     "g=document.querySelector('.today-card'),e=document.querySelector('.log-ways');"
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
    # what is on screen: water's goal and unit stay folded away while water is off
    PRESSED="e=>e.filter(x=>x.getClientRects().length).map(x=>x.textContent)"
    # Ask an agent reads On: this phone is a fakeai.phone, which has already allowed it
    check("settings: it starts on the phone's own look and teal, with carbs, water and Coach hidden",
          p.eval_on_selector_all("#setSheet [aria-pressed=true]",PRESSED)==["Match phone","Teal","In place","Hidden","Hidden","Hidden","On"],
          str(p.eval_on_selector_all("#setSheet [aria-pressed=true]",PRESSED)))
    small=[x for x in p.eval_on_selector_all("#setSheet button",
           "e=>e.filter(b=>b.getClientRects().length).map(b=>[b.textContent.trim()||b.getAttribute('aria-label'),Math.round(b.getBoundingClientRect().height)])")
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
    bw=p.evaluate("()=>{const t=document.querySelector('.tabs'),s=getComputedStyle(t);return t.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight);}")
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
        c.add_init_script("delete window.claude;"); fakeai.phone(c); c.add_init_script(LAPCLOCK)
        q = c.new_page()
        q.on("pageerror", lambda e: errs.append("laps: "+str(e)))
        q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(900)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("edit: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(900)
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
    # nothing from last time to take it from, so the set before cannot lend its tag
    check("technique: with no last time, the next set starts on normal so a tag cannot ride along", q.input_value("#seT")=="")
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
    check("technique: next time, the rows say which set was the drop",
          "20×10 drop" in q.eval_on_selector(".lift .lastsets","e=>e.textContent"),
          q.eval_on_selector(".lift .lastsets","e=>e.textContent"))
    # Most sets are just sets. Never touching the box must be the ordinary
    # path, all the way to closing the movement out. Where last time's
    # matching set was the drop, the sheet opens on drop (the third set here),
    # so that one is chosen back to normal; the others are never touched.
    for i in range(3):
        log_set(q, 0, 30, 12, tech=("" if i == 2 else None), wait=150)
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
    SHOWN=("()=>[...document.querySelectorAll('.pan-rows .pan-item')].map(r=>r.querySelector('.nm').childNodes[0].textContent+"
           "(r.querySelector('.tags')?' ['+r.querySelector('.tags').textContent+']':''))")
    CHOSEN=("a=>[...document.querySelectorAll('['+a+'][aria-pressed=true]')].map(b=>b.getAttribute(a))")
    SAYS=("()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent")
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("sections: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    pan_new(q)
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
    pan_new(q); q.fill("#panName","Rice cakes"); q.fill("#panServe","1"); q.fill("#panCal","35"); q.fill("#panPro","1")
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("undo: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", UND)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    for _ in range(3):
        del_row(q, 0); q.wait_for_timeout(250)
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
    del_row(q, 0); q.wait_for_timeout(250)
    way(q, "numbers")
    q.fill("#fCal","100"); q.fill("#fPro","10"); q.fill("#fNote","Apple"); q.click("#addFood"); q.wait_for_timeout(400)
    check("undo: a change that cannot be undone ends the run", q.evaluate(SAYS)=="", q.evaluate(SAYS))
    del_row(q, 0); q.wait_for_timeout(250)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("compare: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("beat: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    # The line that spelled out every way past it (+5 lb / +1 rep / +1 set) was
    # taken off the card on 2026-10-14, at the owner's word: it was clutter. To
    # beat and the Beaten lines stay, and the rows beneath carry the rest.
    WAYS="()=>[...document.querySelectorAll('.lift')].map(x=>{const w=x.querySelector('.beat-ways');return w?w.textContent:'';})"
    check("beat: the suggestions line is gone from the card",
          q.evaluate(WAYS)[0]=="" and q.locator(".beat-ways").count()==0 and "+1 rep" not in q.eval_on_selector(".lift","e=>e.textContent"),
          q.evaluate(WAYS)[0])
    lift_set(0, "145", "8")
    check("beat: matching it is not beating it", q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    lift_set(0, "150", "7")
    check("beat: five pounds is worth a rep, so 150×7 only matches 145×8",
          q.evaluate(BL)[0]=="To beat · 145×8", q.evaluate(BL)[0])
    lift_set(0, "145", "9")
    check("beat: one more rep at the same weight beats it",
          q.evaluate(BL)[0]=="↑ Beaten · 145×9 over 145×8", q.evaluate(BL)[0])
    check("beat: and there is still no suggestions line once it is beaten", q.evaluate(WAYS)[0]=="", q.evaluate(WAYS)[0])
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
    check("beat: an extra set is no longer spelled out under the target",
          q.evaluate(WAYS)[5]=="" and q.evaluate(BL)[5]=="To beat · 100×10", q.evaluate(WAYS)[5])
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

    # ---------- LAST TIME, SET BY SET ----------
    # Asked for by the owner (issue #5, from his own pick of a prototype): each
    # open movement lays last time's sets out one row each, with today's against
    # each and what is next, and the Set pop-up opens on last time's matching set
    # instead of a blank. The suggestions line (+5 lb / +1 rep / +1 set) is gone.
    LSG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    LSA=(datetime.date.today()-datetime.timedelta(days=7)).isoformat()
    LSB=(datetime.date.today()-datetime.timedelta(days=5)).isoformat()
    LSTORE={"days":{
        LSA:{"food":[],"updated":1,"goal":LSG,"gym":"gA","gymNote":"felt strong","workoutMs":50*60000,"lifts":[
            {"id":"a","cat":"back","movement":"Leg Extension","note":"last set was really hard","sets":[
                {"w":60,"r":15,"tech":"warmup"},{"w":100,"r":15},{"w":150,"r":15},{"w":200,"r":10}]},
            {"id":"b","cat":"back","movement":"Hack Squat","sets":[
                {"w":40,"r":12,"tech":"warmup"},{"w":100,"r":10},{"w":120,"r":8}]},
            {"id":"c","cat":"back","movement":"Dumbbell Curl","sets":[{"w":30,"r":12}]}]},
        LSB:{"food":[],"updated":1,"goal":LSG,"gym":"g24","lifts":[
            {"id":"d","cat":"back","movement":"Leg Extension","sets":[{"w":90,"r":12}]}]}},
        "gyms":[{"id":"gA","name":"Apartment gym","tag":"APT"},{"id":"g24","name":"24 Hour Fitness","tag":"24"}],
        "gymLast":"gA","gymAsked":True,
        "moves":{"back":["Leg Extension","Hack Squat","Dumbbell Curl"]},"movesOwned":True,
        "goal":LSG,"region":"United States","pantry":[],"v":1}
    LSSETS="()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).days['"+Ts+"'].lifts.map(l=>l.sets.map(s=>s.w+'x'+s.r+(s.tech?':'+s.tech:'')))"
    LROWS="""(i)=>[...document.querySelectorAll('.lift')[i].querySelectorAll('.lastset')].map(r=>({
        left:r.children[0].textContent,
        today:(r.querySelector('.ls-right > span:not(.ls-mark):not(.ls-next)')||{}).textContent||'',
        mark:(r.querySelector('.ls-mark')||{className:''}).className.replace('ls-mark ',''),
        word:(r.querySelector('.ls-mark')||{textContent:''}).textContent,
        next:!!r.querySelector('.ls-next')}))"""
    SELECTED="id=>{const e=document.getElementById(id);return e.value.length>0&&e.selectionStart===0&&e.selectionEnd===e.value.length;}"
    FIELDS="()=>[document.getElementById('seW').value,document.getElementById('seR').value,document.getElementById('seT').value]"
    ONFIELD="()=>['seW','seR','seT'].includes((document.activeElement||{}).id)"
    HINT="()=>{const e=document.getElementById('seLastSet');return e.hidden?'':e.textContent;}"
    lsdate=lambda page,k: page.evaluate("k=>new Date(k+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})", k)
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("lastsets: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", LSTORE)
    q.reload(); q.wait_for_timeout(900)
    try: q.click("text=Got it", timeout=1500)
    except Exception: pass
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(400)
    add_movement(q, "Leg Extension"); add_movement(q, "Hack Squat")
    da=lsdate(q, LSA)
    rows=q.evaluate(LROWS, 0)
    check("lastsets: an open card lays last time out one row a set, in order",
          [r["left"] for r in rows]==["Set 1 · 60×15 warm-up","Set 2 · 100×15","Set 3 · 150×15","Set 4 · 200×10"], str(rows))
    check("lastsets: with nothing against them yet, and the first still to do marked next",
          [r["next"] for r in rows]==[True,False,False,False] and all(not r["mark"] and not r["today"] for r in rows), str(rows))
    lline=q.eval_on_selector(".lift .last","e=>e.textContent")
    check("lastsets: the Last line is where, when and both notes, without the sets",
          lline=="Last at APT · %s (felt strong) · “last set was really hard”" % da, lline)
    check("lastsets: To beat stays, and the suggestions line is gone from the card",
          q.eval_on_selector(".lift .beat","e=>e.textContent")=="To beat · 200×10"
          and q.locator(".lift .beat-ways").count()==0)
    check("lastsets: nothing in the rows is tappable, and nothing is teal",
          q.evaluate("""()=>{const hex=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim().replace('#','');
            const acc='rgb('+[0,2,4].map(i=>parseInt(hex.substr(i,2),16)).join(', ')+')';
            const els=[...document.querySelectorAll('.lift .lastsets, .lift .lastsets *')];
            return els.length>8 && !els.some(e=>e.matches('button,a,input,select,[role=button],[tabindex]') ||
              getComputedStyle(e).color===acc);}"""))
    # the Set pop-up opens on last time's next set, and leaves the keyboard down
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("lastsets: Set opens filled from last time's set 1, tag and all, and says which set it was",
          q.evaluate(FIELDS)==["60","15","warmup"] and q.evaluate(HINT)=="Last time, set 1: 60×15 warm-up · APT · %s" % da,
          str(q.evaluate(FIELDS))+" / "+q.evaluate(HINT))
    check("lastsets: opened from Set with numbers in it, no field is focused, so the keyboard stays down",
          not q.evaluate(ONFIELD))
    check("lastsets: the pop-up has no suggestions line either", q.locator("#seWays").count()==0
          and "+1 rep" not in q.eval_on_selector("#setEditSheet","e=>e.textContent"))
    q.click("#seSave"); q.wait_for_timeout(300)
    check("lastsets: Add set on a filled pop-up logs the warm-up as a warm-up", q.evaluate(LSSETS)[0]==["60x15:warmup"], str(q.evaluate(LSSETS)))
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("lastsets: set 2 opens on 100 / 15 / normal, with its own line",
          q.evaluate(FIELDS)==["100","15",""] and q.evaluate(HINT)=="Last time, set 2: 100×15 · APT · %s" % da, str(q.evaluate(FIELDS))+" / "+q.evaluate(HINT))
    q.click("#seSave"); q.wait_for_timeout(300)
    # typing replaces a number that is already there: 12 over 15 is not 1512
    q.click('[data-r="0"]'); q.wait_for_timeout(250)
    check("lastsets: opened from reps it is focused there, the filled number selected",
          q.evaluate("()=>document.activeElement.id")=="seR" and q.evaluate(SELECTED, "seR"))
    q.keyboard.type("12"); q.wait_for_timeout(100)
    check("lastsets: typing 12 over a filled 15 gives 12, not 1512", q.input_value("#seR")=="12", q.input_value("#seR"))
    q.focus("#seW"); q.wait_for_timeout(120)
    check("lastsets: focusing the weight selects it too", q.evaluate(SELECTED, "seW"))
    q.keyboard.type("155"); q.wait_for_timeout(100)
    check("lastsets: and typing 155 over a filled 150 gives 155", q.input_value("#seW")=="155", q.input_value("#seW"))
    q.keyboard.press("Enter"); q.wait_for_timeout(150)
    check("lastsets: Enter from the weight moves to the reps, selected",
          q.evaluate("()=>document.activeElement.id")=="seR" and q.evaluate(SELECTED, "seR"))
    q.keyboard.press("Enter"); q.wait_for_timeout(300)
    check("lastsets: Enter from the reps logs it", q.evaluate(LSSETS)[0]==["60x15:warmup","100x15","155x12"], str(q.evaluate(LSSETS)))
    rows=q.evaluate(LROWS, 0)
    check("lastsets: three sets in read matched, matched, short, with next on set 4",
          [r["mark"] for r in rows]==["ls-matched","ls-matched","ls-short",""]
          and [r["word"] for r in rows]==["= Matched","= Matched","↓ Short",""]
          and [r["next"] for r in rows]==[False,False,False,True], str(rows))
    check("lastsets: today's numbers sit beside them, and a tag only when it differs from last time's",
          [r["today"] for r in rows]==["60×15","100×15","155×12",""], str([r["today"] for r in rows]))
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("lastsets: the pop-up for set 4 opens at 200 / 10 / normal with the Last time, set 4 line",
          q.evaluate(FIELDS)==["200","10",""] and q.evaluate(HINT)=="Last time, set 4: 200×10 · APT · %s" % da,
          str(q.evaluate(FIELDS))+" / "+q.evaluate(HINT))
    q.fill("#seW","205"); q.fill("#seR","11"); q.click("#seSave"); q.wait_for_timeout(300)
    rows=q.evaluate(LROWS, 0)
    check("lastsets: a set worth more reads Beat, and nothing is next any more",
          rows[3]["mark"]=="ls-beat" and rows[3]["word"]=="↑ Beat" and rows[3]["today"]=="205×11"
          and not any(r["next"] for r in rows), str(rows[3]))
    check("lastsets: Beat is in the macro green and Matched and Short are not",
          q.evaluate("""()=>{const h=getComputedStyle(document.documentElement).getPropertyValue('--hit').trim().replace('#','');
            const rgb='rgb('+[0,2,4].map(i=>parseInt(h.substr(i,2),16)).join(', ')+')';
            const c=s=>getComputedStyle(document.querySelector(s)).color;
            return c('.ls-beat')===rgb && c('.ls-matched')!==rgb && c('.ls-short')!==rgb;}"""))
    check("lastsets: the Beaten line stays exactly as it was",
          q.eval_on_selector(".lift .beat","e=>e.textContent")=="↑ Beaten · 205×11 over 200×10", q.eval_on_selector(".lift .beat","e=>e.textContent"))
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("lastsets: past last time's count the pop-up is as before: the weight just used, blank reps, normal, no line",
          q.evaluate(FIELDS)==["205","",""] and q.evaluate(HINT)=="", str(q.evaluate(FIELDS)))
    check("lastsets: and Set goes straight to the weight, ready to type",
          q.evaluate("()=>document.activeElement.id")=="seW")
    q.click("#seCancel"); q.wait_for_timeout(200)
    # an extra warm-up today does not shift every row below it
    q.click('[data-addset="1"]'); q.wait_for_timeout(250)
    check("lastsets: Hack Squat opens on its own warm-up", q.evaluate(FIELDS)==["40","12","warmup"], str(q.evaluate(FIELDS)))
    q.click("#seSave"); q.wait_for_timeout(300)
    log_set(q, 1, 60, 8, tech="warmup")          # an extra warm-up, which last time had no row for
    q.click('[data-addset="1"]'); q.wait_for_timeout(250)
    check("lastsets: an extra warm-up leaves the next set where it was: the first working set",
          q.evaluate(FIELDS)==["100","10",""] and q.evaluate(HINT).startswith("Last time, set 2: 100×10"), str(q.evaluate(FIELDS))+" / "+q.evaluate(HINT))
    q.click("#seSave"); q.wait_for_timeout(300)
    log_set(q, 1, 120, 9)
    rows=q.evaluate(LROWS, 1)
    check("lastsets: so the working sets still pair with the working sets",
          [r["today"] for r in rows]==["40×12","100×10","120×9"] and [r["mark"] for r in rows]==["ls-matched","ls-matched","ls-beat"]
          and not any(r["next"] for r in rows), str(rows))
    check("lastsets: and the extra warm-up has no row of its own", "60×8" not in "".join(r["today"] for r in rows)
          and len(rows)==3 and q.evaluate(LSSETS)[1]==["40x12:warmup","60x8:warmup","100x10","120x9"], str(q.evaluate(LSSETS)[1]))
    # a warm-up skipped today is not offered once the working sets have begun:
    # next follows progress, the set after the furthest one done
    SKIP={"days":{LSA:{"food":[],"updated":1,"goal":LSG,"gym":"gA","lifts":[
            {"id":"a","cat":"back","movement":"Leg Extension","sets":[
                {"w":60,"r":15,"tech":"warmup"},{"w":100,"r":15},{"w":150,"r":15},{"w":200,"r":10}]}]},
          Ts:{"food":[],"updated":1,"goal":LSG,"gym":"gA","lifts":[
            {"id":"t","cat":"back","movement":"Leg Extension","sets":[{"w":100,"r":15,"t":1}]}]}},
        "gyms":[{"id":"gA","name":"Apartment gym","tag":"APT"}],"gymLast":"gA","gymAsked":True,
        "moves":{"back":["Leg Extension"]},"movesOwned":True,"goal":LSG,"region":"United States","pantry":[],"v":1}
    c2 = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c2.add_init_script("delete window.claude;"); fakeai.phone(c2)
    s2 = c2.new_page(); s2.on("pageerror", lambda e: errs.append("lastsets skip: "+str(e)))
    s2.goto("file://"+d+"/mntl-dt.html"); s2.wait_for_timeout(400)
    s2.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", SKIP)
    s2.reload(); s2.wait_for_timeout(900)
    try: s2.click("text=Got it", timeout=1500)
    except Exception: pass
    s2.click('.tabs button[data-tab="gym"]'); s2.wait_for_timeout(400)
    rows=s2.evaluate(LROWS, 0)
    check("lastsets: a warm-up skipped today is not next once the working sets have begun",
          [r["next"] for r in rows]==[False,False,True,False] and rows[1]["today"]=="100×15" and not rows[0]["today"], str(rows))
    s2.click('[data-addset="0"]'); s2.wait_for_timeout(250)
    check("lastsets: so the pop-up opens on set 3, not on the skipped warm-up",
          s2.evaluate(FIELDS)==["150","15",""] and s2.evaluate(HINT).startswith("Last time, set 3: 150×15"),
          str(s2.evaluate(FIELDS))+" / "+s2.evaluate(HINT))
    c2.close()
    # two gyms: rows come only from this gym
    q.click('[data-gym="g24"]'); q.wait_for_timeout(300)
    rows=q.evaluate(LROWS, 0)
    check("lastsets: at the other gym, the rows come from the last time there, not here",
          [r["left"] for r in rows]==["Set 1 · 90×12"] and q.eval_on_selector(".lift .last","e=>e.textContent").startswith("Last at 24 · "), str(rows))
    check("lastsets: a movement never done at this gym has no rows: Hack Squat was only ever at the other one",
          q.eval_on_selector_all(".lift","e=>e[1].querySelectorAll('.lastsets').length")==0
          and q.eval_on_selector_all(".lift .last","e=>e.map(x=>x.textContent)")[1].endswith("not a target here"))
    add_movement(q, "Dumbbell Curl")
    check("lastsets: a first time at a gym shows no rows, and keeps its not-a-target line",
          q.eval_on_selector_all(".lift","e=>e[2].querySelectorAll('.lastset').length")==0
          and q.eval_on_selector_all(".lift .last","e=>e.map(x=>x.textContent)")[2].endswith("30×12 · not a target here"))
    q.click('[data-addset="2"]'); q.wait_for_timeout(250)
    check("lastsets: and its pop-up is as before, with no line", q.evaluate(FIELDS)==["","",""] and q.evaluate(HINT)=="", str(q.evaluate(FIELDS)))
    q.click('[data-seshare="on"]'); q.wait_for_timeout(250)
    check("lastsets: Every gym fills the untouched fields from the new last time, and names the gym it was at",
          q.evaluate(FIELDS)==["30","12",""] and q.evaluate(HINT)=="Last time, set 1: 30×12 · APT · %s" % da,
          str(q.evaluate(FIELDS))+" / "+q.evaluate(HINT))
    q.fill("#seW","35")
    q.click('[data-seshare="off"]'); q.wait_for_timeout(250)
    check("lastsets: going back to this gym only empties what was filled, and keeps the number typed",
          q.evaluate(FIELDS)==["35","",""] and q.evaluate(HINT)=="", str(q.evaluate(FIELDS)))
    q.click('[data-seshare="on"]'); q.wait_for_timeout(250)
    check("lastsets: and a number already typed is never overwritten",
          q.evaluate(FIELDS)==["35","12",""], str(q.evaluate(FIELDS)))
    q.click("#seCancel"); q.wait_for_timeout(200)
    # Edit, inside the sheet: change the movement and the untouched fields follow
    q.click('[data-addset="2"]'); q.wait_for_timeout(250)
    check("lastsets: a movement taking its numbers from every gym opens filled", q.evaluate(FIELDS)==["30","12",""], str(q.evaluate(FIELDS)))
    q.click("#seMoveBtn"); q.wait_for_timeout(200)
    q.select_option("#seMove","Leg Extension"); q.click("#seMoveSave"); q.wait_for_timeout(300)
    check("lastsets: Edit to a movement with its own last time re-fills the untouched fields from that one",
          q.evaluate(FIELDS)==["90","12",""] and q.evaluate(HINT)=="Last time, set 1: 90×12 · 24 · %s" % lsdate(q, LSB),
          str(q.evaluate(FIELDS))+" / "+q.evaluate(HINT))
    q.click("#seCancel"); q.wait_for_timeout(200)
    # folded and locked cards are as they were
    q.click('[data-done="1"]'); q.wait_for_timeout(300)
    check("lastsets: a folded card keeps no rows", q.eval_on_selector_all(".lift.is-closed","e=>e.map(x=>x.querySelectorAll('.lastsets').length)")==[0])
    q.eval_on_selector("#lockDay","e=>e.scrollIntoView({block:'center'})")
    q.click("#lockDay"); q.wait_for_timeout(700)
    # a locked day closes every movement that has sets; the one left open is the
    # one with none, and it is read-only, so it draws no rows and its Last line
    # still carries last time's sets, as it always did
    check("lastsets: a locked day draws no rows, and an untouched card's Last line still carries the sets",
          q.locator(".lift .lastsets").count()==0
          and q.eval_on_selector_all(".lift:not(.is-closed) .last","e=>e.map(x=>x.textContent)")[-1].endswith("— 90×12"),
          str(q.eval_on_selector_all(".lift:not(.is-closed) .last","e=>e.map(x=>x.textContent)")))
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("notes: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    check("notes: and last time's note on the movement, on the same line", "\u201cLast set was really hard\u201d" in last, last)
    check("notes: the sets are in the rows below it, not on the line", "60\u00d710" not in last
          and q.eval_on_selector_all(".lift .lastset","e=>e.map(x=>x.textContent)")[0].startswith("Set 1 \u00b7 60\u00d710"))
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
        c.add_init_script("delete window.claude;"); fakeai.phone(c)
        q = c.new_page(); q.on("pageerror", lambda e: errs.append("special: "+str(e)))
        q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    check("special: the movement's last time is found wherever it was",
          ("Last · "+gday) in last and "35×10" in q.eval_on_selector(".lift .lastsets","e=>e.textContent"), last)
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
    check("special: back at the gym, the home session is last time",
          "(At home, dumbbells only)" in last and "25×20" in q.eval_on_selector(".lift .lastsets","e=>e.textContent"), last)
    check("special: and the number to beat", q.eval_on_selector(".lift .beat","e=>e.textContent")=="To beat · 25×20")
    check("special: with no suggestions line under it any more", q.locator(".lift .beat-ways").count()==0)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("yours: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    q.click("#panNew"); q.wait_for_timeout(250)
    check("yours: and the form offers the new one",
          q.eval_on_selector_all("[data-pansec]","e=>e.map(x=>x.textContent)")==["Brunch","Lunch","Dinner","Snacks","Pre-workout"])
    q.click("#panNewClose"); q.wait_for_timeout(250)
    q.click("#undoBtn"); q.wait_for_timeout(250); q.click("#undoBtn"); q.wait_for_timeout(250)
    check("yours: undo takes the new one back, then brings the old one back with its food",
          q.evaluate(YTABS)==["All 2","Brunch 1","Lunch","Dinner","Snacks","Desserts 1"], str(q.evaluate(YTABS)))
    q.click("#editPanSecs"); q.wait_for_timeout(250)
    while q.locator("[data-rmsec]").count():
        q.locator("[data-rmsec]").first.click(); q.wait_for_timeout(200)
    q.click("#editPanSecs"); q.wait_for_timeout(250)
    q.click("#panNew"); q.wait_for_timeout(250)
    nochoice=q.locator("[data-pansec]").count()==0
    q.click("#panNewClose"); q.wait_for_timeout(250)
    q.locator("[data-panmeals]").first.click(); q.wait_for_timeout(250)
    check("yours: with none at all there are no tabs, no choices and no Meals",
          q.evaluate(YTABS)==[] and nochoice and q.locator("[data-pansecfor]").count()==0)
    q.click("#panEditDone"); q.wait_for_timeout(250)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("sheet: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
          q.eval_on_selector("#seGoal","e=>e.textContent")=="To beat · 45×15")
    check("sheet: and no suggestions line under it any more", q.locator("#seWays").count()==0)
    check("sheet: nothing to remove on a set not yet logged", q.locator("#seRemove").is_hidden())
    # last time's set 1 fills the reps, so empty them: reps are the one field required
    q.fill("#seW","35"); q.fill("#seR",""); q.click("#seSave"); q.wait_for_timeout(250)
    check("sheet: reps are asked for, and nothing is logged without them",
          "reps" in q.eval_on_selector("#seWarn","e=>e.textContent") and not q.evaluate(SSDAY, Ts)["lifts"][0]["sets"])
    q.fill("#seR","20"); q.press("#seR","Enter"); q.wait_for_timeout(350)
    check("sheet: Add set logs it and the sheet goes",
          [(x["w"],x["r"]) for x in q.evaluate(SSDAY, Ts)["lifts"][0]["sets"]]==[(35,20)]
          and q.evaluate("()=>document.getElementById('setEditSheet').hidden"))
    check("sheet: the card says what it did", q.eval_on_selector(".lift .beat","e=>e.textContent")=="↑ Beaten · 35×20 over 45×15")
    q.click('[data-addset="0"]'); q.wait_for_timeout(250)
    check("sheet: the next set opens on last time's set 2, and says it is set 2",
          q.input_value("#seW")=="45" and q.input_value("#seR")=="15"
          and q.eval_on_selector("#seTitle","e=>e.textContent")=="Barbell Curl · set 2")
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
    # a movement with no last time: untouched fields go back to the weight of the set before, blank reps
    check("sheet: and fields nobody touched follow it — no last time for Dumbbell Curl, so 35 and blank",
          q.input_value("#seW")=="35" and q.input_value("#seR")=="" and q.locator("#seLastSet").is_hidden())
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("own: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(500)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("gyms: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("combine: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    # for what they are for, and each opens its box right under it. Since b71
    # the bottom bar is three of them, each with its name under its picture:
    # Log numbers (pencil), Ask an agent (#) and Scan.
    FG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    FSTORE={"days":{Ts:{"food":[{"id":"a","cal":520,"pro":46,"note":"Eggs"},
                                 {"id":"b","cal":0,"pro":0,"note":"chicken breast","pending":True}],
                        "lifts":[],"updated":1,"goal":FG,"supps":{}}},
            "supps":[{"id":"s1","name":"Creatine","dose":"5 g"}],
            "moves":{},"movesOwned":True,"goal":FG,"region":"United States","pantry":[],"v":1,"seen":True}
    WAYS="()=>[...document.querySelectorAll('[data-logway]')].map(b=>[b.dataset.logway,b.getAttribute('aria-expanded')])"
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("ways: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", FSTORE)
    q.reload(); q.wait_for_timeout(900)
    check("ways: both start folded, and neither form is on the page",
          q.evaluate(WAYS)==[["numbers","false"],["estimate","false"]]
          and q.locator("#fCal").count()==0 and q.locator("#runEst").count()==0, str(q.evaluate(WAYS)))
    W3="()=>[...document.querySelectorAll('#ctxMain .w3')].map(x=>x.innerText.trim())"
    check("ways: three buttons, each saying what it is for, in the order pencil, #, barcode",
          q.evaluate(W3)==["Log numbers","Ask an agent","Scan"]
          and q.get_attribute("[data-scanway]","aria-label")=="Scan a barcode", str(q.evaluate(W3)))
    check("ways: Ask an agent, the one most used, is the filled one",
          q.locator('.w3-main[data-logway="estimate"]').count()==1 and q.locator(".w3-main").count()==1)
    wb=q.eval_on_selector_all("#ctxMain .w3","e=>e.map(x=>x.getBoundingClientRect().height)")
    check("ways: all three are proper targets", len(wb)==3 and all(h>=MIN_TAP for h in wb), str(wb))
    # Not "the day fits on the phone": that depends on how much is logged and
    # on the platform's fonts — Linux CI drew this fixture 21px taller than
    # Windows. What folding owns is how little it leaves, and what it saves.
    WAYSPAN="()=>{const b=[...document.querySelectorAll('#ctxMain .w3')].map(x=>x.getBoundingClientRect());return Math.round(Math.max(...b.map(r=>r.bottom))-Math.min(...b.map(r=>r.top)));}"
    check("ways: folded, the forms are down to one row of buttons",
          q.evaluate(WAYSPAN)<=170, "%spx" % q.evaluate(WAYSPAN))
    folded_h=q.evaluate("()=>document.documentElement.scrollHeight")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    open_h=q.evaluate("()=>document.documentElement.scrollHeight")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: and folding takes most of a screen off the page",
          open_h-folded_h>=400, "%s folded, %s open" % (folded_h, open_h))
    q.click('[data-logway="numbers"]'); q.wait_for_timeout(300)
    check("ways: Log numbers opens its box, ready to type",
          q.evaluate(WAYS)[0]==["numbers","true"] and q.evaluate("()=>document.activeElement.id")=="fCal")
    check("ways: and its box opens on the page, with a Close of its own",
          q.locator("#logWays #wayNumbers").count()==1 and q.locator('#logWays [data-wayclose="numbers"]').count()==1)
    q.fill("#fCal","300"); q.fill("#fPro","25"); q.fill("#fNote","Yogurt"); q.click("#addFood"); q.wait_for_timeout(400)
    check("ways: adding says so, and the box stays open for the next one",
          "Added Yogurt" in q.inner_text(".added-flash") and q.locator("#fCal").count()==1)
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: one open at a time — the other folds",
          q.evaluate(WAYS)==[["numbers","false"],["estimate","true"]] and q.locator("#fCal").count()==0
          and q.evaluate("()=>document.activeElement.id")=="estText")
    check("ways: the confirmation still shows with the numbers box folded",
          q.locator(".added-flash").count()==1)
    q.fill("#estText","toast")
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: pressing the open one folds it", q.evaluate(WAYS)==[["numbers","false"],["estimate","false"]])
    q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
    check("ways: and what was typed is still there when it opens again", q.input_value("#estText")=="toast")
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

    # ---------- THE KEYBOARD ----------
    # A phone keyboard covers the page rather than shrinking it. On b66 the dock
    # rode up on it and sat over the field being typed in, and the numbers
    # pop-up opened behind it (the owner's screenshots). Chromium has no
    # keyboard to raise, so the visual viewport is stood in for and shrunk the
    # way an iPhone's is.
    KBFAKE = """(()=>{const t=new EventTarget(); t.offsetTop=0; t.scale=1;
      Object.defineProperty(t,'height',{get(){return innerHeight-(window.__kbH||0);}});
      Object.defineProperty(window,'visualViewport',{configurable:true,get:()=>t});
      window.__kb=(h)=>{window.__kbH=h; t.dispatchEvent(new Event('resize'));};})()"""
    for mode in ("inplace", "popup"):
        c = b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
        c.add_init_script("delete window.claude;"); c.add_init_script(KBFAKE); fakeai.phone(c)
        q = c.new_page(); q.on("pageerror", lambda e: errs.append("keyboard: "+str(e)))
        q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
        q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", dict(FSTORE, logOpen=mode))
        q.reload(); q.wait_for_timeout(900)
        q.click('[data-logway="numbers"]'); q.wait_for_timeout(300)
        HIGH="()=>document.documentElement.scrollHeight"
        ROOM="()=>document.documentElement.classList.contains('kb-room')"
        q.focus("#fCal"); q.wait_for_timeout(50)
        high=q.evaluate(HIGH)
        if mode == "inplace":
            # b75, the owner's video: the room grew while the keyboard came up,
            # iOS dropped the page back to the ledger, and the box went under the
            # keyboard. The room is there on focus, before any keyboard.
            check("keyboard (inplace): the room under the page is there on focus, before the keyboard",
                  q.evaluate(ROOM), str(q.evaluate(ROOM)))
        q.evaluate("()=>window.__kb(330)"); q.wait_for_timeout(600)
        if mode == "inplace":
            check("keyboard (inplace): the keyboard arriving changes no height, so iOS has nothing to re-place",
                  q.evaluate(HIGH)==high, "%s then %s" % (high, q.evaluate(HIGH)))
        DOCK="()=>getComputedStyle(document.querySelector('.dock')).visibility"
        check("keyboard (%s): up, the dock steps aside instead of covering the field" % mode,
              q.evaluate(DOCK)=="hidden", q.evaluate(DOCK))
        # b72, the owner's video: the dock was taken out of the page, the page
        # got shorter, the scroll snapped and the field went under the keyboard
        check("keyboard (%s): and the page never gets shorter, so nothing jumps" % mode,
              q.evaluate(HIGH)>=high, "%s then %s" % (high, q.evaluate(HIGH)))
        if mode == "inplace":
            TOP="()=>getComputedStyle(document.querySelector('.topbar')).position"
            check("keyboard (inplace): the header stops sticking, leaving the room to the form",
                  q.evaluate(TOP)=="relative", q.evaluate(TOP))
            BAND="()=>{const r=document.activeElement.getBoundingClientRect(); return [document.activeElement.id, Math.round(r.top), Math.round(r.bottom)]}"
            fid,ft,fb=q.evaluate(BAND)
            check("keyboard (inplace): the field typed in sits above the keyboard",
                  fid=="fCal" and ft>=0 and fb<=852-330, "%s %s-%s, keyboard at %s" % (fid, ft, fb, 852-330))
            q.evaluate("()=>window.scrollTo(0,0)"); q.wait_for_timeout(100)
            q.fill("#fCal","200"); q.fill("#fNote","Protein bar"); q.wait_for_timeout(150)
            q.dispatch_event("#addFood","pointerdown"); q.wait_for_timeout(700)
            fid,ft,fb=q.evaluate(BAND)
            check("keyboard (inplace): after Add to ledger, Calories is ready and in sight",
                  fid=="fCal" and ft>=0 and fb<=852-330, "%s %s-%s, keyboard at %s" % (fid, ft, fb, 852-330))
        if mode == "popup":
            low=q.evaluate("()=>Math.round(document.querySelector('[data-waysheet] .sheet-inner').getBoundingClientRect().bottom)")
            check("keyboard (popup): the pop-up sits above the keyboard, not behind it",
                  low <= 852-330+1, "sheet ends at %s, keyboard starts at %s" % (low, 852-330))
        q.evaluate("()=>{document.activeElement.blur(); window.__kb(0);}"); q.wait_for_timeout(150)
        check("keyboard (%s): down, the dock is back" % mode, q.evaluate(DOCK)=="visible", q.evaluate(DOCK))
        if mode == "inplace":
            # b74, the owner's video: Ask an agent flickered between the field and
            # the ledger ten times a second. keep() moved the page on every resize
            # the phone reported, the phone moved it back, and round they went.
            # Here the phone's half is played by hand: once the field is lifted,
            # the page is put somewhere else and the phone keeps reporting the same
            # keyboard. The app must move it once, then leave it alone.
            q.evaluate("()=>window.scrollTo(0,0)")
            q.click('[data-logway="estimate"]'); q.wait_for_timeout(300)
            # where the video had it: the box low on the screen, where the keyboard will be
            q.evaluate("()=>window.scrollBy(0,-250)")
            q.evaluate("()=>{window.__moves=0; const sb=window.scrollBy.bind(window); window.scrollBy=(x,y)=>{window.__moves++; sb(x,y);};}")
            q.evaluate("()=>window.__kb(330)"); q.wait_for_timeout(60)
            q.evaluate("()=>window.__kb(331)"); q.wait_for_timeout(60)
            q.evaluate("()=>window.__kb(336)"); q.wait_for_timeout(600)
            fid,ft,fb=q.evaluate(BAND)
            check("keyboard (agent): Ask an agent's box sits above the keyboard",
                  fid=="estText" and ft>=0 and fb<=852-336, "%s %s-%s, keyboard at %s" % (fid, ft, fb, 852-336))
            check("keyboard (agent): lifted once, after the keyboard settled, not once per step of it",
                  q.evaluate("()=>window.__moves")==1, "moved %s times" % q.evaluate("()=>window.__moves"))
            HIGHER=q.evaluate(HIGH)
            q.evaluate("()=>window.__kb(334)"); q.wait_for_timeout(50)
            check("keyboard (agent): a keyboard a pixel or two shorter never makes the page shorter",
                  q.evaluate(HIGH)>=HIGHER, "%s then %s" % (HIGHER, q.evaluate(HIGH)))
            y=q.evaluate("()=>{window.scrollBy(0,-300); return Math.round(scrollY);}")
            q.evaluate("()=>window.__moves=0")
            for i in range(8):
                q.evaluate("()=>window.__kb(window.__kbH)"); q.wait_for_timeout(120)
            check("keyboard (agent): the phone moving the page is not fought, so nothing flickers",
                  q.evaluate("()=>window.__moves")==0 and q.evaluate("()=>Math.round(scrollY)")==y,
                  "moved %s times, scrollY %s then %s" % (q.evaluate("()=>window.__moves"), y, q.evaluate("()=>Math.round(scrollY)")))
            # b75, the same video: put away at the foot of the page, the room went
            # at once and the phone slid the page up a keyboard's height. The room
            # stays until it is off the screen, and then goes without a move.
            y=q.evaluate("()=>{window.scrollTo(0, document.documentElement.scrollHeight); return Math.round(scrollY);}")
            q.evaluate("()=>{document.activeElement.blur(); window.__kb(0);}"); q.wait_for_timeout(250)
            check("keyboard (agent): put away at the foot of the page, the page stays where it was",
                  q.evaluate("()=>Math.round(scrollY)")==y and q.evaluate(ROOM),
                  "scrollY %s then %s, room %s" % (y, q.evaluate("()=>Math.round(scrollY)"), q.evaluate(ROOM)))
            tall=q.evaluate(HIGH)
            q.evaluate("()=>window.scrollTo(0,0)"); q.wait_for_timeout(250)
            check("keyboard (agent): and the room goes once it is off the screen",
                  not q.evaluate(ROOM) and q.evaluate(HIGH)<tall, "room %s, %s then %s" % (q.evaluate(ROOM), tall, q.evaluate(HIGH)))
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("opens: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
    check("opens: pop-up — Log numbers slides up, ready to type",
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
    check("opens: pop-up — Ask an agent slides up too",
          q.evaluate(SHEETS)==["estimate"] and q.evaluate("()=>document.activeElement.id")=="estText")
    q.fill("#estText","white rice"); q.click("#runEst"); q.wait_for_timeout(1000)
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("teal: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
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
          'document.addEventListener("touchstart"' in io.open("mntl-dt.html", encoding="utf-8").read())
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
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("cardio: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", CSTORE)
    q.reload(); q.wait_for_timeout(900)
    tabs=q.eval_on_selector_all(".tabs button","e=>e.filter(b=>b.getClientRects().length).map(b=>b.dataset.tab)")
    check("cardio: a tab of its own, between Gym and Log", tabs==["macros","pantry","gym","cardio","log"], str(tabs))
    q.click('.tabs button[data-tab="cardio"]'); q.wait_for_timeout(400)
    check("cardio: no rest timer here", q.evaluate("()=>document.getElementById('restbar').hidden"))
    check("cardio: an empty day says what to do", "Start a session above" in q.inner_text("#view"))
    check("cardio: the goal starts at 150 minutes a week",
          " ".join(q.inner_text(".cardio-goal .cg-num").split())=="0 of 150 min" and q.inner_text(".cardio-goal .eyebrow")=="THIS WEEK")
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

    # adding by hand: a sheet, behind Log a session by hand
    by_hand(q)
    check("cardio: by hand, the calories line says the app never guesses",
          "never guesses" in q.inner_text("#cardioAdd"))
    q.click("#cAdd"); q.wait_for_timeout(200)
    check("cardio: Add with no minutes says so, and adds nothing",
          q.inner_text("#cHint")=="How many minutes?" and len(q.evaluate(CARDS))==1)
    q.select_option("#cSel","__new"); q.fill("#cNew","Bike"); q.fill("#cMin","20"); q.fill("#cCal","180"); q.click("#cAdd"); q.wait_for_timeout(300)
    check("cardio: a new type, minutes and calories go in, and it says so",
          q.evaluate(CARDS)==["Incline walk | 25 min","Bike | 20 min · 180 kcal"] and q.evaluate(CSAYS)=="Added Bike · 20 min · 180 kcal"
          and q.evaluate(CST)["cardioTypes"]==["Incline walk","Bike"], str(q.evaluate(CARDS)))
    check("cardio: adding closes the sheet", q.locator("#cardioAdd").count()==0)
    by_hand(q)
    check("cardio: the next add opens on the type just used", q.input_value("#cSel")=="Bike")
    q.fill("#cMin","30"); q.fill("#cDist","3.1"); q.select_option("#cSel","Incline walk"); q.click("#cAdd"); q.wait_for_timeout(300)
    check("cardio: distance rides along", q.evaluate(CARDS)[2]=="Incline walk | 30 min · 3.1 mi")
    by_hand(q)
    fields=q.eval_on_selector_all("#cardioAdd input, #cardioAdd select, #cardioAdd button",
          "e=>e.filter(x=>x.getClientRects().length).map(x=>[x.id,Math.round(x.getBoundingClientRect().height),x.tagName=='BUTTON'?16:parseFloat(getComputedStyle(x).fontSize)])")
    check("cardio: every control in the form clears 44px and no field zooms",
          len(fields)>=6 and all(h>=MIN_TAP and f>=16 for _,h,f in fields), str(fields))
    q.click("#cAddClose"); q.wait_for_timeout(250)
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
    by_hand(q); q.select_option("#cSel","Bike"); q.click("#cDrop"); q.wait_for_timeout(300)
    check("cardio: the minus takes a type off the list, not off the sessions",
          q.evaluate(CST)["cardioTypes"]==["Incline walk"] and "Bike | 20 min · 180 kcal" in q.evaluate(CARDS))
    check("cardio: taking a type off closes the sheet, so Undo can be reached",
          q.locator("#cardioAdd").count()==0 and q.locator("#undoBtn").is_visible())
    q.click("#undoBtn"); q.wait_for_timeout(300)

    # the goal
    check("cardio: the week counts what was logged",
          " ".join(q.inner_text(".cardio-goal .cg-num").split())=="75 of 150 min" and "3 sessions so far" in q.inner_text(".cg-legend"), q.inner_text(".cardio-goal"))
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
          q.inner_text(".cardio-goal .eyebrow")=="TODAY" and " ".join(q.inner_text(".cardio-goal .cg-num").split())=="180 of 250 kcal"
          and q.evaluate(CSAYS)=="Cardio goal: 250 kcal a day", q.inner_text(".cardio-goal"))
    q.click("#undoBtn"); q.wait_for_timeout(300)
    check("cardio: and undo puts the old goal back", " ".join(q.inner_text(".cardio-goal .cg-num").split())=="75 of 150 min")
    q.click("#cgOpen"); q.wait_for_timeout(250); q.click('[data-cgkind="dist"]'); q.click('[data-cgperiod="month"]'); q.fill("#cgVal","3"); q.click("#cgSave"); q.wait_for_timeout(300)
    check("cardio: met, it says so in green",
          " ".join(q.inner_text(".cardio-goal .cg-num").split())=="3.1 of 3 mi" and q.inner_text(".cg-left").startswith("✓ Goal met")
          and q.eval_on_selector(".cg-left","e=>e.classList.contains('is-met')"), q.inner_text(".cardio-goal"))
    q.click("#cgOpen"); q.wait_for_timeout(250); q.click('[data-cgkind="min"]'); q.click('[data-cgperiod="week"]'); q.click("#cgSave"); q.wait_for_timeout(300)

    # finished
    q.click("#cardioFinish"); q.wait_for_timeout(300)
    check("cardio: Finish shows the day complete, with confetti",
          q.inner_text(".daydone .dd-title").upper()=="CARDIO COMPLETE" and q.locator(".confetti").count()==1
          and q.locator("#cardioAdd").count()==0 and q.locator("[data-crm]").count()==0)
    check("cardio: and it is kept", q.evaluate(CST)["days"][Ts].get("cardioDone")==True)
    q.click("#cardioUnlock"); q.wait_for_timeout(300)
    check("cardio: Unlock opens it again", q.locator("#cardioByHand").count()==1)

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

    # ---------- THE FOOD FINDER ----------
    # Asked for by the owner in place of the lists the app shipped: anything
    # the pantry doesn't know goes to a free AI, with nothing to set up. The app
    # asks the relay (relay/worker.js, which has its own suite, tests/relay.py);
    # here tests/fakeai.py stands in for it, and `reply` lets a check make it
    # busy, wrong or unreachable.
    LBG={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
    LBSTORE={"days":{},"moves":{},"movesOwned":True,"goal":LBG,"region":"United States","pantry":[],"v":1,"seen":True}
    LBST="()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))"
    ROWS="()=>[...document.querySelectorAll('.rev-item .food')].map(x=>x.textContent)"
    TAGS="()=>[...document.querySelectorAll('.rev-item .src-tag')].map(x=>x.textContent)"
    fx={"reply":None}; fasked=[]
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;")
    fakeai.phone(c, reply=lambda qq: fx["reply"](qq) if fx["reply"] else None, log=fasked)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("finder: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", LBSTORE)
    q.reload(); q.wait_for_timeout(900)
    def estimate(food, qty=""):
        if q.locator("#discardEst").count(): q.click("#discardEst"); q.wait_for_timeout(250)
        way(q, "estimate")
        q.fill("#estText", (qty + " " + food).strip()); q.click("#runEst"); q.wait_for_timeout(900)
    check("finder: nothing to set up — Settings asks for no key",
          q.locator("#setSheet input").count()==q.locator("#setWaterGoal").count() and "key" not in q.inner_text("#setSheet").lower(),
          q.inner_text("#setSheet")[:120])
    estimate("cava harissa avocado bowl", "1")
    check("finder: it answers the first time, with nothing set up", q.evaluate(TAGS)==["AI · rough guess"], str(q.evaluate(TAGS)))
    check("finder: a dish only guessed at says it is a guess", "rough guess" in " ".join(q.evaluate(TAGS)))
    estimate("1 quarter pounder with cheese")
    check("finder: a food named with 'with' stays one food — no stray cheese",
          q.evaluate(ROWS)==["Quarter pounder with cheese"], str(q.evaluate(ROWS)))
    check("finder: the finder was asked in the words typed",
          fasked[-1]["food"]=="1 quarter pounder with cheese", fasked[-1]["food"])
    estimate("medium mcdonalds french fries", "2")
    check("finder: a chain's item says it is the chain's own figure",
          q.evaluate(TAGS)==["AI · brand’s figures"], str(q.evaluate(TAGS)))
    check("finder: the amount reads as typed",
          q.inner_text(".rev-item .amt .pre").startswith("2 medium"), q.inner_text(".rev-item"))
    check("finder: the country typed goes with the question, and nothing else does",
          fasked[-1]["region"]=="United States" and sorted(fasked[-1]["body"])==["food","region"], str(fasked[-1]["body"]))
    q.click("#commitEst"); q.wait_for_timeout(400)
    food=q.evaluate(LBST)["days"][Ts]["food"]
    check("finder: it goes into the ledger marked as an estimate, carbs and fat with it",
          food and food[-1].get("est") is True and food[-1].get("cal")==round(323*222/100) and "carb" in food[-1],
          json.dumps(food[-1:])[:200])
    estimate("xyzzy")
    check("finder: something nobody could read as food says so",
          "Couldn't read that as food" in q.inner_text(".est"), q.inner_text(".est")[:120])

    # Busy: Gemini's free allowance. What the pantry knew is kept, the rest waits.
    fx["reply"]=lambda qq: (429, {"error":"busy"})
    estimate("chicken breast", "6 oz")
    check("finder: busy says so, in words",
          "busy, or at today’s free limit" in q.inner_text(".review"), q.inner_text(".review")[:200])
    check("finder: and the food waits as a placeholder rather than vanishing",
          q.evaluate(TAGS)==["needs numbers"] and q.locator("[data-reask]").count()==1, str(q.evaluate(TAGS)))
    rb=q.locator("[data-reask]").bounding_box()
    check("finder: Find it again is a proper target", rb and rb["height"]>=MIN_TAP, str(rb))
    fx["reply"]=None
    q.click("[data-reask]"); q.wait_for_timeout(700)
    check("finder: Find it again answers the row in place",
          q.evaluate(ROWS)==["Chicken breast"] and q.input_value('[data-ig="0"]')=="6" and q.input_value('[data-iu="0"]')=="oz"
          and "busy" not in q.inner_text(".review"), "%s / %s" % (q.evaluate(ROWS), q.inner_text(".review")[:120]))
    check("finder: and only the row was asked about", fasked[-1]["food"]=="6 oz chicken breast", fasked[-1]["food"])
    # Two at once, the first answering as two foods: the second still lands on
    # its own row rather than being dropped with its spinner left running.
    CHILI={"items":[{"food":"Chili","amount":"1 bowl","grams":250,"calories":260,"protein":18,"carbs":22,"fat":11,"basis":"typical"},
                    {"food":"Cornbread","amount":"1 piece","grams":60,"calories":190,"protein":4,"carbs":28,"fat":7,"basis":"typical"}],"note":""}
    fx["reply"]=lambda qq: (429, {"error":"busy"})
    if q.locator("#discardEst").count(): q.click("#discardEst"); q.wait_for_timeout(250)
    way(q, "estimate")
    q.fill("#estText", "a bowl of chili & 6 oz chicken breast"); q.click("#runEst"); q.wait_for_timeout(900)
    fx["reply"]=lambda qq: CHILI if "chili" in qq["food"] else None
    # both taps before either answer is back: the second button is found
    # again after the first tap redraws the review
    q.evaluate("""()=>{document.querySelector('[data-reask="0"]').click();
                      document.querySelector('[data-reask="1"]').click();}"""); q.wait_for_timeout(1000)
    check("finder: two Find it agains at once each land on their own row",
          q.evaluate(ROWS)==["Chili","Cornbread","Chicken breast"] and q.locator(".est-flag .working").count()==0,
          "%s / spinners %d" % (q.evaluate(ROWS), q.locator(".est-flag .working").count()))
    fx["reply"]=None
    q.click("#discardEst"); q.wait_for_timeout(250)

    # The relay re-checks numbers that don't add up; whatever still doesn't
    # comes back as it was, and the app flags it on its row.
    BAD={"items":[{"food":"Banana","amount":"1 medium","grams":118,"calories":905,"protein":1,"carbs":27,"fat":0,"basis":"typical"}],"note":"","rechecked":True}
    GOOD={"items":[{"food":"Banana","amount":"1 medium","grams":118,"calories":105,"protein":1,"carbs":27,"fat":0,"basis":"typical"}],"note":"","rechecked":True}
    fx["reply"]=lambda qq: GOOD
    estimate("banana", "1")
    check("finder: numbers that add up are not flagged",
          q.input_value('[data-ic="0"]')=="105" and q.locator(".est-flag").count()==0, q.input_value('[data-ic="0"]'))
    fx["reply"]=lambda qq: BAD
    estimate("banana", "1")
    check("finder: a slip that survived the relay's second look is flagged on its row",
          q.input_value('[data-ic="0"]')=="905" and "don’t match its protein, carbs and fat" in q.inner_text(".est-flag"),
          q.inner_text(".review")[:200])

    # The ways it can fail each say what happened.
    for name, rep, said in [("Gemini refusing the relay's key", (502, {"error":"key"}), "a problem on its side"),
                            ("no connection", "abort", "Couldn’t reach the food finder"),
                            ("a reply that isn't numbers", (502, {"error":"unreadable"}), "didn’t come back as numbers"),
                            ("too many lookups from one phone", (429, {"error":"slow_down"}), "lot of lookups from this phone"),
                            ("too many words at once", (400, {"error":"too_long"}), "two shorter goes"),
                            ("a relay with no key yet", (503, {"error":"not_set_up"}), "isn’t available right now"),
                            ("something that isn't the relay", (200, "<html>oops</html>"), "didn’t come back as numbers")]:
        fx["reply"]=(lambda r: (lambda qq: r))(rep)
        estimate("chicken breast", "6 oz")
        check("finder: %s says so" % name, said in q.inner_text(".review"), q.inner_text(".review")[:160])
    fx["reply"]=None
    q.set_viewport_size({"width":320,"height":640}); q.wait_for_timeout(200)
    check("finder: the review fits a 320px phone", q.evaluate("()=>document.documentElement.scrollWidth")<=320)
    q.set_viewport_size({"width":402,"height":874}); q.wait_for_timeout(200)
    q.click("#discardEst"); q.wait_for_timeout(250)
    c.close()

    # A copy of the app with no finder at all: the food waits, and says why.
    nasked=[]
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;"); c.add_init_script(fakeai.NO_RELAY_SCRIPT)
    fakeai.install(c, log=nasked)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("no finder: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", LBSTORE)
    q.reload(); q.wait_for_timeout(900)
    estimate("chicken breast", "6 oz")
    check("finder: with no finder the food waits, and the review says why",
          q.evaluate(TAGS)==["needs numbers"] and "isn’t available in this copy" in q.inner_text(".review")
          and q.locator("[data-reask]").count()==0, q.inner_text(".review")[:200])
    check("finder: and nothing at all was sent", not nasked)
    c.close()

    # ---------- WHAT'S NEW ----------
    # Asked for by the owner: after an update, a one-time pop-up saying what
    # changed. Keyed on the build that last saved the phone's data, so it shows
    # what is new since that phone last opened the app — once — and never to
    # someone opening it for the first time.
    BUILDNOW=re.search(r'var BUILD = "([^"]+)"', io.open("mntl-dt.html", encoding="utf-8").read()).group(1)
    NEWS="()=>[...document.querySelectorAll('#newsBody h3')].map(x=>x.textContent)"
    def opened(store):
        q.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
        q.reload(); q.wait_for_timeout(900)
    c = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
    c.add_init_script("delete window.claude;"); fakeai.phone(c)
    q = c.new_page(); q.on("pageerror", lambda e: errs.append("news: "+str(e)))
    q.goto("file://"+d+"/mntl-dt.html"); q.wait_for_timeout(400)
    opened(dict(LBSTORE, build="2026-10-09.58"))
    titles=q.evaluate(NEWS)
    check("news: after an update it shows what changed since, newest first",
          q.is_visible("#newsSheet") and len(titles)==4 and titles[0]=="An age check, and Ask an agent asks first"
          and titles[1]=="The keyboard settles" and titles[2]=="Ask an agent holds still"
          and titles[3]=="A new name: MNTL D&T", str(titles))
    check("news: and not what this phone already had", "Cardio" not in titles, str(titles))
    # b69's walkthrough aged out of the newest four at b73, like every entry
    # before it. Its checks (inline, preload none, Got it pauses it) ran from
    # b69 to b72; with no video on the sheet they would pass by measuring
    # nothing, so they are gone rather than left standing.
    check("news: the b69 walkthrough has aged out with the older news",
          q.evaluate("()=>document.querySelectorAll('#newsBody video').length")==0)
    nb=q.locator("#newsDone").bounding_box()
    check("news: Got it is a proper target", nb and nb["height"]>=MIN_TAP, str(nb))
    q.set_viewport_size({"width":320,"height":640}); q.wait_for_timeout(200)
    check("news: it fits a 320px phone", q.evaluate("()=>document.documentElement.scrollWidth")<=320)
    q.set_viewport_size({"width":402,"height":874}); q.wait_for_timeout(200)
    q.click("#newsDone"); q.wait_for_timeout(200)
    check("news: Got it closes it, and the phone is marked as on this build",
          not q.is_visible("#newsSheet") and q.evaluate(LBST).get("build")==BUILDNOW, q.evaluate(LBST).get("build"))
    q.reload(); q.wait_for_timeout(900)
    check("news: it is shown once, not on every open", not q.is_visible("#newsSheet"))
    opened(dict(LBSTORE, build="2026-08-01.30"))
    titles=q.evaluate(NEWS)
    check("news: a phone far behind sees the latest four, not the whole history", len(titles)==4, str(titles))
    q.mouse.click(200, 12); q.wait_for_timeout(200)
    check("news: a tap on the dimmed page closes it too", not q.is_visible("#newsSheet"))
    opened(LBSTORE)
    check("news: a phone opening the app for the first time is not told what changed", not q.is_visible("#newsSheet"))
    c.close()

    def fresh(store, label):
        cx = b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True)
        cx.add_init_script("delete window.claude;"); fakeai.phone(cx)
        pg = cx.new_page(); pg.on("pageerror", lambda e: errs.append(label+": "+str(e)))
        pg.goto("file://"+d+"/mntl-dt.html"); pg.wait_for_timeout(400)
        pg.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
        pg.reload(); pg.wait_for_timeout(900)
        return cx, pg

    # ---------- BARCODES ----------
    # Step 3: a package's barcode, found among the grocery brands by the number
    # under its bars. By camera, by photo, or typed. Your pantry answers first,
    # and a product USDA lacks is found from the pantry once saved there.
    # With the brands in, the sheet asks for the camera, and the answer redraws
    # it — wiping a number typed before the answer lands. This browser has no
    # camera, so the answer is a refusal some 400 ms later, which the fixed
    # sleeps here used to outlast only by luck (darkcheck lost its card to it on
    # 2026-10-17). So each step types once the answer is on the sheet — a
    # message drawn, and no camera view still waiting for its stream — and
    # waits for the card rather than sleeping.
    def camera_answered(pg):
        try: pg.wait_for_function("""()=>{const m=document.getElementById('scanMsg'), v=document.getElementById('scanVideo');
            return !!(m && m.textContent.trim()) && (!v || !!v.srcObject);}""", timeout=10000)
        except Exception: pass      # still waiting: type anyway, and the card says whether it worked
    def scan_card(pg):
        """The card Look up brings, once it is on screen; "" if it never comes."""
        try: pg.wait_for_selector(".scan-card", timeout=5000)
        except Exception: return ""
        return pg.inner_text(".scan-card")
    c, q = fresh(LBSTORE, "barcodes")
    # Scan in the bottom bar opens the reader in one press (b71); it used to
    # open a Scan tab whose one button opened it.
    q.click("[data-scanway]"); q.wait_for_timeout(300)
    check("barcodes: Scan in the bottom bar opens the reader itself",
          q.locator("#scanSheet").count()==1 and q.locator("#wayEstimate").count()==0)
    check("barcodes: before grocery brands are on the phone, it offers them rather than failing",
          q.locator("#scanBrands").count()==1 and "9 MB" in q.inner_text("#scanBrands"), q.inner_text("#scanSheet")[:120])
    q.click("#scanBrands")
    try: q.wait_for_selector("#scanType", timeout=40000)
    except Exception: pass
    camera_answered(q)
    check("barcodes: once they are, the camera, a photo and typing are all offered",
          q.locator("#scanType").count()==1 and q.locator("#scanFile").count()==1 and q.evaluate(LBST).get("brandsOn") is True,
          q.inner_text("#scanSheet")[:160])
    ok_, det = sizes_ok(q, "#scanSheet")
    check("barcodes: every control clears 44px and the number field will not zoom", ok_, det)
    q.fill("#scanType", "894700010038"); q.click("#scanGo")
    card=scan_card(q)
    check("barcodes: a typed number finds the product, with its label's serving",
          "Chobani · Greek Yogurt" in card and "1 container · 150 g" in card and "120 kcal" in card,
          card.replace("\n"," | ") or q.inner_text("#scanSheet")[:160])
    # Scan another asks for the camera again; the last card stays until it answers.
    q.click("#scanAgain"); camera_answered(q)
    pg2 = c.new_page(); pg2.set_content(upca_svg("078742351865")); png = pg2.locator("svg").screenshot(); pg2.close()
    q.set_input_files("#scanFile", files=[{"name":"barcode.png","mimeType":"image/png","buffer":png}])
    try: q.wait_for_selector(".scan-card", timeout=30000)
    except Exception: pass
    card=q.inner_text(".scan-card") if q.locator(".scan-card").count() else ""
    check("barcodes: a photo of a barcode is read on the phone and found",
          "Great Value · Whole Milk" in card and "149 kcal" in card, card.replace("\n"," | ") or q.inner_text("#scanSheet")[:120])
    q.click("#scanAdd"); q.wait_for_timeout(400)
    check("barcodes: Add puts it in the review, from the label",
          q.evaluate(ROWS)==["Great Value Whole Milk"] and q.inner_text(".rev-item .src-tag").upper()=="BRAND LABEL · 2026", str(q.evaluate(ROWS)))
    q.click("#discardEst"); q.wait_for_timeout(300)
    q.click("[data-scanway]"); camera_answered(q)
    q.fill("#scanType", "071717171717"); q.click("#scanGo")
    card=scan_card(q)
    check("barcodes: a number that is nowhere says so, and offers the pantry",
          "No product with barcode 071717171717" in card and q.locator("#scanToPantry").count()==1,
          card[:120] or q.inner_text("#scanSheet")[:160])
    q.click("#scanToPantry"); q.wait_for_timeout(400)
    check("barcodes: the pantry form opens knowing the barcode",
          q.get_attribute('.tabs button[data-tab="pantry"]',"aria-selected")=="true" and "71717171717 is saved with it" in q.inner_text("#view"))
    pan_new(q); q.fill("#panName","Corner store protein bar"); q.fill("#panServe","1"); q.select_option("#panUnit","bar")
    q.fill("#panCal","210"); q.fill("#panPro","20"); q.click("#savePan"); q.wait_for_timeout(300)
    pan=[x for x in q.evaluate(LBST)["pantry"] if x["name"]=="Corner store protein bar"]
    check("barcodes: it is saved with the food", pan and pan[0].get("upc")=="71717171717", str(pan))
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    q.click("[data-scanway]"); camera_answered(q)
    q.fill("#scanType", "071717171717"); q.click("#scanGo")
    card=scan_card(q)
    check("barcodes: and the next scan finds it, from the pantry",
          "Corner store protein bar" in card and "Your pantry" in card, card[:120] or q.inner_text("#scanSheet")[:160])
    q.click("#scanClose"); q.wait_for_timeout(200)
    # scanning on the Pantry tab fills the form from the label
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(300)
    q.click("#panBarScan"); camera_answered(q)
    q.fill("#scanType", "888849000005"); q.click("#scanGo"); scan_card(q)
    q.click("#scanFill"); q.wait_for_timeout(300)
    check("barcodes: on the Pantry tab a scan fills in the form from its label",
          q.input_value("#panName")=="Quest Cookies & Cream Protein Bar" and q.input_value("#panCal")=="190"
          and q.input_value("#panPro")=="21" and q.input_value("#panUnit")=="bar", "%s / %s / %s / %s" % (
          q.input_value("#panName"), q.input_value("#panCal"), q.input_value("#panPro"), q.input_value("#panUnit")))
    q.click("#panNewClose"); q.wait_for_timeout(200)
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(200)
    check("barcodes: leaving the tab stops the camera and closes the sheet", q.locator("#scanSheet").count()==0)
    # Grocery brands are what a barcode is found in; Settings can take them off.
    q.click("#setBtn"); q.wait_for_timeout(300)
    sb=q.locator("#setBrands")
    check("brands: Settings says they are on the phone and offers to remove them",
          "are on this phone" in q.inner_text("#setLibHint") and sb.inner_text().upper()=="REMOVE GROCERY BRANDS" and sb.bounding_box()["height"]>=MIN_TAP,
          "%s / %s" % (q.inner_text("#setLibHint"), sb.inner_text()))
    sb.click(); q.wait_for_timeout(300)
    check("brands: removing them says so, and offers the download again",
          q.evaluate(LBST).get("brandsOn") is False and sb.inner_text().upper()=="DOWNLOAD GROCERY BRANDS · 9 MB"
          and "removed" in q.inner_text(".undobar"), "%s / %s" % (sb.inner_text(), q.inner_text(".undobar")))
    q.click("#setDone"); q.wait_for_timeout(200)
    c.close()

    # ---------- CARBS & FAT ----------
    # Off until chosen in Settings. Shown, the day adds them up wherever the
    # food's numbers carry them, and says how many foods it could not count —
    # never a zero standing in for a number nobody knows.
    c, q = fresh(LBSTORE, "carbs")
    check("carbs: off by default, nothing changes", q.locator(".cf-line").count()==0)
    q.click("#setBtn"); q.wait_for_timeout(300)
    q.click('[data-pick-cf="on"]'); q.wait_for_timeout(200)
    check("carbs: switched on in Settings", q.evaluate(LBST).get("cfOn") is True)
    hint=q.inner_text("#setCfHint") if q.locator("#setCfHint").count() else ""
    check("carbs: Settings says where they show, and that a target fills the kettlebells",
          "On Macros" in hint and "target" in hint, hint)
    q.click("#setDone"); q.wait_for_timeout(200)
    estimate("chicken breast", "")
    rv=q.inner_text(".rev-item .rev-cf") if q.locator(".rev-item .rev-cf").count() else ""
    check("carbs: the review shows them for a table food", rv.endswith("g fat") and "carbs" in rv, rv)
    q.fill('[data-ig="0"]', "340"); q.wait_for_timeout(150)
    rv2=q.inner_text(".rev-item .rev-cf")
    check("carbs: and changing the weight changes them with it", rv2!=rv and "g fat" in rv2, "%s -> %s" % (rv, rv2))
    q.click("#commitEst"); q.wait_for_timeout(300)
    way(q, "numbers")
    check("carbs: the numbers form asks for them, optionally", q.locator("#fCarb").count()==1 and q.locator("#fFat").count()==1)
    q.fill("#fCal","300"); q.fill("#fPro","20"); q.click("#addFood"); q.wait_for_timeout(300)
    line=q.inner_text(".cf-line")
    check("carbs: the day's line counts what it knows and names what it doesn't",
          line.startswith("Carbs") and "1 food without them" in line, line)
    ok_, det = sizes_ok(q, "#wayNumbers")
    check("carbs: the extra fields are proper targets that will not zoom", ok_, det)
    # The owner's video (b67): carbs and fat typed with the setting on but no
    # target, and no kettlebell at all, which read as a screen that had not
    # caught up. The card shows the day's carbs and fat and goes to the target.
    way(q, "numbers")
    q.fill("#fCal","500"); q.fill("#fPro","50"); q.fill("#fCarb","60"); q.fill("#fFat","50")
    q.click("#addFood"); q.wait_for_timeout(300)
    cfb=q.eval_on_selector_all(".cf-line b","e=>e.map(x=>x.textContent)")
    ks=q.inner_text("#kbSetGoal") if q.locator("#kbSetGoal").count() else ""
    check("carbs: with no target, the card under the bar still shows the day's carbs and fat",
          len(cfb)==2 and ("%s g · %s g" % (cfb[0], cfb[1])) in ks and "No target yet" in ks, "%s / %r" % (cfb, ks))
    ok_, det = sizes_ok(q, ".kbs")
    check("carbs: and it is a proper target", ok_, det)
    if q.locator("#kbSetGoal").count(): q.click("#kbSetGoal")
    else: q.click("#openGoal")
    q.wait_for_timeout(300)
    check("carbs: a tap on it opens the target, at carbs",
          q.evaluate("()=>document.activeElement && document.activeElement.id")=="gCarb")
    q.fill("#gCarb","200"); q.fill("#gFat","70"); q.click("#saveGoal"); q.wait_for_timeout(300)
    kv=q.eval_on_selector_all(".kb .kb-v","e=>e.map(x=>x.textContent)")
    check("carbs: with targets set, the kettlebells take its place at once",
          q.locator("#kbSetGoal").count()==0 and len(kv)==2 and kv[0].endswith("/200 g") and kv[1].endswith("/70 g"), str(kv))
    c.close()

    # ---------- WATER ----------
    WSTORE=dict(LBSTORE, waterOn=True)
    c, q = fresh(WSTORE, "water")
    q.click("#waterMore"); q.click("#waterMore"); q.wait_for_timeout(150)
    check("water: each tap adds a glass, said on the line", q.inner_text("#waterVal")=="16 of 64 oz", q.inner_text("#waterVal"))
    check("water: kept in the day", abs(q.evaluate(LBST)["days"][Ts]["water"] - 2*8*29.5735) < 1)
    q.click("#waterLess"); q.wait_for_timeout(100)
    check("water: minus takes one back", q.inner_text("#waterVal")=="8 of 64 oz", q.inner_text("#waterVal"))
    for _ in range(7): q.click("#waterMore")
    q.wait_for_timeout(150)
    check("water: the goal met turns the line green", "done" in q.inner_text("#waterVal") and "is-met" in q.get_attribute("#waterVal","class"))
    ok_, det = sizes_ok(q, "#waterRow")
    check("water: both buttons are proper targets", ok_, det)
    q.click("#setBtn"); q.wait_for_timeout(300)
    q.click('[data-pick-wunit="ml"]'); q.wait_for_timeout(200)
    q.click("#setDone"); q.wait_for_timeout(200)
    check("water: switching to ml converts the day rather than re-reading it", q.inner_text("#waterVal").startswith("1,890 of 1,890 ml"), q.inner_text("#waterVal"))
    c.close()
    # The owner's video (b67): water switched on from the Pantry, and nothing
    # turned up on the screen behind Settings. Settings and the bar say where.
    c, q = fresh(LBSTORE, "water-where")
    q.click('.tabs button[data-tab="pantry"]'); q.wait_for_timeout(300)
    q.click("#setBtn"); q.wait_for_timeout(300)
    q.click('[data-pick-water="on"]'); q.wait_for_timeout(200)
    hint=q.inner_text("#setWaterHint") if q.locator("#setWaterHint").count() else ""
    check("water: switched on away from Macros, Settings says where it is", "On Macros" in hint, hint)
    q.click("#setDone"); q.wait_for_timeout(200)
    check("water: and the bar says so once Settings closes",
          q.is_visible(".undobar") and "Water is on Macros" in q.inner_text(".undobar"), q.inner_text(".undobar"))
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    check("water: where it said", q.locator("#waterRow").count()==1)
    c.close()

    # ---------- LOG: OPEN THIS DAY, AND BACK ----------
    # The owner's video (b67): a day opened from the year's small months, and
    # back on the Log the big month was that day's empty one — the month full
    # of history gone to a small square, back only once another day was opened.
    other = (T.replace(day=1) - datetime.timedelta(days=1)).replace(day=1) if T.month > 1 else T.replace(month=2, day=1)
    c, q = fresh(LBSTORE, "log-back")
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    big0 = q.inner_text(".month.is-big h4")
    q.click('.month.is-mini [data-go="%s"]' % other.isoformat()); q.wait_for_timeout(300)
    q.click("#peekOpen"); q.wait_for_timeout(400)
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    check("log: back from a day it opened, the Log is on the month it was left on",
          q.inner_text(".month.is-big h4")==big0, "%s -> %s" % (big0, q.inner_text(".month.is-big h4")))
    q.click('.tabs button[data-tab="gym"]'); q.wait_for_timeout(300)
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    check("log: and stays there by way of another tab", q.inner_text(".month.is-big h4")==big0, q.inner_text(".month.is-big h4"))
    q.click('.tabs button[data-tab="macros"]'); q.wait_for_timeout(300)
    q.click("#nextDay"); q.wait_for_timeout(300)
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    want = "%s %d" % (calendar.month_name[other.month], other.year)
    check("log: a day moved to elsewhere is still the month it opens on",
          q.inner_text(".month.is-big h4")==want, "%s, wanted %s" % (q.inner_text(".month.is-big h4"), want))
    c.close()

    # ---------- BODY WEIGHT ----------
    BW = {}
    for i, w in enumerate([186.2, 185.4, 186.0, 185.1, 184.6, 184.2, 183.8, 183.5]):
        BW[(T - datetime.timedelta(days=(8 - i) * 4)).isoformat()] = {"food": [], "updated": 1, "bw": w}
    c, q = fresh(dict(LBSTORE, days=BW), "weight")
    q.click('.tabs button[data-tab="log"]'); q.wait_for_timeout(400)
    card=q.inner_text("#bwCard")
    check("weight: the Log tab shows the latest weigh-in and the trend", "183.5" in card and "Trend" in card and q.locator("#bwCard svg circle").count()==8, card.replace("\n"," | ")[:160])
    q.fill("#bwIn","182.9"); q.click("#bwSave"); q.wait_for_timeout(300)
    check("weight: logging today says so, with undo", "Logged 182.9 lb for today" in q.inner_text(".undobar") and q.evaluate(LBST)["days"][Ts]["bw"]==182.9)
    q.click(".undobar button"); q.wait_for_timeout(300)
    check("weight: undo takes it back", "bw" not in q.evaluate(LBST)["days"].get(Ts, {}))
    q.click('[data-bwunit="kg"]'); q.wait_for_timeout(300)
    check("weight: kilograms convert what is there", "83.2" in q.inner_text("#bwCard"), q.inner_text(".bw-now"))
    ok_, det = sizes_ok(q, "#bwCard")
    check("weight: every control clears 44px and the field will not zoom", ok_, det)
    q.set_viewport_size({"width":320,"height":640}); q.wait_for_timeout(200)
    check("weight: the card fits a 320px phone", q.evaluate("()=>document.documentElement.scrollWidth")<=320)
    c.close()

    # ---------- THE GOAL CALCULATOR ----------
    c, q = fresh(dict(LBSTORE, days={Ts: {"food": [], "updated": 1, "bw": 182.0}}), "calc")
    q.click("#openGoal"); q.wait_for_timeout(200)
    q.click("#gcOpen"); q.wait_for_timeout(200)
    check("calc: the weight comes from the latest weigh-in", q.input_value("#gcWt")=="182.0", q.input_value("#gcWt"))
    check("calc: with nothing filled in it says what it needs, and Use waits",
          "Fill these in" in q.inner_text("#gcOut") and q.is_disabled("#gcUse"))
    q.click('[data-gcsex="m"]'); q.fill("#gcAge","29"); q.fill("#gcFt","5"); q.fill("#gcIn","11"); q.wait_for_timeout(100)
    out=q.inner_text("#gcOut")
    # Mifflin-St Jeor: 10*82.55 + 6.25*180.34 - 5*29 + 5 = 1812; x1.55 = 2809; -500 -> 2310; 182 lb -> 180 g
    check("calc: the working is shown, from the standard equation", "2,810 kcal a day" in out and "2,310 kcal" in out and "180 g protein" in out, out)
    q.click("#gcUse"); q.wait_for_timeout(200)
    check("calc: Use fills the target, and Save still decides", q.input_value("#gCal")=="2310" and q.input_value("#gPro")=="180"
          and q.evaluate(LBST)["goal"]["cal"]["v"]==2000)
    q.select_option("#gcAim","250"); q.wait_for_timeout(100); q.click("#gcUse"); q.wait_for_timeout(100)
    check("calc: gaining sets calories to reach at least the number",
          q.get_attribute('#dirCal [data-d="+"]',"aria-pressed")=="true", q.inner_text("#gcOut"))
    ok_, det = sizes_ok(q, "#goalCalc")
    check("calc: every control clears 44px and nothing will zoom", ok_, det)
    q.click("#saveGoal"); q.wait_for_timeout(200)
    check("calc: and Save target keeps it", q.evaluate(LBST)["goal"]["cal"]=={"dir":"+","v":3060}, str(q.evaluate(LBST)["goal"]))
    c.close()

    # A heredoc once turned \b into backspace characters inside the app's own
    # source — invisible, harmless that time, and found only by accident.
    src=io.open("mntl-dt.html", encoding="utf-8").read()
    ctl=[i for i,ch in enumerate(src) if ord(ch)<32 and ch not in "\n\r\t"]
    check("source: no control characters hiding in the app (checked in the source)", not ctl, str(ctl[:5]))
    # tools/make-fonts.py writes fonts/fonts.css and prints the same block for
    # the top of the app. Two copies drift; this is where they would be caught.
    ff=[l.strip() for l in io.open("fonts/fonts.css", encoding="utf-8").read().splitlines() if l.strip()]
    inapp=[l.strip() for l in src.splitlines() if l.strip().startswith("@font-face")]
    check("source: the app's @font-face block is fonts/fonts.css, word for word (checked in the source)",
          ff and inapp==ff, "%d in fonts.css, %d in the app" % (len(ff), len(inapp)))

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
