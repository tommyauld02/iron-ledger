from playwright.sync_api import sync_playwright
import os, json, datetime
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
res=[]
def ck(n,ok,det=""): res.append((("PASS" if ok else "FAIL"),n,det))

CLOCK = """
 const REAL = Date; let off = %d;
 window.__setOffsetDays = n => { off = n*86400000; };
 class FD extends REAL { constructor(...a){ if(!a.length) super(REAL.now()+off); else super(...a);} static now(){return REAL.now()+off;} }
 window.Date = FD;
"""

def resume(p):
    """background then foreground, the way iOS suspends and restores a home-screen app"""
    p.evaluate("""()=>{Object.defineProperty(document,'hidden',{value:true,configurable:true});
                      document.dispatchEvent(new Event('visibilitychange'));}""")
    p.wait_for_timeout(120)
    p.evaluate("""()=>{Object.defineProperty(document,'hidden',{value:false,configurable:true});
                      document.dispatchEvent(new Event('visibilitychange'));}""")
    p.wait_for_timeout(500)

def keys(p): return p.evaluate("()=>Object.keys(JSON.parse(localStorage.getItem('iron-ledger-v1')).days).sort()")

with sync_playwright() as pw:
    b=pw.chromium.launch()

    # ---- open 3 days ago, then walk forward one day at a time ----
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    ctx.add_init_script(CLOCK % (-3*86400000))
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(900)
    day0=p.text_content("#dateFull")

    # log food + a workout on day 0
    p.fill("#fCal","1800"); p.fill("#fPro","160"); p.fill("#fNote","Full day")
    p.click("#addFood"); p.wait_for_timeout(400)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    p.select_option("#mSel","Barbell Row"); p.click("#addLift"); p.wait_for_timeout(350)
    p.fill('[data-w="0"]',"135"); p.fill('[data-r="0"]',"10"); p.click('[data-addset="0"]'); p.wait_for_timeout(350)
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(350)
    k0=keys(p)
    ck("day 0: logged", len(k0)==1, k0[0])

    # ---- midnight passes, app resumes ----
    p.evaluate("()=>window.__setOffsetDays(-2)"); resume(p)
    day1=p.text_content("#dateFull")
    ck("rollover: date advances", day1!=day0, "%s -> %s" % (day0.strip(), day1.strip()))
    ck("rollover: new day starts empty", p.eval_on_selector_all(".t-row","e=>e.length")==0)
    ck("rollover: 'back to today' hidden", p.evaluate("()=>document.getElementById('todayBtn').hidden"))
    ck("rollover: yesterday untouched", len(keys(p))==1)

    p.fill("#fCal","2400"); p.fill("#fPro","120"); p.fill("#fNote","Over day")
    p.click("#addFood"); p.wait_for_timeout(400)
    k1=keys(p)
    ck("rollover: logs to the NEW day", len(k1)==2 and k1[1]!=k1[0], " + ".join(k1))

    # ---- last-session lookup must reach back across the day boundary ----
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    p.select_option("#mSel","Barbell Row"); p.click("#addLift"); p.wait_for_timeout(400)
    last=p.eval_on_selector(".lift .last","e=>e.textContent")
    ck("rollover: last-session crosses days", "135" in last and "10" in last, last.strip())
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(300)

    # ---- goal changed today must NOT rewrite yesterday's verdict ----
    p.click("#openGoal"); p.wait_for_timeout(300)
    p.fill("#gCal","3000"); p.click("#saveGoal"); p.wait_for_timeout(400)
    store=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1'))")
    ck("rollover: yesterday keeps its own target",
       store["days"][k1[0]]["goal"]["cal"]["v"]==2000 and store["days"][k1[1]]["goal"]["cal"]["v"]==3000,
       "%s=%s, %s=%s" % (k1[0], store["days"][k1[0]]["goal"]["cal"]["v"], k1[1], store["days"][k1[1]]["goal"]["cal"]["v"]))

    # ---- skip two days entirely (app closed over a weekend) ----
    p.evaluate("()=>window.__setOffsetDays(0)"); resume(p)
    ck("gap: jumps straight to today", p.evaluate("()=>document.getElementById('todayBtn').hidden"))
    ck("gap: today empty, history intact", p.eval_on_selector_all(".t-row","e=>e.length")==0 and len(keys(p))==2)

    # ---- calendar reflects all of it ----
    p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
    hit=p.eval_on_selector_all(".cal-cell.hit","e=>e.length")
    miss=p.eval_on_selector_all(".cal-cell.miss","e=>e.length")
    today_ring=p.eval_on_selector_all(".cal-cell.is-today","e=>e.length")
    ck("calendar: one hit + one miss", hit==1 and miss==1, "hit=%d miss=%d"%(hit,miss))
    ck("calendar: exactly one today ring", today_ring==1)
    stats=p.eval_on_selector_all(".yearstats b","e=>e.map(x=>x.textContent)")
    ck("calendar: stats count both gym days", stats[0]=="2", "gym days=%s hits=%s rate=%s"%tuple(stats))
    ctx.close()

    # ---- viewing a PAST day when midnight hits: cursor must stay put ----
    ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;"); ctx.add_init_script(CLOCK % 0)
    p=ctx.new_page(); p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(800)
    p.click("#prevDay"); p.click("#prevDay"); p.wait_for_timeout(400)
    viewing=p.text_content("#dateFull")
    p.evaluate("()=>window.__setOffsetDays(1)"); resume(p)
    ck("rollover while browsing history: stays on that day", p.text_content("#dateFull")==viewing, viewing.strip())
    ck("rollover while browsing: 'back to today' offered", p.evaluate("()=>!document.getElementById('todayBtn').hidden"))
    ctx.close()

    # ---- month and year boundaries ----
    for label, iso in [("month boundary (Sep30->Oct1)","2026-09-30T22:00:00"),
                       ("year boundary (Dec31->Jan1)","2026-12-31T22:00:00")]:
        ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True)
        ctx.add_init_script("delete window.claude;")
        ctx.add_init_script("""
          const REAL=Date; let base=new REAL('%s').getTime(); let off=0;
          window.__jump=ms=>{off=ms;};
          class FD extends REAL{constructor(...a){if(!a.length)super(base+off);else super(...a);}static now(){return base+off;}}
          window.Date=FD;""" % iso)
        p=ctx.new_page(); p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(800)
        before=p.text_content("#dateFull")
        p.fill("#fCal","500"); p.fill("#fPro","40"); p.fill("#fNote","Before midnight")
        p.click("#addFood"); p.wait_for_timeout(400)
        p.evaluate("()=>window.__jump(4*3600*1000)"); resume(p)
        after=p.text_content("#dateFull")
        p.fill("#fCal","600"); p.fill("#fPro","50"); p.fill("#fNote","After midnight")
        p.click("#addFood"); p.wait_for_timeout(400)
        ks=keys(p)
        ck(label, len(ks)==2 and after!=before, "%s -> %s (%s)" % (before.strip(), after.strip(), " + ".join(ks)))
        if "year" in label:
            p.click('.tabs button[data-tab="log"]'); p.wait_for_timeout(600)
            ck("year boundary: calendar opens on the new year",
               p.text_content(".yearnav .y")=="2027", "showing "+p.text_content(".yearnav .y"))
            p.click("#prevYear"); p.wait_for_timeout(500)
            ck("year boundary: previous year still reachable",
               p.eval_on_selector_all(".cal-cell.hit, .cal-cell.miss","e=>e.length")>=1)
        ctx.close()

    for st,n,det in res: print("%-6s %-46s %s" % (st,n,det))
    f=[r for r in res if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(res)-len(f), len(f)))
    print("pageerrors:", errs if errs else "none")
    b.close()
