"""The planned week split on the Gym tab: a board of this week's days, between
where you train and today's split.

A day trained says what it was (today once it is locked in), a day gone by
with nothing on it says Rest, and today and the days ahead show the weekly
plan, or Open. Tapping a day plans that day of every week; a day gone by can
be opened from there and logged after the fact.

Pinned to a Wednesday so the days either side are inside the Sunday to
Saturday week, whatever day the suite actually runs on.
"""
from playwright.sync_api import sync_playwright
import os, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d

REAL=datetime.date.today()
SHIFT=(2-REAL.weekday())%7                    # days forward to a Wednesday
T=REAL+datetime.timedelta(days=SHIFT)
def k(n): return (T+datetime.timedelta(days=n)).isoformat()
SUN,MON,TUE,WED,THU,FRI,SAT=k(-3),k(-2),k(-1),k(0),k(1),k(2),k(3)

CLOCK = """
 const REAL = Date; const off = %d;
 class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+off); else super(...a);} static now(){return REAL.now()+off;} }
 window.Date = FD;
""" % (SHIFT*86400000)

G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
# Monday trained and locked in; Tuesday trained and never locked in.
STORE={"days":{
    MON:{"food":[],"lifts":[{"id":"m1","cat":"back","movement":"Barbell Row","sets":[{"w":135,"r":10}]}],
         "gymLocked":True,"updated":1},
    TUE:{"food":[],"lifts":[{"id":"t1","cat":"legs","movement":"Back Squat","sets":[{"w":185,"r":5}]}],"updated":1}},
  "moves":{"back":["Barbell Row"],"push":["Bench Press"],"legs":["Back Squat"]},
  "movesOwned":True,"goal":G,"region":"United States","pantry":[],"v":1}

res=[]
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))
def saved(p): return p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
def week(p): return saved(p).get("week")
def pressed(p): return p.evaluate("()=>{const b=document.querySelector('.split-card .cat[aria-pressed=\"true\"]');return b&&b.dataset.cat}")
def undo_label(p): return p.evaluate("()=>{const b=document.getElementById('undobar');return b&&!b.hidden?document.getElementById('undoLabel').textContent:''}")
def tile(p, key):
    return p.evaluate("""k=>{const b=document.querySelector('[data-planday="'+k+'"]'); if(!b) return null;
        return {cls:b.className, d:b.querySelector('.wb-d').textContent, tag:b.querySelector('.wb-tag').textContent,
                n:b.querySelector('.wb-n').textContent, aria:b.getAttribute('aria-label')}}""", key)
def plan(p, key, val):
    p.click('[data-planday="%s"]' % key); p.wait_for_timeout(200)
    p.click('[data-setplan="%s"]' % val); p.wait_for_timeout(250)

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
    check("pinned to a Wednesday", p.evaluate("()=>new Date().getDay()")==3, WED)

    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)

    # ---------- where it sits ----------
    order=p.evaluate("()=>[...document.querySelectorAll('.gym-top > *')].map(e=>e.className)")
    check("between where you train and today's split",
          order[:3]==["session-card","week-card","split-card"], str(order))
    check("today's split is still there to pick from", p.locator(".split-card .cats .cat[data-cat]").count()>=4)
    check("seven days, Sunday first", p.locator(".wb-tile[data-planday]").count()==7 and
          (p.text_content(".wb-tile[data-planday] .wb-d") or "").startswith("SUN"))

    # ---------- what each day says, with no plan at all ----------
    t=tile(p, MON)
    check("a day locked in takes its place", "is-done" in t["cls"] and t["tag"]=="A" and "Back" in t["n"] and "\u2713" in t["d"], str(t))
    t=tile(p, TUE)
    check("a day gone by counts even if never locked in", "is-done" in t["cls"] and t["tag"]=="C", str(t))
    t=tile(p, SUN)
    check("a day gone by with nothing logged is Rest", "is-rest" in t["cls"] and t["n"]=="Rest", str(t))
    t=tile(p, WED)
    check("today with nothing locked in is Open", "is-open" in t["cls"] and t["n"]=="Open", str(t))
    check("the days ahead are Open", all("is-open" in tile(p, x)["cls"] for x in (THU, FRI, SAT)))
    check("no Clear plan with nothing planned", p.locator("#wbClear").count()==0)
    sizes=p.evaluate("()=>[...document.querySelectorAll('.week-card button')].map(e=>{const r=e.getBoundingClientRect();return Math.min(r.width,r.height)})")
    check("every tile is at least 44px", min(sizes)>=44, str(sizes))

    # ---------- planning a day ----------
    p.click('[data-planday="%s"]' % FRI); p.wait_for_timeout(250)
    check("a tile opens that weekday's choices", "Every Friday" in (p.text_content(".wb-pick") or ""))
    opts=p.eval_on_selector_all("[data-setplan]", "e=>e.map(b=>b.dataset.setplan)")
    check("every split, Rest and Open", opts==["back","push","legs","~rest",""], str(opts))
    check("Open is chosen with no plan", p.get_attribute('[data-setplan=""]', "aria-pressed")=="true")
    check("no way to a day that has not come yet", p.locator("#wbGo").count()==0)
    p.click('[data-setplan="legs"]'); p.wait_for_timeout(250)
    check("a choice is saved for every Friday", (week(p) or [None]*7)[5]=="legs", str(week(p)))
    check("a choice says what it did", "Fridays are Legs" in undo_label(p), undo_label(p))
    t=tile(p, FRI)
    check("the day ahead shows its plan", "is-plan" in t["cls"] and t["tag"]=="C" and "planned" in t["aria"], str(t))
    check("the choices fold once chosen", p.locator(".wb-pick").count()==0)
    ring=p.evaluate("k=>!!document.querySelector('.week-day[data-day=\"'+k+'\"] .wm.m-plan')", FRI)
    check("the week strip rings it too", ring)
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undo takes a choice back", week(p)[5] is None and "is-open" in tile(p, FRI)["cls"], str(week(p)))

    # planning today moves today's split to match
    plan(p, WED, "push")
    check("planning today picks today's split", pressed(p)=="push", str(pressed(p)))
    check("today shows its plan", "is-plan" in tile(p, WED)["cls"])
    p.click('.split-card .cat[data-cat="back"]'); p.wait_for_timeout(250)
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(250)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(300)
    check("a split tapped over the plan sticks", pressed(p)=="back", str(pressed(p)))
    check("and leaves the plan alone", week(p)[3]=="push")

    # a plan never rewrites what happened
    plan(p, MON, "legs")
    t=tile(p, MON)
    check("planning a trained day leaves what it was", "is-done" in t["cls"] and t["tag"]=="A", str(t))
    plan(p, SUN, "push")
    check("planning a day gone by leaves it Rest", "is-rest" in tile(p, SUN)["cls"])

    # ---------- today, locked in, takes its place ----------
    p.select_option("#mSel", "Barbell Row"); p.click("#addLift"); p.wait_for_timeout(350)
    check("today with a lift but not locked in still shows the plan", "is-plan" in tile(p, WED)["cls"], str(tile(p, WED)))
    p.click("#lockDay"); p.wait_for_timeout(500)
    t=tile(p, WED)
    check("locking in today takes the plan's place", "is-done" in t["cls"] and t["tag"]=="A", str(t))
    check("and the plan for every Wednesday is kept", week(p)[3]=="push")
    p.click("#unlockDay"); p.wait_for_timeout(300)
    check("unlocking gives the plan back", "is-plan" in tile(p, WED)["cls"])

    # ---------- a day forgotten, logged later ----------
    p.evaluate("k=>{const s=JSON.parse(localStorage.getItem('iron-ledger-v1')); s.week[0]=null; localStorage.setItem('iron-ledger-v1',JSON.stringify(s));}", SUN)
    p.reload(); p.wait_for_timeout(900)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    p.click('[data-planday="%s"]' % SUN); p.wait_for_timeout(250)
    go=p.text_content("#wbGo") if p.locator("#wbGo").count() else ""
    check("a day gone by offers to be logged", go.startswith("Log Sunday"), go)
    p.click("#wbGo"); p.wait_for_timeout(400)
    check("Log goes to that day", p.evaluate("()=>document.querySelector('.week-day[aria-pressed=\"true\"]').dataset.day")==SUN)
    p.click('.split-card .cat[data-cat="push"]'); p.wait_for_timeout(200)
    p.select_option("#mSel", "Bench Press"); p.click("#addLift"); p.wait_for_timeout(350)
    p.click("#lockDay"); p.wait_for_timeout(500)
    t=tile(p, SUN)
    check("logged later, Rest becomes what was trained", "is-done" in t["cls"] and t["tag"]=="B", str(t))
    p.click('[data-planday="%s"]' % SUN); p.wait_for_timeout(200)
    check("the board's day on screen is not offered again", p.locator("#wbGo").count()==0)
    p.click("#wbDone"); p.wait_for_timeout(200)
    p.click('[data-planday="%s"]' % MON); p.wait_for_timeout(200)
    go=p.text_content("#wbGo") if p.locator("#wbGo").count() else ""
    check("a trained day offers to be opened, not logged", go.startswith("Open Monday"), go)
    p.click("#wbDone"); p.wait_for_timeout(200)
    p.click('.week-day[data-day="%s"]' % WED); p.wait_for_timeout(300)

    # ---------- removing a split leaves the plan readable ----------
    p.click("#editSplits"); p.wait_for_timeout(250)
    p.click('[data-rmsplit="push"]'); p.wait_for_timeout(300)
    p.click("#editSplits"); p.wait_for_timeout(250)
    check("a removed split's day reads as Open", "is-open" in tile(p, WED)["cls"], str(tile(p, WED)))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undoing the removal brings the plan back", "is-plan" in tile(p, WED)["cls"], str(tile(p, WED)))

    # ---------- clear the plan ----------
    before=week(p)
    p.click("#wbClear"); p.wait_for_timeout(300)
    check("Clear plan clears every day", week(p)==[None]*7, str(week(p)))
    check("and says so", "Week plan cleared" in undo_label(p), undo_label(p))
    check("what was trained stays", "is-done" in tile(p, MON)["cls"] and "is-done" in tile(p, SUN)["cls"])
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("undo brings the whole plan back", week(p)==before, str(week(p)))

    # ---------- it keeps ----------
    p.reload(); p.wait_for_timeout(900)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    check("the plan survives a reload", week(p)==before and "is-plan" in tile(p, WED)["cls"], str(week(p)))
    ctx.close()

    # ---------- a day passes: Open becomes Rest ----------
    ctx=b.new_context(viewport={"width":375,"height":812}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(CLOCK.replace("const off = %d" % (SHIFT*86400000), "const off = %d" % ((SHIFT+1)*86400000)))
    p=ctx.new_page(); p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(900)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    check("the next day, yesterday's Open is Rest", "is-rest" in tile(p, WED)["cls"], str(tile(p, WED)))
    check("and today is Open", "is-open" in tile(p, THU)["cls"], str(tile(p, THU)))
    ctx.close()

    for st,n,det in res: print("%-6s %-56s %s" % (st,n,det))
    f=[r for r in res if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(res)-len(f), len(f)))
    print("pageerrors:", errs if errs else "none")
    b.close()
    raise SystemExit(1 if (f or errs) else 0)
