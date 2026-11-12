# UDP pull log — B (corrected source)

**Date:** Nov 12, 2026. **Committee:** United Democracy Project (UDP), FEC `C00799031`, Super PAC (independent-expenditure-only), first F1 Jan 3, 2022.
**Outputs:** `money_udp.csv` (665 rows, one per roster person) and this log, in `~/workspace/user/congress-money-tracker/work/`.
**Source files staged:** `bulk/ie/2022/`, `bulk/ie/2024/`, `bulk/ie/2026/` (see §2).

## 1. CORRECTION — the `oppexp` bulk files are NOT Schedule E (do not use them)

The original plan pointed at the FEC `oppexpYY.zip` bulk files as the independent-expenditure source. **That is wrong, and no `oppexp` data was used for any figure in `money_udp.csv`.**

Evidence found while verifying the staged files:

- Every staged `bulk/oppexp/<cycle>/oppexp.txt` (all 12 cycles, 2004–2026) is a **26-column Schedule B operating-expenditure file**: col 1 is the spending committee ID, col 7 is form type (`F3`/`F3X`/`F3P`), col 8 is always `SB`, transaction types are 17/21B/23, and there is **no candidate column and no support/oppose column**. The 2024 file has 2,249,912 rows, all `F3|SB`, `F3X|SB` or `F3P|SB`; zero rows with schedule `SE`.
- UDP rows in those files are operating expenses (e.g. Uber, credit-card payments, hotels), not independent expenditures. El-Sayed's candidate ID `S6MI00418` returns **0 rows** in the 2022/2024/2026 `oppexp` files.
- The FEC's own `oppexp` file-description page lists a 23-column layout headed by `CAN_ID` — the staged files do not match that layout in any column. Whether FEC serves a different file under the `oppexp` name or the staging agent fetched the wrong file is undetermined; either way the staged `oppexp` files cannot produce Schedule E totals.
- The `oppexp` files were **left untouched** (not deleted); the mislabel decision is the coordinator's. The `pas2` staging has a parallel naming oddity (`itpas2.txt` inside `pas2YY.zip`) that the coordinator should also confirm — out of scope for this pull.

## 2. Correct source — FEC `independent_expenditure_<cycle>.csv`

Found on the FEC bulk-data index (`https://www.fec.gov/data/advanced/?tab=bulk-data`, fetched Nov 12, 2026): alongside `oppexpYY.zip`, each cycle also publishes **`independent_expenditure_YYYY.csv`** — the current-format independent-expenditure bulk file. Downloaded Nov 12, 2026 for 2022, 2024, 2026 only (UDP did not exist before 2022, so no earlier cycle can contain UDP rows).

| Cycle | File | Size | Rows (incl. header) | MD5 |
|---|---|---|---|---|
| 2022 | `bulk/ie/2022/independent_expenditure_2022.csv` | 16 MB | 61,780 | `02b1eb886087c259558916f19a7c3045` |
| 2024 | `bulk/ie/2024/independent_expenditure_2024.csv` | 19 MB | 73,450 | `2eda312ee4ef9e49f6065b0ee273af86` |
| 2026 | `bulk/ie/2026/independent_expenditure_2026.csv` | 14 MB | 51,244 | `c34c56cb50dfc2d6cc71c074a92171a6` |

Server `Last-Modified` for all three: Thu Nov 12, 2026 10:13 GMT (downloaded the same day). The 2026 file's latest dissemination date is Oct 31, 2026 — **2026 is partial**.

Header (identical in all three files; 23 columns, 1-indexed):

```
1 cand_id, 2 cand_name, 3 spe_id, 4 spe_nam, 5 ele_type, 6 can_office_state,
7 can_office_dis, 8 can_office, 9 cand_pty_aff, 10 exp_amo, 11 exp_date,
12 agg_amo, 13 sup_opp, 14 pur, 15 pay, 16 file_num, 17 amndt_ind, 18 tran_id,
19 image_num, 20 receipt_dat, 21 fec_election_yr, 22 prev_file_num, 23 dissem_dt
```

Filter columns used: **`spe_id` (3) = `C00799031`, `sup_opp` (13) = `S`, `cand_id` (1) joined to the roster, `exp_amo` (10) summed.** Notes on the layout: `exp_date` (11) is blank on UDP rows — the populated date is `dissem_dt` (23); `ele_type` (5) is a single letter (`P`/`G`/`O`/`S`/`R`), not the `P2024`-style code the old doc suggests. `agg_amo` (12) is a running aggregate, never summed.

## 3. Method

1. Per cycle, read the CSV, keep rows with `spe_id = C00799031`.
2. **Dedup by `tran_id`** (see §4): keep one row per `tran_id` — the one with the latest `receipt_dat`, tie-broken by the highest `file_num` (the amendment). Then keep `sup_opp = 'S'` only.
3. Join `cand_id` to `roster.json` (`fec_candidate_ids`, 755 IDs across 665 persons); sum across all of a person's IDs and all three cycles. `udp_ie_support_career` is in dollars, 2 decimals.
4. **2022 blank-`cand_id` rows — name-resolved (see §6).** 100 of the 185 deduped 2022 UDP rows have a blank `cand_id` (the filer did not supply it; the FEC doc warns this field "is provided by filers and may be missing"). `cand_name` + state + district + office is present on all of them. Where that tuple matches exactly one roster person, the support amount was attributed to that person and flagged in `data_notes`. That added $4,819,602.26 across 3 people (Davis, Foushee, Mullin). The remaining blank-ID support ($660,319.30, Steven Irwin, PA-12) belongs to a non-roster candidate and is excluded; blank-ID oppose rows are never counted as support.
5. Oppose spending is **never** added to a person's total. Where UDP also spent opposing a roster person, the amount is recorded in that person's `data_notes` only (7 people; largest: El-Sayed $20,903,437.57, Dave Min $4,615,288.76, Thomas Massie $3,896,751.38, Summer Lee $3,264,153.49).
6. One roster person (Alan Armstrong, appointed OK senator, no FEC candidate ID on file) is unsearchable in IE data and is $0.00 with that note. Every other $0.00 means the search ran and found no UDP support rows.

What this column is: money UDP spent **about** a candidate's race (ads, mail, phones) — independent expenditures, legally uncoordinated with the campaign. It is **not** money given to the campaign and must not be described as a contribution.

## 4. Amended-filing dedup test + 2024 reconciliation vs published figures

FEC warns the IE file contains both original and amended reports. Test: dedup by `tran_id`, keeping the latest (`receipt_dat`, `file_num`). Two independent implementations of the rule (latest-receipt vs highest-amendment-rank-then-latest-receipt) give **identical totals in all three cycles**, and no duplicated `tran_id` group ever differs in candidate or support/oppose — only in amount (amendments correct amounts, e.g. 2022 tran `E1953A03A1E4C4A4AB49`: $366,425.00 → $315,125.50) or is an exact repeat.

| Cycle | UDP rows raw | Deduped rows | Raw total (S+O) | Deduped total (S+O) | Deduped support | Deduped oppose |
|---|---|---|---|---|---|---|
| 2022 | 199 | 185 | $28,608,537.80 | $26,107,515.77 | $14,336,577.63 | $11,770,938.14 |
| 2024 | 267 | 266 | $39,044,058.49 | $38,044,932.69 | $14,085,443.42 | $23,959,489.27 |
| 2026 (partial) | 166 | 163 | $54,453,360.66 | $54,322,881.51 | $23,355,879.11 | $30,967,002.40 |

Raw (no dedup) would overstate 2024 by $999,125.80 (one duplicated oppose row) and 2022 by $2,501,022.03 (14 duplicated rows). The deduped figures are the ones published in `money_udp.csv`.

**2024 reconciliation vs OpenSecrets tabulation** (2023–2024 cycle: total $37,860,200; $14,067,863 supporting Democrats; $20,786,780 opposing Democrats; $3,043,662 opposing Republicans; $0 supporting Republicans — confirmed via a secondary source quoting OpenSecrets' 2025 tabulation):

| 2024 | This pull (deduped CSV) | OpenSecrets | Difference |
|---|---|---|---|
| Total IE | $38,044,932.69 | $37,860,200 | **+$184,732.69 (+0.49%)** |
| Support Democrats | $14,085,443.42 | $14,067,863 | +$17,580.42 (+0.12%) |
| Oppose Democrats | $20,878,273.36 | $20,786,780 | +$91,493.36 (+0.44%) |
| Oppose Republicans | $1,513,297.17 | $3,043,662 | −$1,530,364.83 |
| Oppose, candidate party blank | $1,567,918.74 | — | — |
| Oppose Rep + oppose blank-party | $3,081,215.91 | $3,043,662 | +$37,553.91 (+1.23%) |

Composition finding: the apparent oppose-Republican gap is a **party-field gap, not a money gap**. The CSV leaves `cand_pty_aff` blank on $1,567,918.74 of oppose spending (one candidate, John Hostettler, IN — a Republican); OpenSecrets evidently classifies those rows as opposing Republicans. Adding them, oppose-Republican reconciles to within 1.2%. Residual total gap is +$184,732.69 (+0.49%), unresolved — see §8 for the leading hypothesis (24/48-hour notices vs Schedule E vintage, §7).

## 5. Period filtering — verified clean in the bulk files

Each CSV's `fec_election_yr` is 100% its own cycle (2022 file: 61,779/61,779 rows are 2022; 2024: 73,449/73,449 are 2024; 2026: 51,243/51,243 are 2026). No cross-cycle leakage in the bulk files — unlike the API (see §7). Dissemination dates: 2022 file Apr 2021–Oct 2022; 2024 file Apr 2023–Oct 2024 (receipt dates from Apr 2023); 2026 file Apr 2025–Oct 31, 2026. **2026 is partial** (through Oct 31, 2026) and must be re-pulled after the cycle closes.

## 6. 2022 blank-`cand_id` rows — detail

100 deduped 2022 UDP rows have blank `cand_id` (57 support, 55 oppose — counts overlap because grouping is by row). By candidate name/state/district/office:

| Candidate (name, state, district) | Support | Oppose | Roster? |
|---|---|---|---|
| Davis, Don (NC-01, H) | $2,102,637.82 | $0 | **Yes — Donald G. Davis (H2NC02287); attributed** |
| Foushee, Valerie (NC-04, H) | $2,128,196.18 | $0 | **Yes — Valerie P. Foushee (H2NC06114); attributed** |
| Mullin, Kevin (CA-15, H) | $588,768.26 | $0 | **Yes — Kevin Mullin (H2CA14162); attributed** |
| Irwin, Steven (PA-12, H) | $660,319.30 | $0 | No (not a member; Jacqui Irwin, CA, is a different person); excluded |
| Lee, Summer (PA-12, H) | $0 | $3,264,153.49 | Yes, but oppose only — $0 support; oppose noted, not counted |
| Cisneros, Jessica (TX-28, H) | $0 | $1,428,196.80 | No (Gilbert Cisneros, CA, is a different person); excluded |
| Garcia, Cristina (CA-42, H) | $0 | $515,088.43 | No; excluded |
| Smith, Erica (NC-01, H) | $0 | $335,412.57 | No; excluded |
| Turner, Nina (OH-11, H) | $0 | $198,878.90 | No (Michael Turner, OH, is a different person); excluded |

Matching was by name **plus** state/district/office, never last name alone (e.g. "Davis, Don" NC-01 matches Donald G. Davis, not Danny K. Davis of IL-07). None of Davis/Foushee/Mullin has any `cand_id`-bearing UDP support row in 2022, so there is no double-counting between the two treatments. 2024 and 2026 have **zero** blank-`cand_id` UDP rows, so this issue is 2022-only.

## 7. API cross-checks — and why the API was NOT used as the source

The Schedule E API (`api.open.fec.gov/v1/schedules/schedule_e/`, DEMO_KEY) was used only for spot-checks. It revealed two material behaviours:

- **Each expenditure appears twice in the raw API** — once as the 24/48-hour notice (`filing_form` F24, `is_notice=true`) and once as the Schedule E itemization on the committee's regular report (`F3X`, `is_notice=false`), same `transaction_id`, same amount. A naive API sum double-counts exactly 2× (Bell 2024: API raw support $6,712,558.50 = 2 × CSV $3,356,279.25). The bulk CSV contains one copy (the notice copy — its `file_num`/`image_num` match the F24 filing). Deduping the API by `tran_id` (or taking F3X-only rows) reproduces the CSV.
- **The API totals endpoint is unreliable for this purpose.** `schedule_e/totals/by_candidate/` for Bell 2024 returned support $4,581,013.51 and oppose $1,075,162.14 — but the raw endpoint for the identical filter returns support $3,356,279.25 and oppose $0. The totals endpoint's figures match neither the F24 nor the F3X universe. Do not use it. (This is consistent with the period-filter leak already noted in `fec-sources.md`: a `two_year_transaction_period=2024` query returned a 2026-cycle row, and the committee-wide count of 1,269 ≈ 2 × the 632 all-cycle UDP transactions — i.e. the filter does not constrain the count.)
- **F24 notices vs F3X Schedule E differ slightly in amount.** Latimer 2024: F24 support $4,682,560.29 (matches the CSV exactly); F3X support $4,643,836.68 (−$38,723.61, −0.83%). El-Sayed 2026: F24 oppose $20,903,437.57; F3X oppose $20,140,908.74 (−$762,528.83, −3.6%; 35 F3X tran_ids vs 34 F24). Notices are filed first and can be corrected on Schedule E, so the F3X universe runs slightly lower. This is the leading explanation for the residual +0.49% gap vs OpenSecrets in §4 (OpenSecrets tabulates from Schedule E filings). Settling it would need a registered API key and a full F3X pull; it was not attempted on DEMO_KEY (one API call returned empty once, apparently rate-limit pressure; a retry after 60 s succeeded — DEMO_KEY is ~30 req/hr shared).

## 8. Spot-checks (≥3 people, all against independent sources)

1. **Wesley Bell (H4MO01134), 2024 support — $3,356,279.25.** API raw rows, F24 copy: $3,356,279.25 (41 rows) — **exact match**. F3X copy also $3,356,279.25. API totals endpoint disagrees ($4,581,013.51) — see §7, endpoint disregarded.
2. **George Latimer (H4NY16087), 2024 support — $4,682,560.29.** API raw rows, F24 copy: $4,682,560.29 (19 rows) — **exact match**. (F3X copy $4,643,836.68; see §7.)
3. **Abdul El-Sayed (S6MI00418), 2026 — $0 support, $20,903,437.57 oppose; Haley Stevens (S6MI00426), 2026 support — $10,498,735.23.** Combined Michigan Senate spending in this pull: $20,903,437.57 + $10,498,735.23 = **$31,402,172.80**, vs $31.47M reported (Nov 4, 2026) for UDP's failed Michigan effort to stop El-Sayed — **within 0.2%**. API raw rows for El-Sayed 2026: 59 rows, 35 distinct tran_ids; F3X oppose $20,140,908.74 (see §7 for the vintage gap).
4. **Adrian Boafo (H6MD05321), 2026 support — $5,734,013.28.** Reported (Nov 4, 2026) as $5.73M for Boafo in MD-05 — **match**.
5. **Cycle totals vs published:** 2022 deduped total $26,107,515.77 vs ~$26.1M reported for UDP's 2022 independent expenditures — **match**. 2026 deduped total $54,322,881.51 vs "≈$54M in independent spending as of Oct 24, 2026" and "$53.4M in the 2026 cycle" from other tallies — **consistent within ~1.7%** (different vintages; this file runs through Oct 31, 2026).

## 9. Results — coverage

- **13 of 665 roster persons have UDP support spending > $0; 652 are $0.00.**
- Roster career support total: **$42,415,003.76** — 2022: $10,936,406.70; 2024: $13,980,903.77; 2026 (partial): $17,497,693.29.
- Top persons (career): Haley M. Stevens $14,376,765.69 (2022 House ID H8MI11254 $3,878,030.46 + 2026 Senate ID S6MI00426 $10,498,735.23); Adrian Boafo $5,734,013.28; George Latimer $4,682,560.29; Sarah Elfreth $4,218,074.08; Wesley Bell $4,041,905.41 (2024 $3,356,279.25 + 2026 $685,626.16); Valerie P. Foushee $2,128,196.18 (name-resolved 2022); Donald G. Davis $2,102,637.82 (name-resolved 2022); Glenn Ivey $1,734,184.42; Jimmy Gomez $1,723,990.15; Kevin Mullin $588,768.26 (name-resolved 2022); Ed Gallrein $579,318.62; Henry Cuellar $421,417.54; Shontel M. Brown $83,172.02.
- UDP support to candidates **not** in the roster (excluded from `money_udp.csv` by design): $8,702,577.10 — Melissa Conyears-Ervin (H4IL07177) $4,968,500.25, Adam Hollier (H2MI13246) $2,739,851.63, Melissa Hernandez (H6CA14163) $825,292.77, Joanna Weiss (H4CA47119) $104,539.65, Michael Rogers (S4MI00595) $64,392.80. (Jamaal Bowman and Cori Bush are also not in the roster — both lost 2024 primaries and are not 119th/120th members — so their large UDP oppose totals, $9,865,492.96 and $7,700,051.64 across 2024+2026, correctly do not appear.)
- `money_udp.csv` verified by re-reading: 665 rows, sum $42,415,003.76, 13 nonzero.

## 10. Unverified / open items

- **Residual 2024 gap +$184,732.69 (+0.49%) vs OpenSecrets** (§4). Leading hypothesis is the F24-notice vs F3X-Schedule E vintage difference (§7: Latimer −0.83%, El-Sayed 2026 −3.6% on the F3X side). Not adjusted — the published figures are the deduped bulk-file figures, and the gap is disclosed here. A registered-key F3X pull could test it.
- **2026 is partial** (through Oct 31, 2026; file last modified Nov 12, 2026). Re-pull after the cycle closes; expect the 2026 totals to rise and some amounts to be amended.
- **API totals endpoint anomaly** (§7) — reported, not resolved; the raw endpoint is the ground truth and it corroborates the CSV.
- **One transient API failure**: a DEMO_KEY call returned an empty response once; a retry after 60 s returned HTTP 200. No data was fabricated around it.
- **2022 name-resolved attribution** (§6) is a judgment call: the FEC file itself leaves `cand_id` blank, and attribution rests on name+state+district+office. The amounts and the method are flagged per person in `data_notes`; a stricter ID-only version would put Davis, Foushee and Mullin at $0 and lower the 2022 roster total to $6,116,804.44.
- The `oppexp`/`pas2` staging question (§1) belongs to the coordinator; the `oppexp` files were left in place.
- `fec_candidate_ids` in `money_udp.csv` are semicolon-joined (the roster stores a list); `person_key` is the join key.

## 11. File inventory (this pull)

- `~/workspace/user/congress-money-tracker/work/money_udp.csv` — 665 rows + header.
- `~/workspace/user/congress-money-tracker/work/pull-log-b.md` — this file.
- `~/workspace/user/congress-money-tracker/work/bulk/ie/2022/independent_expenditure_2022.csv`
- `~/workspace/user/congress-money-tracker/work/bulk/ie/2024/independent_expenditure_2024.csv`
- `~/workspace/user/congress-money-tracker/work/bulk/ie/2026/independent_expenditure_2026.csv`
- Scratch analysis scripts (not deliverables): `/tmp/ie-check/analyze.py`, `names.py`, `final.py`, `build.py`, `build2.py`; API spot-check responses `/tmp/ie-check/api-*.json`.
