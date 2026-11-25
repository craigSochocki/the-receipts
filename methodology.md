# Congress money tracker — methodology

This document defines every column, source, rule and known limitation. It states the
method only. Current figures live in `data/source/baseline.json` (every total, count and
named spot case the pipeline checks itself against) and in the dataset itself. The
figures, named cases and reconciliations that showed each rule are kept in
`research/methodology-evidence.md`, under the same section numbers. The FEC snapshot the
money comes from is named in `baseline.json` (`_snapshot`) and stamped on every row as
`data_as_of` (set in `config.yaml`).

**Files:** `congress-money-tracker.csv` (one row per person), `congress-money-tracker.json`
(same data; `fec_candidate_ids` is a list; each person also carries per-cycle breakdowns and
per-cycle records, §14a) and `congress-money-tracker-cycles.csv` (the per-cycle records, one
row per person per cycle).
Committed inputs live in `data/source/`, the staged FEC bulk files in `data/raw/`
(gitignored), regenerable staging files in `data/intermediate/` (gitignored), and pull logs
and research notes in `research/`.

---

## 1. Coverage — who is in the tracker

- **One row per person**: everyone in the roster source (`legislators-current.yaml`,
  current members of the 119th Congress) plus everyone named to the incoming 120th. A
  person who appears twice in the source roster is collapsed into one row (§7).
- **Uncalled or TBD seats** carry `in_120th = "unknown"`. Re-run after they are called.
- **Members who left before the roster was crawled are not included.** The roster source
  lists current members only. They can be added from `legislators-historical.yaml`; this
  is a scope gap, not a data error.
- **Delegates** are House members with `district = 0`, matching the source repo's
  convention (0 = at-large / delegate).
- **120th results are media calls, uncertified.** 120th membership is transcribed from
  public reporting and cross-checked against per-state apportionment.
- **Leadership:** `leadership_119` is verified against official leadership pages;
  `leadership_120` is `TBD` until the leadership elections are held.
- **Party labels:** DFL (Minnesota) is normalized to Democrat. Any other label is kept as
  filed (e.g. PPD). A member who changed party mid-Congress carries the label they held
  at the end of it.
- **Chamber switchers** have one FEC candidate ID per office; money is summed across all
  of them. **Returning former members** use their historical FEC IDs — confirm each
  matches the current candidacy before reusing the join (§14, data gaps).
- **Mid-session swearing-ins and resignations:** a member is counted in the 120th as
  seated at its start.

---

## 2. Column definitions

| Column | Definition |
|---|---|
| `person_key` | Join key: a bioguide ID where one exists; otherwise a slug built from name + state + chamber. |
| `full_name` | Person's name as in the roster. |
| `chamber_119`, `chamber_120` | `House` / `Senate`, blank if not in that Congress. |
| `state` | Two-letter state (or territory / DC for delegates). |
| `district_119`, `district_120` | House district number; `0` for at-large seats and delegates; blank for Senators and for Congresses the person is not in. |
| `party_119`, `party_120` | Party in that Congress; blank if not in it. |
| `leadership_119`, `leadership_120` | Leadership role in that Congress; blank if none (see §1). |
| `in_119th`, `in_120th` | `yes` / `no`; `in_120th` is `unknown` for uncalled seats. The site derives an election-outcome label from `in_120th` alone (§8 item 21). |
| `fec_candidate_ids` | Every FEC candidate ID for the person, semicolon-joined in the CSV, a list in the JSON. Money is summed across all of them and all cycles in the career range (`config.yaml` `cycles`). A person with no FEC candidate ID has every money column `unknown` (§5). |
| `individual_contribution_total_career` | **Career total of individual contributions** (itemized + unitemized), summed across the person's candidate IDs and all cycles. Source: `TTL_INDIV_CONTRIB` (col 18) of the FEC all-candidates file (`weball`). **De-duplicated (§8 item 15):** where weball repeats the identical `TTL_INDIV_CONTRIB` under two of a person's candidate IDs in the same cycle, it is counted **once** per (person, cycle). Same-cycle amounts that *differ* across IDs are different money and are summed in full. |
| `aipac_pac_direct_career` | **Headline AIPAC column — total Schedule B disbursements from the AIPAC PAC (committee ID in `config.yaml`) to the person's campaign(s).** The sum of *all* `24K`/`24P` pas2 rows from that committee: the PAC's own money **plus** earmarked individual checks transmitted through it. See the AIPAC decision below. |
| `aipac_earmark_transmitted_career` | **Breakout (subset of the headline):** the part of `aipac_pac_direct_career` that is individual donors' earmarked money transmitted through the PAC as a conduit (pas2 rows whose memo text names a donor, e.g. `EARMARK OF <donor>. TRANSMITTED BY CHECK/EFT`). **PAC own-money = headline − this column.** |
| `corporate_pac_career` | Career total of direct contributions from **corporate-connected PACs**. A committee is corporate if, in the same cycle's committee-master file, `CMTE_TP IN ('Q','N')` **and** `ORG_TP IN ('C','W')`. Trade associations (`T`), labor (`L`), membership orgs (`M`, including the AIPAC PAC), cooperatives (`V`) and hybrid PACs (`CMTE_TP` V/W) are excluded. A blank `ORG_TP` is unclassified, never corporate. A reviewed override in `config.yaml` `committees.class_overrides` beats the filed code (§4). |
| `corporate_earmark_transmitted_career` | Breakout (subset of `corporate_pac_career`): earmarked transmissions through corporate PACs, on the AIPAC earmark definition. Corporate own-money = corporate − this column. |
| `udp_ie_support_career` | **United Democracy Project (UDP; committee ID in `config.yaml`) independent expenditures SUPPORTING the person's race.** Money UDP spent *about* the race (ads, mail, phones), legally uncoordinated with the campaign. **It is not money given to the campaign and must never be described as a contribution.** Support only (see below). |
| `cand_contrib_career`, `cand_loans_career` | **Self-funding, career.** Candidate contributions (`CAND_CONTRIB`, weball col 12) and candidate loans (`CAND_LOANS`, col 13), summed across the person's candidate IDs and cycles. |
| `self_funding_career` | Candidate contributions + candidate loans. |
| `loan_repayments_career` | Loan repayments to the candidate (weball cols 15+16), career. |
| `debts_owed_by_career` | Debts owed BY the committee, career = the **latest cycle's** value (a stock, not a sum across cycles). |
| `debts_owed_to_career` | Debts owed TO the committee — **null for every person**: no weball column carries it. The FEC API candidate-totals field `last_debts_owed_to_committee` is the follow-up route (§16). |
| `total_receipts_career`, `total_disbursements_career` | Total receipts (`TTL_RECEIPTS`, weball col 6) and total disbursements (`TTL_DISB`, col 8), career sums. |
| `transfers_from_auth_career`, `transfers_to_auth_career` | Transfers from / to other authorized committees of the same candidate (weball cols 7 / 9), career sums. |
| `cash_on_hand_career` | Cash on hand (`COH_COP`, weball col 11), career = the **latest cycle's** value (a stock, not a sum). |
| `party_committees_career`, `leadership_pacs_career`, `labor_pacs_career`, `trade_pacs_career`, `membership_pacs_career`, `cooperative_pacs_career`, `other_unclassified_career` | **Other-committee contributions, career** — direct contributions from committees that are NOT corporate PACs and NOT the AIPAC PAC, classified from the same-cycle committee-master file: party = `CMTE_TP IN ('X','Y')`; leadership = `CMTE_DSGN == 'D'`; labor = `CMTE_TP IN ('Q','N')` + `ORG_TP == 'L'`; trade = Q/N + `T`; membership = Q/N + `M`; cooperative = Q/N + `V`; other_unclassified = everything else (§4). |
| `other_committees_total_career` | Sum of the seven other-committee classes. It EXCLUDES corporate PAC and AIPAC direct money, which stay in their own columns — the three families are disjoint by construction. |
| `*_earmark_transmitted_career` (7 columns) | Career-only earmark-transmitted breakouts, one per other-committee class, on the AIPAC/corporate earmark definition. |
| `all_ie_support_career`, `all_ie_oppose_career`, `all_ie_total_career` | **All independent expenditures about the person's race, staged IE cycles only** (`config.yaml` `cycles.udp`; earlier IE files are not staged — §8 item 20). Support and oppose from every registered committee, not just UDP. `all_ie_total = support + oppose + blank-direction rows`. Like UDP, this is spending *about* the race, never money given to the campaign. |
| `pro_israel_pac_career`, `pro_israel_ie_support_career` | **Pro-Israel PAC money, career — shown separately, never part of `total_accepted` or dirty money.** `pro_israel_pac_career`: counted direct contributions (the same rows and rules as the AIPAC and corporate columns) from any committee on the pro-Israel PAC list (`data/source/pro_israel_pacs.csv`, Track AIPAC's published list; `research/pro-israel-pacs.md`). `pro_israel_ie_support_career`: support-direction independent expenditures by listed committees about the person, staged IE cycles only. The list includes the AIPAC PAC and UDP, so these columns contain `aipac_pac_direct_career` and `udp_ie_support_career` — never add them together. **Bundled (conduit) checks are not covered**: a listed PAC forwarding individuals' earmarked checks reports them without a candidate ID, which neither the pas2 nor the committee-transfer bulk file carries (§8). |
| `self_funding_per_cycle`, `other_committees_per_cycle`, `all_ie_per_cycle` (JSON only; repr strings in the CSV) | Per-person, per-cycle breakdowns of those three families. `self_funding_per_cycle` carries the weball flow columns plus `coverage_end_date` per (candidate, cycle); `other_committees_per_cycle` carries the seven classes plus an `earmark_transmitted` sub-dict; `all_ie_per_cycle` carries support/oppose/total. Only cycles with a nonzero value are listed. Each sums to its career columns exactly (audited). |
| `pro_israel_per_cycle` (JSON; repr string in the CSV) | Per-person, per-cycle `pro_israel_pac` and `pro_israel_ie_support`; cycles with neither are omitted. They sum to the two career columns. |
| `all_ie_top_committees` (JSON only) | The top five committees per person by career all-IE total, with the support/oppose split; the committee name is taken from its largest single (candidate, cycle) total. Null for a person with no FEC ID; `[]` for people with no IE spending. |
| `data_as_of` | The snapshot date from `config.yaml`, on every row. |
| `data_notes` | Per-person notes carried from the money pulls (search outcome, multi-ID summation, oppose spending, name-attributed UDP rows, data gaps, special cases). See §5. |
| `per_cycle` (JSON only) | Per-person, per-cycle, per-candidate-ID breakdown of the five pas2/weball columns (`individual`, `aipac_pac_direct`, `aipac_earmark_transmitted`, `corporate_pac`, `corporate_earmark_transmitted`). Only nonzero cycles are listed. Sums to the career columns exactly (audited). |
| `udp_per_cycle` (JSON only) | Per-person, per-cycle UDP support (`udp_ie_support`) with `candidate_id`. Only cycles with nonzero support are listed. Sums to `udp_ie_support_career` exactly. A name-attributed entry (§4) carries `"attribution": "name_state_district_office_match; cand_id blank in FEC file"`, and its `candidate_id` is the person's roster FEC ID for that race. |

### AIPAC headline decision (read this before quoting any AIPAC figure)

The headline column `aipac_pac_direct_career` is the **total of the raw Schedule B rows**
from the AIPAC PAC — PAC own-money **plus** earmarked individual checks transmitted
through it. This was a deliberate, coordinator-approved choice: the raw-rows approach
captures bundled checks that FEC summary aggregates drop, and for some recipients the
summary understates what flowed through the PAC by orders of magnitude.

The headline figure is therefore **not** "the PAC's own money." Subtract
`aipac_earmark_transmitted_career` to get PAC own-money, and **always state which of the
two figures you are quoting.** The earmarked money is also inside the candidate's
`individual_contribution_total_career` (weball), because it is individuals' money — it
is counted in both columns by design, and the two must never be added together.

Related rules (`research/pull-log-a.md` §4): **negative earmark rows (voided or refunded
conduit earmarks) are excluded from every total**, because their originals are not in
pas2 and netting them creates phantom negatives. **Positive earmark rows are kept in the
headline** and broken out. Re-reported earmark rows (`ERMK:` memo text, amended filings
pointing at an earlier cycle's originals) are counted in the earmark column; they may
re-attribute money already counted under the originals, which cannot be matched reliably
(different transaction IDs) — see §8 item 4.

### UDP support-only rule

`udp_ie_support_career` counts `sup_opp = 'S'` rows only. Oppose spending is spending
*against* a candidate; netting it against support would be meaningless, so it is never
added to the support column and is recorded in `data_notes`. UDP spending against a
candidate's *opponent* is credited separately under §13.

---

## 3. Sources

**FEC bulk files are the source of truth for every figure.** The FEC API is used for
spot-checks and the freshness overlay only; OpenSecrets is a cross-check only (§6).

| Data | Source file(s) (staged under `data/raw/`) | Method |
|---|---|---|
| Individual contributions | `weball/weballYY.txt`, every career cycle | `TTL_INDIV_CONTRIB`, col 18, per (candidate, cycle), then across the person's candidate IDs — **exact-equal copies under two IDs in the same cycle counted once** (§8 item 15). Amounts summed as integer cents. |
| AIPAC PAC direct + earmarks | `pas2/<cycle>/itpas2.txt`, the PAC's active cycles | Rows from the AIPAC PAC with `TRANSACTION_TP IN ('24K','24P')`. Earmark rows: memo text containing `EARMARK` or starting `ERMK:`. |
| Corporate PAC | `pas2/<cycle>/itpas2.txt` joined to `cm/<cycle>/cm.txt`, every career cycle | pas2 `24K`/`24P` rows whose contributing committee satisfies `CMTE_TP IN ('Q','N')` and `ORG_TP IN ('C','W')` in the **same-cycle** committee master, unless a reviewed override (§4) classes it otherwise. |
| UDP independent expenditures | `ie/<cycle>/independent_expenditure_<cycle>.csv`, staged IE cycles | UDP rows with `sup_opp = 'S'`, summed by `cand_id` after dedup by `tran_id` (keep latest `receipt_dat`, tie-break highest `file_num`). See §4. |
| Self-funding + topline | `weball/weballYY.txt`, every career cycle | Weball cols (1-indexed): 6 `TTL_RECEIPTS`, 7 `TRANS_FROM_AUTH`, 8 `TTL_DISB`, 9 `TRANS_TO_AUTH`, 11 `COH_COP`, 12 `CAND_CONTRIB`, 13 `CAND_LOANS`, 15+16 loan repayments, 17 `DEBTS_OWED_BY`, 28 `CVG_END_DT`. Career flows are sums; cash on hand and debts owed by are the latest cycle's value (stocks). No weball column carries debts owed *to* the committee. The §8 item 15 correction also zeroes a dropped copy's cols 6–9 where they are a strict subset of the kept copy. |
| Other-committee contributions | `pas2/<cycle>/itpas2.txt` joined to the same-cycle `cm/<cycle>/cm.txt`, every career cycle | pas2 `24K`/`24P` rows whose contributing committee is NOT corporate and NOT the AIPAC PAC, classified by `CMTE_TP` / `ORG_TP` / `CMTE_DSGN` as in §2. The step re-derives the corporate and AIPAC totals and must match them to the cent. Diagnostics in `data/intermediate/other_committees_diagnostics.json`. |
| All independent expenditures | `ie/<cycle>/independent_expenditure_<cycle>.csv`, staged IE cycles | Every row whose spender is a **registered committee** (`spe_id` in the same-cycle `cm` file) and whose candidate is **identified** (`cand_id` non-blank), summed by (candidate, cycle) after dedup on (`spe_id`, `tran_id`) — NOT `tran_id` alone. Blank-`cand_id` rows are excluded from the published totals (§8 item 19). |
| Pro-Israel PAC money | `pas2/<cycle>/itpas2.txt` and the staged IE files, filtered to the committee IDs in `data/source/pro_israel_pacs.csv` | Direct: the counted committee contributions (§4) from listed committees. IE: counted support rows (`sup_opp = 'S'`) whose spender is listed. |

**Committee IDs** (AIPAC PAC, UDP, WinRed) are set in `config.yaml` (`committees`) and were
verified against the OpenFEC API (`research/fec-sources.md` §1). The AIPAC PAC and UDP
first filed in the 2022 cycle, so **there are no AIPAC PAC or UDP figures before 2022** —
earlier cycles are legitimately $0 for those columns, not missing data. Do not backfill
pre-2022 "AIPAC money" from other pro-Israel PACs; they are separate committees.

**The `oppexp` files are NOT Schedule E.** The FEC `oppexpYY.zip` bulk files are Schedule
B **operating-expenditure** files — no candidate column, no support/oppose column. No
`oppexp` data is used for any figure. The correct source is
`independent_expenditure_<cycle>.csv` from the FEC bulk-data index (`cand_id`, `spe_id`,
`sup_opp`, `exp_amo`).

**Roster sources:** 119th membership from `legislators-current.yaml`
(unitedstates/congress-legislators); 120th membership as in §1; returning former members
from `legislators-historical.yaml`; FEC IDs for 120th freshmen matched through the OpenFEC
API on office + state + district + party for the current cycle, with name-variant misses
fixed by hand and recorded in `data/source/manual_roster_notes.json`
(`research/roster-notes.md`).

**What is NOT used:** the FEC API totals endpoints for any dataset figure (unreliable —
§8 item 8); the `indiv` bulk files (weball already aggregates them); the `oth` bulk files,
except for a one-off refund check (§4); F3X summary line 23 (not a candidate-level
figure: it includes earmark pass-throughs and contributions to other committees).

---

## 4. How the money was pulled (method summary)

Full detail is in `research/pull-log-a.md` (pas2/weball) and `research/pull-log-b.md` (UDP).
The points that matter for interpreting the numbers:

- **Join key:** FEC candidate ID. A person with several IDs is summed across all of them
  and all cycles in range.
- **Amended-filing dedup (pas2):** dedup on `TRAN_ID` alone is **unsound** — some filers
  reuse line-number-style TRAN_IDs across reports for distinct contributions. Key:
  (`CMTE_ID`, `TRAN_ID` or `SUB_ID`, `CAND_ID`, `TRANSACTION_AMT`, `TRANSACTION_DT`,
  election), per cycle file, preferring non-memo rows, tie-break earliest `FILE_NUM`
  (`receipts/domain/committee_money.py`).
- **Memo rows are kept (pas2):** FEC guidance says memo items "should be included in your
  analysis," and blanket-excluding `MEMO_CD='X'` drops genuine redesignation entries. The
  dedup rule removes the true duplicates instead.
- **Refund netting:** negative pas2 rows are included in the sums, so the AIPAC and
  corporate columns are **net of refunds and voids as recorded by negative pas2 rows**.
  Whether 17Z refund rows hide further refunds was checked against the `oth` file for one
  cycle only (§8 item 10).
- **UDP dedup:** the IE files contain original and amended reports. Dedup by `tran_id`
  (latest `receipt_dat`, tie-break highest `file_num`). Two independent implementations
  of the rule must give identical totals in every cycle.
- **Blank-`cand_id` UDP support rows are name-resolved.** Where the filer left `cand_id`
  blank and `cand_name` + state + district + office match exactly one roster person, the
  support is attributed to that person and flagged in `data_notes` and `udp_per_cycle`
  (`attribution`). A match is used only where the person has no `cand_id`-bearing UDP
  support in that cycle, so nothing is counted twice. Blank-ID support for a non-roster
  candidate is excluded; blank-ID oppose rows are never counted as support. This is a
  disclosed judgment call (§8 item 7).
- **Committee classification follows the filed codes, except reviewed overrides.** A
  committee is classified by its `CMTE_TP` / `ORG_TP` / `CMTE_DSGN` as filed in the
  same-cycle committee master. The one exception is `config.yaml`
  `committees.class_overrides`: committee IDs whose class was set by a reviewed
  methodology decision, with the evidence in `research/corporate-classification.md`. An
  override applies in every cycle and beats every rule but the AIPAC PAC's. A conduit that
  forwards individuals' earmarked contributions is overridden to `other_unclassified`,
  never corporate: the money comes from individuals. Adding an override is a methodology
  decision, never a data fix.
- **Self-funding / topline (`receipts/store/self_funding.py`).** Reads the weball files and
  emits one row per (candidate, cycle) with the flow columns, the two stock columns and
  `coverage_end_date` (col 28). Career stocks take the latest cycle's value; a person with
  no weball rows at all has null stocks, not $0. The §8 item 15 extension is enforced in
  the step: if its recorded arithmetic stops matching the files, the step fails loudly.
- **Other committees (`receipts/store/other_committees.py`).** The same pas2+cm join and
  dedup key as the corporate pull, with the classification inverted: everything not
  corporate and not the AIPAC PAC, split into the seven classes of §2. `other_unclassified`
  takes Q/N PACs with a blank `ORG_TP`, other candidates' campaign committees, hybrid PACs,
  joint fundraisers, super PACs and conduits. Conduits (WinRed, ID in `config.yaml`) stay
  inside unclassified, never dropped, and are flagged in `data_notes` wherever nonzero.
  The step reconciles each person against weball col 26; residuals it cannot explain are
  recorded, never forced (§8 items 17–18).
- **All independent expenditures (`receipts/store/all_ie.py`; exact cents).** The same IE
  files as the UDP pull, every registered committee. Dedup key (`spe_id`, `tran_id`):
  `tran_id` alone is unsound because different spenders reuse transaction IDs. The filter
  — registered committee plus identified candidate — is what removes the large volume of
  bogus filings in the IE files; the excluded amounts per bucket are reported in
  `data/intermediate/all_ie_per_cycle.json`. The row-sum of the total column exceeds
  support + oppose by exactly the blank-direction rows, which count in the total only. The
  step reproduces the UDP pull's cycle totals exactly, and pins the current cycle's
  roster-targeted Senate / House and support / oppose split and the top 5 roster-targeted
  spenders (committee IDs and totals) in `baseline.json`; any change stops the build.
- **Collapse validation.** Where two roster rows are one person (§7), every per-cycle file
  must carry identical values for both keys, or the build fails. Roster-total sums over
  the pull files count such a person twice; the merged dataset rows do not.

---

## 5. Special rows

- **A person with no FEC candidate ID** (for example, an appointed senator who never ran
  for the seat) has every money column `"unknown"`, not 0, with a note saying so. Never
  treat them as $0 in averages or totals; they are excluded from roster sums and ranks.
- **A person with an FEC ID but no weball or pas2 rows** reads 0 with the note "no FEC
  activity found."
- **A self-funded campaign with $0 in the tracked columns** has raised nothing *from
  others*, not nothing at all. Describe it that way; the self-funding columns carry the
  rest.
- **A negative career total is kept as computed.** It arises when a later filing voids
  contributions whose originals are not in pas2 as 24K rows — the same structural
  asymmetry as the earmark voids in §2, but without earmark memo text, so no text-based
  rule can separate them. It is flagged in `data_notes` and ranks as filed.
- **UDP oppose spending** is in `data_notes` only, never in a support total (§2); credited
  opposition is its own column (§13).

---

## 6. Reconciliation and spot-checks

Every build reconciles and audits itself; the results are in the build output, and the
historical record is in `research/methodology-evidence.md` §6 and
`research/verification-log.md`.

- **Roster-wide sums.** The merged dataset's column totals are compared with the pull
  files' totals. The only differences allowed are the §7 collapse and the §8 item 15
  de-duplication, each exactly accounted for; nothing else is adjusted. The per-group
  de-duplication record is `data/source/dedup-applied.json`.
- **Internal consistency** (`receipts/validate/verify_dataset.py`): every staged person
  joins 1:1 to the roster; FEC IDs agree between roster and money files; `per_cycle`,
  `udp_per_cycle` and the three newer per-cycle lists sum to their career columns; the
  seven other-committee classes sum to their total; stock columns equal their latest
  cycle's value; independently recomputed UDP and opposition figures reproduce the pulls;
  CSV and JSON agree field by field.
- **Spot-checks against independent sources** use the FEC API candidate-totals endpoint
  (2-year-cycle rows only — the endpoint also returns cumulative `election_full=true`
  rows, and summing both double-counts), direct reads of the staged bulk files with
  fresh code, the Schedule E API (one copy per expenditure — §8 item 8), OpenSecrets
  (net receipts = gross receipts − refunds − offsets) and published reporting.
  **No dataset figure is changed on the basis of a spot-check**; every mismatch is traced
  to a convention or vintage difference and recorded.

---

## 7. Roster collapse — one person, two roster rows

When the source roster carries **two rows for the same person** — the same FEC candidate
ID and identical money in every file, typically one row recorded as 119th-only and one as
120th-only after a re-election — they are one person who served in the 119th and returns
in the 120th. The dataset collapses them into **one row** under the bioguide key, with
both Congresses' fields filled, and documents the fix in `data_notes`. The merge fails
loudly if the two rows' money ever differs (§4).

---

## 8. Known limitations — read before using these numbers

1. **The current cycle is partial, and the cutoff differs by column family.**
   Committee-money columns (corporate, AIPAC, other-committee — pas2), weball-derived
   columns (individual, self-funding, topline) and all-IE columns (UDP too) each run
   through their own coverage end date, judged from the snapshot and recorded in
   `config.yaml` (`verification.coverage_end`); they are not computed. Figures from
   different families are not directly comparable — independent expenditures typically
   run past the committee and candidate reports. Expect current-cycle totals to rise
   and some amounts to be amended at each re-pull (§15).
2. **120th results are media calls, uncertified** (§1); uncalled seats are `unknown`.
3. **AIPAC PAC and UDP first filed in the 2022 cycle.** Earlier cycles are $0 by
   construction, not missing data.
4. **Earmark treatment.** Negative (void) earmark rows are excluded (§2); positive
   earmarks are kept in the headline and broken out. Re-reported earmark rows may
   double-count originals from an earlier cycle; they cannot be matched reliably.
5. **The AIPAC total does not reconcile to the dollar with OpenSecrets.** The small
   residual is most likely snapshot and amendment timing, or the treatment of in-kind
   (24Z) rows, which the 24K/24P filter excludes. Immaterial but unresolved.
6. **The UDP total does not reconcile to the dollar with OpenSecrets.** Leading
   hypothesis: the bulk IE file carries the 24/48-hour notice copy, while Schedule E
   itemizations on F3X can be corrected later and run slightly lower. Settling it needs a
   full F3X pull with a registered key; not attempted. Not adjusted.
7. **Name-attributed UDP support** rests on name + state + district + office matching
   because the FEC file left `cand_id` blank (§4). An ID-only version would put those
   people at $0. The amounts and method are flagged per person.
8. **The FEC API double-returns Schedule E, and its totals endpoint is unreliable — do
   not use it for figures.** Each expenditure appears twice in the raw API — once as the
   24/48-hour notice (F24, `is_notice=true`) and once as the Schedule E itemization (F3X),
   same transaction ID and amount — so naive sums double. The bulk CSV carries one copy.
   `schedule_e/totals/by_candidate/` disagrees with the raw endpoint for an identical
   filter and matches neither universe, and the API period filter leaks across cycles.
9. **`research/fec-sources.md` §4 mislabeled the `oppexp` bulk files** as independent
   expenditures; the correct source is `independent_expenditure_<cycle>.csv` (§3).
10. **The 17Z refund check covered one cycle only** (§4). The other cycles' `oth` files
    were not downloaded. That result plus pas2 netting makes a large hidden refund
    balance unlikely, but it is not proven for the other cycles.
11. **The Schedule B API times out** on the queries this pull needs; the pas2↔oth
    cross-check and the OpenSecrets reconciliation (§6) were used instead.
12. **DFL is normalized to Democrat; 120th leadership is TBD** until elected (§1).
13. **Pre-1980 careers are out of scope.** FEC bulk files start in 1980.
14. **Weball double-counting warning (FEC documentation):** a candidate with several
    authorized committees that transfer funds between each other has that activity
    counted twice; subtract `TRANS_FROM_AUTH` (col 7) / `TRANS_TO_AUTH` (col 9) where both
    are present. `TTL_INDIV_CONTRIB` is a receipts breakout and is not affected by
    committee-to-committee transfers — but see item 15, the material version of this
    problem for this dataset.
15. **Weball repeats one committee's individual-contribution total under two candidate
    IDs.** For people who hold both a House and a Senate candidate ID, weball can carry
    the *identical* `TTL_INDIV_CONTRIB` under both IDs in the same cycle: the two rows are
    one principal committee's summary reported under two IDs, and the FEC API committee
    totals confirm the committee reports it once. Weball has no committee-ID column, so
    the link is established through the FEC API and pas2 recipient-committee IDs.
    **Correction:** in each (person, cycle) group, each distinct `TTL_INDIV_CONTRIB` value
    is counted once. The kept copy sits on the ID matching the office sought that cycle
    (the election-result `W` marker where present, else the person's chamber after the
    cycle, else the shared principal committee's designation); the dropped copy's
    `individual` is zeroed in `per_cycle`, while its AIPAC and corporate values are
    untouched — pas2 is transaction-level and does not repeat. Groups whose same-cycle
    amounts *differ* across IDs are separate committee totals and are not touched. Every
    decision is recorded in `data/source/dedup-applied.json` and applied as data, never
    re-derived. **Extension:** where the dropped row is a strict subset of the kept row in
    the financial columns too (identical cols 10–18, and kept-minus-dropped equal for
    receipts, transfers-from and disbursements), the dropped copy is zeroed for weball
    cols 6–9 as well; the expected arithmetic is recorded with the decision, and
    `receipts/domain/weball_double_counts.py` fails loudly if it ever stops matching.
16. **The roster is "current members plus the 120th incoming,"** not "everyone who served
    in the 119th" (§1). A member elected in a special election is counted from the
    Congress in which they are seated.
17. **Some other-committee totals fall short of weball.** For some people the
    pas2-derived other-committee total is lower than weball col 26 by more than the
    classes can explain. The step records a `PENDING RECONCILIATION` note in that person's
    `data_notes`, generated from its own validation so it always states the current
    figures; one named case is checked against the baseline every build. No figure is
    adjusted to force a match.
18. **Negative residual in the other-committee reconciliation.** For a few people the
    pas2-derived other-committee total plus corporate plus AIPAC exceeds weball col 26.
    The mechanism is unresolved (leading hypothesis: joint-fundraising-committee or
    transfer reporting, which needs the `oth` bulk file or F3 line-item work). Documented,
    not adjusted.
19. **Systematic blank-`cand_id` filers are excluded from all-IE.** Some large spenders
    (Congressional Leadership Fund, for one) file `cand_id` blank throughout, so their
    spending cannot be attributed by ID under the all-IE filter. Their name-resolvable
    amounts are reported as a diagnostic, never added to a published total. This is a
    filter consequence, not a judgment that the spending did not happen; name-based
    attribution for such filers is a follow-up.
20. **All-IE "career" means the staged IE cycles only** (`config.yaml` `cycles.udp`).
    Earlier IE bulk files exist on the FEC server but are not staged. Never describe an
    all-IE career figure as a lifetime total.
21. **Election outcome is derived from `in_120th` alone — "Not returning" is not
    "Lost".** The site shows Won (`in_120th = "yes"`), Uncalled (`"unknown"`) or Not
    returning (`"no"`) next to each person's party chip. The dataset has no outcome field,
    so a `"no"` cannot be split into lost vs retired vs didn't run vs left early, and the
    label does not guess; that needs the outcomes table (every candidate with a primary and
    general outcome). The party chip derives the same way: `party_120` when non-empty,
    else `party_119`; Democrat → D (blue), Republican → R (red), Independent → I (gray),
    any other label → a gray chip showing the label — always letter plus color, never
    color alone.
22. **Pro-Israel PAC money undercounts bundling and does not match Track AIPAC.** A
    listed PAC acting as a conduit (J Street is the largest) forwards individuals'
    earmarked checks on line 23 with no candidate ID, so neither bulk file carries them;
    the FEC API does (each PAC's Schedule B by recipient committee), but it is not part
    of the pinned snapshot. Track AIPAC also adds individual donors with a history of
    giving to listed PACs, a donor-matching model the tracker does not reproduce. Both
    gaps make these columns a lower bound of Track AIPAC's totals. The list is theirs,
    as published; whether a listed committee belongs on it is their judgment.

---

## 9. Reproducibility

- **Staged inputs** (what a rebuild consumes): the committed inputs in `data/source/`
  (legislators yaml, `historical_lookup.json`, `120th_roster.json`, `dedup-applied.json`,
  `manual_roster_notes.json`, `fec_lookup_results.json`, `baseline.json`) and the pinned
  FEC snapshot staged in `data/raw/`. Everything in `data/intermediate/` is regenerated by
  `python3 receipts/rebuild.py` and is gitignored.
- **Merge rule:** join on `person_key`; collapse as in §7; a person with no FEC ID reads
  `unknown`; every other figure comes from the money steps unchanged, except the
  recorded de-duplication of §8 item 15.
- **To refresh:** publish a new pinned snapshot ("FEC snapshot" workflow), stage it with
  `./fetch_snapshot.sh <tag>`, set `data_as_of`, run `python3 receipts/rebuild.py
  --rebaseline`, and review the diff of `data/source/baseline.json` (README, "Pinned
  snapshots and the baseline"). The FEC updates its bulk files in place, so a rebuild is
  reproducible only against a pinned snapshot. Uncalled seats and 120th leadership are
  roster updates, made separately.

---

## 12. Ranking — "how much money they've accepted"

**Dirty money, plainly — read this before the leaderboards.** "Dirty money" in this
tracker means money from three sources: corporate PACs, the AIPAC PAC, and UDP
independent expenditures that benefited the candidate (support + opposition credit).
Individual contributions are **not** dirty money: they are the normal way campaigns are
funded, from real people giving their own money, and a candidate can raise millions from
individuals and still be verified clean. Self-funding is the candidate's own money, and
other-committee money (party, labor, trade, leadership PACs) is also not dirty under this
definition. "Total accepted" — individual + corporate PAC + AIPAC direct — measures
fundraising **scale**, not dirtiness: it includes individual contributions, which are
most of what most campaigns raise. That is why the site's leaderboards and the default
table sort lead with dirty money (current cycle first, then career), not with total
accepted.

- **`dirty_career`** = `corporate_pac_career` + `aipac_pac_direct_career` +
  `udp_ie_total_benefit_career` — the career analog of `dirty_2026`. Null for a person
  with no FEC ID (money unknown, not zero).
- **Total accepted (career)** = individual contributions + corporate PAC money + AIPAC
  PAC direct. The earmark columns are subsets of their parents and are never added again.
  UDP independent expenditures are **not** accepted — that money was never given to the
  campaign — but UDP support is ranked in its own column.
- **Ranks** (`rank_total_accepted`, `rank_individual`, `rank_corporate_pac`,
  `rank_aipac_direct`, `rank_udp_support`, `rank_udp_opposing_opponents`,
  `rank_udp_total_benefit`, `rank_self_funding`, `rank_all_ie_support`,
  `rank_all_ie_oppose`, `rank_all_ie_total`, `rank_other_committees_total`): 1 = most
  money; ties share a rank (competition ranking: rank = 1 + the count of strictly greater
  values). Ranks run over every person; a person with no FEC ID is unranked. A negative
  total ranks as filed. Ranks are career only; there are no per-cycle ranks.

---

## 13. Opposition credit — UDP spending against a candidate's opponent

Attack spending that effectively benefits a candidate is counted as its own thing,
never blended into direct support or into "total accepted" (UDP money was never given
to any campaign). The AIPAC PAC has **no** Schedule E independent-expenditure activity in
the staged IE files, so there is no AIPAC opposition column; the rule runs for UDP only.

**Definitions (career, staged IE cycles — UDP did not exist before 2022):**

- `udp_ie_opposing_opponents_career` — UDP independent expenditures opposing other
  candidates in races where UDP backed exactly one candidate (see the rule), credited to
  that backed candidate.
- `udp_ie_total_benefit_career` — `udp_ie_support_career` +
  `udp_ie_opposing_opponents_career`: the UDP spending that worked in a person's favor.
- `rank_udp_opposing_opponents`, `rank_udp_total_benefit` — same convention as the other
  rank columns.

**The exactly-one-backed-candidate rule.** A race is one FEC cycle + office + state +
district + election phase (`ele_type`: P primary, G general, O other). For each
race-phase, UDP's backed candidates are those with UDP **support** rows in that phase. If
UDP backed exactly one, all of UDP's spending **opposing other candidates** in that phase
is credited to that one. If it backed zero, or two or more, **nothing is credited for that
phase**. Spending opposing the backed candidate themself is never credited: it is a
filing artifact, not opposition to an opponent.

**Why the phase, and why `ele_type`.** The phase comes from the filing's `ele_type`,
parsed on every row; expenditure dates cannot be used instead, because they are blank on
UDP's rows. Each `ele_type` code is its own phase, O included, with no special-casing.
Backing different candidates in different phases of one race is therefore not a
conflict: each phase is judged on its own. Within a phase the rule stays deliberately
conservative — it credits opposition only where the beneficiary is unambiguous.

**Credit outside the tracker.** When the backed candidate is not on the roster, the
credit is computed but appears in no row. Opposition spending in a phase with no unique
backed candidate is credited to no one. Both buckets are reported in
`data/intermediate/opposition-computed.json`.

**Method notes.** Source: the staged IE files, UDP rows, same dedup rule as the support
pull. Blank-`cand_id` support rows are resolved by name index, then roster match, then —
for support rows only — a name-based identity where no FEC ID exists anywhere, which can
make a non-roster candidate the sole backed candidate in a phase. Blank-`cand_id` oppose
rows need no resolution: the oppose total is summed per race from the
office/state/district columns, and the opposed person's name is in the row. Computation:
`receipts/store/opposition.py`. Reconciliation: its deduped support + oppose totals must
match the UDP pull in every cycle, and its support totals must reproduce
`udp_ie_support_career` for every person.

---

## 14. 2026-cycle columns — "clean in 2026" and the primary-target list

**The 2026 cycle is PARTIAL.** Every 2026 figure is a partial-cycle figure, through each
family's coverage end date (§15), not a full-cycle total. Do not compare 2026 figures
head-to-head with full cycles.

**Definitions (2026 only):**

- `individual_2026`, `corp_2026`, `aipac_direct_2026` — summed from the `per_cycle`
  entries with `cycle == 2026`. People with more than one 2026 committee have their
  entries summed; the §8 item 15 de-duplication already applies to them.
- `udp_support_2026` — summed from `udp_per_cycle` entries with `cycle == 2026`.
- `udp_opp_credit_2026` — the person's §13 opposition credit for cycle 2026 only.
- `udp_benefit_2026` — `udp_support_2026` + `udp_opp_credit_2026`.
- `dirty_2026` — `corp_2026` + `aipac_direct_2026` + `udp_benefit_2026`: all money from
  corporate PACs, the AIPAC PAC, or UDP spending for the candidate in the 2026 cycle.
- `senate_class` — 1, 2 or 3 for every senator in either chamber, null for everyone else
  (derivation below).
- `self_funding_2026`, `cand_loans_2026`, `cand_contrib_2026`, `total_receipts_2026`,
  `total_disbursements_2026` — summed from `self_funding_per_cycle` entries with
  `cycle == 2026`. `cash_on_hand_2026` is that cycle's cash on hand (a stock; null when
  the person has no 2026 self-funding entry). `other_committees_total_2026` and
  `all_ie_support_2026` / `all_ie_oppose_2026` / `all_ie_total_2026` are summed the same
  way from their per-cycle lists. A person with no 2026 entry in a family reads an
  integer 0 in that family's 2026 columns (except `cash_on_hand_2026`, which reads null).
  `dirty_2026` never includes self-funding, other-committee money or all-IE spending.
- `clean_2026` — true when the member took no NET dirty money in 2026: `dirty_2026 <= 0`.
  A cycle test, not a career test. The rule is net because `dirty_2026` is the defined
  net total: a member whose 2026 refunds exceed their 2026 contributions reads clean, not
  dirty on a negative total. **Verification rule:** a person in the 120th is
  *unverified* (`clean_2026 = null`) when they have NO 2026 linkage evidence in ANY money
  source — no `per_cycle` / `udp_per_cycle` 2026 entry, and no `self_funding_per_cycle`
  2026 entry whose `coverage_end_date` falls in calendar 2026. Other-committee and all-IE
  2026 entries do NOT establish linkage on their own: they are third-party reports that
  can be filed under a stale ID. A person with linkage and no net dirty money is verified
  clean **with evidence**. **Unopposed exclusion:** a member who ran unopposed in 2026
  (`unopposed_2026`) with zero or negative net dirty money is **null, not clean** — $0
  dirty money in a race with no opponent is a structural zero, not a verified-clean
  campaign. A dirty unopposed member stays dirty. Implemented in
  `receipts/domain/clean_2026.py` and re-derived in `receipts/validate/verify_dataset.py`.
- `aipac_udp_flag_2026` — true when `aipac_direct_2026 > 0` OR `udp_benefit_2026 > 0`.
  Any AIPAC direct dollar or UDP benefit dollar flags the member under EVERY tolerance
  preset; the flag is not tolerance-based. A boolean on every row, including the nulls (a
  flag is a money fact, not a verdict).
- `tier_balanced_2026` / `tier_lenient_2026` — the member's tier under each corporate PAC
  tolerance preset: `clean` / `below_threshold` / `dirty`, or null exactly where
  `clean_2026` is null. `dirty` when the member is AIPAC/UDP-flagged OR their corporate
  PAC money is material under the preset; `below_threshold` (the middle tier) when they
  took corporate PAC money below the preset's thresholds — never called "clean", and the
  dollar amount is always shown (`corp_2026`); `clean` otherwise. The flag takes
  precedence, and the tiers are monotone: anyone clean under Strict is clean or
  below_threshold under Balanced / Lenient, never dirty. Presets (thresholds in
  `config.yaml` `verification.tolerance_presets`; Balanced is the default):
  - **Strict:** no thresholds of its own — it is `clean_2026` itself.
  - **Balanced** and **Lenient:** corporate PAC money counts as dirty only when BOTH
    `corp_2026 > corp_amount` AND `corp_2026 / total_receipts_2026 > corp_share`.
  - **Share denominator:** `corp_2026` (pas2) and `total_receipts_2026` (weball) must run
    through the same coverage end (§15), or the share is skewed. A non-positive
    `total_receipts_2026` leaves the share undefined, and the share test cannot pass.
  - **"Not dirty"** under a preset means clean or below_threshold.
  - **A count is never shown without its definition:** every clean or not-dirty figure
    is labeled with its preset. The default presentation is Balanced.
- `unopposed_2026` — true when every 2026 candidate ID of the person's in weball sits in a
  race where no OTHER candidate has total receipts over $0. A filed opponent with $0
  receipts does not make the race contested; a write-in who never filed does not appear.
  `unopposed_2026` is a race fact, independent of the clean verdict.
- `dep_share_2026` — `(corp_2026 + aipac_direct_2026) / (individual_2026 + corp_2026 +
  aipac_direct_2026)`: the share of the candidate's own 2026 fundraising that came from
  corporate PACs and the AIPAC PAC. UDP money is excluded from both sides. Null when the
  denominator is not positive.

**The race comes from the filing, not the roster.** The contested test keys each race from
the candidate's own weball row (office prefix + state + district). Roster districts can
differ from the FEC's (a delegate's roster district 0 vs the FEC's district 01, with stale
dormant IDs under 00), and a roster-district lookup can read a contested member as
unopposed. The site renders unopposed members as **Unopposed**, distinct from
**Unverified** (a data gap, not a race fact). Career-clean means no career dirty money: corporate PAC,
AIPAC PAC direct, UDP support and UDP opposition credit (career columns) are all zero. It
is derived from those career columns only and is untouched by the unopposed rule.

**Primary targets — the next cycle's watchlist.** The site's "Primary targets — <next
cycle>" tab lists incoming members of any party whose seat is up in the next cycle and
who took dirty money in their latest election. It is a watchlist, NOT a prediction of
who will be on the ballot: retirements are unknown and the next cycle's filings are
barely open. The rule is mechanical (dirty money only); the tracker does not judge
electability or anything else.

- **The rule** (`is_primary_target` in `receipts/domain/targets.py`): in the incoming
  Congress; seat up in the next cycle (`cycles.next` — every House seat, delegates
  included; a Senate seat when its `senate_class` is that cycle's regular class); and
  dirty in the latest-election record (§14b) under the preset — Strict: `dirty > 0`;
  Balanced / Lenient: that preset's tier is `dirty`. A member with no latest election
  is never a target. Ranked by latest-election `dirty`, descending.
- **It ignores the cycle picker.** The list always reads the latest election; the
  preset changes which members count as dirty, never the pool.
- **Columns:** party, seat, the election judged, and that election's dirty money,
  corporate PAC, AIPAC direct, UDP benefit and individual contributions, plus dirty
  career. The Balanced list is also written to `data/intermediate/primary-targets.md`.
- **How `senate_class` is derived.** From the legislators data
  (`data/source/legislators-current.yaml`): every Senate term carries a `class` field
  (1/2/3), so no date arithmetic is needed. A senator serving into 2026 takes their own
  latest term's class. A new senator with no Senate term takes the class of whoever held
  that seat during 2026 — the appointee or outgoing holder, whose term carries the seat's
  class. Computed in `receipts/transform/build_roster.py` and re-derived independently in
  `receipts/validate/verify_dataset.py`.
- **Why not derive the class from FEC data.** Every senator fundraises every cycle, so
  cycle presence separates nobody; "earliest Senate-ID cycle mod 6" breaks on
  special-election winners; and the FEC candidate-ID digits carry no class. The class
  lives in the legislators data, not the FEC data.
- **Front door.** The Data chapter carries a compact pointer whose button opens the
  targets tab by in-page navigation (`showTab('targets')`).

**Data gaps — read before quoting any 2026 zero.**

- **Corporate PAC money with $0 individual contributions** in 2026 is a likely
  missing-committee-linkage gap, not a real zero, for a member who raised from
  individuals in earlier cycles. A data note says so (`NO_INDIVIDUAL_MONEY_NOTE`); never
  present that $0 individual figure as fact.
- **An unlinked 2026 campaign leaves the member null (unverified).** Where a returning
  member's real 2026 campaign runs under a candidate ID the roster does not link, their
  2026 figures under the linked ID understate reality, so `clean_2026` is null — never
  clean, never dirty — with a data note. Linking the ID is a roster change that also
  moves career totals; it is never made unilaterally.

---

## 14a. Per-cycle records — every cycle judged the same way

Each person's `cycles` list (JSON) and `congress-money-tracker-cycles.csv` (one row per
person per cycle, keyed by `person_key` and `cycle`) hold one record for every cycle in which
the person has an entry in any money list (committee money, UDP support, self-funding and
topline, other committees, all-IE), plus the current cycle for everyone. A record carries
the same fields as the current-cycle columns of §14, without the year suffix, computed by
the same rules from that cycle's per-cycle entries and that cycle's weball races: the money
fields, `dirty`, `aipac_udp_flag`, `dep_share`, `unopposed`, `clean` and both tiers. The
current cycle's record equals its columns exactly (an audit checks it). Opposition credit is
that cycle's credit (§13). Two differences from the current-cycle columns: the
"unverified" rule (no data for an incoming member) applies to the current cycle only, since
an older record exists only where there is data; and a record exists for any cycle with
money, including a year the person was not on the ballot (off-cycle fundraising), so a
record is not by itself a judgement of that cycle's election.

## 14b. Up for election, and the headline verdict

**Up for election.** A cycle record's `up_for_election` is true when one of the person's
FEC candidacies for that cycle is filed for that cycle's election (the candidate file's
election year equals the cycle). The FEC files off-year fundraising against the next
election, so a senator raising money between races, or a Resident Commissioner of Puerto
Rico (four-year term), is not up in those cycles; a special election is filed for its own
year and counts.

**Headline verdict.** Each person's `verdict_cycle`, `clean`, `dirty`, `tier_balanced` and
`tier_lenient` come from one cycle record: the current cycle's when the person is up in it,
or when they are an incoming member whose seat is up this cycle (a House seat, or a Senate
seat whose class is up) and no filing places their next election later; otherwise their
latest cycle up. An incoming member whose seat is up but whose current campaign is not
linked in the roster therefore keeps the current cycle's verdict (unverified, §14), never an
older cycle's. A person never up in any cycle with data has no headline verdict (all null).
The current-cycle columns of §14 are unchanged and remain the current cycle's own verdict.

**What the site shows.** The site opens on the headline verdict ("Latest election"): every
board, chart, count and table reads the record of each person's `verdict_cycle`. The cycle
picker swaps in one cycle's records instead, from `cycles.picker_start` to the current
cycle; a person with no record for the picked cycle shows zero money and no verdict. The
primary-target list always reads the headline verdict (§14).

## 15. Coverage end dates by column family — and the re-pull plan

The bulk files behind this dataset do not all end on the same date (§8 item 1). The
cutoffs are judged from each pinned snapshot at its rebaseline and recorded in
`config.yaml` (`verification.coverage_end`):

| Column family | Source | `coverage_end` key |
|---|---|---|
| Individual, self-funding, topline | weball | `weball` |
| Corporate PAC, AIPAC, other-committee | pas2 | `committee_money_pas2` |
| UDP + all independent expenditures | IE bulk files | `independent_expenditures` |

**Re-pull plan.** After each FEC filing deadline that closes the cycle (the post-general
report and the year-end report): publish a new snapshot and rebaseline (§9). The
freshness layer (§16) covers the gap between the bulk coverage end and each re-pull;
after each re-pull, reconcile its snapshot sums against the new report and start a fresh
snapshot — never carry freshness figures forward into the dataset.

---

## 16. Freshness layer — new money since bulk coverage

The bulk rebuild is the canonical dataset, and it moves only when the bulk files move.
Between bulk pulls, late money arrives through three API routes the bulk files cannot see
yet. The freshness layer (`receipts/ingest/pull_freshness.py`, with
`receipts/ingest/pull_f6.py` and `receipts/ingest/pull_f24.py`) reports that money in
`data/intermediate/freshness_snapshot.json` — labeled by source and date, **never merged
into the dataset totals**. Research: `research/freshness-research.md`.

**The three routes:**

1. **Candidate totals** — `GET /v1/candidate/{id}/totals/?cycle=<cycle>`. Only as fresh as
   the latest processed report. **Trap:** `election_full=true` returns only the
   aggregate row (`cycle: null`), which can span several cycles. The driver uses the
   per-cycle row and flags `newer_than_bulk` only when its `coverage_end_date` passes the
   weball coverage end. The totals row also carries `last_debts_owed_to_committee` — the
   follow-up route for the `debts_owed_to_career` nulls (§2).
2. **Form 6 (48-Hour Notices)** — discovery via `GET /v1/filings/?form_type=F6&committee_id={id}`
   (metadata only; `candidate_id` is null on F6 rows), line items via the per-filing
   docquery CSV (`https://docquery.fec.gov/csv/{last3}/{file_number}.csv`, no key needed;
   F6N/F6A headers, F65 line items). There is no F6 bulk file. **Blocker:** `min_date` is
   silently ignored on `/v1/filings/`, so the pull pages with `sort=-receipt_date` and
   filters client-side. **Amendment chains:** the endpoint returns originals and their
   amendments; the pull drops any filing whose file number appears in another filing's
   `amendment_chain` and keeps only the latest version. Form 6 money is invisible to the
   totals endpoint and to Schedule A until the next regular report.
3. **24/48-hour independent expenditures (F24)** —
   `GET /v1/schedules/schedule_e/?filing_form=F24&committee_id=&candidate_id=&cycle=`. The
   F24-only filter is load-bearing: the endpoint double-returns (each expenditure once
   under its original F3X filing and again under the F24), so the unfiltered sum roughly
   doubles the true amount. The pull reconciles the F24-only set against the deduped
   unfiltered set and classifies the residual: rows filed on a regular report
   (`filing_form != F24`) are expected — they predate the 24/48-hour window — while an
   F24 row missing from the F24-only set would be a real discrepancy and should be $0.
   Form 5 needs no leg: it covers only unregistered spenders.

**Committee sweeps.** A bare `--all` also sweeps the spender committees listed in
`config.yaml` (`freshness.f24_committee_sweep`) committee-wide for the configured cycle
(on demand: `--f24-committee-sweep`). Each sweep reuses `pull_f24.sweep()` committee-only,
so no Schedule E logic is duplicated. Rows are attributed to roster people by
`candidate_id` (support/oppose from `support_oppose_indicator`); rows for candidates not
on the roster are summed separately (`non_roster_total` / `non_roster_n_rows`), never
attributed and never dropped; rows with an indicator other than S/O are summed as
unclassified. Raw rows are not embedded in the snapshot; the per-committee aggregates are
the record, reproducible with `pull_f24.py --committee <id> --cycle <cycle>`.

**Negative residuals at committee scale.** At committee scale the deduped unfiltered
total can come out BELOW the F24-only total: distinct rows sharing a dedup key
(expenditure date / amount / payee) collapse into one, and negative-amount rows
(refunds, corrections) enter the unfiltered set. The check that matters is the
unexplained residual — F24 rows missing from the F24-only set — which must be $0.

**Why the layer exists.** Weball and the totals endpoint run only through the latest
processed report; late candidate loans and contributions appear first, and sometimes
only, as Form 6 notices. The F6 leg finds money that neither the bulk files nor the
totals endpoint can show yet.

**Cadence and keys.** Final 20 days before an election: daily. A cycle in progress outside
the final 20 days: weekly. After each filing deadline: event-driven. DEMO_KEY is
spot-checks only — the driver refuses `--all` and `--f24-committee-sweep` on it.
Production needs a registered api.data.gov key in the `FEC_API_KEY` environment variable
(`config.yaml` `fec_api`, default `DEMO_KEY`).

**Rate limit.** A full `--all` run makes more calls than a standard registered key
allows per hour, so it hits HTTP 429 (`OVER_RATE_LIMIT`) part-way through. The fetch
helpers honor `Retry-After` when sent, otherwise back off exponentially up to a cap
(`config.yaml` `fec_api.retry`). The retry only buys time within the run; it does not make
the run fit under the limit. If the wait would exceed the run's budget, the step fails
loudly, naming the limit, rather than emitting a partial snapshot as if it were complete.

**A freshness failure never touches the dataset.** Freshness is an overlay that is never
merged into dataset totals, so a failed or partial run leaves the dataset, the site and
the rebuild unaffected.

---

## 17. Chamber composition charts — House waffle and Senate state tiles

The front door carries two composition charts, one per chamber, computed from the dataset
at render time. Placement: front door, after the clean story and before the finder;
stacked full-width, House first.

- **House: a 15-row × 29-column waffle grid, 435 bubbles, one per voting seat.** Bubbles
  fill one column at a time from left to right (top to bottom, then the next column),
  grouped Clean D, Dirty D, Dirty R, Clean R, then Unopposed, Unverified, Uncalled at the
  far right. The 435 total is heading text — a grid has no middle to put it in.
- **Senate: 50 tiles, one per state, in a 10 × 5 grid, each labeled with its two-letter
  state code.** Each tile is split in half, one half per senator; a split delegation
  colors each half for its own senator. Halves are ordered by party (D, R, I), then name,
  so a split is deterministic.
- **Encoding — clean is solid, dirty is black with the party color inside.** A clean seat
  is a solid party-color bubble (House) or half (Senate): Democrat blue (#1e40af),
  Republican red (#991b1b), Independent/other gray (#374151). A dirty seat is black with
  the party color inside: a centered dot on the House waffle, a dotted party-color pattern
  on the Senate tiles. Unopposed and unverified are gray hollow rings / white halves (not
  judged — $0 dirty money there is not a clean verdict); uncalled is a dashed gray ring /
  empty half.
- **House: 435 voting seats** = named voting members + uncalled seats. Non-voting
  delegates are **not plotted** — they have no vote — and are listed under the chart, so
  the chart's House clean counts can differ from the verified-clean counts in §14, which
  include delegates.
- **Senate: 100 seats** = named senators + uncalled seats. A state with an uncalled seat
  shows one half decided and one half uncalled.

The counts are computed at render, never typed, so they move with the data.
