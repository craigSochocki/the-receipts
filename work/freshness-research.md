# Freshness-layer research — FEC API, 48-Hour Notices (Form 6), 24/48-hour IE reports

**Researched:** Thu Nov 12, 2026 (all live checks run this day).
**Scope:** what the tracker can read *after* the bulk snapshot's coverage end (Oct 14, 2026, pre-general) and before the next bulk re-pull — i.e. the freshness layer for the complete-financial-picture build.
**Method:** 15 live OpenFEC API calls, all on `DEMO_KEY`, with ≥1 s sleeps between calls (well under the ~30/hr DEMO_KEY budget). No scripts built, no dataset files touched.
**Raw evidence saved in this directory:** `constantino_totals_2026.json`, `constantino_totals_all.json`, `constantino_totals_ef.json`, `constantino_candidate.json`, `constantino_committees.json`, `f6_constantino.json`, `f6_all.json`, `f6_2044138.csv`, `f6_mindate.json`, `scheda_recent.json`, `schede_elsayed.json`, `schede_f24.json`, `f5_all.json`, `f5_udp.json`.

**Relation to `fec-sources.md` (Nov 12, 2026):** builds on it, agrees everywhere it overlaps, and extends it in three places — (a) it **confirms and quantifies** the Schedule E double-return caveat that fec-sources.md only flagged from the period-filter anomaly (§1/§5); (b) it **corrects** the framing of the Constantino "expected API year-end" figures (see §1.3 — they are the election-full aggregate, not a 2026-cycle year-end figure); (c) it adds the Form 6 and Form 5 routes, which fec-sources.md did not cover at all. Rate limits in fec-sources.md §3 (DEMO_KEY ~30/hr shared; registered key 1,000/hr via api.data.gov) were **not re-verified from the docs** but are consistent with what was observed live: response header `X-Ratelimit-Limit: 10, X-Ratelimit-Remaining: 9` (api-umbrella burst window) on every call, and no throttling across 15 calls.

---

## 0. Bottom line

All three freshness sources are **publicly accessible, no auth wall, DEMO_KEY works for spot checks** — but none of them is a single clean feed. Each needs one handling rule:

| Source | Access route (verified live) | Catch |
|---|---|---|
| Candidate totals (receipts, loans, cash) | `GET /v1/candidate/{candidate_id}/totals/?cycle={cycle}&api_key=` | Only as fresh as the latest *processed report* — on Nov 12 it still ends Oct 14 (pre-general). It cannot see anything filed after the last report, no matter how often you poll it. |
| 48-Hour Notices (Form 6) | `GET /v1/filings/?form_type=F6&committee_id={id}` for discovery + per-filing CSV at `https://docquery.fec.gov/csv/{last3}/{file_number}.csv` for the line items | The filings endpoint returns **metadata only** (no contributor/amount). The line items live only in the per-filing docquery CSV (F6N/F65 records), which the build must parse. There is **no F6 bulk file**. Schedule A does **not** contain F6 items. |
| 24/48-hour IE reports | `GET /v1/schedules/schedule_e/?filing_form=F24&committee_id={id}&candidate_id={id}&cycle={cycle}` | Every expenditure is returned **twice** (F24 notice + F3X monthly) with **different `sub_id`s** — naive summing overstates by ~96% in the tested sample. Filter `filing_form=F24` (or dedup on date+amount+payee). Form 5 filings cover only *unregistered* spenders — UDP files zero F5s. |

**Freshness value, proved live on Nov 12:** the bulk snapshot ends Oct 14, but the API already shows activity through **Oct 29** — a $1,000,000 candidate loan to Constantino (F6, Oct 29) and UDP spending against El-Sayed through Oct 29 ($73,834.08 on Oct 29 alone). Both are invisible to every bulk file and every totals endpoint today.

---

## 1. FEC API candidate totals — `/v1/candidate/{candidate_id}/totals/`

### 1.1 Endpoint and parameters (verified live)

```
GET https://api.open.fec.gov/v1/candidate/{candidate_id}/totals/?cycle={cycle}&api_key={key}
GET https://api.open.fec.gov/v1/candidate/{candidate_id}/totals/?election_full=true&api_key={key}
GET https://api.open.fec.gov/v1/candidate/{candidate_id}/totals/?api_key={key}   # all cycles + aggregate
```

- `cycle` — two-year cycle (even year). `cycle=2026` returns the 2026-cycle row only.
- No `cycle` — returns **one row per cycle plus one aggregate row with `cycle: null`** (see §1.3).
- `election_full=true` — returns **only** the aggregate row (`cycle: null`).
- Response is a single page per candidate (pagination `count` 1–3 in tests); no pagination concern at 1 call per candidate per cycle.
- Fields present on every row (confirmed in both the Pelosi sample in `fec-candidate-totals-sample.json` and the Constantino calls): `receipts`, `disbursements`, `individual_contributions`, `individual_itemized_contributions`, `individual_unitemized_contributions`, `other_political_committee_contributions`, `political_party_committee_contributions`, `candidate_contribution`, `loans`, `loans_made_by_candidate`, `loan_repayments`, `loan_repayments_candidate_loans`, `last_cash_on_hand_end_period`, `last_debts_owed_by_committee`, `last_debts_owed_to_committee`, `contribution_refunds`, `coverage_start_date`, `coverage_end_date`, `transaction_coverage_date`, `last_report_type_full`, `last_report_year`, `candidate_election_year`, `election_full`, `net_contributions`, `operating_expenditures`. **Everything the complete-financial-picture build needs for the topline + self-funding columns is in this one endpoint** — total receipts, disbursements, cash on hand, candidate contributions, candidate loans, loan repayments, debts owed by/to the committee.
- Rate limits: DEMO_KEY ~30 req/hr shared globally (per fec-sources.md §3; observed burst header `X-Ratelimit-Limit: 10`). Registered key via https://api.data.gov/signup/ gives 1,000 req/hr. **A registered key is required for any roster-wide use** — 664 members × 1 call each ≈ 664 calls ≈ 40 min at 1,000/hr, but ~22 hours of DEMO_KEY budget. The repo already has this wired: `config.yaml` → `fec_api.api_key_env: "FEC_API_KEY"`, `api_key_default: "DEMO_KEY"`, `sleep_between_requests_seconds: 0.4`.

### 1.2 Live test — Constantino, cycle 2026 (candidate `H6NY21157`, committee `C00892737 CONSTANTINO FOR CONGRESS, INC.`)

`GET /v1/candidate/H6NY21157/totals/?cycle=2026&api_key=DEMO_KEY` → HTTP 200, `count: 1`:

| Field | Value |
|---|---|
| `receipts` | **$14,464,951.19** |
| `disbursements` | **$14,472,853.54** |
| `loans_made_by_candidate` | **$14,400,000.00** |
| `candidate_contribution` | $0.00 |
| `individual_contributions` | $0.00 |
| `other_political_committee_contributions` | $7,000.00 |
| `last_cash_on_hand_end_period` | **$2,298,984.48** |
| `last_debts_owed_by_committee` | **$17,000,000.00** |
| `last_debts_owed_to_committee` | $0.00 |
| `coverage_end_date` | **2026-10-14** |
| `last_report_type_full` | PRE-GENERAL |

Raw: `constantino_totals_2026.json`. Committee ID confirmed via `GET /v1/candidate/H6NY21157/committees/` → 1 result, `C00892737` (raw: `constantino_committees.json`).

### 1.3 Correction: the "expected API year-end" figures are the election-full aggregate, not 2026-cycle

The task brief expected "API year-end: $17,064,951 receipts, $17,000,000 candidate loan, $14,765,967 disbursements, $2,298,984 cash on hand." Live, those exact numbers come back — but **only on the aggregate row**, not on the 2026-cycle row:

`GET /v1/candidate/H6NY21157/totals/?api_key=DEMO_KEY` (no cycle) → 3 rows:

| Row | Receipts | Candidate loans | Disbursements | Cash on hand | Coverage end | Last report |
|---|---|---|---|---|---|---|
| `cycle: null` (aggregate) | **$17,064,951.19** | **$17,000,000.00** | **$14,765,966.71** | $2,298,984.48 | 2026-10-14 | YEAR-END |
| `cycle: 2026` | $14,464,951.19 | $14,400,000.00 | $14,472,853.54 | $2,298,984.48 | 2026-10-14 | PRE-GENERAL |
| `cycle: 2024` | $2,600,000.00 | $2,600,000.00 | $293,113.17 | $2,306,886.83 | 2024-12-31 | YEAR-END |

`election_full=true` returns only the aggregate row (raw: `constantino_totals_ef.json`). The aggregate = 2024 + 2026 ($2.6M + $14.46M receipts = $17.06M; $2.6M + $14.4M loans = $17.0M). Two traps for the build:

1. **Do not label the aggregate row "2026 year-end."** Its `last_report_type_full` says YEAR-END but its `coverage_end_date` is 2026-10-14 — the label is inherited from the 2024 cycle's year-end report, and the row spans two cycles (Constantino's election years are 2025 and 2026; he ran in the 2025 special and the 2026 general under the same candidate ID). The build must use `cycle=2026` rows for per-cycle figures and treat the `cycle: null` row as a cross-cycle aggregate only.
2. **The 2026-cycle row is still pre-general.** As of Nov 12 the API totals have not moved past Oct 14 — no post-general report has been filed/processed yet (due Dec 3). Polling totals more often does not make them fresher; freshness comes from the F6/F24 feeds in §2–§3 until the next report lands.

### 1.4 Freshness semantics

Per the OpenFEC docs (api.open.fec.gov/developers, fetched Nov 12): "Information is made available on the API as soon as it's processed" and "These totals also incorporate any changes made by committees, if any report covering the period is amended." So the totals endpoint is **nightly-processed report data** — fresh to the last filed report, blind to everything after it. It is the right source for the topline/self-funding columns at each bulk re-pull (cross-check weball against it, as fec-sources.md §4 already recommends), and the right source for a *post-filing* freshness check, but it is **not** a late-activity feed. Also note: the docs state the efiling endpoints "provide real-time campaign finance data received from electronic filers" but "only contain the most recent four months of data" — **not investigated** in this task; a possible future real-time route, not a verified one.

---

## 2. 48-Hour Notices — Form 6

Form 6 is filed by candidate committees for contributions/loans of **$1,000+ received in the final 20 days before an election** (fec.gov forms page). There are two API-adjacent access routes, and they do different jobs.

### 2.1 Discovery: `/v1/filings/?form_type=F6` — metadata only, verified live

```
GET https://api.open.fec.gov/v1/filings/?form_type=F6&committee_id={committee_id}&api_key={key}&per_page=100&sort=-receipt_date
GET https://api.open.fec.gov/v1/filings/?form_type=F6&api_key={key}&per_page=100&sort=-receipt_date   # all committees
```

Live results (Nov 12, DEMO_KEY, HTTP 200):

- **Per-committee:** `form_type=F6&committee_id=C00892737` → `count: 1`. One F6 from Constantino's committee: `file_number` 2044138, `receipt_date` 2026-10-29, `report_year` 2026, `document_description` "48-HOUR NOTICE OF CONTRIBUTIONS OR LOANS RECEIVED 2026", `form_category` NOTICE, `means_filed` e-file, `is_amended` False, `amendment_chain` [2044138]. Raw: `f6_constantino.json`.
- **All committees:** `form_type=F6` alone → `count: 221,791` total F6 filings, most recent `receipt_date` **2026-11-11** (MAST FOR CONGRESS, C00632257) — F6s were still being filed 8 days after the Nov 3 election. Raw: `f6_all.json`.
- **Fields returned:** `committee_id`, `committee_name`, `form_type`, `receipt_date`, `report_year`, `cycle`, `file_number`, `fec_file_id`, `beginning_image_number`/`ending_image_number`, `csv_url`, `pdf_url`, `html_url`, `fec_url`, `is_amended`, `amendment_chain`, `amendment_version`, `treasurer_name`, `update_date`. **`candidate_id` and `candidate_name` are null on F6 rows** — the endpoint cannot be filtered by candidate; filter by `committee_id` (from `/v1/candidate/{id}/committees/`) or filter the all-committees stream client-side by `committee_id`.
- **What it does NOT return:** no contributor, no amount, no date of receipt, no loan-vs-contribution flag. All totals fields (`total_receipts`, `total_individual_contributions`, etc.) are null on F6 rows. The filings endpoint is a **discovery index only** — the money is in the per-filing file (§2.2).
- **Date filtering does NOT work:** `min_date=2026-11-01` on `/v1/filings/` was **silently ignored** — `count` stayed exactly 221,791, identical to the unfiltered call (raw: `f6_mindate.json`). Do not trust date params on this endpoint; use `sort=-receipt_date` and stop paging when `receipt_date` falls before the window, or filter client-side. (Docs note: "because the filings data includes many records, counts for large result sets are approximate; you will want to page through the records until no records are returned.")
- **DEMO_KEY works** for spot checks (all calls above were DEMO_KEY, HTTP 200). Roster-wide use needs the registered key: one call per principal committee (664 calls) for the per-committee route, or ~2,218 pages at 100/page for the all-committees stream — the per-committee route is the sane one, and can be restricted to committees with a race in the window.

### 2.2 Line items: per-filing CSV from docquery.fec.gov — verified live, no key needed

Each filings row carries `csv_url`, e.g. `https://docquery.fec.gov/csv/138/2044138.csv` — the path segment is the **last three digits of the file number** (2044138 → `138`). Fetched live, no API key, HTTP 200 (raw: `f6_2044138.csv`, 3 lines):

```
"HDR","FEC","8.5","CMDI CRIMSON FILER","8.0","",""
"F6N","C00892737","","CONSTANTINO FOR CONGRESS, INC.","PO BOX 109","","FONDA","NY","12068","H6NY21157","CONSTANTINO","ANTHONY ","THOMAS","","","H","NY","21","PLISHKA","JOHN","","","","20261029"
"F65","C00892737","F6.01","CAN","","CONSTANTINO","ANTHONY","THOMAS","","","PO BOX 109","","FONDA","NY","12068","","20261029","1000000.00","STICKER MULE","CEO"
```

Fields on the `F65` line-item record: committee ID, form line, contributor type (`CAN` = candidate), contributor last/first/middle name, address (street/city/state/ZIP), contribution date (`20261029`), **amount (`1000000.00`)**, employer (`STICKER MULE`), occupation (`CEO`). The `F6N` header record carries the candidate ID (`H6NY21157`), candidate name, office/state/district, treasurer, and filing date — so the CSV alone is sufficient to attribute the money to a roster member without joining back to the API.

**This is the freshness proof:** a **$1,000,000 candidate loan received Oct 29, 2026** — 15 days after the bulk/totals coverage end (Oct 14) and 5 days before the election. It appears in **no** totals endpoint and **no** Schedule A query (see §2.3). It will only surface in the aggregates when the post-general F3 is filed (due Dec 3) and processed.

### 2.3 What does NOT work for Form 6 — two dead ends, verified live

1. **Schedule A does not contain F6 items.** `GET /v1/schedules/schedule_a/?committee_id=C00892737&min_date=2026-10-15` → `count: 0`. The Oct 29 $1M loan is invisible to Schedule A (raw: `scheda_recent.json`). Any freshness build that only polls schedule_a will miss every F6.
2. **`filing_form` / `form_type` params are silently ignored on Schedule A.** `filing_form=F6` and `form_type=F6` both returned the committee's 15 ordinary F3 rows with no error and no filtering (all `filing_form: F3`, latest Jun 30). Do not rely on these params on the schedules endpoints; the same params **do** work on schedule_e (§3.2) — the behaviour is endpoint-specific, so each filter must be tested, not assumed.
3. **No bulk file for Form 6.** The FEC bulk inventory in fec-sources.md §4 (weball, pas2, oppexp, cm, cn, indiv, oth, pas, ccl, webk, webl) contains no F6 file, and a web search for an F6 bulk download turned up no such file — only the forms page, the docquery PDFs, and the API. If the build needs F6 data at scale, the route is filings-API discovery + per-filing docquery CSV fetch (one HTTP GET per filing, no key). **This is a finding, not a failure** — but it means F6 ingestion is a small parser build (F6N/F65 records in the FEC .fec v8.x format), not a bulk download.

### 2.4 Form 6 handling notes for the build

- **Amendments:** filings rows carry `is_amended`, `amendment_chain`, `amendment_version`. Dedup by `file_number` / amendment chain — keep the latest version only (same rule as pas2/oppexp dedup in fec-sources.md §5).
- **Loans vs contributions:** the F65 record's contributor-type code (`CAN` here) plus the amount identifies a candidate loan; non-candidate contributors are contributions. The build must split F6 amounts into the tracker's self-funding columns (candidate loans) vs individual/other-committee columns — do not blend into `total_accepted` (same rule as the approved complete-financial-picture scope).
- **Threshold:** only $1,000+ items in the final 20 days are reported, so F6 is a *lower bound* on late money, not a complete late-activity feed. Small late contributions never appear here; they surface only in the post-general report.
- **Volume:** 221,791 F6 filings exist historically, but the per-cycle, per-committee counts in-window are small (Constantino: 1). The roster-wide sweep is cheap once committee IDs are known.

---

## 3. 24/48-hour IE reports — Schedule E (F24) and Form 5

### 3.1 The route that works: Schedule E with `filing_form=F24`

```
GET https://api.open.fec.gov/v1/schedules/schedule_e/?committee_id={committee_id}&candidate_id={candidate_id}&cycle={cycle}&filing_form=F24&api_key={key}&per_page=100
```

For **registered committees** (UDP, and every super PAC / PAC on the roster's radar), 24/48-hour IE reports are filed as **Form 24 (F24)** Schedule E notices, not as a separate form. The `filing_form=F24` filter **works** on this endpoint (unlike on Schedule A — see §2.3). `report_type` `24` / `48` marks the 24- vs 48-hour report; `is_notice: true` marks F24 rows.

### 3.2 Live test — UDP vs El-Sayed, cycle 2026 (candidate `S6MI00418`)

`GET /v1/schedules/schedule_e/?committee_id=C00799031&candidate_id=S6MI00418&cycle=2026&api_key=DEMO_KEY&per_page=100` → HTTP 200, `count: 59` (raw: `schede_elsayed.json`):

| Slice | Rows | Sum |
|---|---|---|
| All rows returned | 59 | $41,044,346.31 |
| Unique (expenditure_date, amount, payee) | **35** | **$20,904,442.10** |
| `filing_form=F24` only | 34 | $20,903,437.57 |
| `filing_form=F3X` only | 25 | $20,140,908.74 |
| `report_type` 24 / 48 | 22 / 12 (= 34, exactly the F24 rows) | — |
| `support_oppose_indicator` | all 59 `O` (oppose) | — |

**The double-return caveat from the task brief is CONFIRMED and quantified.** Each expenditure appears twice — once as an F24 notice (`is_notice: true`, `report_type` 24 or 48) and once on the monthly F3X (`is_notice: false`, `report_type` M7/M8/M9) — with **different `sub_id`s**, so `sub_id` dedup does not work. Example (from the raw file): 2026-07-30, $9,797.37, UNITED MEDIA PARTNERS LLC appears as F3X/M8 `sub_id 4090820261595915656` and F24/24 `sub_id 4073020261539935176`. **Naive summing overstates the total by 96.3%** ($41.04M vs the true $20.90M). The OpenFEC docs confirm this is by design: *"Aggregates by candidate do not include 24 and 48 hour reports. This ensures we don't double count expenditures and the totals are more accurate. You can still find the information from 24 and 48 hour reports in `/schedule/schedule_e/`."* (api.open.fec.gov/developers, fetched Nov 12.)

**The fix is the filter, not dedup:** `filing_form=F24` returns exactly the 34 notice rows (verified live — `count: 34`, all rows `filing_form: F24`, raw: `schede_f24.json`). The F24-only sum ($20,903,437.57) matches the deduped unique sum ($20,904,442.10) to within $1,004.53 — one expenditure exists on F3X but has no F24 twin (or vice versa). **Open item:** that $1,004.53 residual is unexplained; the build should reconcile F24-only vs deduped-all on a full-cycle sample before trusting either alone. Either way: **for a freshness feed, use `filing_form=F24` and never sum unfiltered Schedule E.**

**Freshness proof:** latest `expenditure_date` in the sample is **2026-10-29** — $73,834.08 to RIVIERA LLC (F24, report 24), plus $7,154.76 to COLDSPARK (Oct 27) and $94,620.36 to RIVIERA LLC (Oct 26, Oct 23). All of it post-dates the bulk coverage end (Oct 14) and is invisible to the oppexp bulk file. Note this sample is all `O` (oppose) — UDP's El-Sayed spending in 2026 is opposition spending, which the tracker credits as opposition benefit, not support; the same F24 route works for `S` rows.

**Cycle filter:** `cycle=2026` was passed on this call and the returned rows are all 2026 expenditures — but fec-sources.md §1 recorded the period filter misbehaving on this endpoint (a 2026 row returned for a 2024 query). The build should still verify `cycle=` / `two_year_transaction_period` handling on a multi-cycle sample; `min_date`/`max_date` params exist on schedule_e and should be tested as the window filter for the freshness sweep (not tested here — 15-call budget).

### 3.3 Form 5 — only for *unregistered* spenders; UDP files zero F5s

```
GET https://api.open.fec.gov/v1/filings/?form_type=F5&committee_id={committee_id}&api_key={key}&per_page=100&sort=-receipt_date
```

Live results (Nov 12, DEMO_KEY, HTTP 200):

- **All committees:** `form_type=F5` → `count: 18,727`, most recent `receipt_date` **2026-11-10** (24-HOUR REPORT OF INDEPENDENT EXPENDITURES, ASIAN AMERICANS FOR CIVIL RIGHTS AND EQUALITY ACTION FUND, $73,720.46). Filings rows *do* carry `total_independent_expenditures` for F5 (unlike F6). Raw: `f5_all.json`.
- **UDP:** `form_type=F5&committee_id=C00799031` → **`count: 0`**. UDP, as a registered super PAC, reports its IEs on F3X Schedule E plus F24 notices — it never files Form 5. Raw: `f5_udp.json`.

Consequence: **Form 5 is not a UDP freshness route.** It matters only for the all-IE build's long tail (unregistered persons/groups making IEs) — and even there, the filings row gives only a per-filing total, not per-candidate amounts; the per-candidate split needs the F5's own Schedule E lines via the docquery CSV or the schedule_e endpoint (F5 filers' Schedule E rows appear under their filer ID). For the tracker's freshness layer, **Schedule E `filing_form=F24` is the IE route; F5 is out of scope** unless the all-IE build later needs unregistered spenders.

### 3.4 No bulk route for 24/48-hour IEs before the next snapshot

The oppexp bulk file *does* contain Schedule E transactions (including F24 rows, in principle) — but the bulk snapshot is the stale thing. There is no separate "recent IE" bulk file. The freshness route is the API only, until the mid-Dec bulk re-pull.

---

## 4. Recommended pre-election refresh cadence

Built from the filing calendar (verified in the task brief) + what §1–§3 proved about each source's freshness semantics. Assumes a **registered api.data.gov key** (1,000 req/hr) — DEMO_KEY cannot carry any roster-wide step.

### 4.1 The calendar that drives it

| Filing | Coverage closes | Due | What it unlocks |
|---|---|---|---|
| Oct Quarterly | Sep 30 | Oct 15 | (already in bulk snapshot) |
| Pre-General | Oct 14 | Oct 22 | (already in bulk snapshot) |
| **Post-General** | **Nov 23** | **Dec 3, 2026** | First F3/F3X that absorbs all F6 loans and late Schedule E into the aggregates |
| **Year-End** | **Dec 31** | **Jan 31, 2027** | Final 2026-cycle totals |

Between Nov 12 and Dec 3, **no new report will move the totals endpoint** — the only new data is F6 notices and F24 notices, which arrive within 24–48 hours of the underlying activity (e-file). After Dec 3, the totals endpoint and the bulk re-pull become the source of truth again and the notice feeds switch to catching amendments and stragglers.

### 4.2 Cadence

| Window | Cadence | What each run pulls (per roster member / tracked committee) | Est. API calls/run |
|---|---|---|---|
| **Final 20 days before an election** (the F6/F24 window) | **Daily** | 1. F6 discovery: `filings/?form_type=F6&committee_id={principal committee}` for each member's committee; for each *new* `file_number`, fetch the docquery CSV and parse F65 lines (contributor, amount, date, loan-vs-contribution). 2. IE freshness: `schedule_e/?committee_id=C00799031&candidate_id={id}&cycle={cycle}&filing_form=F24` (UDP only in current scope; extend per committee for the all-IE build) + `min_date` = last run date once that param is verified on schedule_e. 3. Totals spot-check only if a new F3/F3X has landed (check `filings/?form_type=F3,F3X` receipt dates first — polling totals daily without a new report is wasted calls). | ~664 F6-discovery + ~664 schedule_e (UDP) ≈ 1,330 calls ≈ 1.5 hr at 1,000/hr. CSV fetches are keyless docquery GETs, not API calls. |
| **Outside the final 20 days, cycle in progress** | **Weekly** | Same two feeds (they will mostly return nothing — F6/F24 only exist near elections — so this is a cheap guard), plus a totals refresh: `candidate/{id}/totals/?cycle={current}` for each member, to catch quarterly/monthly reports and amendments as they are processed. | ~664 totals calls ≈ 40 min at 1,000/hr. |
| **After each filing deadline (Dec 3 post-general; Jan 31 year-end)** | **Event-driven, within 2–3 days of the due date + 1 re-check a week later** (processing lag; paper filings take longer) | 1. Totals refresh for the full roster (catches the new report + amendments). 2. **Bulk re-pull** (see §4.3) — this is what replaces the freshness layer, not the other way round. 3. Reconcile: freshness-feed sums (F6 + F24) vs the new report's figures for a sample of members; log discrepancies, do not silently adjust. | Same as weekly, plus the bulk download. |
| **Cycle closed / between cycles** | **Monthly until the year-end report lands, then stop** | Totals-only check for amendments and late filers. | ~664 calls/run. |

### 4.3 Bulk re-pull dates (unchanged from the task brief — now grounded in the verified access)

- **Mid-Dec 2026 (after Dec 3 post-general due date):** re-pull weball26, pas226, oppexp26, cm26. This absorbs every F6 loan and F24 expenditure into the canonical files; after this pull the freshness layer's Oct 15–Nov 23 catch is verifiable against bulk and can be retired for the 2026 general. Allow a few days past Dec 3 for processing lag before pulling.
- **Feb 2027 (after Jan 31 year-end due date):** re-pull the same four files for final 2026-cycle figures. Same processing-lag allowance.
- Between re-pulls, the freshness layer is the *only* source of post-Oct-14 activity — it should be presented as a separate, clearly-labelled "since Oct 14 (pre-general)" increment, never blended into the bulk-based totals until the re-pull confirms it (same never-blend rule as the self-funding columns).

### 4.4 Call-budget sanity check (registered key, 1,000 req/hr)

- Roster-wide totals refresh: 664 calls ≈ 40 min. Daily in the final 20 days would be ~13,280 calls over the window — feasible, but pointless (see §1.4: totals don't move without a new report). Gate totals polls on filings-receipt checks instead.
- Roster-wide F6 discovery: 664 calls/run ≈ 40 min. Daily in the final 20 days ≈ 13,280 calls — feasible on a registered key, impossible on DEMO_KEY (~22 hr of budget per run).
- UDP F24 sweep: 664 candidate-scoped calls/run, or 1 committee-scoped call with pagination if the build aggregates client-side (UDP 2026 cycle is ~1,269+ rows per fec-sources.md §1 — paginate at 100/page, ~13+ pages). Prefer the committee-scoped pull + client-side candidate filter: far fewer calls.
- **DEMO_KEY verdict: spot checks only, as fec-sources.md §3 already concluded.** This research used 15 calls; a single daily freshness run is ~1,300+ calls.

---

## 5. Blockers, open items, and what was NOT verified

**Blockers (exact):**
1. **No F6 bulk file exists.** F6 line items are only available per-filing via docquery CSV. Not a dead end — the CSV route works — but the build must include a small F6N/F65 parser; there is no bulk shortcut. (Verified: bulk inventory in fec-sources.md §4 + web search, Nov 12.)
2. **`min_date` is silently ignored on `/v1/filings/`.** Date-windowed filings sweeps must page with `sort=-receipt_date` and filter client-side. (Verified live: identical count 221,791 with and without `min_date`.)
3. **`filing_form` / `form_type` are silently ignored on `/v1/schedules/schedule_a/`.** Do not use Schedule A to find F6 items — it contains none (verified: `min_date=2026-10-15` → 0 rows). The same params *do* work on schedule_e, so each endpoint's filters must be tested individually.
4. **Schedule E double-return.** Unfiltered Schedule E sums overstate by ~96% in the tested sample (different `sub_id` per twin, so `sub_id` dedup fails). The `filing_form=F24` filter is the verified fix.

**Open items for the build agent:**
- Verify `min_date`/`max_date` and `two_year_transaction_period` vs `cycle` behaviour on **schedule_e** (fec-sources.md §1 already flagged the period filter misbehaving; not re-tested here).
- Reconcile the **$1,004.53 residual** between the F24-only sum ($20,903,437.57) and the deduped-unique sum ($20,904,442.10) for UDP/El-Sayed 2026 on a full-cycle sample.
- F6 CSV parsing: confirm the F65 record layout against the FEC .fec format spec (v8.5 header observed) and handle amended F6s via `amendment_chain`.
- The **efiling endpoints** (real-time, most recent 4 months) were not investigated — possible future real-time route, unverified.
- **No registered API key exists in the repo yet** (`config.yaml` points at `FEC_API_KEY` env var, default `DEMO_KEY`). Somebody must register one at https://api.data.gov/signup/ before any roster-wide freshness run.

**Not verified in this task (out of scope, carried from fec-sources.md §6):** Schedule B API behaviour beyond the single 504; pas2 refund netting; memo-code treatment; provenance of `legislators-*.yaml`.

---

## 6. Endpoint / parameter cheat sheet (all verified live Nov 12 unless noted)

| Purpose | Endpoint | Key params that work | Params that silently fail |
|---|---|---|---|
| Candidate totals (per cycle) | `GET /v1/candidate/{id}/totals/` | `cycle=2026`, `election_full=true` | — |
| Candidate record | `GET /v1/candidate/{id}/` | — | `principal_committees` field is absent from this response; use the committees endpoint |
| Member's committees | `GET /v1/candidate/{id}/committees/` | — | — |
| F6 discovery | `GET /v1/filings/?form_type=F6` | `committee_id=`, `sort=-receipt_date`, `per_page=100` | `min_date` (ignored); no `candidate_id` filter (field is null on F6 rows) |
| F6 line items | `GET https://docquery.fec.gov/csv/{last3}/{file_number}.csv` | No key needed | — |
| F5 discovery | `GET /v1/filings/?form_type=F5` | `committee_id=`, `sort=-receipt_date` | `min_date` (same filings endpoint; presumed ignored, not separately tested) |
| 24/48h IE (freshness) | `GET /v1/schedules/schedule_e/` | `committee_id=`, `candidate_id=`, `cycle=`, `filing_form=F24`, `report_type` (24/48 in results), `per_page=100` | Unverified: `min_date`/`max_date`, `two_year_transaction_period` (flagged in fec-sources.md §1) |
| Schedule A (for contrast) | `GET /v1/schedules/schedule_a/` | `committee_id=`, `min_date=` (works here — 0 rows after Oct 15) | `filing_form`, `form_type` (ignored); contains no F6 items |

Base URL for all API calls: `https://api.open.fec.gov/v1`. Key: `api_key=DEMO_KEY` (spot checks, ~30/hr shared) or a registered key from https://api.data.gov/signup/ (1,000/hr) for production. Max `per_page=100`.
