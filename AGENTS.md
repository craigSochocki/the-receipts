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
root via `src/common/config.py`, never from an absolute path or the
current working directory.

```
the-receipts/
├── AGENTS.md                  # this file — the agent contract
├── README.md, STATUS.md, methodology.md, architecture.md
├── config.yaml                # single source of truth for shared values
├── congress-money-tracker.csv / .json   # the dataset (stays at repo root)
├── src/
│   ├── common/                # config loader (config.py)
│   ├── ingest/                # pulls from FEC bulk + API:
│   │                          # pull_money, pull_udp, pull_self_funding,
│   │                          # pull_other_committees, pull_all_ie,
│   │                          # pull_f6, pull_f24, pull_freshness
│   ├── transform/             # build_roster, fec_lookup, apply_fec_lookup,
│   │                          # apply_dedup, compute_opposition,
│   │                          # merge_dataset, compute_ranking, compute_2026
│   ├── validate/              # verify_dataset.py — the standing audits
│   └── rebuild.py             # the one command that runs the whole pipeline
├── data/
│   ├── raw/                   # staged FEC bulk (~5.6 GB), GITIGNORED,
│   │                          # re-downloadable — see research/bulk-inventory.md
│   ├── source/                # committed TRUE inputs: legislators yaml,
│   │                          # dedup-applied.json, manual_roster_notes.json,
│   │                          # fec_lookup_results.json
│   ├── intermediate/          # regenerable staging files, GITIGNORED —
│   │                          # rebuild.py recreates them all
│   ├── snapshots/             # dated dataset states (pre-rank, pre-opposition…)
│   └── evidence/              # one-off API dumps from spot checks
├── research/                  # pull logs, verification notes, source research
└── docs/                      # the generated static site (index.html,
                               # from src/site/build_site.py; never hand-edited)
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
  Committee money (pas2) through **Sep 30, 2026**; weball-derived
  figures (individual, self-funding, topline) through **Oct 14, 2026**;
  all-IE (UDP too) through **Oct 31, 2026**. 2026 is partial — say so
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
  `src/ingest/pull_freshness.py` reports late money (Form 6 48-Hour
  Notices, F24 24/48-hour IE, totals refresh) into
  `data/intermediate/freshness_snapshot.json` — labeled by source and
  date, **never merged into dataset totals**. It is a separate entry
  point, not in `rebuild.py`'s default pipeline. Production runs need a
  registered api.data.gov key (`FEC_API_KEY`); DEMO_KEY is spot-checks
  only and the driver refuses `--all` on it. `--all` is gated by
  default (one global `/filings/` check per family first —
  `src/ingest/pull_gate.py`, state in committed
  `data/source/freshness_state.json`); `--no-gate` forces the full run,
  and a gate error falls back to the full run, never to a skip.

## 5. Verification — the gate

A change to data or pipeline is not done until it passes this gate:

1. **Full rebuild reproduces the committed dataset byte-identically:**

   ```sh
   python3 src/rebuild.py
   ```

   It runs the pipeline in order (roster → FEC lookup → money → UDP →
   dedup → self-funding → other-committees → all-IE → opposition →
   merge → ranking → 2026 → verify), backing the current dataset up
   to `data/snapshots/` first, and fails fast if `data/raw/` isn't
   staged. Verified Nov 12, 2026 (after the phase-split opposition-credit
   rebuild): a fresh clone with staged bulk data rebuilds the committed
   dataset byte-identically (CSV md5
   `2e93fa51f148865a9003a75996830bea`, JSON md5
   `10a5b0018f315e9f9894ba4f5d3f1479`).
2. **All audits in `src/validate/verify_dataset.py` pass** (93 standing
   audits: per-cycle sums for every column family, roster totals vs
   methodology, all 12 rank columns, clean counts and the generalized
   clean rule, 2026 columns, opposition, dedup, CSV↔JSON agreement, row
   order). Exit non-zero on any mismatch.
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

Two workflows in `.github/workflows/` (see `README.md`, "Automation
(GitHub Actions)", for the operator-facing version):

- **`ci.yml`** — push + pull request to `master`. Checkout, Python 3.12,
  `pip install -r requirements.txt`, `./download_bulk.sh`,
  `python3 src/rebuild.py`, then **fail unless the rebuild reproduces the
  committed dataset byte-identically** (`git diff --exit-code` on
  `congress-money-tracker.csv` / `.json`), then `build_site.py` +
  `verify_site.py`. No deploy step — GitHub Pages serves `docs/` on
  `master` automatically. `permissions: contents: read`. Needs no secrets,
  so it is safe on PRs from forks.
- **`scheduled-refresh.yml`** — cron `0 9 * * 0` (Sunday 09:00 UTC) +
  `workflow_dispatch` (manual refresh, e.g. right after the Dec 3
  post-general deadline). Same pipeline, then the freshness step, then a
  commit + push back to `master` as `github-actions[bot]`
  (`data: refresh from FEC bulk <YYYY-MM-DD>`). `permissions:
  contents: write`. Job timeout 180 min (freshness step 90 min).

**Commit-back rule (scheduled refresh only).** Commit and push only if
the dataset changed OR the site changed apart from its generation
timestamp — the timestamp line is ignored via `git diff -I`, the same
pattern `verify_site.py` strips. A timestamp-only rebuild commits
nothing. A failed rebuild/verify commits and pushes nothing (commit step
gated on `success()`). The bot's push triggers CI, which re-verifies.

**No cache of the bulk data.** Every run re-downloads fresh with
`./download_bulk.sh` (~315 MB). The 2026 bulk files are updated in place
by the FEC under the same cycle-named URLs, so any cache keyed on
something other than the files' own content could silently serve stale
filings — and the byte-identical gate would not catch it, because it
verifies the rebuild against the committed dataset, not the filings
against the FEC. A content-aware cache (per-file ETag / Last-Modified)
would be safe, but `./download_bulk.sh` has no such mechanism. Do not
add caching to either workflow without one.

**FEC API key.** The freshness step (`pull_freshness.py --all`) runs only
when the `FEC_API_KEY` repository secret is set; the snapshot is uploaded
as a workflow artifact (90-day retention), never merged into dataset
totals, never committed. When the secret is absent the step logs a skip
line and the run continues. The key was added Nov 12, 2026 (Craig
registered at api.data.gov); the first scheduled run will confirm it by
logging whether freshness ran or skipped. Rotate it in repo Settings →
Secrets and variables → Actions if it ever leaks or expires. `--all` runs the six F24 committee sweeps (gated per committee by the pre-flight gate, `src/ingest/pull_gate.py`); `--no-gate` forces the full run.

**Workflow files change like any other code** — one change per commit
(§2), and a workflow change is its own commit, never bundled with a data
or pipeline change.

## 9. Human workflow (Craig in VS Code)

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
