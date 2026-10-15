# For any AI agent working in this repo

Read these two files before you change anything:

1. **`TEAM.md`** — your role, the issue labels, how work moves, and the rules
   every agent follows. The most important: work only on the issue you were
   assigned, on its own branch; never push to `main`; never merge. Nick
   merges, and only when Tommy says "push it".
2. **`CLAUDE.md`** — the seven rules that keep the app from breaking in the
   ways it has broken before, and an index of `docs/`, where how each part of
   the app works is written up. It is named for Claude but applies to every
   model.

Then read the `docs/` file the index names for the area you are changing,
before you change it. Storage, undo, dates and the service worker are in
`docs/architecture.md`, and they are Nick's: a free model never changes them
unaided.

Run `./verify.sh` before you open a pull request. Nothing ships without it
passing.
