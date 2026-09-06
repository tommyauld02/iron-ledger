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

with sync_playwright() as pw:
    b=pw.chromium.launch()
    # a real phone: touch only, no mouse
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True,
                      device_scale_factor=3)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    cdp=ctx.new_cdp_session(p)

    def touch(kind, x=None, y=None):
        pts=[{"x":x,"y":y}] if x is not None else []
        cdp.send("Input.dispatchTouchEvent", {"type":kind, "touchPoints":pts})
    def finger_drag(src, dst, hold=520):
        a=p.locator('[data-row="%s"]'%src).bounding_box()
        z=p.locator('[data-row="%s"]'%dst).bounding_box()
        x0,y0 = a["x"]+40, a["y"]+a["height"]/2
        x1,y1 = z["x"]+40, z["y"]+z["height"]/2
        touch("touchStart", x0, y0)
        p.wait_for_timeout(hold)                      # hold still
        for i in range(1,9):
            touch("touchMove", x0+(x1-x0)*i/8, y0+(y1-y0)*i/8)
            p.wait_for_timeout(35)
        p.wait_for_timeout(80)
        touch("touchEnd")
        p.wait_for_timeout(450)
    def finger_swipe(src, dy=-260):
        a=p.locator('[data-row="%s"]'%src).bounding_box()
        x0,y0 = a["x"]+40, a["y"]+a["height"]/2
        touch("touchStart", x0, y0)
        for i in range(1,9):
            touch("touchMove", x0, y0+dy*i/8)
            p.wait_for_timeout(20)
        touch("touchEnd")
        p.wait_for_timeout(350)

    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(250)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fresh())
    p.reload(); p.wait_for_timeout(800)

    check("touch device detected as coarse pointer",
          p.evaluate("()=>matchMedia('(pointer: coarse)').matches"))
    check("no field small enough to make iOS zoom",
          p.evaluate("""()=>[...document.querySelectorAll('input,select,textarea')]
            .filter(e=>e.getBoundingClientRect().width)
            .every(e=>parseFloat(getComputedStyle(e).fontSize)>=16)"""))

    # ---- a swipe must scroll, not pick a row up ----
    finger_swipe("r1")
    check("a finger swipe scrolls instead of dragging",
          p.locator(".t-row").count()==3 and p.locator(".drag-ghost").count()==0,
          "%d rows"%p.locator(".t-row").count())
    p.evaluate("()=>window.scrollTo(0,0)"); p.wait_for_timeout(300)

    # ---- hold and drag with a finger ----
    finger_drag("r1","r2")
    check("press-and-hold + finger drag combines", p.locator(".t-row.is-meal").count()==1,
          "%d rows, %d meals"%(p.locator(".t-row").count(), p.locator(".t-row.is-meal").count()))
    check("the ghost is cleaned up", p.locator(".drag-ghost").count()==0)
    check("nothing left highlighted", p.locator(".t-row.dropto").count()==0)
    check("nothing left lifted", p.locator(".t-row.lifted").count()==0)
    check("day total survived the finger drag", p.text_content(".t-total .t-cal b")=="884",
          p.text_content(".t-total .t-cal b"))

    # ---- tapping the meal open with a finger ----
    box=p.locator(".meal-open").bounding_box()
    p.touchscreen.tap(box["x"]+box["width"]/2, box["y"]+box["height"]/2)
    p.wait_for_timeout(450)
    check("tap opens the meal on touch", p.locator(".meal-body").count()==1)
    ob=p.locator("[data-takeout]").first.bounding_box()
    p.touchscreen.tap(ob["x"]+ob["width"]/2, ob["y"]+ob["height"]/2); p.wait_for_timeout(450)
    check("Take out works on touch", p.locator(".t-row").count()==3,
          "%d rows"%p.locator(".t-row").count())
    ub=p.locator("#undoBtn").bounding_box()
    p.touchscreen.tap(ub["x"]+ub["width"]/2, ub["y"]+ub["height"]/2); p.wait_for_timeout(450)
    check("Undo works on touch", p.locator(".t-row").count()==2)

    # ---- a drag released over nothing must not combine ----
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fresh())
    p.reload(); p.wait_for_timeout(800)
    a=p.locator('[data-row="r1"]').bounding_box()
    touch("touchStart", a["x"]+40, a["y"]+a["height"]/2)
    p.wait_for_timeout(520)
    touch("touchMove", a["x"]+40, 40)      # up into the header, not a row
    p.wait_for_timeout(120)
    touch("touchEnd"); p.wait_for_timeout(450)
    check("releasing over nothing changes nothing", p.locator(".t-row").count()==3)
    check("and leaves nothing lifted", p.locator(".t-row.lifted").count()==0
          and p.locator(".drag-ghost").count()==0)

    # ---- an interrupted drag (call, notification) must not strand the row ----
    touch("touchStart", a["x"]+40, a["y"]+a["height"]/2)
    p.wait_for_timeout(520)
    touch("touchMove", a["x"]+60, a["y"]+a["height"]/2+30)
    p.wait_for_timeout(80)
    cdp.send("Input.dispatchTouchEvent", {"type":"touchCancel","touchPoints":[]})
    p.wait_for_timeout(400)
    check("an interrupted drag cleans up after itself",
          p.locator(".drag-ghost").count()==0 and p.locator(".t-row.lifted").count()==0
          and p.locator(".t-row").count()==3)

    # ---- every tab reachable by finger, and the whole tab bar is 48px ----
    for t in ["pantry","gym","coach","log","macros"]:
        tb=p.locator('.tabs button[data-tab="%s"]'%t).bounding_box()
        p.touchscreen.tap(tb["x"]+tb["width"]/2, tb["y"]+tb["height"]/2); p.wait_for_timeout(400)
        check("tab %s opens on tap"%t,
              p.get_attribute('.tabs button[data-tab="%s"]'%t,"aria-selected")=="true")
    check("tab bar is at least 48px tall",
          p.evaluate("""()=>[...document.querySelectorAll('.tabs button')]
            .every(b=>b.getBoundingClientRect().height>=48)"""),
          str(round(p.locator('.tabs button').first.bounding_box()["height"])))

    # ---- logging a set with a finger, the thing he'll do most at the gym ----
    tb=p.locator('.tabs button[data-tab="gym"]').bounding_box()
    p.touchscreen.tap(tb["x"]+tb["width"]/2, tb["y"]+tb["height"]/2); p.wait_for_timeout(450)
    p.select_option("#mSel","Barbell Row")
    lb=p.locator("#addLift").bounding_box()
    p.touchscreen.tap(lb["x"]+lb["width"]/2, lb["y"]+lb["height"]/2); p.wait_for_timeout(450)
    p.fill("[data-w='0']","135"); p.fill("[data-r='0']","10")
    sb=p.locator("[data-addset='0']").bounding_box()
    check("the Set button is a proper target",
          sb["height"]>=44 and sb["width"]>=44, "%dx%d"%(sb["width"],sb["height"]))
    p.touchscreen.tap(sb["x"]+sb["width"]/2, sb["y"]+sb["height"]/2); p.wait_for_timeout(450)
    check("a set logs with a finger", p.locator(".set").count()==1,
          "%d sets"%p.locator(".set").count())

    # ---- home-screen metadata ----
    check("declares itself a home-screen app",
          p.evaluate("""()=>!!document.querySelector('meta[name="apple-mobile-web-app-capable"]')"""))
    check("names the icon Iron Ledger",
          p.get_attribute('meta[name="apple-mobile-web-app-title"]',"content")=="Iron Ledger")
    check("paints the status bar to match",
          p.evaluate("""()=>{const m=document.querySelector('meta[name=theme-color]');
            return m && /^#[0-9A-F]{6}$/i.test(m.content);}"""))
    check("rep counts aren't turned into phone links",
          p.get_attribute('meta[name="format-detection"]',"content")=="telephone=no")

    print()
    for st,n,dt in res: print("%-6s %-52s %s"%(st,n,dt))
    print("\n%d passed, %d FAILED"%(sum(1 for r in res if r[0]=="PASS"),
                                    sum(1 for r in res if r[0]=="FAIL")))
    print("pageerrors:", errs or "none")
    b.close()
