# The Iron Ledger team

How the agents that work on this app are organised. Every agent — Claude or
any model running in Hermes — reads this file and `CLAUDE.md` before touching
anything. `CLAUDE.md` is how the app works; this file is how the team works.

The goal: finish the Iron Ledger as a complete app anyone can download and
use, at no added cost.

## Who's who

| Role | Runs on | Does | Never does |
|---|---|---|---|
| **Tommy** (owner) | — | Sets direction. **Approves and merges every pull request.** | — |
| **Nick** (VP) | Claude Opus, in Tommy's Claude project | Turns Tommy's direction into issues, assigns them, runs the team, reports back to Tommy | Merges. Ships without Tommy. |
| **Lexi** (Supervisor) | Claude Sonnet | Reviews every pull request against `CLAUDE.md` and this file; sends work back or marks it approved | Merges. Approves anything with a failing check. |
| **Belico** (Builder) | Claude Sonnet | Code changes to the app: features, fixes, tests | Picks up work not assigned to it. |
| **Ddg** (Clerk) | Claude Haiku | Small jobs: tidying issues, release notes, `NEWS` wording, summaries | Changes app logic. |
| **Jennr** (Intern) | Free models in Hermes (Kimi, GLM, DeepSeek, Nemotron, GPT via ChatGPT) | Easy-to-check work: restaurant menu data in `tools/menus/`, research, drafts of tests or copy, first passes | Edits generated files. Merges. Touches anything outside its issue. |

The names are Tommy's and are how everyone refers to the roles: in issues,
pull requests and Nick's reports, say "Belico opened…", not "the Builder
opened…". The labels keep the role (`for:builder`), so the board never has to
change when a name does.

**The task picks the model, and Tommy never has to.** Each role runs on the
model in its row, and the cheapest model that can do a job well gets it: Nick
chooses the model by choosing who gets the issue. Opus plans and summarises;
it does not do the heavy lifting. When a task turns out harder than its role's
model handles — Belico going round in circles, Jennr's draft unusable — Nick
moves it up a model (Haiku → Sonnet → Opus, or free → Haiku) and says so in the
issue, with why. Moving a task down works the same way when it proves simpler
than expected.

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
   `for:` label. Then `status:ready`.
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
8. **Tommy merges.** Merging to `main` deploys to his phone through
   `pages.yml`. Nobody else merges, ever.
9. **Nick confirms it actually shipped**: `pages.yml` green, and the live page
   at https://tommyauld02.github.io/iron-ledger/ serving the new `BUILD`. A
   merge is not done until both are true — b39 was pushed without anyone
   watching, failed CI, and never reached the phone (see `CLAUDE.md`).
10. **Nick reports** what landed, what is waiting for Tommy, and what is stuck.

## Rules that are not negotiable

- **Only Tommy merges.** No agent merges, pushes to `main`, or force-pushes
  `main`. Force-pushing your own pull request's branch after a rebase is fine —
  it is how Lexi keeps `BUILD` numbers in order (below).
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
  notice. When two approved PRs both bump `BUILD`, Lexi rebases the
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

Nick runs when Tommy starts him — there is no schedule. Tommy gives Nick
direction in the Claude project; Nick files and assigns the work, runs the
Claude roles directly, and leaves `for:intern` issues for Hermes. Tommy starts
Jennr in Hermes when he wants free-model work done.
