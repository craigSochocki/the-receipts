# Opposition-credit pull log

**Date:** Nov 12, 2026. **Committee:** United Democracy Project (UDP), FEC `C00799031`.
**Outputs:** new columns `udp_ie_opposing_opponents_career`, `udp_ie_total_benefit_career`,
`rank_udp_opposing_opponents`, `rank_udp_total_benefit` in `congress-money-tracker.csv` /
`.json`; methodology §13; this log. **Script:** `work/compute_opposition.py`.
**Prior files backed up:** `work/congress-money-tracker-pre-opposition.csv` / `.json`.

## AIPAC PAC Schedule E check

AIPAC PAC (FEC `C00797670`) has **zero** Schedule E independent-expenditure rows in
the 2022, 2024, and 2026 bulk IE files. No AIPAC opposition column was built. (AIPAC
PAC is a traditional PAC: it gives direct contributions, it does not make independent
expenditures. The question of whether its direct contributions count as backing
evidence is therefore moot — there is no AIPAC IE spending to credit.)

## Rule applied

Race = FEC cycle + office + state + district. Backed candidate(s) = candidates with
UDP IE support rows in that race. Exactly one backed candidate → all UDP IE spending
opposing *other* candidates in that race credits to them. Zero or two-or-more backed
→ nothing credits. Spending opposing the backed candidate themself is excluded
(one row: $84,325.84 opposing Latimer, NY-16 2024 primary). The race key does not
split primary from general (documented limitation, methodology §13).

## Source and dedup

Same staged files as the support pull: `work/bulk/ie/<cycle>/independent_expenditure_<cycle>.csv`,
2022/2024/2026, `spe_id = C00799031`. Dedup by `tran_id`, keep latest `receipt_dat`,
tie-break highest `file_num` — identical rule to the support pull. Blank-`cand_id`
support rows resolved by name index, then roster match, then (support rows only) a
name-based identity where no FEC ID exists anywhere (Steven Irwin, PA-12 2022,
$660,319.30). Blank-`cand_id` oppose rows (30, all 2022: Cisneros, Garcia) need no
resolution — oppose totals are summed per race from the office/state/district columns.

## Reconciliation (all exact)

- Per-cycle deduped S+O totals match the earlier UDP pull to the cent in all three
  cycles: 2022 $26,107,515.77; 2024 $38,044,932.69; 2026 $54,322,881.51.
  All-cycles S+O: $118,475,329.97.
- The computation's support totals reproduce `udp_ie_support_career` exactly for all
  664 persons (0 mismatches). The Irwin name-based resolution was what closed the
  last $660,319.30 gap in the all-candidates support total.
- Merge check: roster opposing-opponents sum $28,281,982.23; total benefit sum
  $70,696,985.99 (= support $42,415,003.76 + opposing $28,281,982.23); CSV↔JSON
  agreement on the four new columns 0 mismatches; Alan Armstrong the only
  unknown/unranked.

## Results

- 23 races with UDP oppose spending; 15 credited, 8 not credited.
- Credited to roster persons: $28,281,982.23. Credited to non-roster backed
  candidates: $11,010,009.25 (Hollier $1,428,679.18; Weiss $4,615,288.76;
  Hernandez $1,642,139.53; Conyears-Ervin $59,748.29; Irwin $3,264,153.49).
- Not credited to anyone: $27,321,112.49. Largest: MI-Sen 2026 $20,903,437.57
  (backed=2: Stevens + Rogers); NJ-11 2026 $2,326,917.40 (backed=0 vs Malinowski);
  IN-08 2024 $1,567,918.74 (backed=0 vs Hostettler); TX-23 2024 $1,061,283.96
  (backed=0 vs Herrera); CA-42 2022 $515,088.43 (backed=0 vs Garcia); IL-07 2024
  $494,453.18 (backed=0 vs Collins); KY-04 2024 $319,783.30 (backed=0 vs Massie);
  VA-05 2024 $132,229.91 (backed=0 vs Good).
- Self-opposition excluded: $84,325.84 (one row, Latimer, NY-16 2024 primary).

## Test cases

1. **NY-16 2024:** UDP supported Latimer $4,682,560.29, opposed Bowman
   $9,865,492.96; Latimer the only backed candidate. Credit to Latimer:
   $9,865,492.96; combined benefit $14,548,053.25.
2. **MI-Sen 2026:** UDP opposed El-Sayed $20,903,437.57; supported Stevens
   $10,498,735.23 (primary) and Rogers $64,392.80 (general). Backed count = 2, so
   **nothing credited**. Rogers (S4MI00595) is not in the tracker roster.
   Stevens receives no credit from the anti-El-Sayed spending.

## Race-level record

`work/opposition-computed.json`: `credit_by_person`, `credit_detail` (all 15 credited
races with backed candidate, amount, and opposed names), `no_credit` (all 8
non-credited races with backed count and oppose total), `nonroster_credit`.
