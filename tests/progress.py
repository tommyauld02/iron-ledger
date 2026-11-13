"""The Progress tab (b90): a check-in a day, if you want one.

Asked for by Tommy (2026-11-07): a tab left of Log holding, for any day you
want, a photo, a note and your weight, any one of them enough; the days listed
plainly, each opening to the whole check-in; two photos compared; and the Log
showing which days have one. This suite plays all of it as a phone would:

- the tab sits just left of Log, hides the date strip, and says what it is for
- New check-in: today's weight already in it, nothing saved from nothing, a
  note alone is a check-in, Save says so and Undo takes it back
- the weight is the day's Body weight, one number in both places, and a kg
  phone that changes nothing leaves the pounds exactly as they were
- a photo is shrunk to 1280px, kept in IndexedDB beside the log, never in it,
  never in a backup, and still there after the app is closed and opened
- a day that already has a check-in is opened, and said, never written over
- one check-in: its photo, weight, note, and stepping to the next and last
- Compare, side by side and as a slider, from the top card and from a day
- Remove keeps the day's weight, Undo brings the photo back, and once Undo
  can no longer reach it the photo is deleted the next time the app opens
- a photo this phone does not have says so; nothing shows a broken image
- the Log: a camera on a photo day, a ring on one without, the legend, and the
  peek's Progress line opening the check-in
- the iPhone app: a shell without the Filesystem plugin keeps notes and weight
  and says photos come with the update; with it, photos are the app's files,
  and a file already gone (the plugin refuses that delete) still leaves the bin
- every control 44px, every field 16px, and seven tabs on a 320px phone

Exits non-zero on any failure or page error: it is a gate.
"""
import answered   # every page has said 18 or older: tests/answered.py
from playwright.sync_api import sync_playwright
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os, json, datetime, threading, functools, base64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


# Over http, the way a phone opens it: reloads here stand for the app being
# closed and opened, and file:// can hand a reloaded page an empty
# localStorage for a moment (docs/testing.md).
srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/mntl-dt.html" % srv.server_address[1]
KEY = "iron-ledger-v1"

T = datetime.date.today()
Ts = T.isoformat()
def ago(n): return (T - datetime.timedelta(days=n)).isoformat()
def md(k):  # "Oct 21", as the app writes a day
    dt = datetime.date.fromisoformat(k); return dt.strftime("%b ") + str(dt.day)
G = {"cal": {"dir": "-", "v": 2200}, "pro": {"dir": "+", "v": 180}}


def fixture(prog=None, bwunit=None, coach=False):
    days = {}
    for i, w in enumerate([186.0, 185.2, 184.8, 183.9, 183.0, 182.4]):
        days[ago(60 - i * 10)] = {"food": [], "updated": 1, "goal": G, "bw": w}
    days[Ts] = {"food": [{"id": "f1", "cal": 900, "pro": 80, "note": "Eggs"}], "updated": 1, "goal": G, "bw": 181.6}
    for k, p in (prog or {}).items():
        days.setdefault(k, {"food": [], "updated": 1, "goal": G})["prog"] = p
    s = {"days": days, "goal": G, "region": "United States", "v": 1, "pantry": [], "seen": True,
         "moves": None, "movesOwned": True, "coachOn": coach}
    if bwunit: s["bwUnit"] = bwunit
    return s


res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))

SAYS = "()=>document.getElementById('undobar').hidden?'':document.getElementById('undoLabel').textContent"
LOG = "()=>JSON.parse(localStorage.getItem('%s'))" % KEY
RAW = "()=>localStorage.getItem('%s')" % KEY
# The words as written. Since b96 headings and buttons are drawn in capitals by
# CSS, which is lettering and not wording, so it is set aside while reading.
SHEET = "()=>{const s=document.getElementById('pgSheet');if(!s)return '';const st=document.createElement('style');st.textContent='*{text-transform:none!important}';document.head.appendChild(st);const t=s.innerText;st.remove();return t}"
TABSHOWN = "()=>[...document.querySelectorAll('.tabs button')].filter(b=>b.getClientRects().length).map(b=>b.dataset.tab)"
# what IndexedDB holds for a photo: its type and its size once decoded
IDB = """async (id)=>{const db=await new Promise((ok,no)=>{const r=indexedDB.open('mntl-dt-photos',1);
  r.onupgradeneeded=()=>r.result.createObjectStore('photos');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
  const b=await new Promise((ok,no)=>{const t=db.transaction('photos','readonly'),q=t.objectStore('photos').get(id);
    q.onsuccess=()=>ok(q.result);q.onerror=()=>no(q.error);});
  db.close(); if(!b) return null;
  const bm=await createImageBitmap(b); return {type:b.type,size:b.size,w:bm.width,h:bm.height};}"""
IDBKEYS = """async ()=>{const db=await new Promise((ok,no)=>{const r=indexedDB.open('mntl-dt-photos',1);
  r.onupgradeneeded=()=>r.result.createObjectStore('photos');r.onsuccess=()=>ok(r.result);r.onerror=()=>no(r.error);});
  const k=await new Promise((ok,no)=>{const t=db.transaction('photos','readonly'),q=t.objectStore('photos').getAllKeys();
    q.onsuccess=()=>ok(q.result);q.onerror=()=>no(q.error);}); db.close(); return k;}"""
# every visible control in the open sheet: 44px, and fields 16px (rules 4, 5)
SIZES = """()=>{const bad=[];const s=document.getElementById('pgSheet');if(!s) return ['no sheet'];
  s.querySelectorAll('button,select,input,textarea').forEach(e=>{const r=e.getBoundingClientRect();
    if(!r.width||!r.height) return;
    if(e.tagName!=='TEXTAREA'&&(r.width<44||r.height<44)) bad.push((e.id||e.className||e.tagName)+' '+Math.round(r.width)+'x'+Math.round(r.height));
    if(e.matches('input,select,textarea')&&parseFloat(getComputedStyle(e).fontSize)<16) bad.push((e.id||e.tagName)+' font '+getComputedStyle(e).fontSize);});
  return bad;}"""
# The visual viewport, stood in for and shrunk the way an iPhone's is (keys's).
KBFAKE = """(()=>{const t=new EventTarget(); t.offsetTop=0; t.scale=1;
  Object.defineProperty(t,'height',{get(){return innerHeight-(window.__kbH||0);}});
  Object.defineProperty(window,'visualViewport',{configurable:true,get:()=>t});
  window.__kb=(h)=>{window.__kbH=h; t.dispatchEvent(new Event('resize'));};})()"""
IMG_OK = "(sel)=>{const i=document.querySelector(sel);return !!(i&&i.complete&&i.naturalWidth>0)}"


def phone(b, store, w=402, h=874, init=None, expose=None):
    ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True)
    ctx.add_init_script("delete window.claude;")
    if expose:
        for name, fn in expose.items(): ctx.expose_function(name, fn)
    if init: ctx.add_init_script(init)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(URL); p.wait_for_timeout(300)
    if store is not None:
        p.evaluate("s=>localStorage.setItem('%s',JSON.stringify(s))" % KEY, store)
        p.reload(); p.wait_for_timeout(900)
    if p.locator("#newsSheet").is_visible():
        p.click("#newsDone"); p.wait_for_timeout(200)
    return ctx, p, errs


def tab(p, t):
    p.click('.tabs button[data-tab="%s"]' % t); p.wait_for_timeout(350)


def jpeg(p, w=2400, h=3200, tone="#8e7b6b"):
    """A big phone photo, made in the page: bytes for set_input_files."""
    data = p.evaluate("""([w,h,tone])=>{const c=document.createElement('canvas');c.width=w;c.height=h;
      const x=c.getContext('2d'),g=x.createLinearGradient(0,0,0,h);g.addColorStop(0,'#d6d0c6');g.addColorStop(1,tone);
      x.fillStyle=g;x.fillRect(0,0,w,h);x.fillStyle='#33403d';x.fillRect(w*.3,h*.3,w*.4,h*.45);
      return c.toDataURL('image/jpeg',.9).split(',')[1];}""", [w, h, tone])
    return [{"name": "progress.jpg", "mimeType": "image/jpeg", "buffer": base64.b64decode(data)}]


def add_photo(p, files):
    p.set_input_files("#pgLib", files)
    p.wait_for_selector(".pg-slot.has-photo img", timeout=8000)
    p.wait_for_timeout(150)


def change_day(p, k):
    p.click("#pgDayBtn"); p.wait_for_timeout(150)
    # what the phone's date wheel does: a value, then change
    p.evaluate("(k)=>{const f=document.getElementById('pgDay');f.value=k;f.dispatchEvent(new Event('change',{bubbles:true}));}", k)
    p.wait_for_timeout(250)


def save(p, wait=900):
    p.click("#pgSave"); p.wait_for_timeout(wait)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    allerrs = []

    # ---------- 1. the tab, before anything is in it ----------
    ctx, p, errs = phone(b, fixture(), init=KBFAKE)
    shown = p.evaluate(TABSHOWN)
    check("tab: Progress sits just left of Log", shown[-2:] == ["progress", "log"], str(shown))
    check("tab: and is called Progress",
          p.locator('.tabs [data-tab="progress"] .tl').inner_text().strip().lower() == "progress")
    tab(p, "progress")
    check("tab: it hides the date strip, like Log", p.evaluate("document.getElementById('datenav').hidden"))
    check("tab: with nothing yet, it says what a check-in is",
          p.locator("#pgIntro").is_visible() and "any one of them is a check-in" in p.locator("#pgIntro").inner_text())
    check("tab: and where photos stay", "Photos stay on this phone" in p.locator("#pgIntro").inner_text())
    check("tab: New check-in is the plate above the tabs", p.locator("#plates #pgNew").text_content().strip() == "New check-in")
    tab(p, "macros")
    check("tab: the date strip is back on Macros", not p.evaluate("document.getElementById('datenav').hidden"))

    # ---------- 2. the editor ----------
    tab(p, "progress")
    p.click("#pgNew"); p.wait_for_timeout(300)
    txt = p.evaluate(SHEET)
    check("editor: it opens as New check-in, for today", "New check-in" in txt and "For today" in txt, txt[:80])
    check("editor: today's weigh-in is already in it", p.input_value("#pgW") == "181.6", p.input_value("#pgW"))
    check("editor: a photo is optional and it says so", "A note or a weight on its own is a check-in too" in txt)
    check("editor: Take photo opens the camera, Choose one the library",
          p.get_attribute("#pgCam", "capture") is not None and p.get_attribute("#pgLib", "capture") is None)
    check("editor: every control 44px, every field 16px", not p.evaluate(SIZES), str(p.evaluate(SIZES)))
    p.fill("#pgW", ""); save(p, 300)
    check("editor: nothing in it saves nothing, and says why",
          "Add a photo, a note or a weight first" in p.evaluate(SHEET) and "prog" not in p.evaluate(LOG)["days"][Ts])
    check("editor: and the day's weight was not taken off", p.evaluate(LOG)["days"][Ts].get("bw") == 181.6)
    p.click("#pgX"); p.wait_for_timeout(250)
    check("editor: the X closes it, keeping nothing", not p.locator("#pgSheet").count() and "prog" not in p.evaluate(LOG)["days"][Ts])
    # The empty tab is shorter than the screen, so the room the keyboard made
    # under the page could never scroll out of sight; it has to go anyway.
    p.click("#pgNew"); p.wait_for_timeout(250)
    p.locator("#pgNote").tap(); p.wait_for_timeout(60)
    p.evaluate("h=>window.__kb(h)", 336); p.wait_for_timeout(800)
    grew = p.evaluate("()=>document.documentElement.scrollHeight")
    p.keyboard.type("12"); p.wait_for_timeout(100)
    p.evaluate("()=>{document.activeElement.blur(); window.__kb(0);}"); p.wait_for_timeout(400)
    p.evaluate("()=>window.scrollTo(0, document.documentElement.scrollHeight)"); p.wait_for_timeout(300)
    p.evaluate("()=>window.scrollTo(0, 0)"); p.wait_for_timeout(300)
    left = p.evaluate("()=>[document.documentElement.classList.contains('kb-room'), document.documentElement.scrollHeight]")
    check("keyboard: on the empty tab the keyboard's room is there while typing", grew > 874, str(grew))
    check("keyboard: and goes once typing ends, leaving nothing to scroll", not left[0] and left[1] <= 874, str(left))
    p.click("#pgX"); p.wait_for_timeout(250)

    # ---------- 3. a note alone ----------
    p.click("#pgNew"); p.wait_for_timeout(250)
    p.fill("#pgNote", "Felt strong today"); save(p)
    day = p.evaluate(LOG)["days"][Ts]
    check("note: a note alone is a check-in", day.get("prog", {}).get("note") == "Felt strong today" and "photo" not in day["prog"], str(day.get("prog")))
    check("note: the weight was left as it was", day.get("bw") == 181.6)
    check("note: Save says so (rule 3)", p.evaluate(SAYS) == "Saved today’s check-in", p.evaluate(SAYS))
    row = p.evaluate("""()=>{const r=document.querySelector('.pg-row.is-new'),d=document.querySelector('.dock');
      if(!r) return null; const a=r.getBoundingClientRect(); return {top:a.top,bottom:a.bottom,dock:d.getBoundingClientRect().top}}""")
    check("note: the new row is lit and on screen, above the dock", row and row["top"] >= 0 and row["bottom"] <= row["dock"], str(row))
    check("note: the intro gives way to the list", not p.locator("#pgIntro").count() and p.locator("#pgSince").is_visible())
    p.click("#undoBtn"); p.wait_for_timeout(300)
    check("note: Undo takes it back", "prog" not in p.evaluate(LOG)["days"][Ts] and p.locator("#pgIntro").is_visible())

    # ---------- 4. the weight is Body weight ----------
    p.click("#pgNew"); p.wait_for_timeout(250)
    p.fill("#pgW", "180.2"); save(p)
    check("weight: a weight alone is a check-in, and is the day's Body weight",
          p.evaluate(LOG)["days"][Ts].get("bw") == 180.2 and "prog" in p.evaluate(LOG)["days"][Ts])
    tab(p, "log")
    check("weight: the Log's Body weight card shows it", "180.2" in p.locator("#bwCard .bw-now").inner_text())
    tab(p, "progress")
    check("weight: back on Progress, its Undo is still there", p.evaluate(SAYS) == "Saved today’s check-in", p.evaluate(SAYS))
    p.click("#undoBtn"); p.wait_for_timeout(300)
    d0 = p.evaluate(LOG)["days"][Ts]
    check("weight: Undo puts the old weight back too", d0.get("bw") == 181.6 and "prog" not in d0, str(d0))
    p.click("#pgNew"); p.wait_for_timeout(250)
    p.fill("#pgW", "12"); save(p, 300)
    check("weight: a number that can't be a weight is turned away", "doesn’t look like a weight" in p.evaluate(SHEET))
    p.click("#pgX"); p.wait_for_timeout(200)

    # ---------- 5. a photo ----------
    p.click("#pgNew"); p.wait_for_timeout(250)
    add_photo(p, jpeg(p))
    check("photo: it shows in the editor before saving", p.locator(".pg-slot.has-photo img").is_visible())
    check("photo: with Change photo and Take it off, 44px",
          p.locator("#pgSwap").is_visible() and p.locator("#pgDrop").is_visible() and not p.evaluate(SIZES), str(p.evaluate(SIZES)))
    p.fill("#pgNote", "Waist is down an inch"); save(p, 1200)
    day = p.evaluate(LOG)["days"][Ts]
    pid = day.get("prog", {}).get("photo")
    check("photo: the check-in names its photo", bool(pid), str(day.get("prog")))
    raw = p.evaluate(RAW)
    check("photo: the log holds the name, never the picture", "data:image" not in raw and "base64" not in raw and len(raw) < 60000, str(len(raw)))
    got = p.evaluate(IDB, pid) if pid else None
    check("photo: it is kept on the phone, beside the log", bool(got), str(got))
    check("photo: as a JPEG, shrunk to 1280px on the long side",
          got and got["type"] == "image/jpeg" and max(got["w"], got["h"]) == 1280, str(got))
    check("photo: Save says so", p.evaluate(SAYS) == "Saved today’s check-in", p.evaluate(SAYS))
    check("photo: the row shows a camera and a note",
          p.locator('[data-pgday="%s"] .pg-meta > span:not(.off):not(.pg-w)' % Ts).count() == 2)
    p.click("#backupBtn"); p.wait_for_timeout(250)
    check("photo: a backup never carries it", "data:image" not in p.input_value("#backupText"))
    check("photo: and the backup says photos aren't in it", "Progress photos aren’t in it" in p.inner_text("#sheetNote"))
    p.click("#closeSheet"); p.wait_for_timeout(200)

    # ---------- 6. one check-in ----------
    p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(700)
    txt = p.evaluate(SHEET)
    check("view: a tapped date opens the whole check-in", "Waist is down an inch" in txt and "181.6 lb" in txt, txt[:120])
    check("view: its photo is shown", p.evaluate(IMG_OK, "#pgSheet img.pg-photo"))
    check("view: with no check-in before it, the weight stands alone", "since" not in txt, txt[:200])
    check("view: every control 44px", not p.evaluate(SIZES), str(p.evaluate(SIZES)))
    check("view: nothing later than the latest", p.locator("#pgNewer").is_disabled() and p.locator("#pgOlder").is_disabled())
    p.click("#pgClose"); p.wait_for_timeout(200)

    # ---------- 7. closed and opened again ----------
    p.reload(); p.wait_for_timeout(900)
    tab(p, "progress")
    p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(900)
    check("restart: the photo comes back from the phone's storage", p.evaluate(IMG_OK, "#pgSheet img.pg-photo"))
    p.click("#pgClose"); p.wait_for_timeout(200)

    # ---------- 8. today already has one; an earlier day ----------
    p.click("#pgNew"); p.wait_for_timeout(300)
    txt = p.evaluate(SHEET)
    check("again: New check-in on a day that has one opens it and says so",
          "Edit check-in" in txt and "already has a check-in" in txt and p.input_value("#pgNote") == "Waist is down an inch", txt[:160])
    D30 = ago(30)
    change_day(p, D30)
    txt = p.evaluate(SHEET)
    check("again: Change day goes to an earlier day, as a new check-in",
          "New check-in" in txt and "already" not in txt and p.input_value("#pgNote") == "" and not p.locator(".pg-slot.has-photo").count(), txt[:160])
    check("again: carrying that day's weight, not today's", p.input_value("#pgW") == "183.9", p.input_value("#pgW"))
    add_photo(p, jpeg(p, 1800, 2400, "#a08c7a"))
    p.fill("#pgNote", "Starting the cut"); save(p, 1200)
    check("again: saved on that day, and said so by its date",
          p.evaluate(LOG)["days"][D30].get("prog", {}).get("note") == "Starting the cut" and p.evaluate(SAYS) == "Saved the %s check-in" % md(D30),
          p.evaluate(SAYS))
    check("again: today's check-in was left alone", p.evaluate(LOG)["days"][Ts]["prog"].get("photo") == pid)
    # a future day can't be chosen
    p.click("#pgNew"); p.wait_for_timeout(250)
    p.click("#pgDayBtn"); p.wait_for_timeout(150)
    check("again: the day picker stops at today", p.get_attribute("#pgDay", "max") == Ts)
    p.evaluate("()=>{const f=document.getElementById('pgDay');f.value='2999-01-01';f.dispatchEvent(new Event('change',{bubbles:true}));}")
    p.wait_for_timeout(200)
    check("again: and a day after today is not taken", "For today" in p.evaluate(SHEET))
    p.click("#pgX"); p.wait_for_timeout(200)

    # ---------- 9. stepping, comparing ----------
    p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(500)
    txt = p.evaluate(SHEET)
    check("view: now it says how far the weight moved since the last check-in", "down 2.3 lb since %s" % md(D30) in txt, txt[:200])
    check("view: and counts them", "Check-in 2 of 2" in txt)
    p.click("#pgOlder"); p.wait_for_timeout(400)
    check("view: the arrow steps to the one before", "Starting the cut" in p.evaluate(SHEET) and p.locator("#pgOlder").is_disabled())
    p.click("#pgNewer"); p.wait_for_timeout(400)
    p.click("#pgCompare"); p.wait_for_timeout(700)
    txt = p.evaluate(SHEET)
    check("compare: from a day, against the photo before it",
          p.input_value("#pgA") == D30 and p.input_value("#pgB") == Ts, txt[:120])
    check("compare: side by side, both photos shown",
          p.locator(".pg-cmp img.pg-photo").count() == 2 and p.evaluate(IMG_OK, ".pg-cmp figure:nth-child(1) img")
          and p.evaluate(IMG_OK, ".pg-cmp figure:nth-child(2) img"))
    check("compare: the days and pounds between them", "30" in txt and "days apart" in txt.lower() and "−2.3 lb" in txt, txt)
    check("compare: both notes, by date", "Starting the cut" in txt and "Waist is down an inch" in txt)
    check("compare: every control 44px, every field 16px", not p.evaluate(SIZES), str(p.evaluate(SIZES)))
    p.click('[data-pgmode="slide"]'); p.wait_for_timeout(500)
    check("compare: the slider lays one photo over the other", p.locator("#pgSlide img.pg-photo").count() == 2)
    p.evaluate("()=>{const r=document.getElementById('pgCut');r.value=20;r.dispatchEvent(new Event('input',{bubbles:true}));}")
    check("compare: and dragging it moves the line",
          p.evaluate("document.getElementById('pgSlide').style.getPropertyValue('--cut')") == "20%")
    check("compare: the slider is 44px and its pickers too", not p.evaluate(SIZES), str(p.evaluate(SIZES)))
    p.click("#pgClose"); p.wait_for_timeout(200)
    check("compare: the top card offers first and latest", p.locator("#pgFirstLast").is_visible())
    p.click("#pgFirstLast"); p.wait_for_timeout(500)
    check("compare: first and latest", p.input_value("#pgA") == D30 and p.input_value("#pgB") == Ts)
    p.click("#pgX"); p.wait_for_timeout(200)
    since = p.inner_text("#pgSince")
    check("top: since the first check-in, the trend, the days and the photos",
          md(D30).lower() in since.lower() and "−2.3" in since and "30" in since and "lb on the trend" in since.lower(), since)

    # ---------- 10. the Log ----------
    tab(p, "log")
    cell = '.month.is-big [data-go="%s"]' % Ts
    check("log: today's cell carries the camera", p.locator(cell + " svg.pg-mark").count() == 1)
    check("log: and says so to a screen reader", "progress photo" in (p.get_attribute(cell, "aria-label") or ""))
    check("log: the legend explains the camera and the ring",
          "Progress photo" in p.inner_text(".legend") and "Check-in, no photo" in p.inner_text(".legend"))
    p.click(cell); p.wait_for_timeout(300)
    pk = p.inner_text("#peekSheet")
    check("log: the peek has a Progress line", "Photo · 181.6 lb · “Waist is down an inch”" in pk, pk)
    check("log: See check-in is a proper button", (p.locator("#peekProg").bounding_box() or {}).get("height", 0) >= 44)
    p.click("#peekProg"); p.wait_for_timeout(700)
    check("log: See check-in opens it on Progress",
          p.evaluate("document.querySelector('.tabs [aria-selected=true]').dataset.tab") == "progress" and "Waist is down an inch" in p.evaluate(SHEET))
    p.click("#pgClose"); p.wait_for_timeout(200)

    # ---------- 11. remove, undo, and gone for good ----------
    p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(500)
    p.click("#pgRemove"); p.wait_for_timeout(400)
    d1 = p.evaluate(LOG)
    check("remove: the check-in goes, its weight stays", "prog" not in d1["days"][Ts] and d1["days"][Ts].get("bw") == 181.6)
    check("remove: and says the weight stays", p.evaluate(SAYS) == "Removed today’s check-in · its weight stays", p.evaluate(SAYS))
    check("remove: the photo waits in case of Undo", pid in (d1.get("photoBin") or {}) and p.evaluate(IDB, pid) is not None)
    p.click("#undoBtn"); p.wait_for_timeout(400)
    d2 = p.evaluate(LOG)
    check("remove: Undo brings it back, photo and all",
          d2["days"][Ts].get("prog", {}).get("photo") == pid and pid not in (d2.get("photoBin") or {}))
    p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(600)
    check("remove: the photo shows again", p.evaluate(IMG_OK, "#pgSheet img.pg-photo"))
    # replacing a photo puts the old one in the bin too
    p.click("#pgEdit"); p.wait_for_timeout(300)
    check("edit: Edit opens it without Change day", "Edit check-in" in p.evaluate(SHEET) and not p.locator("#pgDayBtn").count())
    add_photo(p, jpeg(p, 900, 1200, "#6f6155"))
    save(p, 1200)
    d3 = p.evaluate(LOG)
    pid2 = d3["days"][Ts]["prog"].get("photo")
    check("edit: a changed photo says Changed", p.evaluate(SAYS) == "Changed today’s check-in", p.evaluate(SAYS))
    check("edit: a photo under 1280px is never blown up", (p.evaluate(IDB, pid2) or {}).get("h") == 1200, str(p.evaluate(IDB, pid2)))
    check("edit: and the old photo waits in the bin", pid2 != pid and pid in (d3.get("photoBin") or {}))
    p.reload(); p.wait_for_timeout(1300)
    keys = p.evaluate(IDBKEYS)
    check("bin: next time the app opens, the replaced photo is deleted", pid not in keys and pid2 in keys, str(keys))
    allerrs += errs; ctx.close()

    # ---------- 12. a photo this phone does not have ----------
    ctx, p, errs = phone(b, fixture({Ts: {"at": 1, "photo": "notonthisphone", "note": "From the old phone"},
                                     ago(3): {"at": 1, "note": "Rest day"}}))
    tab(p, "progress")
    p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(800)
    check("missing: a restored check-in says its photo isn't on this phone", "isn’t on this phone" in p.evaluate(SHEET))
    check("missing: and shows no broken image", not p.locator("#pgSheet img").count())
    p.click("#pgClose"); p.wait_for_timeout(200)
    tab(p, "log")
    rc = '.month.is-big [data-go="%s"]' % ago(3)
    if p.locator(rc).count():   # in this month's grid unless today is the 1st to 3rd
        check("log: a check-in without a photo has the ring", p.locator(rc + " .pg-ring").count() == 1)
    p.click('.month.is-big [data-go="%s"]' % Ts); p.wait_for_timeout(300)
    check("log: the peek tells a photo day from the rest", "Photo · 181.6 lb" in p.inner_text("#peekSheet"))
    allerrs += errs; ctx.close()

    # ---------- 13. kg ----------
    ctx, p, errs = phone(b, fixture(bwunit="kg"))
    tab(p, "progress"); p.click("#pgNew"); p.wait_for_timeout(250)
    check("kg: the weight is shown in kg", p.input_value("#pgW") == "82.4", p.input_value("#pgW"))
    p.fill("#pgNote", "kg phone"); save(p)
    check("kg: saving without touching it leaves the pounds exactly", p.evaluate(LOG)["days"][Ts].get("bw") == 181.6,
          str(p.evaluate(LOG)["days"][Ts].get("bw")))
    allerrs += errs; ctx.close()

    # ---------- 14. the iPhone app ----------
    phone_store = {"prefs": {}, "files": {}, "calls": []}

    def bridge(plugin, method, opts):
        phone_store["calls"].append((plugin, method, opts.get("directory")))
        if plugin == "Preferences":
            k = "CapacitorStorage." + opts.get("key", "")
            if method == "get": return {"value": phone_store["prefs"].get(k)}
            if method == "set": phone_store["prefs"][k] = opts.get("value", ""); return {}
            if method == "remove": phone_store["prefs"].pop(k, None); return {}
        if plugin == "Filesystem":
            # As @capacitor/filesystem 8.1.5 answers on iOS: a file that is not
            # there is refused with OS-PLUG-FILE-0008, deleting one included.
            path = opts.get("path", "")
            gone = {"error": "'%s' failed because file at '%s' does not exist." % (method, path),
                    "code": "OS-PLUG-FILE-0008"}
            if method == "writeFile": phone_store["files"][path] = opts.get("data", ""); return {}
            if method == "readFile":
                return {"data": phone_store["files"][path]} if path in phone_store["files"] else gone
            if method == "deleteFile":
                if path not in phone_store["files"]: return gone
                del phone_store["files"][path]; return {}
        if plugin in ("Haptics", "LocalNotifications"):
            return {"display": "granted"}
        return {"error": plugin + "." + method + " is not implemented"}

    SHELL = """(() => { const has = %s;
      window.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'ios',
        isPluginAvailable: (n) => has.indexOf(n) !== -1,
        nativePromise: (plugin, method, opts) => window.__native(plugin, method, opts || {})
          .then(r => { if (r && r.error) { const e = new Error(r.error); if (r.code) e.code = r.code; throw e; }
                       return r; }) }; })();"""

    def app(plugins):
        ctx = b.new_context(viewport={"width": 402, "height": 874}, has_touch=True, is_mobile=True)
        ctx.expose_function("__native", bridge)
        ctx.add_init_script(SHELL % json.dumps(plugins))
        p = ctx.new_page(); errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto(URL); p.wait_for_timeout(1000)
        if p.locator("#newsSheet").is_visible(): p.click("#newsDone"); p.wait_for_timeout(200)
        return ctx, p, errs

    phone_store["prefs"]["CapacitorStorage." + KEY] = json.dumps(fixture())
    ctx, p, errs = app(["Preferences", "Haptics", "LocalNotifications"])
    tab(p, "progress"); p.click("#pgNew"); p.wait_for_timeout(300)
    txt = p.evaluate(SHEET)
    check("app: a shell without the Filesystem plugin says photos come with the update",
          "Photos come with the next update of the iPhone app" in txt, txt[:200])
    check("app: and offers no photo buttons", not p.locator("#pgCam, #pgLib, #pgShoot").count())
    p.fill("#pgNote", "From the app"); save(p)
    kept = json.loads(phone_store["prefs"].get("CapacitorStorage." + KEY) or "{}")
    check("app: a note still saves, into native storage",
          kept.get("days", {}).get(Ts, {}).get("prog", {}).get("note") == "From the app")
    check("app: and the missing plugin is never called", not any(c[0] == "Filesystem" for c in phone_store["calls"]))
    allerrs += errs; ctx.close()

    phone_store["calls"].clear()
    ctx, p, errs = app(["Preferences", "Haptics", "LocalNotifications", "Filesystem"])
    tab(p, "progress"); p.click("#pgNew"); p.wait_for_timeout(300)
    add_photo(p, jpeg(p))
    save(p, 1500)
    kept = json.loads(phone_store["prefs"].get("CapacitorStorage." + KEY) or "{}")
    apid = kept.get("days", {}).get(Ts, {}).get("prog", {}).get("photo")
    path = "mntl-dt-photos/%s.jpg" % apid
    check("app: with the plugin, the photo is a file of the app's own",
          apid and path in phone_store["files"] and len(phone_store["files"][path]) > 1000, str(list(phone_store["files"])[:3]))
    check("app: in its data folder, not in the log",
          any(c[:2] == ("Filesystem", "writeFile") and c[2] == "DATA" for c in phone_store["calls"])
          and "base64" not in (phone_store["prefs"].get("CapacitorStorage." + KEY) or ""))
    allerrs += errs; ctx.close()
    ctx, p, errs = app(["Preferences", "Haptics", "LocalNotifications", "Filesystem"])
    tab(p, "progress"); p.click('[data-pgday="%s"]' % Ts); p.wait_for_timeout(900)
    check("app: and read back from there after a restart", p.evaluate(IMG_OK, "#pgSheet img.pg-photo"))
    p.click("#pgRemove"); p.wait_for_timeout(300)
    allerrs += errs; ctx.close()
    ctx, p, errs = app(["Preferences", "Haptics", "LocalNotifications", "Filesystem"])
    p.wait_for_timeout(500)
    check("app: a removed photo's file is deleted on the next open", path not in phone_store["files"])
    allerrs += errs; ctx.close()
    # Nothing was saved on that open, so the stored bin still names the photo,
    # and the next open asks to delete a file that is already gone. The plugin
    # refuses that; the bin must let the name go all the same.
    before = json.loads(phone_store["prefs"].get("CapacitorStorage." + KEY) or "{}")
    check("app: (the stored bin still names the deleted photo)", apid in (before.get("photoBin") or {}),
          str(before.get("photoBin")))
    phone_store["calls"].clear()
    ctx, p, errs = app(["Preferences", "Haptics", "LocalNotifications", "Filesystem"])
    p.wait_for_timeout(500)
    tab(p, "progress"); p.click("#pgNew"); p.wait_for_timeout(300)
    p.fill("#pgNote", "After the bin"); save(p)
    kept = json.loads(phone_store["prefs"].get("CapacitorStorage." + KEY) or "{}")
    check("app: a photo file already gone leaves the bin at the next save",
          any(c[:2] == ("Filesystem", "deleteFile") for c in phone_store["calls"])
          and apid not in (kept.get("photoBin") or {})
          and kept.get("days", {}).get(Ts, {}).get("prog", {}).get("note") == "After the bin",
          str(kept.get("photoBin")))
    allerrs += errs; ctx.close()

    # ---------- 15. seven tabs on a 320px phone ----------
    ctx, p, errs = phone(b, fixture({Ts: {"at": 1, "note": "n"}}, coach=True), w=320, h=568)
    tabs = p.evaluate("""()=>[...document.querySelectorAll('.tabs button')].filter(b=>b.getClientRects().length).map(b=>{
      const r=b.getBoundingClientRect(),l=b.querySelector('.tl').getBoundingClientRect();
      return [b.dataset.tab,Math.round(r.width),Math.round(r.height),l.left>=r.left-1&&l.right<=r.right+1&&r.right<=innerWidth+1]})""")
    check("320: seven tabs with Coach on", len(tabs) == 7, str(tabs))
    check("320: each one at least 44px wide and 48px tall", all(t[1] >= 44 and t[2] >= 48 for t in tabs), str(tabs))
    check("320: every label inside its tab, nothing off the side", all(t[3] for t in tabs), str(tabs))
    tab(p, "progress")
    check("320: the tab fits the phone", p.evaluate("document.documentElement.scrollWidth") <= 320)
    p.click("#pgNew"); p.wait_for_timeout(300)
    check("320: the editor fits and its controls are 44px",
          p.evaluate("document.documentElement.scrollWidth") <= 320 and not p.evaluate(SIZES), str(p.evaluate(SIZES)))
    allerrs += errs; ctx.close()

    check("no page errors", not allerrs, "; ".join(allerrs[:4]))
    b.close()

srv.shutdown()
fails = [r for r in res if r[0] == "FAIL"]
for r in res:
    print(("  ✓ " if r[0] == "PASS" else "  ✕ ") + r[1] + (("  [" + r[2] + "]") if r[0] == "FAIL" and r[2] else ""))
print("\n%d passed, %d FAILED" % (len(res) - len(fails), len(fails)))
raise SystemExit(1 if fails else 0)
