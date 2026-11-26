# Square-one JFC variants: do joint-fundraising-committee earmarks count as AIPAC direct?

**Status:** research for the square-one re-derivation. **Not a decision.** This file brings the decision to Craig with numbers; it does not pick a variant.
**Date:** 2026-11-25. **Branch:** `square-one-rederivation` (repo at `2f65cb5`). No commits or pushes were made for this work; the coordinator owns commits.

## TL;DR — the decision, in numbers

1. **The JFC question is small. The earmark question is enormous. Do not confuse them.** Replacing the pinned bulk-file (pas2) AIPAC/pro-Israel direct figures with live FEC API Schedule B figures moves the 120th-Congress `aipac_direct` career total from **$5,955,560** to **$81,285,425** (Variant B) and the `pro_israel_pac_career` total from **$19,140,251** to **$109,519,850**. The JFC decision — whether to add JFC earmarks on top of that — moves those totals by **+$564,631** and **+$3,644,165** respectively (Variant A). The JFC decision is ~0.7% of the AIPAC correction and ~4% of the pro-Israel correction.
2. **On flags, the JFC decision moves exactly two members of the 120th Congress.** Under Variant A (JFC counts) vs Variant B (JFC excluded), the 2026-cycle AIPAC/UDP flag count is **258 vs 256** and the headline-term flag count is **299 vs 297**. The two members are **Elijah Crane** (2026 AIPAC-JFC $4,694.08) and **Paul LePage** (2026 AIPAC-JFC $3,179.12) — each has no other AIPAC/UDP money in the window, so the JFC money alone flags them. Strict-clean counts do not change at all (81 in the 2026 cycle, 77 headline-term, under both variants); Balanced and Lenient not-dirty counts each fall by 2 (the same two members move from below-threshold to dirty). Across all 664 roster rows, one more member flips Strict-clean under A: **Ryan K. Zinke** (119th only; 2026 AIPAC-JFC $3,705.12, dirty $0 → $3,705.12).
3. **Seven of the ten comparison members have $0 in JFC earmarks in every cycle.** Stevens, Bell, Gottheimer, Latimer, Boafo, Aguilar and Warner received no listed-conduit money through any joint fundraising committee in 2022, 2024 or 2026. Only Jeffries ($577,950 career JFC, of which AIPAC $490,650), Susan Collins ($90,606) and Fetterman ($25,500, all non-AIPAC conduits) have any JFC money among the ten.
4. **The November 13/25 claim that the OpenSecrets gaps for Bell, Gottheimer and Aguilar "are JFCs" is refuted by the FEC record, on two independent legs.** (a) No listed conduit disbursed a dollar to any JFC for Bell, Gottheimer or Aguilar in any cycle 2022–2026 — and Bell has no JFC at all in the FEC committee record. (b) Jeffries *does* have $399,300 of AIPAC→JFC earmarks in 2026, all dated on or before 2026-05-20 (before OpenSecrets' Oct 24, 2026 cutoff) — yet OpenSecrets shows him below $155,955 for 2026, i.e. it does **not** count those earmarks. The OpenSecrets gaps (Bell +$771,839; Gottheimer +$239,177 after correcting a committee-name miss; Aguilar +$402,814) remain unexplained by any FEC Schedule B mechanism. See §8.
5. **A classifier bug found in this session moved $1,149,551.63.** The committee-master lookup was last-wins per normalized name, so when two House candidates shared a committee name (Vargas, Rogers, Schneider, Salazar, Case, Courtney, Lucas, Moore), every by-recipient row under that name went to the wrong candidate. All eight cases are resolved from raw Schedule B and fixed in the v4 figures used here; the classifier now fails safe on ambiguous names. See §3.3.

## 1. The question and the two variants

OpenSecrets counts earmarks sent to a candidate's joint fundraising committee (JFC) as AIPAC money; the tracker's live-direct figure does not. A JFC is a committee (FEC designation `J`) that raises money jointly for two or more beneficiaries — typically a candidate's authorized committee plus a party committee and/or other candidates — and then distributes it. An earmarked contribution is an individual donor's check routed through a conduit PAC (here AIPAC PAC or another listed pro-Israel PAC) to the JFC; the conduit reports the transmission on Schedule B, line 23, with a description such as `EARMARK OF SANDRA WULIGER`. The money is the donor's, not the conduit's own funds, but it reaches the candidate's fundraising operation only because the conduit bundled and transmitted it.

- **Variant A — JFC earmarks COUNT as AIPAC direct.** Every dollar a listed conduit disbursed to a JFC is attributed to the JFC's candidate(s) and added to `aipac_direct` (AIPAC PAC disbursements) or the pro-Israel PAC columns (other listed conduits). Single-candidate JFCs attribute in full to that candidate; multi-candidate JFCs attribute by the outflow-split rule in §3.2.
- **Variant B — JFC earmarks EXCLUDED.** Only disbursements to a candidate's own authorized committee count. JFC disbursements are reported separately (or not at all) and never enter `aipac_direct`, the pro-Israel PAC columns, the AIPAC/UDP flag, or any clean verdict.

Both variants sit on the same API-corrected direct base (Base 2 in §7). The report also shows Base 1 — JFC money added to the *current pas2 base* without the API correction — so the JFC decision can be judged independently of the much larger source correction.

## 2. Sources and as-of dates

| Figure | Source | As of |
|---|---|---|
| Live API direct + JFC (all dollar figures in §§4–6) | FEC API `schedules/schedule_b/by_recipient`, committee-by-committee, via direct `curl` from this VM with `DEMO_KEY` (background-worker calls to `api.open.fec.gov` are blocked by sandbox egress; direct curl works) | **2026-11-25** (pulled this day; AIPAC 2026 totals identical to the Nov 13 pull to the cent: 734 rows, $54,425,012.12) |
| Raw Schedule B rows (collision resolutions, Jeffries dates) | FEC API `schedules/schedule_b`, filtered by `committee_id` + `recipient_committee_id` (+ cycle) | **2026-11-25** |
| Tracker baseline (pas2 figures, flag/clean counts) | `congress-money-tracker.json` (664 rows), remote master `2f65cb5`, pinned snapshot `fec-bulk-2026-11-22` (`data/source/baseline.json`) | Pinned bulk files through **2026-10-14** (pas2 coverage end date) |
| Committee master (designations, candidate linkage) | `data/raw/cm/{2022,2024,2026}/cm.txt` (pinned) | Same snapshot |
| Pro-Israel PAC list | `data/source/pro_israel_pacs.csv` (66 committees; 62 with FEC IDs) | Downloaded **2026-11-25** (Track AIPAC's published list) |
| OpenSecrets figures | `~/workspace/user/trackaipac-opensecrets-comparison-2026.md` §§4–5 (state pages + org recipients page) | OS 2026 figures as of **2026-10-24** (pages still carried that note on Nov 25; unchanged since Nov 13) |
| Recount rules | `receipts/domain/term.py`, `receipts/domain/clean_2026.py`, `receipts/transform/compute_2026.py`, methodology §14; presets from `config.yaml` (Balanced: corp >$100k AND >5% of total receipts; Lenient: corp >$250k AND >10%) | — |

Cycle note: the Nov 13 report's cycle trap (the `by_recipient` endpoint returning 2022/2024/2026 rows despite a 2026 filter) did **not** bite on the Nov 25 pulls — every row carried the requested cycle — but all figures here were still filtered on the `cycle` field in the returned rows, as the task required.

## 3. Classification rule

### 3.1 The rule, in order

For each disbursement row in a listed conduit's `by_recipient` pull (spender = one of the 62 FEC-ID committees in `pro_israel_pacs.csv`; cycles 2022, 2024, 2026):

1. **Committee-master lookup by normalized name** (uppercase, punctuation stripped) against that cycle's `cm.txt`. Exact match first, then prefix match (≥15 chars), then difflib fuzzy ≥0.88, then other cycles' masters for terminated committees.
2. **Designation decides the kind.** `J` (joint fundraising committee) → **JFC**. `P`/`A` (principal/authorized committee) → **direct**, attributed to the candidate in cm `CAND_ID` (mapped to a roster person where the candidate is in the dataset). Any other designation (party `Y`, super PAC `U`, vendor, etc.) → **other**.
3. **Only on a cm miss:** pas2-name fallback, restricted to 24K/24P rows, with a surname-token rule (a roster person's surname must appear as a token in the recipient name). This exists because some recipient names in the API do not match cm (e.g. a typo variant such as `MIKE JOHNSON FOR LOUSIANA`, which resolves to Mike Johnson via cm fuzzy matching).
4. **Proven renames as aliases:** `BIDEN VICTORY FUND` → Harris Victory Fund (C00744946, J); `BIDEN ACTION FUND` → Harris Action Fund (J); `BIDEN FOR PRESIDENT` → Harris for President (P, non-roster). Proven by the `(FORMERLY BIDEN VICTORY FUND)` by-recipient rows.
5. **Name-pattern-only `jfc?`:** an unmatched name containing VICTORY FUND / MAJORITY FUND / BATTLEGROUND / LEADERSHIP FUND / JOINT FUNDRAIS / VICTORY COMMITTEE is flagged `jfc?` rather than silently dropped. In the event, only **$250.00** fell in this bucket (one DJOPA 2024 row, `RITCHIE TORRES VICTORY FUND`, attributed to Ritchie Torres in the attribution step).

### 3.2 Attributing JFC money to members

- **Single-candidate JFCs (name-attributed):** where the JFC name contains one roster person's name (first+last match; surname-only if unique in the roster, with Jr./Sr./II/III suffix stripping — this fixed `KEAN VICTORY FUND` → Tom Kean Jr., $46,950; first-name-only only when the name has no other name token, e.g. `ELISE VICTORY FUND` → Stefanik), the full inflow attributes to that person. 99 JFC-cycle keys, **$3,660,462.02**.
- **Multi-candidate or ambiguous-surname JFCs (outflow-split):** the inflow is split by the JFC's own same-cycle Schedule B disbursements to candidate committees. Denominator = roster + non-roster candidate-committee outflows (party committees, vendors and other PACs excluded); shares sum to the inflow when the denominator is positive. 24 JFC-cycle keys, inflows **$2,071,627.03**, of which **$1,502,770.63** reaches roster members (including the §3.3 Salazar fix). Verified on single-beneficiary JFCs, where the rule returns 100% (e.g. `JOHNSON LEADERSHIP FUND` 2024 $62,042.98 → Mike Johnson 100%).
- **Non-roster JFCs** (presidential JFCs, lost/retired candidates, no roster match): 38 keys, **$6,939,958.48** — including `HARRIS VICTORY FUND` 2024 $3,360,153.47, `TRUMP 47 COMMITTEE` $361,500, `TRUMP SAVE AMERICA` $141,510.09. Plus need-pull inflows whose outflow shares go entirely to non-roster candidates ($568,856.40 after the Salazar fix). **Unmapped:** $1,800 (`MONICA TRANEL VICTORY FUND` — full name matches no roster person; first-name-only rule correctly refuses it, since Tranel is not in Congress, unlike Monica De La Cruz).
- **AIPAC vs other-conduit split for outflow shares:** each share is split across spenders pro-rata to that JFC's inflow by spender (the JFC's outflows are funded pro-rata by all its inflows). This is an allocation rule, stated as such — the FEC record does not tag outflows by funding source.

### 3.3 Three classifier bugs found and fixed in this session

**Bug 1 — pas2 fallback included non-24K rows (fixed before v3).** The first pas2 name→candidate map included every pas2 row type, so vendor names mapped to candidates (e.g. UDP → `FIRST NATIONAL BANK OF OMAHA` $45,204.66 in 2026 / $79,971.04 in 2024 was mapped to a candidate via filer-miscoded pas2 rows, and `SCALE TO WIN` vendor rows likewise). Root cause: pas2 contains filer-miscoded operating expenditures reported as 24K — e.g. a SUNRUN PAC row with recipient_name `NRCC` but `other_id` C00213512 = NANCY PELOSI FOR CONGRESS. Fix: fallback restricted to 24K/24P rows plus the surname-token rule; the outfile script's pas2 fallback was also fixed to respect a cm hit first (it had misattributed NRCC's $40,082,460.35 outflow from GROW THE MAJORITY to Nancy Pelosi).

**Bug 2 — by_recipient `total` is non-memo only (characterized, not a bug in the classifier).** `by_recipient` returns `total` and `memo_total` separately; `total` excludes memo-coded rows. Verified: JACPAC → `SCHNEIDER FOR CONGRESS` 2026 has 17 memo-X earmark rows ($12,925, all `EARMARKED THROUGH ACTBLUE CONDUIT-…`) plus 1 non-memo row ($1,500); by_recipient reports total=$1,500, memo_total=$12,925, and raw Schedule B sums to $14,425. The direct figures in this report are on the `total` (non-memo) basis, consistent with the Nov 13 live-direct figures. The memo layer is quantified separately in §4.4 ($2,393,323.26 across listed PACs, 2022–2026) and is a real additional layer of earmarked money, not double-counting: memo rows are conduit notifications of donor money transmitted, distinct transactions from the non-memo rows.

**Bug 3 — committee-master name collisions, last-wins (found 2026-11-25; $1,149,551.63 fixed).** `load_cm()` built `{normalized_name: (cmte_id, designation, cand_id)}` with last-wins semantics. When two House candidates share a committee name, the last `cm.txt` row won and every by-recipient row under that name went to the wrong candidate. The audit found 48 by-recipient rows (across listed PACs and JFC outflow files) whose name maps to 2+ distinct candidate IDs, totalling $2,762,945.69. Every roster-relevant case was resolved from raw Schedule B (`committee_id` + `recipient_committee_id` + cycle — the narrow query works where the unfiltered Schedule B pull 504s), with residuals vs by_recipient of $0.00 except the memo cases in Bug 2. The fixes, all moved from non-roster to the roster member:

| Name | Correct owner (committee) | Amount moved | Evidence |
|---|---|---|---|
| `VARGAS FOR CONGRESS` | Juan Vargas, CA (C00497321) — AIPAC 2022 $55,600.00, 2024 $162,715.51, 2026 $133,244.48; DMFI 2022 $2,000 | **$353,560.00** | Schedule B: 52/153/141 rows, all to C00497321; Nebraska Vargas (C00784371, Tony Vargas) got $0 from AIPAC in all cycles |
| `MIKE ROGERS FOR CONGRESS` | Mike Rogers, AL (C00367862, H2AL03032) — AIPAC 2024 $516,823.10; NORPAC 2024 $7,500 | **$524,323.10** | Schedule B: all to C00367862; MD Rogers (C00857243) got $0 |
| `SCHNEIDER FOR CONGRESS` | Brad Schneider, IL (C00495952, H2IL10068) — 2022 only: AIPAC $72,601, NORPAC $15,200, JACPAC $2,500, DMFI $2,000 | **$92,301.00** | Schedule B: all to C00495952; FL Schneider (C00374751) got $0 (2024/2026 were already correct) |
| `SALAZAR FOR CONGRESS` | Maria Elvira Salazar, FL (C00714261, H8FL27185) — 2022: AIPAC $37,967, RJC $29,142.78 | **$67,109.78** | Schedule B: all to C00714261; TX Salazar (C00778373) got $0 |
| `CASE FOR CONGRESS` | Ed Case, HI (C00680918, H2HI02128) — AIPAC 2026 $32,168.82, 2024 $10,345.93 | **$42,514.75** | Schedule B: all to C00680918; GA Case (C00925107/C00864538) got $0 |
| `COURTNEY FOR CONGRESS` | Joe Courtney, CT (C00410233, H2CT02112) — AIPAC 2024 $27,222.92; J Street 2026 $12,836.29, 2024 $11,166.37 | **$51,225.58** | Schedule B: all to C00410233; TN Courtney got $0 |
| `LUCAS FOR CONGRESS` | Frank Lucas, OK (C00287912, H4OK06056) — AIPAC 2024 $10,567.43 | **$10,567.43** | Schedule B: all to C00287912; WV Lucas got $0 |
| `MOORE FOR CONGRESS` | Gwen Moore, WI (C00397505, H4WI04183) — J Street 2022 $4,450, 2024 $3,500 | **$7,950.00** | Schedule B: all to C00397505; NY Moore got $0 |
| `SALAZAR FOR CONGRESS` (JFC outflow) | Maria Salazar — TAKE BACK THE HOUSE 2022 outflow $174,636.97 was classified non-roster (TX); it is all C00714261 | **JFC share +$500.01** | Schedule B: TAKE BACK THE HOUSE → C00714261 $174,636.97 (5 rows), TX $0 |

Two Vargas subtleties, for the record. (a) J Street's `VARGAS FOR CONGRESS` money (2024 $165,323.73; 2022 $42,260.82) went entirely to **Tony Vargas of Nebraska** (C00784371), not Juan — verified from raw Schedule B; the classifier's last-wins pick happened to be right there. One J Street 2024 row ($2,642.51, `TRAVEL, MEALS AND STAFF SALARY`) is J Street operating spending that happens to name the committee, and by_recipient correctly excludes it. (b) `JUAN CARLOS VARGAS FOR CONGRESS` (DMFI 2024, $2,000) is committee C00259705 with no candidate linkage — not Juan Vargas's committee (C00497321) — and stays non-roster. `TONY VARGAS FOR CONGRESS` is correctly non-roster throughout. The classifier now returns `ambiguous` (with every candidate and committee ID) instead of silently picking one when a name maps to 2+ distinct candidate IDs, so a future re-run fails safe rather than repeating Bug 3. Residual risk: a name with exactly one cm entry that points at the wrong candidate (a cm data error) would not be caught by this check; the pas2 cross-check is the backstop.

## 4. What the live API shows

### 4.1 Classification totals (listed PACs only, cycles 2022 + 2024 + 2026)

| Bucket | Amount | Note |
|---|---|---|
| Direct to candidate committees | **$154,705,627.17** | Of which roster-attributed **$132,388,344.65**; non-roster $22,317,282.52 |
| JFC (cm-confirmed + aliases) | **$12,673,597.53** | See reconciliation below |
| `jfc?` (name-pattern only) | $250.00 | One DJOPA 2024 row, Ritchie Torres Victory Fund |
| Other (party committees, super PACs, vendors, transfers) | $69,913,260.28 | Incl. UDP transfers to other committees and vendors; UDP has no JFC rows — its Schedule B is transfers/vendors, and its "direct" is only ~$45k–$80k/cycle once the bank-fee false directs were removed (Bug 1) |
| Unmatched | $27,882,050.81 | Mostly vendors/processors (Democracy Engine $5,627,557.75 across AIPAC cycles; Impact Research; Fidelity) and individuals (e.g. SCHLEIFER, HARRIET $550,500 from AIPAC 2024) |

**JFC reconciliation** ($12,673,847.53 = JFC + `jfc?`): name-attributed to one roster person **$3,660,462.02** + outflow-shared to roster members **$1,502,770.63** + non-roster/unmapped **$7,510,614.88** (incl. Harris Victory Fund 2024 $3,360,153.47; Trump 47 Committee $361,500; Trump Save America $141,510.09) + unmapped $1,800.00 (`MONICA TRANEL VICTORY FUND`). Non-roster includes need-pull inflows whose outflow shares go entirely to non-roster candidates (e.g. TEAM ROGERS 2026 $105,453 — its outflows go to `ROGERS FOR SENATE` $4,659,937.23, i.e. the **Michigan** Mike Rogers, 2024 Senate candidate, not the Alabama Rep. Mike Rogers in the dataset — a name-collision trap correctly handled; MICHIGAN VICTORY FUND 2026 $65,700 and DEMOCRATIC GRASSROOTS VICTORY FUND 2026 $65,600, whose outflows are vendors/parties only).

**Roster JFC totals by cycle:** 2022 **$40,899.05** (AIPAC $0; other $40,899.05); 2024 **$1,512,804.81** (AIPAC $91,350.00; other $1,421,454.81); 2026 **$3,609,528.79** (AIPAC $630,419.31; other $2,979,109.48). **Career roster JFC: $5,163,232.65** (AIPAC **$721,769.29**; other conduits **$4,441,463.36**).

**Roster API direct by cycle** (post-Bug-3 fix): 2022 **$18,718,381.16** (AIPAC $12,838,513.75; other $5,879,867.41); 2024 **$55,043,625.23** (AIPAC $46,120,050.91; other $8,923,574.32); 2026 **$58,626,338.26** (AIPAC $49,359,732.01; other $9,266,606.25). **Total 2022–2026: $132,388,344.65.**

**AIPAC PAC alone** (all recipients, not just roster): 2022 direct $17,087,589.67, JFC $0; 2024 direct $52,329,175.89, JFC $91,350.00; 2026 direct $50,543,858.48, JFC $671,800.00. AIPAC 2026 JFC rows: GROW THE MAJORITY $262,500; JEFFRIES VICTORY FUND $250,000; JEFFRIES BATTLEGROUND PROTECTION FUND $149,300; SUSAN COLLINS FOR MAINE $10,000.

**Big-conduit JFC totals:** J Street 2024 $3,915,548.79, 2026 $1,387,528.73, 2022 $61,860.00; RJC-PAC 2024 $1,370,820.51, 2026 $1,494,887.70, 2022 $92,611.80; NORPAC 2024 $576,160.00, 2026 $636,568.00; JACPAC 2024 $12,500, 2026 $22,000.

**Bulk-file cross-check (why the API is needed at all).** The pinned pas2 files carry **zero** AIPAC→JFC rows in 2024/2026 (all 1,311 AIPAC rows in pas2 2026 have a candidate ID; grep for VICTORY/JOINT recipients returned none), and JFC committee IDs appear nowhere in pas2 2024/2026 as contributors either — JFC→candidate transfers are not 24K/24P rows. So JFC money lives only in the live API. More broadly, pas2 2026 AIPAC rows sum only $2,708,055 raw vs live API direct $50.5M — pas2 captures ~5% of AIPAC's 2026 Schedule B. (The mechanism for the bulk gap is not established; reported as observed fact. Earmark rows in pas2 cluster oddly — 655 earmark rows in 2026, 529 dated Nov 2025; in 2024, 1,165 earmark rows, 1,113 dated Oct 2023 — consistent with re-reported earmarks, methodology §8 item 4.) The 4 `C900*` rows in `pro_israel_pacs.csv` are aliases of committees already pulled under their real FEC IDs (RJC, J Street, JDCA, DMFI) and contribute $0 in pas2 24K rows to roster candidates in 2024/2026, so no money is lost by excluding them from the API pulls.

### 4.2 Multi-candidate JFCs and the outflow-split rule (summary; full table in Appendix A)

- **GROW THE MAJORITY 2026** ($592,906.15 in; roster shares $499,439.99): top Mike Johnson $107,697.62, then Lawler, Ciscomani, Barrett, Begich, Evans, Valadao (~$16.5k–$19.3k each); 33 roster members. 2024 ($203,500; roster shares $104,884.43): top Mike Johnson $38,819.95.
- **DEFEND OUR MAJORITY 2026** ($205,000; roster shares $194,143.13): top Scalise $30,530.61, then Miller-Meeks $9,132.00, Begich $8,766.59, Bresnahan $8,690.17, Ciscomani $8,594.68, Barrett $8,525.43; 29 roster members.
- **TAKE BACK THE HOUSE 2022** ($60,000; roster shares $26,058.05 incl. the Salazar fix): 64 roster members, all small (top Van Orden $706.84, Turner $694.76, Calvert $690.24, Kean $671.05; Maria Salazar $500.01).
- **Zero-attribution (denominator $0 or no roster candidate outflow):** TEAM ROGERS 2026 ($105,453, Michigan Rogers — see §4.1), MICHIGAN VICTORY FUND 2026 ($65,700), DEMOCRATIC GRASSROOTS VICTORY FUND 2026 ($65,600), FISH FAMILY FREEDOM FUND 2026 ($32,500 → Alaskans for Mary Peltola, non-roster), SAM BROWN 2024 ($61,501), SCOTT BROWN 2026 ($221.85), MIKE GARCIA 2022 ($1,000) — all non-roster.
- **PUT ALASKA FIRST 2026 ($25,000): thin evidence — do NOT attribute on the outflow rule alone.** Its only candidate-committee outflow is $120 to Dan Sullivan, while $1,543,929.29 went to Crossroads Media LLC (ad buys) and $25,132.65 to the NRSC. Attributing the full $25,000 to Sullivan on a $120 outflow is not supportable. In the figures in this report the mechanical rule assigns it to Sullivan (his career JFC total $83,814.11 includes it), but the honest treatment is to mark it unattributed with this caveat; removing it changes no flag or clean count (Sullivan is flagged under both variants via direct money).
- **Single-beneficiary JFCs verified at 100%:** JOHNSON LEADERSHIP FUND → Mike Johnson (2024 $62,042.98; 2026 $11,611.73); TORRES VICTORY FUND → Ritchie Torres (2024 $24,800; 2026 $21,600); TEAM MCCORMICK → David McCormick (~100%: 2024 $69,962 of $70,000; 2026 $1,000); GOLDMAN VICTORY FUND → **Craig A. Goldman** $8,000 (not Daniel S. Goldman); COLLINS VICTORY COMMITTEE → Susan M. Collins 100% ($80,606.32); OHIO GRASSROOTS → Sherrod Brown ~100% (2024 $68,290.06 of $68,300; 2026 $301,734); DELUZIO STELSON → Stelson $502.79 / Deluzio $497.21; VAN HOLLEN OSSOFF → Ossoff $1,350.91 / Van Hollen $1,199.09; COOPER VICTORY FUND → Roy Cooper (outflows confirm: top recipient `COOPER FOR NORTH CAROLINA` $27,642,614.13).

### 4.3 What `by_recipient` totals do and do not include

- `total` is the sum of **non-memo** Schedule B rows (Bug 2). `memo_total` is reported separately. For AIPAC the memo layer is negligible (2026: $0; 2024: $22,000; 2022: $5,800).
- `total` **nets refunds**: rows with negative totals exist (72 of 734 AIPAC 2026 rows are ≤ $0), and the per-person direct figures here are net. Patrick Ryan's tracker pas2 figure is -$15,000 for 2026 (a refund/void row) while live API direct is +$138,538.15 — the Nov 13 note that Ryan is clean on the Sep 30 snapshot but not on live data is confirmed.
- The endpoint aggregates by recipient **name**, not committee ID — hence Bug 3. Where a name is shared, the split was resolved from raw Schedule B (see §3.3).
- The earmark-vs-own-money split is **not** derivable from `by_recipient`: it returns one total per recipient. The Schedule B descriptions (e.g. `EARMARK OF …`) show the JFC rows are earmark transmissions, but the direct rows cannot be split into earmarked vs PAC-own dollars from this endpoint. The trackers' `aipac_earmark_transmitted` concept (methodology §8 item 4) therefore cannot be rebuilt from `by_recipient` alone; raw Schedule B would be needed, and the unfiltered pull 504s.

### 4.4 The memo layer (excluded from the direct figures; quantified here)

Total `memo_total` across the 62 listed PACs, cycles 2022–2026: **$2,393,323.26** (674 rows with nonzero memo). Largest memo rows: NORPAC → `MENENDEZ FOR SENATE` 2024 $112,260.00; JDCA → itself 2022 $84,392.89; NORPAC → `LCV VICTORY FUND` 2026 $55,636.00; JDCA → `GUSTO` (vendor) 2024 $48,472.16 / 2026 $20,177.96; JACPAC → `WARNOCK FOR GEORGIA` 2022 $32,786.33; JACPAC → `FRIENDS OF SHERROD BROWN` 2024 $22,505.85; JACPAC → `TIM RYAN FOR OHIO` 2022 $24,315.00. Roster-relevant memo items include JACPAC → Schneider 2026 $12,925.00 and JACPAC → Dan Goldman 2026 $19,471.00. The memo layer is ~1.8% of roster direct ($132.4M) and does not change any variant comparison (memo earmarks are direct-to-candidate money under both variants); whether the re-derivation should add `memo_total` to the direct figures is a separate open question for the coordinator, not part of the JFC decision.

## 5. Per-member table: the ten comparison members

All dollars are live FEC API `by_recipient` totals (non-memo basis), fetched 2026-11-25, post-Bug-3 fix. `Tracker pas2` is the current dataset figure for the same cycle (`aipac_pac_direct` per cycle). `OS` is the OpenSecrets figure from the Nov 25 comparison report (2026 as of Oct 24, 2026; 2024 finalized). Variant A = direct + JFC; Variant B = direct only. Pro-Israel = AIPAC + the other 61 listed conduit PACs.

### Haley M. Stevens (MI House) — tracker pas2 career AIPAC $22,100.00; pro-Israel career $96,110.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $688,292.00 | $4,500.00 | $0.00 | $0.00 | $688,292.00 | $688,292.00 | $692,792.00 | $692,792.00 | $7,100.00 | — |
| 2024 | $100,744.93 | $4,500.00 | $0.00 | $0.00 | $100,744.93 | $100,744.93 | $105,244.93 | $105,244.93 | $10,000.00 | $47,100 |
| 2026 | $381,346.43 | $78,290.00 | $0.00 | $0.00 | $381,346.43 | $381,346.43 | $459,636.43 | $459,636.43 | $5,000.00 | $302,156 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### Wesley Bell (MO House) — tracker pas2 career AIPAC $25,000.00; pro-Israel career $65,650.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | — |
| 2024 | $3,170,853.03 | $30,500.00 | $0.00 | $0.00 | $3,170,853.03 | $3,170,853.03 | $3,201,353.03 | $3,201,353.03 | $10,000.00 | $2,555,095 |
| 2026 | $2,301,963.42 | $14,800.00 | $0.00 | $0.00 | $2,301,963.42 | $2,301,963.42 | $2,316,763.42 | $2,316,763.42 | $15,000.00 | $3,073,802 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### Josh Gottheimer (NJ House) — tracker pas2 career AIPAC $93,630.00; pro-Israel career $301,617.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $222,015.00 | $87,183.00 | $0.00 | $0.00 | $222,015.00 | $222,015.00 | $309,198.00 | $309,198.00 | $7,900.00 | — |
| 2024 | $860,536.99 | $105,450.00 | $0.00 | $0.00 | $860,536.99 | $860,536.99 | $965,986.99 | $965,986.99 | $10,000.00 | $797,189 |
| 2026 | $810,090.17 | $36,240.00 | $0.00 | $0.00 | $810,090.17 | $810,090.17 | $846,330.17 | $846,330.17 | $75,730.00 | $1,049,267 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### George Latimer (NY House) — tracker pas2 career AIPAC $20,000.00; pro-Israel career $69,800.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | — |
| 2024 | $2,818,638.95 | $76,100.00 | $0.00 | $0.00 | $2,818,638.95 | $2,818,638.95 | $2,894,738.95 | $2,894,738.95 | $10,000.00 | $2,448,899 |
| 2026 | $94,333.40 | $0.00 | $0.00 | $0.00 | $94,333.40 | $94,333.40 | $94,333.40 | $94,333.40 | $10,000.00 | < $155,955 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### Susan M. Collins (ME Senate) — tracker pas2 career AIPAC $10,000.00; pro-Israel career $235,167.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | — |
| 2024 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | n/a |
| 2026 | $3,358,020.18 | $206,453.05 | $10,000.00 | $80,606.32 | $3,368,020.18 | $3,358,020.18 | $3,655,079.55 | $3,564,473.23 | $10,000.00 | $2,786,964 |
| **Career JFC (2022–2026)** | | | **$10,000.00** | **$80,606.32** | | | | | | |

### Adrian Boafo (MD House) — tracker pas2 career AIPAC $0.00; pro-Israel career $16,000.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | — |
| 2024 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | n/a |
| 2026 | $0.00 | $16,000.00 | $0.00 | $0.00 | $0.00 | $0.00 | $16,000.00 | $16,000.00 | $0.00 | $0 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### Pete Aguilar (CA House) — tracker pas2 career AIPAC $17,900.00; pro-Israel career $62,535.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $100,850.00 | $15,665.00 | $0.00 | $0.00 | $100,850.00 | $100,850.00 | $116,515.00 | $116,515.00 | $7,900.00 | — |
| 2024 | $621,674.43 | $48,510.00 | $0.00 | $0.00 | $621,674.43 | $621,674.43 | $670,184.43 | $670,184.43 | $5,000.00 | $620,898 |
| 2026 | $605,985.82 | $18,250.00 | $0.00 | $0.00 | $605,985.82 | $605,985.82 | $624,235.82 | $624,235.82 | $5,000.00 | $1,008,800 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### Hakeem S. Jeffries (NY House) — tracker pas2 career AIPAC $11,700.00; pro-Israel career $82,600.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $72,895.00 | $99,000.00 | $0.00 | $0.00 | $72,895.00 | $72,895.00 | $171,895.00 | $171,895.00 | $4,200.00 | — |
| 2024 | $939,360.14 | $54,600.00 | $91,350.00 | $8,300.00 | $1,030,710.14 | $939,360.14 | $1,093,610.14 | $993,960.14 | $7,500.00 | $866,425 |
| 2026 | $22,095.99 | $16,875.00 | $399,300.00 | $79,000.00 | $421,395.99 | $22,095.99 | $517,270.99 | $38,970.99 | $0.00 | < $155,955 |
| **Career JFC (2022–2026)** | | | **$490,650.00** | **$87,300.00** | | | | | | |

### Mark R. Warner (VA Senate) — tracker pas2 career AIPAC $5,000.00; pro-Israel career $119,400.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | — |
| 2024 | $0.00 | $15,700.00 | $0.00 | $0.00 | $0.00 | $0.00 | $15,700.00 | $15,700.00 | $0.00 | n/a |
| 2026 | $671,736.18 | $0.00 | $0.00 | $0.00 | $671,736.18 | $671,736.18 | $671,736.18 | $671,736.18 | $5,000.00 | $665,473 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$0.00** | | | | | | |

### John Fetterman (PA Senate) — tracker pas2 career AIPAC $0.00; pro-Israel career $32,381.00

| Cycle | API direct AIPAC | API direct other | JFC AIPAC | JFC other | Var A AIPAC | Var B AIPAC | Var A pro-Isr | Var B pro-Isr | Tracker pas2 AIPAC | OS AIPAC |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | $0.00 | $224,125.26 | $0.00 | $0.00 | $0.00 | $0.00 | $224,125.26 | $224,125.26 | $0.00 | — |
| 2024 | $0.00 | $12,636.00 | $0.00 | $500.00 | $0.00 | $0.00 | $13,136.00 | $12,636.00 | $0.00 | n/a |
| 2026 | $0.00 | $3,000.00 | $0.00 | $25,000.00 | $0.00 | $0.00 | $28,000.00 | $3,000.00 | $0.00 | $0 |
| **Career JFC (2022–2026)** | | | **$0.00** | **$25,500.00** | | | | | | |

Reading the table: for seven members (Stevens, Bell, Gottheimer, Latimer, Boafo, Aguilar, Warner) the JFC columns are $0.00 in every cycle, so Variants A and B are identical for them. The only members where the variants differ are **Jeffries** (2026: A $421,395.99 vs B $22,095.99 AIPAC; 2024: A $1,030,710.14 vs B $939,360.14), **Collins** (2026: A $3,368,020.18 vs B $3,358,020.18 AIPAC; pro-Israel A $3,655,079.55 vs B $3,564,473.23) and **Fetterman** (2026 pro-Israel A $28,000 vs B $3,000; 2024 A $13,136 vs B $12,636 — all of it non-AIPAC conduits, so his AIPAC column never moves). Note Gottheimer's 2026 live direct AIPAC is **$810,090.17**, not the $398,164 in the Nov 13 report: his committee files under two names, `JOSH GOTTHEIMER FOR CONGRESS` ($398,164.03) and `JOSH FOR JERSEY` ($411,926.14, committee C00573949), and Nov 13 counted only the first. See §8.

## 6. Roster-wide: every member with career JFC over $10,000

Career JFC (2022–2026, AIPAC + other listed conduits, name-attributed + outflow-shared). Multi-candidate JFC shares are modeled attributions (outflow-split rule, §3.2), not directly observed per-member receipts. 73 members clear $10,000. Darline Graham (appointed SC Senator, served Jul 14, 2026–Jan 3, 2027; in the 119th, not the 120th) is the roster's only Graham — the `GRAHAM MAJORITY FUND` ($267,686.19) attributes to her row; Lindsey Graham is not in the dataset roster (see §10).

| Career JFC | Member | AIPAC-JFC | Other-JFC |
|---|---|---|---|
| $577,950.00 | Hakeem S. Jeffries (NY House) | $490,650.00 | $87,300.00 |
| $394,575.14 | Jon Ossoff (GA Senate) | $0.00 | $394,575.14 |
| $370,024.06 | Sherrod Brown (OH Senate) | $0.00 | $370,024.06 |
| $267,686.19 | Darline Graham (SC Senate) | $0.00 | $267,686.19 |
| $220,172.28 | Mike Johnson (LA House) | $47,681.45 | $172,490.83 |
| $201,500.00 | Bernie Moreno (OH Senate) | $0.00 | $201,500.00 |
| $190,750.00 | Katherine M. Clark (MA House) | $0.00 | $190,750.00 |
| $184,955.77 | Elise M. Stefanik (NY House) | $0.00 | $184,955.77 |
| $173,550.00 | Ted Cruz (TX Senate) | $0.00 | $173,550.00 |
| $172,038.00 | Roy Cooper (NC Senate) | $0.00 | $172,038.00 |
| $169,670.08 | Michael Lawler (NY House) | $7,199.36 | $162,470.72 |
| $122,520.00 | Tom Emmer (MN House) | $0.00 | $122,520.00 |
| $113,840.48 | Randy Fine (FL House) | $0.00 | $113,840.48 |
| $90,606.32 | Susan M. Collins (ME Senate) | $10,000.00 | $80,606.32 |
| $83,814.11 | Dan Sullivan (AK Senate) | $0.00 | $83,814.11 |
| $72,888.95 | Thomas H. Kean, Jr. (NJ House) | $6,709.25 | $66,179.70 |
| $70,962.00 | David McCormick (PA Senate) | $0.00 | $70,962.00 |
| $70,300.00 | Guy Reschenthaler (PA House) | $0.00 | $70,300.00 |
| $67,089.11 | Ashley Hinson (IA House) | $0.00 | $67,089.11 |
| $63,879.70 | Tammy Baldwin (WI Senate) | $0.00 | $63,879.70 |
| $60,130.00 | Josh Turek (IA Senate) | $0.00 | $60,130.00 |
| $51,200.00 | Colin Allred (TX House) | $0.00 | $51,200.00 |
| $47,079.80 | Ashley Moody (FL Senate) | $0.00 | $47,079.80 |
| $46,650.00 | Ritchie Torres (NY House) | $0.00 | $46,650.00 |
| $42,994.25 | Tom Cotton (AR Senate) | $0.00 | $42,994.25 |
| $41,500.00 | Angela D. Alsobrooks (MD Senate) | $0.00 | $41,500.00 |
| $41,001.00 | Lisa C. McClain (MI House) | $0.00 | $41,001.00 |
| $39,488.99 | Tom Barrett (MI House) | $7,592.95 | $31,896.04 |
| $38,600.00 | Tim Sheehy (MT Senate) | $0.00 | $38,600.00 |
| $35,787.50 | Christina Bohannan (IA House) | $0.00 | $35,787.50 |
| $35,531.61 | Steve Scalise (LA House) | $0.00 | $35,531.61 |
| $31,904.76 | Juan Ciscomani (AZ House) | $7,677.91 | $24,226.85 |
| $31,600.00 | Rick Scott (FL Senate) | $0.00 | $31,600.00 |
| $30,038.56 | Gabe Evans (CO House) | $7,343.46 | $22,695.10 |
| $28,502.49 | Robert P. Bresnahan, Jr. (PA House) | $6,366.93 | $22,135.56 |
| $27,603.31 | David G. Valadao (CA House) | $7,340.31 | $20,263.00 |
| $27,598.32 | John Cornyn (TX Senate) | $0.00 | $27,598.32 |
| $27,363.14 | Nicholas J. Begich III (AK House) | $7,410.93 | $19,952.21 |
| $26,890.73 | Ken Calvert (CA House) | $4,002.50 | $22,888.23 |
| $26,751.22 | Derrick Van Orden (WI House) | $6,791.20 | $19,960.02 |
| $26,749.72 | Jennifer A. Kiggans (VA House) | $7,026.38 | $19,723.34 |
| $26,558.53 | Ryan Mackenzie (PA House) | $7,032.17 | $19,526.36 |
| $26,248.65 | Zachary Nunn (IA House) | $6,903.86 | $19,344.79 |
| $25,500.00 | John Fetterman (PA Senate) | $0.00 | $25,500.00 |
| $25,485.06 | Mariannette Miller-Meeks (IA House) | $7,026.38 | $18,458.68 |
| $25,000.00 | Deb Fischer (NE Senate) | $0.00 | $25,000.00 |
| $25,000.00 | Mike Rogers (AL House) | $0.00 | $25,000.00 |
| $25,000.00 | Jon Husted (OH Senate) | $0.00 | $25,000.00 |
| $23,317.64 | Juan Vargas (CA House) | $0.00 | $23,317.64 |
| $22,139.24 | Nick LaLota (NY House) | $5,211.95 | $16,927.29 |
| $21,217.64 | Sharice Davids (KS House) | $0.00 | $21,217.64 |
| $19,870.54 | Jeff Hurd (CO House) | $5,110.01 | $14,760.53 |
| $19,356.97 | Scott Perry (PA House) | $6,551.68 | $12,805.29 |
| $19,084.58 | Brian K. Fitzpatrick (PA House) | $7,130.51 | $11,954.07 |
| $18,317.64 | John W. Mannion (NY House) | $0.00 | $18,317.64 |
| $17,953.61 | Bryan Steil (WI House) | $5,047.03 | $12,906.58 |
| $17,196.79 | Young Kim (CA House) | $4,501.94 | $12,694.85 |
| $17,112.26 | Ryan K. Zinke (MT House) | $3,705.12 | $13,407.14 |
| $16,866.30 | Kurt Alme (MT Senate) | $0.00 | $16,866.30 |
| $16,750.00 | Derek Tran (CA House) | $0.00 | $16,750.00 |
| $15,880.00 | Bobby Pulido (TX House) | $0.00 | $15,880.00 |
| $14,437.61 | Bill Huizenga (MI House) | $6,116.67 | $8,320.94 |
| $14,256.06 | Monica De La Cruz (TX House) | $4,910.10 | $9,345.96 |
| $13,762.65 | John James (MI House) | $1,125.40 | $12,637.25 |
| $13,261.94 | David Schweikert (AZ House) | $2,769.24 | $10,492.70 |
| $12,046.06 | Robert J. Wittman (VA House) | $5,333.21 | $6,712.85 |
| $12,000.00 | Pete Ricketts (NE Senate) | $0.00 | $12,000.00 |
| $11,882.71 | Kevin Kiley (CA House) | $5,215.53 | $6,667.18 |
| $11,171.13 | Don Bacon (NE House) | $2,127.88 | $9,043.25 |
| $10,965.20 | Elijah Crane (AZ House) | $4,694.08 | $6,271.12 |
| $10,936.65 | Brian Jack (GA House) | $0.00 | $10,936.65 |
| $10,241.20 | Max L. Miller (OH House) | $0.00 | $10,241.20 |
| $10,050.00 | Catherine Cortez Masto (NV Senate) | $0.00 | $10,050.00 |

Count over $10,000: **73**. The full per-person JFC file (all members, all cycles, including below-threshold members such as Maria Salazar at $500.01) is `~/workspace/tmp-jfc/jfc_per_person.json`.

## 7. Roster-wide effect of each variant

How the counts were recomputed: for each dataset row, the per-cycle `aipac_direct` in the stored `cycles` records was replaced per variant and `dirty`, the AIPAC/UDP flag, `clean` and both tiers were recomputed with the repo's own functions (`receipts/domain/clean_2026.py`: `verdict`, `tier`, `aipac_udp_flagged`; `receipts/domain/term.py`: `term_record`), with linkage and unopposed flags carried from the stored records. Headline-term records sum cycle records from `verdict_cycle` onward, per methodology §14b. Career totals replace the pas2 2022/2024/2026 per-cycle figures with the API figures (pre-2022 pas2 money is carried over unchanged: for AIPAC that remainder is $0.00 — all $7,567,773 of pas2 AIPAC direct sits in 2022/2024/2026 — while for pro-Israel it is $10,407,859 of the $25,417,511 career total). **Verification:** recomputing the baseline this way reproduces `data/source/baseline.json` exactly — 2026-cycle flag 231, headline-term flag 270, Strict clean 83 (2026) / 79 (term), Balanced not-dirty 201 / 183, Lenient not-dirty 253 / 224, `site.clean.all_120` 79.

Definitions: **Baseline** = current dataset (pas2). **B** = Base 2 Variant B: per-cycle AIPAC direct replaced by live-API direct, JFC excluded. **A** = Base 2 Variant A: live-API direct + JFC. **A1** = Base 1 Variant A: JFC added to the pas2 base, API direct *not* substituted (so A1 vs baseline isolates the JFC decision on the current data). There is no Base-1 Variant B distinct from the baseline. Flag = any AIPAC direct dollar or UDP benefit dollar in the window (every preset). Strict clean = `dirty <= 0`. Not-dirty = tier `clean` or `below_threshold`.

### 7.1 The 120th Congress (n = 535)

| Variant | 2026-cycle flag | Headline-term flag | Strict clean (2026 / term) | Balanced not-dirty (2026 / term) | Lenient not-dirty (2026 / term) | `aipac_direct` career | `pro_israel_pac_career` |
|---|---|---|---|---|---|---|---|
| Baseline (pas2) | 231 | 270 | 83 / 79 | 201 / 183 | 253 / 224 | $5,955,560.00 | $19,140,251.00 |
| B — API direct, JFC excluded | 256 | 297 | 81 / 77 | 191 / 172 | 236 / 205 | $81,285,424.83 | $109,519,849.64 |
| A — API direct + JFC | 258 | 299 | 81 / 77 | 189 / 170 | 234 / 203 | $81,850,056.24 | $113,164,014.18 |
| A1 — JFC on pas2 base | 235 | 274 | 83 / 79 | 198 / 180 | 249 / 220 | $6,520,191.41 | $22,784,415.54 |

**The JFC decision, isolated (A − B, API-corrected base):** flag +2 (2026-cycle 256 → 258; headline-term 297 → 299); Strict clean ±0 (81 / 77 both); Balanced not-dirty −2 (191 → 189 in-cycle; 172 → 170 term); Lenient not-dirty −2 (236 → 234; 205 → 203); `aipac_direct` career +$564,631.41 ($81,285,424.83 → $81,850,056.24); `pro_israel_pac_career` +$3,644,164.54 ($109,519,849.64 → $113,164,014.18). **The JFC decision, isolated on the pas2 base (A1 − baseline):** flag +4 (231 → 235 in-cycle; 270 → 274 term); Strict clean ±0 (83 / 79 both); Balanced not-dirty −3 (201 → 198; 183 → 180); Lenient −4 (253 → 249; 224 → 220); `aipac_direct` career +$564,631.41 ($5,955,560.00 → $6,520,191.41); pro-Israel +$3,644,164.54 ($19,140,251.00 → $22,784,415.54). The career deltas are the same under both bases, as they must be — the JFC money is the same money; only the base it is added to differs.

**The API correction, isolated (B − baseline):** flag +25 in-cycle (231 → 256) and +27 term (270 → 297); Strict clean −2 (83 → 81; 79 → 77); Balanced not-dirty −10 / −11; Lenient −17 / −19; `aipac_direct` career +$75,329,864.83; pro-Israel +$90,379,598.64. The API correction is roughly **130×** the JFC decision on the AIPAC career total and **25×** on the pro-Israel career total.

### 7.2 All roster rows (n = 664, 119th + 120th)

| Variant | 2026-cycle flag | Headline-term flag | Strict clean (2026 / term) | Balanced not-dirty (2026 / term) | Lenient not-dirty (2026 / term) | `aipac_direct` career | `pro_israel_pac_career` |
|---|---|---|---|---|---|---|---|
| Baseline (pas2) | 291 | 330 | 97 / 92 | 254 / 235 | 314 / 284 | $7,567,773.00 | $25,417,511.00 |
| B — API direct, JFC excluded | 346 | 387 | 93 / 88 | 226 / 206 | 273 / 241 | $108,318,296.67 | $142,796,203.65 |
| A — API direct + JFC | 349 | 390 | 92 / 87 | 223 / 203 | 270 / 238 | $109,040,065.96 | $147,959,436.30 |
| A1 — JFC on pas2 base | 299 | 338 | 96 / 91 | 248 / 229 | 306 / 276 | $8,289,542.29 | $30,580,743.65 |

A − B across all rows: flag +3 (346 → 349 in-cycle; 387 → 390 term); Strict clean −1 (93 → 92; 88 → 87) — the extra member is Ryan K. Zinke (119th only, §7.3); Balanced not-dirty −3; Lenient −3; `aipac_direct` career +$721,769.29 ($108,318,296.67 → $109,040,065.96); pro-Israel +$5,163,232.65 ($142,796,203.65 → $147,959,436.30). A1 − baseline across all rows: flag +8; Strict clean −1; `aipac_direct` career +$721,769.29 ($7,567,773.00 → $8,289,542.29); pro-Israel +$5,163,232.65 ($25,417,511.00 → $30,580,743.65).

### 7.3 Who actually changes status

**A vs B (the JFC decision, API-corrected base), 120th — 2 members, both windows:**
- **Elijah Crane** (C001132, AZ House): 2026 AIPAC-JFC $4,694.08 (other-JFC $5,908.39; career JFC $10,965.20). 2026 corp $15,250, so he was already not-clean; he moves from below-threshold to dirty under both presets. No other AIPAC/UDP money in the window.
- **Paul LePage** (paullepagemehouse, ME House): 2026 AIPAC-JFC $3,179.12 (other-JFC $6,216.93; career JFC $9,396.05). 2026 corp $5,000, already not-clean; below-threshold → dirty under both presets.
**A1 vs baseline (the JFC decision on the pas2 base), 120th — 4 members:** Crane, LePage, plus **Hakeem Jeffries** (2026 AIPAC-JFC $399,300; pas2 2026 AIPAC $0, so the JFC money alone flags him on the old base — on the API base he is already flagged via $22,095.99 direct) and **Anna Paulina Luna** (2026 AIPAC-JFC from the GROW/DEFEND outflow shares; pas2 2026 AIPAC $0 — on the API base she is already flagged via $15,240.43 direct). Across all rows A1 adds Don Bacon, John James, David Schweikert and Ryan K. Zinke (all 119th-only).
**B vs baseline (the API correction alone), 120th — 25 members newly flagged in the 2026 cycle:** Kurt Alme ($21,000.00 AIPAC direct 2026), Sanford D. Bishop Jr. ($6.02), Ed Case ($32,168.82), John Cowan ($21,200.00), Rosa L. DeLauro ($1,472.82), Sarah Elfreth ($5,071.31), Shomari Figures ($500.00), Harriet M. Hageman ($49.36), John W. Hickenlooper ($319,743.52), Hakeem S. Jeffries ($22,095.99), William R. Keating ($422.81), Mike Kennedy ($796.85), Anna Paulina Luna ($15,240.43), Seth Magaziner ($7,572.82), Chris McGowan ($1,000.00), John J. McGuire III ($33,353.77), Barry Moore ($513.43), Richard E. Neal ($1,524.81), Scott H. Peters ($539.52), Mike Quigley ($3,012.43), Pete Ricketts ($205,037.17), Deborah K. Ross ($3,100.00), Patrick Ryan ($138,538.15), Greg Stanton ($111,764.83), Marlin A. Stutzman ($25,077.77). Term-window additions: the same 25 plus Jim Banks (2024 AIPAC direct $227,602.42; verdict cycle 2024) and Maria Cantwell (2024 $316,208.48; verdict cycle 2024). Note the any-dollar flag rule at work: Bishop flags on **$6.02** and Hageman on **$49.36** of net 2026 AIPAC direct. That is the existing rule (any AIPAC dollar flags under every preset), not a JFC artifact — but the API correction exposes it at scale, and the coordinator should expect questions about sub-$100 flags. Full list with amounts in Appendix B.
**One member's flag is removed by the API correction: Juan Vargas.** His pas2 AIPAC figures ($7,900 in 2022, $10,000 in 2024, $10,000 in 2026) are 24K rows in the pinned bulk files, but the live API shows his AIPAC direct as $55,600.00 (2022) / $162,715.51 (2024) / $133,244.48 (2026) — the pas2 rows are a small, stale subset (including a -$6.00 void row and a $0.00 void row for a refunded Howard Welinsky earmark, dated Nov 2025). With the Bug-3 fix he stays flagged under both variants; the v3 (pre-fix) recount had briefly shown him flipping to unflagged, which was the collision bug, not the data.

## 8. The OpenSecrets correction — the "JFC gap" is not JFCs

The Nov 13 report (§2d) and the Nov 25 comparison (§8 rec. 2) said the OpenSecrets-vs-live gaps for Bell ($771,839), Gottheimer ($651,103) and Aguilar ($402,814) "are JFCs" — OpenSecrets counts earmarks to a candidate's JFCs, the tracker's live-direct figure does not. That claim is wrong, and the FEC record refutes it twice over.

**Leg 1 — the disbursements do not exist.** No listed conduit disbursed one dollar to any JFC for Bell, Gottheimer or Aguilar in any cycle 2022–2026 (checked in the live `by_recipient` pulls for all 62 listed PACs, plus the committee master). Bell has **no JFC at all** in the FEC record — `cm26` and `cm24` contain no Bell joint fundraising committee (the only similar name is `ASHLEY BELL VICTORY FUND`, a different Bell). Gottheimer *has* JFCs in cm (`GOTTHEIMER VICTORY FUND` C00851048 in 2024; `GOTTHEIMER HORSFORD VICTORY FUND`) and Aguilar has several (`AGUILAR LEADERSHIP FUND`; `JEFFRIES CLARK AGUILAR VICTORY FUND`; `AGUILAR HOUSE MAJORITY FUND`) — but AIPAC's `by_recipient` shows **zero** disbursements to any of them in 2024/2026, and no other listed conduit's pull shows any either. Their OpenSecrets gaps therefore cannot be AIPAC→JFC Schedule B disbursements.

**Leg 2 — where JFC disbursements do exist, OpenSecrets does not show them.** Jeffries's 2026 AIPAC→JFC earmarks total $399,300: `JEFFRIES VICTORY FUND` $250,000 (20 earmark rows, all dated **2025-02-27**, e.g. `EARMARK OF SANDRA WULIGER`) and `JEFFRIES BATTLEGROUND PROTECTION FUND` $149,300 (2 rows, dated **2026-05-20**, `EARMARK OF DANIEL OCH`). Both predate OpenSecrets' Oct 24, 2026 cutoff by 5–20 months. If OpenSecrets counted JFC earmarks, Jeffries's 2026 OS figure would be at least $399,300 + $22,096 direct ≈ $421,396 — far above the $155,955 NY top-10 threshold. Instead OS shows him **below $155,955** (not in the NY top 10). OpenSecrets does not count these earmarks. (His 2024 `JEFFRIES MAJORITY FUND` $91,350, dated 2024-06-12, is likewise absent from the OS 2024 picture relative to live direct: OS 2024 $866,425 vs live direct $939,360.14 — OS is *below* live direct, not above it.)

**The 2024 comparison points the same way.** For all six members with an OS 2024 figure, OS is at or *below* live direct — Bell $2,555,095 vs $3,170,853.03; Latimer $2,448,899 vs $2,818,638.95; Jeffries $866,425 vs $939,360.14; Gottheimer $797,189 vs $860,536.99; Aguilar $620,898 vs $621,674.43; Stevens $47,100 vs $100,744.93. There is no JFC-attribution excess in 2024 at all. OS's 2024 "From Individuals" split is the shape of the thing OS is counting — for Bell 2024, $2,550,095 from individuals + $5,000 from the organization (99.8% earmarked individuals) — but the mechanism by which OS associates those individuals with AIPAC is not established from the FEC record and is not asserted here.

**A correction inside the correction — Gottheimer's live figure.** The Nov 13 report's live direct for Gottheimer 2026 ($398,164) counted only `JOSH GOTTHEIMER FOR CONGRESS` ($398,164.03). His committee also files as `JOSH FOR JERSEY` (C00573949, $411,926.14 in AIPAC's 2026 by_recipient). Correct live direct 2026 is **$810,090.17**, so the OS gap is **$239,176.83** ($1,049,267 − $810,090.17), not $651,103. The tracker's pas2-based figure already sums both names by candidate ID, so this was a live-pull matching miss, not a tracker error.

**What the gaps are, then — honestly unknown.** The remaining 2026 gaps (Bell +$771,839; Gottheimer +$239,177; Aguilar +$402,814; OS above live direct) have no Schedule B mechanism in the FEC record: no JFC disbursements, no direct disbursements beyond the live totals, and (for Jeffries) positive proof OS ignores known JFC earmarks. Leading hypotheses, stated as hypotheses: OS counts bundled individual contributions delivered to the candidate's committee that never pass through AIPAC's Schedule B; OS attributes individual donors to AIPAC by donor overlap (people who gave to AIPAC's PAC and also to the candidate); or OS cycle-attribution differences (its 2026 data is Oct 24, live is Nov 25 — though that cuts the wrong way for Bell/Gottheimer/Aguilar, where later filings should raise live, not lower it). The re-derivation should **not** treat OpenSecrets' state-page figures as the JFC ground truth, and methodology §8 should stop saying the Bell gap "is JFCs". The OS comparison remains useful as an independent check that the tracker is in the right order of magnitude — it is not a line-item reconciliation target.

## 9. The open decision

**Question for Craig: in the square-one re-derivation, do JFC earmarks count as AIPAC direct (Variant A) or not (Variant B)?**

What each variant means, in one line each:

- **Variant A** says: money a conduit bundled and transmitted to a candidate's joint fundraising vehicle is money the candidate's operation received because of that conduit, so it counts — the same logic the tracker already applies to earmarks transmitted directly to the candidate's authorized committee. It is the more complete measure of conduit influence, and it is the only variant under which Jeffries's $399,300 (2026) and $490,650 (career) of AIPAC→JFC money appears in his AIPAC column.
- **Variant B** says: a JFC is not the candidate's committee — it is a joint vehicle whose money is split among beneficiaries (candidate, party, other candidates), so attributing the full inflow to one candidate overstates what that candidate received, and the cleanest auditable rule is to count only disbursements to the candidate's own authorized committee. It is the more conservative, more defensible-against-challenge measure, and it is the variant under which the tracker never has to defend a modeled attribution (the outflow split) as if it were an observed receipt.

Facts that bear on the choice (not a recommendation):

1. **The numerical stakes are small.** A vs B moves 2 of 535 flags, 0 Strict-clean verdicts, and 2 not-dirty verdicts per preset in the 120th; $564,631 on an $81.3M AIPAC career total. The decision will not change the tracker's headline story, which is driven by the API correction (§7).
2. **The stakes are methodological, not numerical.** Whichever variant is chosen, the methodology must state it explicitly (§14) and the site must show JFC money as its own broken-out column either way — the honest presentation is direct + JFC shown separately with the variant as the headline rule, so a reader can see both numbers. The worst outcome is a silent choice.
3. **The outflow-split attribution is the honest middle path for multi-candidate JFCs, but it is a model.** For the $2,071,627.03 in multi-candidate JFC inflows, no FEC row says how much each candidate got; the outflow split assumes the JFC's disbursements are funded pro-rata by its inflows. If Variant A is chosen, the methodology should say that plainly and the per-member JFC figures for Grow/Defend/Take-Back recipients should be labeled modeled, not observed.
4. **Only AIPAC-JFC money moves flags.** The $4,441,463.36 of other-conduit JFC money changes the pro-Israel career totals under A but cannot flag anyone, because the flag rule covers AIPAC direct and UDP benefit only. If the re-derivation ever extends the flag rule to pro-Israel PAC money generally, that asymmetry disappears and the JFC decision gets bigger — worth deciding now whether the flag stays AIPAC+UDP-only.
5. **Pre-2022 JFC money is unquantified under both variants.** The API pulls cover 2022–2026; pas2 carries no JFC rows in any cycle. A member whose JFC money predates 2022 is understated under both variants. If Craig wants career JFC figures to be complete, that is a separate pull (pre-2022 cycles via the same by_recipient route).
6. **The memo layer is a separate decision.** `memo_total` ($2,393,323.26 across listed PACs, §4.4) is excluded from both variants' direct figures. If the re-derivation adds memo earmarks to direct, that is a second, independent call — do not let it get folded into the JFC decision silently.

## 10. Limitations and open items

- **Pre-2022 JFC earmarks are unquantified.** API pulls cover cycles 2022, 2024, 2026 only. Career JFC totals are therefore 2022–2026 totals, not full careers. (For AIPAC direct this does not matter — all pas2 AIPAC direct is 2022–2026 — but JFCs existed before 2022.)
- **Outflow-split shares are modeled, not observed.** See §3.2 and §9 point 3. The largest modeled amounts are the Grow/Defend/Take-Back shares (§4.2, Appendix A).
- **PUT ALASKA FIRST 2026 ($25,000) is attributed to Dan Sullivan by the mechanical rule on a $120 outflow and should be treated as unattributed.** It changes no flag or clean count.
- **MONICA TRANEL VICTORY FUND $1,800 is unmapped.** No roster person matches; left unattributed.
- **Memo earmarks ($2,393,323.26) are excluded from direct figures in both variants.** See §4.4.
- **Earmark-vs-own-money split is not derivable from `by_recipient`.** See §4.3.
- **Name-collision residual risk.** Bug 3 was fixed for the 48 flagged rows; a name with exactly one cm entry pointing at the wrong candidate would not be caught. The largest remaining exposure is in the `unmatched` bucket ($27,882,050.81), which was audited for the big items only (vendors, individuals) — a JFC hiding there under a non-pattern name cannot be fully ruled out, though the cm designation-J check makes it unlikely: every committee with designation J in cm was classified JFC regardless of name.
- **Roster note: Darline Graham.** The dataset's only Graham row is G000608 `Darline Graham` (appointed SC Senator, term 2026-07-14–2027-01-03, in the 119th, not the 120th; source `data/source/legislators-current.yaml`, bioguide G000608). Lindsey Graham is not in the dataset roster. The $267,686.19 `GRAHAM MAJORITY FUND` attribution attaches to the Darline Graham row per the name rule; if the roster build intended a different Graham, the coordinator should say so — the JFC numbers are unaffected either way, only the name on the row.
- **Edge cases in the recount.** Brian Jack (J000311): $16.65 of API money in 2022 with no 2022 cycle record in the dataset — excluded from term sums, immaterial. Alan Armstrong (A000383): career AIPAC and pro-Israel figures are the string `'unknown'` in the dataset (one of the two null-unverified members); carried as unknown, excluded from career sums.
- **UDP.** UDP (C00799031) has no JFC rows and its "direct" is ~$45k–$80k/cycle after removing bank-fee false directs; its Schedule B is dominated by transfers to other committees and vendors. Nothing in this report changes the UDP treatment.
- **What this report does not cover.** Whether `memo_total` should be added to direct (§4.4); whether the flag rule should ever extend beyond AIPAC+UDP (§9 point 4); the December re-pull (methodology §8 item 22 — the AIPAC earmark gap is now measured, and the December bulk re-pull is the moment to apply the chosen variant).

## Appendix A. Multi-candidate JFCs: outflow-split detail

Every JFC that needed an outflow split (24 keys). `Inflow` is the listed-conduit money into the JFC in that cycle; `Denominator` is the JFC's same-cycle disbursements to candidate committees (roster + non-roster); `Roster share` is the inflow attributed to roster members by that split. Single-beneficiary JFCs (100% to one person) are omitted here; they are listed in §4.2.

| JFC (cycle) | Inflow | Denominator | Roster share | Top roster beneficiaries |
|---|---|---|---|---|
| GROW THE MAJORITY (2026) | $592,906.15 | $31,102,536.06 | $499,439.99 | Mike Johnson $107,697.62; Juan Ciscomani $17,342.02; Tom Barrett $17,150.11 |
| OHIO GRASSROOTS VICTORY FUND (2026) | $301,734.00 | $7,860,600.00 | $301,734.00 | Sherrod Brown $301,734.00 |
| DEFEND OUR MAJORITY (2026) | $205,000.00 | $8,765,441.80 | $194,143.13 | Steve Scalise $30,530.61; Mariannette Miller-Meeks $9,132.00; Nicholas J. Begich III $8,766.59 |
| GROW THE MAJORITY (2024) | $203,500.00 | $11,512,943.14 | $104,884.43 | Mike Johnson $38,819.95; Tom Barrett $6,478.07; Gabe Evans $5,607.31 |
| TEAM ROGERS (2026) | $105,453.00 | $4,659,937.23 | $0.00 | — |
| COLLINS VICTORY COMMITTEE (2026) | $80,606.32 | $3,927,289.71 | $80,606.32 | Susan M. Collins $80,606.32 |
| TEAM MCCORMICK (2024) | $70,000.00 | $4,605,690.58 | $70,000.00 | David McCormick $69,962.00; Eric Schmitt $38.00 |
| OHIO GRASSROOTS VICTORY FUND (2024) | $68,300.00 | $10,094,580.20 | $68,300.00 | Sherrod Brown $68,290.06; Christopher A. Coons $9.94 |
| MICHIGAN VICTORY FUND (2026) | $65,700.00 | $0.00 | $0.00 | — |
| DEMOCRATIC GRASSROOTS VICTORY FUND (2026) | $65,600.00 | $0.00 | $0.00 | — |
| JOHNSON LEADERSHIP FUND (2024) | $62,042.98 | $4,148,073.00 | $62,042.98 | Mike Johnson $62,042.98 |
| SAM BROWN VICTORY FUND (2024) | $61,501.00 | $1,008,820.89 | $0.00 | — |
| TAKE BACK THE HOUSE 2022 (2022) | $60,000.00 | $20,955,852.90 | $26,058.05 | Derrick Van Orden $706.84; Michael R. Turner $694.76; Ken Calvert $690.24 |
| FISH FAMILY FREEDOM FUND (2026) | $32,500.00 | $1,876,500.00 | $0.00 | — |
| PUT ALASKA FIRST (2026) | $25,000.00 | $120.00 | $25,000.00 | Dan Sullivan $25,000.00 |
| TORRES VICTORY FUND (2024) | $24,800.00 | $1,549,870.84 | $24,800.00 | Ritchie Torres $24,800.00 |
| TORRES VICTORY FUND (2026) | $21,600.00 | $2,846,067.94 | $21,600.00 | Ritchie Torres $21,600.00 |
| JOHNSON LEADERSHIP FUND (2026) | $11,611.73 | $2,799,165.72 | $11,611.73 | Mike Johnson $11,611.73 |
| GOLDMAN VICTORY FUND (2026) | $8,000.00 | $776,120.50 | $8,000.00 | Craig A. Goldman $8,000.00 |
| VAN HOLLEN OSSOFF VICTORY FUND (2026) | $2,550.00 | $236,515.26 | $2,550.00 | Jon Ossoff $1,350.91; Chris Van Hollen $1,199.09 |
| MIKE GARCIA VICTORY FUND (2022) | $1,000.00 | $337,104.70 | $0.00 | — |
| TEAM MCCORMICK (2026) | $1,000.00 | $1,924,652.82 | $1,000.00 | David McCormick $1,000.00 |
| DELUZIO STELSON VICTORY FUND (2024) | $1,000.00 | $102,194.43 | $1,000.00 | Janelle Stelson $502.79; Christopher R. Deluzio $497.21 |
| SCOTT BROWN VICTORY COMMITTEE (2026) | $221.85 | $628,338.22 | $0.00 | — |

Zero-denominator / zero-roster-share cases (inflow unattributed to any roster member): TEAM ROGERS 2026 $105,453.00; MICHIGAN VICTORY FUND 2026 $65,700.00; DEMOCRATIC GRASSROOTS VICTORY FUND 2026 $65,600.00; FISH FAMILY FREEDOM FUND 2026 $32,500.00; SAM BROWN 2024 $61,501.00; SCOTT BROWN 2026 $221.85; MIKE GARCIA 2022 $1,000.00. PUT ALASKA FIRST 2026 $25,000.00 is the thin-evidence case in §4.2 (denominator $120.00, mechanically assigned to Dan Sullivan).

## Appendix B. Members newly flagged by the API correction alone (Variant B vs baseline)

2026-cycle flags gained when pas2 AIPAC direct is replaced by live-API direct (JFC excluded). Amounts are 2026 live-API direct AIPAC; the tracker pas2 2026 figure was $0.00 for every member on this list except Patrick Ryan (-$15,000.00, a refund/void row).

| Member | 2026 AIPAC direct (live API) | 2026 other-conduit direct |
|---|---|---|
| John W. Hickenlooper (CO Senate) | $319,743.52 | $64,950.00 |
| Pete Ricketts (NE Senate) | $205,037.17 | $8,168.80 |
| Patrick Ryan (NY House) | $138,538.15 | $2,500.00 |
| Greg Stanton (AZ House) | $111,764.83 | $2,000.00 |
| John J. McGuire III (VA House) | $33,353.77 | $355.00 |
| Ed Case (HI House) | $32,168.82 | $0.00 |
| Marlin A. Stutzman (IN House) | $25,077.77 | $1,050.00 |
| Hakeem S. Jeffries (NY House) | $22,095.99 | $16,875.00 |
| John Cowan (GA House) | $21,200.00 | $5,000.00 |
| Kurt Alme (MT Senate) | $21,000.00 | $53,191.00 |
| Anna Paulina Luna (FL House) | $15,240.43 | $0.00 |
| Seth Magaziner (RI House) | $7,572.82 | $6,018.00 |
| Sarah Elfreth (MD House) | $5,071.31 | $0.00 |
| Deborah K. Ross (NC House) | $3,100.00 | $1,100.00 |
| Mike Quigley (IL House) | $3,012.43 | $6,000.00 |
| Richard E. Neal (MA House) | $1,524.81 | $2,602.00 |
| Rosa L. DeLauro (CT House) | $1,472.82 | $38,380.00 |
| Chris McGowan (IA House) | $1,000.00 | $0.00 |
| Mike Kennedy (UT House) | $796.85 | $0.00 |
| Scott H. Peters (CA House) | $539.52 | $2,325.00 |
| Barry Moore (AL Senate) | $513.43 | $4,000.00 |
| Shomari Figures (AL House) | $500.00 | $0.00 |
| William R. Keating (MA House) | $422.81 | $9,723.00 |
| Harriet M. Hageman (WY Senate) | $49.36 | $2,000.00 |
| Sanford D. Bishop, Jr. (GA House) | $6.02 | $0.00 |

Count: **25** in the 2026 cycle. Term-window additions (verdict cycle 2024): Jim Banks (2024 AIPAC direct $227,602.42) and Maria Cantwell (2024 $316,208.48).

## Appendix C. Reproduction notes

- **Evidence (raw API dumps):** `data/evidence/jfc-variants/by_recipient_<committee>_<cycle>.json` — 124 listed-PAC files (62 committees × 2024/2026) + AIPAC 2022 + 8 main conduits 2022 + 25 JFC outflow files. The `by_recipient` pulls used direct `curl` from this VM with `DEMO_KEY` only.
- **Analysis scripts (scratch, `~/workspace/tmp-jfc/`):** `classifier.py` (final; Bug 3 fail-safe), `analyze3.py` → `per_person_api3.json` (v4, post-Bug-3 fix; v3 backup `per_person_api3.json.v3.json`), `per_spender3.json` (v4; v3 backup likewise), `jfc_rows3.json`; `attribute4.py` → `jfc_attribution4.json`; `outflows4.py` → `jfc_outflow_shares4.json` (v4; includes the TBH2022 Salazar fix); `assemble.py` → `jfc_per_person.json`; `recount.py` → `recount_results.json` (baseline / A / B / A1). `collision_audit.py`, `resolve_collisions.py` → `collision_resolutions.json`; `fix_collisions.py` (the Bug-3 fix, with evidence per row).
- **Recount verification:** the baseline recomputation reproduces `data/source/baseline.json` exactly (§7). The recount replaces per-cycle `aipac_direct` only; corporate PAC, UDP, individual, total receipts, linkage and unopposed flags are carried from the stored records; pre-2022 cycles are untouched.
- **Known pre-existing data quirks encountered (not caused by this work):** Alan Armstrong's career AIPAC/pro-Israel figures are the string `'unknown'` in the dataset; Patrick Ryan's pas2 2026 AIPAC figure is -$15,000.00; the dataset roster has no Lindsey Graham row (see §10).
