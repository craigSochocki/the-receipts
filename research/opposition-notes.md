# Opposition credit — rule and checks

Moved verbatim from the header of `src/transform/compute_opposition.py` (Nov 23, 2026), when the step moved onto the store as `receipts/store/opposition.py`. It also printed spot checks to the console; the NY-16 2024 self-opposition ($84,325.84 opposing Latimer) and the PA-12 2022 name-only backed candidate (Steven Irwin) are recorded in methodology.md, and the MI-Sen 2026 phase case is described in the header below.

```
Opposition-credit computation for the Congress money tracker.

Rule (conservative, per task): for each committee and race phase (FEC cycle +
office + state + district + election phase), determine the committee's backed
candidate(s) from its own IE SUPPORT rows in that phase. If it backed EXACTLY
ONE candidate, credit all of that committee's IE spending OPPOSING other
candidates in the same phase to that one backed candidate. If it backed zero
or two or more, credit NOTHING for that phase.

The phase is the filing's `ele_type` (P primary, G general, O other), already
parsed on every row. Expenditure dates cannot be used instead: the date is
blank on 100% of UDP rows in all three cycles. Each ele_type code is its own
phase, O included — no special-casing. Backing different candidates in the
primary and the general therefore credits each phase's opposition spending to
that phase's backed candidate (MI-Sen 2026: Stevens in the primary, Rogers in
the general).

Sources: staged bulk IE files data/raw/ie/<cycle>/independent_expenditure_<cycle>.csv
(cycles from config cycles.udp). Dedup by tran_id, keep latest receipt_dat, tie-break
highest file_num (same rule as the UDP support pull). AIPAC PAC (see config
committees.aipac_pac) has ZERO Schedule E rows in all three cycles, so no AIPAC
opposition column is built.
```
