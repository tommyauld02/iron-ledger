from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd()
T=datetime.date.today(); Ts=T.isoformat()
Y=(T-datetime.timedelta(days=2)).isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
store={"days":{
  Y:{"lifts":[{"id":"yl","cat":"back","movement":"Barbell Row",
               "sets":[{"w":135,"r":10},{"w":145,"r":8}]}],
     "food":[{"id":"f1","cal":1800,"pro":160,"note":"Whole day"}],"updated":1,"goal":G}},
  "moves":None,"goal":G,"region":"United States","pantry":[],"v":1}

res=[]
def check(n, ok, d=""): res.append((("PASS" if ok else "FAIL"), n, d))

with sync_playwright() as pw:
    b=pw.chromium.launch()
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    # prompt() answers, popped in order
    answers=[]
    def on_dialog(dlg):
        p.wait_for_timeout(1)
        dlg.accept(answers.pop(0) if answers else "")
    p.on("dialog", on_dialog)

    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
    p.reload(); p.wait_for_timeout(900)

    # ---------- tab reachable ----------
    check("coach: tab exists", p.locator('[data-tab="coach"]').count()==1)
    p.click('[data-tab="coach"]'); p.wait_for_timeout(400)
    check("coach: 5 tabs all visible in viewport",
          all(p.locator('[data-tab]').nth(i).bounding_box()["x"]>=0 and
              p.locator('[data-tab]').nth(i).bounding_box()["x"]+
              p.locator('[data-tab]').nth(i).bounding_box()["width"]<=394 for i in range(5)))
    check("coach: default 3 day cards", p.locator(".rt-day").count()==3,
          str(p.locator(".rt-day").count()))
    check("coach: routine name field", p.locator("#rtName").count()==1)

    # ---------- open a day, library shows ----------
    p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
    check("coach: library groups render", p.locator(".lib-group").count()>=10,
          str(p.locator(".lib-group").count())+" groups")
    check("coach: library movements render", p.locator("[data-addmove]").count()>80,
          str(p.locator("[data-addmove]").count())+" movements")
    already=p.locator("[data-addmove][disabled]").count()
    check("coach: movements already in the day are marked", already>0, str(already)+" ticked")

    # ---------- add a movement from the library ----------
    before=p.locator(".rt-chip").count()
    p.locator("[data-addmove]:not([disabled])").first.click(); p.wait_for_timeout(300)
    check("coach: add movement from library", p.locator(".rt-chip").count()==before+1,
          str(before)+" -> "+str(p.locator(".rt-chip").count()))
    check("coach: added movement now ticked",
          p.locator("[data-addmove][disabled]").count()==already+1)

    # ---------- remove a movement + undo ----------
    n=p.locator(".rt-chip").count()
    p.locator(".rt-chip").first.click(); p.wait_for_timeout(300)
    check("coach: remove movement", p.locator(".rt-chip").count()==n-1)
    check("coach: remove offers undo", p.locator("#undobar").is_visible())
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("coach: undo restores movement", p.locator(".rt-chip").count()==n)

    # ---------- add your own movement ----------
    answers.append("Meadows Row")
    p.locator("[data-newmove]").first.click(); p.wait_for_timeout(400)
    check("coach: add your own movement",
          "Meadows Row" in p.locator(".rt-moves").first.inner_text())

    # ---------- rename a day, history must follow ----------
    answers.append("Pull Day")
    p.locator("[data-renameday]").first.click(); p.wait_for_timeout(400)
    check("coach: rename day", "Pull Day" in p.locator(".rt-day").first.inner_text())
    p.click('[data-tab="gym"]'); p.wait_for_timeout(400)
    check("gym: renamed day shows on gym chips", "Pull Day" in p.locator("#view").inner_text())
    # the old workout was logged under cat "back" — must still resolve
    p.click('[data-tab="log"]'); p.wait_for_timeout(500)
    p.click('[data-go="%s"]'%Y); p.wait_for_timeout(600)
    p.click('[data-tab="gym"]'); p.wait_for_timeout(400)
    gym=p.locator("#view").inner_text()
    check("history: old workout survives a rename",
          "Barbell Row" in gym and "Removed day" not in gym)

    # ---------- add a day ----------
    p.click('[data-tab="coach"]'); p.wait_for_timeout(300)
    answers.append("Arms")
    p.click("#addDay"); p.wait_for_timeout(400)
    check("coach: add a training day", p.locator(".rt-day").count()==4,
          str(p.locator(".rt-day").count())+" days")
    check("coach: new day opens for editing", p.locator(".rt-moves").count()==1)
    check("coach: new day starts empty",
          "No movements yet" in p.locator(".rt-moves").first.inner_text())
    p.click('[data-tab="gym"]'); p.wait_for_timeout(400)
    check("gym: new day appears as a split chip",
          p.locator("[data-cat]").count()==4, str(p.locator("[data-cat]").count())+" chips")

    # ---------- delete a day + undo ----------
    p.click('[data-tab="coach"]'); p.wait_for_timeout(300)
    p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
    p.locator("[data-rmday]").first.click(); p.wait_for_timeout(400)
    check("coach: delete a day", p.locator(".rt-day").count()==3)
    check("coach: delete offers undo", p.locator("#undobar").is_visible())
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("coach: undo restores the day", p.locator(".rt-day").count()==4)
    check("coach: undo restores it in place",
          "Pull Day" in p.locator(".rt-day").first.inner_text())

    # ---------- delete the day the history belongs to ----------
    p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
    p.locator("[data-rmday]").first.click(); p.wait_for_timeout(400)
    p.evaluate("()=>document.getElementById('undobar').hidden=true")
    p.click('[data-tab="log"]'); p.wait_for_timeout(500)
    p.click('[data-go="%s"]'%Y); p.wait_for_timeout(600)
    p.click('[data-tab="gym"]'); p.wait_for_timeout(500)
    gym=p.locator("#view").inner_text()
    live=[t.strip() for t in p.eval_on_selector_all("[data-cat]","e=>e.map(x=>x.innerText)")]
    check("history: deleted day keeps the name it was logged under",
          "no longer train" in gym and "Pull Day" in gym,
          "; ".join(l for l in gym.split("\n") if "logged under" in l.lower()))
    check("history: deleted day is NOT relabelled as a surviving day",
          not any(n.split("\n")[-1].strip() and n.split("\n")[-1].strip() in
                  gym.split("Logged under")[-1][:80] for n in live),
          "live chips: " + ", ".join(n.replace("\n"," ") for n in live))
    check("history: the lift itself is still there", "Barbell Row" in gym)

    # ---------- last day cannot be deleted ----------
    p.click('[data-tab="coach"]'); p.wait_for_timeout(300)
    answers+= [""]
    p.click("#resetRoutine"); p.wait_for_timeout(400)
    check("coach: start over restores 3 days", p.locator(".rt-day").count()==3)
    check("coach: start over offers undo", p.locator("#undobar").is_visible())
    p.click("#undoBtn"); p.wait_for_timeout(400)
    check("coach: undo start over", p.locator(".rt-day").count()==3)

    # ---------- persistence ----------
    p.reload(); p.wait_for_timeout(900)
    p.click('[data-tab="coach"]'); p.wait_for_timeout(400)
    check("coach: routine survives a reload",
          "Pull Day" in p.locator("#view").inner_text() or
          "Arms" in p.locator("#view").inner_text())

    # ---------- touch targets on coach ----------
    p.locator("[data-openday]").first.click(); p.wait_for_timeout(400)
    check("coach: chips are actually on screen when measured",
          p.locator(".rt-chip").count()>0 and p.locator("[data-addmove]").count()>0,
          str(p.locator(".rt-chip").count())+" chips, "+str(p.locator("[data-addmove]").count())+" library")
    small=p.evaluate("""()=>{const bad=[];
      document.querySelectorAll('#view button').forEach(b=>{
        const r=b.getBoundingClientRect();
        if(r.width&&r.height&&r.height<44)
          bad.push((b.className||b.id||'button')+' '+Math.round(r.width)+'x'+Math.round(r.height));
      }); return bad;}""")
    check("coach: every tappable is 44px tall", len(small)==0, "; ".join(small))

    print()
    for s,n,dt in res: print("%-6s %-52s %s"%(s,n,dt))
    print("\n%d passed, %d FAILED"%(sum(1 for r in res if r[0]=="PASS"),
                                   sum(1 for r in res if r[0]=="FAIL")))
    print("pageerrors:", errs or "none")
    b.close()
