// Assembles www/, the folder Capacitor copies into the iPhone app, and the
// live-update manifest that tells installed apps about a newer one.
//
// mntl-dt.html stays the one source of truth. The app needs it at index.html,
// so the copy is made here, every time, and never committed — the same rule
// pages.yml follows, because a second copy in the repo is how this project
// once spent a while testing green against a stale build.
//
//   npm run www     just this
//   npm run sync    this, then `cap sync ios` (what you run before Xcode)
//   node tools/make-www.mjs --out <dir> --manifest <file> --base <url>
//                   what pages.yml runs: the same files, plus a manifest
//                   naming each one, its SHA-256 and where Pages serves it
//
// Left out on purpose: sw.js (the app ships its own files, so there is
// nothing for a service worker to keep, and the app never registers one
// inside the shell) and media/ (the b69 walkthrough video, which no longer
// shows in What's new).
import { cpSync, mkdirSync, rmSync, statSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const arg = (name) => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : null; };
const OUT = arg("--out") ? resolve(arg("--out")) : join(ROOT, "www");

// It is emptied first, so it must never be the repo or anything holding it.
if ((ROOT + sep).startsWith(OUT + sep)) throw new Error("--out must be a folder of its own, not " + OUT);
rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
cpSync(join(ROOT, "mntl-dt.html"), join(OUT, "index.html"));
for (const f of ["manifest.webmanifest"]) cpSync(join(ROOT, f), join(OUT, f));
for (const d of ["fonts", "icons", "vendor"]) cpSync(join(ROOT, d), join(OUT, d), { recursive: true });

const build = /BUILD = "([^"]+)"/.exec(readFileSync(join(OUT, "index.html"), "utf8"))[1];
const size = (p) => statSync(p).size;
console.log(`${relative(process.cwd(), OUT) || "."}/ assembled from mntl-dt.html, BUILD ${build} (${(size(join(OUT, "index.html")) / 1024).toFixed(0)} KB)`);

// The live-update manifest. minNative is the shell this build was made with —
// MARKETING_VERSION in the Xcode project, its one home — so a phone with an
// older shell, which may lack a plugin this build uses, leaves it alone
// (tools/shell-version.py keeps that version honest). Each URL carries the
// build, so no cache between Pages and the phone can answer with an older
// copy of a file; one that did would fail its hash and be fetched again.
const MANIFEST = arg("--manifest");
if (MANIFEST) {
  const base = arg("--base");
  if (!base || !/^https:\/\/.+\/$/.test(base)) throw new Error("--base must be an https URL ending in /");
  const proj = readFileSync(join(ROOT, "ios", "App", "App.xcodeproj", "project.pbxproj"), "utf8");
  const versions = new Set([...proj.matchAll(/MARKETING_VERSION = ([^;]+);/g)].map((m) => m[1].trim()));
  if (versions.size !== 1) throw new Error("MARKETING_VERSION differs between configurations: " + [...versions]);
  const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(d, e.name)) : [join(d, e.name)]);
  const files = walk(OUT).map((full) => relative(OUT, full).split(sep).join("/")).sort().map((name) => ({
    file_name: name,
    file_hash: createHash("sha256").update(readFileSync(join(OUT, name))).digest("hex"),
    download_url: base + name.split("/").map(encodeURIComponent).join("/") + "?b=" + build,
  }));
  mkdirSync(dirname(resolve(MANIFEST)), { recursive: true });
  writeFileSync(resolve(MANIFEST),
    JSON.stringify({ build, minNative: [...versions][0], files }, null, 1) + "\n");
  console.log(`${MANIFEST}: BUILD ${build}, needs shell ${[...versions][0]}, ${files.length} files`);
}
