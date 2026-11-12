# Congress money tracker — methodology

**Data as of: November 12, 2026.** All source files were pulled on that date; nothing in this
dataset reflects filings or results after it. Re-pull after the 2026 cycle closes and after the
remaining 2026 races are called and certified.

**Files:** `congress-money-tracker.csv` (one row per person) and `congress-money-tracker.json`
(same data; `fec_candidate_ids` is a list; each person also carries `per_cycle` and
`udp_per_cycle` breakdowns). Staged source files and pull logs live in `work/`.

---

## 1. Coverage — who is in the tracker

- **664 persons** (one row each). The source roster contained 665 rows, but Kristen McDonald
  Rivet appeared twice (see §7, "Roster fix"); collapsing her duplicate leaves 664 distinct
  people. **540 served in the 119th Congress; 535 named persons are in the 120th; 411 are in
  both; 124 are 119th-only; 124 are 120th-only; 5 are in the 119th with 120th membership
  unknown** (see below).
- **5 seats TBD / uncalled** (`in_120th = "unknown"`): Dan Sullivan (R-AK, Senate) and
  Nick Begich III (R-AK, House at-large) — races uncalled; Mike Thompson (D-CA-04) and
  Jay Obernolte (R-CA-23) — seats listed TBD; Cleo Fields (D-LA-06) — runoff Dec 12, 2026.
  LA-05 also has no named winner (Julia Letlow left for the Senate) and has no roster row.
  Re-run after these races are called.
- **16 people who served in the 119th but left before November 2026 are excluded.** The roster
  source (`legislators-current.yaml`) lists current members only, so anyone who departed
  earlier is absent. They are: JD Vance, Marco Rubio, Lindsey Graham, David Scott, Sylvester
  Turner, Raúl Grijalva, Gerry Connolly, Mark Green, Mikie Sherrill, Marjorie Taylor Greene,
  Doug LaMalfa, Tony Gonzales, Eric Swalwell, Sheila Cherfilus-McCormick, Markwayne Mullin,
  and Mike Waltz. Add them from `legislators-historical.yaml` if full "anyone who served in
  the 119th" coverage is wanted. This is a scope gap, not a data error.
- **Delegates (6)** are included as House members with `district = 0`, matching the source
  repo's convention (0 = at-large / delegate).
- **120th results are media calls, uncertified.** 120th membership was transcribed from
  Wikipedia's "120th United States Congress" page (Nov 12, 2026) and cross-checked against
  its "List of new members" page; per-state House counts match apportionment exactly
  (430 named of 435 seats) and the Senate is 99 named of 100.
- **120th leadership is all TBD** (`leadership_120 = "TBD"` for every row). Leadership
  elections are Nov 18–19, 2026. 119th leadership (17 roles) is recorded in
  `leadership_119` and was verified against Wikipedia, history.house.gov, and the
  Senate/House leadership pages.
- **Party labels:** DFL (Minnesota) is normalized to Democrat. PR Resident Commissioner
  Pablo Hernández Rivera is kept as PPD. Kevin Kiley (CA-03) is recorded as Independent in
  the 119th (he left the Republican Party Mar 9, 2026).
- **Chamber switchers (House → Senate, 6 in the 120th):** Andy Barr, Harriet Hageman,
  Kevin Hern, Julia Letlow, Barry Moore, Chris Pappas. Six freshmen are returning former
  members (Jerry Carl, Hilda Solis, Melissa Bean, Colin Allred, Ben McAdams, Elaine Luria);
  their historical FEC IDs were used — confirm they match the 2026 candidacy before
  re-using this join.
- **Early / special swearing-ins:** Kevin Hern (OK) moves House → Senate Nov 30, 2026;
  Sherrod Brown (OH) takes his Senate seat Dec 15, 2026; Jon Husted serves until Dec 15,
  2026; Alan Armstrong (OK, appointed) serves until Nov 30, 2026; Darline Graham (SC,
  appointed) serves to Jan 3, 2027. Amy Klobuchar (MN) and Marsha Blackburn (TN) were
  elected governor and plan to resign from the Senate in Jan 2027; they are counted as in
  the 120th as seated at its start, successors TBD.

---

## 2. Column definitions

| Column | Definition |
|---|---|
| `person_key` | Join key. A bioguide-style ID where one exists (e.g. `M001237`); otherwise a slug built from name + state + chamber (e.g. `kristen-mcdonaldrivetmihouse` was the slug for the duplicate Rivet row — see §7). |
| `full_name` | Person's name as in the roster. |
| `chamber_119`, `chamber_120` | `House` / `Senate`, blank if not in that Congress. |
| `state` | Two-letter state (or territory / DC for delegates). |
| `district_119`, `district_120` | House district number; `0` for at-large seats and delegates; blank for Senators and for Congresses the person is not in. |
| `party_119`, `party_120` | Party in that Congress; blank if not in it. |
| `leadership_119`, `leadership_120` | Leadership role in that Congress; blank if none. `leadership_120` is `TBD` for everyone (see §1). |
| `in_119th`, `in_120th` | `yes` / `no`; `in_120th` is `unknown` for the 5 TBD seats in §1. |
| `fec_candidate_ids` | Every FEC candidate ID for the person, semicolon-joined in the CSV, a list in the JSON. A person who moved House → Senate has one ID per office; money is summed across all of them and all cycles 1980–2026. One person (Alan Armstrong) has none. |
| `individual_contribution_total_career` | **Career total of individual contributions** (itemized + unitemized) to the person's campaign(s), summed across all their candidate IDs and all FEC cycles 1980–2026. Source: `TTL_INDIV_CONTRIB` (col 18) of the FEC all-candidates file (`weball`). **De-duplicated (corrected Nov 12, 2026 — see §8.15):** where weball repeats the identical `TTL_INDIV_CONTRIB` under two of a person's candidate IDs in the same cycle (one principal committee reported under both a House and a Senate ID), the amount is counted **once** per (person, cycle). Groups where same-cycle amounts *differ* across IDs are genuinely different money and are still summed in full. Roster-wide individual total after the correction: **$8,763,847,353.73** (was $9,215,623,369.07 before it; correction $451,776,015.34 across 32 persons / 90 (person, cycle) groups). |
| `aipac_pac_direct_career` | **HEADLINE AIPAC column — TOTAL Schedule B disbursements from the AIPAC PAC (C00797670) to the person's campaign(s), 2022–2026.** This is the sum of *all* `24K`/`24P` pas2 rows from that committee: the PAC's own money **plus** earmarked/bundled individual checks transmitted through it. See the AIPAC decision box below. |
| `aipac_earmark_transmitted_career` | **Breakout (subset of the headline column):** the part of `aipac_pac_direct_career` that is individual donors' earmarked money transmitted through the AIPAC PAC as a conduit (pas2 rows whose memo text names a donor, e.g. `EARMARK OF <donor>. TRANSMITTED BY CHECK/EFT`). **PAC own-money = `aipac_pac_direct_career` − `aipac_earmark_transmitted_career`.** Career own-money total: **$7,376,200** (headline $7,567,773 − earmark $191,573). |
| `corporate_pac_career` | Career total of direct contributions from **corporate-connected PACs**, 1980–2026. A committee counts as corporate if, in the same cycle's committee-master file, `CMTE_TP IN ('Q','N')` **and** `ORG_TP IN ('C','W')` (corporation / corporation without capital stock). Trade associations (`T`, e.g. NAR PAC), labor (`L`), membership orgs (`M`, including the AIPAC PAC itself), cooperatives (`V`), and hybrid PACs (`CMTE_TP` V/W) are excluded. Committees with blank `ORG_TP` are treated as unclassified, never corporate. |
| `corporate_earmark_transmitted_career` | Breakout (subset of `corporate_pac_career`): earmarked transmissions through corporate PACs, on the same definition as the AIPAC earmark column. Career total $26,850 across 14 persons. Corporate own-money = corporate − this column. |
| `udp_ie_support_career` | **United Democracy Project (UDP, C00799031) independent expenditures SUPPORTING the person's race, 2022–2026 only.** This is money UDP spent *about* the race (ads, mail, phones) — independent expenditures, legally uncoordinated with the campaign. **It is not money given to the campaign and must never be described as a contribution.** Support only: UDP spending *opposing* a person is never added to any total; where it exists it is recorded in `data_notes` only (7 people — see §5). |
| `cand_contrib_career`, `cand_loans_career` | **Self-funding, career.** Candidate contributions (`CAND_CONTRIB`, weball col 12) and candidate loans (`CAND_LOANS`, col 13), summed across all of a person's candidate IDs and all cycles 1980–2026. Roster totals: contributions **$127,959,956.91**, loans **$325,314,576.77**. |
| `self_funding_career` | Candidate contributions + candidate loans. Roster total **$453,274,533.68**. Top: Rick Scott $89,994,251.12; Darrell Issa $27,875,844.99; David McCormick $22,090,582.51; Pete Ricketts $19,442,012.33; Shri Thanedar $17,456,074.00; Anthony Constantino $17,000,000.00 exactly. |
| `loan_repayments_career` | Loan repayments to the candidate (weball cols 15+16), career. Roster total **$117,267,525.92**. |
| `debts_owed_by_career` | Debts owed BY the committee, career = the **latest cycle's** value (a stock, not a sum across cycles). Roster total (latest-cycle sum) **$191,691,118.19**. |
| `debts_owed_to_career` | Debts owed TO the committee — **null for every person**: no weball column carries it. The FEC API candidate-totals field `last_debts_owed_to_committee` is the follow-up route; it was not backfilled (see §16). |
| `total_receipts_career`, `total_disbursements_career` | Total receipts (`TTL_RECEIPTS`, weball col 6) and total disbursements (`TTL_DISB`, col 8), career sums. Roster totals: receipts **$13,123,758,383.28**, disbursements **$12,119,674,234.67**. |
| `transfers_from_auth_career`, `transfers_to_auth_career` | Transfers from / to other authorized committees of the same candidate (weball cols 7 / 9), career sums. Roster totals: from **$1,084,116,950.90**, to **$196,548,621.70**. |
| `cash_on_hand_career` | Cash on hand (`COH_COP`, weball col 11), career = the **latest cycle's** value (a stock, not a sum). Roster total (latest-cycle sum) **$1,011,890,622.93**. |
| `party_committees_career`, `leadership_pacs_career`, `labor_pacs_career`, `trade_pacs_career`, `membership_pacs_career`, `cooperative_pacs_career`, `other_unclassified_career` | **Other-committee contributions, career** — direct contributions from committees that are NOT corporate PACs and NOT the AIPAC PAC, classified from the same-cycle committee-master file: party = `CMTE_TP IN ('X','Y')`; leadership = `CMTE_DSGN == 'D'`; labor = `CMTE_TP IN ('Q','N')` + `ORG_TP == 'L'`; trade = Q/N + `T`; membership = Q/N + `M`; cooperative = Q/N + `V`; other_unclassified = everything else (19.3% of the total — see §4 for the composition). Roster totals: party $12,452,000; leadership $232,556,005; labor $293,658,668; trade $476,385,811; membership $220,580,356; cooperative $30,134,616; other_unclassified $302,968,291. |
| `other_committees_total_career` | Sum of the seven other-committee classes above. Roster total **$1,568,735,747.00**. This EXCLUDES corporate PAC money and AIPAC direct, which stay in their existing columns — the three families are disjoint by construction. Top career takers: Pallone $17,794,814; Hoyer $15,801,231; McConnell $11,203,442; Sherrod Brown $10,981,813; Pelosi $10,105,781. |
| `*_earmark_transmitted_career` (7 columns) | Career-only earmark-transmitted breakouts, one per other-committee class (`party_committees_earmark_transmitted_career`, etc.), matching the existing AIPAC/corporate earmark-breakout precedent. Roster total $5,500,260 (party $18,743; leadership $786,779; labor $790; trade $456,352; membership $2,479,868; cooperative $0; other_unclassified $1,633,442). |
| `all_ie_support_career`, `all_ie_oppose_career`, `all_ie_total_career` | **All independent expenditures about the person's race, 2022–2026 ONLY** (the 2010–2020 IE files are not staged — see §8). Support + oppose from every registered committee, not just UDP. `all_ie_total = support + oppose + blank-direction rows` (see §4 for the $21,231.43 reconciliation). Roster totals (distinct persons): support **$1,490,363,373.56**, oppose **$2,351,872,876.19**, total **$3,842,257,481.18**. Top: Talarico $259,873,813.32; Husted $197,481,557.46; Sherrod Brown $151,242,621.14; El-Sayed $148,486,253.91. Like UDP, this is spending *about* the race, never money given to the campaign. |
| `self_funding_per_cycle`, `other_committees_per_cycle`, `all_ie_per_cycle` (JSON only; also as repr strings in the CSV) | Per-person, per-cycle breakdowns of the three new families. `self_funding_per_cycle` carries the weball flow columns plus `coverage_end_date` per (candidate, cycle); `other_committees_per_cycle` carries the seven classes plus an `earmark_transmitted` sub-dict; `all_ie_per_cycle` carries support/oppose/total. Only cycles with a nonzero value are listed. Each sums to its career columns exactly (0 mismatches — verified in `work/verify_dataset.py`, checks (j)–(l)). |
| `all_ie_top_committees` (JSON only) | Top 5 committees per person by career all-IE total, with support/oppose split (committee name taken from the largest single (candidate, cycle) total). Null for Armstrong; `[]` for people with no IE spending. Example — Constantino's top: House Majority PAC $1,482,254 oppose; Invest in Tomorrow Coalition PAC $1,283,283.97 oppose; YOUR COMMUNITY PAC $499,066.68 oppose. El-Sayed's top: NO GOING BACK PAC $27,461,680.99 oppose; UDP $20,903,437.57 oppose; GLCF $19,557,129.77 oppose; WinSenate $12,551,320 support; AFP Action $11,880,001.04 oppose. |
| `data_as_of` | `2026-11-12` for every row. |
| `data_notes` | Per-person notes carried from the money pulls (search outcome, multi-ID summation, oppose spending, name-attributed UDP rows, special cases). See §5. |
| `per_cycle` (JSON only) | Per-person, per-cycle, per-candidate-ID breakdown of the five pas2/weball columns (`individual`, `aipac_pac_direct`, `aipac_earmark_transmitted`, `corporate_pac`, `corporate_earmark_transmitted`). Only cycles with a nonzero value are listed. Sums to the career columns exactly (0 mismatches across all 664 persons — verified in the merge). |
| `udp_per_cycle` (JSON only) | Per-person, per-cycle breakdown of UDP support (`udp_ie_support`), with `candidate_id`. Only cycles with nonzero support are listed (13 persons, 15 entries). Sums to `udp_ie_support_career` exactly. For the three 2022 name-attributed rows the entry carries `"attribution": "name_state_district_office_match; cand_id blank in FEC file"` and the `candidate_id` is the person's roster FEC ID for that race (see §4). |

### AIPAC headline decision (read this before quoting any AIPAC figure)

The headline column `aipac_pac_direct_career` is the **total of the raw Schedule B rows**
from the AIPAC PAC — PAC own-money **plus** earmarked/bundled individual checks transmitted
through it. This was a deliberate, coordinator-approved choice, and it exists because the
spec's raw-rows approach was specifically meant to capture bundled checks that FEC summary
aggregates drop. The motivating example: for one 2024 recipient the FEC summary aggregates
showed $8,500 while the raw Schedule B rows totalled $726,000 — the difference is bundled
individual checks transmitted through the PAC. Using only the summary figure would understate
what flowed through the PAC by two orders of magnitude.

The consequence is that the headline figure is **not** "the PAC's own money." That is why the
separate `aipac_earmark_transmitted_career` column exists: subtract it from the headline to
get PAC own-money. Example — Josh Gottheimer's career headline is $93,630, of which $65,730
is earmarked transmissions; his PAC own-money is $27,900. **Always state which of the two
figures you are quoting.** The earmarked money is also already inside the candidate's
`individual_contribution_total_career` (weball), because it is individuals' money — it is
counted in both columns by design, and the two columns must never be added together.

Related rules applied in the pull (see `work/pull-log-a.md` §4): **negative earmark rows
(voided/refunded conduit earmarks) were excluded from all totals** — 1,375 roster-matched
rows (−$624,280) — because their originals are not in pas2, so netting them creates phantom
negatives (e.g. Maria Cantwell would otherwise show −$15,500 with zero positive AIPAC rows).
**Positive earmark rows were kept in the headline** and broken out. The 2024 `ERMK:`
re-report rows ($21,410, amended filing 1734505, "ORIGINALLY FORWARDED … SEE JULY 2022
MONTHLY") are counted in the earmark column; they may re-attribute money already counted
via 2022 originals — a possible ~$21k overstatement in the 2024 cycle, not surgically
removable (originals cannot be reliably matched; different TRAN_IDs).

### UDP support-only rule

`udp_ie_support_career` counts `sup_opp = 'S'` rows only. Oppose spending is spending
*against* a candidate; netting it against support would be meaningless, so it is excluded
from every total and recorded in `data_notes` only. The 7 roster persons with UDP oppose
spending noted are: Abdul El-Sayed ($20,903,437.57), Dave Min ($4,615,288.76), Thomas Massie
($3,896,751.38), Summer Lee ($3,264,153.49), Aisha Wahab ($1,642,139.53), Shri Thanedar
($1,428,679.18), George Latimer ($84,325.84).

---

## 3. Sources

**FEC bulk files are the source of truth for every figure.** The FEC API was used for
spot-checks only; OpenSecrets was used as a cross-check only (see §6).

| Data | Source file(s) (staged under `work/bulk/`) | Method |
|---|---|---|
| Individual contributions | `weball/weballYY.txt`, cycles 1980–2026 (24 files, 70,381 rows) | `TTL_INDIV_CONTRIB`, col 18, summed per (candidate, cycle), then across all of a person's candidate IDs — **with exact-equal copies under two IDs in the same cycle counted once** (de-duplication verified and applied Nov 12, 2026; see §8.15). No duplicate `CAND_ID` rows exist within any cycle's weball file. Amounts summed as integer cents. |
| AIPAC PAC direct + earmarks | `pas2/<cycle>/itpas2.txt`, cycles 2022/2024/2026 only (the PAC's only active cycles) | Rows with `CMTE_ID = 'C00797670'`, `TRANSACTION_TP IN ('24K','24P')`. Earmark rows identified by memo text containing `EARMARK` or starting `ERMK:`. |
| Corporate PAC | `pas2/<cycle>/itpas2.txt`, all 24 cycles (7,879,684 rows) joined to `cm/<cycle>/cm.txt`, all 24 cycles (298,679 rows) | pas2 `24K`/`24P` rows whose contributing committee satisfies `CMTE_TP IN ('Q','N')` and `ORG_TP IN ('C','W')` in the **same-cycle** committee-master file. |
| UDP independent expenditures | `bulk/ie/<cycle>/independent_expenditure_<cycle>.csv`, cycles 2022/2024/2026 | `spe_id = 'C00799031'`, `sup_opp = 'S'`, summed by `cand_id` after dedup by `tran_id` (keep latest `receipt_dat`, tie-break highest `file_num`). See §4. |
| Self-funding + topline | `weball/weballYY.txt`, cycles 1980–2026 (same 24 files as the individual pull) | Weball cols (1-indexed): 6 `TTL_RECEIPTS`, 7 `TRANS_FROM_AUTH`, 8 `TTL_DISB`, 9 `TRANS_TO_AUTH`, 11 `COH_COP`, 12 `CAND_CONTRIB`, 13 `CAND_LOANS`, 15+16 loan repayments, 17 `DEBTS_OWED_BY`, 28 `CVG_END_DT`. Career flows are sums; cash on hand and debts owed by are the latest cycle's value (stocks). No weball column exists for debts owed *to* the committee (null everywhere). The Curtis 2024 extension (§8.15) zeroes the dropped copy for cols 6–9 as well as 10–18. Script: `work/pull_self_funding.py`. |
| Other-committee contributions | `pas2/<cycle>/itpas2.txt`, all 24 cycles, joined to `cm/<cycle>/cm.txt` (same-cycle committee master) | pas2 `24K`/`24P` rows whose contributing committee is NOT corporate (Q/N + C/W) and NOT the AIPAC PAC, classified by `CMTE_TP` / `ORG_TP` / `CMTE_DSGN` as in §2. Cross-checks re-derive the corporate ($972,228,584), corporate earmark ($26,850), AIPAC direct ($7,567,773) and AIPAC earmark ($191,573) totals to the cent. Script: `work/pull_other_committees.py`; diagnostics in `work/other_committees_diagnostics.json`. |
| All independent expenditures | `bulk/ie/<cycle>/independent_expenditure_<cycle>.csv`, cycles 2022/2024/2026 (same three files as the UDP pull) | Every row whose spender is a **registered committee** (`spe_id` in the same-cycle `cm` file) and whose candidate is **identified** (`cand_id` non-blank), summed by (candidate, cycle) after dedup on (`spe_id`, `tran_id`) — NOT `tran_id` alone. Blank-`cand_id` rows are excluded from the published totals, including Congressional Leadership Fund, which files `cand_id` blank systematically (2024 $105.5M / 2026 $199.2M roster-resolved by name — see §8). Script: `work/pull_all_ie.py`. |

Committee IDs (verified Nov 12, 2026 via the OpenFEC API — see `work/fec-sources.md` §1):
**AIPAC PAC = `C00797670`** (American Israel Public Affairs Committee Political Action
Committee; first F1 filed Dec 15, 2021; cycles 2022/2024/2026 only) and **UDP =
`C00799031`** (United Democracy Project, Super PAC; first F1 filed Jan 3, 2022; cycles
2022/2024/2026 only). **There are no AIPAC PAC or UDP figures before 2022** — earlier
cycles are legitimately $0 for those two columns, not missing data. Do not backfill
pre-2022 "AIPAC money" from other pro-Israel PACs (e.g. Democratic Majority for Israel,
USI PAC, Friends of Israel PAC) — they are separate committees, not the AIPAC PAC.

**Corrected source — the `oppexp` files are NOT Schedule E.** `work/fec-sources.md` §4
originally labelled the FEC `oppexpYY.zip` bulk files as independent expenditures. That is
wrong: the staged `oppexp` files (12 cycles, 2004–2026) are 26-column Schedule B
**operating-expenditure** files — no candidate column, no support/oppose column (UDP rows
in them are Uber, credit-card and hotel payments). No `oppexp` data was used for any figure
in this dataset. The correct source is `independent_expenditure_<cycle>.csv` from the FEC
bulk-data index (23 columns; `cand_id`, `spe_id`, `sup_opp`, `exp_amo`):

| Cycle | File | Size | Rows (incl. header) | MD5 |
|---|---|---|---|---|
| 2022 | `bulk/ie/2022/independent_expenditure_2022.csv` | 16 MB | 61,780 | `02b1eb886087c259558916f19a7c3045` |
| 2024 | `bulk/ie/2024/independent_expenditure_2024.csv` | 19 MB | 73,450 | `2eda312ee4ef9e49f6065b0ee273af86` |
| 2026 | `bulk/ie/2026/independent_expenditure_2026.csv` | 14 MB | 51,244 | `c34c56cb50dfc2d6cc71c074a92171a6` |

Server `Last-Modified` for all three: Thu Nov 12, 2026 10:13 GMT. The 573 MB of staged
`oppexp` files were left in place; whether to keep or delete them is a coordinator decision.

**Roster sources:** 119th membership from `legislators-current.yaml`
(unitedstates/congress-legislators, fetched Nov 12, 2026; 539 persons) plus Sherrod Brown;
120th membership from Wikipedia (see §1); returning former members from
`legislators-historical.yaml`; FEC IDs for 120th freshmen matched via the OpenFEC API on
office + state + district + party for the 2026 cycle (113 of 121 automatic, 7 manual
name-variant fixes — see `work/roster-notes.md`).

**What was NOT used:** the FEC API totals endpoints (unreliable — see §8); the `indiv`
bulk files (tens of GB; weball already aggregates them); the `oth` bulk files except for a
one-off 2024 refund check (see §8); the F3X summary line 23 ($53.7M — not a
candidate-level figure: it includes earmark pass-throughs and contributions to other
committees).

---

## 4. How the money was pulled (method summary)

Full detail is in `work/pull-log-a.md` (pas2/weball) and `work/pull-log-b.md` (UDP).
The points that matter for interpreting the numbers:

- **Join key:** FEC candidate ID. A person with several IDs is summed across all of them
  and all cycles 1980–2026 (individual / corporate) or 2022–2026 (AIPAC / UDP).
- **Amended-filing dedup (pas2):** dedup on `TRAN_ID` alone was tested and found **unsound**
  — some filers reuse line-number-style TRAN_IDs across reports (e.g. three distinct
  contributions sharing one TRAN_ID). Adopted key: (`CMTE_ID`, `TRAN_ID`, `CAND_ID`,
  `TRANSACTION_AMT`, `TRANSACTION_DT`, `RPT_YR`) per cycle file, preferring non-memo rows,
  tie-break latest `FILE_NUM`. Effect: **198 rows dropped, $369,558** (all corporate; no
  AIPAC roster rows collided under the refined key). The naive TRAN_ID-only dedup would
  have overstated the corporate total by $2,201,359.
- **Memo rows kept (pas2):** FEC guidance says memo items "should be included in your
  analysis," and testing confirmed it — blanket-excluding `MEMO_CD='X'` would drop $2,000
  of genuine redesignation entries in AIPAC 2024. The dedup rule removes the one true
  duplicate instead.
- **Refund netting:** pas2 negative rows are included in the sums, so the AIPAC and
  corporate columns are **net of refunds/voids as recorded by negative pas2 rows**. The
  flagged 17Z question was tested for 2024 only: `oth24` was downloaded and streamed —
  **zero 17Z rows** for AIPAC in 2024, and all 1,931/1,931 pas2 AIPAC 24K/24P rows appear
  identically in `oth24` by `SUB_ID`. The F3X summary's `fed_candidate_contribution_refunds`
  ($32,100 for 2024) is captured inside pas2's negative 24K rows. **oth for 2022/2026 was
  not downloaded** — the same check was not repeated for those cycles (see §8).
- **UDP dedup:** the IE files contain original + amended reports. Dedup by `tran_id`
  (latest `receipt_dat`, tie-break highest `file_num`). Two independent implementations of
  the rule give identical totals in all three cycles. Without dedup, 2024 would be
  overstated by $999,125.80 (one duplicated oppose row) and 2022 by $2,501,022.03.
  Deduped UDP totals (all candidates): 2022 $26,107,515.77; 2024 $38,044,932.69;
  2026 (partial) $54,322,881.51.
- **UDP 2022 blank-`cand_id` rows — name-resolved.** 100 of the 185 deduped 2022 UDP rows
  have a blank `cand_id` (the filer did not supply it). Where `cand_name` + state + district
  + office matches exactly one roster person, the support was attributed to that person and
  flagged in `data_notes` and in `udp_per_cycle` (`attribution` field). That added
  **$4,819,602.26** across 3 people: Donald G. Davis ($2,102,637.82, NC-01), Valerie P.
  Foushee ($2,128,196.18, NC-04), Kevin Mullin ($588,768.26, CA-15). None of the three has
  any `cand_id`-bearing UDP support row in 2022, so there is no double-counting. The
  remaining blank-ID support ($660,319.30, Steven Irwin, PA-12) belongs to a non-roster
  candidate and is excluded; blank-ID oppose rows are never counted as support. 2024 and
  2026 have **zero** blank-`cand_id` UDP rows, so this issue is 2022-only. **An ID-only
  version would put Davis, Foushee and Mullin at $0** and lower the 2022 roster UDP total
  to $6,116,804.44 — this is a judgment call, disclosed here, not a data error.
- **UDP roster support by cycle:** 2022 $10,936,406.70; 2024 $13,980,903.77; 2026 (partial)
  $17,497,693.29. **13 of 664 roster persons have UDP support > $0; 650 are $0.00** (plus
  Alan Armstrong, whose UDP figure is `unknown` — see §5).
  Top: Haley M. Stevens $14,376,765.69; Adrian Boafo $5,734,013.28; George Latimer
  $4,682,560.29; Sarah Elfreth $4,218,074.08; Wesley Bell $4,041,905.41.
- **AIPAC roster totals by cycle:** 2022 $2,155,300 (earmark $500); 2024 $2,757,810
  (earmark $21,410); 2026 $2,654,663 (earmark $169,663). Top career AIPAC: Gottheimer
  $93,630; Josh Riley $40,181; Ted Lieu $36,302. Top career corporate: Hoyer $14,673,995;
  McConnell $12,341,700; Neal $12,157,658. Top career individual: Warnock $316,226,119.10;
  Ossoff $295,701,989.71; Kelly $242,078,530.22; Brown $195,719,509.72; Cruz
  $152,064,880.63. (Before the §8.15 de-duplication the #5 spot was Schiff at
  $162,422,170.20; his corrected total is $108,856,103.98.)
- **Coverage of the pulls (final 664-row dataset):** individual ≠ 0 for 661 persons; AIPAC ≠ 0 for 421 (420 positive, 1 negative — Patrick Ryan); corporate
  ≠ 0 for 602; AIPAC earmark > 0 for 32 persons; corporate earmark > 0 for 14 persons.
  Zero matched pas2 rows had a contributing committee missing from the same-cycle
  committee-master file (classification coverage 100%). Zero bad-field rows in any
  weball/cm/pas2 file.
- **Corporate-PAC edge case:** `NEA FUND FOR CHILDREN AND PUBLIC EDUCATION` carries
  `ORG_TP=C` in cm24 despite being labor-affiliated; it counts as corporate under the
  Q/N + C/W rule as written. Any reclassification is a methodology decision, not a data
  error.
- **Self-funding / topline pull (`work/pull_self_funding.py`).** Reads the same 24 weball
  files as the individual pull and emits one row per (candidate, cycle) with the flow
  columns, the two stock columns, and `coverage_end_date` (col 28). Career stocks take
  the latest cycle's value; a person with no weball rows at all has null stocks (not $0).
  Guard: the Curtis 2024 extension (§8.15) is enforced in the pull — if the kept-minus-
  dropped arithmetic for cols 6–9 does not come out to exactly $107,207.83, the pull
  fails loudly rather than silently emitting wrong figures.
- **Other-committee pull (`work/pull_other_committees.py`).** Same pas2+cm join as the
  corporate pull, same dedup key, but the classification inverts it: everything that is
  not corporate and not the AIPAC PAC, split into the seven classes of §2. The
  `other_unclassified` class is 19.3% of the total; its composition (career): Q/N
  blank-`ORG_TP` PACs $193.1M, other candidates' campaign committees $68.9M, hybrid PACs
  (`CMTE_TP` V/W) $37.9M, joint fundraisers (`J`) $8.1M, super PACs $0.19M, and WinRed
  (C00694323) −$5.24M — WinRed is a conduit, kept inside unclassified per the never-drop
  rule and flagged in `data_notes` wherever it is nonzero. **Scalise-type negative
  residual (known limitation, §8):** for a handful of people the pas2-derived
  other-committee total is lower than the weball col 26 figure by more than the
  corporate+AIPAC amounts can explain; the mechanism is unresolved (likely joint-
  fundraising-committee / transfer reporting) and needs the `oth` bulk file or F3
  line-item work — no figure was adjusted to force a match.
- **All-IE pull (`work/pull_all_ie.py`).** Same three IE bulk files as the UDP pull, but
  every registered committee, not just UDP. Dedup key is (`spe_id`, `tran_id`): `tran_id`
  alone is unsound because different spenders reuse transaction IDs. Filter: spender must
  be a registered committee in the same cycle's `cm` file, and `cand_id` must be
  identified — this is what removes the tens of billions in bogus filings. Excluded
  amounts by bucket: 2022 raw $46,938.9M → included $1,666.6M; 2024 raw $49,679.4M →
  $3,438.5M; 2026 raw $42,826.7M → $3,326.9M. **The $21,231.43 row-sum discrepancy is
  resolved exactly:** the coordinator's row-sum of `work/all_ie.csv` ($3,845,189,042.23)
  summed support+oppose, while the pull's row-sum ($3,845,210,273.66) summed the total
  column — the $21,231.43 gap is exactly the roster subset of blank-`sup_opp` rows,
  counted in the total column only (Gallego 2024 $182.73; Tran 2024 $11,521.93; Tran
  2026 $5,641.70; Goldman 2026 $3,885.07). All-candidates no-direction total is
  $454,183.37. **Validation:** UDP 2024 deduped $38,044,932.69, exact to the cent.
  Roster-targeted cycle totals: 2022 $635,983,318.22; 2024 $957,619,902.44; 2026
  $2,248,654,260.52 (targets $635.2M / $959.1M / $2,264.3M — residuals concentrated in
  2026 oppose-vs-House, consistent with a slightly different roster snapshot; the rule
  was not tweaked to chase them). Top 2026 spenders: NO GOING BACK PAC $202,510,758.40
  (oppose), House Majority PAC $146,738,795.63 (oppose), WinSenate $131,103,921.28
  (oppose), TEXAS PAC $112,153,741.90 (oppose), DEFEND AMERICAN JOBS $70,681,048.37
  (support). **"Career" for all-IE means 2022–2026 only** — the 2010–2020 IE files exist
  on the FEC server but are not staged; downloading them is a follow-up, not this build.
  The pull also emits `work/all_ie_top_committees.json` (top 5 committees per person by
  career all-IE total, support/oppose split; grouped by `committee_id`, name from the
  largest single (candidate, cycle) total).
- **Rivet collapse validation extended.** The merge's collapse check now covers ALL
  per-cycle files (self-funding, other-committees, all-IE): both Rivet person_keys share
  FEC ID `H4MI08218`, so the values must be identical in each file, and the merge fails
  loudly on any mismatch. Per-person roster-total sums double-count her $2,952,792.48
  career all-IE / $2,219,737 other-committee (same convention as the existing §6
  methodology totals); the merged dataset rows do not double-count.

---

## 5. Special rows

- **Alan Armstrong (`A000383`) — money columns are `"unknown"`, not 0.** Appointed senator
  (OK, Mar 2026) who never ran for the seat; no FEC candidate ID exists, so no FEC search
  is possible — not even for UDP. All six money columns read `unknown` in both files, with
  a note saying so. Do not treat him as $0 in averages or totals (he is excluded from the
  reconciliation sums in §7).
- **Everton Blair Jr. (`H6GA13062`) — 0 with a note.** FEC ID present, but no weball or
  pas2 rows at all: "no FEC activity found."
- **Anthony Constantino (`H6NY21157`) — $0 in the tracked columns, $17M self-funded.**
  His individual / corporate / AIPAC / UDP totals are all $0.00 ("FEC activity found; all
  totals zero" — and that zero is now *verified*, see §14: he has 2026 self-funding and
  all-IE entries). But his campaign is largely self-funded: candidate loans $17,000,000.00
  exactly (2024 $2.6M + 2026 $14.4M), total receipts $17,064,951.19, disbursements
  $14,765,966.71, 2026 cash on hand $2,298,984.48. Do not describe him as having raised
  nothing — describe him as having raised nothing *from others*.
- **Patrick Ryan (`R000579`) — AIPAC −$10,000, kept as computed.** Rows: +$5,000 (2022),
  +$5,000 (2026 M12), +$5,000 (2026 amended M10), and five −$5,000 rows in the 2026 M8
  filing voiding prior-cycle contributions whose originals are not in pas2 as 24K rows —
  the same structural asymmetry as the earmark voids in §2, but without earmark memo text,
  so no text-based rule can separate them. Kept as-is; flagged in `data_notes`. This is
  the **only negative career total in any column**.
- **UDP oppose spending** is in `data_notes` only, never in any total (see §2).

---

## 6. Reconciliation and spot-checks

### Roster-wide sums (664 distinct persons, Nov 12, 2026)

| Column | Merged total (664 rows) | Pull total (665 rows, Rivet counted twice) | Difference | Explanation |
|---|---:|---:|---:|---|
| Individual contributions | **$8,763,847,353.73** | $9,224,969,929.06 | −$461,122,575.33 | Rivet counted once, not twice (−$9,346,559.99) **plus the §8.15 weball de-duplication (−$451,776,015.34)** |
| AIPAC PAC direct | $7,567,773.00 | $7,567,773.00 | $0.00 | Rivet's AIPAC total is $0 |
| AIPAC earmark transmitted | $191,573.00 | $191,573.00 | $0.00 | — |
| Corporate PAC | $972,228,584.00 | $972,722,564.00 | −$493,980.00 | Rivet counted once, not twice |
| Corporate earmark transmitted | $26,850.00 | $26,850.00 | $0.00 | — |
| UDP IE support | $42,415,003.76 | $42,415,003.76 | $0.00 | Rivet's UDP total is $0 |
| Candidate contributions | **$127,959,956.91** | $127,967,614.21 | −$7,657.30 | Rivet counted once, not twice |
| Candidate loans | $325,314,576.77 | $325,314,576.77 | $0.00 | Rivet's loans are $0 |
| Self-funding (contrib + loans) | **$453,274,533.68** | $453,282,190.98 | −$7,657.30 | Rivet counted once, not twice |
| Loan repayments | $117,267,525.92 | $117,267,525.92 | $0.00 | — |
| Total receipts | **$13,123,758,383.28** | $13,142,389,149.63 | −$18,630,766.35 | Rivet counted once (−$12,989,910.60) **plus the Curtis 2024 extension, §8.15 (−$5,640,855.75)** |
| Total disbursements | **$12,119,674,234.67** | $12,135,228,288.49 | −$15,554,053.82 | Rivet counted once (−$10,315,041.50) **plus the Curtis extension (−$5,239,012.32)** |
| Transfers from auth | **$1,084,116,950.90** | $1,086,095,264.80 | −$1,978,313.90 | Rivet counted once (−$716,516.87) **plus the Curtis extension (−$1,261,797.03)** |
| Transfers to auth | **$196,548,621.70** | $196,551,921.70 | −$3,300.00 | **Curtis extension only** (Rivet's transfers-to are $0) |
| Cash on hand (latest-cycle sum) | **$1,011,890,622.93** | $1,014,565,492.03 | −$2,674,869.10 | Rivet counted once, not twice |
| Debts owed by (latest-cycle sum) | $191,691,118.19 | $191,691,118.19 | $0.00 | Rivet's debts are $0 |
| Party committees | $12,452,000.00 | $12,462,203.00 | −$10,203.00 | Rivet counted once, not twice |
| Leadership PACs | $232,556,005.00 | $233,044,255.00 | −$488,250.00 | Rivet counted once, not twice |
| Labor PACs | $293,658,668.00 | $294,097,168.00 | −$438,500.00 | Rivet counted once, not twice |
| Trade PACs | $476,385,811.00 | $476,628,002.00 | −$242,191.00 | Rivet counted once, not twice |
| Membership PACs | $220,580,356.00 | $220,879,178.00 | −$298,822.00 | Rivet counted once, not twice |
| Cooperative PACs | $30,134,616.00 | $30,170,866.00 | −$36,250.00 | Rivet counted once, not twice |
| Other unclassified | $302,968,291.00 | $303,673,812.00 | −$705,521.00 | Rivet counted once, not twice |
| Other-committee total | **$1,568,735,747.00** | $1,570,955,484.00 | −$2,219,737.00 | Rivet counted once, not twice |
| All-IE support (2022–2026) | **$1,490,363,373.56** | $1,491,815,311.74 | −$1,451,938.18 | Rivet counted once, not twice |
| All-IE oppose (2022–2026) | **$2,351,872,876.19** | $2,353,373,730.49 | −$1,500,854.30 | Rivet counted once, not twice |
| All-IE total (2022–2026) | **$3,842,257,481.18** | $3,845,210,273.66 | −$2,952,792.48 | Rivet counted once, not twice (the pull-file sum is the total column; see the $21,231.43 note in §4) |
| UDP IE opposing opponents (new, §13) | **$28,281,982.23** | — | — | Credited opposition spending, roster persons only; non-roster backed candidates received a further $11,010,009.25 (not in any tracker row) |
| UDP IE total benefit (new, §13) | **$70,696,985.99** | — | — | Support + opposing-opponents credit, roster persons only |

The pull totals are the sums of the staged 665-row money files, which double-count Rivet
(her individual $9,346,559.99 and corporate $493,980.00 appear in both of her rows). The
merged individual total is further reduced by the **weball de-duplication applied Nov 12,
2026** (§8.15): $451,776,015.34 of exact-equal `TTL_INDIV_CONTRIB` copies under two
candidate IDs in the same cycle, counted once instead of twice (32 persons, 90
(person, cycle) groups). Apart from that correction and the Rivet collapse, **no figure
was adjusted** — every other difference is exactly Rivet's amounts, to the cent. AIPAC
own-money (headline − earmark) is $7,376,200.00 in both versions. The staged work files
(`work/money_pas2_weball.csv`, `work/money_per_cycle.json`) were updated with the same
de-duplication so the staged inputs match the final dataset; the per-group correction
record (person, cycle, amount, kept/dropped candidate ID) is saved as
`work/dedup-applied.json`, and the full evidence is in `work/verification-log.md`.

### Internal consistency (verified in the merge)

- All 665 staged person_keys joined 1:1 to the roster; all FEC IDs agree between roster
  and both money files; no full-name mismatches. The only FEC ID shared by two roster
  entries is Rivet's `H4MI08218`.
- `per_cycle` sums to the career columns with **0 mismatches** (all 664 persons × 5
  columns); `udp_per_cycle` sums to `udp_ie_support_career` with **0 mismatches**.
- UDP per-cycle figures were **independently recomputed from the staged IE files** during
  the merge (same dedup + name-resolution rules) and reproduce `money_udp.csv` exactly:
  0 mismatches across all 665 staged persons; roster cycle totals $10,936,406.70 /
  $13,980,903.77 / $17,497,693.29 match pull-log-b §9.
- CSV ↔ JSON agreement verified field-by-field (0 mismatches); roster fields preserved
  exactly for all non-Rivet rows.
- Opposition-credit merge (Nov 12, 2026, §13): the credit computation independently
  reproduces the existing `udp_ie_support_career` column exactly (0 mismatches across
  all 664 persons) and the per-cycle UDP S+O totals match pull-log-b exactly in all
  three cycles ($26,107,515.77 / $38,044,932.69 / $54,322,881.51, $0.00 difference).
  CSV ↔ JSON agreement on the four new columns verified (0 mismatches).
- Complete-picture merge (Nov 12, 2026): `self_funding_per_cycle`,
  `other_committees_per_cycle` and `all_ie_per_cycle` each sum to their career columns
  with **0 mismatches**; the seven other-committee classes sum to
  `other_committees_total_career` with 0 mismatches; the stock columns (cash on hand,
  debts owed by) equal their latest cycle's value with 0 mismatches. The other-committee
  pull re-derives corporate ($972,228,584), corporate earmark ($26,850), AIPAC direct
  ($7,567,773) and AIPAC earmark ($191,573) **to the cent**. The all-IE pull reproduces
  UDP 2024 deduped $38,044,932.69 **exactly**; roster cycle totals $635,983,318.22 /
  $957,619,902.44 / $2,248,654,260.52. CSV ↔ JSON agreement covers all new columns
  (0 mismatches), including the three new per-cycle lists compared by repr; the
  JSON-only `all_ie_top_committees` lists are sorted, split correctly, max 5 per person.
  Named spot cases verified exact: Constantino self-funding $17,000,000.00, Rick Scott
  $89,994,251.12, Ricketts $19,442,012.33, Thanedar $17,456,074.00, McClain Delaney
  $14,873,000.00, Jacobs $11,551,385.89, Cisneros $9,807,843.10, Shreve $7,943,000.00.
  All 93 standing audits in `work/verify_dataset.py` pass.

### Spot-checks against independent sources (all run Nov 12, 2026)

- **Individual totals vs FEC API candidate totals:** Jeffries 2024 $15,936,793.65, McCaul
  2024 $1,464,364.63, Pelosi 2024 $9,554,439.66 — **exact matches** in all three cases.
  Gottheimer career individual re-checked by direct `grep` over all 24 weball files:
  $30,958,908.44 — matches.
- **AIPAC 2024 all-candidate total vs OpenSecrets:** this pull $3,041,310 (786 rows, 363
  distinct recipients, max $20,000 net per recipient) vs OpenSecrets $3,037,900 — gap
  **+$3,410 (+0.11%, this pull higher), unresolved** (see §8). Note the pre-exclusion
  literal sum was $2,445,814 (24% below OpenSecrets) — the void-earmark exclusion (§2) is
  what closes the gap, which corroborates it.
- **pas2 vs oth24 (AIPAC 24K/24P, by SUB_ID):** 1,931/1,931 identical amounts; `oth` adds
  only 36 non-candidate rows ($199,000) correctly excluded from candidate totals.
- **UDP spot-checks:** Wesley Bell 2024 support $3,356,279.25 and George Latimer 2024
  $4,682,560.29 — **exact matches** to the Schedule E API (F24 copy). El-Sayed 2026
  oppose $20,903,437.57 + Stevens 2026 support $10,498,735.23 = $31,402,172.80 vs $31.47M
  reported Nov 4, 2026 for UDP's Michigan effort — within 0.2%. Adrian Boafo 2026
  $5,734,013.28 vs $5.73M reported — match. 2022 deduped total $26,107,515.77 vs ~$26.1M
  reported — match. 2026 deduped total $54,322,881.51 vs "≈$54M as of Oct 24, 2026" —
  consistent within ~1.7% (different vintages; this file runs through Oct 31, 2026).
- **Verification pass, Nov 12, 2026 (after the §8.15 de-duplication)** — 5-person
  spot-check, full detail in `work/verification-log.md`. Career individual totals match
  the FEC API candidate-totals endpoint **exactly, to the cent, for all five** (Pelosi
  $73,415,016.76; Cruz $152,064,880.63; Schumer $109,755,537.29; Stefanik $30,071,951.49;
  Talarico $139,776,602.82), summing the endpoint's 2-year-cycle rows only. **Trap
  documented:** the totals endpoint also returns cumulative `election_full=true` rows
  (6-year Senate windows) alongside the 2-year rows — a naive sum over all returned rows
  double-counts (Pelosi $146,830,033.52 = exactly 2× the true total). OpenSecrets
  2-year "raised" (net receipts = gross receipts − refunds − offsets) matches the
  dataset-derived net exactly for Pelosi 2024 ($10,003,159) and Stefanik 2024
  ($15,444,946); its 6-year Senate windows run within ~0.5% of the dataset-derived net
  (Cruz 2024 window $105,557,321 vs $106,112,320.79 — vintage/netting difference, data
  vintage Sep 16, 2025 vs Nov 12, 2026). Schumer's 6-year 2022 gross receipts reconcile
  exactly: dataset $41,884,544.60 vs Ballotpedia/FEC $41,884,545. AIPAC direct (PAC
  own-money) cross-checks exactly against SpectrumVote's direct column for the Jan
  2023–2026 window (Cruz $10,000; Stefanik $10,000; Pelosi $5,000; Schumer $0; Talarico
  $0) and for Gottheimer ($20,000), confirming the headline−earmark split. Corporate-PAC
  2024 figures were re-derived from the staged pas2+cm files with fresh code and match
  exactly (Pelosi $31,500; Cruz $101,133; Stefanik $451,450). UDP support is $0 for all
  five, confirmed by direct read of the staged IE files (no UDP rows for any of them in
  any cycle, support or oppose). **No dataset figure was changed on the basis of these
  spot-checks** — every mismatch found was a convention/vintage difference, explained
  in the log.

---

## 7. Roster fix — Kristen McDonald Rivet

The source roster contained **two rows for the same person**: `M001237` (recorded as
119th-only, MI-08, with the note "Not in 120th; MI-08 in the 120th is held by Kristen
McDonald Rivet") and `kristen-mcdonaldrivetmihouse` (recorded as 120th-only, "first term in
Congress"). Both carry the same FEC ID `H4MI08218` and identical money totals in both money
files (individual $9,346,559.99; corporate $493,980.00; AIPAC $0; UDP $0), and identical
per-cycle breakdowns. She is one person who served in the 119th and was re-elected to the
120th. The final dataset collapses them into **one row** (`person_key` `M001237`;
`chamber_119` and `chamber_120` both `House`; `district_119` and `district_120` both `8`;
`party_119` and `party_120` both `Democrat`; `in_119th` and `in_120th` both `yes`), with
the fix documented in her `data_notes`.

**Consequence for counts:** the source files describe "665 persons," but 665 rows minus
this one duplicate is **664 distinct persons**. The task brief for this merge specified a
final row count of 665 *and* the collapse to one row; those two instructions cannot both
hold, because the source roster is 665 rows *including* the duplicate. The collapse was
applied (664 rows) and the pull totals in §6 are shown with the double-count made explicit
rather than silently adjusted. After the collapse: in both Congresses 411 (was 410),
119th-only 124 (was 125), 120th-only 124 (was 125); 119th total still 540, 120th named
total still 535.

---

## 8. Known limitations — read before using these numbers

1. **2026 cycle is partial — and the cutoff date differs by column family.**
   Pulled Nov 12, 2026. Committee-money columns (corporate, AIPAC, other-committee —
   all pas2-derived) run through **Sep 30, 2026** (the staged pas2 2026 zip effectively
   ends then; only 991 October rows). Weball-derived columns (individual, self-funding,
   topline) run through **Oct 14, 2026**. All-IE columns (UDP too) run through **Oct 31,
   2026**. So a 2026 figure from one family is not directly comparable to a 2026 figure
   from another — e.g. a candidate's October corporate PAC money is missing while their
   October individual money is present. Re-pull after the cycle closes (planned: mid-Dec
   2026 after the Dec 3 post-general deadline, and Feb 2027 after the Jan 31 year-end
   deadline); expect 2026 totals to rise and some amounts to be amended.
2. **120th results are media calls, uncertified** (see §1); 5 seats are still TBD/uncalled.
3. **AIPAC PAC first filed Dec 2021; UDP first filed Jan 2022.** No pre-2022 figures exist
   for those two columns. Earlier cycles are $0 by construction, not missing data.
4. **Earmark treatment.** Negative (void) earmark rows excluded (§2); positive earmarks
   kept in the headline and broken out separately. The 2024 `ERMK:` re-report rows
   ($21,410) may double-count 2022 originals.
5. **AIPAC 2024 residual vs OpenSecrets: +$3,410 (+0.11%), unresolved.** Likely
   snapshot/amendment timing (e.g. the 87-row amended 12G filing, FILE_NUM 1879064,
   image-dated 2025-03-03, +$422,000, post-dates OpenSecrets' Feb 6, 2025 data release)
   and/or the 24Z in-kind treatment (2 rows, $5,000, excluded per the 24K/24P filter).
   Immaterial but unreconciled to the dollar.
6. **UDP 2024 reconciliation residual: +$184,732.69 (+0.49%) vs OpenSecrets
   ($38,044,932.69 vs $37,860,200), unresolved.** Leading hypothesis: the F24-notice vs
   F3X-Schedule E vintage difference — notices are filed first and can be corrected on
   Schedule E, so the F3X universe runs slightly lower (Latimer 2024: F24 $4,682,560.29
   vs F3X $4,643,836.68, −0.83%; El-Sayed 2026 oppose: F24 $20,903,437.57 vs F3X
   $20,140,908.74, −3.6%). The bulk IE file contains the notice copy. Settling it would
   need a registered API key and a full F3X pull; not attempted. Not adjusted.
7. **UDP 2022 name-attributed rows ($4,819,602.26)** rest on name+state+district+office
   matching because the FEC file left `cand_id` blank (§4). An ID-only version would put
   Davis, Foushee and Mullin at $0. The amounts and method are flagged per person.
8. **F24-vs-F3X duplication in the API (naive API sums double-count 2×), and the API
   totals endpoint is unreliable — do not use it.** Each Schedule E expenditure appears
   twice in the raw API — once as the 24/48-hour notice (F24, `is_notice=true`) and once
   as the Schedule E itemization (F3X, `is_notice=false`), same transaction ID, same
   amount (e.g. Bell 2024: API raw support $6,712,558.50 = 2 × CSV $3,356,279.25). The
   bulk CSV contains one copy. The totals endpoint
   (`schedule_e/totals/by_candidate/`) disagrees with the raw endpoint for the identical
   filter (Bell 2024: totals endpoint support $4,581,013.51 vs raw $3,356,279.25) and
   matches neither the F24 nor the F3X universe. The API period filter also leaks across
   cycles (a `two_year_transaction_period=2024` query returned a 2026-cycle row).
9. **`fec-sources.md` §4 mislabeled the `oppexp` bulk file — corrected source is
   `independent_expenditure_<cycle>.csv`** (§3). The staged `oppexp` files are operating
   expenditures (Schedule B), not Schedule E; no `oppexp` data was used for any figure.
10. **Refund netting (17Z) was checked for 2024 only** (§4). `oth22`/`oth26` were not
    downloaded. The 2024 result (zero 17Z rows) plus pas2 netting makes a large hidden
    refund balance unlikely, but it is not proven for 2022/2026.
11. **Schedule B API spot-check failed with HTTP 504** ("Query timed out", twice on Nov 12,
    2026; the verification agent hit a 504 on this endpoint once as well). The
    pas2↔oth cross-check and the OpenSecrets reconciliation (§6) were substituted; the
    Schedule B API was not used.
12. **DFL normalized to Democrat; 120th leadership all TBD** (elections Nov 18–19, 2026)
    (see §1).
13. **Pre-1980 careers are out of scope.** FEC bulk files start in 1980; anything a member
    raised before 1980 is not in this dataset.
14. **Weball double-counting warning (FEC doc):** if a candidate has multiple authorised
    committees that transfer funds between each other, activity is counted twice; subtract
    `TRANS_FROM_AUTH` (col 7) / `TRANS_TO_AUTH` (col 9) where both are present.
    `TTL_INDIV_CONTRIB` itself is a receipts breakout and is not affected by
    committee-to-committee transfers — but see limitation 15, which is the material
    version of this problem for this dataset.
15. **✅ CORRECTED Nov 12, 2026 — weball repeats the same individual-contribution total
    under both candidate IDs for chamber-switchers (found in the merge, not in either
    pull log; mechanism independently verified and the fix applied — see
    `work/verification-log.md`).** For people who moved House → Senate (or hold both a
    House and a Senate candidate ID), the FEC weball file carries the *identical*
    `TTL_INDIV_CONTRIB` under both IDs in the same cycle. **Mechanism proven:** the two
    rows are one principal committee's summary reported under two IDs — e.g. Wesley Bell
    2024 (`H4MO01134` and `S4MO00250`, $5,136,025.24 each; every amount field identical;
    both IDs point at committee `C00842336` BELL FOR MISSOURI), Ruben Gallego 2024
    ($59,385,707.27; both IDs → `C00558627` GALLEGO FOR ARIZONA), Adam B. Schiff 2024
    ($45,110,628.66; both IDs → `C00343871` SCHIFF FOR SENATE). The FEC API committee
    totals endpoint confirms each committee reports the figure **once** (e.g. Gallego's
    `C00558627` 2024 individual contributions = $59,385,707.27). Note weball has **no
    committee-ID column** (30 columns, no `CMTE_ID`); the committee link was established
    via the FEC API candidate/committee endpoints and pas2 recipient-committee IDs, not
    from weball itself. **Fix applied:** for each (person, cycle) group, each distinct
    `TTL_INDIV_CONTRIB` value is counted once, not once per candidate ID. The kept copy
    sits on the ID matching the office actually sought that cycle (election-result `W`
    marker where present, else the person's chamber after the cycle, else the shared
    principal committee's designation — per-group record in `work/dedup-applied.json`);
    the dropped copy's `individual` is zeroed in `per_cycle` while its AIPAC/corporate
    values are untouched. **Scope: 32 persons, 90 (person, cycle) groups,
    $451,776,015.34** — the corrected roster-wide individual total is **$8,763,847,353.73**
    (was $9,215,623,369.07). Largest single cases: Ruben Gallego 2024 ($59,385,707.27),
    Gary C. Peters 2020 ($45,404,376.66), Adam B. Schiff 2024 ($45,110,628.66), Jacky
    Rosen 2024 ($33,769,624.63) and 2018 ($22,909,611.89), Chris Pappas 2026
    ($21,080,102.32). Two further duplicate groups carry $0.00 under both IDs (Markey
    1986, Stutzman 2018) and change nothing. A re-computation from the raw weball files,
    independent of the staged per-cycle file, reproduces the $451,776,015.34 correction
    and the $8,763,847,353.73 total exactly. The AIPAC and corporate columns are *not*
    affected the same way: pas2 is transaction-level, and the per-ID AIPAC/corporate
    amounts for these people differ (e.g. Bell 2024 AIPAC: House ID $10,000, Senate ID
    $0; Gallego 2024 corporate: House ID $76,825, Senate ID $194,799), so only the
    weball-derived individual column carried this duplication. Separately, 158
    (person, cycle) groups across 59 persons have *unequal* individual amounts under two
    IDs in the same cycle (e.g. Haley Stevens 2026: House ID $808,903.75 vs Senate ID
    $10,497,818.26) — those look like genuinely separate committee totals and were NOT
    counted as duplication; only exact-equal copies were. One edge case was checked
    individually: John Curtis 2024 has identical `TTL_INDIV_CONTRIB` ($2,319,425.97) but
    different receipts/disbursements across the two rows (the Senate copy carries an extra
    $107,207.83 of transfers from authorized committees); both IDs share principal
    committee `C00647339` JOHN CURTIS FOR UTAH, whose own 2024 individual total is the
    single $2,319,425.97 — so it was de-duplicated like the rest.
    **Extension (same date) — the Curtis 2024 dropped copy is now zeroed for the
    financial columns too, not just the individual column.** Re-verified from the staged
    `work/bulk/weball/weball24.txt`: Curtis's two 2024 rows are `H8UT03238` (dropped) and
    `S4UT00282` (kept); cols 10–18 are byte-identical, and kept-minus-dropped is
    **$107,207.83 exactly** for receipts ($5,748,063.58 vs $5,640,855.75),
    transfers-from-auth ($1,369,004.86 vs $1,261,797.03) and disbursements
    ($5,346,220.15 vs $5,239,012.32) — the dropped row is a strict subset of the kept
    row, so counting both double-counts the House row's activity. The extension zeroes
    the dropped copy for weball cols 6–9 as well as 10–18 (recorded in
    `work/dedup-applied.json` as `extend_to_columns_6_9` with the expected cents;
    `work/pull_self_funding.py` fails loudly if the arithmetic ever stops matching).
    Effect on roster totals vs the pre-extension figures: receipts −$5,640,855.75,
    disbursements −$5,239,012.32, transfers-from-auth −$1,261,797.03, transfers-to-auth
    −$3,300.00. Only Curtis's row changed; the four dedup-partial flags are gone.
16. **Roster-notes scope reminder:** the roster is "current members + 120th incoming,"
    not "everyone who served in the 119th" (§1, 16 excluded). Jasmine Clark (GA-13) is
    counted as 120th-only pending confirmation of whether she is seated before Jan 3,
    2027 (Wikipedia says she was elected in a special election to replace David Scott).
17. **Lamb 2026 other-committee total is pending reconciliation.** Mark Lamb's 2026
    other-committee total from the staged pas2 file is **$96,500** (leadership $43,000;
    labor $5,000 ALPA; trade $6,000 incl. ABC $5,000 + NSSF $1,000; membership $8,000;
    other_unclassified $34,500; party $0; cooperative $0), but his weball col 26 figure
    for 2026 is **$129,150** — a **$32,650 residual** that the pas2-derived classes
    cannot account for. The gap is consistent with the pas2 Sep-30 staleness (item 1):
    the missing $32,650 is presumably October committee money not yet in the staged
    pas2 file. Recorded as `PENDING RECONCILIATION` in Lamb's `data_notes`; no figure
    was adjusted to force a match. The mid-Dec re-pull settles it.
18. **Scalise-type negative residual (other-committee reconciliation).** For a handful
    of people the pas2-derived other-committee total plus corporate plus AIPAC does not
    reconcile against the weball col 26 figure, leaving a negative residual the classes
    cannot explain. The mechanism is unresolved (leading hypothesis: joint-fundraising-
    committee / transfer reporting, which needs the `oth` bulk file or F3 line-item work
    — neither is staged). Documented, not adjusted.
19. **Congressional Leadership Fund blank-`cand_id` rows are excluded from the
    all-IE totals.** CLF files `cand_id` blank systematically, so its spending cannot be
    attributed by ID under the all-IE filter (registered committee + identified
    candidate). Its roster-resolved-by-name amounts — 2024 $105.5M, 2026 $199.2M — are
    excluded from the published all-IE totals, and the validation targets exclude them
    too. This is a filter consequence, not a judgment that the spending did not happen;
    name-based attribution for CLF is a follow-up, not this build.
20. **All-IE "career" means 2022–2026 only.** The 2010–2020 IE bulk files exist on the
    FEC server but are NOT staged and were not pulled. Every all-IE career figure in
    this dataset is a 2022+2024+2026 figure; do not describe it as a lifetime total.
    Downloading the earlier cycles is a follow-up.

---

## 9. Reproducibility

- Staged inputs: `work/roster.json`, `work/money_pas2_weball.csv`,
  `work/money_udp.csv`, `work/money_per_cycle.json`, `work/bulk/` (weball/cm/pas2 all
  cycles; `bulk/ie/` 2022/2024/2026), `work/pull-log-a.md`, `work/pull-log-b.md`,
  `work/fec-sources.md`, `work/bulk-inventory.md`, `work/roster-notes.md`.
- Merge rule: join on `person_key`; Rivet collapsed as in §7; Armstrong's money columns
  set to `unknown`; all other figures copied verbatim from the staged money files (no
  figure was invented). **Exception:** the `individual_contribution_total_career` column
  (and the `individual` values in `per_cycle`) were adjusted by the verified weball
  de-duplication of §8.15 (32 persons, $451,776,015.34); nothing else was adjusted. UDP
  per-cycle figures were recomputed from the staged IE files during the merge and
  reproduce `money_udp.csv` exactly (0 mismatches). After the de-duplication,
  re-verification (Nov 12, 2026) confirms `per_cycle` still sums to the career columns
  with **0 mismatches** and CSV ↔ JSON agreement is **0 mismatches** (see
  `work/verification-log.md`).
- **To refresh:** re-download the FEC bulk files after the 2026 cycle closes, re-run the
  pulls, re-run the merge, and update `data_as_of`. The 5 TBD seats and the 120th
  leadership (Nov 18–19, 2026) will also need updating.

---

## 12. Ranking — "how much money they've accepted"

- **Total accepted (career)** = individual contributions + corporate PAC money + AIPAC PAC direct. The two earmark columns are subsets of their parent columns and are never added again. UDP independent expenditures are **not** counted as accepted — that money was never given to the campaign, it was spent about the race — but UDP support is ranked separately in its own column.
- **Ranks** (`rank_total_accepted`, `rank_individual`, `rank_corporate_pac`, `rank_aipac_direct`, `rank_udp_support`, `rank_udp_opposing_opponents`, `rank_udp_total_benefit`, `rank_self_funding`, `rank_all_ie_support`, `rank_all_ie_oppose`, `rank_all_ie_total`, `rank_other_committees_total`): 1 = most money, ties share a rank (competition ranking). Ranks are computed over all 664 people; Alan Armstrong is unranked (money unknown, not zero). A negative total (Patrick Ryan, AIPAC −$10,000) ranks as filed. The five new ranks (self-funding, all-IE support/oppose/total, other-committee total) are career only — there are no per-cycle ranks.
- **Top 10 by total accepted (career, as of Nov 12, 2026):** Warnock $316.4M, Ossoff $295.7M, Kelly $242.1M, Brown $201.0M, Cruz $154.2M, Talarico $139.8M, McConnell $123.7M (119th only), Schumer $117.7M, Schiff $110.9M, Baldwin $104.7M.
- **Top 10 by self-funding (career):** Rick Scott $89,994,251.12, Darrell Issa $27,875,844.99, David McCormick $22,090,582.51, Pete Ricketts $19,442,012.33, Shri Thanedar $17,456,074.00, Anthony Constantino $17,000,000.00, Maria Cantwell $15,628,249.00, April McClain Delaney $14,873,000.00, Sara Jacobs $11,551,385.89, Mark R. Warner $10,726,284.00.
- **Top 10 by all-IE total (career, 2022–2026 only):** James Talarico $259,873,813.32, Jon Husted $197,481,557.46, Sherrod Brown $151,242,621.14, Abdul El-Sayed $148,486,253.91, Bernie Moreno $144,269,327.01, David McCormick $100,622,798.35, Tim Sheehy $81,608,222.10, Josh Turek $71,523,244.93, Mark Kelly $61,452,069.16, Ron Johnson $60,574,856.06.
- **Top 10 by other-committee total (career):** Frank Pallone, Jr. $17,794,814, Steny H. Hoyer $15,801,231, Mitch McConnell $11,203,442, Sherrod Brown $10,981,813, Nancy Pelosi $10,105,781, James E. Clyburn $9,889,929, Richard E. Neal $9,541,014, Chuck Grassley $9,239,433, Susan M. Collins $9,095,131, Mike Thompson $9,013,645.

---

## 13. Opposition credit — UDP spending against a candidate's opponent

Attack spending that effectively benefits a candidate is counted here as its own
thing, never blended into direct support or into "total accepted" (UDP money was
never given to any campaign). AIPAC PAC has **no** Schedule E independent-expenditure
activity at all — zero rows in the 2022, 2024, and 2026 IE files — so there is no
AIPAC opposition column; the rule below was run for UDP only.

**Definitions (career, 2022–2026 — UDP did not exist before 2022):**

- `udp_ie_opposing_opponents_career` — UDP independent expenditures opposing other
  candidates in races where UDP backed exactly one candidate (see rule), credited to
  that backed candidate.
- `udp_ie_total_benefit_career` — `udp_ie_support_career` +
  `udp_ie_opposing_opponents_career`. The total UDP spending that worked in a
  person's favor, support plus attack spending against their opponents.
- `rank_udp_opposing_opponents`, `rank_udp_total_benefit` — 1 = most, ties share a
  rank, same convention as the other rank columns. Alan Armstrong is unranked
  (money unknown, not zero).

**The exactly-one-backed-candidate rule.** A race is one FEC cycle + office + state
+ district. For each race, UDP's backed candidate(s) are the candidates with UDP
IE **support** rows in that race. If UDP backed exactly one candidate, all of UDP's
IE spending **opposing other candidates** in that same race is credited to that one
backed candidate. If it backed zero, or two or more, **nothing is credited for that
race**. Spending opposing the backed candidate themself is never credited (one such
row exists: $84,325.84 opposing George Latimer in the NY-16 2024 primary, where UDP
was backing him — excluded as a filing artifact, not opposition to an opponent).

**Primary/general limitation — read this before quoting any credited figure.** The
race key does not distinguish primary from general. If UDP backed different
candidates in the primary and the general within one cycle+race, that counts as two
backed candidates, so nothing is credited — even when the opposition spending
plainly helped one of them. The MI-Sen 2026 case below is the live example: UDP
backed Stevens in the primary and Rogers in the general, so the $20.9M spent
opposing El-Sayed credits to no one. The rule is deliberately conservative: it
credits opposition spending only where the beneficiary is unambiguous.

**What the rule did, in numbers.** 23 races had UDP oppose spending. 15 races
credited (exactly one backed candidate); 8 did not. Roster persons were credited
$28,281,982.23 in total; a further $11,010,009.25 was credited to backed
candidates who are not in the tracker (Hollier, Weiss, Hernandez, Conyears-Ervin,
Irwin), so it appears in no row. $27,321,112.49 of opposition spending was not
credited to anyone, plus the $84,325.84 self-opposition row excluded above.

**Races credited (15):** NY-16 2024 → Latimer $9,865,492.96 (vs Bowman); MO-01
2024 → Bell $5,242,260.11 (vs Bush); MD-04 2022 → Ivey $4,258,735.79 (vs
Edwards); KY-04 2026 → Gallrein $3,576,968.08 (vs Massie); MO-01 2026 → Bell
$2,457,791.53 (vs Bush); TX-28 2022 → Cuellar $1,428,196.80 (vs Cisneros); CA-47
2024 → Weiss $4,615,288.76 (vs Min, non-roster); MI-13 2022 → Hollier
$1,428,679.18 (vs Thanedar, non-roster); CA-14 2026 → Hernandez $1,642,139.53
(vs Wahab, non-roster); CA-34 2024 → Gomez $576,452.51 (vs Kim); MI-11 2022 →
Stevens $341,792.98 (vs Levin); NC-01 2022 → Davis $335,412.57 (vs Smith); OH-11
2022 → Brown $198,878.90 (vs Turner); IL-07 2026 → Conyears-Ervin $59,748.29
(vs Friedman, non-roster); PA-12 2022 → Irwin $3,264,153.49 (vs Lee,
non-roster — the credit exists only outside the tracker, see the Irwin note in
Method notes below).

**Races NOT credited (8) — opposition spending with no beneficiary under the rule:**
MI-Sen 2026, $20,903,437.57 vs El-Sayed — UDP backed **two** candidates (Stevens
in the primary, Rogers in the general), so nothing credits; NJ-11 2026,
$2,326,917.40 vs Tom Malinowski — backed nobody; IN-08 2024, $1,567,918.74 vs
John Hostettler — backed nobody; TX-23 2024, $1,061,283.96 vs Brandon Herrera —
backed nobody; CA-42 2022, $515,088.43 vs Cristina Garcia — backed nobody; IL-07
2024, $494,453.18 vs Kina Collins — backed nobody; KY-04 2024, $319,783.30 vs
Thomas Massie — backed nobody (UDP backed Gallrein against Massie only in 2026,
not 2024); VA-05 2024, $132,229.91 vs Bob Good — backed nobody.

**Test case 1 — NY-16, 2024 (House).** UDP supported George Latimer $4,682,560.29
and opposed Jamaal Bowman $9,865,492.96; Latimer was the only candidate UDP backed
in the race. Credited to Latimer: **$9,865,492.96**. Combined UDP benefit for
Latimer: **$14,548,053.25** (support + credit). One UDP row opposing Latimer
himself ($84,325.84, primary media placement) was excluded from the credit as
self-opposition, not opposition to an opponent.

**Test case 2 — Michigan Senate, 2026.** UDP spent **$20,903,437.57 opposing Abdul
El-Sayed** and supported **two** candidates in the race: Haley Stevens $10,498,735.23
(all primary) and Michael Rogers $64,392.80 (general). Because the rule keys on
cycle+race and does not split primary from general, the backed count is two, so
**nothing is credited — the $20.9M benefits no one in this tracker**. Rogers is
not in the tracker (he holds no seat in the 119th or 120th Congress), and Stevens
receives no credit from the anti-El-Sayed spending. If the rule were split by
primary/general, the primary-season anti-El-Sayed spending would credit to Stevens
and the general-season spending to Rogers; that split was deliberately not made.
El-Sayed's own row stays at $0 UDP support and $0 opposing-opponents credit.

**Top 10 by UDP total benefit (career):** Stevens $14,718,558.67, Latimer
$14,548,053.25, Bell $11,741,957.05, Ivey $5,992,920.21, Boafo $5,734,013.28,
Elfreth $4,218,074.08, Gallrein $4,156,286.70, Davis $2,438,050.39, Gomez
$2,300,442.66, Foushee $2,128,196.18. **Top 10 by opposing-opponents credit:**
Latimer $9,865,492.96, Bell $7,700,051.64, Ivey $4,258,735.79, Gallrein
$3,576,968.08, Cuellar $1,428,196.80, Gomez $576,452.51, Stevens $341,792.98,
Davis $335,412.57, Brown $198,878.90. (The next 654 people are $0 and share rank
10 on the opposing-opponents rank.)

**Method notes.** Source: staged `independent_expenditure_<cycle>.csv` bulk files,
cycles 2022/2024/2026, `spe_id = C00799031`, same dedup rule as the support pull
(dedup by `tran_id`, keep latest `receipt_dat`, tie-break highest `file_num`).
Blank-`cand_id` support rows were resolved by name index, then roster match, then
— for support rows only — a name-based identity where no FEC ID exists anywhere
(Steven Irwin, PA-12 2022, $660,319.30; that resolution is what makes Irwin the
sole backed candidate in PA-12 and moves its $3,264,153.49 anti-Lee spending to
the non-roster bucket instead of the no-credit bucket). Blank-`cand_id` oppose
rows (30, all 2022: Cisneros, Garcia) need no resolution — the oppose total is
summed per race from the office/state/district columns, and the opposed person's
name is in the row. Computation script: `work/compute_opposition.py`; race-level
record: `work/opposition-computed.json`. Full per-cycle reconciliation: the
computation's deduped S+O totals match the earlier UDP pull exactly in all three
cycles ($26,107,515.77 / $38,044,932.69 / $54,322,881.51, $0.00 difference), and
its support totals reproduce `udp_ie_support_career` exactly for all 664 persons.

---

## 14. 2026-cycle columns — "clean in 2026" and the primary-target list

**The 2026 cycle is PARTIAL — through October 31, 2026.** Every 2026 figure below
is a partial-cycle figure, not a full-cycle total. Post-October fundraising,
late filings, and the December runoff cycle are not in these numbers. Do not
compare 2026 figures head-to-head with full cycles (2022, 2024).

**Definitions (2026 only):**

- `individual_2026`, `corp_2026`, `aipac_direct_2026` — summed from the
  `per_cycle` entries with `cycle == 2026` (individual contributions, corporate
  PAC money, AIPAC PAC direct). People with more than one 2026 committee
  (chamber switchers, returning members) have their entries summed; where the
  FEC weball repeats an identical total under two candidate IDs, the career
  dedup in §8 applies and the per-cycle entries already reflect it (the second
  ID's entry is zero).
- `udp_support_2026` — summed from `udp_per_cycle` entries with `cycle == 2026`.
- `udp_opp_credit_2026` — the person's share of the §13 opposition credit for
  cycle 2026 only. Only two roster people have any: Wesley Bell $2,457,791.53
  and Ed Gallrein $3,576,968.08. The other two 2026 credited races (CA-14,
  IL-07) went to people not in the tracker.
- `udp_benefit_2026` — `udp_support_2026` + `udp_opp_credit_2026`.
- `dirty_2026` — `corp_2026` + `aipac_direct_2026` + `udp_benefit_2026`. All
  money that came from corporate PACs, AIPAC's PAC, or UDP spending for the
  candidate in the 2026 cycle.
- `self_funding_2026`, `cand_loans_2026`, `cand_contrib_2026`,
  `total_receipts_2026`, `total_disbursements_2026` — summed from the
  `self_funding_per_cycle` entries with `cycle == 2026`. `cash_on_hand_2026` is
  that cycle's COH (a stock; null when the person has no 2026 self-funding entry).
  `other_committees_total_2026` — summed from `other_committees_per_cycle`
  entries with `cycle == 2026`. `all_ie_support_2026`, `all_ie_oppose_2026`,
  `all_ie_total_2026` — summed from `all_ie_per_cycle` entries with
  `cycle == 2026`. The int-0-when-empty convention matches the existing 2026
  columns (a person with no 2026 entry in a family reads $0 in that family's 2026
  columns, except `cash_on_hand_2026`, which reads null). `dirty_2026` is
  UNCHANGED by all of this — self-funding, other-committee money and all-IE
  spending are never folded into it.
- `clean_2026` — true when `corp_2026`, `aipac_direct_2026`,
  `udp_support_2026`, and `udp_opp_credit_2026` are ALL zero in 2026. This is
  a cycle test, not a career test: a member can be clean in 2026 while having
  taken such money in earlier cycles. **Verification rule (generalized Nov 12,
  2026 — previously a hardcoded Luria exception):** a person in the 120th is
  *unverified* (`clean_2026 = null`) iff they have NO 2026 linkage evidence in
  ANY money source — no tracked `per_cycle` / `udp_per_cycle` 2026 entry, and no
  `self_funding_per_cycle` 2026 entry whose `coverage_end_date` falls in calendar
  2026. Other-committee and all-IE 2026 entries do NOT establish linkage on their
  own (they are third-party reports filed under a possibly stale ID). A person
  with linkage and all-zero dirty columns is verified clean **with evidence**;
  a person with linkage and nonzero dirty columns is dirty. The rule is
  implemented in `work/compute_2026.py` (`has_2026_linkage`) and re-verified in
  `work/verify_dataset.py` (checks (e) and (m)).
- `dep_share_2026` — `(corp_2026 + aipac_direct_2026) / (individual_2026 +
  corp_2026 + aipac_direct_2026)`, the share of the candidate's own 2026
  fundraising (individual + corporate PAC + AIPAC direct) that came from
  corporate PACs and AIPAC's PAC. UDP money is excluded from both numerator
  and denominator — it was never given to the campaign. Null when the
  denominator is 0.

**Headline — incoming House, 2026 cycle (partial): 67 of 436 verified-clean (63
Democrats, 4 Republicans).** The four clean Republicans are Kimberlyn
King-Hinds, Aumua Amata Coleman Radewagen, Mark Lamb, and Anthony Constantino
(Constantino's zero is verified — FEC activity found, all totals zero). The
nearest miss is Paul Gosar (R), $4,250 in corporate PAC money in 2026. All 53
career-clean incoming House members are also clean in 2026; 14 more are
2026-clean but not career-clean. For the Senate, 10 of 99 incoming senators
are clean in 2026 (9 Democrats, 1 independent, 0 Republicans).

**Top dirty-2026 incoming House Democrats:** Adrian Boafo $5,745,013.28
(UDP-driven: $5,734,013.28 UDP support, $11,000 corporate PAC); Wesley Bell
$3,446,667.69 (UDP-driven: $3,143,417.69 UDP benefit — $685,626.16 support +
$2,457,791.53 opposition credit — plus $288,250 corporate PAC and $15,000
AIPAC direct); Pete Aguilar $1,359,750.00; Hakeem S. Jeffries $1,259,000.00;
Katherine M. Clark $1,166,250.00. The last three are corporate-driven, and the
three most corporate-PAC-funded House Democrats in 2026 are the party
leadership itself: Aguilar $1,354,750, Jeffries $1,259,000, Clark $1,156,250
(Richard E. Neal $1,136,763 and Terri A. Sewell $1,026,500 round out the top
five). Highest dependence shares among them: Sewell 69.6%, Neal 61.6%, Clark
48.0%, Aguilar 37.5% — against Jeffries at 9.0%, whose $12.7M in 2026
individual contributions dwarfs his corporate PAC take.

**Data gaps — read before quoting any 2026 zero.** Three returning former
members have broken 2026 committee linkage in the roster, and their 2026
figures understate reality:

- Melissa Bean and Hilda Solis show $3,500 in corporate PAC money for 2026
  but $0 in individual contributions. Both raised millions from individuals
  across their careers (Bean $6.19M, Solis $1.83M); a $0 individual figure
  alongside real corporate PAC money is a missing-committee-linkage gap, not a
  real zero. Do not present their $0 individual_2026 as fact.
- Elaine Luria has no 2026 per-cycle data at all under the roster's linked
  candidate ID, so her `clean_2026` is null (unverified), NOT true. She is
  excluded from the 67 verified-clean count above. Do not present Luria as
  confirmed clean — or as dirty — until her 2026 committee ID is linked and
  her 2026 figures are pulled. **Correction to the original premise (Nov 12,
  2026):** the earlier note said she had "no 2026 entries in any source." That
  was wrong. Under her linked old ID `H8VA02111` she DOES have 2026 entries:
  self-funding 2026 receipts $590.89 (coverage through 07/15/2025 only — a
  pre-2026 coverage date, so it does not establish 2026 linkage under the
  generalized rule), other-committee 2026 $85,610 (leadership $19,000; labor
  $36,000; other $30,610), and all-IE 2026 support $685,786.28. What she does
  NOT have is a 2026-coverage weball row under the linked ID — and her real
  2026 campaign is a different, **unlinked** candidate ID, `H6VA02198`
  (committee `C00926303` "ELAINE LURIA FOR CONGRESS": receipts $8,044,063.94,
  individual $6,209,590.10, coverage through 10/14/2026, 242 pas2 2026 rows,
  132 IE 2026 rows). Linking `H6VA02198` is a roster change and was NOT done
  unilaterally — it would change her career totals. The conclusion (Luria stays
  null) is substantively correct; the premise was not, and this paragraph now
  states the evidence. Constantino is the mirror case: his tracked 2026 $0s
  are now verified WITH evidence (self-funding 2026 loans $14,400,000, coverage
  10/14/2026; all-IE 2026 support $459,491.94 / oppose $3,721,257.82;
  other-committee 2026 $19,500), so he counts among the 67 verified-clean —
  the count returns to **67 House / 77 total**, correcting the 66 / 76 figures
  recorded in MEMORY.md and the intro page (the dataset itself always said 67).

---

## 15. Coverage end dates by column family — and the re-pull plan

The bulk files behind this dataset do not all end on the same date (see §8.1).
The authoritative cutoffs, also recorded in `config.yaml` (`verification.coverage_end`):

| Column family | Source | Coverage ends |
|---|---|---|
| Individual, self-funding, topline | weball | **2026-10-14** |
| Corporate PAC, AIPAC, other-committee | pas2 | **2026-09-30** |
| UDP + all independent expenditures | IE bulk files | **2026-10-31** |

**Re-pull plan.** Mid-Dec 2026 (after the Dec 3 post-general filing deadline) and
Feb 2027 (after the Jan 31 year-end deadline): re-download the bulk files, re-run the
pulls, re-run the merge, update `data_as_of`. The freshness layer (§16) covers the gap
between Oct 14 and each re-pull; after each re-pull, reconcile its snapshot sums
against the new report and start a fresh snapshot — never carry freshness figures
forward into the dataset.

---

## 16. Freshness layer — new money since bulk coverage (Oct 14)

The bulk rebuild is the canonical dataset, and it only moves when the bulk files move.
Between bulk pulls, late money arrives through three API routes that the bulk files
cannot see yet. The freshness layer (`work/pull_freshness.py`, with
`work/pull_f6.py` and `work/pull_f24.py`) reports that money in
`work/freshness_snapshot.json` — labeled by source and date, **never merged into the
dataset totals**. Full research in `work/freshness-research.md`.

**The three routes (all verified live, Nov 12, 2026, on DEMO_KEY):**

1. **Candidate totals** — `GET /v1/candidate/{id}/totals/?cycle=2026`. Only as fresh
   as the latest processed report: on Nov 12 it still ended Oct 14 (PRE-GENERAL) for
   both test candidates. **Trap:** `election_full=true` returns only the aggregate
   row (`cycle: null`) — for Constantino that is the 2024+2026 aggregate (receipts
   $17,064,951.19, loans $17,000,000.00), NOT a 2026 figure. The driver uses the
   per-cycle row and flags `newer_than_bulk` only when its `coverage_end_date`
   passes Oct 14. The totals row also carries `last_debts_owed_to_committee` — the
   follow-up route for the `debts_owed_to_career` nulls (§2).
2. **Form 6 (48-Hour Notices)** — discovery via
   `GET /v1/filings/?form_type=F6&committee_id={id}` (metadata only; `candidate_id`
   is null on F6 rows), line items via the per-filing docquery CSV
   (`https://docquery.fec.gov/csv/{last3}/{file_number}.csv`, no key needed; F6N/F6A
   headers, F65 line items). There is NO F6 bulk file. **Blocker:** `min_date` is
   silently ignored on `/v1/filings/` — the pull pages with `sort=-receipt_date` and
   filters client-side. **Amendment chains:** the endpoint returns both an original
   and its amended version, and amended filings carry an `F6A` header (same field
   positions as `F6N`); the pull drops any filing whose file number appears in
   another filing's `amendment_chain` and keeps only the latest version of each
   chain. **Live proof:** a $1,000,000 Constantino candidate loan, Oct 29 (file
   2044138), invisible to the totals endpoint and to Schedule A.
3. **24/48-hour independent expenditures (F24)** —
   `GET /v1/schedules/schedule_e/?filing_form=F24&committee_id=&candidate_id=
   &cycle=2026`. The F24-only filter is load-bearing: the endpoint double-returns
   (each expenditure once under its original F3X filing and again under the F24),
   so the unfiltered sum roughly doubles the true amount (UDP vs El-Sayed 2026:
   naive $41.04M vs true $20.90M). **The $1,004.53 residual is reconciled, not
   open:** the deduped-unfiltered total ($20,904,442.10) exceeds the F24-only total
   ($20,903,437.57) by exactly one row — a UDP $1,004.53 GOTV expenditure dated
   Aug 3, 2026, filed Sep 19 on an F3X monthly report (file 2014027). It predates
   the 24/48-hour window and was never an F24, so it belongs in the deduped total
   but not the F24-only total. The pull classifies residual rows accordingly
   (explained = `filing_form != F24`; unexplained = `filing_form == F24`, which
   should be $0). Form 5 needs no leg: it covers only unregistered spenders, and
   registered committees file zero F5s.

**Weball-vs-API gap, with Constantino as the test case.** The bulk weball file says
Constantino's 2026 loans are $14.4M through Oct 14; the API totals endpoint agrees
(per-cycle row) — but the $1M Oct-29 loan exists ONLY as a Form 6 notice. Neither
the totals endpoint nor Schedule A sees it, and no bulk file carries it yet. That is
the gap the freshness layer exists to close: bulk says $14.4M, the truth on Nov 12
was $15.4M, and only the F6 leg finds the difference.

**First live run (Nov 12, 2026, DEMO_KEY, 2 persons)** — in
`work/freshness_snapshot.json`: Constantino F6 $1,000,000.00 candidate loan (1 filing);
El-Sayed F6 $1,953,368.64 in late contributions (16 filings after amendment-chain
dedup — 2 superseded originals dropped, $351,042.26); UDP vs El-Sayed F24
$20,903,437.57 (34 rows, latest expenditure Oct 29); totals newer than bulk: none;
unexplained F24 residual: $0.

**Cadence and keys.** Final 20 days before an election: daily. Cycle in progress
outside the final 20 days: weekly. After each filing deadline (Dec 3 post-general,
Jan 31 year-end): event-driven. A full refresh is ~1,300+ API calls; DEMO_KEY
(~30/hr, shared) is spot-checks only — the driver refuses `--all` on DEMO_KEY.
Production needs a registered api.data.gov key (1,000 req/hr) via the `FEC_API_KEY`
environment variable (wired in `config.yaml`, default `DEMO_KEY`). No registered key
exists in the repo yet.
