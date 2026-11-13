# Congress Money Tracker — Status Snapshot

**As of: Thursday, November 12, 2026, ~5:20 PM EST**

## What is built

- **Static site — DONE Nov 12.** `docs/index.html` is generated from the
  canonical dataset by `src/site/build_site.py` (one command regenerates
  it; `src/site/verify_site.py` checks it). Single self-contained page, no
  external dependencies, dataset embedded in a compact positional encoding
  (1.6 MB for 664 rows). Content parity with the private tracker artifact
  (v6): search; filters (Congress, chamber, party, state, leadership-only,
  clean-in-2026); sort by every money column; totals strip + footer;
  per-person drill-down (FEC IDs, cycle-by-cycle tables, UDP-by-cycle,
  ranks, notes, self-funding/topline/other-committee/all-IE); leaderboards
  (Top 20 total accepted, Top 10 UDP benefit, Top 10 self-funding, Top 10
  all-IE); party-by-chamber breakdown; clean-money view (74 verified clean:
  64 House + 10 Senate; Luria the one unverified, 3 ran unopposed); 2026 primary-target list
  (192 House Democrats); methodology section; CSV download from the same
  embedded figures. The 14 complete-picture columns are switchable views,
  not one 25-column table. Verification: embedded data round-trips exactly
  (0 mismatched fields), all headline figures recomputed from the embedded
  data match, page JS parses, local serve returns 200, Node runtime smoke
  test passes (table + every tab render, drill-down, CSV), generator
  deterministic apart from the timestamp. **LIVE Nov 12:** Craig enabled
  GitHub Pages (publishing source `docs/` on `master`) and the site is
  public at https://craigsochocki.github.io/the-receipts/ — verified the
  live page serves the methodology content with correct figures. Never
  hand-edit `docs/index.html` — edit the generator. **Data-as-of stamp —
  DONE Nov 12 (commit `8d7129b`):** the page carries a visible "Data as
  of" stamp — coverage end dates from `config.yaml` (committee money
  through Sep 30, 2026; individual / self-funding / topline through Oct
  14, 2026; independent expenditures through Oct 31, 2026) plus the build
  time — checked by `verify_site.py`.

- **Landing-first redesign — DONE Nov 12.** The default view is now a calm front
  door (one column, max 680px): dirtiest in 2026 top 5 first (Stevens $31,025,889.44 —
  more than the next four combined, ~2.04× — computed at render, the comparison line
  only if it holds), then the clean story (74 of 535, 64 House + 10 Senate), then the
  find-your-member finder, one freshness line, one "Explore the full data" button.
  `#explore` in the URL opens the full-data workspace (six tabs, filters, table,
  methodology) with the story and finder removed from above the table; no URL state
  for filters/tabs (Change 2, queued). Stat cards and the totals strip now live in
  the workspace only — the front door carries no repeated totals. Person marks on
  every surface (front-door lists, finder results, drill-down headers, leaderboards,
  clean table, full table): party chip (D blue, R red, I gray, other stored labels
  gray with the label shown, always letter + color) and outcome label (Won / Uncalled
  / Not returning, derived from `in_120th`; "Not returning" is not "Lost" — see
  methodology §8 item 15). Verifier + smoke test cover the front-door figures (with
  a negative test), the mode hash, and the marks (spot-checks Stevens D / Not
  returning, El-Sayed D / Won, Guthrie R / Won, Hernández PPD / Won). Dataset
  byte-identical through the build (csv md5 2e93fa51f148865a9003a75996830bea, json
  md5 10a5b0018f315e9f9894ba4f5d3f1479).

- **Dirty-first leaderboards + composition charts — DONE Nov 12.** Leaderboards tab now leads with dirtiness: Top 20 dirtiest in 2026, Top 20 dirtiest career (new `dirty_career` column = corporate PAC + AIPAC direct + UDP benefit, career; roster total $1,070,633,247.20; Stevens #1 at $36,864,670.88; null only for Armstrong), then Top 20 total accepted — kept, but after the dirty lists, because total accepted measures fundraising scale, not dirtiness. The Tracker table's default sort is now Dirty 2026 desc (was total accepted). Methodology §12 states the framing plainly: individual contributions are NOT dirty money. Front door now carries House + Senate hemicycle charts (after the clean story, before the finder; side by side on desktop, stacked on mobile): one dot per seat, chamber total in the middle, party by color (chip palette) and dirtiness by fill — solid = dirty, hollow ring = verified clean, gray hollow ring = not judged (unopposed/unverified), dashed gray ring = uncalled. House plots the 435 voting seats (Dirty D 198, Clean D 58, Dirty R 169, Clean R 2, Unopposed 2, Unverified 1, Uncalled 5); Senate 100 (Dirty D 44, Clean D 9, Dirty R 44, Dirty I 1, Clean I 1, Uncalled 1); the 6 non-voting delegates are listed, not plotted (Clean D 3, Clean R 1, Unopposed R 1, Dirty PPD 1). All figures computed at render; verifier + smoke test cover the board order, the default sort, and the chart dot counts per category (with a no-hardcoded-counts check). Dataset md5s after the build: csv 0ef36dd4519f912ae1cca4b0fce95bfb, json 6455cbda6946f2d3628a2179540b044f (changed only by the added `dirty_career` column, plus a de-duplication of six 2026 `data_notes` segments that a targeted `compute_2026` re-run had doubled; the full rebuild reproduces the committed dataset byte-identically).

- **Composition charts reworked — DONE Nov 12.** Craig found the House hemicycle hard to read, so both charts were replaced. House is now a 15-row x 29-column waffle grid (435 bubbles), filled one column at a time left to right, grouped Clean D, Dirty D, Dirty R, Clean R, then Unopposed / Unverified / Uncalled at the far right. Senate is now 50 tiles, one per state in a 10 x 5 grid, each labeled with its state code and split in half, one half per senator (halves ordered by party, then name). New encoding, Craig's scheme: clean is solid party color (D blue #1e40af, R red #991b1b, I gray #374151); dirty is black with the party color inside — a single centered dot on the House waffle, a dotted pattern on the Senate tiles; unopposed/unverified are gray hollow / white, uncalled is dashed / empty. Alaska's Senate tile is half Murkowski (R, dirty) and half uncalled; every other state has two named senators. Charts are stacked full-width on the front door (the 680px front door was too narrow to read them side by side). Counts unchanged and reconciled (House 430 named + 5 uncalled = 435; Senate 99 named + 1 uncalled = 100); methodology §17 rewritten for the new layouts. Dataset byte-identical through the build (csv md5 0ef36dd4519f912ae1cca4b0fce95bfb, json md5 6455cbda6946f2d3628a2179540b044f).

- **Scrollytelling front door — DONE Nov 12.** The front-door stack is now a scroll-driven story in seven chapters, dirtiest first: (1) hook — the dirtiest fact in big type (Stevens $31.03M in dirty money in 2026, more than the next four combined, ~2.04×); (2) the dirtiest top 5, revealing row by row; (3) what counts as dirty — dirty is corporate PAC + AIPAC direct + UDP benefit, individual contributions are not dirty, career dirty across the tracker $1.07B (computed); (4) the clean ones (74 of 535); (5) the whole chamber — waffle + state tiles; (6) your member — the finder; (7) the data — freshness line + Explore the full data. Chapters reveal on scroll via IntersectionObserver (fade + slight rise); the waffle fills column by column (40ms per column) and Senate tiles stagger as they enter view; headline figures count up from 0 to the computed value on entry. Content is fully visible with JS disabled or if the observer never fires (hidden state lives under `html.js` only), and `prefers-reduced-motion` renders everything instantly with no count-ups. No scroll-jacking, no pinned sections, no parallax; mobile-first single column. Full-data mode (`#explore`) untouched. Verifier + smoke test cover the chapter order, the reveal/reduced-motion paths, and the count-up end values (with a literal scan + negative test for the explainer figures). Dataset byte-identical through the build (csv md5 0ef36dd4519f912ae1cca4b0fce95bfb, json md5 6455cbda6946f2d3628a2179540b044f).

- **2028 primary targets — DONE Nov 12.** New full-data tab next to the 2026 tab (kept untouched as history): "the dirtiest Democrats to watch for 2028 primaries" — a watchlist from 2026-cycle dirty money, NOT a ballot prediction (retirements unknown, 2028 filings not open, 2026 partial). House: same rule as the 2026 tab (120th House Democrats, dirty_2026 > 0) — 192 rows, top five Boafo $5,745,013.28, Bell $3,446,667.69, Aguilar $1,359,750.00, Jeffries $1,259,000.00, Clark $1,166,250.00. Senate: Class 3 Democrats only, dirty_2026 > 0 — 13 rows, led by Hassan $407,388.00, Wyden $304,500.00, Schatz $279,400.00 (all thirteen corporate-PAC-only dirty in 2026). New `senate_class` dataset column (1/2/3 for senators, null otherwise), read from the Senate-term `class` field in `legislators-current.yaml` — own term where held into 2026, else the 2026 seat-holder's class (Brown 3 via Husted); render-time derivation from FEC cycles was tested and fails on all three attempts, documented in methodology §14. Audit (n) in `verify_dataset.py` re-derives it independently: 0 mismatches, 120th C1 33 / C2 32 / C3 34, 16 Class 3 Democrats (Kelly/Bennet $0 and Warnock −$3,500 corp-PAC refund are the three not on the tab). Front-door pointer in the Data chapter opens the tab by in-page navigation (onclick, no URL state — Change 2 still queued). Verifier + smoke test cover the counts, the Senate top 3, the computed intro (literal scan + negative test), and the tab order. Dataset md5s after the build: csv edaf65eb6850c498f7436c05098338c0, json 436211b328d3682c8f7104e6a2b57325 (changed only by the added `senate_class` column; every other value byte-identical).

- **Automation (GitHub Actions) — DONE Nov 12; workflows in
  `.github/workflows/` (committed Nov 12, 2026, `713f67f`).** `ci.yml` runs
  on push + pull request to `master`: download bulk → `src/rebuild.py` →
  fail unless the rebuild reproduces the committed dataset byte-identically
  (`git diff --exit-code` on the CSV/JSON) → build + verify the site. No
  deploy step (Pages serves `docs/` automatically); `contents: read`; no
  secrets needed. `scheduled-refresh.yml` runs weekly, Sunday 09:00 UTC,
  plus manual `workflow_dispatch` (e.g. right after the Dec 3 post-general
  deadline): same pipeline, then the freshness step (only when the
  `FEC_API_KEY` repository secret is set — added Nov 12, 2026 (first
  scheduled run will confirm it by logging whether freshness ran or
  skipped); without it the step logs a skip line), then a commit + push back to
  `master` as `github-actions[bot]` (`data: refresh from FEC bulk
  <YYYY-MM-DD>`) only if the dataset changed or the site changed apart
  from its generation timestamp (timestamp ignored via `git diff -I`). A
  failed rebuild/verify commits and pushes nothing. That push triggers CI,
  which re-verifies. No cache of the bulk data: every run re-downloads
  fresh with `./download_bulk.sh` (~315 MB) — see `README.md`,
  "Automation (GitHub Actions)", for the reason. See also the F24 item
  under Open questions (closed Nov 12, pending Sunday live confirmation).

- **Roster: 664 people** — union of the 119th Congress (540 served) and the
  incoming 120th (535 named): 411 in both, 124 in the 119th only, 124 in the
  120th only, 5 with 120th membership unknown.
- **Career money (FEC filings, cycles 1980–2026, source of truth = FEC bulk
  files; OpenSecrets cross-check only):** individual contributions
  $8,763,847,353.73; corporate PAC $972,228,584.00; AIPAC PAC direct
  $7,567,773.00 (earmark transmitted $191,573.00); UDP independent
  expenditures supporting $42,415,003.76. **Complete picture (Nov 12):**
  self-funding $453,274,533.68 (contributions $127,959,956.91 + loans
  $325,314,576.77); total receipts $13,123,758,383.28; total disbursements
  $12,119,674,234.67; cash on hand (latest-cycle sum) $1,011,890,622.93;
  other-committee contributions $1,568,735,747.00 (party $12,452,000;
  leadership $232,556,005; labor $293,658,668; trade $476,385,811;
  membership $220,580,356; cooperative $30,134,616; unclassified
  $302,968,291); ALL independent expenditures 2022–2026 $3,842,257,481.18
  (support $1,490,363,373.56 / oppose $2,351,872,876.19).
- **Ranking:** total accepted (career) = individual + corporate PAC + AIPAC
  PAC direct; UDP excluded, ranked separately. Top 10: Warnock $316.4M,
  Ossoff $295.7M, Kelly $242.1M, Brown $201.0M, Cruz $154.2M, Talarico
  $139.8M, McConnell $123.7M, Schumer $117.7M, Schiff $110.9M, Baldwin
  $104.7M. Five new rank columns: self-funding (Scott $89,994,251.12 #1),
  all-IE support/oppose/total (Talarico $259,873,813.32 total #1),
  other-committee total (Pallone $17,794,814 #1).
- **UDP opposition credit (phase-split, Nov 12, 2026):** $48,421,886.44 credited
  to the single UDP-backed candidate in 17 race-phases (Stevens $20.48M,
  Latimer $9.87M, Bell $7.70M top). The $20,903,437.57 spent opposing El-Sayed
  in MI-Sen 2026 now splits by phase: $20,139,904.21 to Stevens (primary),
  $763,533.36 to Rogers (general, non-roster). Total UDP benefit roster-wide:
  $90,836,890.20. Stevens is the #1 UDP beneficiary at $34,858,462.88 and the
  dirtiest in 2026 at $31,025,889.44. Each person's drill-down on the site
  shows the credit phase by phase.
- **2026 layer:** per-cycle 2026 columns (individual, corporate PAC, AIPAC
  direct, UDP support, UDP opposition credit, UDP benefit, dirty, clean,
  dependence share — plus the ten new 2026 columns: self-funding, candidate
  loans/contributions, total receipts/disbursements, cash on hand,
  other-committee total, all-IE support/oppose/total); party-by-chamber
  breakdown for the 120th; clean-money view; 2026 primary-target list (House
  Democrats by dirty_2026: Boafo $5,745,013; Bell $3,446,668; Aguilar
  $1,359,750; Jeffries $1,259,000; Clark $1,166,250).
- **Clean counts:** career-clean 53 incoming House members (all also
  2026-clean). Verified-clean in 2026: **67 of 436** incoming House (63 D,
  4 R); 14 are 2026-clean but not career-clean. Senate clean in 2026: 10 of
  99 (9 D, 1 I, 0 R).
- **Design guide:** `architecture.md` (one canonical JSON dataset; stable
  FEC-ID keys; raw/staging/mart/presentation layers; idempotent re-runnable
  pulls; versioned snapshots; exact money; per-cycle first-class grain;
  outcomes as a separate table; app-ready seams).
- **North Star:** expose the effect money has on politics — money breakdowns,
  election outcomes, public perception (polling), behavior in session
  (votes, signals, priorities), follow-through on campaign promises and how
  funding shapes platforms — as a voter guide for 2028.
- **Methodology:** `methodology.md` documents every definition, source, and
  limitation, including the $451,776,015.34 weball double-count correction
  (32 persons, 90 person-cycle groups) and the UDP reconciliation gap
  (+0.49% vs OpenSecrets 2024, unresolved).
- **Known blind spot — self-funding — FIXED Nov 12 by the
  complete-financial-picture build (below).** The tracker never pulled
  candidate loans or contributions, so self-funders were understated — 474
  people self-funded something, 61 over $1M, and 17 whose self-funding
  EXCEEDS their total_accepted (Rick Scott $90.0M self vs $28.7M accepted;
  Thanedar $17.5M vs $2.1M; Constantino $17M vs $0). The verification script
  checks the dataset against its own definitions and would NOT have caught
  this. The build added self-funding as separate columns (never blended into
  total_accepted), plus topline, other-committee, all-IE, ten new 2026
  columns, five new rank columns, and the freshness layer.
- **Corrections applied Nov 12:** clean-in-2026 is 67, not 69 (Russell Fry
  took $338k corporate PAC + $10k AIPAC in 2026); Wesley Bell's 2026
  individual total is $3,221,101.71, not $0 (real $0-individual gaps are
  Melissa Bean and Hilda Solis, $3,500 corporate each); Elaine Luria's
  clean_2026 set to null (unverified — no 2026-coverage weball row under her
  linked candidate ID), excluded from the verified-clean count — and the
  original premise corrected: she DOES have 2026 entries under the stale
  linked ID (other-committee $85,610; all-IE support $685,786.28), and her
  real 2026 campaign is unlinked ID H6VA02198 (C00926303, receipts
  $8,044,063.94); linking it is a roster change, not done unilaterally.
  Anthony Constantino verified clean **with evidence** (2026 self-funding
  loans $14.4M, coverage 10/14/2026; all-IE 2026 $459,491.94 support /
  $3,721,257.82 oppose) — the counts return to **67 House / 77 total**,
  correcting the 66 / 76 figures recorded in MEMORY.md and the intro page
  (the dataset itself always said 67). A later change the same day excludes
  members who ran unopposed in 2026 from verified-clean (Pressley MA-07,
  Jacobs CA-51, Radewagen AS — no opponent with receipts over $0 in
  weball26; King-Hinds is contested — MP race filed under district 01, not
  the roster's 0 — and stays verified-clean), bringing the counts to
  **64 House / 74 total**. Curtis 2024 dedup extended to weball
  cols 6–9 (kept-minus-dropped $107,207.83 exactly; roster receipts
  −$5,640,855.75, disbursements −$5,239,012.32, transfers-from
  −$1,261,797.03, transfers-to −$3,300.00; only Curtis's row changed).
  The $21,231.43 all-IE row-sum gap resolved exactly (blank-`sup_opp`
  rows). The $1,004.53 F24 residual reconciled (Aug 3 F3X row, pre-window).
- **Codification — DONE Nov 12, ~10:40 AM EST.** The whole pipeline is
  scripted and one command rebuilds the dataset: `python3
  src/rebuild.py` (build_roster → apply_fec_lookup → pull_money →
  pull_udp → apply_dedup → pull_self_funding → pull_other_committees →
  pull_all_ie → compute_opposition → merge_dataset →
  compute_ranking → compute_2026 → verify_dataset). `src/validate/verify_dataset.py`
  runs 93 standing audits (per-cycle sums for every column family,
  roster totals vs methodology, all 12 rank columns, clean counts and
  the generalized clean rule, 2026 columns, opposition, dedup,
  CSV↔JSON agreement, row order). Verified in a fresh clone with staged
  bulk data: the rebuild reproduces the committed dataset **byte-identically**
  (csv md5 f346fca949d1c160317f2f1b45100273, json md5
  48c2a2146523ef9aa1c4f11ac3d361a7), every intermediate byte-identical, all
  93 audits passing. The verifier checks the dataset against its own
  definitions — it cannot catch a missing money dimension (see the
  self-funding blind spot below).
- **Repo restructure — DONE Nov 12.** Staged `src/` (`common/` config
  loader, `ingest/` pulls, `transform/` roster/dedup/merge/ranking/2026,
  `validate/` audits, `src/rebuild.py`); `data/` (`raw/` gitignored bulk,
  `source/` committed inputs, `intermediate/` gitignored regenerable
  staging, `snapshots/` dataset states, `evidence/` one-off API dumps);
  `research/` for notes and logs; `docs/` holds the generated static site
  (`index.html`, from `src/site/build_site.py`);
  dataset stays at the repo root. Full rebuild after the move reproduces
  the dataset **byte-identically** (same md5s as above), all 93 audits
  pass. Future direction (not built): data eventually lives outside the
  repo in a database, not in git — all data access goes through the
  `config.yaml` paths layer so that move is a config change.

## Running / next, in order

1. **Complete-financial-picture build — DONE Nov 12.** Whatever the FEC
   reports, the tracker now covers it: (1) self-funding columns — candidate
   contributions, candidate loans, loan repayments, debts owed (career +
   per-cycle); (2) topline — total receipts, total disbursements, cash on
   hand (latest cycle); (3) all other-committee + party-committee
   contributions, not just corporate PACs (Lamb's $129k gap — pas2-derived
   $96,500 + $32,650 pending reconciliation, methodology §8.17); (4) ALL
   independent expenditures for/against each person, not just UDP —
   filtered to registered committees + identified candidates (IE files
   contain tens of billions in bogus filings; CLF's $199.2M 2026 /
   $105.5M 2024 excluded — it files `cand_id` blank systematically);
   (5) freshness layer — FEC API + 48-Hour Notices (Form 6) + 24/48-hour
   IE reports, with a pre-election refresh cadence (first live run:
   Constantino's $1M Oct-29 loan; UDP vs El-Sayed F24 $20,903,437.57);
   (6) transfers between authorized committees. New columns shown
   separately, never blended into total_accepted. Re-pull bulk mid-Dec
   (post-general, due Dec 3) and Feb (year-end, due Jan 31, 2027).
2. **Static site — DONE Nov 12, LIVE the same day.** `docs/index.html`
   generated from the canonical dataset (see "What is built"). Craig
   enabled GitHub Pages (publishing source `docs/` on `master`) and the
   site is public at https://craigsochocki.github.io/the-receipts/.
   The tracker artifact stays the private version until he says to publish.
3. **Ad spending — research DONE Nov 12; Google build BLOCKED on GCP
   access.** Google first (BigQuery public dataset
   `bigquery-public-data.google_political_ads`, no approvals; join is
   direct via FEC IDs), Meta second (needs Craig's personal ID
   verification, cannot be delegated). TV deferred (no structured source;
   FCC files are PDFs). Needs a Google Cloud project + credentials —
   Craig sets it up or the build stays queued. Five decisions queued for
   Craig: Google-first order, Meta v1 scope, midpoint rule (geometric
   recommended), backfill before 2026 (recommend 2026 only), TV parallel
   or deferred.
4. **Phase 2 — every 2026 candidate (~4,371 FEC candidate IDs), no spending
   threshold,** with primary/general outcome flags (won primary, won
   general, lost, uncalled, runoff) and the same money columns. Good filters
   so the long tail doesn't bury interesting races.
5. **Later layers (North Star):** polling/perception; voting behavior
   (roll calls, sponsorships, priorities); promises vs. reality
   (follow-through scoring, how funding shapes platforms); synthesis into
   the 2028 voter guide.
6. **Public sharing:** the site is live and public by Craig's go-ahead
   (Nov 12, GitHub Pages on `docs/`). Nothing beyond the live site goes
   public without his explicit go-ahead.

## Open questions

- Freshness F24 gap — CLOSED Nov 12, pending live confirmation on the Sunday
  Nov 15 scheduled run. A bare `pull_freshness.py --all` — the form the
  scheduled refresh runs — used to run NO F24 sweeps, because the driver's
  `f24_targets` list (`src/ingest/pull_freshness.py:184`) was
  `args.f24_candidate or args.person`, empty unless `--person` /
  `--f24-candidate` was given. The driver now also runs committee-only F24
  sweeps for six config-listed spender committees on every `--all` (top 5 by
  2026 roster-targeted IE — NO GOING BACK PAC, WinSenate, HMP, TEXAS PAC,
  DEFEND AMERICAN JOBS — plus UDP by design; `config.yaml`,
  `freshness.f24_committee_sweep`, cycle 2026 only), attributed to roster
  people by candidate_id with non-roster rows summed separately, into a
  top-level `committee_sweeps` list in the snapshot — never merged into
  dataset totals. A standalone `--f24-committee-sweep` mode runs just the
  sweeps. No workflow change was needed (it already runs bare `--all`). The
  first live confirmation is the Sunday Nov 15, 2026 scheduled run: check
  that the snapshot artifact carries `committee_sweeps` with six entries.
- Freshness pre-flight gate — ADDED Nov 12, pending live confirmation on
  the Sunday Nov 15 scheduled run. `pull_freshness.py --all` is now gated
  by default (`src/ingest/pull_gate.py`): one global `/filings/` check per
  family (F6, F24, F3) decides who gets refreshed; state in committed
  `data/source/freshness_state.json`, seeded at the window start
  2026-10-15 for all families (the Nov 12 snapshot covered only two
  persons, so it is not a roster-wide baseline). A gate error falls back
  to the full run, never to a skip. No workflow change (bare `--all` gets
  the gate automatically); `--no-gate` forces the full run. On Sunday
  check the snapshot artifact's `gate` record: `calls_used`,
  `affected_person_keys`, and whether the state file advanced.
- Add the 16 members who served in the 119th but left before Nov 2026
  (Vance, Rubio, Graham, D. Scott, Turner, Grijalva, Connolly, Green,
  Sherrill, Greene, LaMalfa, Gonzales, Swalwell, Cherfilus-McCormick,
  Mullin, Waltz)?
- Refreshes: 120th leadership after Nov 18–19, 2026 elections; TBD seats
  (Alaska ranked-choice tabulation Nov 18, certification ~Nov 25; LA-06
  runoff Dec 12; California certification Dec 11); re-pull once the 2026
  cycle closes (current 2026 money is partial — pas2 through Sep 30,
  2026; weball through Oct 14, 2026; IE data through Oct 31, 2026).
- Data sources: FEC is the spine for disclosed federal money; other
  spending needs other sources (dark money, FCC/Meta/Google ads, state
  disclosure via FollowTheMoney.org, lobbying via Senate Lobbying
  Disclosure). OpenSecrets is a cross-check, not a primary source.
