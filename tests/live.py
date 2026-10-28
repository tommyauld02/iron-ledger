"""Live updates in the iPhone app: what it takes, when, and what it refuses.

Between store builds, every Pages deploy publishes live/manifest.json, and the
iPhone app downloads a newer build through @capgo/capacitor-updater
(docs/ios.md, "How an update reaches phones"). This suite stands in for both
ends: the manifest is answered by a route here, and window.Capacitor answers
the updater and native storage from dicts held in Python, like tests/native.py.

It checks that:
- every start tells the updater the app is ready, after the log has loaded,
  so a build that works is never rolled back
- a newer build made for this shell is downloaded, file by file with hashes,
  and the app says so; nothing is switched while the app is in use
- the plugin's next() is never used: it swaps on going to the background
- the switch happens at a cold start, before the log is read or drawn
- the guards: an older or equal build, a build needing a newer shell, a build
  that failed to start here before, and a malformed manifest are all left alone
- an updater that never answers cannot hold the app's start up
- a failed download is named in the Backup panel and claims nothing
- resuming checks again, but not more than every half hour
- the web build never asks
- tools/make-www.mjs --manifest describes exactly the files the app ships,
  with the right hashes and the shell they need (needs Node; skipped if absent)
- the shell's version went up if the shell changed (tools/shell-version.py)
"""
from playwright.sync_api import sync_playwright
import os, io, re, json, shutil, hashlib, tempfile, subprocess, datetime, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = ROOT.replace("\\", "/"); d = "/" + d if d[1:2] == ":" else d
FILE = "file://" + d + "/mntl-dt.html"
SRC = io.open(os.path.join(ROOT, "mntl-dt.html"), encoding="utf-8").read()
BUILD = re.search(r'BUILD = "([^"]+)"', SRC).group(1)
LIVE_URL = re.search(r'LIVE_URL = "([^"]+)"', SRC).group(1)
DAY, N = BUILD.split(".")
NEWER = "%s.%d" % (DAY, int(N) + 1)
OLDER = "%s.%d" % (DAY, int(N) - 1)

res = []
def check(n, ok, det=""): res.append(("PASS" if ok else "FAIL", n, det))

spec = importlib.util.spec_from_file_location("shellversion", os.path.join(ROOT, "tools", "shell-version.py"))
shell = importlib.util.module_from_spec(spec); spec.loader.exec_module(shell)
SHELL = shell.marketing_version()

# --- the phone, outside the WebView ------------------------------------------
st = {}
def reset(native=SHELL, bundles=None, failed=None, download_fails=False):
    st.clear()
    st.update(native=native, bundles=list(bundles or []), failed=failed, download_fails=download_fails,
              calls=[], downloads=[], prefs={}, fetches=0, manifest=None)

def bridge(plugin, method, opts):
    st["calls"].append((plugin, method))
    if plugin == "Preferences":
        k = "CapacitorStorage." + opts.get("key", "")
        if method == "get": return {"value": st["prefs"].get(k)}
        if method == "set": st["prefs"][k] = opts.get("value", ""); return {}
    if plugin == "CapacitorUpdater":
        if method == "notifyAppReady": return {}
        if method == "getFailedUpdate":
            f, st["failed"] = st["failed"], None
            return {"bundle": f} if f else {}
        if method == "list": return {"bundles": st["bundles"]}
        if method == "current": return {"bundle": {"id": "builtin", "version": "builtin"}, "native": st["native"]}
        if method == "download":
            st["downloads"].append(opts)
            if st["download_fails"]: return {"error": "Failed to download: checksum mismatch"}
            b = {"id": "dl%d" % len(st["downloads"]), "version": opts.get("version"), "status": "pending"}
            st["bundles"].append(b); return b
        if method in ("set", "next"): st[method] = opts; return {}
    return {"error": "%s.%s is not implemented" % (plugin, method)}

def called(plugin, method): return (plugin, method) in st["calls"]
def at(plugin, method):          # where in the order of calls; never if it was not called
    c = (plugin, method)
    return st["calls"].index(c) if c in st["calls"] else float("inf")

BRIDGE = """(() => {
  const hang = %s;
  window.Capacitor = {
    isNativePlatform: () => true,
    getPlatform: () => 'ios',
    isPluginAvailable: (name) => name === 'Preferences' || name === 'CapacitorUpdater',
    nativePromise: (plugin, method, opts) => (hang && plugin === 'CapacitorUpdater')
      ? new Promise(() => {})
      : window.__native(plugin, method, opts || {}).then(r => r && r.error ? Promise.reject(new Error(r.error)) : r)
  };
})();"""
# Date.now() that a test can move on, to cross the half-hour between checks.
CLOCK = """(() => { let skew = 0; const now = Date.now.bind(Date);
  Date.now = () => now() + skew; window.__later = ms => { skew += ms; }; })();"""

def manifest(build=NEWER, minNative=None, files=None):
    return {"build": build, "minNative": SHELL if minNative is None else minNative,
            "files": files if files is not None else [
                {"file_name": "index.html", "file_hash": "ab" * 32,
                 "download_url": "https://example.test/index.html?b=" + build}]}

PHONE = {"width": 402, "height": 874}

def open_app(b, man=None, hang=False, url=FILE, native=True, settle=1200):
    ctx = b.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    ctx.expose_function("__native", bridge)
    if native: ctx.add_init_script(BRIDGE % ("true" if hang else "false"))
    ctx.add_init_script(CLOCK)
    st["manifest"] = man
    def answer(route):
        st["fetches"] += 1
        if st["manifest"] is None: route.fulfill(status=404, body="")
        else: route.fulfill(status=200, content_type="application/json",
                            headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(st["manifest"]))
    ctx.route(LIVE_URL + "*", answer)
    p = ctx.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(url); p.wait_for_timeout(settle)
    try: p.click("text=Got it", timeout=500)
    except Exception: pass
    return ctx, p, errs

def notices(p): return p.evaluate("() => document.body.innerText")


with sync_playwright() as pw:
    b = pw.chromium.launch()
    allerrs = []

    # ---- 1. nothing new: ready is said, nothing is fetched twice -------------
    reset()
    ctx, p, errs = open_app(b, manifest(build=BUILD))
    check("every start tells the updater the app is ready", called("CapacitorUpdater", "notifyAppReady"))
    check("only once the log has loaded", called("Preferences", "get")
          and at("Preferences", "get") < at("CapacitorUpdater", "notifyAppReady"), str(st["calls"][:8]))
    check("it asks Pages what the newest build is", st["fetches"] == 1, "%d fetches" % st["fetches"])
    check("the same build is not downloaded", not st["downloads"])
    allerrs += errs; ctx.close()

    # ---- 2. a newer build for this shell -----------------------------------
    reset()
    ctx, p, errs = open_app(b, manifest())
    dl = st["downloads"][0] if st["downloads"] else {}
    check("a newer build is downloaded", dl.get("version") == NEWER, str(dl)[:120])
    check("file by file, each with its hash", dl.get("manifest") == manifest()["files"])
    check("and the app says it is ready for next time",
          ("Update b%s opens next time you start the app" % NEWER.split(".")[1]) in notices(p),
          notices(p)[-200:])
    check("nothing is switched while the app is in use", "set" not in st and "next" not in st)
    p.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))"); p.wait_for_timeout(400)
    check("coming back within half an hour does not ask again", st["fetches"] == 1, "%d" % st["fetches"])
    p.evaluate("() => window.__later(31 * 60 * 1000)")
    p.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))"); p.wait_for_timeout(800)
    check("after half an hour, coming back asks again", st["fetches"] == 2, "%d" % st["fetches"])
    check("and the build already waiting is not downloaded again",
          [x.get("version") for x in st["downloads"]] == [NEWER], str([x.get("version") for x in st["downloads"]]))
    p.evaluate("() => window.__later(31 * 60 * 1000)")
    st["manifest"] = manifest(build="%s.%d" % (DAY, int(N) + 2))
    p.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))"); p.wait_for_timeout(800)
    check("while a newer one than that is",
          [x.get("version") for x in st["downloads"]] == [NEWER, "%s.%d" % (DAY, int(N) + 2)],
          str([x.get("version") for x in st["downloads"]]))
    check("next(), which swaps on going to the background, is never used", not called("CapacitorUpdater", "next"))
    allerrs += errs; ctx.close()

    # ---- 3. the cold start that switches -----------------------------------
    reset(bundles=[{"id": "dl1", "version": NEWER, "status": "pending"},
                   {"id": "old", "version": OLDER, "status": "pending"}])
    ctx, p, errs = open_app(b, manifest(build=NEWER), settle=500)
    check("a cold start switches to the waiting build", st.get("set") == {"id": "dl1"}, str(st.get("set")))
    check("before the log is read or anything drawn", not called("Preferences", "get"), str(st["calls"]))
    p.wait_for_timeout(3500)
    # the stand-in does not reload, which is the case the app must survive too
    check("if the switch never comes, the app starts anyway", called("Preferences", "get")
          and "TODAY" in p.evaluate("() => document.getElementById('view').innerText").upper())
    allerrs += errs; ctx.close()

    # ---- 4. what is left alone ---------------------------------------------
    for name, man, kw in (
        ("an older build", manifest(build=OLDER), {}),
        ("a build that needs a newer shell", manifest(minNative="%s.1" % SHELL), {}),
        ("a manifest with no shell named", dict(manifest(), minNative=""), {}),
        ("a malformed build", manifest(build="next"), {}),
        ("a build with no files", manifest(files=[]), {}),
    ):
        reset(**kw)
        ctx, p, errs = open_app(b, man)
        check("left alone: " + name, not st["downloads"] and "set" not in st, str(st["downloads"])[:80])
        allerrs += errs; ctx.close()
    # numbers, not strings: shell 1.10 is newer than 1.9
    reset(native="1.10")
    ctx, p, errs = open_app(b, manifest(minNative="1.9"))
    check("shell versions compare as numbers (1.10 runs a 1.9 build)", len(st["downloads"]) == 1)
    allerrs += errs; ctx.close()

    # ---- 5. a build that failed to start here ------------------------------
    reset(failed={"id": "dl1", "version": NEWER, "status": "error"})
    ctx, p, errs = open_app(b, manifest())
    check("a build that was rolled back is not downloaded again", not st["downloads"])
    allerrs += errs; ctx.close()
    # the note of it lives in the WebView, so the next start is a reload here
    reset(failed={"id": "dl1", "version": NEWER, "status": "error"})
    ctx, p, errs = open_app(b, None)
    st["bundles"] = [{"id": "dl1", "version": NEWER, "status": "pending"}]
    p.reload(); p.wait_for_timeout(1200)
    check("nor switched to at the next start", "set" not in st, str(st.get("set")))
    allerrs += errs; ctx.close()

    # ---- 6. an updater that never answers ----------------------------------
    reset()
    ctx, p, errs = open_app(b, manifest(), hang=True, settle=2600)
    check("an updater that never answers cannot hold up the start",
          called("Preferences", "get") and "TODAY" in p.evaluate("() => document.getElementById('view').innerText").upper())
    allerrs += errs; ctx.close()

    # ---- 7. a download that fails -------------------------------------------
    reset(download_fails=True)
    ctx, p, errs = open_app(b, manifest())
    check("a failed download claims nothing", "opens next time" not in notices(p))
    p.click("#backupBtn"); p.wait_for_timeout(300)
    diag = p.eval_on_selector("#diag", "e => e.textContent")
    check("and the Backup panel names it", "live update" in diag and "checksum" in diag, diag[:140])
    allerrs += errs; ctx.close()

    # ---- 8. the web build ----------------------------------------------------
    reset()
    ctx, p, errs = open_app(b, manifest(), native=False)
    check("the web build never asks Pages for live updates", st["fetches"] == 0)
    check("nor calls the updater", not any(c[0] == "CapacitorUpdater" for c in st["calls"]))
    allerrs += errs; ctx.close()

    check("no page errors", not allerrs, str(allerrs[:3]))
    b.close()

# ---- 9. the manifest Pages publishes ----------------------------------------
node = shutil.which("node")
if not node:
    check("the published manifest (needs Node, not found: SKIPPED)", True)
else:
    tmp = tempfile.mkdtemp()
    try:
        out, man = os.path.join(tmp, "bundle"), os.path.join(tmp, "live", "manifest.json")
        r = subprocess.run([node, os.path.join(ROOT, "tools", "make-www.mjs"), "--out", out,
                            "--manifest", man, "--base", "https://example.test/app/"],
                           capture_output=True, text=True)
        check("make-www.mjs writes the manifest", r.returncode == 0 and os.path.exists(man), r.stderr[-200:])
        m = json.load(io.open(man, encoding="utf-8"))
        names = sorted(f["file_name"] for f in m["files"])
        shipped = sorted(os.path.relpath(os.path.join(dp, f), out).replace(os.sep, "/")
                         for dp, _, fs in os.walk(out) for f in fs)
        check("it names every file the app ships, and nothing else", names == shipped,
              "%d named, %d shipped" % (len(names), len(shipped)))
        check("with the app itself as index.html", "index.html" in names and
              io.open(os.path.join(out, "index.html"), "rb").read() == io.open(os.path.join(ROOT, "mntl-dt.html"), "rb").read())
        check("and no service worker or video", not any(n == "sw.js" or n.startswith("media/") for n in names))
        bad = [f["file_name"] for f in m["files"]
               if hashlib.sha256(io.open(os.path.join(out, f["file_name"]), "rb").read()).hexdigest() != f["file_hash"]]
        check("every hash is the file's SHA-256", not bad, str(bad[:3]))
        check("every file is fetched from Pages, marked with its build",
              all(f["download_url"].startswith("https://example.test/app/") and f["download_url"].endswith("?b=" + BUILD)
                  for f in m["files"]))
        check("it carries this BUILD and the shell it needs", m["build"] == BUILD and m["minNative"] == SHELL,
              "%s / %s" % (m["build"], m["minNative"]))
        r = subprocess.run([node, os.path.join(ROOT, "tools", "make-www.mjs"), "--out", ROOT],
                           capture_output=True, text=True)
        check("it refuses to empty the repo", r.returncode != 0 and os.path.exists(os.path.join(ROOT, "mntl-dt.html")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---- 10. the app looks where Pages publishes -----------------------------------
pages = io.open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8").read()
base = re.search(r"--base (https://\S+/)", pages)
check("the app reads the manifest where Pages publishes it",
      base is not None and "--manifest _site/live/manifest.json" in pages
      and base.group(1) + "live/manifest.json" == LIVE_URL, base.group(1) if base else "no --base in pages.yml")

# ---- 11. the shell's version is honest ---------------------------------------
fp, led = shell.fingerprint(), shell.ledger()
check("the shell's version is recorded with this shell (tools/shell-version.py)",
      led.get(SHELL) == fp,
      "MARKETING_VERSION %s: %s" % (SHELL, "recorded" if led.get(SHELL) == fp else
                                    "the shell changed: raise MARKETING_VERSION in Xcode, then run tools/shell-version.py --record"
                                    if SHELL in led else "not recorded: run tools/shell-version.py --record"))

for s, n, det in res: print("%-6s %-66s %s" % (s, n, " / ".join(l.strip() for l in str(det).splitlines() if l.strip())[:100]))
bad = sum(1 for s, _, _ in res if s == "FAIL")
print("\n%d passed, %d FAILED" % (len(res) - bad, bad))
raise SystemExit(1 if bad else 0)
