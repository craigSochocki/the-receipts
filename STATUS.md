# Congress Money Tracker — Status Snapshot

**As of: Thursday, November 12, 2026, ~10:40 AM EST**

## What is built

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
- **UDP opposition credit:** $28,281,982.23 credited to the single UDP-backed
  candidate in 15 races (Latimer $9.87M, Bell $5.24M+ $2.46M, Ivey $4.26M
  top). The $20,903,437.57 spent opposing El-Sayed in MI-Sen 2026 is NOT
  credited — UDP backed two candidates there (Stevens in the primary, Rogers
  in the general). Total UDP benefit roster-wide: $70,696,985.99.
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
  (the dataset itself always said 67). Curtis 2024 dedup extended to weball
  cols 6–9 (kept-minus-dropped $107,207.83 exactly; roster receipts
  −$5,640,855.75, disbursements −$5,239,012.32, transfers-from
  −$1,261,797.03, transfers-to −$3,300.00; only Curtis's row changed).
  The $21,231.43 all-IE row-sum gap resolved exactly (blank-`sup_opp`
  rows). The $1,004.53 F24 residual reconciled (Aug 3 F3X row, pre-window).
- **Codification — DONE Nov 12, ~10:40 AM EST.** The whole pipeline is
  scripted and one command rebuilds the dataset: `python3
  work/rebuild.py` (build_roster → apply_fec_lookup → pull_money →
  pull_udp → apply_dedup → pull_self_funding → pull_other_committees →
  pull_all_ie → compute_opposition → merge_dataset →
  compute_ranking → compute_2026 → verify_dataset). `work/verify_dataset.py`
  runs 93 standing audits (per-cycle sums for every column family,
  roster totals vs methodology, all 12 rank columns, clean counts and
  the generalized clean rule, 2026 columns, opposition, dedup,
  CSV↔JSON agreement, row order). Verified in a fresh clone with staged
  bulk data: the rebuild reproduces the committed dataset **byte-identically**
  (csv md5 1462a44e2910f27659d7b2239319853e, json md5
  a04a1549dad9882f319d9bf819edc154), every intermediate byte-identical, all
  93 audits passing. The verifier checks the dataset against its own
  definitions — it cannot catch a missing money dimension (see the
  self-funding blind spot below).

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
2. **Static site — APPROVED, after the complete-picture build.** Build
   the tracker page as a static site in `docs/` (generated from the
   canonical dataset) so GitHub Pages can serve it — a link that works on
   iPhone/Android. Craig then enables GitHub Pages in repo Settings →
   Pages. The tracker artifact stays the private version until he says to
   publish.
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
6. **Public sharing:** tracker is private until Craig explicitly says go.

## Open questions

- Opposition credit: split by primary vs. general phase (so anti-El-Sayed
  spending would credit to Stevens in the primary and Rogers in the
  general), or keep the conservative single-backer rule?
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
