from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd(); T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
base={"days":{},"moves":None,"goal":G,"region":"United States","pantry":[],"v":1}
res=[]
def check(n, ok, dt=""): res.append((("PASS" if ok else "FAIL"), n, dt))

with sync_playwright() as pw:
    b=pw.chromium.launch()
    ctx=b.new_context(viewport={"width":393,"height":900}, has_touch=True, is_mobile=True)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)

    def reset():
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", base)
        p.reload(); p.wait_for_timeout(800)
    def estimate(text):
        p.fill("#estText", text)
        p.click("#runEst"); p.wait_for_timeout(700)
    def food(): return p.evaluate("()=>(JSON.parse(localStorage['iron-ledger-v1']).days['%s']||{}).food||[]"%T)

    reset()
    check("heading is 'Need help counting?'",
          "NEED HELP COUNTING" in p.locator("#view").inner_text().upper())
    check("textarea prompts 'What did you eat?'",
          p.get_attribute("#estText","placeholder")=="What did you eat?",
          p.get_attribute("#estText","placeholder"))

    # ---- multi-item estimate offers the toggle ----
    estimate("chicken and rice")
    check("review panel appeared", p.locator(".review").count()==1)
    check("two items resolved", p.locator(".rev-item").count()==2,
          str(p.locator(".rev-item").count()))
    check("one-meal toggle offered", p.locator("#estMeal").count()==1)
    check("toggle starts off", p.get_attribute("#estMeal","aria-pressed")=="false")
    check("button says items while off", "ITEM" in p.text_content("#commitEst").upper(),
          p.text_content("#commitEst"))

    # ---- toggle on ----
    p.click("#estMeal"); p.wait_for_timeout(300)
    check("toggle turns on", p.get_attribute("#estMeal","aria-pressed")=="true")
    check("toggle survives the re-render", p.locator("#estMeal").count()==1)
    check("button changes to one meal", p.text_content("#commitEst").strip()=="Add as one meal",
          p.text_content("#commitEst"))
    check("editing a number keeps the toggle on",
          (p.fill(".rev-item input","300") or p.wait_for_timeout(400) or
           p.get_attribute("#estMeal","aria-pressed"))=="true")

    p.click("#commitEst"); p.wait_for_timeout(500)
    f=food()
    check("committed as one row", len(f)==1, "%d rows"%len(f))
    check("that row is a meal", bool(f and f[0].get("items")))
    check("the meal holds both items", len(f[0]["items"])==2 if f and f[0].get("items") else False)
    check("meal is named from what you typed", f[0].get("note")=="chicken and rice",
          str(f[0].get("note")))
    check("one row on screen", p.locator(".t-row").count()==1)
    check("total is the sum", p.text_content(".t-total .t-cal b")=="505",
          p.text_content(".t-total .t-cal b"))

    # ---- toggle resets for the next estimate ----
    estimate("2 eggs")
    check("single-item estimate offers no toggle", p.locator("#estMeal").count()==0)
    p.click("#commitEst"); p.wait_for_timeout(500)
    f=food()
    check("single item goes in flat", len(f)==2 and not f[1].get("items"),
          "%d rows"%len(f))

    # ---- toggle off stays off ----
    estimate("chicken and rice")
    check("toggle reset to off for a new estimate",
          p.get_attribute("#estMeal","aria-pressed")=="false")
    p.click("#commitEst"); p.wait_for_timeout(500)
    f=food()
    check("with the toggle off they go in separately",
          len(f)==4 and not f[2].get("items") and not f[3].get("items"),
          "%d rows"%len(f))

    # ---- discard clears the toggle ----
    estimate("chicken and rice")
    p.click("#estMeal"); p.wait_for_timeout(300)
    p.click("#discardEst"); p.wait_for_timeout(400)
    estimate("chicken and rice")
    check("discard resets the toggle", p.get_attribute("#estMeal","aria-pressed")=="false")
    p.click("#discardEst"); p.wait_for_timeout(300)

    # ---- a long description falls back to the auto name ----
    reset()
    estimate("chicken and rice and a banana and some almonds and a protein shake after the gym")
    p.click("#estMeal"); p.wait_for_timeout(300)
    p.click("#commitEst"); p.wait_for_timeout(500)
    f=food()
    check("a too-long description doesn't become the meal name",
          f[0].get("note")=="", repr(f[0].get("note")))
    check("it auto-names from its contents instead",
          "+" in p.text_content(".meal-open .mn"), p.text_content(".meal-open .mn"))

    # ---- resolving a placeholder inside a meal never nests ----
    p.evaluate("""s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))""",
      {"days":{T:{"food":[{"id":"m1","note":"Dinner","items":[
          {"id":"i1","cal":200,"pro":20,"note":"Rice"},
          {"id":"i2","cal":0,"pro":0,"note":"chicken and rice","pending":True}]}],
        "lifts":[],"updated":1,"goal":G}},
       "moves":None,"goal":G,"region":"United States","pantry":[],"v":1})
    p.reload(); p.wait_for_timeout(800)
    p.click(".meal-open"); p.wait_for_timeout(400)
    p.locator("[data-est]").first.click(); p.wait_for_timeout(700)
    check("a placeholder inside a meal resolves offline, no Claude needed",
          p.locator(".review").count()==1, p.locator("#view").inner_text()[:80].replace("\n"," "))
    check("the one-meal toggle is offered there too", p.locator("#estMeal").count()==1)
    p.click("#estMeal"); p.wait_for_timeout(300)
    p.click("#commitEst"); p.wait_for_timeout(500)
    f=food()
    check("resolving inside a meal stays flat — no meal in a meal",
          len(f)==1 and len(f[0]["items"])==3 and all(not x.get("items") for x in f[0]["items"]),
          "%d items"%len(f[0].get("items",[])))
    check("the meal absorbed the answer in place",
          [x["note"] for x in f[0]["items"]][0]=="Rice",
          str([x["note"] for x in f[0]["items"]]))
    check("no 'items' when there is one", "1 items" not in p.locator("#view").inner_text())

    print()
    for st,n,dt in res: print("%-6s %-52s %s"%(st,n,dt))
    print("\n%d passed, %d FAILED"%(sum(1 for r in res if r[0]=="PASS"),
                                    sum(1 for r in res if r[0]=="FAIL")))
    print("pageerrors:", errs or "none")
    b.close()
