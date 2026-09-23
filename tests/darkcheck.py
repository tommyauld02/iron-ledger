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
            "lifts": [{"id": "l", "cat": "back", "movement": "Barbell Row", "sets": [{"w": 135, "r": 10}]}],
            "supps": {"s1": True},                       # one ticked, one not: both states
            "workoutStart": int(time.time() * 1000) - 45 * 60000,
            "updated": 1, "goal": G}},
         "moves": None, "goal": G, "region": "United States",
         "supps": [{"id": "s1", "name": "Creatine", "dose": "5 g"},
                   {"id": "s2", "name": "Zinc", "dose": "50 mg"}],
         "pantry": [{"id": "p", "name": "protein coffee", "serveQty": 1, "serveUnit": "bottle",
                     "serveG": None, "sCal": 130, "sPro": 30, "aliases": []}], "v": 1}
    if theme: s["theme"] = theme
    if accent: s["accent"] = accent
    return s


LOW = """() => {
  const bad = [];
  const lum = c => { const m=c.match(/\\d+/g); if(!m) return null;
    const [r,g,b]=m.slice(0,3).map(n=>{n/=255; return n<=.03928? n/12.92 : Math.pow((n+.055)/1.055,2.4);});
    return .2126*r+.7152*g+.0722*b; };
  document.querySelectorAll('main *, .topbar *, .tabs *, .undobar *, .sheet:not([hidden]) *').forEach(el=>{
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
    for tab in ["macros", "gym", "pantry", "coach", "log"]:
        p.click('.tabs button[data-tab="%s"]' % tab); p.wait_for_timeout(350)
        if tab == "coach" and p.locator("[data-openday]").count():
            p.locator("[data-openday]").first.click(); p.wait_for_timeout(300)
        if tab == "macros" and p.locator(".meal-open").count():
            p.locator(".meal-open").first.click(); p.wait_for_timeout(300)
        low = p.evaluate(LOW)
        if low: found.append("%s: %s" % (tab, low))
        if tab == "macros":
            # the review header sits on the soft tint too
            if not p.locator("#estText").count():
                p.click("#estSwap"); p.wait_for_timeout(200)
            p.fill("#estText", "chicken and rice"); p.click("#runEst"); p.wait_for_timeout(900)
            low = p.evaluate(LOW)
            if low: found.append("estimate review: %s" % low)
            p.click("#discardEst"); p.wait_for_timeout(300)
    p.click("#setBtn"); p.wait_for_timeout(350)
    low = p.evaluate(LOW)
    if low: found.append("settings: %s" % low)
    p.click("#setDone"); p.wait_for_timeout(250)
    for f in found:
        FAILS.append("%s %s" % (label, str(f)[:110]))
    return found


with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- pass 1: following the phone, default accent ----
    for scheme in ["light", "dark"]:
        ctx = b.new_context(viewport={"width": 393, "height": 852}, has_touch=True,
                            is_mobile=True, color_scheme=scheme)
        ctx.add_init_script("delete window.claude;")
        p = ctx.new_page(); errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(400)
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fixture())
        p.reload(); p.wait_for_timeout(800)
        try: p.click("text=Got it", timeout=1500)
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
            p = ctx.new_page(); errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto("file://" + d + "/iron-ledger.html"); p.wait_for_timeout(400)
            p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", fixture(theme, accent))
            p.reload(); p.wait_for_timeout(800)
            try: p.click("text=Got it", timeout=1500)
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
