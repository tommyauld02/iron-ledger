"""Pre-handoff sweep: the gaps the other suites leave.

Four things nothing else covers:

1. viewport-fit=cover. The app insets for safe areas in four places, but
   env(safe-area-inset-*) resolves to 0 unless the viewport opts in, so
   without this meta all of that CSS is dead on a Dynamic Island phone.
2. The other two wake paths. checkDayRollover() is wired to visibilitychange,
   focus and pageshow; days.py only ever fires the first. iOS picks a
   different one depending on how you come back to the app, so a rollover
   that works on one and not the others fails in the field and nowhere else.
3. Touch targets, measured, on Tommy's own phone size. tests/audit.py was not
   in the archive, so audit2 is skipped and this is currently the only thing
   holding rule 5 up besides mobile.py. Every element is asserted on screen
   before it is measured — a hidden element measures nothing and passes.
4. The GitHub Pages reality: no window.claude AND no network at once. That is
   the mode Tommy's phone actually runs in, and it is the combination no
   other suite exercises together.
"""
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, io, re, json, datetime, threading, functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = ROOT.replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))

T = datetime.date.today()
Ts = T.isoformat()
Y = (T - datetime.timedelta(days=1)).isoformat()
G = {"cal": {"dir": "-", "v": 2000}, "pro": {"dir": "+", "v": 150}}

# Realistic state, not a fresh install: history, a workout, pantry, plus one
# legacy-shaped row and one deliberately malformed one.
STORE = {
    "days": {
        Y: {"food": [{"id": "y1", "cal": 610, "pro": 44, "note": "Oats and whey"}],
            "lifts": [{"id": "l1", "cat": "back", "movement": "Barbell Row",
                       "sets": [{"w": 135, "r": 10}, {"w": 155, "r": 8}]}],
            "updated": 1, "goal": G},
        Ts: {"food": [{"id": "t1", "cal": 520, "pro": 46, "note": "Eggs"},
                      {"id": "t2", "note": "Lunch", "items": [
                          {"id": "t2a", "cal": 300, "pro": 30, "note": "Chicken"},
                          {"id": "t2b", "cal": 200, "pro": 5,  "note": "Rice"}]},
                      {"id": "t3", "cal": 150},                    # legacy: no pro
                      {"id": "t4", "cal": None, "pro": None, "note": "malformed"}],
             "lifts": [], "updated": 1, "goal": G},
    },
    "moves": None, "goal": G, "region": "United States",
    "pantry": [{"id": "p1", "name": "costco protein coffee", "serveQty": 1,
                "serveUnit": "bottle", "serveG": None, "sCal": 130, "sPro": 30, "aliases": []},
               {"id": "p2", "name": "legacy item", "serveQty": 100,
                "serveUnit": "g", "serveG": 100, "sCal": 900, "sPro": 2}],  # absurd density
    "v": 1,
}

CLOCK = """(function(){
  var real = Date, cur = new real('%s');
  function D(){ return arguments.length ? new (Function.prototype.bind.apply(real,[null].concat([].slice.call(arguments)))) : new real(cur); }
  D.now = function(){ return cur.getTime(); };
  D.parse = real.parse; D.UTC = real.UTC; D.prototype = real.prototype;
  window.Date = D;
  window.__advance = function(iso){ cur = new real(iso); };
})();"""


class H(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p in ("/", "/index.html"):
            return os.path.join(ROOT, "iron-ledger.html")
        return super().translate_path(path)
    def log_message(self, *a): pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/" % PORT

# Tommy's phone. 402x874 is the logical size the 6.3" Pro reports.
PHONE = {"width": 402, "height": 874}

with sync_playwright() as pw:
    b = pw.chromium.launch()

    # ---- 1. viewport opts into the safe area ------------------------------
    src = io.open(os.path.join(ROOT, "iron-ledger.html"), encoding="utf-8").read()
    meta = re.search(r'<meta name="viewport" content="([^"]+)"', src).group(1)
    check("viewport opts into safe areas", "viewport-fit=cover" in meta, meta)
    check("app actually insets for them", src.count("env(safe-area-inset") >= 4,
          "%d uses" % src.count("env(safe-area-inset"))

    # ---- 2. rollover on every wake path ----------------------------------
    for path, fire in [
        ("visibilitychange", "document.dispatchEvent(new Event('visibilitychange'))"),
        ("focus",            "window.dispatchEvent(new Event('focus'))"),
        ("pageshow",         "window.dispatchEvent(new Event('pageshow'))"),
    ]:
        ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
        ctx.add_init_script(CLOCK % (Ts + "T22:00:00"))
        p = ctx.new_page()
        p.goto(BASE); p.wait_for_timeout(500)
        p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", STORE)
        p.reload(); p.wait_for_timeout(700)
        before = p.eval_on_selector("#dateFull", "e => e.textContent.trim()")
        # the phone was asleep; it is now tomorrow and the app is woken, not reloaded
        tomorrow = (T + datetime.timedelta(days=1)).isoformat()
        p.evaluate("iso => window.__advance(iso)", tomorrow + "T07:30:00")
        p.evaluate(fire); p.wait_for_timeout(700)
        after = p.eval_on_selector("#dateFull", "e => e.textContent.trim()")
        check("wake by %s rolls the date over" % path, before != after,
              "%s -> %s" % (before.split("\n")[-1][:24], after.split("\n")[-1][:24]))
        ctx.close()

    # ---- 3. touch targets on the real phone size -------------------------
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE); p.wait_for_timeout(500)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(900)
    try:
        p.click("text=Got it", timeout=2500)
    except Exception:
        pass
    p.wait_for_timeout(300)

    MEASURE = """() => {
      const out = [];
      document.querySelectorAll('button,a,input,select,textarea,[role="button"],[data-tab]').forEach(el => {
        const r = el.getBoundingClientRect();
        const st = getComputedStyle(el);
        // only judge what is actually on screen: a hidden element measures
        // nothing and would otherwise pass silently
        const shown = r.width > 0 && r.height > 0 && st.visibility !== 'hidden' &&
                      st.display !== 'none' && parseFloat(st.opacity) > 0.05 &&
                      r.bottom > 0 && r.top < innerHeight;
        if (!shown) return;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        // elementFromPoint only answers for points inside the viewport. Asking
        // it about a control below the fold returns null, which is not the same
        // as the control being covered — that read as a bug until it was chased.
        const inView = cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight;
        const hit = inView ? document.elementFromPoint(cx, cy) : null;
        const reachable = !inView || (!!hit && (hit === el || el.contains(hit) || hit.contains(el)));
        out.push({
          id: el.id || el.className || el.tagName,
          w: Math.round(r.width), h: Math.round(r.height),
          calCell: (el.className || '').toString().includes('cal-cell'),
          type: (el.getAttribute('type') || el.tagName).toLowerCase(),
          destructive: /rm|del|remove|clear|x\\b/i.test((el.id || '') + ' ' + (el.className || '') + ' ' + (el.textContent || '')),
          reachable
        });
      });
      return out;
    }"""

    tabs = ["macros", "pantry", "gym", "coach", "log"]
    small, blocked, seen, cal_cells = [], [], 0, 0
    for t in tabs:
        p.click('.tabs button[data-tab="%s"]' % t); p.wait_for_timeout(500)
        for el in p.evaluate(MEASURE):
            seen += 1
            # Calendar day cells are exempt by a decision this project already
            # made — a 12-month grid cannot give every day 44px on a phone, and
            # mobile.py carries the same exemption. Counted, not silently dropped.
            if el["calCell"]:
                cal_cells += 1
            elif el["type"] != "hidden" and (el["w"] < 44 or el["h"] < 44):
                small.append("%s/%s %dx%d%s" % (t, el["id"][:26], el["w"], el["h"],
                                                " DESTRUCTIVE" if el["destructive"] else ""))
            if not el["reachable"] and not el["calCell"]:
                blocked.append("%s/%s" % (t, el["id"][:30]))
    check("measured a real number of controls", seen >= 40, "%d measured" % seen)
    check("every control is at least 44px", not small, "; ".join(small[:6]))
    check("no control is covered by something else", not blocked, "; ".join(blocked[:6]))
    check("calendar cells are the only exemption", cal_cells > 0,
          "%d cal-cells, exempt by existing decision" % cal_cells)
    check("no page errors while sweeping tabs", not errs, str(errs[:2]))
    ctx.close()

    # ---- 4. the Pages reality: no Claude and no network ------------------
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE); p.wait_for_timeout(600)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", STORE)
    p.reload(); p.wait_for_timeout(1400)          # let the worker precache
    ctx.set_offline(True)
    p.goto(BASE); p.wait_for_timeout(1000)
    try:
        p.click("text=Got it", timeout=2500)
    except Exception:
        pass

    check("loads with no Claude and no network",
          p.evaluate("() => !!document.querySelector('.brand h1')"))
    check("history survived", p.evaluate("() => !!document.querySelector('.t-row')"))

    # the offline food table must answer without any network or capability
    p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(400)
    p.fill("#estText", "2 eggs"); p.click("#runEst"); p.wait_for_timeout(900)
    got = p.eval_on_selector_all(".rev-item", "e => e.length")
    check("offline food table still answers", got > 0, "%d rows for '2 eggs'" % got)
    if got:
        p.click("#discardEst"); p.wait_for_timeout(300)

    # writes must persist with everything cut
    n_before = p.evaluate("() => (JSON.parse(localStorage.getItem('iron-ledger-v1')).days['%s'].food || []).length" % Ts)
    p.fill("#fCal", "300"); p.fill("#fPro", "25"); p.fill("#fNote", "offline entry")
    p.click("#addFood"); p.wait_for_timeout(700)
    n_after = p.evaluate("() => (JSON.parse(localStorage.getItem('iron-ledger-v1')).days['%s'].food || []).length" % Ts)
    check("can log with everything cut", n_after == n_before + 1, "%d -> %d" % (n_before, n_after))
    check("the new row is visible, not just saved",
          p.evaluate("() => [...document.querySelectorAll('.t-row')].some(r => r.textContent.includes('offline entry'))"))
    check("photo button correctly absent without Claude",
          p.evaluate("() => !document.getElementById('shotBtn')"))
    check("no page errors offline", not errs, str(errs[:2]))
    ctx.close()

    # ---- 5. states that only exist after an action ------------------------
    # darkcheck walks the tabs as it finds them, so a panel that only appears
    # once you press something is never painted and its contrast is never
    # judged. The finished-day card shipped at 4.37:1 in light for exactly that
    # reason. Anything gated behind a click belongs here.
    CONTRAST = r"""() => {
      const lum = c => {const [r,g,b] = c.match(/\d+/g).map(Number).map(v => {v /= 255;
        return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4);});
        return 0.2126*r + 0.7152*g + 0.0722*b;};
      const bgOf = el => {let n = el;
        while (n && n !== document.documentElement) {
          const b = getComputedStyle(n).backgroundColor;
          if (b && !/rgba\(0, 0, 0, 0\)|transparent/.test(b)) return b;
          n = n.parentElement;}
        return getComputedStyle(document.body).backgroundColor;};
      const out = [];
      document.querySelectorAll('.daydone, .daydone *').forEach(el => {
        if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
        const s = getComputedStyle(el);
        const L1 = lum(s.color), L2 = lum(bgOf(el));
        const ratio = (Math.max(L1,L2)+0.05) / (Math.min(L1,L2)+0.05);
        const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700;
        const need = (size >= 24 || (size >= 18.66 && bold)) ? 3 : 4.5;
        out.push({what: (el.className || el.tagName) + '',
                  ratio: Math.round(ratio*100)/100, need: need, ok: ratio >= need});
      });
      return out;}"""
    LOCKED = dict(STORE)
    LOCKED["days"] = dict(STORE["days"])
    LOCKED["days"][Ts] = dict(STORE["days"][Ts])
    LOCKED["days"][Ts]["gymLocked"] = True
    LOCKED["days"][Ts]["lifts"] = [
        {"id": "lk", "cat": "back", "movement": "Lat Pulldown", "sets": [{"w": 120, "r": 10}]}]

    for scheme in ("light", "dark"):
        ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True, color_scheme=scheme)
        p = ctx.new_page()
        p.goto(BASE); p.wait_for_timeout(500)
        p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", LOCKED)
        p.reload(); p.wait_for_timeout(900)
        try:
            p.click("text=Got it", timeout=2500)
        except Exception:
            pass
        p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(600)
        rows = p.evaluate(CONTRAST)
        # an empty list would pass silently — the whole point of this section
        check("finished-day card painted in %s" % scheme, len(rows) > 0, "%d text nodes" % len(rows))
        bad = ["%s %.2f<%.1f" % (r["what"][:12], r["ratio"], r["need"]) for r in rows if not r["ok"]]
        check("finished-day card contrast in %s" % scheme, not bad, "; ".join(bad))
        ctx.close()

    # mobile.py sweeps five iPhone widths but never locks a day, so the card's
    # four-column stat grid is unmeasured there. A big volume figure on the
    # narrowest phone is exactly where it would burst.
    for name, w, h in [("iPhone SE", 320, 568), ("iPhone 17 Pro", 402, 874)]:
        ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True)
        p = ctx.new_page()
        p.goto(BASE); p.wait_for_timeout(500)
        BIG = dict(LOCKED)
        BIG["days"] = dict(LOCKED["days"])
        BIG["days"][Ts] = dict(LOCKED["days"][Ts])
        # six movements, heavy numbers: the shape of a real long session
        BIG["days"][Ts]["lifts"] = [
            {"id": "b%d" % n, "cat": "back", "movement": "Movement %d" % n,
             "sets": [{"w": 315, "r": 12}, {"w": 315, "r": 12}, {"w": 315, "r": 10}]}
            for n in range(6)]
        p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", BIG)
        p.reload(); p.wait_for_timeout(900)
        try:
            p.click("text=Got it", timeout=2500)
        except Exception:
            pass
        p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(600)
        card = p.eval_on_selector_all(".daydone", "e => e.length")
        check("finished card renders on %s" % name, card == 1, "%d cards" % card)
        over = p.evaluate("""() => {
          const bad = [];
          document.querySelectorAll('.daydone, .daydone *').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width && (r.left < -1 || r.right > window.innerWidth + 1))
              bad.push((el.className || el.tagName) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
          });
          return bad;}""")
        check("finished card fits on %s" % name, not over, "; ".join(over[:4]))
        check("page does not scroll sideways on %s" % name,
              p.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"),
              "scrollWidth=%s inner=%s" % (p.evaluate("()=>document.documentElement.scrollWidth"),
                                           p.evaluate("()=>window.innerWidth")))
        ctx.close()

    # The split editor is the same shape of blind spot: it exists only after
    # you press "Edit splits", so no suite that walks the tabs ever paints it.
    for scheme, w, h, name in [("light", 320, 568, "SE light"), ("dark", 402, 874, "Pro dark")]:
        ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=True,
                            is_mobile=True, color_scheme=scheme)
        p = ctx.new_page()
        p.goto(BASE); p.wait_for_timeout(500)
        p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", STORE)
        p.reload(); p.wait_for_timeout(900)
        try:
            p.click("text=Got it", timeout=2500)
        except Exception:
            pass
        p.click('.tabs button[data-tab="gym"]'); p.wait_for_timeout(500)
        p.click("#editSplits"); p.wait_for_timeout(500)

        rows = p.eval_on_selector_all(".split-row", "e => e.length")
        check("split editor opens on %s" % name, rows > 0, "%d rows" % rows)
        small = p.evaluate("""() => {
          const bad = [];
          document.querySelectorAll('.split-name, .split-rm, #editSplits').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width && r.height && r.height < 44)
              bad.push((el.className || el.id) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
          });
          return bad;}""")
        check("split editor controls are 44px on %s" % name, not small, "; ".join(small[:4]))
        over = p.evaluate("""() => {
          const bad = [];
          document.querySelectorAll('.split-row, .split-row *').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width && (r.left < -1 || r.right > window.innerWidth + 1))
              bad.push((el.className || el.tagName) + ' ' + Math.round(r.right));
          });
          return bad;}""")
        check("split editor fits on %s" % name, not over, "; ".join(over[:4]))
        ctx.close()

    # ---- 6. the backup safety net ----------------------------------------
    # On a phone `db` is null, so queueSync() never runs and localStorage is
    # the only copy of everything logged. The app has to know when a copy was
    # last taken and say so, or the first anyone hears about it is after the
    # phone is gone.
    DAY = 86400000
    now = int(datetime.datetime.now().timestamp() * 1000)

    def seeded(last=None, with_data=True):
        s = json.loads(json.dumps(STORE))
        s["days"][Ts]["food"] = STORE["days"][Ts]["food"] if with_data else []
        s["days"][Ts]["lifts"] = []
        s["days"].pop(Y, None) if not with_data else None
        if last is not None:
            s["lastBackupAt"] = last
        return s

    for label, seed, want in [
        ("nothing logged yet",   seeded(None, False), False),
        ("never taken a copy",   seeded(None, True),  True),
        ("copied today",         seeded(now),         False),
        ("copied 13 days ago",   seeded(now - 13 * DAY), False),
        ("copied 14 days ago",   seeded(now - 14 * DAY), True),
    ]:
        ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
        p = ctx.new_page()
        p.goto(BASE); p.wait_for_timeout(400)
        p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", seed)
        p.reload(); p.wait_for_timeout(800)
        try:
            p.click("text=Got it", timeout=2000)
        except Exception:
            pass
        due = p.evaluate("() => !document.getElementById('backupDot').hidden")
        check("backup nudge — %s" % label, due == want,
              "showing=%s wanted=%s" % (due, want))
        ctx.close()

    # taking a copy has to actually clear it, and has to survive a reload
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True,
                        permissions=["clipboard-read", "clipboard-write"])
    p = ctx.new_page()
    p.goto(BASE); p.wait_for_timeout(400)
    p.evaluate("s => localStorage.setItem('iron-ledger-v1', JSON.stringify(s))", seeded(None, True))
    p.reload(); p.wait_for_timeout(800)
    try:
        p.click("text=Got it", timeout=2000)
    except Exception:
        pass
    check("backup nudge shows before a copy is taken",
          p.evaluate("() => !document.getElementById('backupDot').hidden"))
    p.click("#backupBtn"); p.wait_for_timeout(400)
    p.click("#copyBtn"); p.wait_for_timeout(800)
    clip = p.evaluate("() => navigator.clipboard.readText()")
    check("copy puts a real backup on the clipboard",
          clip.startswith("{") and '"days"' in clip, clip[:40])
    check("copying clears the nudge",
          not p.evaluate("() => !document.getElementById('backupDot').hidden"))
    p.click("#closeSheet"); p.reload(); p.wait_for_timeout(900)
    check("and it stays cleared after a reload",
          not p.evaluate("() => !document.getElementById('backupDot').hidden"))

    # a restored phone has not taken a copy of its own, so it must still nudge
    p.evaluate("() => localStorage.clear()")
    p.reload(); p.wait_for_timeout(900)
    try:
        p.click("text=Got it", timeout=2000)
    except Exception:
        pass
    p.click("#backupBtn"); p.wait_for_timeout(400)
    p.fill("#backupText", clip); p.click("#restoreBtn"); p.wait_for_timeout(900)
    check("a restored phone is still asked for its own copy",
          p.evaluate("() => !document.getElementById('backupDot').hidden"))
    ctx.close()

    b.close()

srv.shutdown()
for s, n, det in res:
    print("%-6s %-46s %s" % (s, n, det))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
