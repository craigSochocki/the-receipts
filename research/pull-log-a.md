# Pull log A — career money totals (pas2 + weball + cm)

**Date:** Thu Nov 12, 2026. **Agent:** money pull (pas2/weball). **Script:** `pull_money.py` (in this directory). **Diagnostics:** `pull-diagnostics.json`.

## Outputs

- `money_pas2_weball.csv` — 665 rows (one per roster person). Columns: `person_key, full_name, fec_candidate_ids, individual_contribution_total_career, aipac_pac_direct_career, aipac_earmark_transmitted_career, corporate_pac_career, corporate_earmark_transmitted_career, data_notes`.
  - The two `*_earmark_transmitted_career` columns are ADDITIONS to the specified column set (see §4): they break out conduit-earmark transmissions so the committee's own money is recoverable as (primary − earmark). All specified columns are present unchanged.
- `money_per_cycle.json` — per-person, per-cycle, per-candidate-id breakdown (`individual`, `aipac_pac_direct`, `aipac_earmark_transmitted`, `corporate_pac`, `corporate_earmark_transmitted`); only cycles with a nonzero value are listed. CSV↔JSON reconciliation: 0 mismatches (checked programmatically for all 665 persons × 5 money columns).
- `pull-diagnostics.json` — per-cycle diagnostics (row counts, dedup, corp-PAC counts, cm-missing stats).

## Inputs (all present; no waiting was needed)

- `roster.json` — 665 persons, 755 FEC candidate IDs (1 person with no IDs; 1 candidate ID shared by 2 roster entries — see §7).
- Bulk files staged by the download agent Nov 12, 2026 (downloads 12:13–12:19 UTC; see `bulk-inventory.md`): weball 24 cycles (70,381 rows), cm 24 cycles (298,679 rows), pas2 24 cycles (7,879,684 rows). All 84 zips downloaded with zero failures; pas224.zip re-verified here (`unzip -t` OK, 24,678,487 bytes, 703,163 rows).
- `fec-sources.md` (verified Nov 12, 2026) for committee IDs, field positions, and pull strategy. One correction noted in `bulk-inventory.md`: the doc's weball sample attached the value 143,180.09 to col 18 via the wrong row — col 18 IS `TTL_INDIV_CONTRIB`; the value belongs to a different row. My column use was verified independently by the API spot checks (§6).

## Method

- **Join key:** FEC candidate ID (`CAND_ID`). A person with several IDs is summed across all of them and all cycles 1980–2026.
- **Individual:** `TTL_INDIV_CONTRIB`, weball col 18 (1-indexed), summed per (candidate, cycle). No duplicate `CAND_ID` rows exist within any cycle's weball file (checked all 24). Amounts summed as integer cents (exact).
- **AIPAC PAC direct:** pas2 rows with `CMTE_ID = 'C00797670'`, `TRANSACTION_TP IN ('24K','24P')`, `CAND_ID` in the roster. AIPAC PAC exists only in cycles 2022/2024/2026 (first F1 Dec 2021); earlier cycles are legitimately $0.
- **Corporate PAC:** pas2 rows with `TRANSACTION_TP IN ('24K','24P')` where the contributing committee, joined to the **same-cycle** cm file, satisfies `CMTE_TP IN ('Q','N')` (col 10) AND `ORG_TP IN ('C','W')` (col 13). Column positions verified on known committees (Hallmark, Olin, TI, Weyerhaeuser, Citigroup all `ORG_TP=C`; AIPAC `ORG_TP=M`; UDP `ORG_TP` blank). Corporate-PAC counts per cycle: 1,382 (1980) – 2,179 (1988); 1,759 in 2024; 1,799 in 2026.
- **2026 is partial:** weball26 downloaded Nov 12, 2026 (max `CVG_END_DT` observed 12/31/2026 in-file). Re-pull after the cycle closes.

## Results — coverage and totals (career, 1980–2026)

| | Persons | Total $ |
|---|---:|---:|
| Any of the three columns ≠ 0 | 662 / 665 | — |
| Individual contributions ≠ 0 | 662 | **9,224,969,929.06** |
| AIPAC PAC direct ≠ 0 | 421 | **7,567,773.00** |
| Corporate PAC ≠ 0 | 603 | **972,722,564.00** |
| AIPAC earmark transmitted (subset of AIPAC direct) | 32 persons > 0 | 191,573.00 |
| Corporate earmark transmitted (subset of corporate) | 14 persons > 0 | 26,850.00 |
| AIPAC own-money (direct − earmark) | — | 7,376,200.00 |

- **No FEC activity found:** 1 — Everton Blair Jr. (`H6GA13062`).
- **No FEC candidate IDs in roster:** 1 — Alan Armstrong (`A000383`, appointed senator, never ran).
- **FEC activity found, all totals zero:** 1 — Anthony Constantino (`H6NY21157`).
- **Net-negative AIPAC career total:** 1 — Patrick Ryan, −$10,000 (see §5).
- AIPAC roster totals by cycle: 2022 **$2,155,300** (earmark $500); 2024 **$2,757,810** (earmark $21,410); 2026 **$2,654,663** (earmark $169,663).
- Top career AIPAC: Gottheimer $93,630 (of which earmark $65,730; own-money $27,900); Josh Riley $40,181; Ted Lieu $36,302; Scholten $35,564; Ronny Jackson $35,000. Top career corporate: Hoyer $14,673,995; McConnell $12,341,700; Neal $12,157,658; Clyburn $10,382,243; Cornyn $9,906,098. Top career individual: Warnock $316,226,119.10; Ossoff $295,701,989.71; Kelly $242,078,530.22; Brown $195,719,509.72; Schiff $162,422,170.20.
- Matched-row volumes: weball 4,186 roster rows; pas2 1,908,247 roster-matched 24K/24P rows; 324,510 of them negative (−$90,137,283 gross negatives netted). Zero bad-field rows in any weball/cm/pas2 file (all rows had the expected 30/15/22 fields). Zero matched pas2 rows had a contributing committee missing from the same-cycle cm file (classification coverage 100%).

## 1. Amended-filing dedup — TESTED, refined after a failed first attempt

**Test:** dedup on `TRAN_ID` alone was tried first and found UNSOUND. Evidence:
- `('C00841114','SB23.2000','S4WV00332')`, 2024: THREE rows share one TRAN_ID but are three distinct contributions — $18,000 (12/29/2023, YE), $78,000 (04/09/2024, Q2), $50 (09/10/2024, Q3). Different amounts, dates, and filings.
- `('C00749788','SB23004','H4MT00050')`, 2024: $103,176 (Q2) and $28,246 (Q3) share a TRAN_ID; distinct contributions.
- Some filers reuse line-number-style TRAN_IDs (`SB23.2000`, `SB23004`, `SB21.4511`) across reports. Across all cycles, 5,672 (committee, TRAN_ID, candidate) collision keys exist; 12 of them have differing amounts.
- The naive TRAN_ID-only dedup dropped 1,467 rows and **overstated the corporate career total by $2,201,359** (run-1 $974,923,923 vs final $972,722,564).

**Adopted rule:** dedup key = (`CMTE_ID`, `TRAN_ID`, `CAND_ID`, `TRANSACTION_AMT`, `TRANSACTION_DT`, `RPT_YR`), per cycle file; among colliding rows prefer non-memo (`MEMO_CD ≠ 'X'`), tie-break latest `FILE_NUM`. Final effect: **198 rows dropped, $369,558** across all cycles (all corporate; no AIPAC roster rows collided under the refined key).
- The rule still catches the genuine duplicate that motivated the test: Menendez `S6NJ00289`, TRAN_ID `B79BE4D20A8FC4EAD961` — original N/M4 +$5,000 (FILE_NUM 1701763) and amended A/M7 +$5,000 memo-X "SEE REDESIGNATION BELOW" (FILE_NUM 1734505), same amount/date/RPT_YR — one kept, one dropped. (Menendez is not in the roster, so this affects only the all-candidate diagnostic, not the CSV.)
- Exact-duplicate rows (full-row identical): 0 in AIPAC 2024; the `C00027466`/`C00042366` cases (identical amount/date/RPT_YR, same or different filings) are caught by the refined key.
- Cross-cycle TRAN_ID overlap for AIPAC: 0 shared TRAN_IDs between any pair of 2022/2024/2026 files, so no cross-cycle dedup was applied.

## 2. Memo code — TESTED, memo rows kept

- FEC's pas2 doc says memo items "should be included in your analysis." Tested against the data rather than taking it on faith.
- AIPAC 2024 memo-X rows: 7 rows totaling **+$12,000** (5× 24K + 2× 24Z). Of these, the $5,000 Menendez row is the duplicate handled by dedup (§1); the other 5× 24K rows (all in amended filing 1734505) net **+$2,000** of genuine redesignation entries (Menendez +$1,000 P2024, Barrasso +$1,000, Menendez +$1,000 G2024 "REDESIGNATION", Menendez −$1,000). Blanket-excluding `MEMO_CD='X'` would drop that $2,000 and understate redesignated money.
- Treatments compared, AIPAC 2024 (all candidates, 24K/24P, before the §3 exclusion): all rows $2,450,814; excluding all memo-X $2,443,814; refined dedup $2,445,814.
- **Decision: keep memo rows; let the dedup rule remove the one true duplicate.** (The separate earmark-text handling in §3–§4 is independent of `MEMO_CD`.)

## 3. Refund netting for AIPAC — INVESTIGATED; column is net of pas2-recorded refunds/voids

- pas2 negative rows are included in the sum (they net out). For AIPAC 2024: 1,204 negative rows (−$880,596) against 729 positive rows (+$3,336,410).
- **`oth` check (the flagged 17Z question):** `oth` was not staged, so I downloaded `oth24.zip` (505 MB, since deleted) and streamed it. AIPAC rows in oth24: 24K 1,967 rows ($2,649,814), 24Z 2 rows ($5,000), 22Z 1 row ($1,000), 18K 144 rows ($332,843). **Zero 17Z rows** ("Refund/Rebate/Return from candidate or committee") for AIPAC in 2024.
- **pas2 vs oth cross-check:** by `SUB_ID`, all **1,931 / 1,931** pas2 AIPAC 24K/24P rows appear identically in oth24 (same amounts). oth adds 36 rows ($199,000) whose recipients are NOT candidate committees (OTHER_IDs with blank `CAND_ID` in cm24; $15,000 amounts above the $5,000/candidate limit; 3 to leadership PACs) — correctly excluded from candidate totals. So pas2 is the right candidate-level source; oth adds nothing attributable to candidates.
- The F3X summary (`/v1/committee/C00797670/totals/?cycle=2024`) reports `fed_candidate_contribution_refunds` = **$32,100** for 2024 — captured inside pas2's negative 24K rows (netting by summation). No separate 17Z subtraction was needed or possible.
- **Label:** the AIPAC and corporate columns are **net of refunds/voids as recorded by negative pas2 rows**. That netting was verified as above for 2024; oth for 2022/2026 was NOT downloaded (same check not repeated for those cycles — residual caveat, §8).
- The $53.7M F3X line-23 figure (`fed_candidate_committee_contributions`) is NOT the candidate-level total: it includes earmark pass-throughs and contributions to other committees. The candidate-attributable total reconciles to OpenSecrets instead (§6). Do not use line 23 as the AIPAC direct total.

## 4. Earmark transmissions — the material finding (positive and negative sides)

AIPAC acts as a conduit for individual donors' earmarked contributions, reported as 24K rows in pas2 with memo text naming the donor (`EARMARK OF <donor>. TRANSMITTED BY CHECK/EFT`, `ERMK: <donor> - ORIGINALLY FORWARDED …`). These are **individuals' money, not the PAC's**, and they are already inside the candidate's individual-contribution total (weball). Two consequences:

**(a) Negative earmark rows (voids) — EXCLUDED from all totals.** Rows with memo text containing `EARMARK` (or starting `ERMK:`) and a negative amount are voided/refunded conduit earmarks whose originals are NOT in pas2. Proof: Maria Cantwell (`S8WA00194`) has 31 such voids (−$15,500, all "VOID: REFUNDED EARMARK OF HARRIET SCHLEIFER", 10/16/2023) and **zero** positive AIPAC rows in any cycle — searched by CAND_ID across 2022/2024/2026 and by OTHER_ID (`C00349506`) in both 2022 and 2024. Netting them creates phantom negatives (Cantwell −$15,500, Moulton −$22,301, Barrasso −$2,000, Barragán −$1,400 in the pre-exclusion run). Excluded (roster-matched): **1,375 rows, −$624,280** (all-candidate: 2022: 22 rows/−$16,371; 2024: 1,144/−$595,496; 2026: 536/−$52,608). Generic `VOIDED CHECK` / `VOID - …` rows are NOT excluded — those void PAC-treasury contributions whose originals ARE in pas2 (e.g. "VOIDED CHECK: REPORTED ON SEPTEMBER MONTHLY REPORT") and net correctly. Corporate-matched negative earmark rows: 5 rows, −$2,891 (all cycles) — same rule applied uniformly.
**(b) Positive earmark rows — KEPT in the primary column per the task spec, but broken out.** Positive earmark transmissions, all candidates: 2022 +$500 (1 row); 2024 $0; 2026 +$180,663 (119 rows, almost all in the amended year-end filing, Dec 2025). Roster share: $191,573 across 32 persons. Example: Gottheimer 2026 — 2× $5,000 own-money (the $5,000/election cap) + 32 earmark rows totaling $65,730 (donors named in memo text), for a $75,730 primary-column total. His own-money career AIPAC total is $27,900, not $93,630. The new `aipac_earmark_transmitted_career` column (and per-cycle `aipac_earmark_transmitted`) carries this split; PAC own-money = primary − earmark. Corporate earmark positives are small: 66 rows, +$65,329 all-candidate / $26,850 roster.
- The 2024 `ERMK:` re-report rows (21 rows, +$21,410, amended filing 1734505, "ORIGINALLY FORWARDED … SEE JULY 2022 MONTHLY") are counted in the earmark column; they may re-attribute money already counted via 2022 originals — kept, disclosed here as a possible ~$21k overstatement in the 2024 cycle (not surgically removable: originals cannot be reliably matched, different TRAN_IDs).

## 5. Remaining net-negative case

- **Patrick Ryan (`H8NY19223`): AIPAC −$10,000.** Rows: +$5,000 (2022 12G), +$5,000 (2026 M12 P2026), +$5,000 (2026 amended M10 P2026), and five −$5,000 rows in the 2026 M8 filing (07/31/2026, RPT_YR P2024/P2026/G2022/G2024/G2026, no memo text). The five negatives void prior-cycle contributions whose originals are not in pas2 as 24K rows — the same structural asymmetry as §4(a) but without earmark memo text, so no text-based rule can separate them. Kept as-is; flagged in `data_notes`. This is the only negative career total in any column.

## 6. Spot checks (all run Nov 12, 2026)

| # | Check | Result |
|---|---|---|
| 1 | Weball vs FEC API candidate totals, Jeffries `H2NY10092`, 2024 | weball `TTL_INDIV_CONTRIB` $15,936,793.65 == API `individual_contributions` $15,936,793.65 — **exact** |
| 2 | Same, McCaul `H4TX10093`, 2024 | $1,464,364.63 == $1,464,364.63 — **exact** |
| 3 | Same, Pelosi `H8CA05035`, 2024 | $9,554,439.66 == API sample `fec-candidate-totals-sample.json` — **exact** |
| 4 | AIPAC 2024 all-candidate total (final rules) vs OpenSecrets | Mine **$3,041,310** (786 rows) vs OpenSecrets $3,037,900 (347 House + 20 Senate recipients, max $20,000/recipient). Gap **+$3,410 (0.11%, mine higher)**. Structural agreement: my 363 distinct recipients, max $20,000 net per recipient. Note the pre-exclusion literal sum was $2,445,814 (24% below OpenSecrets) — the VOID-earmark exclusion (§4a) is what closes the gap, corroborating it. |
| 5 | pas2 vs oth24, AIPAC 24K/24P, by SUB_ID | 1,931/1,931 identical amounts; oth adds only 36 non-candidate rows ($199,000) |
| 6 | AIPAC 2024 row counts vs download inventory | 1,933 rows (943 in 2022; 1,311 in 2026) — matches `bulk-inventory.md` smoke counts |
| 7 | Schedule B API, AIPAC→Jeffries 2024 | **Failed, HTTP 504 "Query timed out"** (twice today; verification agent also hit a 504 once on this endpoint). Not used; checks 4–5 substitute for it. |
| 8 | Independent re-check, Gottheimer individual career | `grep` over all 24 weball files, summed: $30,958,908.44 — matches CSV |
| 9 | 24Z in-kind rows | 2 rows, $5,000, 2024 only (Jeffries $2,500; McCarthy $2,500, both memo-X). Excluded per the specified 24K/24P filter; documented here |

## 7. Roster / data-quality notes

- **Kristen McDonald Rivet is in the roster twice** (`M001237` and `kristen-mcdonaldrivetmihouse`), same FEC ID `H4MI08218`, identical totals in both rows. Roster fix needed upstream; both rows are emitted as-is per the "one row per roster person" spec.
- **Alan Armstrong** (`A000383`): no FEC candidate IDs — appointed senator (Mar 2026), never ran; all totals 0.00 with note.
- **Everton Blair Jr.** (`H6GA13062`): IDs present, no weball or pas2 rows at all — "no FEC activity found".
- **Anthony Constantino** (`H6NY21157`): FEC rows exist but every total is 0.00 — "FEC activity found; all totals zero".
- **ORG_TP quirk (rule follows the file):** `NEA FUND FOR CHILDREN AND PUBLIC EDUCATION` carries `ORG_TP=C` in cm24 despite being labor-affiliated; it counts as corporate under the Q/N + C/W rule. Any reclassification is a methodology decision for the coordinator, not a data error.
- Corporate-PAC definition excludes trade associations (`ORG_TP=T`, e.g. NAR PAC), labor (`L`), membership orgs (`M`, incl. the AIPAC PAC itself), cooperatives (`V`), and hybrid PACs (`CMTE_TP` V/W) per the verified rule. `ORG_TP` blank for 17,699/20,937 cm24 rows (mostly candidate committees) — treated as unclassified, never corporate.

## 8. Unverified / open items (do not treat as resolved)

1. **$3,410 residual** between my AIPAC 2024 all-candidate total ($3,041,310) and OpenSecrets ($3,037,900). Likely snapshot/amendment timing (e.g. the 87-row amended 12G filing, FILE_NUM 1879064, image-dated 2025-03-03, +$422,000, post-dates OpenSecrets' Feb 6, 2025 data release) and/or the 24Z in-kind treatment. Immaterial (0.11%) but unreconciled to the dollar.
2. **17Z check is 2024-only.** oth22/oth26 were not downloaded. The 2024 result (zero 17Z rows) plus pas2 netting makes a large hidden refund balance unlikely, but it is not proven for 2022/2026.
3. **ERMK re-report rows** ($21,410, 2024) may double-count 2022 originals (§4b).
4. **F3X line 23 ($53.7M)** not reconciled line-by-line; it aggregates earmark pass-throughs and other-committee contributions and is not a candidate-level figure (§3).
5. **Patrick Ryan −$10,000** (§5) — negatives without earmark memo text, originals not in pas2.
6. **2026 figures are partial** (cycle in progress; re-pull after close). Pre-1980 careers are out of scope (bulk files start 1980).
7. **Column-presentation decision for the coordinator:** `aipac_pac_direct_career` follows the specified pas2 sum (includes positive earmark transmissions; excludes conduit-earmark voids). If the tracker wants "PAC's own money" as the headline AIPAC column, use `aipac_pac_direct_career − aipac_earmark_transmitted_career` (career total $7,376,200 vs $7,567,773). The earmark breakout columns exist precisely so this choice can be made downstream without re-pulling.
8. `oth24.zip` (505 MB, downloaded only for the §3 test) was deleted after the test; findings are recorded here and are reproducible from fec.gov bulk downloads.

## Method history (for audit)

- Run 1 (superseded): TRAN_ID-only dedup, no earmark-void exclusion. AIPAC $6,978,506; corporate $974,923,923; 7 persons with net-negative AIPAC totals. Discarded after the §1/§4 tests showed the dedup key was unsound and the earmark voids were phantom negatives.
- Run 2 (superseded): refined dedup + narrow `VOID: REFUNDED EARMARK` exclusion. AIPAC $7,560,463; corporate $972,721,864.
- **Run 3 (final, shipped):** refined dedup + broad earmark-negative exclusion + earmark breakout columns. AIPAC $7,567,773 (earmark $191,573); corporate $972,722,564 (earmark $26,850). Differences vs run 2 are the 9 variant-wording void rows in 2024 (−$7,310 AIPAC) and 5 corporate negative earmark rows (+$700 net corporate).
