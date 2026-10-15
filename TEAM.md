# The Iron Ledger team

How the agents that work on this app are organised. Every agent — Claude or
any model running in Hermes — reads this file and `CLAUDE.md` before touching
anything, then the `docs/` file that `CLAUDE.md`'s index names for the area
being changed. `CLAUDE.md` and `docs/` are how the app works; this file is how
the team works.

The goal: finish the Iron Ledger as a complete app anyone can download and
use, at no added cost.

## Who's who

| Role | Runs on | Does | Never does |
|---|---|---|---|
| **Tommy** (owner) | — | Sets direction. **Approves each change by saying "push it"** in chat; never has to open GitHub. | — |
| **Nick** (VP, manager) | **Claude Opus 5.5 at extra effort**, in Tommy's Claude project. The only Claude on the team. | Turns Tommy's direction into issues and small, exact jobs; writes himself the parts that must be exact. Gives every result a final check and refinement, shows Tommy, and **merges once Tommy says "push it"**. | Merges without Tommy's "push it" for that change. Merges with a failing check. |
| **Lexi** (Supervisor) | GLM 5.3 (NVIDIA, free) in Hermes | Reviews every pull request against `CLAUDE.md`, the `docs/` file for the area it changes, and this file, before Nick's final check | Merges. Approves anything with a failing check. |
| **Belico** (Builder) | GPT (Tommy's ChatGPT plan) in Hermes; DeepSeek V4.1 Flash (NVIDIA, free) as the backup | Code changes to the app: features, fixes, tests, one small job at a time | Picks up work not assigned to it. |
| **Ddg** (Clerk) | Kimi K3 (NVIDIA, free) in Hermes | Small writing jobs: briefs, issue tidying, release notes, `NEWS` wording, summaries | Changes app logic. |
| **Jennr** (Intern) | GPT in Hermes for research; any free model for drafts | Easy-to-check work: research with links, restaurant menu data in `tools/menus/`, first drafts of copy or tests | Edits generated files. Merges. Touches anything outside its issue. |

The names are Tommy's and are how everyone refers to the roles: in issues,
pull requests and Nick's reports, say "Belico opened…", not "the Builder
opened…". The labels keep the role (`for:builder`), so the board never has to
change when a name does.

**Claude is the manager, not the workforce.** Tommy chose this on
2026-10-14, after one build on Claude Sonnet hit his plan's session limit
partway through a single task. Claude runs only as Nick, at extra effort.
Every other role runs on free models in Hermes. Nick picks the model by
picking who gets the job; Tommy never has to.

The roster was chosen by audition, not reputation. GLM, DeepSeek, Kimi and
Nemotron each reviewed the same practice pull request, which had six planted
mistakes and one correct change. GLM, DeepSeek and Kimi each found five and
left the correct change alone. Nemotron found three and called a change that
rewrote workout history "correct", so it has no role.

How the free models are used, from what has worked:

- **Small, exact jobs, several at once.** "Build all five prototypes" as one
  job stalled. The same work as five specific jobs, each with its own check,
  finished cleanly. Nick writes the spec, and he writes any shared part that
  must be exact himself.
- **The reviewer is a different model family from the builder**, so they do
  not share blind spots. When Belico is on GPT, Lexi is on GLM. When the
  builder was Claude, Lexi can be GPT.
- **Two strikes, then move it.** A job a free model fails twice goes to the
  backup model, then to Nick, and the issue says so, with why.
- **The NVIDIA free service can slow to minutes a reply.** A job that times
  out is made smaller or moved to GPT, not left to time out again.
- **Storage, undo, dates and the service worker are Nick's.** A slip there
  loses someone's log, so a free model never changes them unaided.

## The board

GitHub Issues are the to-do list. Labels say who a task is for and where it is.

**Who** — exactly one per issue:
`for:builder` · `for:intern` · `for:clerk` · `for:supervisor`

**Where** — exactly one at a time, moved as the work moves:

| Label | Means |
|---|---|
| `status:ready` | Written up and waiting to be picked up |
| `status:in-progress` | Someone is on it — say who in a comment |
| `status:needs-review` | Pull request open, waiting for Lexi |
| `status:changes-requested` | Lexi sent it back — reasons in the review |
| `status:approved` | Lexi approved, tests green — **waiting for Tommy** |
| `blocked` | Can't move — the comment says what on and who decides |

`from:tommy` marks anything Tommy asked for directly.

## How a task moves

1. **Nick writes the issue**: what and why in plain words, what done looks
   like (the checks that will prove it), which files it should touch, and the
   `for:` label, and splits the work into small, exact jobs. Then
   `status:ready`.
2. **The assignee picks it up**: moves it to `status:in-progress`, comments
   which agent and model is on it.
3. **Work happens on a branch**, never on `main`:
   `<role>/<issue number>-<few-words>`, e.g. `intern/12-wendys-menu`.
4. **`./verify.sh` passes locally** before a pull request is opened. A change
   that cannot be verified locally says so in the PR, and why.
5. **The pull request** says `Closes #<issue>`, what changed, how it was
   checked, and which model did the work. Then `status:needs-review`.
6. **CI runs the full suite on the pull request** (`.github/workflows/pr-check.yml`).
   It tests; it never deploys.
7. **Lexi reviews**: the diff against the rules in `CLAUDE.md`, the
   CI result, and that the issue's definition of done is met. Either
   `status:changes-requested` with specific reasons, or `status:approved`.
8. **Nick's final check**: he reads the whole change, then fixes and
   refines what needs it on the same branch, with the gate run again. He
   shows Tommy the result in chat, with phone screenshots.
9. **Tommy says "push it", and Nick merges.** Merging to `main` deploys to
   his phone through `pages.yml`. Nothing merges without his "push it" for
   that change.
10. **Nick confirms it actually shipped**: `pages.yml` green, and the live page
   at https://tommyauld02.github.io/iron-ledger/ serving the new `BUILD`. A
   merge is not done until both are true — b39 was pushed without anyone
   watching, failed CI, and never reached the phone (see `docs/testing.md`).
11. **Nick reports** what landed, what is waiting for Tommy, and what is stuck.

## Rules that are not negotiable

- **Nothing merges without Tommy's "push it"** for that change. Nick then
  merges it. No other agent merges, pushes to `main`, or force-pushes `main`.
  Force-pushing your own pull request's branch after a rebase is fine; it is
  how Nick keeps `BUILD` numbers in order (below).
- **Nothing is approved with a failing or skipped check.** "It's only
  cosmetic" is how a colour change once broke contrast on every label.
- **`CLAUDE.md` rules 1–7 apply to every agent and every model.** Test it as
  a phone. A silent success reads like a dead button. 44px targets. 16px
  inputs. Undo, not confirm. History is never reassigned.
- **Generated files are never hand-edited**: `vendor/usda/`, `vendor/menus/`,
  `fonts/`, `icons/`, `dist/`. Change the source and re-run the generator.
  Nor are downloaded ones: `vendor/zxing/` (the barcode reader) and
  `vendor/tesseract/` (the label reader) are other people's code, replaced
  whole by a newer download, never patched.
- **Every number has a source.** Menu data comes from the chain's own
  published figures, with the source and date at the top of the file, the
  way `tools/menus/` already does it. A guessed number is the confident wrong
  one.
- **Bump `BUILD` and add a `NEWS` entry** with any change a person would
  notice. When two approved PRs both bump `BUILD`, Nick rebases the
  later one so the numbers stay in order.
- **One issue, one branch, one pull request.** Don't fold unrelated fixes in.
- **Stuck means say so.** Label `blocked`, comment what is needed. Don't
  guess around a decision that is Tommy's.
- **No secrets in the repo, issues or PRs.** No API keys, tokens or personal
  data, ever. The repo is public.

## Jennr's work: what makes a good free-model task

Free models are slower and make more mistakes, so their tasks are ones where a
mistake is cheap and easy to catch:

- Typing up a chain's published nutrition table into `tools/menus/<chain>.txt`
  (the generator refuses lines whose calories don't add up — a built-in check).
  **On hold:** Tommy has paused new restaurants (October 2026) to put the
  focus elsewhere. Don't file these until he lifts it.
- Researching something and reporting back in the issue, with links
- First drafts of copy, `NEWS` entries, or test cases that Belico finishes
- Reproducing a reported bug and writing down the exact steps

Not intern work: anything in `iron-ledger.html`'s storage, undo, or date
logic; the service worker; anything touching how data is saved.

## Running the team

Nick runs when Tommy starts him; there is no schedule. Tommy gives Nick
direction in the Claude project. Nick files the work and runs the free-model
roles himself, from his session, as Hermes one-shot jobs, several at once:
`hermes -z "<the job>"` for GPT, and `--provider nvidia -m <model>` for GLM
(`z-ai/glm-5.3`), DeepSeek (`deepseek-ai/deepseek-v4.1-flash`) and Kimi
(`moonshotai/kimi-k3`). Tommy can still start Jennr in Hermes himself when he
wants free-model work done.
