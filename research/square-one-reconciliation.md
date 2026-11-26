# Square-one reconciliation — every figure vs the committed dataset

How this was built: the square-one derivation (`receipts/square_one/`,
run by `python3 -m receipts.square_one.derive`) re-derives every figure
from the pinned snapshot (`fec-bulk-2026-11-22` +
`fec-candidates-2026-11-23`) and the API evidence on disk, then diffs
every figure against the committed dataset
(`congress-money-tracker.csv` / `.json`). The diff covered **130,944
figures** — every per-cycle record field, every headline field, and
every career column, for all 664 roster rows. **2,045 differ**, and
every one of them is in the six fields below. Nothing else differs:
every cycle record, every headline verdict, and every other career
column reproduces the dataset exactly, to the cent.

The full machine-readable diff is `/tmp/recon-diff.json` (regenerable
with `/tmp/recon_diff.py`); `data/intermediate/square_one/derived.json`
is the CLI output it was built from.

## Headline

| What changed | People affected | Total dollars (derived − dataset) |
|---|---|---|
| AIPAC direct, career, variant B (API direct, JFC excluded) | 436 | +$100,750,523.67 |
| AIPAC direct, career, variant A (API direct + JFC shares) | 438 | +$101,472,292.96 |
| Pro-Israel PAC direct, career, variant B | 568 | +$117,378,692.65 |
| Pro-Israel PAC direct, career, variant A | 568 | +$122,541,925.30 |
| Transfers from, career, with the shared-committee dedup | 21 | −$20,781,632.49 (removed double-count) |
| Transfers to, career, with the shared-committee dedup | 14 | −$3,635,503.57 (removed double-count) |

Per-cycle AIPAC direct (variant B) differs for 949 (person, cycle)
pairs: 268 in 2022, 340 in 2024, 341 in 2026. The correction grows by
cycle: 2022 +$10,683,213.75; 2024 +$43,369,940.91; 2026
+$46,710,095.29. Variant A adds JFC shares on top: $0 in 2022,
+$91,350.00 in 2024, $618,840.97 in 2026.

Largest career AIPAC increases under variant B: Wesley Bell
+$5,447,816.45; Susan Collins +$3,348,020.18; George Latimer
+$2,892,972.35; Jacky Rosen +$1,817,565.15; Josh Gottheimer
+$1,799,012.16; Jared Moskowitz +$1,604,880.10; Donald G. Davis
+$1,602,827.18; Ritchie Torres +$1,582,850.01; Debbie Wasserman
Schultz +$1,489,244.58; Juan Ciscomani +$1,380,521.67.

## 1. The AIPAC / pro-Israel correction (the point of the exercise)

The dataset's AIPAC direct comes from pas2, which carries only the
conduit's own contributions — not the earmarked individual money it
transmits. The square-one derivation substitutes the FEC API Schedule B
figures (by-recipient aggregates, classified by the conduit rules) for
cycles 2022–2026, keeping pas2 for earlier cycles. The increase is the
earmarked money the bulk files never carried. Two people differ between
the variants on AIPAC career and no one else does: Elijah Crane and Paul LePage have
JFC-only AIPAC money, so their careers are higher under variant A than
under variant B; every other person is identical across variants on AIPAC (pro-Israel
amounts differ more widely, through the non-AIPAC JFC shares).

Two edge cases in the correction, both documented rather than adjusted:

- **One career decrease: Mike Collins, $5,000 → $0.** His pas2 row is
  a $5,000 AIPAC contribution to "COLLINS FOR CONGRESS" (his committee
  C00544684). The API's by-recipient row for that name totals
  $19,146.43, but the name is shared by more than one committee — the
  committee-master lookup for 2026 has no entry under it, and the
  cross-cycle fallback returns a different Collins's committee
  (C00909440, a Florida candidate not on the roster), so the money is
  unattributed rather than guessed. The December row-level pull
  attributes by recipient committee ID and resolves this exactly.
- **Four negative per-cycle figures under the correction** (Blumenthal
  2024 −$475.00, Mike Lee 2024 −$475.00, Troy Nehls 2026 −$2.00, Ralph
  Norman 2026 −$11.14): lone voids. Pas2 excludes voided earmarks, so
  it shows $0; the API nets the void, so the corrected figure is
  negative. The voids are real filings; the negative is the API net,
  not an error.

Coverage behind the correction: 6,237 by-recipient rows processed
(direct 3,726 rows; JFC 198; other 264; ambiguous 44 rows,
$2,312,137.02; unmatched 2,004 rows, $27,899,235.81, mostly
JFC/party/vendor/other money plus name-collision cases like Collins).
53 (committee, cycle) files are missing, all cycle 2022: the 2022
evidence covers AIPAC plus eight main conduits only, so 2022
corrected figures for the other listed committees are $0 where pas2
had money — the 2022 correction is a lower bound, and the December
run fills it. The memo layer ($2,393,323.26 across listed PACs) is
tracked separately and belongs to neither variant.

## 2. The shared-committee transfer dedup

The transfers pilot found one case (Barr): two candidate IDs sharing
one principal committee double-count transfers. The square-one
derivation generalizes it: **29 people** have two IDs sharing one
principal committee (almost all House→Senate redesignations), 163
report rows, $20,781,632.49 of transfers-from and $3,635,503.57 of
transfers-to removed as double-counted. Largest career reductions:
Andy Barr $7,515,009.69 → $2,828,109.51; Tom Cotton $8,588,476.41 →
$7,127,399.59; Ted Budd $5,914,490.51 → $3,257,717.00; Mike Collins
$5,716,180.56 → $2,884,746.08; Adam Schiff $4,580,168.57 →
$1,108,314.92; Steve Daines $5,867,070.60 → $4,454,812.98.

Two bugs found and fixed while building this (both in
`receipts/square_one/transfers.py`, with regression tests):

- The kept-choice comparison matched office letters (`H`/`S`)
  against chamber words (`House`/`Senate`), so it never fired and the
  kept view fell back to roster order. Bell's House view was dropped
  and his Senate stub kept. Fixed: the comparison now translates the
  chamber to a letter. Bell keeps his House ID.
- Where the §8 item 15 record's kept ID differs from the transfer
  rule's (Carter, Hunt, Marshall, Moulton — all 119th-only), the two
  passes zeroed each other's kept view and deleted real money
  ($2,191,303.98 across six cycle rows). The transfer pass now defers
  to the §8 kept ID where a record exists for that cycle. The kept
  choices now agree everywhere a §8 record exists.

Scope note, for Craig: the dedup covers transfer fields only. The
same two-views-of-one-committee pattern also doubles the other weball
fields (Barr's cash on hand and total receipts are both doubled in
the dataset — $3,107,714.20 is twice $1,553,857.10), because the §8
item 15 dedup only zeroes fields where the two views are equal and
Barr's views differ. That wider double-count is unchanged by this
work and needs its own decision.

## 3. Ryan (election-attributed refunds) — the pilot report was wrong twice over

The transfers pilot reported Ryan's election-attributed 2026 net as
+$5,000 and said he would flip. Both halves are wrong:

- The $5,000 arithmetic missed a refund: two of the five refunds are
  2026 (P2026 and G2026), so the election-attributed 2026 net is
  +$10,000 − $10,000 = **$0**, not +$5,000. The refund elections come
  from TRANSACTION_PGI in the pinned snapshot, confirmed live against
  Schedule A line 16 (same transaction IDs, same election type).
  Attributed nets by election year are 2022 −$5,000, 2024 −$10,000,
  2026 $0; the career total is unchanged at −$15,000 (the pas2 net) —
  attribution moves refunds between years, it does not change the total.
- The money doesn't attach to Ryan at all under roster linkage. His
  AIPAC rows are filed under H8NY19223 ("PAT RYAN FOR CONGRESS",
  committee C00815290), which the roster does not link — it links him
  to H4AS00036. The API by-recipient total for his committee is
  $138,538.15 in 2026 (mostly earmarked money), and it sits
  unattributed for the same reason. Ryan's corrected 2026 AIPAC is $0
  under every variant, he stays null (unopposed) and unflagged, and no
  count moves. Linking H8NY19223 to Ryan is a roster decision for
  Craig; if linked, Ryan flips dirty under both variants (flag +1,
  cycle and term; clean/not-dirty unchanged, since he is null).

The pilot report's count effects (Strict clean 83→82 and so on)
assumed Ryan was counted clean. He is not — he is one of the four
nulls (unopposed, dirty $0), so even the Schedule-B-only figure
(+$10,000) would move him null → dirty (flag +1, clean unchanged),
not clean → dirty.

## 4. Roster-linkage gaps found along the way

- **Luria (L000591).** The roster links her to H8VA02111 (her old
  committee, $590.89 in 2026, coverage ending July 2025). Her current
  committee H6VA02198 ($8,044,063.94 in 2026) is not linked, so her
  2026 linkage fails and she is null. The derivation reproduces the
  null exactly once the per-cycle entry rule follows the pipeline's
  (a cycle appears when the candidate filed individual money or any
  AIPAC/corporate pas2 money, as filed — the rule that keeps Luria
  null; an earlier version of the counts code created an entry from
  the mere existence of a weball row and wrongly counted her clean).
- **Latimer's misfiled row.** The Latimer pilot report claimed a
  $2,500 JACPAC row filed under the wrong candidate ID (H2AR01063)
  was captured by the tracker. It is not — it sits in the store under
  H2AR01063. The API merge (recipient-committee attribution) is what
  catches this class; the pas2 path cannot.
- **Pappas / Hageman.** The transfers pilot said neither had a House
  weball26 row. Both do, with values identical to the Senate rows;
  both are in `dedup-applied.json` and already covered by §8 item 15.
- **Collins (Senate) double-count does not reproduce.** The transfers
  pilot reported her weball26 transfers_from as $5,605,663.89 (two
  views summed). The roster has one Collins ID and the pinned
  snapshot gives $5,371,811.34. Open discrepancy, reported as found.

## 5. What the audits now catch

`receipts/square_one/audits.py` runs four checks on the corrected
derivation (22/22 pass in the full CLI run):

- (a) No zero columns: any money column zero for every record in a
  cycle fails loudly. It fires on the old pas2 AIPAC earmark share
  and on a zeroed-column control.
- (b) Earmark share: AIPAC and NORPAC near-total conduits, JACPAC
  mixed (~37% earmark in 2024), DMFI zero — each against a
  pilot-grounded minimum.
- (c) Independent-source spot checks: corrected 2026 AIPAC equals the
  live FEC Schedule B pulls for the ten comparison members, and
  corrected career totals sit within the comparison doc's own residual
  band (±$650,000, set by the largest open residual) of Track
  AIPAC's, with the Latimer (+$610,488) and Collins (+$293,670)
  residuals flagged as known-open, never absorbed. The first version
  of this check assumed corrected must sit *under* Track AIPAC; it
  failed on Fetterman and Bell, correctly — Track AIPAC's IE layer
  undercounts the FEC-reconcilable IE for Fetterman by $65,539, and
  its committee list is narrower than the tracker's for Bell.
- (d) Headline-includes-earmarks: for every comparison member whose
  live 2026 figure exceeds pas2, the corrected figure reaches the
  live figure.

## 6. Counts under both JFC variants

Recomputed from the derivation with the repo's own rules
(`compute_2026` cycle records and headline, `term_record`,
`clean_2026` tiers). Baseline reproduces the committed counts
exactly.

| | 2026-cycle rule | Term ("clean since last election") |
|---|---|---|
| Baseline (pas2) | flag 231, Strict clean 83, Balanced not-dirty 201, Lenient 253, null 4 | flag 270, Strict clean 79, Balanced 183, Lenient 224, null 4 |
| Variant A (JFC counts) | flag **258**, Strict clean 81, Balanced 189, Lenient 234, null 4 | flag **299**, Strict clean 77, Balanced 170, Lenient 203, null 4 |
| Variant B (JFC excluded) | flag **256**, Strict clean 81, Balanced 191, Lenient 236, null 4 | flag **297**, Strict clean 77, Balanced 172, Lenient 205, null 4 |

House-120th career-clean stays 58 under both variants (only Zinke
flips it, and he is 119th-only). Only Crane and LePage change flag
status between the variants. The counts are the JFC recount's counts
to the person — the independent re-derivation reproduces them
exactly, including the nulls.

## 7. What is still open (not a difference, a gap)

- **Full registered-key merge run (December).** The roster-wide
  Schedule B pull (~2,000–2,500 calls, cycles 2022+2024+2026, all 66
  listed committees) needs the registered `FEC_API_KEY` (GitHub
  secret, not on this VM). The merge runner takes the key from the
  environment and is validated end to end against the pilot evidence;
  the December run (CI with the secret) completes it: it fills the 53
  missing 2022 files, resolves the 44 ambiguous rows (including the
  Collins $19,146.43) by recipient committee ID, and checks whether
  earmarking moved vehicles after AIPAC's October 2026 announcement
  that it will stop direct contributions and earmarking.
- **Latimer residual (+$610,488) and Collins residual (+$293,670)**
  vs Track AIPAC: documented-unknown, mechanism unknown, all four
  hypotheses ruled out with dollars. Not adjusted.
- **STATUS.md says Strict clean 84; the dataset counts 83.**
  The 84 is the Nov 12 tiered-rule count (Ryan then counted clean on a
  −$15,000 AIPAC refund); the current dataset counts 83, and the
  recount agrees — the 84 is stale history from before the later
  fixes, not a live conflict.
- **Barr wider double-count** (§2 scope note) and the **Ryan /
  Luria roster links** (§3, §4) are Craig's calls.
- **Debts-owed-to career** is not covered by the derivation (the
  weball reader's 30 columns carry no debts-owed-to field); the
  dataset column is null for 663 of 664 rows, so nothing is lost.
- **The §8 item 15 prose understates the implemented rule.** The
  methodology says the dropped copy's `individual` is zeroed; the
  implementation zeroes any weball financial field where the dropped
  copy equals the kept copy (plus the cols 6–9 extension where
  recorded). Noted in methodology §8.

## 8. Verification summary

- Baseline-variant cycle records match the dataset's for every
  person and every cycle, every field (the counts test spot-checks
  four members field by field; the diff above covers all 664).
- Baseline counts reproduce the committed counts exactly; variants A
  and B reproduce the JFC recount's counts exactly, person for
  person.
- Full existing rebuild still reproduces the committed dataset
  byte-identically (md5s in the final report); the pipeline and the
  dataset are untouched on this branch.
- Fast gates per commit: `ruff check`, `ruff format --check`,
  `mypy`, `pytest -q`. Two pre-existing gate failures were fixed
  along the way (complexity over the limit in the classifier and the
  dedup-candidate builder; two files under the maintainability floor;
  result figures in code comments), and two more bugs were found by
  the new tests (the transfer kept-choice letter mismatch; the
  all-IE total dropping blank-direction rows).
