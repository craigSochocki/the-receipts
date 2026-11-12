# Congress Money Tracker — Data Architecture Principles

## North Star (Craig, Nov 12, 2026)

Expose the effect money has on politics, as a voter guide for 2028. The layers,
in order:

1. **Money** (this tracker, in progress): who funds whom, how much, from which
   sources — individual, corporate PAC, AIPAC direct, UDP support and
   opposition spending.
2. **Outcomes:** does money predict winning? Needs outcome flags (won primary /
   won general) and *all* candidates, winners and losers — phase 2.
3. **Perception:** how does funding track with public perception — polling and
   poll standing over time.
4. **Behavior in session:** how do they vote, what do they signal, what do
   they prioritize? Roll-call votes, sponsorships, committee work.
5. **Promises vs. reality:** campaign platforms and promises vs. votes and
   actions — follow-through scoring, and how funding sources may shape
   platforms.
6. **The voter guide:** the synthesis — a guide for people deciding who to
   vote for in 2028.

### Signals and scores (Craig, Nov 12, 2026)

Per candidate, beyond money and votes: **behavior** — platforms, campaign
websites, social media, press releases, and **what is said about them in the
news**. These are stored as their own tables (`statements`: person, source,
date, text; `news`: person, outlet, date, coverage) and feed the scores.

**Scores — a trust / integrity score, kept up to date.** Two questions it
must answer, as separate components, never one opaque number:
1. **Follow-through:** do they do what they said they were going to do?
   (Promises vs. votes/actions.)
2. **Whose interests:** are the things they do beneficial to the working
   class, or more subservient to a donor class?
Scores are derived views with a **published, versioned formula** — every
input visible, every component shown separately. A score nobody can audit is
just an opinion, and this app's whole point is the opposite. Scores recompute
on a schedule whenever inputs change (new votes, new filings, new
statements), never by hand.

### Geography (Craig, Nov 12, 2026)

Federal first. Then **state (Michigan), county (Oakland County), and
municipal (Ferndale)** — the same tables and the same patterns, with a
jurisdiction key, repeated for other states and municipalities later. State
and local are NOT in the initial build: the data sources change (state
disclosure via FollowTheMoney.org / Michigan Secretary of State; local races
often have thin or no digital disclosure), so Michigan is the pilot for the
pattern, not a parallel build.

Every layer is a separate table with its own source and as-of date, joined on
the same stable keys (person = FEC candidate ID). No layer is allowed to
contaminate another's sourcing.

**Status:** design guide, not a migration plan. Written Nov 12, 2026. The tracker is a
static web page today; the long-term goal is a full political-analytics app.
Nothing here requires a rebuild now. These rules exist so each expansion
(2026 columns, losing candidates, public launch) makes the future app easier,
not harder.

## 1. One canonical dataset
- `congress-money-tracker.json` is the source of truth. The CSV is an export of
  it. The web page embeds a *copy* — it is never the master, and it is never
  hand-edited. Every change flows: script → JSON → CSV → artifact re-embed.
- If a number exists in two places and they disagree, the JSON wins and the
  disagreement is a bug.

## 1a. Configuration — one source of truth (added Nov 12, 2026)
- `config.yaml` (repo root) holds every value shared across pipeline
  scripts: FEC committee IDs (AIPAC PAC, UDP), cycles (career range, UDP
  cycles, current cycle), repo-relative paths, FEC API settings (base URL,
  key from `FEC_API_KEY` with `DEMO_KEY` fallback, timeout, request delay),
  party-code map, verification constants (prior UDP cycle totals), and
  reporting thresholds.
- `src/common/config.py` loads it; every script resolves paths from the repo root
  (derived from the script's own location), never from an absolute path and
  never from the current working directory. The repo runs from any checkout
  location. No script may re-hardcode a value from `config.yaml`; a new
  shared value goes in `config.yaml` first.
- Verified Nov 12, 2026: the config refactor reproduced outputs exactly —
  `pull_money.py` re-run byte-identical to the original script's output,
  `compute_opposition.py` re-run byte-identical, `build_roster.py` re-run in
  a copied checkout identical except for post-build enrichment (see below).
- Reproducibility gap — CLOSED Nov 12, 2026. Every step that used to live
  only in the builder's head is now a script, and one command runs them
  all: `python3 src/rebuild.py` (build_roster → apply_fec_lookup →
  pull_money → pull_udp → apply_dedup → pull_self_funding →
  pull_other_committees → pull_all_ie → compute_opposition →
  merge_dataset → compute_ranking → compute_2026 → verify_dataset). The weball
  double-count dedup is applied by `src/transform/apply_dedup.py`, which reads the
  kept/dropped decisions from `data/source/dedup-applied.json` as data (it does
  not re-derive them). The roster enrichment is `src/transform/apply_fec_lookup.py`
  (committed lookup results + the 7 recorded manual notes in
  `data/source/manual_roster_notes.json`); the live lookup is optional
  (`--with-fec-lookup`) and restores the manual entries afterwards. The
  merge (`src/transform/merge_dataset.py`), ranking (`src/transform/compute_ranking.py`),
  and 2026 columns (`src/transform/compute_2026.py`, including the primary-target
  list) are scripted, and `src/validate/verify_dataset.py` runs the standing
  audits. Verified Nov 12, 2026: a fresh clone with staged bulk data
  rebuilds the committed dataset byte-identically (csv md5
  f346fca949d1c160317f2f1b45100273, json md5
  48c2a2146523ef9aa1c4f11ac3d361a7), all intermediates byte-identical,
  all 93 audits passing. Two judgment calls are recorded as data, not
  re-derived: the dedup decisions (`dedup-applied.json`) and the manual
  roster notes (`manual_roster_notes.json`); the Rivet roster collapse and
  the Luria unverified-clean rule are hardcoded constants in the merge and
  2026 scripts with their exact committed text, and both scripts fail
  loudly if the data stops matching those constants.

## 2. Stable keys — join on IDs, never on names
- Person = `person_key` (Bioguide ID from the legislators dataset — the
  stable identity across chambers and cycles). A person's FEC candidate IDs
  live as a list on the person record (`fec_candidate_ids`), since
  chamber-switchers hold several. Money joins on FEC candidate ID; people
  join on `person_key`.
- Race = cycle + office + state + district. Committee = FEC committee ID.
- Name-based matching is a documented fallback only (blank candidate IDs,
  non-roster people), and each fallback is logged with its rule.

## 2a. Data model — tables by grain (proposed Nov 12, 2026)

Today the mart is one wide record per person (664 rows, 91 fields, JSON
~4 MB): identity, career money, ranks, embedded `per_cycle` /
`udp_per_cycle` / `self_funding_per_cycle` / `other_committees_per_cycle` /
`all_ie_per_cycle` lists, the JSON-only `all_ie_top_committees`, and 2026
columns. That works at this scale. It does not
scale to the North Star layers, because polls are a time series, votes are
thousands of rows per person, and promises are a list with statuses — none of
that flattens into one row without going sparse and slow.

The model, as layers are added:

- `persons` — identity + congress membership. Key: `person_key`. FEC
  candidate IDs as a list.
- `money_by_cycle` — grain (person, cycle): every money fact. Career totals
  are sums over this table; stocks (cash on hand, debts owed by) are the
  latest cycle's value, not sums. (Today this exists as the embedded
  `per_cycle` lists; the move is to make it a first-class table.)
- `committees` — FEC committee registry: committee ID → name, type, cycle.
  The all-IE top-committees view is a (person, committee) rollup of the IE
  table, not a person attribute.
- `freshness` — an OVERLAY, not part of the canonical dataset: grain
  (person, source, date): Form 6 notices, F24 expenditures, and totals-
  refresh flags found since bulk coverage. It is never merged into the mart;
  it is reconciled against the next bulk re-pull and then discarded. A
  freshness figure that lands in the mart without a bulk source behind it
  is a bug.
- `outcomes` — grain (person, cycle, race): won primary / won general /
  lost / uncalled / runoff, margins. Own as-of date, own source.
- `committees` — FEC committee registry: committee ID → name, type, cycle.
- `ads` — grain (advertiser, cycle, week): spend min/max/mid + impressions.
  Per-person rollups are derived, never stored as raw.
- `polls` — grain (person, race, poll, date): time series. Never in the
  person row.
- `votes` — grain (person, roll call): vote, bill, date. Bills and
  sponsorships are their own tables.
- `promises` — grain (person, promise): promise text, source, status,
  linked votes.
- The per-person wide record **stays** — as a derived view (gold) computed
  from these tables. The app reads the same shape it reads today; only the
  storage underneath gets sane.

Money stays exact: cents as integers in the store; ad estimates as
min/max/mid with an `is_estimate` flag. Versioned snapshots become a
`dataset_versions` table plus `as_of` on every row.

## 2b. Future direction — data lives outside the repo (Craig, Nov 12, 2026)

Eventually the data does not live in git at all: the tables above live in
a database, and the repo holds code, config, and the published dataset
only. That move is NOT built yet. The Nov 12, 2026 restructure prepares
for it: every script reads and writes data through the `config.yaml`
paths layer (`src/common/config.py`), never through hardcoded repo-relative
file paths, so pointing the pipeline at a database-backed store is a
config change, not a rewrite of every script. Until then, the on-disk
layout mirrors the future tables — `data/source/` (inputs),
`data/intermediate/` (regenerable staging, gitignored),
`data/snapshots/` (versions), `data/raw/` (immutable bulk, gitignored).

## 3. Layered pipeline (bronze → silver → gold)
- **Raw (bronze):** FEC bulk dumps and API responses, stored as received under
  `data/raw/`, immutable, dated. Never edited in place.
- **Staging (silver):** deduped, typed, joined tables (`money_pas2_weball.csv`,
  `money_per_cycle.json`, `opposition-computed.json`,
  `self_funding_per_cycle.json`, `other_committees_per_cycle.json`,
  `all_ie_per_cycle.json`, `all_ie_top_committees.json`). Each staging script
  records its inputs, its dedup rule, and its row counts in a log.
- **Marts (gold):** the per-person dataset (career + per-cycle). Every column
  is produced by a script. No manual edits to the JSON/CSV, ever.
- **Freshness (overlay):** `freshness_snapshot.json`, produced by a separate
  entry point (`src/ingest/pull_freshness.py`) on its own cadence. It is not part
  of the rebuild pipeline and never feeds the mart.
- **Presentation:** the artifact. It reads the mart; it computes nothing that
  the mart doesn't already contain (except display sorting/filtering).

## 4. Idempotent, re-runnable pulls
- Every pull/compute script must be safe to re-run: same inputs → same
  outputs. No step depends on hidden state. A re-pull after the 2026 cycle
  closes must reproduce the current dataset plus the new filings, not a
  different dataset.

## 5. Versioned snapshots
- Before each change, back up the current JSON/CSV to `data/snapshots/` with a dated,
  descriptive name (`congress-money-tracker-pre-<change>.csv/.json` — the
  existing convention). Every dataset carries a `data_as_of` date, and the
  methodology is updated in the same change, never later.

## 6. Money is exact
- Store money as exact decimals (cents as integers internally; dollars to 2dp
  on display). Never float-sum money across steps without a reconciliation
  check. The standing audit: per-cycle sums must reproduce every career
  column exactly, zero mismatches, before any build ships.

## 7. Per-cycle is first-class grain
- Every money fact lives at (person, cycle) grain; career totals are sums over
  cycles. New analyses (2026-clean, dependence share, primary targets) are
  queries over cycles, never new pulls. If a question needs a cycle we don't
  have staged, stage it first.

## 8. Outcomes are a separate table
- Election outcomes (won primary / won general / lost / uncalled / runoff)
  live in their own table keyed by (person, cycle, race), sourced from race
  calls/certification, with their own as-of date. Outcomes arrive on a
  different schedule than money, so they must never be baked into the money
  tables.

## 9. App-ready seams
- The static page embeds the mart, which is fine at 664 rows and workable at
  ~4,400. The seams to watch: if rows grow past ~10k, or if refresh becomes
  frequent, or if users need to save/filter server-side, move to a backend +
  database serving the same mart tables over an API. The presentation layer
  then reads the API, not a file. Do not make that move until one of those
  triggers fires.
- Keep the public/private boundary explicit: a flag for what is publishable.
  A public build must never show unverified or partial-cycle figures without
  labeling them as such (e.g. "2026 cycle partial — committee money through
  Sep 30, weball through Oct 14, independent expenditures through Oct 31").

## 10. Methodology ships with the data
- Every new column, rule, or definition lands in `methodology.md` in the same
  change that lands the data. A number without its definition documented is
  not done.

## 11. Interface: mobile-first web app, native later
- The interface is a **mobile-first web app**: a link that works natively on
  iPhone and Android (responsive layout, touch-friendly controls, fast load
  even at ~4,400 rows). That is the first interface and the foundation.
- **Static site — BUILT Nov 12, 2026.** `docs/index.html` is generated from
  the canonical dataset by `src/site/build_site.py` (one command:
  `python3 src/site/build_site.py`; verified by
  `src/site/verify_site.py`, which decodes the embedded data and checks it
  against the dataset field-by-field, plus a Node runtime smoke test
  `src/site/smoke_test.js`). Single self-contained page, no external
  dependencies: the dataset is embedded in a compact positional encoding
  (1.6 MB for 664 rows). Content parity with the private tracker artifact
  (v6): search, filters, sort by every money column, totals strip + footer,
  per-person drill-down with cycle-by-cycle tables, leaderboards, clean-money
  view, party-by-chamber breakdown, 2026 primary-target list, methodology
  section, CSV download from the same embedded figures. The 14
  complete-picture columns are shown through switchable column views, not
  one 25-column table. **Never hand-edit `docs/index.html`** — edit the
  generator and re-run it. GitHub Pages is the publishing source (`docs/`);
  enabling Pages in repo Settings is Craig's step — the site is not public
  until he does that.
- **Native apps (App Store, Google Play) and a desktop app come later** — as
  packaging of the same web app and the same data layer (e.g. a web-view
  wrapper), not a rebuild. They need developer accounts (Apple $99/yr,
  Google $25 one-time) and store review; the data pipeline, mart, and API do
  not change.
- The presentation layer must never become the source of truth: whatever the
  interface, it reads the mart (or an API over it), never its own copy of the
  numbers.
