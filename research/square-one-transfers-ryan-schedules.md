# Square-one reconciliation: F3 transfers, Ryan's AIPAC flip, Schedule A vs B

Research for the square-one re-derivation of The Receipts tracker.
Repo `~/workspace/user/congress-money-tracker/`, branch `square-one-rederivation`
(at `2f65cb5`). This file documents findings only — it does not change the
dataset; implementation is a separate step, owned by the coordinator.

**Pinned snapshot:** `fec-bulk-2026-11-22`. **Dataset:** `congress-money-tracker.json`
(Nov 22 build). **Live API:** direct curl / Python `urllib` with `DEMO_KEY`
on 2026-11-25 (background-worker calls to `api.open.fec.gov` are blocked by
the sandbox egress; direct calls work). Every dollar below names its source
and as-of date. Where a route was blocked or a figure could not be
reproduced, that is stated — nothing here is guessed.

## 0. Infrastructure finding: local `data/raw/` is NOT the pinned snapshot

Before any of the three items could be checked, the local staging had to be
audited, because the numbers did not reproduce at first.

- SHA-256 check of `data/raw/` against the release `SHA256SUMS`: **60 files
  match, 12 differ** — `cm22/24/26`, `pas222/24/26`, `weball16/18/20/22/24/26`.
  Local `pas2-2026` has **239,201 rows** vs **252,533** in the snapshot;
  local `pas2-2026` is the **Nov 12 download (coverage to Sep 30)** while the
  snapshot is **Oct 14 coverage** (per `config.yaml`
  `verification.coverage_end`: pas2 2026-10-14, weball 2026-10-14, IE
  2026-11-03).
- `data/intermediate/` files are dated Nov 12–14 (stale Nov 12 build) — do
  not trust them; the dataset + snapshot files are authoritative.
- The snapshot tar (315 MB) was downloaded from the GitHub release, hashes
  verified (`pas226.zip` `14851e00…`, `cm26.zip` `6c246bfa…`, `weball26.zip`
  `c09b6202…`), tar deleted after extraction. Snapshot 2026/2024/2022 files
  live at `~/workspace/scratch-square-one/snap2026/`; evidence JSONs and
  helper scripts at `~/workspace/scratch-square-one/` (`ryan_aipac_live.json`,
  `f2009101.csv`, `fec_api2.py` / `fec_api3.py`, `recompute_corp.py`,
  `barr_schedA12.json`, `Subramanyam_schedA.json`, `Randall_schedA.json`,
  `Garcia_schedA.json`, `sched_ab_results.json`, `cm-live/`). `/tmp` is a
  512 MB tmpfs that filled up once — use the scratch dir for large files.
- **Independent recompute from snapshot `pas2-2026` + `cm26`** (pipeline
  dedup, voided-earmark exclusion, overrides C00003251→labor,
  C00468314→unclassified) **matches the dataset exactly** for all six
  members checked: Subramanyam corp $148,500 / other $263,670; Randall
  $70,250 / $289,600; Garcia $253,500 / $466,508; Barr-House corp $561,631 /
  other $530,500; Barr-Senate corp $418,000 / other $823,941; Ryan corp $0 /
  AIPAC net −$15,000 (raw −$15,006 incl. a −$6 voided earmark, excluded).
  Dedup dropped 0 rows for all six. The same recompute from **local**
  `pas2-2026` reproduces the **Nov 12** figures (Subramanyam $133,500;
  Randall $68,250; Garcia $238,500) — the Nov 12 → Nov 22 drift is the
  Sep 30 → Oct 14 coverage move, not a rule change.
- The `oth` bulk file is **not** staged in `data/raw/` — F3 transfer work
  below uses weball cols 7/9 + the live API.

**Consequence for the square-one re-derivation:** any re-derivation must
start from the pinned snapshot, not from local `data/raw/`. The local
staging drift is silent (same filenames, different bytes) and is the most
likely explanation for any future "the numbers moved" surprise.

---

## (a) F3 line-22 transfers for chamber-switchers — the Barr $1.74M gap

### Background (Nov 13)

Tracker all-PAC for Andy Barr (House→Senate switcher) was **$2,282,072**
(corp + other, both campaigns) vs OpenSecrets-implied Senate-only
**≈$4,025,773** — a $1.74M gap in the wrong direction for timing. The
working hypothesis was that House→Senate inter-committee transfers were
counted by OpenSecrets but not by the tracker's line-23-only pull. Source:
`~/workspace/user/opensecrets-crosscheck-2026.md` §3 — Courier-Journal,
Oct 27, 2026, citing OpenSecrets data as of Aug 4, 2026: Barr Senate total
raised **$12,541,350.16**, PAC **32.1%** → ≈$4,025,773 (rounding range
$4,022,778–$4,028,768).

On the Nov 22 dataset the tracker side is: corp **$979,631** + other
**$1,354,441** = **$2,334,072**; + AIPAC $5,000 = **$2,339,072**
(dataset `congress-money-tracker.json`, Nov 22 build). Gap vs OpenSecrets:
$4,025,773 − $2,339,072 = **$1,686,701**.

### The headline finding: there is no House committee to transfer from

FEC API, committees endpoint, 2026-11-25, `DEMO_KEY`: **both Barr candidate
IDs map to ONE principal committee, C00467571 "ANDY BARR FOR SENATE, INC."**
(H0KY06104 → C00467571; S6KY00286 → C00467571 + nominee fund C00898403).
The House committee was redesignated as the Senate committee; no separate
House committee exists. **There is no $1.74M House→Senate transfer**, and
there cannot be one: weball26 (pinned snapshot) transfers_to is **$3,361.42**
(House row) / **$56,817.82** (Senate row).

### What the $1.74M actually is: JFC distributions counted as PAC money

Weball26, pinned snapshot `fec-bulk-2026-11-22`, Barr rows:

| | House ID H0KY06104 | Senate ID S6KY00286 |
|---|---|---|
| total receipts | $12,476,747.89 | $12,541,350.16 |
| individual | $6,913,746.00 | $6,931,212.69 |
| transfers_from (col 7) | $2,780,973.93 | $2,828,109.51 |
| transfers_to (col 9) | $3,361.42 | $56,817.82 |
| total disbursements | $14,615,968.43 | $14,680,570.70 |

Identical under both IDs: F3 line 11c (col 26) **$2,489,548.54**, party
(col 27) **$62,000**, cash on hand **$1,553,857.10**, refunds
**$75,115.70 / $20,500** (committee refunds $20,500). Flow columns differ,
Senate row higher on every one. The weball-generation mechanism for the
identical-vs-differing columns is **not established** — say so in any
methodology note; do not assert a mechanism.

Decomposition of the OpenSecrets Senate PAC figure
(OpenSecrets-implied, via Courier-Journal Oct 27, 2026, OS data as of
Aug 4, 2026):

- Tracker Senate PAC: corp $418,000 + other $823,941 + AIPAC $0 =
  **$1,241,941** (dataset, Nov 22 build).
- + Senate transfers_from **$2,828,109.51** (weball26, pinned snapshot)
  = $4,070,050.51 — **$44,277.51 (1.1%) above** the OpenSecrets figure's
  range top ($4,028,768).
- Using the **House-row** transfers_from **$2,780,973.93** instead:
  $1,241,941 + $2,780,973.93 = **$4,022,914.93 — inside** OpenSecrets'
  rounding range ($4,022,778–$4,028,768).
- Person-level identity (exact): $4,025,773 − $2,339,072 (tracker
  person all-PAC incl. AIPAC) = **$1,686,701** = $2,828,109.51 (Senate
  transfers_from) − $1,097,131 (House PAC: corp $561,631 + other $530,500
  + AIPAC $5,000) − **$44,277.51**.

**The $44,277.51 residual (1.1%) is unexplained.** Tested and rejected:
committee refunds $20,500 do not explain it. Likely OpenSecrets vintage /
definition (their PAC share is a rounded 32.1% of a total that itself
matches the Oct-14 weball row exactly — see the as-of tension below), but
that is a hypothesis, not a finding.

**As-of tension to disclose:** the Courier-Journal article says its
OpenSecrets data is as of Aug 4, 2026, yet the total-raised figure it cites
($12,541,350.16) matches the **Oct-14 weball26 Senate row exactly**. Either
the as-of date in the article is wrong or OpenSecrets' total had already
reached the Oct-14 value by Aug 4 (impossible if filings after Aug 4 added
receipts — the Oct-14 row includes September/October filings). The
OpenSecrets figure should be treated as an approximate cross-check, not a
precise target; the $44,277.51 residual sits inside that imprecision.

**Dead ends, documented:** Sch A F3-12 API pull for C00467571 returned
3,000 rows / $9,511,842.42 — **not usable** as a transfers total (cycle
leak + likely pagination cap + JFC itemization by underlying donor).
Committee totals endpoint is mostly nulls (only individual $6,913,746.00) —
unreliable per methodology §8 item 8. Barr is not in `dedup-applied.json`
(90 entries).

### The same mechanism, roster-wide: switcher sweep (2026, dataset Nov 22 build)

Person-level transfers (dataset `self_funding_per_cycle`, 2026) for every
member with two candidate IDs in the roster:

| Member | 120th | transfers_from 2026 | transfers_to 2026 | Committee structure (API, 2026-11-25) |
|---|---|---|---|---|
| Andy Barr | yes (Senate) | $5,609,083.44 | $60,179.24 | **One** committee C00467571 |
| Kevin Hern | yes (Senate) | $3,956,918.27 | $2,471,687.34 | **Two**: C00636092 / C00943142 |
| Julia Letlow | yes (Senate) | $4,775,569.37 | $2,480,968.58 | **Two**: C00766428 / C00935411 |
| Barry Moore | yes (Senate) | $852,746.23 | $617,396.44 | **Two**: C00720375 (old, renamed "FOR U.S. SENATE") + C00954974 |
| Chris Pappas | yes (Senate) | $1,196,079.97 | $0.00 | **One** committee C00660464 |
| Harriet Hageman | yes (Senate) | $565,559.36 | $0.00 | **One** committee C00788943 |
| Mike Collins | no | $5,605,663.89 | $810,279.28 | **One** committee C00544684 |
| Raja Krishnamoorthi | no | $19,380,171.21 | $19,072,171.21 | (two-committee transfer — see below) |
| Jasmine Crockett | no | $5,235,297.07 | $5,275,059.41 | (two-committee transfer) |
| Robin L. Kelly | no | $2,158,560.13 | $2,156,081.69 | (two-committee transfer) |
| Angie Craig | no | $1,056,524.74 | $670,494.91 | (two-committee transfer) |
| Haley M. Stevens | no | $1,694,919.73 | $1,510,792.89 | (two-committee transfer) |
| Lisa Blunt Rochester | yes (Senate) | $58,000.00 | $0.00 | — |
| Russell Fry | yes (House) | $258,941.62 | $0.00 | — |
| John James | no | $287,794.03 | $2,365.57 | — |

Per-ID 2026 detail (dataset `self_funding_per_cycle`, Nov 22 build) for
the genuine two-committee transfers — House transfers_to vs Senate
transfers_from:

| Member | House trans_to | Senate trans_from | Difference |
|---|---|---|---|
| Krishnamoorthi (H6IL08147 → S6IL00482) | $18,989,567.94 | $19,380,171.21 | +$390,603.27 |
| Crockett (H2TX30178 → S6TX00552) | $4,907,000.00 | $4,857,000.00 | −$50,000.00 |
| Kelly (H2IL02172 → S6IL00474) | $2,156,081.69 | $2,158,560.13 | +$2,478.44 |
| Hern (H8OK01157 → S6OK04247) | $2,397,828.34 | $3,143,879.01 | +$746,050.67 |
| Letlow (H2LA05126 → S6LA00664) | $2,480,968.58 | $4,184,281.51 | +$1,703,312.93 |
| Stevens (H8MI11254 → S6MI00426) | $1,244,042.89 | $1,688,919.73 | +$444,876.84 |
| Craig (H6MN02131 → S6MN00499) | $595,995.47 | $1,055,323.05 | +$459,327.58 |
| Moore (H8AL02171 → S6AL00476) | $300,000.00 | $631,702.82 | +$331,702.82 |

The near-equality of House trans_to and Senate trans_from is the signature
of a real inter-committee transfer; the positive differences are additional
money into the Senate committee from elsewhere (JFC distributions and other
authorized committees). For the one-committee members (Barr, Collins,
Pappas, Hageman) the Senate transfers_from are JFC distributions, not
inter-committee transfers: Collins House trans_to is $0.00 while his Senate
transfers_from is $2,831,434.48 (House trans_from $2,774,229.41 — the House
committee itself received JFC money); Pappas and Hageman have no House
weball26 row at all (Senate transfers_from $1,196,079.97 / $565,559.36 from
JFCs/other).

**Methodology gap exposed:** Barr's person-level transfers_from_2026 of
$5,609,083.44 is the **sum of two views of one committee** ($2,780,973.93 +
$2,828,109.51) — it double-counts. The same applies to Collins
($5,605,663.89 = $2,774,229.41 + $2,831,434.48). Person-level transfers need
a transfers analog to methodology §8 item 15's double-count correction /
shared-committee rule: when two candidate IDs share one principal committee,
their weball transfer rows must be deduplicated, not summed. (This is a
documentation + implementation item for square one; it does not change the
current dataset.)

### Verdict (a)

**The $1.74M Barr gap is explained — but not by a House→Senate transfer.
There is no such transfer: Barr has one committee. The gap is OpenSecrets
counting the Senate committee's transfers_from ($2,828,109.51, overwhelmingly
JFC distributions) as Senate PAC money, which the tracker does not count —
minus a $44,277.51 (1.1%) residual that is unexplained and sits inside
OpenSecrets' rounding/vintage imprecision. Correct treatment: the tracker's
line-23-only PAC pull is right not to count transfers as PAC money; what
square one must fix is (1) the person-level double-count when two candidate
IDs share one committee (Barr, Collins — and Pappas/Hageman by the same
logic), and (2) any OS-style comparison must state that OpenSecrets' PAC
share includes transfers_from. For genuine two-committee switchers
(Krishnamoorthi, Crockett, Kelly, Hern, Letlow, Stevens, Craig, Moore),
the House→Senate transfer is old-chamber money and must never be re-counted
as new-chamber PAC money in a person-level rollup.**

---

## (b) Ryan's AIPAC flip

### The figures

Dataset (Nov 22 build), Patrick Ryan, H8NY19223: corp_2026 **$0**,
aipac_direct_2026 **−$15,000**, dirty_2026 **−$15,000**, clean_2026 **True**,
tier_balanced_2026 **clean**, tier_lenient_2026 **clean**,
total_receipts_2026 **$5,359,733.43**; term: clean **True**, dirty −$15,000,
tiers clean/clean; career: corp **$2,000**, AIPAC **−$10,000**, UDP $0,
dirty_career **−$8,000**.

Snapshot `pas2-2026` (pinned snapshot `fec-bulk-2026-11-22`) AIPAC rows for
Ryan: two **+$5,000** contributions (2025-09-02, file 1956674, tran
B9C2B11398E604DE4BA8; 2025-11-19, file 1929590, tran B5A324C548BD340288A7),
**five −$5,000** dated **2026-07-31** (file 2009101, trans
AAA26ACB63EF64FC08BE, ADF32ABF2B7E64D168F3, A49F4ED94C0EA4AB6B8B,
AFB59638786224BCE8DE, A443AB32809DD4176A2B), and one **−$6.00** voided
earmark 2025-11-19 (memo "VOID: REFUNDED EARMARK OF HOWARD WELINSKY…",
tran B7BC2AB6EEFE94D62BCA). Pipeline net −$15,000 (raw −$15,006 incl. the
voided −$6, excluded by the voided-earmark rule).

### Live re-verification (FEC API, 2026-11-25, `DEMO_KEY`)

Schedule B, disburser C00797670 (AIPAC PAC), recipient C00815290
(Ryan committee), cursor pagination, `cycle=2026` with client-side filter
on `two_year_transaction_period`: **301 distinct rows** returned, **142 in
period 2026**; own-money **+$10,000** (exactly the two +$5,000 rows);
earmarks **$128,538.15** (140 rows); raw total **$138,538.15**; **zero rows
dated 2026-07-31**. This confirms the Nov 13 live figure of +$10,000.

### Mechanism correction: the Nov 13 "amendment" explanation is REFUTED

The Nov 13 working theory was that AIPAC amended its July 2026 report
after Sep 30. **It did not.** Filings endpoint, 2026-11-25: file **2009101**
(AUGUST MONTHLY, coverage 2026-07-01→2026-07-31, received 2026-08-20) has
amendment_indicator **N**, chain **[2009101]**, most_recent **True** — no
amendment exists. The docquery CSV for file 2009101 (fetched 2026-11-25)
contains all five transaction IDs as **"SA16" rows**: "Refund of
Primary/General 2026/2024/2022 Contribution", **+$5,000 each** — refunds
**from** Ryan's committee **to** AIPAC on **AIPAC's Schedule A line 16**,
not Schedule B disbursements. Refund elections: P2026, G2024, G2026, G2022,
P2024. Pas2 carries SA16 refunds as negative 24K rows; the schedule_b
endpoint structurally cannot show them. **The gap is a scope difference,
not an amendment:** pas2 (disburser-side bulk, all of AIPAC's Schedule A
and B) nets the refunds against the contributions, while a Schedule B-only
live pull sees only the +$10,000 of contributions.

True reconciliation (live API, own-money, all cycles): 2022 **$5,000**;
2024 **$10,000** ($1,000 + $4,000 + $5,000); 2026 **$10,000**;
contributions **$25,000** total, refunds **$25,000**, net **$0 career**.
Election-attributed 2026 net: +$10,000 − $5,000 (P2026 refund) =
**+$5,000**. All three views (+$10,000 Sch B-only, +$5,000
election-attributed, −$15,000 pas2-net) agree on the verdict: **dirty**.

Minor divergences, no dataset impact: Welinsky void −$6.76 (API) vs −$6.00
(pas2), same transaction ID; Weisberg void −$174.42 in the API only. Both
are excluded by the voided-earmark rule.

### Adjacent gap: the stale candidate ID

The three 2024 contributions sit in snapshot `pas2-2024` under candidate ID
**H2NY18103**, not H8NY19223 — the roster links only H8NY19223, so the
tracker reads Ryan's 2024 AIPAC as **$0** vs true **+$10,000**, and career
AIPAC as −$10,000 vs true $0 net. H2NY18103 has no weball24/weball22 row.
H2NY18103 pas2 sums (snapshot; 2024 cm is the local file, approximate):
2026 other $27,000 (12 rows), corp $0, AIPAC $0; 2024 other $84,500
(38 rows), AIPAC $10,000 (3 rows), corp $0. Linking it is a roster change
(Craig's call); it has **no effect on the 2026 verdict**.

OpenSecrets cross-check: NY page shows Ryan **$155,955** AIPAC 2026 (Oct 24,
unchanged since Nov 13) vs live API cycle-2026 total $138,538.15 — gap
**$17,416.85**, cause not pinned down. Immaterial to the verdict.

### Count effects (computed directly from the dataset, 120th n=535)

Current (Nov 22 build), **2026-cycle rule**: Strict clean **83** (House 70,
Senate 13), Balanced not-dirty **201** (dirty 330, clean 83,
below_threshold 118), Lenient not-dirty **253** (dirty 278, clean 83,
below_threshold 170), AIPAC/UDP flag **231**, null 4.
**After the flip** (AIPAC +$10,000: Ryan's clean_2026 False, dirty under
both presets — verified by analogy: Ed Gallrein $5,000 AIPAC, corp $0 →
dirty/dirty; Mike Levin $10,000 AIPAC, corp $0 → dirty/dirty):
Strict clean **83→82**, Balanced not-dirty **201→200**, Lenient not-dirty
**253→252**, flag **231→232**.

Current, **term rule ("clean since last election")**: Strict term-clean
**79** (House 70, Senate 9), Balanced not-dirty **183** (dirty 348, clean
79, below_threshold 104), Lenient not-dirty **224** (dirty 307, clean 79,
below_threshold 145), term AIPAC/UDP flag **270** (recomputed from the
dataset by `term_record`'s flag logic — term AIPAC direct > 0 or term UDP
benefit > 0 over cycles ≥ verdict_cycle), null 4.
**After the flip**: term-clean **79→78**, Balanced **183→182**, Lenient
**224→223**, flag **270→271**.

Two corrections to earlier estimates: (1) the Nov 13 estimate "83/202/256"
was on the old base (84/203/257) — do not carry it forward; the Nov 22
base is 83/201/253. (2) **STATUS.md says 120th Strict clean 84→82 (House
70→69), but the dataset counts 83 (House 70, Senate 13)** and the baseline
`house_120th_verified_clean`=70 supports 83 — flag the discrepancy for the
coordinator. (3) Career-clean is **unaffected** by the flip: House
career-clean stays **58** (120th: 64), because Ryan is already not
career-clean — his career corporate PAC is $2,000. His career figures move:
dirty_career −$8,000 → **+$17,000**; career AIPAC −$10,000 → **+$15,000**.

### Verdict (b)

**The flip is real and the mechanism is now established: it is not an
amendment, it is a scope difference. AIPAC's own August Monthly report
(file 2009101, unamended) records five $5,000 refunds from Ryan's committee
on its Schedule A line 16; pas2 nets those refunds (−$15,000) while a
Schedule B-only live pull sees only the +$10,000 of contributions. Square
one must decide the method — (i) keep pas2 netting (Ryan stays clean, which
misrepresents 2026: he took $10,000 of AIPAC money in-cycle and refunded
$25,000 across elections), (ii) Schedule B-only +$10,000, or (iii) attribute
refunds to the named election (+$5,000 for 2026, recommended). On any of
(ii) or (iii) Ryan flips to dirty and the counts move by exactly one
everywhere: cycle 83→82 / 201→200 / 253→252 / flag 231→232; term 79→78 /
183→182 / 224→223 / flag 270→271; career-clean 58 unchanged.**

---

## (c) Schedule A vs B reconciliation — Subramanyam, Randall, Garcia

Members: Suhas Subramanyam (H4VA10279, committee C00856963), Emily Randall
(H4WA06117, C00857094), Sylvia R. Garcia (H8TX29052, C00660555). Presets
(`config.yaml`): Balanced = corp > $100k AND share > 5% of
total_receipts_2026; Lenient = corp > $250k AND share > 10%.

### The claims, reproduced from the pinned files

Corporate claim = snapshot `pas2-2026` 24K/24P rows, corporate-classified
via snapshot `cm26` (committee type Q/N + org type C/W, overrides
C00003251→labor, C00468314→unclassified), pipeline dedup, voided-earmark
exclusion. All corp rows are 24K; memo $0; 24P $0 for all three (among the
six members checked, only Barr-Senate has $2,500 memo corp).

| Member | Claim Nov 12 (local pas2) | Claim Nov 22 (snapshot pas2) | Drift | Dataset corp_2026 |
|---|---|---|---|---|
| Subramanyam | $133,500 | **$148,500** | +$15,000 | $148,500 |
| Randall | $68,250 | **$70,250** | +$2,000 | $70,250 |
| Garcia | $238,500 | **$253,500** | +$15,000 | $253,500 |

The Nov 13 claims reproduce **exactly** from the local (Nov 12) pas2 file.
The drift is fully explained: **14 corporate rows present in the snapshot
pas2 but absent from local pas2, all dated Sep 2 – Oct 9, 2026, summing
+$32,000** (+$15,000 Subramanyam, +$2,000 Randall, +$15,000 Garcia), **zero
rows removed** — the Sep 30 → Oct 14 coverage move (plus a few
late-September filings processed after the Nov 12 pull). It is not a rule
change.

Weball col-26 residuals (col 26 − pas2 gross nonparty), snapshot: Subramanyam
**$40,316**; Randall **$30,806.07**; Garcia **$68,947.15**; Ryan **$153,646.61**
(reconciliation formula in `receipts/store/other_committees_report.py`).
The Lamb validation in `data/intermediate/` is stale (Nov 12: pas2 $96,500,
residual $32,650; Nov 22 per methodology-evidence: $105,750 / $23,400) — do
not cite it.

### Schedule A (recipient side), live API 2026-11-25

Method: API `schedule_a`, `committee_id=<cmte>`, `cycle=2026`,
`line_number=F3-11C`, cursor pagination; client-side filter on
`two_year_transaction_period==2026` (the `cycle` filter leaks — e.g.
Subramanyam's 320 returned rows split 160/160 across periods 2024/2026);
dedup by (contributor_id, transaction_id, amount, date) keeping the latest
file_number; corporate-classified via snapshot `cm26`; earmark rows noted
separately.

| Member | Sch A corp, live Nov 25 | Nov 13 Sch A | Claim Nov 22 | Sch A − claim |
|---|---|---|---|---|
| Subramanyam | **$95,500** (58 rows; earmark $3,500) | $95,500 | $148,500 | −$53,000 |
| Randall | **$70,875** (50 rows; earmark $2,000) | $56,375 | $70,250 | **+$625** |
| Garcia | **$249,500** (145 rows; earmark $0) | $198,500 | $253,500 | −$4,000 |

Subramanyam's Sch A figure is **unchanged from Nov 13 to the dollar**;
Randall's rose $14,500 and Garcia's $51,000 as later filings arrived. The
recipient side is catching up to the disburser side, unevenly.

Row-level join on (contributor committee, amount) between snapshot pas2
corp and live Sch A corp — the disburser-side date and the recipient-side
date for the same contribution routinely differ by days to weeks, so an
exact-date join is meaningless; the (committee, amount) join is the right
one:

| Member | In pas2, not in live Sch A | In live Sch A, not in pas2 |
|---|---|---|
| Subramanyam | **$53,000** (31 pairs) | **$0** (0 pairs) |
| Randall | $2,000 (3 pairs: C00142711 $2,000; C00360354 $1,000; C00227546 −$1,000) | $2,625 (3 pairs: C00569152 $1,000; C00332833 $1,000; C00402321 $625) |
| Garcia | $23,000 (16 pairs) | $19,000 (10 pairs) |

For Subramanyam the live Sch A corporate set is a **strict subset** of
pas2 on that key: every recipient-side corporate row also appears
disburser-side, but 31 pas2 rows ($53,000) never appear on the candidate's
live Schedule A — including $5,000 ×2 dated 2026-09-29 and $3,000 dated
2026-10-07, and also older rows (e.g. $2,500 dated 2025-03-26), so this is
not purely recent-reporting lag. The same committees do appear in her live
Sch A, but with different amounts (e.g. Micron $5,000 in pas2 vs $2,500 in
live Sch A; Boeing $3,000 in pas2 vs $0 in live Sch A) — the two sides file
the same underlying contributions with different amounts and dates. For
Randall the two sides agree to within $625 on 50 rows (essentially
reconciled). For Garcia the churn is two-sided ($23,000 pas2-only vs
$19,000 Sch A-only), mostly timing.

### Schedule B (disburser side), live API 2026-11-25 — NOT a usable total

The naive recipient-scoped live pull **does not work** for this purpose,
and its numbers must not be cited as totals. API `schedule_b`,
`recipient_committee_id=<cmte>`, `cycle=2026`: the endpoint is flooded by
**conduit rows from ActBlue (C00401224)** — 3,850 of the first 4,000 rows
for Subramanyam, 3,967 of 4,000 for Randall — because ActBlue transmits
thousands of individual earmarked contributions, each reported as a
separate Schedule B line-23 row to the candidate's committee. The fetch
hit the 40-page cap at 4,000 rows, so the corporate sums from it are
**truncated lower bounds, not totals**: Subramanyam $112,000 (66 rows),
Randall $23,500 (16 rows). Garcia's Sch B fetch was killed mid-run and no
figure is cited. The disburser side **is** pas2 by construction; a correct
live Schedule B figure would require per-contributor queries, which were
not run. API mechanics learned while doing this: schedule endpoints
**ignore `page`** (pages 1 and 2 return identical rows) — cursor pagination
via `last_indexes` is mandatory (fixed helper:
`~/workspace/scratch-square-one/fec_api3.py`); the `cycle` filter leaks
across two-year periods — filter client-side on
`two_year_transaction_period`; `line_number` must be `FORM-LINENUMBER`
(`F3-12`, `F3-11C` — bare `12`/`11C` → HTTP 400); Schedule B multi-returns
rows in some contexts — dedup by `sub_id`.

**The Nov 13 Schedule B figures are not reproducible.** Nov 13: Subramanyam
$122,000 / Randall $64,250 / Garcia $215,000 (method not recorded — no
endpoint/filter in memory or docs). Tested and rejected:
- **Classification-rule variants** against the Nov 12 local pas2: no single
  variant reproduces all three. (Randall's $64,250 matches QN_C — exclude
  org-type W — on local data exactly, but Subramanyam has $0 of W rows so
  no variant moves her $133,500 to $122,000, and Garcia's closest variant
  is Q_C at $219,500, not $215,000.)
- **Live-committee reclassification**: reclassifying snapshot pas2 corp
  rows with a **live `cm26.zip` downloaded 2026-11-25** changes nothing —
  zero committees reclassified; corp sums unchanged ($148,500 / $70,250 /
  $253,500).
- The Nov 13 figures are all below the Nov 12 claims by $11,500 / $4,000 /
  $23,500, the same direction as a truncated ActBlue-flooded API fetch —
  but that is a hypothesis, not a finding. **Document the Nov 13 Sch B
  figures as unreproducible under any documented method; do not carry them
  forward.** The Nov 13 pattern "claim > Sch B > Sch A" therefore does **not**
  reproduce on Nov 25 data: Sch A now **exceeds** the claim for Randall
  ($70,875 vs $70,250), and Sch B is not a usable total.

### Classification under both presets

On the **claim** (pas2, Nov 22), dataset tiers:

| Member | corp | share of receipts | Balanced | Lenient |
|---|---|---|---|---|
| Subramanyam | $148,500 | 8.70% ($1,707,804.06) | **dirty** (>$100k and >5%) | below_threshold (<$250k) |
| Randall | $70,250 | 4.94% ($1,422,767.38) | below_threshold | below_threshold |
| Garcia | $253,500 | 21.10% ($1,201,321.76) | **dirty** | **dirty** (>$250k and >10%) |

**Garcia's Lenient tier changed since Nov 13**: on Nov 13 numbers she was
dirty under Balanced / below_threshold under Lenient; on Nov 22 numbers she
is dirty under **both** — the $15,000 October addition pushed corporate
over the $250,000 Lenient line. All three have aipac_udp_flag_2026 False and
AIPAC direct −$5,000, so their tiers depend on corporate only.

Sensitivity — tiers under the **live Sch A** figures instead of the claim
(same receipts denominator): Subramanyam $95,500 → below_threshold under
**both** presets (5.59% share but below the $100k line — her Balanced tier
flips); Randall $70,875 → below_threshold under both (unchanged); Garcia
$249,500 → dirty under Balanced, below_threshold under Lenient **by $500**
($249,500 vs the $250,000 line — her Lenient tier flips on $500). The
classification is sensitive to **which side of the same contribution is
counted**. The tracker's choice (pas2 / disburser side) is the more complete
side for these three as of Nov 25 and should stay — but the methodology note
must disclose the Sch A sensitivity, especially Garcia's $500 margin.

### Methodology-note drafts (one paragraph per member)

**Subramanyam.** "Corporate PAC, 2026 cycle: $148,500 (FEC pas2 bulk,
pinned snapshot fec-bulk-2026-11-22; 89 rows, corporate-classified via cm26).
The recipient-side Schedule A (FEC API, live 2026-11-25) shows $95,500 (58
rows) — $53,000 lower, with the recipient-side corporate set a strict
subset of the disburser side on (committee, amount): the contributing PACs
filed the disbursements, but the candidate's committee has not reported
those 31 contributions on its Schedule A line 11C (same committees appear
with different amounts, e.g. Micron $5,000 disburser-side vs $2,500
recipient-side), so the gap is two-sided filing discrepancy, not missing
money on either side alone. The claim is dirty under Balanced (>$100k and
8.70% of $1,707,804.06 receipts) and below_threshold under Lenient; under
the recipient-side figure alone it would be below_threshold under both
presets — the tier is sensitive to which side is counted, and the tracker
counts the disburser side."

**Randall.** "Corporate PAC, 2026 cycle: $70,250 (FEC pas2 bulk, pinned
snapshot fec-bulk-2026-11-22; 50 rows, corporate-classified via cm26). The
recipient-side Schedule A (FEC API, live 2026-11-25) shows $70,875 (50
rows) — $625 higher, with three unmatched (committee, amount) pairs on each
side (pas2-only $2,000 incl. a −$1,000 row; Sch A-only $2,625 incl. a $625
row), i.e. the two sides agree to within $625 on 50 rows and the difference
is filing timing and amended amounts, not a systematic gap. Below_threshold
under both presets on either side; the classification does not depend on
which side is counted."

**Garcia.** "Corporate PAC, 2026 cycle: $253,500 (FEC pas2 bulk, pinned
snapshot fec-bulk-2026-11-22; 151 rows, corporate-classified via cm26) —
up $15,000 from the Nov 12 figure of $238,500, the October filings in the
Nov 22 snapshot. The recipient-side Schedule A (FEC API, live 2026-11-25)
shows $249,500 (145 rows) — $4,000 lower, with two-sided churn (16
pas2-only pairs, $23,000; 10 Sch A-only pairs, $19,000), mostly filing
timing. Dirty under both presets on the claim (21.10% of $1,201,321.76
receipts); the October addition is what pushed corporate over the $250,000
Lenient line — on Nov 12 numbers she was dirty under Balanced only. Under
the recipient-side figure alone she would be dirty under Balanced and
below_threshold under Lenient by $500 ($249,500 vs $250,000), so the
Lenient tier turns on which side of the same contributions is counted, and
the tracker counts the disburser side."

### Verdict (c)

**The claims reproduce exactly from the pinned snapshot, and the Nov 12 →
Nov 22 drift is 14 new rows (+$32,000), not a rule change. The recipient
side (Schedule A, live) now sits below the claim for Subramanyam (−$53,000,
one-sided) and Garcia (−$4,000, two-sided churn) and above it for Randall
(+$625, essentially reconciled) — the gap is two committees filing the same
contributions with different amounts and dates, and the disburser side is
the more complete one for these three as of Nov 25. The Nov 13 Schedule B
figures ($122,000 / $64,250 / $215,000) are not reproducible under any
documented method (no classification variant, no live-committee
reclassification) and the naive live Schedule B pull is unusable
(ActBlue conduit flood + pagination cap) — do not cite either. Tiers hold
on the claim for all three; Garcia's Lenient tier flipped to dirty since
Nov 13 on the $15,000 October addition, and her Lenient tier (and
Subramanyam's Balanced tier) would flip back on the recipient-side figures
alone — disclose that sensitivity in the methodology note, keep counting
the disburser side.**

---

## Evidence index (scratch, not committed)

`~/workspace/scratch-square-one/`: `snap2026/` (snapshot bulk files
2026/2024/2022 — deletable by the coordinator when done), `ryan_aipac_live.json`,
`f2009101.csv` (file 2009101 docquery CSV), `fec_api2.py`, `fec_api3.py`
(cursor pagination, fixed), `recompute_corp.py`, `barr_schedA12.json`,
`Subramanyam_schedA.json`, `Randall_schedA.json`, `Garcia_schedA.json`,
`Subramanyam_schedB.json`, `Randall_schedB.json` (truncated, ActBlue-flooded
— lower bounds only), `sched_ab_results.json`, `cm-live/` (live cm26.zip
downloaded 2026-11-25).

## Open items for the coordinator / Craig

1. **Ryan method decision** (b): keep pas2 netting, Schedule B-only, or
   election-attributed refunds (recommended). Counts move by exactly one
   everywhere on a flip.
2. **Roster decision**: link Ryan's stale ID H2NY18103 (2024 AIPAC +$10,000,
   other $84,500) — no effect on the 2026 verdict.
3. **Transfers rule** (a): person-level dedup when two candidate IDs share
   one principal committee (Barr, Collins); state in methodology that
   OpenSecrets' PAC share includes transfers_from.
4. **STATUS.md discrepancy**: Strict clean is 83 in the dataset (House 70,
   Senate 13), not 84→82 as STATUS.md states.
5. **Weball mechanism**: why some Barr weball26 columns are identical
   under both IDs while flow columns differ — not established; needs an
   `oth`-file or F3 line-item check when `oth` is staged.
6. **Sch B live route**: per-contributor queries if a live disburser-side
   figure is ever needed; the naive recipient-scoped pull is unusable.
