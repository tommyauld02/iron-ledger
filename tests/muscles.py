"""What a movement works, and the recovery body map it feeds (b88).

Movements are the owner's own names, so the app knows what one works in
three ways, in this order: what he has said (store.muscles, by name), the
built-in list (every name the app suggests), or a guess from the words in the
name, which says it is a guess. A name none of those place asks, once, and is
never counted until it is answered.

Locked in, a day shows the body front and back, coloured by working sets per
muscle (warm-ups out, a helping muscle half, a set to failure one and a half),
with the same in words under it, on the profile's figure or one picked once.

Exits non-zero on any failure or page error: it is a gate.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
import os, json, datetime, copy
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d
URL="file://"+d+"/mntl-dt.html"
MIN_TAP=44

T=datetime.date.today(); Ts=T.isoformat()
def ago(n): return (T-datetime.timedelta(days=n)).isoformat()
G={"cal":{"dir":"-","v":2200},"pro":{"dir":"+","v":180}}
def lift(i, name, sets): return {"id":"l%d"%i, "cat":"back", "movement":name, "sets":sets}
def S(w, r, tech=None):
    x={"w":w,"r":r}
    if tech: x["tech"]=tech
    return x
# The guesses: a name, and what its line must start with. The narrow rules
# win over the broad ones, and a name with nothing to read stays a question.
GUESSES=[
    ("Leg curl machine",       "Works Hamstrings"),
    ("Dumbbell kickbacks",     "Works Triceps"),
    ("Glute kickback",         "Works Glutes"),
    ("Rowing machine",         "Not on the body map"),
    ("Hammer curls",           "Works Biceps \u00b7 Forearms"),
    ("Smith squat",            "Works Quads"),
    ("Machine lateral raise",  "Works Side delts"),
    ("Reverse fly",            "Works Rear delts"),
    ("Kroc row",               "Works Upper back \u00b7 Lats"),
    ("Smith incline thing",    None),            # nothing to read: asked
]
BASE={"days":{
    Ts:{"food":[],"goal":G,"gym":"gA","lifts":[
        lift(1,"Barbell Row",[S(95,10,"warmup"),S(135,10),S(155,8),S(155,8)]),
        lift(2,"Lat Pulldown",[S(120,10),S(120,9),S(110,10,"failure")]),
        lift(3,"Big blue machine",[S(90,12),S(90,12)])]},
    ago(2):{"food":[],"goal":G,"gym":"gA","gymLocked":True,"lifts":[lift(9,"barbell row",[S(135,10)])]}},
  "gyms":[{"id":"gA","name":"Apartment gym","tag":"APT"}],"gymLast":"gA","gymAsked":True,"seen":True,
  "moves":{"back":["Barbell Row","Lat Pulldown","Big blue machine"]},"movesOwned":True,
  "goal":G,"region":"United States","v":1,"pantry":[],"profile":{"sex":"m"}}
GUESSDAY={"days":{Ts:{"food":[],"goal":G,"gym":"gA","lifts":[lift(i,n,[S(50,10)]) for i,(n,_) in enumerate(GUESSES)]}},
  "gyms":[{"id":"gA","name":"Apartment gym","tag":"APT"}],"gymLast":"gA","gymAsked":True,"seen":True,
  "moves":None,"movesOwned":True,"goal":G,"region":"United States","v":1,"pantry":[]}

LINES="()=>[...document.querySelectorAll('.lift')].map(l=>{const w=l.querySelector('.works .wk-t'), a=l.querySelector('.works-ask'); return w?w.textContent:(a?'ASK':'');})"
SAYS="()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
SAVED="()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).muscles||{}"
STATES="()=>Object.fromEntries([...document.querySelectorAll('[data-musc]')].filter(b=>b.dataset.state).map(b=>[b.dataset.musc,b.dataset.state]))"
REC="()=>[...document.querySelectorAll('.rec-list p')].map(p=>[p.dataset.rec,p.querySelector('span').textContent,p.querySelector('b').className])"
FILL="(id)=>{const e=document.querySelector('#recovery [data-musc-on=\"'+id+'\"]'); return e?e.getAttribute('fill'):null}"

res=[]
def check(n, ok, det=""): res.append((("PASS" if ok else "FAIL"), n, det))

def page(b, store, scheme="light"):
    ctx=b.new_context(viewport={"width":402,"height":874}, has_touch=True, is_mobile=True, color_scheme=scheme)
    ctx.add_init_script("delete window.claude;")
    p=ctx.new_page(); errs=[]
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(URL); p.wait_for_timeout(300)
    p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", store)
    p.reload(); p.wait_for_timeout(800)
    if p.locator("#newsSheet").is_visible():
        p.keyboard.press("Escape"); p.wait_for_timeout(200)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    return ctx, p, errs

with sync_playwright() as pw:
    b=pw.chromium.launch()
    allerrs=[]

    # ---------- the guesses ----------
    ctx, p, errs = page(b, GUESSDAY)
    lines=p.evaluate(LINES)
    for (name, want), got in zip(GUESSES, lines):
        if want is None:
            check("guess: %s has nothing to read, so it asks" % name, got=="ASK", got)
        else:
            check("guess: %s reads as %s" % (name, want.split(" ",1)[1] if want.startswith("Works") else want),
                  got.startswith(want), got)
    check("guess: a guess says it is one, and from which word",
          "a guess from \u201crow\u201d" in lines[GUESSES.index(("Kroc row","Works Upper back \u00b7 Lats"))], str(lines))
    allerrs += errs; ctx.close()

    # ---------- the list, the guess and the question ----------
    ctx, p, errs = page(b, BASE)
    lines=p.evaluate(LINES)
    check("list: a name the app suggests says what it works, main muscles first",
          lines[0]=="Works Upper back \u00b7 Lats \u00b7 Biceps \u00bd \u00b7 Rear delts \u00bd \u00b7 Lower back \u00bd", lines[0])
    check("list: and it is not called a guess", "guess" not in lines[0])
    check("ask: a name nothing places asks, instead of being guessed at", lines[2]=="ASK", str(lines))
    ch=p.locator(".lift .wk-ed").first.bounding_box()
    check("list: Change is a proper target", ch and ch["height"]>=MIN_TAP and ch["width"]>=MIN_TAP, str(ch))
    ab=p.locator(".lift .works-ask").first.bounding_box()
    check("ask: the question is a proper target", ab and ab["height"]>=MIN_TAP, str(ab))

    p.locator(".lift .works-ask").first.click(); p.wait_for_timeout(300)
    check("ask: tapping it opens the question, naming the movement",
          p.locator("#worksSheet").count()==1 and "Big blue machine" in p.text_content("#worksSheet h2"))
    chips=p.evaluate("""()=>[...document.querySelectorAll('[data-musc]')].map(b=>{const r=b.getBoundingClientRect();
        const h=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
        return {id:b.dataset.musc, w:r.width, h:r.height, hit:!!h&&(h===b||b.contains(h))}})""")
    check("ask: all sixteen muscles, none chosen yet", len(chips)==16 and p.evaluate(STATES)=={}, str(len(chips)))
    check("ask: every muscle is a proper target a tap reaches",
          all(c["w"]>=MIN_TAP and c["h"]>=MIN_TAP and c["hit"] for c in chips), str([c for c in chips if not (c["w"]>=MIN_TAP and c["h"]>=MIN_TAP and c["hit"])][:3]))
    p.click('[data-musc="upback"]'); p.click('[data-musc="lats"]')
    p.click('[data-musc="biceps"]'); p.click('[data-musc="biceps"]')
    p.click('[data-musc="chest"]'); p.click('[data-musc="chest"]'); p.click('[data-musc="chest"]')
    p.wait_for_timeout(100)
    check("ask: once is main, twice helps, three times is off",
          p.evaluate(STATES)=={"upback":"p","lats":"p","biceps":"s"}, str(p.evaluate(STATES)))
    check("ask: and each says so to a screen reader",
          p.get_attribute('[data-musc="biceps"]',"aria-label")=="Biceps, helps"
          and p.get_attribute('[data-musc="chest"]',"aria-pressed")=="false")
    check("ask: nothing is written before Save", p.evaluate(SAVED)=={})
    p.click("#worksSave"); p.wait_for_timeout(400)
    sv=p.evaluate(SAVED)
    check("ask: Save keeps it by name", sv.get("big blue machine",{}).get("p")==["upback","lats"]
          and sv["big blue machine"].get("s")==["biceps"], str(sv))
    check("ask: and says what it saved", p.evaluate(SAYS)=="Big blue machine works Upper back, Lats and Biceps \u00bd", p.evaluate(SAYS))
    check("ask: the card says it now", p.evaluate(LINES)[2]=="Works Upper back \u00b7 Lats \u00b7 Biceps \u00bd", p.evaluate(LINES)[2])
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("ask: Undo takes it back to a question", p.evaluate(LINES)[2]=="ASK" and p.evaluate(SAVED)=={}, str(p.evaluate(SAVED)))

    # Not now, the X and a tap on the dim page all leave it as it was
    for closer in ["#worksCancel", "#worksClose", "#worksSheet"]:
        p.locator(".lift .works-ask").first.click(); p.wait_for_timeout(250)
        p.click('[data-musc="quads"]')
        if closer=="#worksSheet": p.mouse.click(200, 60)
        else: p.click(closer)
        p.wait_for_timeout(250)
        check("ask: %s closes it and keeps nothing" % {"#worksCancel":"Not now","#worksClose":"the X","#worksSheet":"a tap on the dim page"}[closer],
              p.locator("#worksSheet").count()==0 and p.evaluate(SAVED)=={})

    # Change on a listed one starts from the list, and the answer wins from then on
    p.locator(".lift .wk-ed").first.click(); p.wait_for_timeout(300)
    check("change: it opens on what the list says",
          p.evaluate(STATES)=={"upback":"p","lats":"p","biceps":"s","rdelt":"s","lowback":"s"}, str(p.evaluate(STATES)))
    p.click('[data-musc="lowback"]')   # helps -> off
    p.click("#worksSave"); p.wait_for_timeout(400)
    # saved in the body's own order, top to bottom: Rear delts before Biceps
    CHANGED="Works Upper back · Lats · Rear delts ½ · Biceps ½"
    check("change: what he says wins over the list",
          p.evaluate(LINES)[0]==CHANGED, p.evaluate(LINES)[0])
    p.reload(); p.wait_for_timeout(800)
    p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(400)
    check("change: kept after a reload", p.evaluate(LINES)[0]==CHANGED, p.evaluate(LINES)[0])
    for _ in range(2): p.click("#prevDay"); p.wait_for_timeout(150)
    check("change: and on every day with that name, whatever its case",
          p.evaluate(LINES)[0]==CHANGED, str(p.evaluate(LINES)))
    for _ in range(2): p.click("#nextDay"); p.wait_for_timeout(150)

    # ---------- the recovery card ----------
    p.click("#lockDay"); p.wait_for_timeout(600)
    check("recovery: locked in, the day shows the body front and back",
          p.locator("#recovery").count()==1 and p.locator("#recovery svg.body-fig").count()==2)
    rec=p.evaluate(REC)
    got={r[0]:r[1] for r in rec}
    # Barbell Row: 3 working sets (the warm-up is out) -> upback 3, lats 3, biceps 1.5, rdelt 1.5
    # Lat Pulldown: 2 + a set to failure (1.5) = 3.5 -> lats 3.5, biceps 1.75, upback 1.75
    check("recovery: warm-ups out, helping muscles half, a set to failure one and a half",
          got.get("lats")=="6.5 sets" and got.get("upback")=="5 sets" and got.get("biceps")=="3.5 sets"
          and got.get("rdelt")=="1.5 sets", str(rec))
    check("recovery: most worked first", [r[0] for r in rec][:2]==["lats","upback"], str(rec))
    lv={r[0]:r[2] for r in rec}
    check("recovery: 6 sets or more is red, 3 to 5 yellow, under 3 green",
          lv.get("lats")=="lv-red" and lv.get("upback")=="lv-yellow" and lv.get("rdelt")=="lv-green", str(lv))
    check("recovery: and the body is coloured to match",
          p.evaluate(FILL,"lats")=="var(--miss)" and p.evaluate(FILL,"upback")=="var(--warn-fill)"
          and p.evaluate(FILL,"rdelt")=="var(--hit)" and p.evaluate(FILL,"quads")=="var(--surface-2)",
          "%s %s %s %s" % tuple(p.evaluate(FILL,x) for x in ("lats","upback","rdelt","quads")))
    ask=p.locator("#recovery .works-ask")
    check("recovery: a movement nobody has placed is named, not quietly left out",
          ask.count()==1 and "Big blue machine is not counted yet" in ask.text_content())
    check("recovery: it says it is a guide, not a measurement",
          "not a measurement" in p.text_content("#recovery .rec-note"))
    ask.click(); p.wait_for_timeout(300)
    p.click('[data-musc="lats"]'); p.click("#worksSave"); p.wait_for_timeout(400)
    got={r[0]:r[1] for r in p.evaluate(REC)}
    check("recovery: answered, its sets count", got.get("lats")=="8.5 sets" and p.locator("#recovery .works-ask").count()==0, str(got))
    allerrs += errs; ctx.close()

    # ---------- the figure: the profile's, or picked once ----------
    FEM=copy.deepcopy(BASE); FEM["profile"]={"sex":"f"}; FEM["days"][Ts]["gymLocked"]=True
    ctx, p, errs = page(b, FEM, "dark")
    check("figure: a woman's profile shows the female figure",
          p.locator('#recovery svg.body-fig path[d^="M99 84 Q87 79"]').count()>=1, str(p.locator("#recovery svg").count()))
    allerrs += errs; ctx.close()
    NONE=copy.deepcopy(BASE); del NONE["profile"]; NONE["days"][Ts]["gymLocked"]=True
    ctx, p, errs = page(b, NONE)
    pk=p.locator("[data-bodyfig]")
    check("figure: with nothing in the profile, it asks which", pk.count()==2 and p.locator("#recovery svg").count()==0)
    bb=pk.first.bounding_box()
    check("figure: and each choice is a proper target", bb and bb["height"]>=MIN_TAP, str(bb))
    p.click('[data-bodyfig="female"]'); p.wait_for_timeout(400)
    check("figure: the choice is kept and said",
          p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).bodyFig")=="female"
          and "female figure" in p.evaluate(SAYS) and p.locator("#recovery svg.body-fig").count()==2, p.evaluate(SAYS))
    allerrs += errs; ctx.close()

    for st,n,det in res: print("%-5s %-84s %s" % (st,n,det))
    f=[r for r in res if r[0]=="FAIL"]
    print("\n%d passed, %d FAILED" % (len(res)-len(f), len(f)))
    print("pageerrors:", allerrs if allerrs else "none")
    b.close()
    raise SystemExit(1 if (f or allerrs) else 0)
