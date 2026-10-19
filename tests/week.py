"""The week's plan on the Gym tab: which split goes on which day of the week.

Pinned to a Wednesday so yesterday and tomorrow are both inside the Sunday to
Saturday strip, whatever day the suite actually runs on.
"""
from playwright.sync_api import sync_playwright
import os, json, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d

REAL=datetime.date.today()
SHIFT=(2-REAL.weekday())%7                    # days forward to a Wednesday
T=REAL+datetime.timedelta(days=SHIFT)
WED,TUE,THU=3,2,4                             # JS getDay()
Ts=T.isoformat()
TUEs=(T-datetime.timedelta(days=1)).isoformat()
THUs=(T+datetime.timedelta(days=1)).isoformat()

CLOCK = """
 const REAL = Date; const off = %d;
 class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+off); else super(...a);} static now(){return REAL.now()+off;} }
 window.Date = FD;
""" % (SHIFT*86400000)

G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
STORE={"days":{},
  "moves":{"back":["Barbell Row"],"push":["Bench Press"],"legs":["Back Squat"]},
  "movesOwned":True,"goal":G,"region":"United States","pantry":[],"v":1}

res=[]
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))
def saved(p): return p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
def week(p): return saved(p).get("week")
def pressed(p): return p.evaluate("()=>{const b=document.querySelector('.cat[aria-pressed=\"true\"]');return b&&b.dataset.cat}")
def undo_label(p): return p.evaluate("()=>{const b=document.getElementById('undobar');return b&&!b.hidden?document.getElementById('undoLabel').textContent:''}")
def plan(p, dow, val):
    p.select_option('[data-plan="%d"]' % dow, val); p.wait_for_timeout(250)

with sync_playwright() as pw:
    b=pw.chromium.launch()
    ctx=b.new_context(viewport={"width":375,"height":812}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(CLOCK)
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(900)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    check("pinned to a Wednesday", p.evaluate("()=>new Date().getDay()")==WED, Ts)

    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)

    # ---------- nothing planned yet ----------
    check("plan line invites a plan", "Give each day" in (p.text_content(".plan-line") or ""))
    check("Plan week is a 44px button",
          p.evaluate("()=>{const r=document.getElementById('planWeek').getBoundingClientRect();return r.height>=44&&r.width>=44}"))

    # ---------- the planner ----------
    p.click("#planWeek"); p.wait_for_timeout(300)
    check("seven pickers, Sunday first", p.locator("[data-plan]").count()==7 and
          (p.text_content('.plan-row:first-child label') or "").startswith("Sunday"))
    check("today is marked in the list", "Today" in (p.text_content('.plan-row.is-shown') or "") and
          (p.text_content('.plan-row.is-shown label') or "").startswith("Wednesday"))
    opts=p.eval_on_selector('[data-plan="3"]', "e=>[...e.options].map(o=>o.value)")
    check("each picker holds nothing, every split and rest", opts==["","back","push","legs","~rest"], str(opts))
    sizes=p.evaluate("""()=>[...document.querySelectorAll('[data-plan]')].map(e=>{const r=e.getBoundingClientRect();
                         return [r.height,parseFloat(getComputedStyle(e).fontSize)]})""")
    check("pickers are 44px tall and never zoom iOS", all(h>=44 and f>=16 for h,f in sizes), str(sizes[:2]))
    check("no Clear the week with nothing planned", p.locator("#clearPlan").count()==0)

    plan(p, WED, "legs")
    check("a change is saved", (week(p) or [None]*7)[WED]=="legs", str(week(p)))
    check("a change says what it did", "Wednesdays are Legs" in undo_label(p), undo_label(p))

    plan(p, THU, "push")
    th=p.evaluate("k=>{const b=document.querySelector('.week-day[data-day=\"'+k+'\"]');const m=b.querySelector('.wm');"
                  "return {cls:m.className,bc:m.style.borderColor,aria:b.getAttribute('aria-label')}}", THUs)
    check("a planned day ahead is ringed in the strip", "m-plan" in th["cls"] and th["bc"], str(th))
    check("and says so to a screen reader", "planned: Chest" in (th["aria"] or ""), th["aria"])
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undo takes a change back", week(p)[THU] is None, str(week(p)))
    check("undo redraws the strip", p.evaluate("k=>!document.querySelector('.week-day[data-day=\"'+k+'\"] .wm.m-plan')", THUs))

    plan(p, TUE, "push")
    check("Clear the week appears", p.locator("#clearPlan").count()==1)
    p.click("#planDone"); p.wait_for_timeout(300)
    check("Done closes the planner", p.locator("[data-plan]").count()==0 and p.locator(".cats").count()==1)

    # ---------- today's split ----------
    check("plan line names today's split", "Legs" in (p.text_content(".plan-line") or ""))
    check("planning today moved today's chip", pressed(p)=="legs", str(pressed(p)))
    p.click('.cat[data-cat="back"]'); p.wait_for_timeout(250)
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(250)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(300)
    check("a chip tapped over the plan sticks", pressed(p)=="back", str(pressed(p)))
    check("the plan is untouched by a tap", week(p)[WED]=="legs")

    # another day opens on its own planned split
    p.click('.week-day[data-day="%s"]' % TUEs); p.wait_for_timeout(350)
    check("opening a planned day picks its split", pressed(p)=="push", str(pressed(p)))
    p.click('.week-day[data-day="%s"]' % Ts); p.wait_for_timeout(350)

    # a day with lifts keeps what was logged in charge
    p.click('.cat[data-cat="back"]'); p.wait_for_timeout(200)
    p.select_option("#mSel", "Barbell Row"); p.click("#addLift"); p.wait_for_timeout(350)
    p.click('.week-day[data-day="%s"]' % TUEs); p.wait_for_timeout(300)
    p.click('.week-day[data-day="%s"]' % Ts); p.wait_for_timeout(300)
    check("a day with a lift on it is not re-picked", pressed(p)!="legs", str(pressed(p)))

    # ---------- rest days ----------
    p.click('.week-day[data-day="%s"]' % THUs); p.wait_for_timeout(300)
    p.click("#planWeek"); p.wait_for_timeout(250)
    plan(p, THU, "~rest")
    check("rest is saved", week(p)[THU]=="~rest")
    check("rest says so", "Thursdays are a rest day" in undo_label(p), undo_label(p))
    p.click("#planDone"); p.wait_for_timeout(250)
    check("a rest day says so where the movements go",
          "rest day on your plan" in (p.text_content("#view .empty") or "").lower(), p.text_content("#view .empty"))
    check("plan line says rest", "Rest day" in (p.text_content(".plan-line") or ""))
    p.click('.week-day[data-day="%s"]' % Ts); p.wait_for_timeout(300)

    # ---------- removing a split leaves the plan readable ----------
    p.click("#editSplits"); p.wait_for_timeout(250)
    p.click('[data-rmsplit="legs"]'); p.wait_for_timeout(300)
    p.click("#editSplits"); p.wait_for_timeout(250)
    check("a removed split reads as nothing planned",
          "Nothing planned for Wednesdays" in (p.text_content(".plan-line") or ""), p.text_content(".plan-line"))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undoing the removal brings the plan back", "Legs" in (p.text_content(".plan-line") or ""), p.text_content(".plan-line"))

    # ---------- clear the week ----------
    p.click("#planWeek"); p.wait_for_timeout(250)
    before=week(p)
    p.click("#clearPlan"); p.wait_for_timeout(300)
    check("Clear the week clears it", week(p)==[None]*7, str(week(p)))
    check("and says so", "Week plan cleared" in undo_label(p), undo_label(p))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undo brings the whole week back", week(p)==before, str(week(p)))

    # ---------- it keeps ----------
    p.reload(); p.wait_for_timeout(900)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    check("the plan survives a reload", week(p)==before and p.locator(".plan-line").count()==1, str(week(p)))

    # ---------- a restore brings it ----------
    s=saved(p)
    check("the plan is in the backup", s.get("week")==before)
    ctx.close()

    for st,n,det in res: print("%-6s %-52s %s" % (st,n,det))
    f=[r for r in res if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(res)-len(f), len(f)))
    print("pageerrors:", errs if errs else "none")
    b.close()
    raise SystemExit(1 if (f or errs) else 0)
