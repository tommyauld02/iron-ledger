// Assembles www/, the folder Capacitor copies into the iPhone app.
//
// mntl-dt.html stays the one source of truth. The app needs it at index.html,
// so the copy is made here, every time, and never committed — the same rule
// pages.yml follows, because a second copy in the repo is how this project
// once spent a while testing green against a stale build.
//
//   npm run www     just this
//   npm run sync    this, then `cap sync ios` (what you run before Xcode)
//
// Left out on purpose: sw.js (the app ships its own files, so there is
// nothing for a service worker to keep, and the app never registers one
// inside the shell) and media/ (the b69 walkthrough video, which no longer
// shows in What's new).
import { cpSync, mkdirSync, rmSync, statSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "www");

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT);
cpSync(join(ROOT, "mntl-dt.html"), join(OUT, "index.html"));
for (const f of ["manifest.webmanifest"]) cpSync(join(ROOT, f), join(OUT, f));
for (const d of ["fonts", "icons", "vendor"]) cpSync(join(ROOT, d), join(OUT, d), { recursive: true });

const build = /BUILD = "([^"]+)"/.exec(readFileSync(join(OUT, "index.html"), "utf8"))[1];
const size = (p) => statSync(p).size;
console.log(`www/ assembled from mntl-dt.html, BUILD ${build} (${(size(join(OUT, "index.html")) / 1024).toFixed(0)} KB)`);
