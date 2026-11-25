# Square-one conduit pilot — FEC API Schedule B merge

**Date:** November 25, 2026 (all API pulls made Nov 25, 2026, ~18:00–23:30 EST)
**Branch:** `square-one-rederivation` (repo at `2f65cb5`)
**Author:** research subagent (conduit API pilot)
**Status:** pilot complete. No commits made; this file is the deliverable.
**Sources and as-of dates (every dollar below names its source):**
- FEC bulk `pas2` files from the pinned snapshot `fec-bulk-2026-11-22`
  (`data_as_of` 2026-11-22; pas2/weball coverage through Oct 14, 2026).
  Pas2 figures below are the **tracker rule**: `24K`/`24P` rows only,
  negative (voided) earmarks excluded, deduped on the tracker identity key
  (methodology §2/§4).
- FEC OpenFEC API (`api.open.fec.gov/v1`), `DEMO_KEY`, pulled Nov 25, 2026.
  API figures are live as of the pull; the API data itself had not moved since
  the Nov 13, 2026 pull (AIPAC `by_recipient` totals reproduce Nov 13
  exactly — see §3).
- `research/pro-israel-pacs.md` and
  `~/workspace/user/trackaipac-opensecrets-comparison-2026.md` (both Nov 25, 2026)
  for the claims verified in §4.

## 0. Verdict up front

1. **The merge is feasible and the endpoint works — but not on `DEMO_KEY` and
   not with the server-side line-number filter.** The working route is
   `GET /schedules/schedule_b/?committee_id=<spending committee>&two_year_transaction_period=<cycle>&per_page=100`,
   cursor-paginated on `last_indexes`, filtering to `line_number == "23"`
   client-side. The committee-scoped path
   `/committee/{id}/schedules/schedule_b/` **does not exist (HTTP 404)**.
   `line_number=F3X-23` works for AIPAC, JStreet and NORPAC but **times out
   (HTTP 504, ~16 s) for DMFI in both cycles and JACPAC in 2024** — twice each,
   reproducible, not transient. That reproduces methodology §8 item 11 on the
   exact queries the pull needs.
2. **The gap is as large as feared, and bigger for NORPAC/JACPAC than the
   pas2 comparison alone suggested.** Across the five pilot committees,
   pas2 carries 9,711 tracker-rule rows vs 130,885 API line-23 rows in cycles
   2024+2026 (see §3). AIPAC's API line-23 row count is ~42× its pas2 row
   count in 2026 (41,238 vs 977 deduped).
3. **There is no single earmark rule.** The pas2 memo-text definition
   (`EARMARK` in memo text / `ERMK:` prefix) works for AIPAC and JStreet
   only. It finds **$0** for NORPAC, JACPAC and DMFI, whose earmarks are
   identified by `memo_code = 'X'` (JACPAC) or by
   `disbursement_description` patterns (`EARMARK…` / `<donor> CONDUIT
   DONATION TO …`, NORPAC). The merge rule must be per-committee (§2).
4. **Fetterman verifies.** JStreet 2022 reproduces at **$214,625.26**
   (research said $214,625 — 26¢ under); JStreet 2024 at **$1,386.00**
   exactly; JACPAC ActBlue earmarks 2022 at **$10,757.00** exactly.
   NORPAC 2026 $25,000 is real but went to the **Fetterman Victory Fund
   (a JFC)**, not to the candidate committee — the research line needs that
   qualifier, and the merge needs a JFC decision (§4, §8).
5. **Roster-wide merge needs the registered key.** Estimated **~2,000–2,500
   API calls for cycles 2022+2024+2026** across all 66 listed committees
   (§8), plus a 183-call count sweep to firm up the 61 unmeasured
   committees. `DEMO_KEY` advertises a limit of 10 (window unclear),
   survived ~262 pilot calls with zero 429s, but the repo rule (AGENTS.md
   §4) already forbids `--all`-scale work on it, and the registered key
   (`FEC_API_KEY`, a GitHub secret) is **not on this VM**. Do not attempt
   the roster-wide pull with `DEMO_KEY`.

## 1. Endpoint spec — what works, what breaks

Base: `https://api.open.fec.gov/v1`, key `DEMO_KEY`, direct `curl` from this
VM (background-worker calls to `api.open.fec.gov` are blocked by the sandbox
egress; direct curl works — the same split documented in AGENTS.md / the
Nov 13 report).

### 1.1 Endpoints tested

| Endpoint | Result |
|---|---|
| `GET /committee/{id}/schedules/schedule_b/` (trailing slash and not) | **HTTP 404**, HTML "Not Found", both forms. This path does not exist. |
| `GET /committees/{id}/schedules/schedule_b/` | **HTTP 404.** Also does not exist. |
| `GET /schedules/schedule_b/?committee_id=…` | **Works (HTTP 200).** The route to use. |
| `GET /schedules/schedule_b/by_recipient/?committee_id=…` | **Works (HTTP 200), fast (0.5–1.2 s/page).** Aggregates only — see §1.4. |
| `GET /candidate/{id}/committees/` | Works. Used to resolve Fetterman committees (§4). |

### 1.2 Filters on `/schedules/schedule_b/`

| Parameter | Behaviour (tested Nov 25, 2026) |
|---|---|
| `committee_id` | Works. Spender committee. |
| `recipient_committee_id` | **Works, and is fast (~1.0–1.4 s/page)** even for AIPAC. The per-recipient route; returns only line-23 rows for that recipient in practice (Bell: 2,180/2,180 rows line 23). |
| `two_year_transaction_period` | **Respected.** Every pulled row's `two_year_transaction_period` equalled the requested cycle. Dates span both calendar years of the cycle (e.g. JStreet 2024 rows dated 2023-06-29–2024-10-31). One stale row: a JACPAC 2024 row dated **2021-04-21** — flag, don't trust dates alone. |
| `line_number=F3X-23` | Works for AIPAC (2024, 2026), JStreet (2022, 2024, 2026), NORPAC (2024, 2026), JACPAC 2026. **HTTP 504 at ~16 s for DMFI 2024, DMFI 2026, JACPAC 2024 — twice each, reproducible.** The format must be `FORM-LINENUMBER` (`F3X-23`); `23` and `F3X23` return HTTP 400 with `{"message": "Invalid line_number detected. A valid line_number is using the following format: 'FORM-LINENUMBER'. For example an argument such as 'F3X-16' …"}`. **Recommendation: do not use this filter in production; pull unfiltered and filter `line_number == "23"` client-side.** Unfiltered pulls are only modestly larger (AIPAC 2026: 42,285 rows all-lines vs 41,238 line-23; JStreet 2026: 13,335 vs 13,023; DMFI 2026: 322 vs 72 — the worst ratio, still tiny). |
| `transaction_type=24K`, `disbursement_type=CONTRIBUTION` | **Silently ignored** — result count unchanged (AIPAC 2026 stayed 42,285). There is no `transaction_type` field in Schedule B API rows at all (pas2 `24K`/`24P` has no API counterpart; the API exposes `line_number`, `disbursement_description`, `memo_text`, `memo_code`). |
| `per_page` | 100 is the max used; works. `per_page=1` count-only queries work and are the cheap way to get row counts — except they also 504 with the `line_number` filter (§1.2). |

### 1.3 Pagination

- `/schedules/schedule_b/` paginates by **cursor**: response `pagination`
  carries `last_indexes: {last_disbursement_date, last_index}`; pass both
  back as query params for the next page. Verified working (Bell 2026:
  page 1 ends 2026-07-22, page 2 continues 2026-07-22 with no overlap;
  full 22-page pull returned exactly the advertised 2,180 rows).
  `pagination.count` is exact (`is_count_exact: true`) and `pages` is
  reliable. Sort order is disbursement date descending.
- `/schedules/schedule_b/by_recipient/` paginates by **`page` number**
  (no `last_indexes`). Verified: AIPAC 20 pages / 1,977 rows, exact.
- **Per-call latency is erratic, not rate-limit-shaped:** identical
  count-only queries took 0.5–16 s (see §7). The 15–16 s calls are slow
  query plans, not throttling — no 429 accompanied them.

### 1.4 `by_recipient` — useful, but three traps

1. **It ignores `two_year_transaction_period`.** It returns **all cycles**
   despite the filter (AIPAC: 2022/2024/2026; JACPAC: 1982–2026; NORPAC:
   1990–2026). Always filter client-side on the `cycle` field. (Confirms
   the Nov 13 "by_recipient cycle trap".)
2. **`memo_count` / `memo_total` are NOT earmark totals.** They sum
   `memo_code = 'X'` rows only. JACPAC→Fetterman 2022: memo 37 / $10,757.00
   — exactly the ActBlue earmarks (§4). AIPAC→Bell 2026: memo 0 / $0.00
   despite $2,291,963.42 of earmarks in the row-level pull, because AIPAC
   earmark rows carry `memo_code: null`. Do not use `memo_total` as an
   earmark proxy.
3. **Totals cover ALL Schedule B lines, not candidate contributions.**
   `count`/`total` sum every line number. For most pilot committees the
   non-line-23 share is small (AIPAC 2026: 1,047 of 42,285 rows, 2.5%),
   but DMFI 2026 is the counterexample: `by_recipient` total is
   $3,975,272.97 while line-23 rows total only $151,750.00 — the rest is
   line 29 transfers ($3,731,459.23) and line 21B operating expenses
   ($106,813.74). Never quote a `by_recipient` total as candidate money
   without the line-23 cut.

### 1.5 What a Schedule B API row carries (vs pas2)

Row fields that matter for the merge (full schema sampled Nov 25, 2026,
saved in `data/evidence/square-one/sample_aipac_bell_2026_p1.json`):

- `committee_id` (spender), `recipient_committee_id`, `recipient_name`,
  `candidate_id` (**unreliable** — see below), `disbursement_amount`,
  `disbursement_date`, `disbursement_description`, `memo_text`,
  `memo_code`, `line_number`, `filing_form` (always `F3X` in pilot pulls),
  `amendment_indicator` (`A` = Add, `N` = New, `C` = Change — **not**
  "amended"; do not treat `A` rows as duplicates), `transaction_id`,
  `sub_id`, `file_number`, `image_number`, `load_date`,
  `two_year_transaction_period`, `report_year`.
- **Dedup key confirmed:** pas2 col 22 `SUB_ID` == API `sub_id`, and
  pas2 col 18 `TRAN_ID` == API `transaction_id`, verified exactly on two
  independent cases (Bell LONI RUSH $5,000, 2025-10-15:
  `BC2D0E62316E3488C916` / `4033120261434822643` in both; all four
  JStreet→Fetterman 2024 pas2 rows match API rows by `transaction_id`).
  Merge dedup should be on `sub_id` (fallback: committee + transaction
  id + candidate + amount + date). API `sub_id` was distinct on every
  row in every full pull (no duplicate `sub_id` within a pull).
- **`candidate_id` is not safe for attribution.** NORPAC 2024 line-23
  rows: 246 of 313 have `candidate_id: null`, including rows whose
  recipient committee is a House (`H`, 137 rows) or Senate (`S`, 59 rows)
  candidate committee (e.g. `WALBERG FOR CONGRESS`, `MAGGIE FOR
  CONGRESS`). `recipient_committee_id` is populated on 311/313 of those
  rows. Attribute by `recipient_committee_id` → committee master →
  candidate IDs, never by the API's `candidate_id` field.

## 2. Earmark identification — there is no single rule

The pas2 definition (methodology §4: memo text contains `EARMARK` or
starts `ERMK:`) reproduces exactly for AIPAC and JStreet and **fails
completely ($0) for the other three pilot committees**. Earmark rows are
identified differently per filer:

| Committee | Earmark signal in the API (line-23 rows) | Pilot evidence (Nov 25, 2026) |
|---|---|---|
| AIPAC C00797670 | `memo_text` = `EARMARK OF <donor>. TRANSMITTED BY CHECK/EFT`; voids read `VOID: REFUNDED EARMARK OF <donor>…` (negative amounts). `memo_code` is null. | Bell 2026: 2,178/2,180 rows earmark, $2,291,963.42 gross; 4 void rows −$1,681.16; 2 own-money rows $10,000 (`CONTRIBUTION TO COMMITTEE`, empty memo). |
| JStreetPAC C00441949 | `memo_text` = `EARMARKED BY <donor>`; `disbursement_description` = `CONDUIT CONTRIBUTION`. | Fetterman 2022: 601/601 earmark, $214,625.26. Fetterman 2024: 18/18 earmark, $1,386.00. |
| NORPAC C00247403 | `disbursement_description` starts `EARMARK…` (248 rows, $2,701,309.22 in 2024) **or** contains `CONDUIT` as `<donor> CONDUIT DONATION TO <candidate>` (52 rows, $186,660.00 in 2024). `memo_text` is empty on all rows — the pas2 memo rule finds $0. Own-money pattern: `PAC DONATION TO <candidate>` (13 rows, $34,900.00 in 2024; includes 3 rows reading `PAC DONATION TO EARMARK FOR …` — small ambiguity, flag it). | NORPAC 2024 L23 earmark ≈ $2,887,969.22 (300 rows) vs own-money ≈ $34,900.00 (13 rows). 2026: earmark-desc $2,557,843.69 (228) + conduit-desc $42,900.00 (12). |
| JACPAC C00139659 | `memo_code = 'X'` (the ActBlue conduit rows). `disbursement_description` starts `EARMARKED…` / contains `CONDUIT EARMARKED THROUGH ACTBLUE-<donor>`; own-money reads `DIRECT CAMPAIGN CONTRIBUTION` (typos included: `DIDIRECT`, `DIRECT CAMPAGIN`). `memo_text` is empty — pas2 memo rule finds $0. | 2024: memoX 970 rows, $251,622.32 (vs earmark-desc 956 rows, $243,887.32 — memoX is the cleaner rule). 2026: memoX 894 rows, $318,762.67. |
| DMFI PAC C00710848 | No earmarks found in either cycle: all line-23 rows read `CONTRIBUTION` (70 rows in 2026) or `IN-KIND CONTRIBUTION MADE: POLLING` (2 rows, $37,750.00 to EDW Action Fund, 2026). | DMFI 2024 L23 $285,000.00, 2026 L23 $151,750.00, earmark $0 by every rule tried. |

**Recommended merge rule (for the coordinator to approve):** line 23 only;
earmark = `memo_text` matches the pas2 definition **OR** `memo_code =
'X'` **OR** `disbursement_description` starts with `EARMARK` **or**
contains `CONDUIT` — with a per-committee override table, since the
signals differ by filer and `memo_code='X'` / `CONDUIT` wording may not
mean "earmark" for committees outside the pilot. Negative earmark rows
(voids/refunds) stay excluded from every total, as in methodology §2
(Bell 2026 voids: −$1,681.16 across 4 rows; the pas2 file's AIPAC 2026
earmark rows include 202 rows of $0.00 and 295 rows of −$6.00, all
`VOID: REFUNDED EARMARK OF HOWARD WELINSKY…` fragments spread across
recipients — treat $0 rows as $0 and keep the negative-earmark exclusion).
**JFC rows are a separate decision** (§4, §8): NORPAC's line-23 rows to
JFCs/victory funds (e.g. `TORRES VICTORY FUND` $11,600.00, 2024-12-31;
`TED CRUZ VICTORY COMMITTEE`) carry `candidate_id: null` and are not in
pas2 at all; counting them as candidate money requires a JFC→candidate
mapping the tracker does not have yet.

## 3. Gap table — pas2 vs API, per committee and cycle

Pas2 = tracker rule (24K/24P, deduped, negative earmarks excluded),
pinned snapshot `fec-bulk-2026-11-22`. API = OpenFEC, `DEMO_KEY`,
Nov 25, 2026. API line-23 rows/$ are from full row-level pulls for
NORPAC, JACPAC, DMFI; for AIPAC and JStreet the row count is exact
(count query / `by_recipient` row sum) and the dollar figure is the
`by_recipient` **all-lines** total, marked † — it includes non-line-23
rows (AIPAC 2026: 1,047 rows, 2.5%; JStreet 2026: 312 rows, 2.3%;
AIPAC 2024: 1,573 rows, 2.7%; JStreet 2024: 193 rows, 1.1%), so the
dollar gap for those two is an upper bound, overstated by that share
at most. API line-23 dollars for AIPAC/JStreet need the full row-level
pull (§8).

| Committee | Cycle | pas2 rows | pas2 $ | API L23 rows | API $ | Gap rows | Gap $ |
|---|---|---|---|---|---|---|---|
| AIPAC C00797670 | 2024 | 786 | $3,041,310.00 | 55,871 | $57,342,000.13 † | +55,085 | ≈ +$54,300,690 |
| AIPAC C00797670 | 2026 | 977 | $2,760,663.00 | 41,238 | $54,425,012.12 † | +40,261 | ≈ +$51,664,349 |
| JStreetPAC C00441949 | 2022 | 280 | $324,088.00 | 15,185 | $6,780,109.78 † | +14,905 | ≈ +$6,456,022 |
| JStreetPAC C00441949 | 2024 | 6,328 | $2,435,913.00 | 17,810 | $14,471,769.22 † | +11,482 | ≈ +$12,035,856 |
| JStreetPAC C00441949 | 2026 | 659 | $478,308.00 | 13,023 | $8,608,935.16 † | +12,364 | ≈ +$8,130,627 |
| NORPAC C00247403 | 2024 | 70 | $603,770.00 | 313 | $2,922,869.22 | +243 | +$2,319,099.22 |
| NORPAC C00247403 | 2026 | 54 | $308,600.00 | 271 | $2,683,575.69 | +217 | +$2,374,975.69 |
| JACPAC C00139659 | 2024 | 510 | $437,665.00 | 1,138 | $674,322.32 | +628 | +$236,657.32 |
| JACPAC C00139659 | 2026 | 108 | $173,905.00 | 997 | $554,562.67 | +889 | +$380,657.67 |
| DMFI PAC C00710848 | 2024 | 146 | $270,000.00 | 152 | $285,000.00 | +6 | +$15,000.00 |
| DMFI PAC C00710848 | 2026 | 73 | $108,000.00 | 72 | $151,750.00 | −1 | +$43,750.00 |

Earmark subtotals (pas2 memo-text definition vs API §2 rule), same sources:

| Committee | Cycle | pas2 earmark $ | API earmark $ |
|---|---|---|---|
| AIPAC | 2024 | $21,410.00 (21 rows) | not pulled row-level (see §8) |
| AIPAC | 2026 | $180,663.00 (321 rows) | Bell alone: $2,293,644.58 positive earmarks (§5) |
| JStreetPAC | 2022 | $0.00 | Fetterman alone: $214,625.26 (§4); committee-wide not pulled row-level |
| JStreetPAC | 2024 | $2,110,245.00 (6,116 rows) | not pulled row-level |
| JStreetPAC | 2026 | $333,536.00 (572 rows) | not pulled row-level |
| NORPAC | 2024 | $0.00 | ≈ $2,887,969.22 (300 rows, §2 rule) |
| NORPAC | 2026 | $0.00 | ≈ $2,600,743.69 (240 rows, §2 rule) |
| JACPAC | 2024 | $0.00 | $251,622.32 memoX (970 rows) |
| JACPAC | 2026 | $0.00 | $318,762.67 memoX (894 rows) |
| DMFI | 2024 / 2026 | $0.00 | $0.00 |

Notes on the table:

- **DMFI 2026 is the only near-match, and it still disagrees by
  $43,750.00.** API line-23 is $151,750.00 (72 rows) vs pas2 $108,000.00
  (73 rows). $37,750.00 of the API figure is two in-kind polling rows to
  EDW Action Fund ($15,250.00 + $22,500.00), which are 24Z-style rows
  pas2's 24K/24P filter excludes; a $6,000.00 residual (one extra pas2
  row) is unexplained — small, flagged, not chased in this pilot.
- **DMFI 2024:** API 152 rows match pas2's 146 on (candidate, amount,
  date) for 146 rows; the 6 extra API rows are $5,000.00 to Gallego
  Victory Fund (JFC), $2,000.00 to Gillen, $1,000.00 to Cisneros and
  three more — JFC/non-roster rows pas2 does not carry in this form.
- **JACPAC 2024:** 502 of 1,138 API rows match a pas2 row on
  (candidate, amount, date); the rest are ActBlue conduit rows pas2
  omits (e.g. 63 memoX rows to Bob Casey for Senate, $19,352.85, of
  which pas2 carries 7 rows, $2,550.00).
- **NORPAC 2024:** only 64 of 313 API rows match a pas2 row. The 246
  non-matching rows ($2,315,567.72) have `candidate_id: null`; 118 of
  their recipient names do appear among pas2's 48 NORPAC recipients, so
  this is not a recipient-coverage difference — pas2 carries a few rows
  per recipient (the PAC's own-money contributions: round amounts like
  $20,100.00, $28,200.00, $9,900.00 to Gottheimer) and omits the
  conduit transmissions to the same recipients.
- **What pas2 drops is whole filings, not scattered rows** (observed,
  root cause undetermined — see §6). Gottheimer/NORPAC 2024: pas2 has
  the rows from file 1767606 (image 20240404…) and file 1788408 (image
  20240611…), and none from files 1783203, 1807266, 1822784, 1834381 —
  presence/absence is per-`file_number`, not per-row. The same pattern
  explains the AIPAC/JStreet date quirk: pas2's AIPAC 2026 earmarks are
  all dated in 2025 (655 rows, 2025-01-19–2025-12-31, zero dated 2026),
  and pas2's JStreet 2024 earmarks are all dated in 2023
  (2023-02-14–2023-11-29) — the filings carrying 2026-dated (resp.
  2024-dated) earmarks are the ones missing from the bulk file. This
  needs FEC bulk-file provenance work by the coordinator; it does not
  change the merge design (the API is the complete source; pas2 is the
  subset to dedup against).
- **API data has not moved since Nov 13.** AIPAC `by_recipient` cycle
  sums reproduce the Nov 13 report exactly: 2022: 19,339 rows,
  $17,990,083.15; 2024: 57,444 rows, $57,342,000.13; 2026: 42,285 rows,
  $54,425,012.12 (Nov 13: 734 recipient groups / $54,425,012.12 for
  2026). Identical to the cent means either nothing new was filed Nov
  13–25 or the API's view hasn't moved; either way the Nov 13 live
  figures stand.

## 4. Fetterman verification — research/pro-israel-pacs.md claims

Fetterman candidate ID `S6PA00274`; live committee `C00765800`
(`FETTERMAN FOR PA`, cycles 2022/2024/2026, via
`/candidate/S6PA00274/committees/`, Nov 25, 2026). Old committee
`C00586578` (2016–2020) checked for JStreet 2022: 0 rows. AIPAC:
0 rows in 2022, 2024 and 2026 — $0 confirmed in every cycle.

| Claim (research/pro-israel-pacs.md, Nov 25, 2026) | API Schedule B, Nov 25, 2026 | pas2, snapshot fec-bulk-2026-11-22 | Verdict |
|---|---|---|---|
| JStreetPAC conduit checks 2022: $214,625 | **$214,625.26**, 601 rows, all earmark (`EARMARKED BY <donor>`, `CONDUIT CONTRIBUTION`), dates 2022-03-31–2022-11-08, to C00765800 | $0.00 (0 rows) | **Reproduces, 26¢ higher.** The research figure was $214,625; the API total is $214,625.26. Quote $214,625.26. |
| JStreetPAC conduit checks 2024: $1,386 | **$1,386.00**, 18 rows, all earmark, dates 2023-06-29–2024-10-31, to C00765800 | $131.00 (4 rows) | **Reproduces exactly.** All 4 pas2 rows are inside the API 18 (same `transaction_id`); net new from the API is $1,255.00. |
| JACPAC ActBlue earmarks 2022: $10,757 | **$10,757.00**, 37 rows, all `memo_code='X'`, `EARMARKED CONTRIBUTION ACTBLUE-<donor>`, dates 2022-06-24–2022-11-03, to C00765800. (Plus 2 direct rows, $7,500.00, `DIRECT CAMPAIGN CONTRIBUTION` — total to the committee $18,257.00, 39 rows.) `by_recipient` independently agrees: `FETTERMAN FOR PA`, cycle 2022, memo 37 / $10,757.00. | $5,000.00 (3 rows, all non-earmark) | **Reproduces exactly** on the earmark subset. |
| NORPAC 2026 earmarked donations: $25,000 | **$25,000.00 confirmed — but to `FETTERMAN VICTORY FUND`, not the candidate committee.** `by_recipient`: cycle 2026, `FETTERMAN VICTORY FUND`, count 1, $25,000.00. Recipient-filtered pull to C00765800 for 2026: **0 rows**. | $0.00 (0 rows) | **Confirmed with a qualifier.** The $25,000 is a JFC earmark. Whether it counts as Fetterman money is the open JFC decision (§8), not a data error. |
| AIPAC PAC / UDP to Fetterman: $0 | 0 rows, all cycles | $0.00 | Confirmed. |

## 5. Bell exemplar — the merge arithmetic on one recipient

Wesley Bell, `H4MO01134`, committee `C00842336`, AIPAC 2026. Full
recipient-filtered pull, 22 pages, 2,180 rows, Nov 25, 2026
(`data/evidence/square-one/schedb_aipac_to_bell_2026.json`):

- API total: **$2,301,963.42** (2,180 rows) — reproduces the Nov 13 live
  figure to the cent.
- Earmarks (memo-text rule): 2,178 rows, $2,291,963.42 gross =
  $2,293,644.58 positive (2,174 rows) minus $1,681.16 voids (4 rows:
  Heymann −$1,000.00, Smith −$500.00, Welinsky −$6.75, Weisberg
  −$174.41, all `VOID: REFUNDED EARMARK OF …`).
- PAC own-money: 2 rows, $10,000.00 (`CONTRIBUTION TO COMMITTEE`,
  2026-02-20 and 2026-03-23, empty memo).
- pas2 (tracker rule, snapshot fec-bulk-2026-11-22): 3 rows, $15,000.00
  — 1 earmark $5,000.00 (LONI RUSH, 2025-10-15) + 2 own-money $5,000.00
  (2026-02-20, 2026-03-23). All three match API rows exactly
  (`sub_id`, amount, date).
- **Merge result for Bell 2026: $2,303,644.58** (API total minus the
  $1,681.16 void earmarks, per the tracker rule; equivalently pas2
  $15,000.00 + net-new API earmarks $2,288,644.58). The tracker's
  current `aipac_direct_2026` for Bell is $15,000.00 — the merge moves
  it to $2,303,644.58, a 154× increase on this member, and the
  earmark breakout goes from $5,000.00 to $2,293,644.58.

## 6. What pas2 drops (observed patterns — root cause open)

1. **Conduit earmark transmissions are mostly absent from pas2.**
   NORPAC 2024: 313 API line-23 rows vs 70 pas2 rows; JACPAC 2026:
   997 vs 108; AIPAC 2026: 41,238 API line-23 rows vs 977 pas2
   tracker-rule rows. The rows pas2 does carry for these committees are
   predominantly the PAC's own-money contributions (round amounts, few
   rows per recipient).
2. **Absence is per-filing, not per-row** (Gottheimer/NORPAC 2024 file
   numbers in §3). Whole `file_number`s are present or absent.
3. **The earmarks pas2 does carry are stale-dated.** AIPAC 2026 pas2
   earmarks: all 2025-dated, zero dated 2026 (task premise confirmed:
   655 raw rows, all 2025). JStreet 2024 pas2 earmarks: all 2023-dated.
   JStreet 2026 pas2 earmarks: all 2025-dated. JStreet 2022 pas2
   earmarks: $0 (all 2022 conduit money missing, e.g. Fetterman
   $214,625.26).
4. **pas2 earmark rows include $0 / −$6 void fragments.** AIPAC 2026
   pas2 earmark rows: 202 at $0.00 and 295 at −$6.00, all memo
   `VOID: REFUNDED EARMARK OF HOWARD WELINSKY. TRANSMITTED BY
   CHECK/EFT` spread across recipients (the API's matching Bell void
   for Welinsky is −$6.75). They contribute $−1,770.00 raw and are
   excluded by the tracker's negative-earmark rule; the $0 rows
   contribute nothing. No action — noted so the next reader isn't
   surprised by 497 near-zero earmark rows.
5. **Future-dated rows exist in the API.** JACPAC 2026 has 2 rows dated
   after the pull date (2026-12-07, $250.00 to Riley; 2026-12-19,
   $30.00 to Ossoff; `load_date` ≤ 2026-11-15). Filer-dated future
   transactions; the merge should flag `disbursement_date` after the
   pull date rather than silently counting it.

## 7. Rate limits and latency (DEMO_KEY, Nov 25, 2026)

- **Calls made in this pilot: ~262.** 186 logged in
  `data/evidence/square-one/pilot-call-log.jsonl` (all HTTP 200) plus
  ~76 probe calls (count-only queries, schema probes, header checks,
  the 14-call burst test). No other key was used; no registered key
  exists on this VM.
- **HTTP 429s: 0.** No throttling observed at any point, including a
  14-call burst in ~9 s and sustained ~1 call / 2 s for over an hour.
- **HTTP 504s: 5, all on `line_number=F3X-23` count queries**
  (per_page=1): JACPAC 2024 (twice), DMFI 2024 (once), DMFI 2026
  (twice), each timing out at ~15–16 s. No other endpoint or filter
  504'd in ~262 calls.
- **Latency (186 logged calls):** curl time min 0.46 s, mean 1.20 s,
  max 19.24 s, total 224 s. Typical: `by_recipient` 0.5–1.2 s/page;
  recipient-filtered Schedule B 1.0–1.4 s/page; unfiltered
  committee-wide count queries 0.6–16 s (erratic — the 15–16 s calls
  are slow plans, see §1.3).
- **Rate-limit headers:** every response carries
  `X-Ratelimit-Limit: 10`, `X-Ratelimit-Remaining: 9` — and `Remaining`
  stayed at 9 across a 14-call burst, so the header does not reflect a
  live per-minute budget from this VM. Do not rely on it: the
  advertised limit is 10 (window unstated), the observed behaviour is
  unthrottled, and the two do not reconcile. The repo's own rule
  (AGENTS.md §4: `DEMO_KEY` is spot-checks only; the driver refuses
  `--all` on it) is the binding constraint, not the header.
- **Timeouts are the binding reliability limit, not rate limits.**
  The `line_number` filter is what 504s; the unfiltered and
  recipient-filtered routes never did in this pilot.

## 8. Feasibility verdict and call-count estimate

**Verdict: the roster-wide Schedule B merge is feasible with the
registered key, not with `DEMO_KEY`.** The endpoint, pagination,
filters, dedup key (`sub_id`) and per-committee earmark rules are all
determined in this pilot. What is missing is key capacity and two
methodology decisions (below).

**Call-count estimate** (design: one unfiltered row-level pull per
(conduit committee × cycle), `per_page=100`, cursor pagination, filter
`line_number == "23"` client-side; cycles 2022, 2024, 2026):

- Measured all-lines row counts (generic count queries, Nov 25, 2026)
  for the five pilot committees, cycles 2022+2024+2026:
  AIPAC 119,078 rows (1,191 pages); JStreet 46,597 (466 pages);
  NORPAC ~1,803 (19 pages); JACPAC ~3,858 (39 pages, incl. 2022
  `by_recipient` row sum 565); DMFI ~1,361 (14 pages). **Pilot five
  total: ≈ 172,700 rows ≈ 1,730 pages.**
- The other 61 listed committees are unmeasured. AIPAC and JStreet are
  the two giants and are already in the pilot; the remaining list is
  mostly small, old or terminated PACs (only ~40 of the 66 are Active;
  several, e.g. UDP C00799031, are IE-only with near-zero line-23
  volume). A 1-call-per-committee-cycle count sweep (61 × 3 = **183
  calls**) would firm this up. Extrapolating from the pilot and the
  `by_recipient` recipient-group counts, the other 61 committees add
  roughly **300–700 pages** for the three cycles.
- **Total estimate for 2022+2024+2026: ~2,000–2,500 calls.**
  At ~1–2 s per call including the 1 s pace, that is ~1–1.5 hours of
  wall time. A standard registered key (1,000 requests/hour, per
  `receipts/common/fec_api.py`) needs 2–3 hours across the hourly cap
  unless the 120 calls/min tier (7,200/hour, via email to
  apiinfo@fec.gov) is requested — with that tier the pull is ~20–30
  minutes. Full-career (1980–2026) would be several times larger and
  is not estimated here; the 2022+2024+2026 scope covers the
  AIPAC/UDP era and the cycles where the gap is material, but the
  scope decision belongs to the coordinator (pre-2022 pro-Israel money
  exists for NORPAC/JACPAC-era committees — their `by_recipient`
  cycles run back to 1990 / 1982).
- **`by_recipient` is not a substitute for the row-level pull.** It
  gives totals fast (~90 pages for all five pilot committees'
  all-cycle history) but no earmark split, no `sub_id` for dedup, no
  `recipient_committee_id`, and it ignores the cycle filter. Use it
  only for reconciliation (its per-cycle row sums should equal the
  row-level pull's row counts: AIPAC 2026 42,285 = 42,285 ✓; AIPAC
  2024 57,444 vs generic 57,454 — a 10-row discrepancy, likely rows
  with no recipient name that `by_recipient` cannot group; JStreet
  2022: 15,231 vs generic 15,244 — 13 rows; flag, don't chase).

**Decisions the coordinator still needs (not made in this pilot):**

1. **JFC attribution.** NORPAC→Fetterman Victory Fund $25,000.00
   (2026), NORPAC→Torres Victory Fund $11,600.00 (2024), DMFI→Gallego
   Victory Fund $5,000.00 (2024) and all other JFC/victory-fund rows
   are line-23 money to a candidate's joint fundraiser, not to the
   candidate committee. OpenSecrets counts them toward the candidate;
   the tracker currently counts only money to the candidate's own
   committees (comparison doc §8 rec. 2). The merge must pick a rule
   and document it in methodology §14 before the numbers land.
2. **Earmark rule per committee.** Adopt the §2 table (memo-text /
   memoX / description patterns) with a per-committee override list,
   or restrict the merge to committees whose earmark signal is
   verified. NORPAC's `PAC DONATION TO EARMARK FOR …` rows (3 rows in
   2024) sit on the boundary.
3. **Cycle scope** (2022+2024+2026 vs full career) and **in-kind rows**
   (DMFI's 2 polling rows, $37,750.00 — 24Z-style; the tracker excludes
   24Z from the headline columns today).
4. **Dedup against pas2** on `sub_id`, with the (committee,
   transaction id, candidate, amount, date) fallback; re-reported
   `ERMK:` rows (methodology §8 item 4) still cannot be matched
   reliably — the API pull does not fix that item.

## 9. Exact curl commands used

All with `DEMO_KEY` as `api_key` (never any other key). Base
`https://api.open.fec.gov/v1`.

```sh
# --- Route tests ---
# Committee-scoped path: HTTP 404 (both forms)
curl -s "https://api.open.fec.gov/v1/committee/C00797670/schedules/schedule_b/?api_key=DEMO_KEY&per_page=5&two_year_transaction_period=2026"
curl -s "https://api.open.fec.gov/v1/committees/C00797670/schedules/schedule_b/?api_key=DEMO_KEY&per_page=5&two_year_transaction_period=2026"

# --- Working route: committee-wide Schedule B, count-only ---
curl -s "https://api.open.fec.gov/v1/schedules/schedule_b/?api_key=DEMO_KEY&committee_id=C00797670&per_page=1&two_year_transaction_period=2026"
# Line-23 count (works for AIPAC/JStreet/NORPAC; 504s for DMFI + JACPAC 2024)
curl -s "https://api.open.fec.gov/v1/schedules/schedule_b/?api_key=DEMO_KEY&committee_id=C00797670&per_page=1&two_year_transaction_period=2026&line_number=F3X-23"

# --- Row-level pull, cursor pagination (per_page=100) ---
# Page 1:
curl -s "https://api.open.fec.gov/v1/schedules/schedule_b/?api_key=DEMO_KEY&committee_id=C00797670&recipient_committee_id=C00842336&per_page=100&two_year_transaction_period=2026"
# Page 2+: take last_indexes from the previous response and pass both back:
curl -s "https://api.open.fec.gov/v1/schedules/schedule_b/?api_key=DEMO_KEY&committee_id=C00797670&recipient_committee_id=C00842336&per_page=100&two_year_transaction_period=2026&last_index=4082720261586078597&last_disbursement_date=2026-07-22"

# --- by_recipient (aggregates; page-number pagination; IGNOR
...[truncated 2310 chars]