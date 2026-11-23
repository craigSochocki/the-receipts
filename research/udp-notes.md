# UDP support pull — rules and note text

Moved verbatim from the header of `src/ingest/pull_udp.py` (Nov 23, 2026), when the pull moved onto the store as `receipts/store/udp.py`. The blank-ID rules now live in `receipts/domain/blank_candidates.py` and `receipts/store/udp_rows.py`.

```
UDP independent-expenditure pull for the Congress money tracker.

Reads the staged bulk IE files (`data/raw/ie/<cycle>/
independent_expenditure_<cycle>.csv`, cycles from config `cycles.udp`)
and produces, per roster person:
- `data/intermediate/money_udp.csv` — career UDP support total + `data_notes`
  (665 rows, roster order).
- `data/intermediate/money_udp_per_cycle.json` — per-cycle UDP support breakdown
  (the input `merge_dataset.py` reads for `udp_per_cycle`).

This is the script the original UDP pull (see `research/pull-log-b.md`) never
had saved: methodology §6 records that the merge independently recomputed
these figures from the staged IE files with the same rules and reproduced
`money_udp.csv` exactly (0 mismatches). The rules, all from pull-log-b:

- Committee: UDP (`spe_id` from config `committees.udp`). Support rows
  only (`sup_opp = 'S'`) count toward a person's support total; oppose
  rows (`sup_opp = 'O'`) are never added to any total — they are recorded
  in `data_notes` only, for the people UDP spent against.
- Dedup by `tran_id`: keep the latest `receipt_dat`, tie-break highest
  `file_num` (the IE files carry original + amended reports).
- Blank `cand_id` rows are resolved, in order: (1) a name index built
  from deduped non-blank rows, keyed on (candidate name, state, district,
  office); (2) a roster fallback on last/first name + state + district,
  which only fires when exactly one roster person matches and that person
  has exactly one FEC ID. Support rows that still have no ID get a
  name-based identity (`__name__:NAME|STATE|DISTRICT|OFFICE`) so they
  still count as a backed candidate for the opposition-credit race rule —
  they can never map to a roster person. Oppose rows that still have no
  ID stay unresolved (30 in 2022, all Cisneros/Garcia) and are never
  counted as support.
- Amounts resolved from a blank `cand_id` are flagged: the
  `udp_per_cycle` entry carries
  `"attribution": "name_state_district_office_match; cand_id blank in FEC
  file"` and the person's note records the attributed amount. (2022 only:
  Davis $2,102,637.82, Foushee $2,128,196.18, Mullin $588,768.26.)

Note text, per person (verified against the committed file):
- No FEC IDs: `No FEC candidate ID on file; not searchable in IE data.`
- Support > 0: `UDP support by cycle (<current> partial) — <cycle>:
  $<amt>; ...` (cycles with support, ascending), then
  ` Summed across <n> candidate IDs.` when the person has > 1 FEC ID,
  then one ` Includes $<amt> of <cycle> support identified by candidate
  name/state/district; the FEC file left cand_id blank for those rows.`
  per name-attributed cycle, then the oppose suffix.
- Support = 0: `No UDP support spending found in <cycles> IE files.`
  (cycles joined with `/`), then the same `Summed across` suffix, then
  the oppose suffix.
- Oppose suffix (when UDP spent against the person):
  ` UDP also spent $<amt> opposing this person (excluded from support
  total).`

The per-cycle reconciliation totals are printed and checked against
config `verification.udp_prior_cycle_totals` (deduped S+O, all
candidates). If an old `money_udp.csv` is present it is compared
(informational only — a re-pull on newer filings is expected to differ).
```
