# AGENTS.md — The Receipts

The shared operating model for every agent working in this repo — Muse
and Craig's VS Code agent alike. Read this file first when you open the
repo cold. It is the contract.

- `README.md` is the setup guide (clone, rebuild, layout).
- `methodology.md` is the definitions — every column, source, and
  limitation. If this file and `methodology.md` disagree on a number,
  `methodology.md` wins.
- `architecture.md` is the design (data model, North Star, gaps).
- `STATUS.md` is where the build stands right now.

## 1. The job / North Star

Expose the effect money has on politics — money breakdowns, election
outcomes, public perception (polling), behavior in session (votes,
signals, priorities), follow-through on campaign promises and how
funding shapes platforms — as a **voter guide for 2028**.

This tracker is layer 1: every person in Congress and the money behind
them, from FEC filings. **664 rows** — the union of the 119th Congress
(540 served) and the incoming 120th (535 named).

The ethos is audit-first: **show the evidence, never just the number.**
Every figure traces to an FEC filing, and the method for every column is
written down in `methodology.md`. A number without its definition
documented is not done.

## 2. Source of truth and git

- Remote: `git@github.com:craigSochocki/the-receipts.git`, branch
  `master`. This repo is the shared source of truth between agents and
  Craig's local clone.
- **Pull before starting work; push when done.** Check the remote for
  new commits first — another agent or Craig may have landed work since
  you last looked.
- **One change per commit, scoped to a single bit of functionality**,
  so the history stays auditable. A commit message names the one thing
  it does (`feat(merge): ...`, `fix(dedup): ...`, `docs(methodology):
  ...`, `data: ...`).
- **Never work the same files as another agent or human at the same
  time.** Coordinate through branches (e.g. `craig/<thing>`) or by
  stating what area you are touching, and wait for a running job in the
  same repo to finish and push before starting yours.
- Push from this VM needs the proxy SSH command — plain `git push`
  intermittently gets connection-reset by the egress proxy:

  ```sh
  GIT_SSH_COMMAND="ssh -i /home/hatch/.ssh/id_ed25519 -o IdentitiesOnly=yes -o UserKnownHostsFile=/home/hatch/.ssh/known_hosts -o ProxyCommand='nc -X connect -x 198.19.0.1:3128 %h %p'" git push
  ```

- **SSH home-dir split (Nov 12, 2026):** the shell's `$HOME` is
  `/home/hatch` but ssh resolves `~` from the passwd entry, which is
  `/root` — so the `~` form of the push command fails with "Host key
  verification failed". The command above (and `~/.ssh/config`) uses
  absolute paths for that reason. If some other ssh use still fails
  with "Host key verification failed" even though
  `~/.ssh/known_hosts` is populated,
  copy it over (`cp ~/.ssh/known_hosts /root/.ssh/known_hosts`) and
  retry; the server key is GitHub's published Ed25519
  (`SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`) — verify with
  `ssh-keygen -lf` before trusting it. A push that prints
  `28b390f..xxxx master -> master` and then fails on the `ls-remote`
  verify with "Connection reset" has already succeeded — just retry
  the `ls-remote` alone.

- After pushing, verify remote master = local HEAD:

  ```sh
  git ls-remote origin master   # must match git rev-parse HEAD
  ```

## 3. Layout

The staged layout (Nov 12, 2026 restructure). Paths below are
repo-relative; `config.yaml` is the single source of truth for shared
values (committee IDs, cycles, paths, thresholds, API settings) — change
a value there, never in a script. Scripts resolve all paths from the repo
root via `settings()` in `receipts/common/settings.py`, never from an absolute path,
the current working directory, or at import time.

```
the-receipts/
├── AGENTS.md                  # this file — the agent contract
├── README.md, STATUS.md, methodology.md, architecture.md
├── config.yaml                # single source of truth for shared values
├── congress-money-tracker.csv / .json   # the dataset (stays at repo root)
├── receipts/               # the Python package
│   ├── common/                # settings, baseline, file writers
│   ├── domain/                # the rules, free of file formats: Money,
│   │                          # which committee money counts
│   ├── store/                 # silver tables (DuckDB, every FEC candidate and
│   │                          # committee) and the scripts that read them:
│   │                          # other_committees.py, self_funding.py, all_ie.py,
│   │                          # udp.py, opposition.py; models.py runs dbt
│   ├── fec/                   # one typed reader per FEC bulk file
│   │                          # (weball, cm, pas2, independent expenditures)
│   ├── ingest/                # pulls from FEC bulk + API:
│   │                          # pull_f6, pull_f24, pull_freshness
│   ├── transform/             # build_roster, fec_lookup, apply_fec_lookup,
│   │                          # assemble, compute_2026, build_dataset
│   ├── site/                  # build_site.py fills templates/ (page.html,
│   │                          # style.css, tracker.js, views.js, method.html)
│   │                          # into docs/index.html; verify_site.py checks it
│   ├── validate/              # verify_dataset.py — the standing audits;
│   │                          # run_history.py — the FEC input checks
│   └── rebuild.py             # the one command that runs the whole pipeline
├── data/
│   ├── raw/                   # staged FEC bulk (~5.6 GB), GITIGNORED,
│   │                          # re-downloadable — see research/bulk-inventory.md
│   ├── source/                # committed TRUE inputs: legislators yaml,
│   │                          # dedup-applied.json, manual_roster_notes.json,
│   │                          # fec_lookup_results.json, baseline.json,
│   │                          # run_history.csv
│   ├── intermediate/          # regenerable staging files, GITIGNORED —
│   │                          # rebuild.py recreates them all
│   ├── snapshots/             # dated dataset states (pre-rank, pre-opposition…)
│   └── evidence/              # one-off API dumps from spot checks
├── research/                  # pull logs, verification notes, source research
├── dbt/                       # SQL models over the store, and their tests
│                              # (dbt-duckdb; run by receipts.store.models):
│                              # models/silver over the FEC tables, models/marts
│                              # over the gold tables the money steps write
├── tests/                     # unit tests for domain/ and fec/ (pytest)
└── docs/                      # the generated static site (index.html,
                               # from receipts/site/build_site.py; never hand-edited)
                               # — live on GitHub Pages since Nov 12, 2026
```

- The dataset (`congress-money-tracker.csv` / `.json`) stays at the repo
  root for now. The CSV is an export of the JSON; the JSON wins if they
  ever disagree.
- **Future direction: data eventually lives outside the repo in a
  database, not in git.** Until then, every script reads and writes data
  through the `config.yaml` paths layer, so that move is a config
  change, not a rewrite of every script.
- Before changing the dataset, back it up to `data/snapshots/` with a
  dated, descriptive name (`congress-money-tracker-pre-<change>.csv/.json`).

## 4. Data rules

- **FEC filings are the spine and source of truth.** OpenSecrets is a
  cross-check only, never a primary source. Every number traces to a
  filing; methodology §3–§4 names the file and columns for each family.
- **A changed FEC file layout stops the build.** The readers in
  `receipts/fec/` raise `LayoutChanged` when a row has the wrong number
  of fields or a column is missing. Update the reader to the new layout;
  never skip or blank-fill rows to get past it.
- **Never blend columns.**
  - Earmark columns are subsets of the headline column — never added again.
  - UDP / outside spending is **excluded from `total_accepted`**. It is
    money spent *about* a race, never given to the campaign.
  - `total_accepted` (career) = individual contributions + corporate PAC
    + AIPAC PAC direct. New columns never change this definition; they
    are shown separately.
- **Clean rule (generalized, methodology §14).** A 120th member is
  `unverified` (`clean_2026 = null`) only if they have **no 2026 entries
  in ANY money source**. A member who ran unopposed in 2026
  (`unopposed_2026` — no other candidate in the race with receipts over
  $0 in weball26; the race comes from the filing's own row, not the
  roster district) is also null, not clean. Verified-clean in 2026:
  **74 total (64 House + 10 Senate)**. Nulls: Elaine Luria (unverified
  — her real 2026 campaign H6VA02198, $8.04M receipts, is not linked in
  the roster; linking it is a roster change, not something to do
  unilaterally) plus three unopposed (Pressley MA-07, Jacobs CA-51,
  Radewagen AS). Career-clean is derived from career money columns only
  and is untouched by the unopposed rule.
- **Cutoffs differ by data family and must be labeled everywhere.**
  Committee money (pas2) through **Oct 14, 2026**; weball-derived
  figures (individual, self-funding, topline) through **Oct 14, 2026**;
  all-IE (UDP too) through **Nov 3, 2026** — as judged for snapshot
  `fec-bulk-2026-11-22`; `config.yaml` `verification.coverage_end` is
  the one place they are set, and they are re-judged at every rebaseline. 2026 is partial — say so
  wherever 2026 figures appear.
- **Weball is a lower bound where the FEC API runs ahead — document the
  gap, never paper over it.** Constantino: weball loans $14.4M vs API
  $17M. Spot-check named cases against the FEC API where the bulk lags.
- **All-IE "career" means 2022–2026 only** (the 2010–2020 IE files are
  not staged) — label it as such everywhere. IE files contain tens of
  billions in bogus filings, so the filter (registered committee +
  identified candidate) and the excluded amounts are part of the method
  (methodology §4, §8), not an implementation detail.
- **Freshness is an overlay, not part of the dataset.**
  `receipts/ingest/pull_freshness.py` reports late money (Form 6 48-Hour
  Notices, F24 24/48-hour IE, totals refresh) into
  `data/intermediate/freshness_snapshot.json` — labeled by source and
  date, **never merged into dataset totals**. It is a separate entry
  point, not in `rebuild.py`'s default pipeline. Production runs need a
  registered api.data.gov key (`FEC_API_KEY`); DEMO_KEY is spot-checks
  only and the driver refuses `--all` on it. `--all` is gated by
  default (one global `/filings/` check per family first —
  `receipts/ingest/pull_gate.py`, state in committed
  `data/source/freshness_state.json`); `--no-gate` forces the full run,
  and a gate error falls back to the full run, never to a skip.

## 5. Verification — the gate

A change to data or pipeline is not done until it passes this gate:

1. **Full rebuild from the pinned snapshot reproduces the committed
   dataset byte-identically:**

   ```sh
   ./fetch_snapshot.sh        # stages the snapshot named in baseline.json
   python3 receipts/rebuild.py
   ```

   It runs the pipeline in order (roster → FEC lookup → store →
   run checks → dbt silver → accepted money → UDP → self-funding →
   other committees → all-IE → opposition → dbt marts → dataset (with
   2026) → verify), backing the current dataset up
   to `data/snapshots/` first. It refuses to run on anything but the
   snapshot recorded in `data/source/baseline.json` (`_snapshot`): the
   FEC updates its bulk files in place, so a live download is a
   different input and can never reproduce a committed dataset.
   Verified Nov 22, 2026 on `fec-bulk-2026-11-22`: byte-identical on
   Python 3.11 / 3.12 / 3.13 (CSV md5
   `6ada15a535ce1865b9485ff2f2b4ebbf`, JSON md5
   `f5b46dbcb954c4443c4fa9edb81797c1`).
   The run checks (`receipts/validate/run_history.py`) stop a rebuild when
   a FEC file lost rows since the last snapshot in
   `data/source/run_history.csv`, or the newest current-cycle file is
   stale (limits in `config.yaml` → `run_checks`). A rebaseline records
   the snapshot's rows there, so they land with the refresh PR.
2. **All audits in `receipts/validate/verify_dataset.py` pass** (per-cycle
   sums for every column family, roster totals, all rank columns, clean
   counts and the generalized clean rule, tiers, 2026 columns,
   opposition, dedup, CSV↔JSON agreement, row order). Exit non-zero on
   any mismatch. **Every data-dependent expected figure lives in
   `data/source/baseline.json`**, never as a literal in a script or in
   `config.yaml` (`receipts/common/baseline.py`; config keeps policy values
   only — thresholds, presets, committee IDs).
2a. **New FEC data is accepted only by a reviewed rebaseline:** publish
   a snapshot ("FEC snapshot" workflow), `./fetch_snapshot.sh <tag>`,
   set `data_as_of`, `python3 receipts/rebuild.py --rebaseline`, and review
   `git diff data/source/baseline.json` — every figure that moved, old
   next to new, including what the public page says (`site.*`). The
   rebaseline still enforces cross-step agreement (two steps that
   compute the same figure must match). A rebaseline changes public
   figures, so it lands by pull request with Craig's go-ahead (§6),
   never by a bot push.
3. **If any value differs, STOP and report — never adjust a figure to
   match.** A mismatch means the code, the data, or the method is
   wrong; find which one.
4. **The verifier checks the dataset against its own definitions, so it
   cannot catch a missing money dimension.** Any new money type needs a
   **coverage check** — what the FEC reports vs what the tracker
   covers — not just a math check. (This is how the self-funding blind
   spot survived: 474 people self-funded something, 17 with
   self-funding exceeding their total_accepted, and no audit fired.)
5. New columns, rules, or definitions land in `methodology.md` **in the
   same change** that lands the data.

## 6. Hard no's

- **Nothing goes public without Craig's explicit go-ahead.** The live
  site (GitHub Pages, publishing source `docs/` on `master`, enabled by
  Craig Nov 12, 2026) is the one public surface; nothing BEYOND it goes
  public — do not share or publish anything else derived from the repo,
  do not enable any other publishing. The intro page stays private.
  Public launch beyond the live site is his call, in his words.
- **Nothing goes out under Craig's name without his approval** — no
  emails, posts, or submissions.
- **No invented figures. No guessed URLs.** If a value isn't in a
  source you can cite, say you don't have it. If a route is blocked,
  document the blocker — do not invent a workaround or fake the data.
- **Never hand-edit generated files** — the dataset CSV/JSON and
  everything in `data/intermediate/` are rebuilt, not edited. Edit the
  scripts and docs; let the rebuild regenerate the rest. (Same rule
  applies to the web tracker page: it re-embeds the dataset; it is
  never the master.)

## 7. Reporting

Every build reports back with evidence, not adjectives:

- md5s of the dataset CSV/JSON, audit count and result, the commit
  list (one change per commit), and what changed.
- **Open items get documented** in `methodology.md` / `STATUS.md`,
  never silently dropped. If an access route is blocked, name the
  blocker and what it would take to unblock it.
- If a verification step fails, report what failed, what the evidence
  says, and what happens next — and stop. Do not retry a blocked step
  through another tool or agent.

## 8. Automation (GitHub Actions)

Three workflows in `.github/workflows/` (see `README.md`, "Automation
(GitHub Actions)", for the operator-facing version):

- **`ci.yml`** — push + pull request to `master`. Checkout, Python 3.12,
  `pip install -r requirements.txt`, `./fetch_snapshot.sh` (the pinned
  snapshot, sha256-verified), `python3 receipts/rebuild.py`, then **fail
  unless the rebuild reproduces the committed dataset byte-identically**
  (`git diff --exit-code` on `congress-money-tracker.csv` / `.json`),
  then `build_site.py`, **fail if the committed `docs/index.html` is not
  the rebuilt page** (timestamp aside), then `verify_site.py`. No deploy
  step — GitHub Pages serves `docs/` on `master` automatically.
  `permissions: contents: read`. Needs no secrets, so it is safe on PRs
  from forks.
- **`fec-snapshot.yml`** — manual, and called by the refresh. Publishes the live FEC bulk files as
  an immutable `fec-bulk-<date>` Release (raw files + `SHA256SUMS` +
  `PROVENANCE.tsv`). Public FEC data; Craig approved publishing these
  snapshots Nov 22, 2026. Does not touch the dataset.
- **`fec-refresh.yml`** — weekly (Sundays 09:17 UTC), on demand, or on
  a push to `refresh-now`. Automates §5 step 2a: snapshot today's bulk
  and candidate files (via `fec-snapshot.yml`), stage them, set
  `data_as_of`, `python3 receipts/rebuild.py --rebaseline`, and, if any
  baseline figure moved, open a pull request from a fresh
  `fec-refresh-<date>-r<run>` branch listing every moved figure
  (`receipts/validate/baseline_changes.py`), start CI on it, and close any
  older open refresh pull request as superseded. **It never pushes to
  `master` and never force-pushes**; merging is Craig's call (§6), after
  re-judging `verification.coverage_end`, which the workflow leaves as
  it was. Replaces `scheduled-refresh.yml` (retired Nov 23, 2026; it
  rebuilt from a live download and never completed a run).

**Pinned, not cached.** CI stages the pinned snapshot Release on every
run and verifies every sha256, so its inputs are identified by content.
Never point CI back at `./download_bulk.sh`: a live download is a
different input every day. Only the snapshot step downloads live files.

**Freshness overlay — not scheduled.** `pull_freshness.py --all` ran only
in the retired scheduled refresh, which never completed a run. No
workflow runs it now; it is run by hand with the `FEC_API_KEY` key
(registered by Craig at api.data.gov, also a repository secret since
Nov 12, 2026; rotate it in Settings → Secrets and variables → Actions if
it leaks or expires). `--all` runs the six F24 committee sweeps (gated
per committee by `receipts/ingest/pull_gate.py`); `--no-gate` forces the full run.

**Workflow files change like any other code** — one change per commit
(§2), and a workflow change is its own commit, never bundled with a data
or pipeline change.

## 9. Code style (Craig, Nov 22, 2026)

Code should read without commentary: small functions, names that say
what a thing is, one level of abstraction per function. Use comments
sparingly — only for a reason the code cannot show (an FEC quirk, a
decision and who made it). Do not narrate history or restate the code
in comments; history belongs in commit messages and `STATUS.md`,
definitions in `methodology.md`. Much of the existing code predates
this rule and is being refactored toward it.

Tooling enforces the mechanical part: `ruff check receipts tests` and
`ruff format --check receipts tests` must pass (CI runs both; the rules
are in `pyproject.toml`). Run `ruff format receipts tests` before
committing. A script does its work in `main()` under
`if __name__ == '__main__':`, never at import.

## 10. Human workflow (Craig in VS Code)

Craig works on this repo in VS Code on a local clone. The same rules
apply, in human form:

- Pull before starting, push when done. Work on a branch
  (`craig/<thing>`) or state the area you're touching; never work the
  same files as a running agent job.
- Never hand-edit generated files (dataset, `data/intermediate/`).
- The bulk data (~5.6 GB, gitignored) is **not in the clone** — a local
  rebuild needs the documented download (`README.md`,
  `research/bulk-inventory.md`). Editing code, methodology, or docs
  doesn't need it.
- A fuller human-facing `CONTRIBUTING.md` may follow; this file is the
  agent contract.
