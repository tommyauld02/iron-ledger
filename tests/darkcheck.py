"""WCAG contrast, measured off the rendered page.

Two passes. The first follows the phone's own light/dark setting with the
default accent, which is the media-query path. The second chooses every accent
in both themes through Settings, which is the data-theme / data-accent path —
the one a person who picks a colour actually runs.

The fixture carries every state that sits on the soft accent tint: a combined
meal, a checklist with one item ticked, a running workout clock, and an open
estimate review. It used to carry none of them, and "5 g" on a ticked checklist
row shipped at 4.08:1 in b36 because nothing ever ticked one. A contrast suite
only measures the states its fixture puts on screen.
"""
import fakeai
from playwright.sync_api import sync_playwright
import os, time, datetime

d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}


def fixture(theme=None, accent=None):
    s = {"days": {T: {
            "food": [
                {"id": "a", "cal": 520, "pro": 46, "note": "Eggs and oats"},
                {"id": "m1", "note": "chicken and rice", "items": [
                    {"id": "i1", "cal": 284, "pro": 53, "note": "Chicken breast · 172 g", "est": True},
                    {"id": "i2", "cal": 205, "pro": 4, "note": "White rice · 158 g", "est": True}]}],
            # an open movement, a finished one with its time, and one finished
            # untimed — the folded card only exists after Done is tapped
            # a superset: its bracket, label and Split sit on their own ground
            "lifts": [{"id": "g1a", "cat": "back", "movement": "Dumbbell Curl", "ss": "g1",
                       "sets": [{"w": 30, "r": 12}]},
                      {"id": "g1b", "cat": "back", "movement": "Barbell Curl", "ss": "g1",
                       "sets": [{"w": 60, "r": 10}]},
                      {"id": "l", "cat": "back", "movement": "Barbell Row", "note": "Grip gave out on the last set",
                       "sets": [{"w": 135, "r": 10}, {"w": 95, "r": 8, "tech": "drop"}]},
                      {"id": "l2", "cat": "back", "movement": "Lat Pulldown", "note": "Slow negatives", "sets": [{"w": 120, "r": 10}, {"w": 120, "r": 9}], "doneAt": 1, "lapMs": 452000, "closed": True},
                      {"id": "l3", "cat": "back", "movement": "Seated Cable Row", "sets": [{"w": 100, "r": 12}], "doneAt": 2, "lapMs": None, "closed": True},
                      # a special day's movement: its own colour on the spine, tag and Done
                      {"id": "l4", "cat": "special", "movement": "Hammer Curl", "sets": [{"w": 25, "r": 20}]}],
            "supps": {"s1": True},                       # one ticked, one not: both states
            "workoutStart": int(time.time() * 1000) - 45 * 60000,
            "gymNote": "Hotel gym, dumbbells only",
            "gym": "gA",
            "cardio": [{"id": "c1", "type": "Incline walk", "min": 30, "dist": 3.1, "cal": 265, "t": 1}],
            "updated": 1, "goal": G}},
         "gyms": [{"id": "gA", "name": "Apartment gym", "tag": "APT"}, {"id": "g24", "name": "24 Hour Fitness", "tag": "24"}],
         "gymLast": "gA", "cardioTypes": ["Incline walk", "Bike"], "moves": None, "coachOn": True, "goal": G, "region": "United States",
         "supps": [{"id": "s1", "name": "Creatine", "dose": "5 g"},
                   {"id": "s2", "name": "Zinc", "dose": "50 mg"}],
         # sorted and not: the tabs, a heading, the hint and Sort in the
         # accent all exist only once the pantry has sections in it
         "pantry": [{"id": "p", "name": "protein coffee", "serveQty": 1, "serveUnit": "bottle",
                     "serveG": None, "sCal": 130, "sPro": 30, "aliases": []},
                    {"id": "p2", "name": "Eggs", "serveQty": 1, "serveUnit": "egg",
                     "serveG": None, "sCal": 72, "sPro": 6, "aliases": [], "secs": ["breakfast", "dinner"]},
                    {"id": "p3", "name": "Ice cream sandwich", "serveQty": 1, "serveUnit": "piece",
                     "serveG": None, "sCal": 180, "sPro": 3, "aliases": [], "sec": "desserts"}], "v": 1}
    P = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    s["days"][P] = {"food": [], "updated": 1, "goal": G, "workoutMs": 40 * 60000, "gymNote": "At home", "gym": "gA",
        # last time's sets decide the line under each open card: Barbell Row
        # is beaten today, Dumbbell Curl still to beat, and the folded Lat
        # Pulldown keeps its "Beaten" — every state of it on screen
        #
        # The same sets are laid out as rows under each open card, and each row
        # has a state of its own: Barbell Row is beat, Barbell Curl matched,
        # Dumbbell Curl short with the next set still to do. A state the fixture
        # stops painting is a state this suite stops measuring, so the walk fails
        # if any of the four is missing.
        "lifts": [{"id": "p1", "cat": "back", "movement": "Barbell Row", "note": "Last set was really hard", "sets": [{"w": 115, "r": 10}]},
                  {"id": "p2", "cat": "back", "movement": "Dumbbell Curl", "sets": [{"w": 40, "r": 12}, {"w": 40, "r": 12}]},
                  {"id": "p3", "cat": "back", "movement": "Lat Pulldown", "sets": [{"w": 110, "r": 10}]},
                  {"id": "p4", "cat": "back", "movement": "Barbell Curl", "sets": [{"w": 60, "r": 10}]}]}
    # an earlier workout nobody has said the gym of: the one-time question
    P2 = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    s["days"][P2] = {"food": [], "updated": 1, "goal": G,
        "lifts": [{"id": "q1", "cat": "back", "movement": "Face Pull", "sets": [{"w": 40, "r": 15}]}]}
    if theme: s["theme"] = theme
    if accent: s["accent"] = accent
    s["build"] = "2026-10-09.58"        # last opened on an older build: What's new is drawn
    # carbs and fat, water, and a few weigh-ins: each paints something of its own
    s["cfOn"] = True
    s["waterOn"] = True
    s["days"][T]["water"] = 600
    for i, w in enumerate([184.0, 183.2, 183.6, 182.8]):
        k = (datetime.date.today() - datetime.timedelta(days=10 - i * 2)).isoformat()
        s["days"].setdefault(k, {"food": [], "updated": 1, "goal": G})["bw"] = w
    return s


LOW = """() => {
  const bad = [];
  const lum = c => { const m=c.match(/\\d+/g); if(!m) return null;
    const [r,g,b]=m.slice(0,3).map(n=>{n/=255; return n<=.03928? n/12.92 : Math.pow((n+.055)/1.055,2.4);});
    return .2126*r+.7152*g+.0722*b; };
  document.querySelectorAll('main *, .topbar *, .dock *, .sheet:not([hidden]) *').forEach(el=>{
    if(!el.textContent.trim() || el.children.length) return;
    const s=getComputedStyle(el); const f=lum(s.color);
    let p=el, bgc=null;
    while(p && p!==document.documentElement){ const c=getComputedStyle(p).backgroundColor;
      if(c && !c.includes('rgba(0, 0, 0, 0)')){ bgc=c; break; } p=p.parentElement; }
    const bl=lum(bgc||'rgb(255,255,255)');
    if(f===null||bl===null) return;
    const ratio=(Math.max(f,bl)+.05)/(Math.min(f,bl)+.05);
    const size=parseFloat(s.fontSize), bold=parseInt(s.fontWeight)>=700;
    const need=(size>=24||(size>=18.66&&bold))?3:4.5;
    if(ratio<need) bad.push(el.textContent.trim().slice(0,28)+' | '+ratio.toFixed(2)+':1 need '+need);
  });
  return [...new Set(bad)];
}"""

# The palette itself, read off the page, independent of which elements a
# fixture happens to put on screen: every pairing the accent is used in.
PAIRS = """() => {
  const v = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const hex = h => { h = h.replace('#',''); if (h.length===3) h=h.split('').map(c=>c+c).join('');
    return [0,2,4].map(i=>parseInt(h.substr(i,2),16)); };
  const lum = h => { const [r,g,b] = hex(h).map(n=>{n/=255; return n<=.03928? n/12.92 : Math.pow((n+.055)/1.055,2.4);});
    return .2126*r+.7152*g+.0722*b; };
  const ratio = (a,b) => { const x=lum(a), y=lum(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
  const t = { accent: v('--accent'), soft: v('--accent-soft'), on: v('--on-accent'),
              surface: v('--surface'), surface2: v('--surface-2'), ground: v('--ground'),
              ink: v('--ink'), ink2: v('--ink-2') };
  const out = {
    'accent on surface': ratio(t.accent, t.surface),
    'accent on surface-2': ratio(t.accent, t.surface2),
    'accent on ground': ratio(t.accent, t.ground),
    'button text on accent': ratio(t.on, t.accent),
    'accent on soft': ratio(t.accent, t.soft),
    'ink on soft': ratio(t.ink, t.soft),
    'ink-2 on soft': ratio(t.ink2, t.soft)
  };
  const bad = Object.keys(out).filter(k => out[k] < 4.5).map(k => k+' '+out[k].toFixed(2));
  // a ticked row has to look different from an unticked one
  const sep = ratio(t.soft, t.surface);
  if (sep < 1.12) bad.push('soft tint indistinguishable from surface '+sep.toFixed(2));
  return { accent: t.accent, bad: bad };
}"""

FAILS = []


def walk(p, label):
    """Every tab, plus the states and panels that only exist after a press."""
    found = []
    # What's new only exists on the first open after an update: the fixture
    # carries an older build so that it is drawn, and it is measured first
    if not p.is_visible("#newsSheet") or not p.locator("#newsBody h3").count():
        found.append("what's new: the pop-up is not on screen")
    else:
        low = p.evaluate(LOW)
        if low: found.append("what's new: %s" % low)
        p.click("#newsDone"); p.wait_for_timeout(200)
    for tab in ["macros", "gym", "pantry", "cardio", "coach", "log"]:
        p.click('.tabs button[data-tab="%s"]' % tab); p.wait_for_timeout(350)
        if tab == "coach" and p.locator("[data-openday]").count():
            p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
        if tab == "macros" and p.locator(".meal-open").count():
            p.locator(".meal-open").first.click(); p.wait_for_timeout(300)
        low = p.evaluate(LOW)
        if low: found.append("%s: %s" % (tab, low))
        if tab == "pantry":
            # the sections have looks of their own: the tabs, a chosen one,
            # the meals named under a food, and Meals itself
            painted = p.evaluate("""()=>({
              tabs: document.querySelectorAll('[data-pantab]').length,
              chosen: document.querySelectorAll('[data-pantab][aria-pressed=true]').length,
              tags: document.querySelectorAll('.pan-item .tags').length,
              meals: document.querySelectorAll('.pan-item .pan-open').length})""")
            for k, n in painted.items():
                if not n: found.append("pantry: the %s state is not on screen" % k)
            # a chosen one in the form sits on the form's ground, and a food's
            # own choices only exist once its Meals is pressed
            p.click("#panNew"); p.wait_for_timeout(250)
            p.click('[data-pansec="snacks"]'); p.wait_for_timeout(100)
            low = p.evaluate(LOW)
            if low: found.append("pantry (new food): %s" % low)
            p.click("#panNewClose"); p.wait_for_timeout(250)
            p.locator("[data-panmeals]").first.click(); p.wait_for_timeout(250)
            if not p.locator('[data-pansecfor][aria-pressed="true"]').count():
                found.append("pantry: a food's chosen meals are not on screen")
            low = p.evaluate(LOW)
            if low: found.append("pantry (choosing meals): %s" % low)
            p.click("#panEditDone"); p.wait_for_timeout(150)
            # editing the sections themselves only exists after a press
            p.click("#editPanSecs"); p.wait_for_timeout(250)
            low = p.evaluate(LOW)
            if low: found.append("pantry (editing sections): %s" % low)
            p.click("#editPanSecs"); p.wait_for_timeout(150)
            # combining foods: a draft with a food in it, only after presses
            p.click("#combStart"); p.wait_for_timeout(250)
            p.locator("[data-addpan]").first.click(); p.wait_for_timeout(250)
            p.click("#panAddBtn"); p.wait_for_timeout(250)
            p.click("#combSave"); p.wait_for_timeout(250)    # one food: the warning shows
            if not p.locator(".comb-part").count() or not p.locator("#combWarn").count():
                found.append("pantry: the combination draft is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("pantry (combining): %s" % low)
            p.click("#combCancel"); p.wait_for_timeout(150)
        if tab == "cardio":
            # every look of it: the goal met and not, its editor, the chooser,
            # a running clock, a session being changed, and finished
            if not p.locator(".cardio-card").count():
                found.append("cardio: no session on screen to measure")
            for step, sel, undo in [("goal editor", "#cgOpen", "#cgCancel"), ("choosing a session", "#cardioStart", "#cPickCancel"),
                                    ("changing a session", "[data-cedit]", "#ceCancel"), ("logging by hand", "#cardioByHand", "#cAddCancel")]:
                p.locator(sel).first.click(); p.wait_for_timeout(250)
                low = p.evaluate(LOW)
                if low: found.append("cardio (%s): %s" % (step, low))
                p.click(undo); p.wait_for_timeout(200)
            p.click("#cardioStart"); p.wait_for_timeout(200); p.click("#cPickGo"); p.wait_for_timeout(300)
            low = p.evaluate(LOW)
            if low: found.append("cardio (running): %s" % low)
            p.click("#cardioDiscard"); p.wait_for_timeout(200)
            p.click("#cardioFinish"); p.wait_for_timeout(300)
            low = p.evaluate(LOW)
            if low: found.append("cardio (finished): %s" % low)
            p.click("#cardioUnlock"); p.wait_for_timeout(200)
        if tab == "log" and not p.locator(".cardio-track").count():
            found.append("log: the cardio tracker is not on screen")
        if tab == "log" and not p.locator("#bwCard svg polyline").count():
            found.append("log: the body weight trend is not on screen")
        if tab == "gym":
            # the set to beat has three looks, and a state the fixture stops
            # painting is a state this suite stops measuring — so say so
            painted = p.evaluate("""()=>({
              toBeat: document.querySelectorAll('.lift:not(.is-closed) .beat:not(.is-beaten)').length,
              beaten: document.querySelectorAll('.lift:not(.is-closed) .beat.is-beaten').length,
              folded: document.querySelectorAll('.lift.is-closed .beat.is-beaten').length})""")
            for k, n in painted.items():
                if not n: found.append("set to beat: the %s state is not on screen" % k)
            # the suggestions line (+5 lb / +1 rep / +1 set) was taken off on
            # 2026-10-14; it must not be on screen, in either theme
            if p.locator(".lift .beat-ways").count():
                found.append("set to beat: the suggestions line is back on the card")
            # last time, set by set: every state a row can be in is measured, so
            # the fixture has to paint each of them
            rows = p.evaluate("""()=>({
              rows: document.querySelectorAll('.lift .lastset').length,
              matched: document.querySelectorAll('.lift .ls-mark.ls-matched').length,
              beat: document.querySelectorAll('.lift .ls-mark.ls-beat').length,
              short: document.querySelectorAll('.lift .ls-mark.ls-short').length,
              next: document.querySelectorAll('.lift .ls-next').length})""")
            for k, n in rows.items():
                if not n: found.append("last time, set by set: the %s state is not on screen" % k)
            # Beat is the one coloured label, in the macro green; the rest are grey
            tones = p.evaluate("""()=>{const c=s=>{const e=document.querySelector(s);return e?getComputedStyle(e).color:null;};
              return {beat:c('.ls-mark.ls-beat'), matched:c('.ls-mark.ls-matched'), short:c('.ls-mark.ls-short'),
                      hit:getComputedStyle(document.querySelector('.beat.is-beaten b')).color};}""")
            if tones["beat"] != tones["hit"]: found.append("last time, set by set: Beat is not in the macro green")
            if tones["matched"] == tones["beat"] or tones["short"] == tones["beat"]:
                found.append("last time, set by set: Matched or Short is coloured like Beat")
            # and the notes: the day's, one on an open card, one on a folded
            # card, and last time's riding on the Last line
            notes = p.evaluate("""()=>({
              day: document.querySelectorAll('.day-note').length,
              open: document.querySelectorAll('.lift .lift-note').length,
              folded: document.querySelectorAll('.lift .lift-note-done').length,
              last: [...document.querySelectorAll('.lift .last')].filter(e=>e.textContent.includes('\u201c')).length})""")
            for k, n in notes.items():
                if not n: found.append("notes: the %s note is not on screen" % k)
            # the set sheet, adding a set with the target in it, then its Edit
            p.locator("[data-addset]").first.click(); p.wait_for_timeout(250)
            # filled from last time's next set, with the line that says so
            if not p.is_visible("#seLastSet") or not p.eval_on_selector("#seLastSet", "e=>e.textContent").startswith("Last time, set "):
                found.append("set sheet: the Last time line is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("set sheet (adding): %s" % low)
            p.click("#seMoveBtn"); p.wait_for_timeout(200)
            low = p.evaluate(LOW)
            if low: found.append("set sheet (changing the movement): %s" % low)
            p.click("#seCancel"); p.wait_for_timeout(200)
            # the special day chosen: its chip pressed, its own movement list
            p.click('[data-cat="special"]'); p.wait_for_timeout(250)
            low = p.evaluate(LOW)
            if low: found.append("gym (special day): %s" % low)
            p.click('[data-cat="back"]'); p.wait_for_timeout(200)
            # where you train: a chosen gym, the tag on a card, the one-time
            # question, the sheet's Targets row — then the editor, which only
            # exists after a press
            gyms = p.evaluate("""()=>({
              chosen: document.querySelectorAll('[data-gym][aria-pressed=true]').length,
              tag: document.querySelectorAll('.lift h3 .gymtag').length,
              ask: document.querySelectorAll('[data-gymask]').length})""")
            for k, n in gyms.items():
                if not n: found.append("gyms: the %s is not on screen" % k)
            p.locator("[data-addset]").first.click(); p.wait_for_timeout(250)
            if not p.locator("#seGym").is_visible():
                found.append("gyms: the set sheet's Targets row is not on screen")
            p.click("#seCancel"); p.wait_for_timeout(200)
            p.click("#editGyms"); p.wait_for_timeout(250)
            low = p.evaluate(LOW)
            if low: found.append("gym (editing gyms): %s" % low)
            p.click("#editGyms"); p.wait_for_timeout(200)
            # the rest bar lives in the dock, and running looks different
            p.click("#restBtn"); p.wait_for_timeout(200)
            low = p.evaluate(LOW)
            if low: found.append("gym (resting): %s" % low)
            p.click("#restBtn"); p.wait_for_timeout(150)
            # the comparison is a sheet, open only after a press
            if p.locator("#openCompare").count():
                p.click("#openCompare"); p.wait_for_timeout(300)
                low = p.evaluate(LOW)
                if low: found.append("compare: %s" % low)
                p.click("#cmpDone"); p.wait_for_timeout(200)
            # The held state only exists mid-drag — the superset zones and the
            # lit one under the finger. Put on screen and measured, because a
            # state no test paints is a state no test measures.
            p.evaluate("""()=>{document.body.classList.add('arranging');
              const z=document.querySelectorAll('.ss-zone'); if(z[1]) z[1].classList.add('is-over');}""")
            low = p.evaluate(LOW)
            if low: found.append("gym (held): %s" % low)
            p.evaluate("""()=>{document.body.classList.remove('arranging');
              document.querySelectorAll('.ss-zone.is-over').forEach(z=>z.classList.remove('is-over'));}""")
        if tab == "macros":
            # both boxes are folded until a press: open each and measure it
            p.click('[data-logway="numbers"]'); p.wait_for_timeout(250)
            if not p.locator("#fCal").count(): found.append("macros: the numbers box is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("macros (log calories / protein): %s" % low)
            p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
            if not p.locator('[data-ef="0"]').count(): found.append("macros: the estimate table is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("macros (don't know the numbers): %s" % low)
            # and as pop-ups, chosen in Settings, then back to in place; the
            # open box is folded first, or it would come back as a pop-up over
            # the very button the next step presses
            p.click('[data-logway="estimate"]'); p.wait_for_timeout(200)
            p.click("#setBtn"); p.wait_for_timeout(250)
            p.click('[data-pick-logopen="popup"]'); p.wait_for_timeout(200)
            p.click("#setDone"); p.wait_for_timeout(250)
            for w in ("numbers", "estimate"):
                p.click('[data-logway="%s"]' % w); p.wait_for_timeout(250)
                if not p.locator('[data-waysheet="%s"]' % w).count():
                    found.append("macros: the %s pop-up is not on screen" % w)
                low = p.evaluate(LOW)
                if low: found.append("macros (%s pop-up): %s" % (w, low))
                p.click('[data-wayclose="%s"]' % w); p.wait_for_timeout(200)
            p.click("#setBtn"); p.wait_for_timeout(250)
            p.click('[data-pick-logopen="inplace"]'); p.wait_for_timeout(200)
            p.click("#setDone"); p.wait_for_timeout(250)
            p.click('[data-logway="estimate"]'); p.wait_for_timeout(250)
            # the Scan a barcode tab only exists after a press
            p.click('[data-esttab="scan"]'); p.wait_for_timeout(200)
            if not p.locator("#openScan").count(): found.append("macros: the Scan a barcode tab is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("macros (Scan a barcode tab): %s" % low)
            # the review header sits on the soft tint too
            if not p.locator("#estText").count():
                p.click('[data-esttab="agent"]'); p.wait_for_timeout(200)
            p.fill("#estText", "chicken and rice"); p.click("#runEst"); p.wait_for_timeout(900)
            low = p.evaluate(LOW)
            if low: found.append("estimate review: %s" % low)
            # saving it as a meal opens a row of sections, one of them chosen
            p.click("#estSave"); p.wait_for_timeout(250)
            p.click('[data-estsec="lunch"]'); p.wait_for_timeout(100)
            low = p.evaluate(LOW)
            if low: found.append("meal save row: %s" % low)
            p.click("#estSaveCancel"); p.wait_for_timeout(200)
            p.click("#discardEst"); p.wait_for_timeout(300)
            # the food finder's flags, each only on screen after an answer: numbers
            # that don't add up, and a food left waiting when the finder was busy
            p.fill("#estText", "cava harissa avocado bowl"); p.click("#runEst"); p.wait_for_timeout(900)
            if not p.locator(".est-flag .why").count(): found.append("macros: the doesn't-add-up flag is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("macros (doesn't add up): %s" % low)
            p.click("#discardEst"); p.wait_for_timeout(300)
            p.fill("#estText", "lasagne"); p.click("#runEst"); p.wait_for_timeout(900)
            if not p.locator("[data-reask]").count(): found.append("macros: a food waiting for the finder is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("macros (waiting for the finder): %s" % low)
            # a scanned barcode only exists after presses; grocery brands first
            p.click("#openScan"); p.wait_for_timeout(500)
            if p.locator("#scanBrands").count():
                p.click("#scanBrands")
                try: p.wait_for_selector("#scanType", timeout=40000)
                except Exception: found.append("macros: grocery brands did not download for the scanner")
            if p.locator("#scanType").count():
                p.fill("#scanType", "894700010038"); p.click("#scanGo"); p.wait_for_timeout(400)
            if not p.locator(".scan-card").count(): found.append("macros: a scanned product is not on screen")
            low = p.evaluate(LOW)
            if low: found.append("macros (barcode): %s" % low)
            p.click("#scanClose"); p.wait_for_timeout(200)
            # carbs and fat, and water, are in the fixture: their lines must be painted
            if not p.locator(".cf-line").count(): found.append("macros: the carbs and fat line is not on screen")
            if not p.locator("#waterRow").count(): found.append("macros: the water line is not on screen")
            # the goal calculator, filled in so its answer shows
            p.click("#openGoal"); p.wait_for_timeout(200)
            p.click("#gcOpen"); p.wait_for_timeout(200)
            p.click('[data-gcsex="f"]'); p.fill("#gcAge", "31"); p.fill("#gcFt", "5"); p.fill("#gcIn", "6"); p.wait_for_timeout(100)
            low = p.evaluate(LOW)
            if low: found.append("macros (goal calculator): %s" % low)
            p.click("#cancelGoal"); p.wait_for_timeout(200)
            p.click("#discardEst"); p.wait_for_timeout(300)
    p.click("#setBtn"); p.wait_for_timeout(350)
    low = p.evaluate(LOW)
    if low: found.append("settings: %s" % low)
    p.click("#setDone"); p.wait_for_timeout(250)
    for f in found:
        FAILS.append("%s %s" % (label, str(f)[:110]))
    return found


# The food finder's two flags: an answer whose numbers still don't add up
# after the relay's second look, and Gemini too busy to answer at all.
def dark_reply(q):
    t = q["food"]
    if "cava" in t:
        return {"items": [{"food": "Cava harissa avocado bowl", "amount": "1 bowl", "grams": 450, "calories": 1900,
                           "protein": 20, "carbs": 60, "fat": 30, "basis": "rough"}], "note": "Assumed a full bowl."}
    if "lasagne" in t:
        return (429, {"error": "busy"})
    return None


with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- pass 1: following the phone, default accent ----
    for scheme in ["light", "dark"]:
        ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True,
                            is_mobile=True, color_scheme=scheme)
        ctx.add_init_script("delete window.claude;")
        fakeai.phone(ctx, reply=dark_reply)
        p = ctx.new_page(); errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(400)
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fixture())
        p.reload(); p.wait_for_timeout(800)
        try: p.click("#dismissWelcome", timeout=1500)     # the welcome only; What's new is measured first
        except Exception: pass
        found = walk(p, "phone-%s" % scheme)
        print("phone %-5s  teal      %s" % (scheme, "; ".join(found) if found else "clean"))
        if errs: FAILS.append("phone-%s: page errors %s" % (scheme, str(errs[:2])[:80]))
        ctx.close()

    # ---- pass 2: every accent, both themes, chosen in Settings ----
    for accent in ["teal", "blue", "violet", "orange", "graphite"]:
        for theme in ["light", "dark"]:
            # the phone deliberately set the opposite way, so the choice has to win
            ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True, is_mobile=True,
                                color_scheme=("dark" if theme == "light" else "light"))
            ctx.add_init_script("delete window.claude;")
            fakeai.phone(ctx, reply=dark_reply)
            p = ctx.new_page(); errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(400)
            p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fixture(theme, accent))
            p.reload(); p.wait_for_timeout(800)
            try: p.click("#dismissWelcome", timeout=1500)     # the welcome only; What's new is measured first
            except Exception: pass
            pairs = p.evaluate(PAIRS)
            for x in pairs["bad"]:
                FAILS.append("%s/%s palette: %s" % (accent, theme, x))
            found = walk(p, "%s/%s" % (accent, theme))
            print("chosen %-5s %-9s %s  %s" % (theme, accent, pairs["accent"],
                  "; ".join(pairs["bad"] + found) if (pairs["bad"] or found) else "clean"))
            if errs: FAILS.append("%s/%s: page errors %s" % (accent, theme, str(errs[:2])[:80]))
            ctx.close()
    b.close()

print('\n' + "=== VERDICT ===")
for x in FAILS: print("  FAIL", x)
print("  %d contrast problems" % len(FAILS))
raise SystemExit(1 if FAILS else 0)
