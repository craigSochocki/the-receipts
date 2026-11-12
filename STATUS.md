# Congress Money Tracker — Status Snapshot

**As of: Thursday, November 12, 2026, ~9:18 AM EST**

## What is built

- **Roster: 664 people** — union of the 119th Congress (540 served) and the
  incoming 120th (535 named): 411 in both, 124 in the 119th only, 124 in the
  120th only, 5 with 120th membership unknown.
- **Career money (FEC filings, cycles 1980–2026, source of truth = FEC bulk
  files; OpenSecrets cross-check only):** individual contributions
  $8,763,847,353.73; corporate PAC $972,228,584.00; AIPAC PAC direct
  $7,567,773.00 (earmark transmitted $191,573.00); UDP independent
  expenditures supporting $42,415,003.76.
- **Ranking:** total accepted (career) = individual + corporate PAC + AIPAC
  PAC direct; UDP excluded, ranked separately. Top 10: Warnock $316.4M,
  Ossoff $295.7M, Kelly $242.1M, Brown $201.0M, Cruz $154.2M, Talarico
  $139.8M, McConnell $123.7M, Schumer $117.7M, Schiff $110.9M, Baldwin
  $104.7M.
- **UDP opposition credit:** $28,281,982.23 credited to the single UDP-backed
  candidate in 15 races (Latimer $9.87M, Bell $5.24M+ $2.46M, Ivey $4.26M
  top). The $20,903,437.57 spent opposing El-Sayed in MI-Sen 2026 is NOT
  credited — UDP backed two candidates there (Stevens in the primary, Rogers
  in the general). Total UDP benefit roster-wide: $70,696,985.99.
- **2026 layer:** per-cycle 2026 columns (individual, corporate PAC, AIPAC
  direct, UDP support, UDP opposition credit, UDP benefit, dirty, clean,
  dependence share); party-by-chamber breakdown for the 120th; clean-money
  view; 2026 primary-target list (House Democrats by dirty_2026: Boafo
  $5,745,013; Bell $3,446,668; Aguilar $1,359,750; Jeffries $1,259,000;
  Clark $1,166,250).
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
- **Corrections applied Nov 12:** clean-in-2026 is 67, not 69 (Russell Fry
  took $338k corporate PAC + $10k AIPAC in 2026); Wesley Bell's 2026
  individual total is $3,221,101.71, not $0 (real $0-individual gaps are
  Melissa Bean and Hilda Solis, $3,500 corporate each); Elaine Luria's
  clean_2026 set to null (unverified — no 2026 data under her linked
  candidate ID), excluded from the verified-clean count.

## Running / next, in order

1. **Ad spending — research running (started Nov 12, ~9:15 AM).** Sources:
   FCC political files (TV), Meta Ad Library, Google Ads Transparency
   Center. Scope: per-candidate ad spend, for/against where the source
   supports it, 2026 cycle first. Build follows the design guide (stage raw
   files first, then per-person columns). Dark money (IRS 990s / ProPublica
   Nonprofit Explorer) deferred until after ads.
2. **Phase 2 — every 2026 candidate (~4,371 FEC candidate IDs), no spending
   threshold,** with primary/general outcome flags (won primary, won
   general, lost, uncalled, runoff) and the same money columns. Good filters
   so the long tail doesn't bury interesting races.
3. **Later layers (North Star):** polling/perception; voting behavior
   (roll calls, sponsorships, priorities); promises vs. reality
   (follow-through scoring, how funding shapes platforms); synthesis into
   the 2028 voter guide.
4. **Public sharing:** tracker is private until Craig explicitly says go.

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
  cycle closes (current 2026 money is partial — weball through Sep 30,
  2026; IE data through Oct 31, 2026).
- Data sources: FEC is the spine for disclosed federal money; other
  spending needs other sources (dark money, FCC/Meta/Google ads, state
  disclosure via FollowTheMoney.org, lobbying via Senate Lobbying
  Disclosure). OpenSecrets is a cross-check, not a primary source.
