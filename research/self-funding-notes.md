# Self-funding and topline — weball column map, verification and dedup notes

Moved verbatim from the header of `src/ingest/pull_self_funding.py` (Nov 22, 2026). The rules now live in `src/domain/campaign_finances.py` and `src/domain/weball_double_counts.py`; the figures below are as of the Nov 12, 2026 pull.

```text
Congress money tracker — self-funding + topline + transfers columns from FEC weball.

Reads the staged bulk weball files (data/raw/weball/weballYY.txt, cycles
1980-2026) and produces:
  - data/intermediate/self_funding_per_cycle.json — per person_key, per-cycle entries
  - data/intermediate/self_funding.csv — one row per person, career totals + 2026 values

The tracker's definition of total_accepted (individual + corporate PAC +
AIPAC direct) is UNCHANGED. The columns built here are separate and are
never blended into total_accepted. Self-funding for validation =
candidate_contributions + candidate_loans (career).

VERIFIED WEBALL COLUMN MAP (1-indexed, 30 columns; FEC all-candidates
file description, https://www.fec.gov/campaign-finance-data/all-candidates-file-description/,
fetched Nov 12, 2026, cross-checked against the staged rows below):
    6  TTL_RECEIPTS      -> total_receipts
    7  TRANS_FROM_AUTH   -> transfers_from_auth
    8  TTL_DISB          -> total_disbursements
    9  TRANS_TO_AUTH     -> transfers_to_auth
   10  COH_BOP           -> (not output; beginning cash, for reference only)
   11  COH_COP           -> cash_on_hand (ending cash)
   12  CAND_CONTRIB      -> candidate_contributions
   13  CAND_LOANS        -> candidate_loans
   14  OTHER_LOANS       -> (not output; non-candidate loans)
   15  CAND_LOAN_REPAY   -> loan_repayments, candidate part
   16  OTHER_LOAN_REPAY  -> loan_repayments, other-loan part
   17  DEBTS_OWED_BY     -> debts_owed_by
   18  TTL_INDIV_CONTRIB -> (not output here; already in money_per_cycle.json;
                             used only as the dedup guard, see below)
   28  CVG_END_DT        -> coverage_end_date
  loan_repayments in the output = col 15 + col 16 (total loan repayments,
  matching the FEC API `loan_repayments` field).
  debts_owed_to has NO weball column: the 30-column weball file carries only
  DEBTS_OWED_BY (col 17). It is therefore output as null (unknown) for every
  row, never as zero. The FEC API does carry it (`last_debts_owed_to_committee`);
  the spot-check below found $0.00 for Constantino in both cycles, but that
  single API value is NOT backfilled into the weball-derived columns.

CONSTANTINO VERIFICATION (candidate ID H6NY21157, roster person
anthonyconstantinonyhouse). His weball rows:
  2024: receipts $2,600,000.00, disb $293,113.17, cand_loans $2,600,000.00,
        coh_cop $2,306,886.83, debts_owed_by $2,600,000.00, cvg 12/31/2024
  2026: receipts $14,464,951.19, disb $14,472,853.54, cand_loans $14,400,000.00,
        coh_cop $2,298,984.48, debts_owed_by $17,000,000.00,
        trans_to_auth $640,000.00, indiv $0.00, cvg 10/14/2026
  Career sums reproduce the FEC API year-end figures exactly:
    total receipts $17,064,951.19, candidate loans $17,000,000.00,
    total disbursements $14,765,966.71, cash on hand $2,298,984.48 (2026),
    transfers to auth $640,000.00.
  NOTE on the "$14.4M vs $17M loans" gap: the $17M figure is the CAREER
  total (2024 $2.6M + 2026 $14.4M), not a 2026-only figure. The FEC API
  candidate-totals endpoint (DEMO_KEY, Nov 12, 2026) returns, per cycle,
  values IDENTICAL to weball for both 2024 and 2026 (receipts, disbursements,
  loans, cash, debts owed by/to, transfers, loan repayments — all exact to
  the cent, including last_debts_owed_to_committee $0.00). There is NO
  weball-vs-API discrepancy at matched coverage dates. The genuine caveat
  is timeliness only: the staged 2026 weball snapshot covers through
  10/14/2026 (pre-general); post-general / year-end 2026 filings are not
  yet in it, so 2026 figures are a lower bound against later filings.

FLOWS vs STOCKS (career aggregation):
  Flows (summed across cycles): candidate_contributions, candidate_loans,
    loan_repayments, total_receipts, total_disbursements,
    transfers_from_auth, transfers_to_auth.
  Stocks (NOT summed; latest cycle's value): cash_on_hand (COH_COP) and
    debts_owed_by (outstanding balance at cycle end). Summing them would
    double-count — e.g. Constantino's debts_owed_by is $2.6M in 2024 and
    $17.0M in 2026; the career value is $17.0M (2026), not $19.6M.
    `cash_on_hand_cycle` / `debts_owed_by_cycle` record which cycle the
    career stock value came from (the person's latest cycle with a weball
    row). The 2026 stock columns are blank when the person has no 2026
    weball row (no report), not zero.

DEDUP (chamber-switchers with two candidate IDs in the same cycle):
  data/source/dedup-applied.json records 90 (person, cycle) groups where weball
  repeats the identical TTL_INDIV_CONTRIB under both IDs. Checked here
  against the raw weball rows: in 89 of the 90 groups the dropped copy is
  identical to the kept copy on EVERY financial column (6-18, 26, 27, 29,
  30), so the same double-count hits these columns too and the recorded
  correction is applied column-by-column (dropped copy zeroed wherever it
  equals the kept copy). ONE exception — John R. Curtis, 2024 (kept
  S4UT00282, dropped H8UT03238): cols 10-18 are identical (so the dropped
  copy IS zeroed for cash/contrib/loans/repayments/debts), but cols 6-9
  differ (receipts $5,748,063.58 vs $5,640,855.75; transfers from auth
  $1,369,004.86 vs $1,261,797.03; disbursements $5,346,220.15 vs
  $5,239,012.32; transfers to auth $107,982.83 vs $3,300.00). The recorded
  dedup decision was scoped to TTL_INDIV_CONTRIB and does not cover those
  four differing columns — BUT the extension recorded on the Curtis 2024
  entry in dedup-applied.json (`extend_to_columns_6_9`) covers them:
  kept-minus-dropped is $107,207.83 EXACTLY for cols 6, 7 and 8, and cols
  10-18 are byte-identical, so the dropped row is a strict subset of the
  kept row and counting both double-counts the House row's activity. The
  extension zeroes the dropped copy for cols 6-9 as well, guarded by the
  recorded expected cents; the guard fails loudly if the staged file ever
  stops matching. Effect on roster totals: receipts -$5,640,855.75,
  disbursements -$5,239,012.32, transfers-from-auth -$1,261,797.03,
  transfers-to-auth -$3,300.00. Any OTHER group whose dropped copy differs
  from the kept copy on any column is still flagged in data_notes and in
  the JSON meta block, NOT silently corrected.
  Guard: the kept row's col 18 and each dropped row's col 18 must equal
  the recorded dedup `amount`, else the script fails loudly.

UNKNOWN vs ZERO: Alan Armstrong (person_key A000383) has no FEC candidate
  IDs in the roster (appointed senator, never ran for the seat). His
  career and 2026 values are null (blank in the CSV, null in JSON), NOT
  zero — matching the dataset convention ('unknown'). Persons WITH IDs but
  no weball rows get 0.00 for flow columns and blank for stock columns.

Amounts are summed as integer cents (same convention as pull_money.py);
outputs are dollars with 2 decimals.
```
