# FEC data sources — verification & pull strategy

**Verified:** Thu Nov 12, 2026 (all live checks run this day; bulk-file sizes via `HEAD` on `fec.gov`).
**Scope:** career totals per person (all FEC cycles 1980–2026) for the Congress money tracker.
**Raw evidence saved in this directory:** `fec-aipac-committee.json`, `fec-aipac-name-search.json`, `fec-aipac-search.json`, `fec-udp-committee.json`, `fec-udp-search.json`, `fec-udp-schede.json`, `fec-candidate-totals-sample.json`, `fec-israel-names.json`, `fec-aipac-schedb.json` (contains a 504 timeout — see §5), plus sample downloads `weball26.zip` and `cm26.zip`.

---

## 1. Verified committee IDs

### AIPAC PAC — ✅ VERIFIED: `C00797670`

| Field | Value (from OpenFEC API, direct lookup `/v1/committee/C00797670/`) |
|---|---|
| Name | **AMERICAN ISRAEL PUBLIC AFFAIRS COMMITTEE POLITICAL ACTION COMMITTEE** |
| Committee ID | **C00797670** |
| Committee type | **Q — PAC - Qualified** |
| Designation | **B — Lobbyist/Registrant PAC** |
| Organization type | **M — Membership Organization** |
| Affiliated committee | AMERICAN ISRAEL PUBLIC AFFAIRS COMMITTEE |
| State / treasurer | DC / PHILLIPS, JUSTIN |
| First F1 filed | 2021-12-15 (the PAC was created Dec 2021) |
| API cycles with activity | **2022, 2024, 2026 only** |

**Consequence:** there are **no AIPAC PAC direct contributions before the 2022 cycle**. Career totals for AIPAC PAC = 2022 + 2024 + 2026 only. Any pre-2022 "AIPAC money" to a candidate came from other pro-Israel PACs, not this committee — do not backfill.

**Cross-check:** the same ID/name appears in the 2026 committee-master bulk file (`cm26.zip` → `cm.txt`):
`C00797670|AMERICAN ISRAEL PUBLIC AFFAIRS COMMITTEE POLITICAL ACTION COMMITTEE|PHILLIPS, JUSTIN|...|B|Q||M|M||`
(API search `q="American Israel Public Affairs"` returns exactly this one committee; `q="AIPAC"` alone does **not** return it — it returns only "Citizens Against AIPAC Corruption" C00879080 and "Reject AIPAC PAC" C00876649 — because the legal name contains no "AIPAC" token. Search by full legal name, not by acronym.)

**Related / not-to-conflate committees** (from `/v1/names/committees/?q=Israel` — separate pro-Israel PACs, NOT the AIPAC PAC):
- PRO-ISRAEL AMERICA PAC — C00699470 (inactive)
- DEMOCRATIC MAJORITY FOR ISRAEL — C90022864 (active)
- U.S. ISRAEL PAC (USI PAC) — C00127811 (active)
- FRIENDS OF ISRAEL PAC (FIPAC) — C00141747 (active)
- AMERICAN PRO-ISRAEL PAC — C00687657 (active)
- DEMOCRATS FOR ISRAEL LOS ANGELES FEDERAL PAC — C00761965 (active)
- EMERGENCY COMMITTEE FOR ISRAEL — C90013244 (active)
None of these is affiliated with the AIPAC PAC per the API (`affiliated_committee_name` for C00797670 is the AIPAC organization itself). Track them only if the project later decides to widen scope beyond AIPAC itself.

### United Democracy Project — ✅ VERIFIED: `C00799031`

| Field | Value (from OpenFEC API, direct lookup `/v1/committee/C00799031/`) |
|---|---|
| Name | **UNITED DEMOCRACY PROJECT ('UDP')** |
| Committee ID | **C00799031** |
| Committee type | **O — Super PAC (Independent Expenditure-Only)** |
| Designation | U — Unauthorized |
| Organization type | null (super PACs have no ORG_TP) |
| State / treasurer | DC / D'ALESSIO, CHRISTOPHER |
| First F1 filed | 2022-01-03 |
| API cycles | **2022, 2024, 2026** |

**Consequence:** UDP did not exist before 2022. Its independent expenditures only ever occur in 2022/2024/2026. Cross-checked in `cm26.zip` (`C00799031|UNITED DEMOCRACY PROJECT ('UDP')|...|U|O||M|||`).

**API smoke test:** `/v1/schedules/schedule_e/?committee_id=C00799031&two_year_transaction_period=2024` returned HTTP 200, pagination count **1,269** rows. ⚠️ Caveat: the first returned row was a **2026**-cycle expenditure (candidate EL-SAYED, ABDUL, S6MI00418) despite the `two_year_transaction_period=2024` parameter, so the period filter's behaviour on this endpoint is **not confirmed** — the pull agent must verify filtering (try `cycle=` / check `two_year_transaction_period` handling) before trusting a per-cycle API pull. Raw response saved as `fec-udp-schede.json` (first page only, `per_page=1`).

---

## 2. Corporate PAC definition — ORG_TP (committee master file)

Source: FEC, **Committee master file description** — https://www.fec.gov/campaign-finance-data/committee-master-file-description/ (fetched Nov 12, 2026). Field **ORG_TP, "Interest group category", position 13**:

> **C = Corporation · L = Labor organization · M = Membership organization · T = Trade association · V = Cooperative · W = Corporation without capital stock**

**Corporate-connected PAC = committee type Q or N AND ORG_TP C or W**, where the committee-type codes come from https://www.fec.gov/campaign-finance-data/committee-type-code-descriptions/:

> **Q = PAC - Qualified** — "PACs that have been in existence for six months and received contributions from 50 people and made contributions to five federal candidates"
> **N = PAC - nonqualified** — same test not yet met; "lower limits for their contributions to candidates"

So the rule is: **`CMTE_TP IN ('Q','N') AND ORG_TP IN ('C','W')`**.

Notes / edge cases:
- **W is overloaded — do not confuse the two fields.** `ORG_TP = W` means "corporation without capital stock" (counts as corporate). `CMTE_TP = W` means "Hybrid PAC (with Non-Contribution Account) - Qualified" — a different thing. A hybrid PAC whose connected org is a corporation (`CMTE_TP` V/W + `ORG_TP` C/W) is a judgment call: the standard (OpenSecrets-style) corporate-PAC definition uses Q/N only. Recommend Q/N + C/W as the primary definition and, if hybrids are included, label them separately.
- **Trade associations (`ORG_TP = T`) are NOT corporations** — exclude (e.g. National Association of Realtors PAC is T, not C). Labor (`L`), membership orgs (`M`, e.g. the AIPAC PAC itself), and cooperatives (`V`) are also excluded.
- `ORG_TP` lives only in the committee-master file (`cmYY.zip`, col 13) and the API `organization_type` field — **not** in pas2. Corporate-PAC pulls therefore require joining pas2's `CMTE_ID` to the committee master on `CMTE_ID`.
- ORG_TP can be blank for some committees (e.g. UDP has null; many old committees have blanks). Blank ≠ corporate; treat as unclassified and report the unclassified share.
- Committee-master rows are keyed by `CMTE_ID`; a committee's ORG_TP is stable, but use the **cycle-matched** cm file (a committee's type can change across cycles, e.g. N → Q).

---

## 3. FEC API test (DEMO_KEY) — result

Base: `https://api.open.fec.gov/v1`, key `DEMO_KEY`. All calls Nov 12, 2026, ~12:09–12:11 UTC.

| Test | Result |
|---|---|
| Committee search `q=AIPAC` | ✅ HTTP 200 (returned 2 unrelated committees — see §1 note on acronym search) |
| Committee search `q=American Israel Public Affairs` | ✅ HTTP 200, 1 result (C00797670) |
| Direct committee lookup C00797670, C00799031 | ✅ HTTP 200 |
| Candidate totals `/v1/candidate/H8CA05035/totals/?cycle=2024` | ✅ HTTP 200. Sample: Pelosi 2024 — `individual_itemized_contributions` $4,213,520.42, `individual_unitemized_contributions` $5,340,919.24, `individual_contributions` $9,554,439.66. Raw: `fec-candidate-totals-sample.json` |
| Schedule E, UDP, 2024 | ✅ HTTP 200, 1,269 rows (but see period-filter caveat in §1) |
| Schedule B, AIPAC PAC, 2024 | ❌ **HTTP 504 "Query timed out"** (single attempt; transient gateway timeout, not an auth/limit error). Raw: `fec-aipac-schedb.json` |

**Rate limits observed:**
- Response headers on successful calls: `X-Ratelimit-Limit: 10`, `X-Ratelimit-Remaining: 9` (api-umbrella burst window).
- Documented limits (FEC/OpenFEC docs, corroborated by multiple third-party references): **DEMO_KEY ≈ 30 requests/hour, shared globally per IP**; a free registered key at https://api.data.gov/signup/ gives **1,000 requests/hour** (up to 7,200/hr on request to APIinfo@fec.gov). Each call max 100 results/page.
- **Implication:** DEMO_KEY is fine for spot checks but **unusable for the full pull** (535 members × ~24 cycles × 4 data types ≈ tens of thousands of calls). The pull agent needs a registered key — or, better, bulk files (see §5).

---

## 4. Bulk data inventory

Base URL pattern: `https://www.fec.gov/files/bulk-downloads/<cycle>/<file><YY>.zip` (e.g. `.../2024/pas224.zip`). All files are **pipe-delimited (`|`) text, LF line endings**, inside a zip. Index page: https://www.fec.gov/data/browse-data/?tab=bulk-data. All URLs below were verified with `HEAD` (HTTP 200 after redirect) on Nov 12, 2026; sizes are the zipped sizes measured that day.

| File | Cycles available | Total zipped size, all cycles | Per-cycle size (recent) | Contents / use for tracker |
|---|---|---|---|---|
| **weball** — All candidates file (`weballYY.zip`) | 1980–2026 (24 cycles) | **3.0 MB** | 2024: 0.17 MB; 2026: 0.20 MB | 1 row/candidate/cycle. **Individual contributions: `TTL_INDIV_CONTRIB`, col 18.** Also `OTHER_POL_CMTE_CONTRIB` col 26, `TTL_RECEIPTS` col 6, `CVG_END_DT` col 28, `INDIV_REFUNDS` col 29, `CMTE_REFUNDS` col 30. |
| **pas2** — Contributions from committees to candidates (`pas2YY.zip`) | 1980–2026 (24 cycles) | **248.4 MB** | 2024: 24.7 MB; 2026: 9.2 MB (partial cycle); 2020: 29.0 MB | Itemized committee→candidate contributions (Schedule A subset). **Contributing committee: `CMTE_ID` col 1. Recipient candidate committee: `OTHER_ID` col 16. Candidate: `CAND_ID` col 17. Amount: `TRANSACTION_AMT` col 15. Transaction type: `TRANSACTION_TP` col 6.** |
| **oppexp** — Independent expenditures (`oppexpYY.zip`) | **2004–2026 only (12 cycles)** | **573.1 MB** | 2024: 67.9 MB; 2026: 52.6 MB; 2022: 61.9 MB | Schedule E. **Spender: `SPE_ID`. Candidate: `CAN_ID`. Amount: `EXP_AMO`. Support/oppose: `SUP_OPP` — `S` = Support, `O` = Oppose.** Also `EXP_DAT`, `PUR`, `AMN_IND`, `TRA_ID`, `FILE_NUM`. Doc says historical data from 2010, but files exist back to 2004. Pre-2004 files on the server are ~0 KB placeholders. |
| **cm** — Committee master (`cmYY.zip`) | 1980–2026 (24 cycles) | **13.4 MB** | 2024/2026: ~0.88 MB | 1 row/committee. `CMTE_ID` col 1, `CMTE_TP` col 10, **`ORG_TP` col 13**, `CONNECTED_ORG_NM` col 14, `CAND_ID` col 15. Join key for corporate-PAC classification. |

**Format verified by download:** `weball26.zip` (200,004 bytes) unzips to `weball26.txt` (555,025 bytes); first row `H2AK00200|CONSTANT, CHRISTOPHER|C|1|DEM|0|0|0|0|0|0|0|0|0|0|0|0|143180.09|0|AK|00||||||0|0|09/30/2026|0|0` — col 18 (`TTL_INDIV_CONTRIB`) = 143,180.09. `cm26.zip` (880,749 bytes) unzips to `cm.txt` (2,520,251 bytes); both target committees confirmed present (see §1).

**Other bulk files present (not needed for this tracker):** `cn` (candidate master), `indiv` (individual contributions — huge, do NOT use for individual totals; use weball instead), `oth` (other committee transactions), `pas` (committee contributions, 2-year), `ccl`, `webk`, `webl`.

### Key columns — exact positions

**pas2** (22 cols; doc: https://www.fec.gov/campaign-finance-data/contributions-committees-candidates-file-description/):
- 1 `CMTE_ID` — filer = contributing committee (filter `= C00797670` for AIPAC; join to cm for corporate PACs)
- 6 `TRANSACTION_TP` — pas2 contains only 24A, 24C, 24E, 24F, 24H, 24K, 24N, 24P, 24R, 24Z. For direct contributions the relevant codes are **24K** ("Contribution made to nonaffiliated committee") and **24P** ("Contribution made to possible federal candidate including in-kind"). 24E/24A are independent expenditures that also appear in this file — exclude them from the direct-contributions total.
- 15 `TRANSACTION_AMT`
- 16 `OTHER_ID` — recipient committee's FEC ID
- 17 `CAND_ID` — candidate receiving the money (stable across cycles for the same office)
- 18 `TRAN_ID`, 19 `FILE_NUM`, 22 `SUB_ID` — dedup keys (see §5)
- 20 `MEMO_CD` — FEC doc says of memo items: *"When using the bulk data file these memo items should be included in your analysis."* Flag as an open decision: the pull agent should test memo handling against AIPAC's published Schedule B totals before finalising.

**oppexp** (doc: https://www.fec.gov/campaign-finance-data/independent-expenditures-file-description/):
- `SPE_ID` — spender committee (filter `= C00799031` for UDP), `CAN_ID` — target candidate, `SUP_OPP` — **`S` = Support, `O` = Oppose** (keep S only), `EXP_AMO` — amount, `EXP_DAT`, `ELE_TYP`, `AMN_IND`, `TRA_ID`, `FILE_NUM`, `PREV_FILE_NUM`.
- ⚠️ **Duplication warning, quoted from the FEC doc:** *"This file contains transactions from both original reports and amended reports. Transactions from an original report are not removed when that report is later amended. This means that transactions will be duplicated in this dataset… sorting the records by filer and date and targeted candidate with an examination of amendment indicator columns or report type codes when the same dates and amounts appear."* Dedup is mandatory.

**weball** (30 cols; doc: https://www.fec.gov/campaign-finance-data/all-candidates-file-description/):
- 1 `CAND_ID`, 2 `CAND_NAME`, 18 **`TTL_INDIV_CONTRIB`** — total individual contributions (itemized + unitemized) for that candidate in that cycle. Sum across cycles per candidate for the career total.
- ⚠️ **Double-counting warning, quoted from the FEC doc:** if a candidate has multiple authorised committees that transfer funds between each other, activity is counted twice; subtract `TRANS_FROM_AUTH` (col 7) / `TRANS_TO_AUTH` (col 9) where both are present. `TTL_INDIV_CONTRIB` itself is a receipts breakout and is not affected by committee-to-committee transfers, but note the caveat in the methodology.
- ⚠️ **Timeliness warning:** weball is the *current-cycle* summary file and "may be more recent than other data files… some of the information in this file is less precise" than the post-cycle candidate summary. For completed cycles prefer cross-checking weball against the API candidate-totals endpoint for a sample of members.

---

## 5. Recommended pull strategy

### Bottom line: bulk files for everything; API only for spot-checks and member-list enrichment.

| Data type | Recommended source | Why |
|---|---|---|
| AIPAC PAC direct contributions | **Bulk pas2** (2022, 2024, 2026 only — 3 files, ~59 MB zipped) | One committee, 3 cycles. Filter `CMTE_ID = C00797670`, `TRANSACTION_TP IN (24K, 24P)`, group by `CAND_ID`, sum `TRANSACTION_AMT`. The API alternative (Schedule B endpoint) timed out once (HTTP 504) in testing and would need paginating thousands of rows under DEMO_KEY limits. |
| UDP independent expenditures (support) | **Bulk oppexp** (2022, 2024, 2026 — ~182 MB zipped) | Filter `SPE_ID = C00799031`, `SUP_OPP = 'S'`, group by `CAN_ID`, sum `EXP_AMO`. Dedup amended rows (see below). API Schedule E worked in testing but the period filter behaved unexpectedly (§1) and 1,269+ rows/cycle × pagination under DEMO_KEY is impractical. |
| Corporate PAC money | **Bulk pas2 (all 24 cycles, 248 MB) + cm (all 24 cycles, 13 MB)** | Build the corporate-PAC set per cycle from cm (`CMTE_TP IN ('Q','N') AND ORG_TP IN ('C','W')`), then sum pas2 rows where `CMTE_ID` is in that set, grouped by `CAND_ID` and cycle. This is the only feasible route — the API has no "all corporate PAC contributions to candidate X" aggregate. |
| Individual contribution totals | **Bulk weball (all 24 cycles, 3 MB)** | `TTL_INDIV_CONTRIB` per `CAND_ID` per cycle, summed across cycles. Trivially small files. Cross-check a sample against `/v1/candidate/<id>/totals/` (`individual_contributions` field). Do NOT use the `indiv` bulk files (individual itemized contributions, tens of GB) for this — weball already aggregates them. |
| Member roster / candidate IDs | **API `/v1/candidates/` or the `cn` bulk files + the existing `legislators-current.yaml` / `legislators-historical.yaml` in this work directory** | Candidate IDs are stable per person per office; a member who moved House→Senate gets a new ID, so map person → all their CAND_IDs and sum across them. Note: the yaml files were already present in this directory before this verification task — confirm with the coordinator where they came from before relying on them. |

### Rules the pull agent must apply
1. **Get a registered api.data.gov key** (free, 1,000 req/hr) before any API use; DEMO_KEY (~30/hr shared) cannot carry the pull.
2. **Dedup amended filings** in pas2 and oppexp: same `TRAN_ID`/`FILE_NUM` appearing in an original and an amendment must be counted once (keep the latest amendment; use `SUB_ID` as the unique row key and `AMNDT_IND`/`AMN_IND` to identify amendments). Validate by reconciling one cycle's AIPAC total against AIPAC's own published committee totals.
3. **Netting AIPAC contributions of refunds — OPEN, not yet verified.** Refunds *to* AIPAC from candidate committees are reported on AIPAC's Schedule A as receipts (transaction type **17Z**, "Refund/Rebate/Return from candidate or committee", per the FEC transaction-type list) — those live in the **`oth`** bulk files, not pas2. The pull agent must check whether pas2 `TRANSACTION_AMT` already contains negative refund rows for C00797670, and if not, subtract 17Z receipts from `othYY.zip` (`CMTE_ID = C00797670`, `TRANSACTION_TP = 17Z`, matched to the candidate via `OTHER_ID`/`CAND_ID`). Do not publish "net of refunds" until this is tested on the 2024 cycle.
4. **Memo-code decision:** test including vs excluding `MEMO_CD = 'X'` pas2 rows against AIPAC's published totals; document the choice.
5. **UDP support-only:** `SUP_OPP = 'S'` only; `O` rows are spending *against* the candidate and must be a separate column (or excluded), never netted.
6. **Cycle coverage gaps:** AIPAC PAC and UDP exist only from 2022 — earlier cycles are legitimately $0, not missing data. oppexp bulk files exist only from 2004 (irrelevant for UDP, which starts 2022).
7. **2026 cycle is in progress** (weball sample coverage end dates Sep–Oct 2026). Label 2026 figures as partial and re-pull after the cycle closes; record the `CVG_END_DT` / file download date with every figure.
8. **Reconciliation checks:** for each of the four money types, reconcile at least one full cycle against an independent source (FEC committee totals via API, or OpenSecrets) before publishing; report any discrepancy rather than silently adjusting.

### Estimated download (bulk, all cycles)
- weball 3.0 MB + pas2 248.4 MB + cm 13.4 MB + oppexp 573.1 MB ≈ **838 MB zipped** (uncompressed several GB; oppexp dominates). If the pull is scoped to AIPAC/UDP only, just 2022/2024/2026 pas2 + oppexp ≈ 242 MB zipped. Corporate-PAC money is what forces the full 24-cycle pas2 + cm download (~262 MB zipped).

---

## 6. What was NOT verified (gaps for the pull agent)

- Schedule B API endpoint for AIPAC PAC (HTTP 504 on the one attempt — retry with a registered key; bulk pas2 is the recommended path regardless).
- Whether pas2 amounts for C00797670 already net refunds (see rule 3 above).
- Memo-code treatment (rule 4).
- The exact `two_year_transaction_period` behaviour on Schedule E (see §1 caveat).
- Individual-contribution totals for members whose careers span pre-1980 cycles (FEC bulk starts 1980; anything earlier is out of scope for this source).
- Provenance of the `legislators-*.yaml` files already in this directory.
