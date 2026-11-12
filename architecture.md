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

Today the mart is one wide record per person (664 rows, 44 fields, JSON
1.88 MB): identity, career money, ranks, embedded `per_cycle` /
`udp_per_cycle` lists, 2026 columns. That works at this scale. It does not
scale to the North Star layers, because polls are a time series, votes are
thousands of rows per person, and promises are a list with statuses — none of
that flattens into one row without going sparse and slow.

The model, as layers are added:

- `persons` — identity + congress membership. Key: `person_key`. FEC
  candidate IDs as a list.
- `money_by_cycle` — grain (person, cycle): every money fact. Career totals
  are sums over this table. (Today this exists as the embedded `per_cycle`
  lists; the move is to make it a first-class table.)
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

## 3. Layered pipeline (bronze → silver → gold)
- **Raw (bronze):** FEC bulk dumps and API responses, stored as received under
  `work/bulk/`, immutable, dated. Never edited in place.
- **Staging (silver):** deduped, typed, joined tables (`money_pas2_weball.csv`,
  `money_per_cycle.json`, `opposition-computed.json`). Each staging script
  records its inputs, its dedup rule, and its row counts in a log.
- **Marts (gold):** the per-person dataset (career + per-cycle). Every column
  is produced by a script. No manual edits to the JSON/CSV, ever.
- **Presentation:** the artifact. It reads the mart; it computes nothing that
  the mart doesn't already contain (except display sorting/filtering).

## 4. Idempotent, re-runnable pulls
- Every pull/compute script must be safe to re-run: same inputs → same
  outputs. No step depends on hidden state. A re-pull after the 2026 cycle
  closes must reproduce the current dataset plus the new filings, not a
  different dataset.

## 5. Versioned snapshots
- Before each change, back up the current JSON/CSV to `work/` with a dated,
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
  labeling them as such (e.g. "2026 cycle partial through Sep 30, 2026").

## 10. Methodology ships with the data
- Every new column, rule, or definition lands in `methodology.md` in the same
  change that lands the data. A number without its definition documented is
  not done.

## 11. Interface: mobile-first web app, native later
- The interface is a **mobile-first web app**: a link that works natively on
  iPhone and Android (responsive layout, touch-friendly controls, fast load
  even at ~4,400 rows). That is the first interface and the foundation.
- **Native apps (App Store, Google Play) and a desktop app come later** — as
  packaging of the same web app and the same data layer (e.g. a web-view
  wrapper), not a rebuild. They need developer accounts (Apple $99/yr,
  Google $25 one-time) and store review; the data pipeline, mart, and API do
  not change.
- The presentation layer must never become the source of truth: whatever the
  interface, it reads the mart (or an API over it), never its own copy of the
  numbers.
