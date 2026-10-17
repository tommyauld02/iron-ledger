from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
def fresh():
    return {"days":{T:{"food":[
      {"id":"r1","cal":205,"pro":4,"note":"White rice"},
      {"id":"r2","cal":489,"pro":57,"note":"Top sirloin"},
      {"id":"r3","cal":190,"pro":21,"note":"Protein bar"}],
      "lifts":[],"updated":1,"goal":G}},
     "moves":None,"goal":G,"region":"United States","pantry":[],"v":1}
res=[]
def check(n, ok, dt=""): res.append((("PASS" if ok else "FAIL"), n, dt))

def hold_drag(p, src, dst):
    """press and hold on src, then move onto dst and release"""
    a=p.locator('[data-row="%s"]'%src).bounding_box()
    b=p.locator('[data-row="%s"]'%dst).bounding_box()
    p.mouse.move(a["x"]+30, a["y"]+a["height"]/2)
    p.mouse.down()
    p.wait_for_timeout(500)                       # outlast the hold timer
    p.mouse.move(b["x"]+30, b["y"]+b["height"]/2, steps=8)
    p.wait_for_timeout(120)
    p.mouse.up()
    p.wait_for_timeout(450)

def store_of(p): return p.evaluate("()=>JSON.parse(localStorage['iron-ledger-v1'])")

def open_meal(p):
    """expand the meal only if it isn't already open — it stays open while you edit it"""
    if p.locator(".meal-body").count()==0:
        p.click(".meal-open"); p.wait_for_timeout(400)

with sync_playwright() as pw:
    b=pw.chromium.launch()
    ctx=b.new_context(viewport={"width":393,"height":900}, has_touch=True, is_mobile=True)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    # Naming happens in a field now, not a system dialog. Anything that opens
    # one is a regression, so record it and assert none fired.
    dialogs=[]
    p.on("dialog", lambda dl: (dialogs.append(dl.type), dl.dismiss()))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)

    def reset():
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fresh())
        p.reload(); p.wait_for_timeout(800)

    reset()
    before=p.text_content(".t-total .t-cal b")
    check("hint shown before any meal exists", p.locator(".drag-hint").count()==1)

    # ---- a plain quick tap must NOT combine ----
    a=p.locator('[data-row="r1"]').bounding_box()
    bb=p.locator('[data-row="r2"]').bounding_box()
    p.mouse.move(a["x"]+30, a["y"]+a["height"]/2); p.mouse.down()
    p.mouse.move(bb["x"]+30, bb["y"]+bb["height"]/2, steps=5); p.mouse.up(); p.wait_for_timeout(300)
    check("a quick drag does nothing (that's a scroll)", p.locator(".t-row").count()==3,
          str(p.locator(".t-row").count())+" rows")

    # ---- hold and drag combines ----
    hold_drag(p, "r1", "r2")
    check("hold + drag makes a meal", p.locator(".t-row.is-meal").count()==1)
    check("two rows became one", p.locator(".t-row").count()==2,
          str(p.locator(".t-row").count())+" rows")
    check("day total is unchanged by combining",
          p.text_content(".t-total .t-cal b")==before,
          before+" -> "+p.text_content(".t-total .t-cal b"))
    check("meal shows the summed numbers",
          p.text_content(".t-row.is-meal .t-cal b")=="694",
          p.text_content(".t-row.is-meal .t-cal b"))
    check("meal is auto-named from what's in it",
          "Top sirloin" in p.text_content(".meal-open .mn") and
          "White rice" in p.text_content(".meal-open .mn"),
          p.text_content(".meal-open .mn"))
    check("hint gone once a meal exists", p.locator(".drag-hint").count()==0)
    check("combine offers undo", p.locator("#undobar").is_visible())

    # ---- undo puts them back ----
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("undo restores both rows", p.locator(".t-row").count()==3)
    check("undo restores their order",
          p.eval_on_selector_all(".t-row .nm","e=>e.map(x=>x.textContent.trim())")==
          ["White rice","Top sirloin","Protein bar"],
          str(p.eval_on_selector_all(".t-row .nm","e=>e.map(x=>x.textContent.trim())")))

    # ---- open, split ----
    hold_drag(p, "r1", "r2")
    open_meal(p)
    check("meal opens on tap", p.locator(".meal-body").count()==1)
    check("meal lists what's inside", p.locator(".meal-item").count()==2)
    p.click("[data-split]"); p.wait_for_timeout(400)
    check("split apart", p.locator(".t-row").count()==3 and p.locator(".t-row.is-meal").count()==0)
    check("split keeps them in place",
          p.eval_on_selector_all(".t-row .nm","e=>e.map(x=>x.textContent.trim())")==
          ["Top sirloin","White rice","Protein bar"],
          str(p.eval_on_selector_all(".t-row .nm","e=>e.map(x=>x.textContent.trim())")))
    check("split offers undo", p.locator("#undobar").is_visible())
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("undo split rebuilds the meal", p.locator(".t-row.is-meal").count()==1)

    # ---- drag a third row into the existing meal ----
    reset(); hold_drag(p, "r1", "r2")
    mid=p.get_attribute(".t-row.is-meal","data-row")
    hold_drag(p, "r3", mid)
    check("dragging onto a meal adds to it", p.locator(".t-row").count()==1)
    check("meal now holds three", p.text_content(".meal-open .mc").startswith("3 items"),
          p.text_content(".meal-open .mc"))
    check("nothing nested: items are flat",
          p.evaluate("()=>JSON.parse(localStorage['iron-ledger-v1']).days['%s'].food[0].items.every(x=>!x.items)"%T))
    check("day total still right", p.text_content(".t-total .t-cal b")=="884",
          p.text_content(".t-total .t-cal b"))

    # ---- take one back out ----
    open_meal(p)
    p.locator("[data-takeout]").first.click(); p.wait_for_timeout(400)
    check("take out returns it to the list", p.locator(".t-row").count()==2)
    check("meal keeps the other two", p.text_content(".t-row.is-meal .meal-open .mc").startswith("2 items"),
          p.text_content(".t-row.is-meal .meal-open .mc"))
    check("take out offers undo", p.locator("#undobar").is_visible())
    check("day total unchanged by taking out", p.text_content(".t-total .t-cal b")=="884",
          p.text_content(".t-total .t-cal b"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("undo take out", p.locator(".t-row").count()==1)

    # ---- taking out until one is left dissolves the meal ----
    open_meal(p)
    p.locator("[data-takeout]").first.click(); p.wait_for_timeout(400)
    p.evaluate("()=>document.getElementById('undobar').hidden=true")
    check("the meal stays open while you edit it", p.locator(".meal-body").count()==1)
    open_meal(p)
    p.locator("[data-takeout]").first.click(); p.wait_for_timeout(400)
    check("a meal of one dissolves back into plain rows",
          p.locator(".t-row").count()==3 and p.locator(".t-row.is-meal").count()==0,
          str(p.locator(".t-row").count())+" rows, "+str(p.locator(".t-row.is-meal").count())+" meals")

    # ---- naming ----
    reset(); hold_drag(p, "r1", "r2")
    open_meal(p)
    p.click("[data-renamemeal]"); p.wait_for_timeout(400)
    check("naming a meal opens a field, not a dialog",
          p.evaluate("()=>!!document.getElementById('mealName')"))
    mb=p.locator("#mealName").bounding_box()
    check("the name field is a proper target", mb and mb["height"]>=44,
          mb and "%dx%d"%(mb["width"],mb["height"]))
    p.fill("#mealName","Dinner"); p.click("#mealNameSave"); p.wait_for_timeout(450)
    check("meal can be named", p.text_content(".meal-open .mn")=="Dinner",
          p.text_content(".meal-open .mn"))

    # ---- persistence and deletion ----
    p.reload(); p.wait_for_timeout(800)
    check("meal survives a reload", p.locator(".t-row.is-meal").count()==1)
    check("named meal survives", p.text_content(".meal-open .mn")=="Dinner")
    p.locator(".t-row.is-meal .t-del").click(); p.wait_for_timeout(400)
    check("deleting a meal removes the whole thing", p.locator(".t-row").count()==1)
    check("deleting a meal offers undo", p.locator("#undobar").is_visible())
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("undo brings the meal back whole",
          p.locator(".t-row.is-meal").count()==1 and p.text_content(".meal-open .mn")=="Dinner")

    # ---- a pending entry inside a meal still blocks the verdict ----
    p.evaluate("""s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))""",
      {"days":{T:{"food":[{"id":"m1","items":[
          {"id":"i1","cal":200,"pro":20,"note":"Rice"},
          {"id":"i2","cal":0,"pro":0,"note":"Mystery sauce","pending":True}]}],
        "lifts":[],"updated":1,"goal":G}},
       "moves":None,"goal":G,"region":"United States","pantry":[],"v":1})
    p.reload(); p.wait_for_timeout(800)
    txt=p.locator("#view").inner_text()
    check("a pending item inside a meal is still counted",
          "waiting on an estimate" in txt, [l for l in txt.split("\n") if "waiting" in l][:1])
    p.click('[data-tab="log"]'); p.wait_for_timeout(600)
    cls=p.get_attribute('[data-go="%s"]'%T, "class")
    check("day stays uncoloured while a meal item is pending",
          "hit" not in cls and "miss" not in cls, cls)

    # ---- resolving a placeholder that lives inside a meal ----
    p.click('[data-tab="macros"]'); p.wait_for_timeout(400)
    open_meal(p)
    before_rows=p.locator(".t-row").count()
    p.locator("[data-est]").first.click(); p.wait_for_timeout(500)
    st=store_of(p)["days"][T]["food"]
    check("an unresolvable placeholder is never silently thrown away",
          len(st)==1 and [x.get("note") for x in st[0]["items"]]==["Rice","Mystery sauce"],
          str([x.get("note") for x in st[0]["items"]]))
    check("it opens the review so you can type the numbers there",
          p.locator(".review").count()==1 and p.locator(".rev-item").count()==1,
          "%d review, %d items"%(p.locator(".review").count(), p.locator(".rev-item").count()))
    check("the review still names what it couldn't price",
          "Mystery sauce" in p.locator(".review").inner_text(),
          p.locator(".review").inner_text()[:60].replace("\n"," "))
    check("no double count", p.text_content(".t-total .t-cal b")=="200",
          p.text_content(".t-total .t-cal b"))

    # ---- correcting a row after it went in ----
    # The owner logged "Pure protein bar" meaning "Built Protein bar", and the
    # only way to fix it was to delete it and start again.
    def row_of(rid):
        return [f for f in store_of(p)["days"][T]["food"] if f["id"]==rid][0]
    fx=fresh(); fx["days"][T]["food"][2]={"id":"r3","cal":190,"pro":21,"note":"Pure protein bar · 1 bar",
                                          "est":True,"carb":17,"fat":7}
    fx["days"][T]["food"].append({"id":"r4","cal":0,"pro":0,"note":"Mystery sauce","pending":True})
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fx)
    p.reload(); p.wait_for_timeout(800)
    nb=p.locator('[data-editrow="r3"]').bounding_box()
    check("edit: a food's name is the way in, a proper target", nb and nb["height"]>=44,
          nb and "%dx%d"%(nb["width"],nb["height"]))
    check("edit: and it says so, in teal", p.text_content('[data-editrow="r3"] .ed').strip().lower()=="edit")
    p.click('[data-editrow="r3"]'); p.wait_for_timeout(400)
    check("edit: tapping it opens the row's own values, not a dialog",
          p.input_value("#reName")=="Pure protein bar · 1 bar" and p.input_value("#reCal")=="190"
          and p.input_value("#rePro")=="21",
          "%s / %s / %s"%(p.input_value("#reName"), p.input_value("#reCal"), p.input_value("#rePro")))
    check("edit: the cursor is in the name, after it",
          p.evaluate("()=>document.activeElement.id==='reName' && document.activeElement.selectionStart===document.activeElement.value.length"))
    small=p.evaluate("""()=>[...document.querySelectorAll('.row-edit input, .row-edit button')]
        .map(e=>[e.id||e.textContent.trim(), e.getBoundingClientRect().height]).filter(x=>x[1]<44)""")
    check("edit: every field and button in the box is 44px or more", not small, str(small))

    p.fill("#reName","Built Protein bar · 1 bar"); p.click("#reSave"); p.wait_for_timeout(400)
    r=row_of("r3")
    check("edit: a new name is saved, and the box closes",
          r["note"]=="Built Protein bar · 1 bar" and p.locator(".row-edit").count()==0, str(r))
    check("edit: a rename leaves the numbers, the estimate mark, carbs and fat as they were",
          r["cal"]==190 and r["pro"]==21 and r.get("est") is True and r.get("carb")==17 and r.get("fat")==7, str(r))
    check("edit: and says what it did, with undo",
          p.locator("#undobar").is_visible() and "Renamed to Built Protein bar" in p.text_content("#undoLabel"),
          p.text_content("#undoLabel"))
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("edit: undo puts the old name back", row_of("r3")["note"]=="Pure protein bar · 1 bar", str(row_of("r3")))

    p.click('[data-editrow="r3"]'); p.wait_for_timeout(400)
    p.fill("#reName","Built Protein bar"); p.fill("#reCal","130"); p.fill("#rePro","17")
    p.press("#rePro","Enter"); p.wait_for_timeout(400)
    r=row_of("r3")
    check("edit: Enter saves new numbers, and the day total follows",
          r["cal"]==130 and r["pro"]==17 and p.text_content(".t-total .t-cal b")=="824",
          "%s · total %s"%(r, p.text_content(".t-total .t-cal b")))
    check("edit: typed-over numbers are yours, not an estimate, and hidden carbs and fat go with them",
          "est" not in r and "carb" not in r and "fat" not in r, str(r))
    check("edit: it says it updated", "Updated Built Protein bar" in p.text_content("#undoLabel"),
          p.text_content("#undoLabel"))

    p.click('[data-editrow="r3"]'); p.wait_for_timeout(400)
    p.fill("#reName","Nothing"); p.fill("#reCal",""); p.fill("#rePro","0"); p.click("#reSave"); p.wait_for_timeout(300)
    check("edit: no calories and no protein is refused out loud, keeping what was typed",
          p.locator(".re-hint").is_visible() and row_of("r3")["cal"]==130 and p.input_value("#reName")=="Nothing",
          p.locator(".re-hint").inner_text() if p.locator(".re-hint").count() else "no hint")
    p.click("#reCancel"); p.wait_for_timeout(300)
    check("edit: Cancel closes it and changes nothing",
          p.locator(".row-edit").count()==0 and row_of("r3")["note"]=="Built Protein bar")

    p.click('[data-editrow="r4"]'); p.wait_for_timeout(400)
    p.fill("#reName","Sriracha mayo"); p.click("#reSave"); p.wait_for_timeout(400)
    r=row_of("r4")
    check("edit: a waiting row can have its name fixed and keep waiting",
          r["note"]=="Sriracha mayo" and r.get("pending") is True and p.locator('[data-est="r4"]').count()==1, str(r))

    a=p.locator('[data-editrow="r1"]').bounding_box()
    p.mouse.move(a["x"]+30, a["y"]+a["height"]/2); p.mouse.down(); p.wait_for_timeout(500)
    p.mouse.up(); p.wait_for_timeout(400)
    check("edit: holding a name to drag it doesn't open the box when let go",
          p.locator(".row-edit").count()==0 and p.locator(".t-row").count()==4)
    hold_drag(p, "r1", "r2")
    check("edit: and a row is still dragged by its name",
          p.locator(".t-row.is-meal").count()==1, str(p.locator(".t-row").count())+" rows")
    check("edit: a meal is named its own way, not by this box", p.locator('.t-row.is-meal [data-editrow]').count()==0)

    print()
    for st,n,dt in res: print("%-6s %-52s %s"%(st,n,dt))
    print("\n%d passed, %d FAILED"%(sum(1 for r in res if r[0]=="PASS"),
                                    sum(1 for r in res if r[0]=="FAIL")))
    check("no system dialogs anywhere", not dialogs, str(dialogs))
    print("pageerrors:", errs or "none")
    b.close()

    # A suite that prints FAIL and exits 0 cannot gate anything — verify.sh
    # says ALL SUITES PASSED and CI deploys anyway. Page errors count too: a
    # thrown exception is what leaves the buttons after it dead and silent.
    _bad = sum(1 for r in res if r[0] == "FAIL")
    raise SystemExit(1 if (_bad or errs) else 0)
