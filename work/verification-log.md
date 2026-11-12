# Verification log — weball de-duplication + independent spot-checks

**Date:** November 12, 2026. **Agent:** verification/fix agent (subagent, no live browser).
**Scope:** (Part 1) verify the weball double-count mechanism found in the merge
(methodology §8.15) and, if proven, apply the de-duplication; check whether the
AIPAC/corporate columns double-count for chamber-switchers. (Part 2) independent
spot-check of the final dataset for 5 members against FEC.gov totals and OpenSecrets.
**Files changed:** `congress-money-tracker.csv`, `congress-money-tracker.json`,
`methodology.md`, `work/money_pas2_weball.csv`, `work/money_per_cycle.json`;
new files `work/dedup-applied.json` (per-group correction record) and this log.

## Verdicts up front

- **Weball double-count: PROVEN on all 3 required examples (Bell, Gallego, Schiff),
  plus the hardest edge case (Curtis). De-duplication APPLIED.**
  Corrected roster-wide individual total: **$8,763,847,353.73** (was $9,215,623,369.07;
  correction **$451,776,015.34** across 32 persons / 90 (person, cycle) groups).
- **AIPAC/corporate columns: NO double-count.** Per-candidate-ID amounts differ in every
  duplicated cycle (pas2 is transaction-level); those columns are untouched.
- **Spot-checks: all 5 career individual totals match the FEC API exactly, to the cent.**
  AIPAC direct (own-money) matches SpectrumVote's direct column in-window for all 5;
  corporate-PAC 2024 figures re-derived from raw pas2+cm match exactly for 3 of 3 checked;
  UDP support $0 for all 5, confirmed in the staged IE files. **No dataset figure was
  changed on the basis of the spot-checks** — every apparent mismatch was a convention or
  vintage difference (detailed below).

---

## Part 1a — Mechanism evidence (raw weball rows)

Weball layout (30 columns, 1-indexed): col 1 `CAND_ID`, col 6 `TTL_RECEIPTS`,
col 7 `TRANS_FROM_AUTH`, col 8 `TTL_DISB`, col 9 `TRANS_TO_AUTH`, col 18
`TTL_INDIV_CONTRIB`, col 19–20 office state/district, cols 21–25 election-result
fields, col 28 `CVG_END_DT`, col 29 `INDIV_REFUNDS`, col 30 `CMTE_REFUNDS`.
**Important correction to the task brief: weball has NO committee-ID column.** The
committee link for each example was therefore established two other ways: the FEC API
(`candidate/{id}/committees/` and `committee/{id}/candidates/`) and pas2
recipient-committee IDs (`OTHER_ID` on committee-contribution rows). Both agree.

### Example 1 — Wesley Bell, 2024 (and 2026)

Raw rows, `weball24.txt`:

```
H4MO01134|BELL, WESLEY MR|C|1|DEM|5386197.6|0|4952276.71|0|0|433920.89|100|0|0|0|0|0|5136025.24|MO|01||||||244750|125|12/31/2024|24982|0
S4MO00250|BELL, WESLEY|C|1|DEM|5386197.6|0|4952276.71|0|0|433920.89|100|0|0|0|0|0|5136025.24|MO|00||||||244750|125|12/31/2024|24982|0
```

Identical in **every amount field** (`TTL_RECEIPTS` $5,386,197.60, `TTL_DISB`
$4,952,276.71, cash on hand $433,920.89, `TTL_INDIV_CONTRIB` **$5,136,025.24**, refunds
$24,982, coverage end 12/31/2024); the rows differ only in `CAND_ID`, name suffix
("MR"), and office district (01 vs 00). Same in 2026: both IDs $3,221,101.71, every
amount field identical, coverage end 10/14/2026.
Committee: API `candidate/H4MO01134/committees/` → `C00842336` BELL FOR MISSOURI,
designation P (principal). The API committee linkage for the Senate ID returned 0 rows
(an API gap, not evidence against), so it was closed via pas2: the single 2024 pas2 row
under `S4MO00250` carries `OTHER_ID = C00842336` (BELL FOR MISSOURI), as do 91 of the
190 House-ID rows. **Same committee under both IDs: proven.**
Cross-check: FEC API committee totals for `C00842336`, cycle 2024:
individual contributions **$5,136,025.24**, receipts $5,386,197.60 — the committee
reports the figure **once**.

### Example 2 — Ruben Gallego, 2024

Raw rows, `weball24.txt` (amount fields only): `TTL_RECEIPTS` $64,657,199.96,
`TRANS_FROM_AUTH` $2,910,010.25, `TTL_DISB` $65,722,622.25, `TTL_INDIV_CONTRIB`
**$59,385,707.27** under both `H4AZ07043` (ICI=I, district 03) and `S4AZ00139`
(ICI=O, district 00); every amount field identical, coverage end 12/31/2024.
Committee: API returns `C00558627` GALLEGO FOR ARIZONA (P) for **both** IDs, and
`committee/C00558627/candidates/` lists both IDs. Pas2 2024: 704 rows under the Senate
ID carry `OTHER_ID = C00558627`. **Same committee: proven.**
Cross-check: API committee totals for `C00558627`, 2024: individual **$59,385,707.27**,
receipts $64,657,199.96 — reported once.

### Example 3 — Adam B. Schiff, 2024

Raw rows, `weball24.txt`: `TTL_RECEIPTS` $48,149,196.78, `TRANS_FROM_AUTH` $536,367.79,
`TTL_DISB` $62,791,130.49, `TTL_INDIV_CONTRIB` **$45,110,628.66** under both `H0CA27085`
(ICI=I, district 30) and `S4CA00555` (ICI=O, district 00); every amount field
identical, coverage end 12/31/2024.
Committee: API returns `C00343871` SCHIFF FOR SENATE (P) for **both** IDs, and
`committee/C00343871/candidates/` lists both IDs. Pas2 2024: 323 rows under the Senate
ID carry `OTHER_ID = C00343871`. **Same committee: proven.**
Cross-check: API committee totals for `C00343871`, 2024: individual **$45,110,628.66**,
receipts $48,149,196.78 — reported once.

### Edge case examined — John R. Curtis, 2024 (the one non-identical fingerprint)

Curtis is the only nonzero duplicate group where the two weball rows differ in amount
fields other than election results: `TTL_INDIV_CONTRIB` is identical ($2,319,425.97)
but the Senate row's receipts/disbursements are $107,207.83 higher — exactly the extra
`TRANS_FROM_AUTH` on the Senate copy (a transfer between his authorized committees).
Both IDs share principal committee `C00647339` JOHN CURTIS FOR UTAH (API, both
directions), and that committee's own 2024 API totals are individual **$2,319,425.97**,
receipts $5,640,855.75 (= the House row's receipts). So the individual-contribution
figure is still one committee's money reported twice; the receipts difference is
transfer accounting on the Senate copy, not separate individual fundraising.
**De-duplicated like the rest.**

### The other non-identical fingerprints (8 groups)

Of the 90 nonzero duplicate groups, 80 have rows identical in every field except
`CAND_ID`/name/`CAND_ICI`/district. The other 10 differ in at least one more field;
all 10 were inspected field-by-field:

- Baldwin 2012, Cotton 2014, Daines 2012, Durbin 1996, Gillibrand 2010, Heinrich 2012,
  Hirono 2012, Reed 1996: **all amount fields identical**; differences are only in
  election-result fields (`PRIM_ELECTION`/`GEN_ELECTION` = `W`, `GEN_ELECTION_PRECENT`)
  recorded on the Senate-ID row, plus name variants and `CAND_ICI`. Same committee
  summary; the `W` marker identifies the office actually sought. De-duplicated.
- Curtis 2024: see edge case above. De-duplicated.
- Markey 1986: both IDs $0.00 in every amount field that matters (receipts differ, but
  the duplicated amount is $0). No correction needed; excluded from counts.

### Scope reconciliation (why the counts are 32/90, not 33/92)

An independent recomputation straight from the 24 raw weball files (not from the staged
per-cycle file) finds 33 persons / 92 (person, cycle) groups with an exact-equal
`TTL_INDIV_CONTRIB` under two IDs — but two of those groups are $0.00 under both IDs
(Markey 1986, Stutzman 2018) and contribute $0.00, so the nonzero scope is **32 persons /
90 groups**, matching the merge's count. The recomputed correction is
**$451,776,015.34** and the corrected roster total **$8,763,847,353.73**, both exactly
matching the merge's unverified reference figures. The staged `money_per_cycle.json`
grouping gives the same 90 groups and the same dollar total, and staged-vs-raw-weball
individual sums agree for all 665 staged persons (0 mismatches) — so the pull itself
was arithmetically correct; only the double-counting treatment was wrong.
Separately, 158 (person, cycle) groups across 59 persons have *unequal* amounts under
two IDs in the same cycle (157 unequal-only + 1 both, Kevin Cramer 2018, where the
duplicate $3,721,721.43 sits alongside a $0 third ID). Those were **not** touched.

### Two-House-ID cases (not chamber-switchers)

Three duplicate groups involve two House IDs, not House+Senate. All three share one
principal committee (API-verified), so the same logic applies: Onder 2024/2026 — both
IDs → `C00870238` ONDER FOR CONGRESS; Mark Harris 2026 — both IDs → `C00850404` MARK
HARRIS FOR CONGRESS; Stutzman 2016 — both IDs → `C00484683` STUTZMAN FOR SENATE
(the shared principal is Senate-designated; 2016 was his Senate run).

## Part 1b — De-duplication applied

**Rule:** for each (person, cycle) group, each distinct `TTL_INDIV_CONTRIB` value is
counted once. Groups with differing same-cycle amounts are summed in full, unchanged.
**Kept-copy attribution** (which candidate ID keeps the value in `per_cycle`; career
and per-cycle totals are identical either way): election-result `W` marker on exactly
one duplicate row (8 groups); else the person's chamber in the Congress seated the
January after the cycle — Senate ID for sitting Senators (74 groups, including the 4
2026 groups for Daines/Lummis/Marshall/Peters, who are Senators in the 119th but not
the 120th); else the shared principal committee's designation (4 groups: Carter, Hunt,
Moulton 2026 and Stutzman 2016 — all Senate-designated, API-verified); else the first
House ID in roster order (Bell 2024/2026, Harris 2026, Onder 2024/2026 — House members
whose Senate/extra ID is a filed echo). Per-group record: `work/dedup-applied.json`.
The dropped copy's `individual` is set to `0.00` in `per_cycle`; its AIPAC/corporate
values are untouched, and the entry itself is kept (it still carries real pas2 money).

**Corrected totals:** roster-wide individual **$8,763,847,353.73** (was $9,215,623,369.07;
correction $451,776,015.34). All other roster totals unchanged to the cent
(AIPAC $7,567,773.00; AIPAC earmark $191,573.00; corporate $972,228,584.00; corporate
earmark $26,850.00; UDP $42,415,003.76). Largest corrections are Rosen ($63,718,624.44),
Gallego ($63,279,147.51), Peters ($59,861,076.56) and Schiff ($53,566,066.22); Schiff's
corrected career total is $108,856,103.98 (was $162,422,170.20), which moves the #5
career-individual spot to Cruz ($152,064,880.63) — methodology §4 updated accordingly.

| Person | Cycles de-duplicated | Correction |
|---|---|---|
| Jacky Rosen | 2018, 2020, 2022, 2024, 2026 | $63,718,624.44 |
| Ruben Gallego | 2024, 2026 | $63,279,147.51 |
| Gary C. Peters | 2014, 2016, 2018, 2020, 2022, 2024, 2026 | $59,861,076.56 |
| Adam B. Schiff | 2024, 2026 | $53,566,066.22 |
| Martin Heinrich | 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026 | $21,556,178.25 |
| Tom Cotton | 2014, 2016, 2018, 2022, 2024, 2026 | $21,138,884.05 |
| Chris Pappas | 2026 | $21,080,102.32 |
| Todd Young | 2016, 2018, 2020, 2022, 2024, 2026 | $16,862,580.33 |
| Marsha Blackburn | 2018, 2020, 2022, 2024, 2026 | $15,795,074.22 |
| Tammy Baldwin | 2012 | $13,477,549.03 |
| Ben Ray Luján | 2020, 2022, 2024, 2026 | $12,919,381.08 |
| Andy Kim | 2024, 2026 | $12,665,555.99 |
| Kirsten E. Gillibrand | 2010 | $10,880,702.00 |
| James Lankford | 2014, 2016, 2018, 2020, 2022, 2024, 2026 | $9,838,845.71 |
| Wesley Bell | 2024, 2026 | $8,357,126.95 |
| Kevin Cramer | 2018, 2020, 2022, 2024, 2026 | $7,831,782.72 |
| Seth Moulton | 2026 | $6,292,010.46 |
| Steve Daines | 2012, 2022, 2024, 2026 | $4,281,475.98 |
| Mazie K. Hirono | 2012 | $4,136,454.00 |
| Richard J. Durbin | 1996 | $3,337,700.00 |
| Roger Marshall | 2022, 2024, 2026 | $3,298,319.55 |
| John R. Curtis | 2024, 2026 | $2,726,916.78 |
| Ted Budd | 2024, 2026 | $2,328,741.41 |
| Marlin A. Stutzman | 2016 | $2,061,718.00 |
| Earl L. "Buddy" Carter | 2026 | $1,944,348.93 |
| Jack Reed | 1996 | $1,511,660.00 |
| Harriet M. Hageman | 2026 | $1,473,761.71 |
| Wesley Hunt | 2026 | $1,452,679.26 |
| Robert F. Onder, Jr. | 2024, 2026 | $1,207,106.37 |
| Jim Banks | 2026 | $1,135,451.66 |
| Mark Harris | 2026 | $897,255.50 |
| Cynthia M. Lummis | 2022, 2024, 2026 | $861,738.35 |
| **TOTAL (32 persons, 90 groups)** | | **$451,776,015.34** |

New career individual totals for the three worked examples: Bell $8,357,126.95 (was
$16,714,253.90); Gallego $68,028,228.72 (was $131,307,376.23); Schiff $108,856,103.98
(was $162,422,170.20). Each affected person's `data_notes` in the CSV/JSON records the
correction (cycles + dollar amount).

**Post-fix verification (re-run after applying):** `per_cycle` sums to the career
columns with **0 mismatches** (all 664 persons × 5 columns); `udp_per_cycle` sums to
`udp_ie_support_career` with **0 mismatches**; CSV ↔ JSON agreement field-by-field
**0 mismatches**; exactly 32 CSV rows changed (individual total + `data_notes` only),
90 `per_cycle` entries changed (`individual` only), staged `money_pas2_weball.csv`
changed in 32 rows (individual only). No other column or row changed.

## Part 1c — AIPAC / corporate double-count check for switchers

Per-candidate-ID amounts from `money_per_cycle.json` (all values are the dataset's
own figures; the point is whether the two IDs carry the *same* amount, which would
indicate duplication, or *different* amounts, which indicates distinct transactions):

| Person / cycle | AIPAC House ID | AIPAC Senate ID | Corporate House ID | Corporate Senate ID |
|---|---|---|---|---|
| Bell 2024 | $10,000 | $0 | $41,800 | $0 |
| Bell 2026 | $15,000 | $0 | $288,250 | $0 |
| Gallego 2024 | $0 | $0 | $76,825 | $194,799 |
| Gallego 2026 | $0 | $0 | $7,500 | $326,000 |
| Schiff 2024 | $5,000 | $0 | −$14,500 | $9,900 |
| Schiff 2026 | $0 | $0 | $0 | $8,000 |
| Curtis 2024 | $10,000 | $0 | $656,502 | $447,200 |
| Curtis 2026 | $0 | $0 | $27,500 | $253,500 |

**Finding: no duplication.** In every duplicated cycle the per-ID AIPAC and corporate
amounts differ (often one side is $0 while the other is substantial; Gallego 2024
corporate is $76,825 vs $194,799 — two different transaction sets). Pas2 rows are
attributed to distinct candidate IDs, so the AIPAC and corporate columns stand as-is.
Career per-ID splits confirm the same pattern (e.g. Schiff career AIPAC House $12,900
vs Senate $0; corporate House $2,032,984 vs Senate $20,400).

---

## Part 2 — Independent spot-checks (5 members)

Checked Nov 12, 2026. Mix: House D, Senate R, Senate D, House R, one 120th freshman
(James Talarico, TX Senate, first-time member, FEC ID `S6TX00479`, verified in the
roster). Dataset figures are the **corrected** (post-dedup) values.

### Individual contributions — career

| Person | Dataset (corrected) | FEC API candidate totals (2-yr cycle rows) | FEC.gov candidate page | OpenSecrets | Verdict |
|---|---|---|---|---|---|
| Nancy Pelosi (House D, `H8CA05035`) | $73,415,016.76 | **$73,415,016.76 — exact** | — | 2024 "raised" (net receipts) $10,003,159 — matches dataset-derived net $10,003,159.38 exactly (see note 1) | **Match** |
| Ted Cruz (Senate R, `S2TX00312`) | $152,064,880.63 | **$152,064,880.63 — exact** | — | 2024 6-yr "raised" $105,557,321 vs dataset-derived 6-yr net $106,112,320.79 (−0.52%, note 2) | **Match** |
| Charles E. Schumer (Senate D, `S8NY00082`+`H0NY16010`) | $109,755,537.29 | **$109,755,537.29 — exact** | — | 6-yr 2022 gross receipts: Ballotpedia/FEC $41,884,545 vs dataset-derived $41,884,544.60 — match (note 3) | **Match** |
| Elise M. Stefanik (House R, `H4NY21079`) | $30,071,951.49 | **$30,071,951.49 — exact** | — | 2024 "raised" (net receipts) $15,444,946 — matches dataset-derived net $15,444,945.59 exactly (note 1) | **Match** |
| James Talarico (120th freshman, Senate D-TX, `S6TX00479`) | $139,776,602.82 | **$139,776,602.82 — exact** | **$139,776,602.82 — exact** (fec.gov candidate overview: "Total individual contributions", coverage 09/08/2025–10/14/2026) | Oct 2026 article: $127.3M raised through Sep 30 (vintage; dataset runs through Oct 14). Ballotpedia: "$146 million" raised = FEC total receipts $146,349,912.38 (note 4) | **Match** |

**Notes on the individual comparisons**

1. **OpenSecrets "raised" is a net figure, not the dataset's gross individual figure.**
   OpenSecrets states its figures "reflect net amounts, which subtract refunds, offsets
   and loan repayments." Reproducing that arithmetic from the FEC API totals rows
   (receipts − contribution refunds − offsets to operating expenditures) gives Pelosi
   2024 $10,223,363.88 − $218,817.34 − $1,387.16 = **$10,003,159.38** vs OpenSecrets
   $10,003,159, and Stefanik 2024 $15,467,577.50 − $7,100.00 − $15,531.91 =
   **$15,444,945.59** vs OpenSecrets $15,444,946 — exact to the dollar in both cases.
   OpenSecrets publishes no single career-individual-contributions figure, so the
   career comparison runs through the FEC API (exact for all five); the 2-year
   "raised" figures corroborate the same underlying receipts.
2. **Cruz 6-year window (−0.52%).** OpenSecrets' Senate "raised" tables use a 6-year
   window (2019–2024 receipts for the 2024 table). Dataset-derived 6-year net is
   $106,112,320.79 vs OpenSecrets $105,557,321. The gap is a vintage/netting
   difference: OpenSecrets' 2024 table is "based on data released by the FEC on
   September 16, 2025" while this pull is Nov 12, 2026 (amendments filed in between
   move the window), and the exact netting rule for the 6-year window is not published.
   The underlying per-cycle individual figures match the FEC API exactly, so the
   dataset figure **stands**; no correction.
   (For reference, the same 6-year check on the 2020 table gives OpenSecrets
   $54,749,210 vs dataset-derived $54,547,118.36, −0.37% — same pattern, opposite sign.)
3. **Schumer 2022.** No OpenSecrets 2022-cycle "raised" figure for Schumer surfaced in
   search (the 2022 totals page is JS-rendered). Substitute check: Ballotpedia's
   2022 NY-Senate page (FEC data, as of Dec 31, 2022) lists Schumer receipts
   $41,884,545 — that is the **6-year election window** (2018+2020+2022 cycles), and the
   dataset's weball receipts for those cycles sum to $41,884,544.60. Match.
   A second OpenSecrets Pelosi table value ($11,518,822, same page, different table)
   could not be reconciled to any receipts/net combination and is not used; the
   $10,003,159 value is the one that matches the net-receipts arithmetic exactly.
4. **Talarico.** OpenSecrets' $127.3M is through Sep 30, 2026 quarterly filings; the
   dataset's weball26 file runs through Oct 14, 2026 filings (coverage end 10/14/2026),
   hence the higher figure — vintage, not error. Ballotpedia's "$146 million" is total
   receipts ($146,349,912.38), of which individual contributions are $139,776,602.82.
   Talarico's committee also reported $518,805 in PAC/committee contributions (press,
   from FEC data) — the dataset's corporate-PAC figure for him is $0.00 because none of
   those PAC contributions came from corporate-connected PACs under the Q/N + C/W rule;
   not an error, a definition difference.

**FEC API trap documented (found during this check).** The candidate-totals endpoint
(`/v1/candidate/{id}/totals/`) returns **two rows per cycle**: a 2-year row
(`cycle` set, `election_full=false`) and a cumulative election-period row
(`cycle=null`, `election_full=true`, e.g. Cruz 2019–2024 = $96,809,924.23, which is
exactly the sum of his 2020+2022+2024 2-year rows). A naive sum over all returned rows
double-counts — Pelosi sums to $146,830,033.52, exactly 2× the true $73,415,016.76.
Career totals above use the 2-year rows only. (This is a separate quirk from the
Schedule E totals-endpoint problem already in methodology §8.8.)

### AIPAC PAC direct — career

OpenSecrets publishes no AIPAC-PAC-only career figure (its "pro-Israel" totals are
composites of many PACs and individual donors). The independent check below uses
SpectrumVote's AIPAC PAC page (FEC-based; splits **direct** PAC-own-money from
**bundled** earmarked individual gifts; window Jan 2023–latest 2026 reports), which
tests the dataset's headline−earmark split directly: SpectrumVote "direct" should equal
dataset (headline − earmark) over the same window.

| Person | Dataset headline (career) | Dataset own-money, Jan 2023–2026 window | SpectrumVote direct (Jan 2023–2026) | Verdict |
|---|---|---|---|---|
| Pelosi | $12,900 (2022 $7,900 + 2024 $5,000) | $5,000 (2024 only; earmark $0) | $5,000 | **Match** |
| Cruz | $10,000 (2024) | $10,000 (earmark $0) | $10,000 | **Match** |
| Schumer | $2,100 (2022) | $0 (2024/2026 $0) | — (absent from list = $0 in-window) | **Match** |
| Stefanik | $14,200 (2022 $4,200 + 2024 $5,000 + 2026 $5,000) | $10,000 (2024 $5,000 + 2026 $5,000) | $10,000 | **Match** |
| Talarico | $0 | $0 | — (absent = $0) | **Match** |

Second confirmation of the split: Josh Gottheimer's dataset own-money for 2024+2026 is
$20,000.00 (career headline $93,630 − earmark $65,730 = $27,900 own; 2022 own $7,900),
and SpectrumVote direct for Gottheimer is $20,000 — exact. Wesley Bell likewise:
dataset own-money in-window $20,000 (2024 $10,000 + 2026 $15,000−$5,000 earmark) vs
SpectrumVote direct $20,000 — exact.
**Bundled-definition caveat (not an error):** SpectrumVote's "bundled" column is far
larger than the dataset's `aipac_earmark_transmitted` column (Cruz $630,404 vs $0;
Stefanik $425,594 vs $0; Pelosi $3,322 vs $0; Bell $4,693,385 vs $5,000). The two
count different things: SpectrumVote counts all individual donations routed through
AIPAC's fundraising platform, while the dataset's earmark column counts only pas2 rows
from the AIPAC PAC itself whose memo text identifies an earmark (`EARMARK OF …` /
`ERMK:`). The dataset's definition is stated in methodology §2; the headline column
(PAC disbursements + memo-identified earmarks) is unaffected. The OpenSecrets profile
of Stefanik corroborates the same split from the other side: "She received $5,000 from
AIPAC itself" in 2024 (dataset 2024 AIPAC $5,000, earmark $0), while "individuals who
donated through AIPAC" gave $204,000 — the broader platform-based cohort.

### Corporate PAC — career

OpenSecrets publishes no corporate-PAC-only figure (its per-candidate PAC totals cover
all PAC types, and its industry groupings are not the Q/N + C/W rule). Check performed
instead: **fresh independent re-derivation** from the staged `pas2/2024/itpas2.txt` +
`cm/2024/cm.txt` files with new code (not the pull script, and without the pull's
amended-filing dedup rules) for the 2024 cycle, for three of the five:

| Person | Dataset corporate-PAC 2024 | Re-derived 2024 | Verdict |
|---|---|---|---|
| Pelosi | $31,500 | $31,500.00 | **Match (exact)** |
| Cruz | $101,133 | $101,133.00 | **Match (exact)** |
| Stefanik | $451,450 | $451,450.00 | **Match (exact)** |

Career corporate totals (Pelosi $5,307,970; Cruz $2,083,018; Schumer $7,895,596;
Stefanik $2,913,750; Talarico $0) were not re-derived cycle-by-cycle; the 2024
re-derivation plus the exact per-cycle FEC individual matches give no reason to doubt
them. No correction made.

### UDP independent-expenditure support — career

All five: dataset **$0.00**. Verified by direct read of the staged IE files
(`bulk/ie/2022|2024|2026/independent_expenditure_*.csv`, filtered
`spe_id = C00799031`): **zero UDP rows** — support or oppose — name any of the five
candidate IDs in any of the three cycles. **Match; no correction.** (Talarico's race
did see heavy outside spending — Ballotpedia reports $467M in satellite spending in the
TX-Sen race — but none of it was UDP support for Talarico; UDP's 2026 file runs through
Oct 31, 2026 and contains no Talarico rows at all.)

### Spot-check summary

| Person | Individual | AIPAC direct | Corporate PAC | UDP support | Overall |
|---|---|---|---|---|---|
| Pelosi | exact (FEC API) | exact (SpectrumVote, in-window) | 2024 exact (re-derived) | $0 confirmed | **Stands as-is** |
| Cruz | exact (FEC API) | exact (SpectrumVote, in-window) | 2024 exact (re-derived) | $0 confirmed | **Stands as-is** |
| Schumer | exact (FEC API) | exact (SpectrumVote, in-window) | not re-derived this pass | $0 confirmed | **Stands as-is** |
| Stefanik | exact (FEC API) | exact (SpectrumVote + OpenSecrets profile) | 2024 exact (re-derived) | $0 confirmed | **Stands as-is** |
| Talarico | exact (FEC API + fec.gov page) | $0 confirmed | $0 (definition note) | $0 confirmed | **Stands as-is** |

No dataset figure was changed on the basis of Part 2. Mismatches found: none that
indicate error. Apparent gaps (OpenSecrets 6-year windows within ~0.5%; Talarico
vintage; SpectrumVote bundled vs dataset earmark; Talarico PAC $518,805 vs corporate
$0) are all convention, vintage, or definition differences, each explained above.

---

## Files changed (this verification)

| File | Change |
|---|---|
| `congress-money-tracker.csv` | 32 rows: `individual_contribution_total_career` corrected; `data_notes` gained a correction note. Nothing else changed. |
| `congress-money-tracker.json` | Same 32 rows + the 90 affected `per_cycle` entries (`individual` zeroed on dropped copies). Nothing else changed. |
| `methodology.md` | §2 individual definition (dedup rule + corrected total); §3 source table; §4 top-5 individual (Cruz replaces Schiff); §6 reconciliation table + verification spot-checks; §8.15 rewritten as corrected; §9 merge rule (dedup exception). |
| `work/money_pas2_weball.csv` | 32 rows: `individual_contribution_total_career` corrected (staged inputs now match final). |
| `work/money_per_cycle.json` | 90 entries: `individual` corrected (dropped copies zeroed). |
| `work/dedup-applied.json` | **New.** Per-group correction record: person, cycle, amount, kept/dropped candidate ID, reason. |
| `work/verification-log.md` | **New.** This file. |

## Open items / things not done

- OpenSecrets' JS-rendered member pages could not be read by text fetch (pages return
  almost no text), so OpenSecrets career figures were checked via its search-indexed
  "Fundraising Totals" tables and news articles instead, plus SpectrumVote for AIPAC.
  No OpenSecrets career-individual figure exists in a single published number anyway.
- The SpectrumVote "bundled" vs dataset "earmark" definition gap (see above) is
  disclosed, not resolved — resolving it would need a methodology decision about what
  counts as an AIPAC earmark (pas2 memo text vs platform-routed individual gifts).
- Pre-correction copies of the final files were not retained in the workspace (the
  correction is fully specified by `work/dedup-applied.json` + this log + §8.15).
- As before: 2026 cycle is partial; re-pull after it closes.
