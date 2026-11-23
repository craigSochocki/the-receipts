# All independent expenditures — rules, checks and findings

Moved verbatim from the header of `src/ingest/pull_all_ie.py` (Nov 23, 2026), when the pull moved onto the store as `receipts/store/all_ie.py`. The rules now live in `receipts/domain/outside_spending.py` and `receipts/domain/blank_candidates.py`.

```
All-independent-expenditures pull for the Congress money tracker.

Reads the staged bulk IE files (`data/raw/ie/<cycle>/
independent_expenditure_<cycle>.csv`, cycles 2022/2024/2026 from config
`cycles.udp`) and produces:
- `data/intermediate/all_ie_per_cycle.json` — per candidate, per-cycle support/oppose
  totals for ALL identified candidates (not just roster members), plus a
  per-committee breakdown of the top spenders.
- `data/intermediate/all_ie.csv` — one row per roster person with career all-IE
  support, oppose and total, plus the same for the latest cycle (2026).
  "Career" here means the covered cycles (2022+2024+2026) only: no IE
  files are staged for earlier cycles, so these are NOT full-career
  totals. Ranks are computed later; this script writes totals only.

These columns are SEPARATE from `total_accepted` (individual + corporate
PAC + AIPAC direct). Nothing in this script touches that definition.

Filter rules (applied in this order, per cycle, on deduped rows):
1. Dedup by (spe_id, tran_id) — keep the latest `receipt_dat`,
   tie-break highest `file_num`. This is the pull_udp /
   compute_opposition rule, scoped to the filer: the FEC file
   description says TRA_ID is "unique within the specific filing", and
   the FEC's own dedup guidance is to sort "by filer and date and
   targeted candidate". Tran IDs are NOT globally unique — e.g. `SE.4117`
   is shared by many committees — so deduping by tran_id alone across
   all committees wrongly drops real spending (it understates the
   roster total by ~$105M in 2022, ~$147M in 2024, ~$455M in 2026).
   Within one committee (UDP) the two keys coincide, which is why the
   UDP pull's tran_id-only dedup was correct there.
2. REGISTERED committee: `spe_id` must be present in the same-cycle
   committee master (`data/raw/cm/<cycle>/cm.txt`, col 1). This kills
   the bogus billions: "Committee of 300" C00800508, C00874586,
   C00785352, "Warren Buffet" C00946087, C00944025, etc. are in no cm
   file for their cycle.
3. IDENTIFIED candidate: non-blank `cand_id` that resolves to a real
   candidate — present in ANY staged weball file (all cycles
   1980-2026, `data/raw/weball/weball*.txt`) OR one of the roster's
   FEC candidate IDs. Same-cycle weball alone is NOT a valid test: real
   roster IDs are missing from every weball file (Glenn Ivey H2MD04315,
   Laura Gillen H4NY04158), while the bogus IDs (Akhlaghy H2NY05118 /
   P40007304 / P40019226, Bettis H6FL11274) are in NO weball file and
   not in the roster. Blank `cand_id` rows are EXCLUDED from the
   published totals (see the blank-attribution diagnostic below).
4. Support (`sup_opp='S'`) and oppose (`sup_opp='O'`) are summed
   separately, never netted. Rows with blank `sup_opp` (a handful,
   ~$10k/cycle) count in the total only and are reported.

Blank-cand_id attribution (DIAGNOSTIC ONLY, not added to totals):
the pull_udp name-index + roster-fallback machinery is run over the
registered blank rows and the amounts are reported, but they are NOT
added to any published total. Reason: the validation targets for this
pull (see below) exclude them — with global name-index attribution,
Congressional Leadership Fund alone would add ~$199M of 2026 oppose
spending and appear as the #2 roster-targeted spender, while the
validated top-5 list has no CLF and matches the no-attribution figures
to the dollar. CLF files `cand_id` blank systematically (2029 blank
rows in 2024, 787 in 2026); attributing a systematic blank-filer by
name needs a coordinator decision, not a silent inclusion. The
diagnostic amounts are in the JSON under
`blank_attribution_diagnostic`.

Form-type double-count check (F24 vs F3X trap):
the FEC API Schedule E endpoint returns every expenditure twice (an
F24 24/48-hour notice + the F3X Schedule E itemization, same
transaction_id). This pull uses the BULK files, not the API. The bulk
file has NO form-type column, so F24/F3X cannot be separated by form
— but pull-log-b §7 verified the bulk file carries ONE copy (the
notice copy: its file_num/image_num match the F24 filing), and the
(spe_id, tran_id) dedup removes any same-transaction repeat. Proof in
this run: the UDP 2024 deduped S+O total reproduces the tracker's
$38,044,932.69 TO THE CENT; if the file double-counted across form
types it would be ~2x. A near-duplicate scan (same committee +
candidate + exp_date + amount + sup_opp under DIFFERENT tran_ids, with
different image numbers = different filings) is also run and reported;
those rows are treated as separate expenditures, NOT collapsed —
collapsing them would break the exact UDP 2024 reproduction (UDP
2024 alone has 27 such groups, $2,850,554.43).

Validation targets (from the task brief — the coordinator's prior
filtered, deduped figures; printed, not hard-failed except UDP):
- UDP 2024 deduped S+O = $38,044,932.69 (HARD check, to the cent).
- Roster-targeted IE: 2022 $635.2M / 2024 $959.1M / 2026 $2,264.3M.
- Top 2026 non-UDP roster-targeted spenders: NO GOING BACK PAC
  $202.5M (O), HMP $146.7M (O), WinSenate $131.1M (O), TEXAS PAC
  $112.2M (O), DEFEND AMERICAN JOBS $70.7M (S).
- 2026 roster split: Senate $1,376.4M vs House $887.9M;
  oppose $1,479M vs support $785M.

Coverage: staged IE files cover 2022/2024/2026 only. Per the FEC
independent-expenditures file description (fetched Nov 12, 2026),
historical data is available beginning with the 2010 cycle, and the
bulk-data index publishes `independent_expenditure_YYYY.csv` per cycle
— so 2010/2012/2014/2016/2018/2020 files exist and are NOT staged
here. Expanding to them is a follow-up (each file is ~14-19 MB);
pre-2010 cycles have no such file.
```
