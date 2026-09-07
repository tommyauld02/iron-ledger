"""Hit-test every control on every tab.

audit2.py measures whether controls are big enough. This one asks a different
question: when you tap the middle of a control, does the tap actually reach it,
or is something sitting on top? A sticky tab bar, the undo bar, or an expanded
panel can cover a button that measures perfectly.

elementFromPoint only works inside the viewport, so the page is scrolled in
viewport-sized steps and each pass tests only what is fully on screen at that
moment. Scrolling per element instead makes every rect measured before the
scroll stale, which reports controls as covered when they are not.
"""
from playwright.sync_api import sync_playwright
import os, datetime

# file:// wants /C:/Users/... on Windows; a no-op on POSIX, where there is no
# drive letter and no backslash.
d = os.getcwd().replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
T = datetime.date.today().isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}
store = {
    "days": {T: {
        "food": [
            {"id": "a", "cal": 520, "pro": 46, "note": "Eggs and oats"},
            {"id": "m1", "note": "chicken and rice", "items": [
                {"id": "i1", "cal": 284, "pro": 53, "note": "Chicken breast · 172 g", "est": True},
                {"id": "i2", "cal": 205, "pro": 4, "note": "White rice · 158 g", "est": True}]},
            {"id": "b", "cal": 200, "pro": 20, "note": "Protein bar"}],
        "lifts": [{"id": "l1", "cat": "back", "movement": "Barbell Row",
                   "sets": [{"w": 135, "r": 10}, {"w": 155, "r": 8}]}],
        "updated": 1, "goal": G}},
    "moves": None, "goal": G, "region": "United States",
    "pantry": [{"id": "p1", "name": "costco protein coffee", "serveQty": 1,
                "serveUnit": "bottle", "serveG": None, "sCal": 130, "sPro": 30,
                "aliases": []}],
    "v": 1}

HITTEST = """() => {
  const out = [];
  const sel = 'button, input, select, textarea, [role=tab]';
  const els = [...document.querySelectorAll(
    'main ' + sel + ', .topbar ' + sel + ', .tabs ' + sel + ', .undobar ' + sel)];

  for (const el of els) {
    // The year calendar is 365 deliberately-tiny cells in a dense grid; it is
    // excluded from the size audit for the same reason.
    if (el.classList.contains('cal-cell')) continue;

    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;

    // The usable band is between the sticky header and the sticky tab bar.
    // Content scrolled up under the header is behind it by design — reporting
    // that is crying wolf. Only judge what is actually in the band, and judge
    // the header and tab bar themselves wherever they are.
    const chrome = el.closest('.topbar, .tabs, .undobar');
    if (!chrome) {
      const bar = document.querySelector('.topbar');
      const tabs = document.querySelector('.tabs');
      const top = bar ? bar.getBoundingClientRect().bottom : 0;
      const bottom = tabs ? tabs.getBoundingClientRect().top : innerHeight;
      if (r.top < top || r.bottom > bottom) continue;
    } else if (r.top < 0 || r.bottom > innerHeight) {
      continue;
    }

    const name = el.id || el.getAttribute('data-del') || el.getAttribute('data-tab')
              || el.className || el.tagName.toLowerCase();

    // The centre, plus the four corners just inside the edge — a control can be
    // reachable dead centre and still have half of it under the tab bar.
    const pts = [
      ['centre', r.left + r.width / 2, r.top + r.height / 2],
      ['top-left', r.left + 4, r.top + 4],
      ['top-right', r.right - 4, r.top + 4],
      ['bottom-left', r.left + 4, r.bottom - 4],
      ['bottom-right', r.right - 4, r.bottom - 4]];

    const blocked = [];
    for (const [where, x, y] of pts) {
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      const hit = document.elementFromPoint(x, y);
      if (!hit) continue;
      if (hit === el || el.contains(hit) || hit.contains(el)) continue;

      // Two different things can be true here. A control whose CENTRE is taken
      // is unusable. A control clipped only at a corner by an ordinary
      // neighbour is two chips sitting next to each other — normal. What
      // matters is a corner taken by something floating over the layout,
      // because that is a bar or panel eating the tap.
      const overlay = /fixed|sticky/.test(getComputedStyle(hit).position)
                   || !!hit.closest('.undobar, .tabs, .topbar, .sheet');
      if (where !== 'centre' && !overlay) continue;

      blocked.push(where + ' <- ' + (hit.id || hit.className || hit.tagName.toLowerCase()));
    }
    if (blocked.length) {
      out.push({name: String(name).slice(0, 26),
                size: Math.round(r.width) + 'x' + Math.round(r.height),
                blocked: blocked.join('; ')});
    }
  }
  return out;
}"""


def sweep(p):
    """Scroll the current tab top to bottom, hit-testing each screenful."""
    found = {}
    p.evaluate("() => window.scrollTo(0, 0)")
    p.wait_for_timeout(150)
    seen_y = -1
    while True:
        for c in p.evaluate(HITTEST):
            found[(c["name"], c["size"], c["blocked"])] = c
        y = p.evaluate("() => window.scrollY")
        if y == seen_y:
            break
        seen_y = y
        p.evaluate("() => window.scrollBy(0, Math.round(innerHeight * 0.8))")
        p.wait_for_timeout(150)
        if p.evaluate("() => window.scrollY") == y:
            break
    return list(found.values())


TABS = ["macros", "pantry", "gym", "coach", "log"]
covered = []          # anything a tap cannot reach — this suite gates on it

with sync_playwright() as pw:
    b = pw.chromium.launch()
    # a phone, not a laptop
    ctx = b.new_context(viewport={"width": 393, "height": 852},
                        has_touch=True, is_mobile=True)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text[:100])
         if m.type == "error" else None)

    p.goto("file://" + d + "/iron-ledger.html")
    p.wait_for_timeout(400)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", store)
    p.reload()
    p.wait_for_timeout(900)

    print("=== CONTROLS WITH SOMETHING ON TOP OF THEM ===")
    found = 0
    for tab in TABS:
        p.click('.tabs button[data-tab="%s"]' % tab)
        p.wait_for_timeout(450)
        # open the panels that only exist once something is expanded
        if tab == "coach" and p.locator("[data-openday]").count():
            p.locator("[data-openday]").first.click()
            p.wait_for_timeout(400)
        if tab == "macros" and p.locator(".meal-open").count():
            p.locator(".meal-open").first.click()
            p.wait_for_timeout(400)
        for c in sweep(p):
            found += 1
            covered.append("%s/%s %s" % (tab, c["name"], c["blocked"]))
            print("  %-8s %-26s %-9s %s" % (tab, c["name"], c["size"], c["blocked"]))
    if not found:
        print("  none — every control is reachable at its centre and all four corners")

    # The undo bar is the one thing that appears over the layout, so prove a
    # control is still reachable while it is showing.
    print("\n=== WITH THE UNDO BAR SHOWING ===")
    undo_took_tap = None
    p.click('.tabs button[data-tab="macros"]')
    p.wait_for_timeout(450)
    if p.locator(".t-del").count():
        p.locator(".t-del").first.click()
        p.wait_for_timeout(400)
        showing = p.locator("#undobar").is_visible()
        print("  undo bar visible:", showing)
        blocked = sweep(p)
        tabs = [c for c in blocked if c["name"] in
                ("macros", "pantry", "gym", "coach", "log")]
        print("  tabs covered (must be none — this was a real bug in b19):",
              "; ".join(c["name"] for c in tabs) or "none")
        for c in tabs:
            covered.append("undo bar covers the %s tab" % c["name"])
        print("  other controls it overlaps:",
              "; ".join(c["name"] + " " + c["blocked"] for c in blocked) or "none")
        ub = p.locator("#undoBtn").bounding_box()
        p.touchscreen.tap(ub["x"] + ub["width"] / 2, ub["y"] + ub["height"] / 2)
        p.wait_for_timeout(400)
        undo_took_tap = p.eval_on_selector_all(".t-row", "e => e.length") == 3
        print("  and Undo itself takes a tap:", undo_took_tap)

    print("\nerrors:", errs or "none")
    b.close()

# A suite that prints its findings and exits 0 cannot gate anything. A control
# a tap cannot reach is a dead button by any other name.
print("\n=== VERDICT ===")
for x in covered:
    print("  UNREACHABLE", x)
if undo_took_tap is False:
    print("  UNREACHABLE the undo button itself did not take a tap")
print("  %d unreachable, %d page errors" % (len(covered), len(errs)))
raise SystemExit(1 if (covered or errs or undo_took_tap is False) else 0)
