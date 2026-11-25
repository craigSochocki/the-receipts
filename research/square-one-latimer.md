# Latimer residual — square-one research note

**Date:** November 25, 2026 (all live pulls this day, unless stated)
**Question:** Track AIPAC's career total for George Latimer (D-NY-16) is
$19,195,523; the tracker's comparable total is $15,623,782 — a gap of
$3,571,741. The direct-money gap explains $2,961,253, leaving a residual of
**+$610,488** that no direct-money layer explains.
**Verdict: DOCUMENTED-UNKNOWN** — the residual is pinned to one place
(Track AIPAC's "Independent Expenditures" layer), hypotheses (a)–(d) below
are ruled out with dollars, but the mechanism inside TA's IE computation
cannot be determined from any public source. See "What would settle it".

**Repo state:** branch `square-one-rederivation`, dataset at remote master
`2f65cb5`, pinned FEC snapshot `fec-bulk-2026-11-22`. All tracker figures
below are from `congress-money-tracker.json` at that commit.
**Method note:** live FEC API calls were made by direct `curl` from this VM
with `DEMO_KEY` (background-worker calls to api.open.fec.gov are blocked by
the sandbox egress). TA's old candidate-page slug
(`/member-george-latimer-ny-16-d`) now 404s; the current URL is
`https://www.trackaipac.com/tracker/people/member-george-latimer-ny-16-d`.

## 1. Decomposition table — the tracker's side (pinned snapshot)

| Layer | Amount | Source / as-of |
|---|---|---|
| Tracker `pro_israel_pac_career` | $69,800.00 | Dataset 2f65cb5. 2024 $59,800 + 2026 $10,000 |
| Tracker `pro_israel_ie_support_career` | $5,593,241.85 | Dataset 2f65cb5. 2024 only: UDP $4,682,560.29 + DMFI PAC $910,681.56 |
| Tracker `pro_israel_opp_credit_career` | $9,960,740.16 | Dataset 2f65cb5. 2024 only: UDP vs Bowman $9,865,492.96 + DMFI vs Bowman $95,247.20 |
| **Tracker comparable total** | **$15,623,782.01** | Sum of the three rows above |
| Track AIPAC "Israel Lobby Total" | $19,195,523 | trackaipac.com candidate page + NY state page, re-fetched Nov 25, 2026 (unchanged from Nov 25 comparison report) |
| **TA − tracker comparable (gap)** | **$3,571,740.99** | |
| WhoFundsMyRep direct+earmarked | $3,031,053 | whofundsmyrep.com/rep/george-latimer, re-fetched Nov 25, 2026; "as of November 2026", most recent filing 2026-10-14 |
| Direct gap (WFMR direct − tracker PAC) | $2,961,253.00 | $3,031,053 − $69,800 |
| **Residual** | **+$610,487.99** | $3,571,740.99 − $2,961,253.00 |

WhoFundsMyRep's other layers (same page, same fetch): IE support
$5,559,360; "spent against opponents" $9,960,740 (2024 vs Jamaal Bowman:
UDP + DMFI PAC); total $8,590,413. WFMR's opposition figure matches the
tracker's opposition credit to the dollar ($9,960,740 vs $9,960,740.16), so
the opposition layer is **not** a source of the residual. WFMR's IE support
is $33,881.85 *below* the tracker's ($5,559,360 vs $5,593,241.85), so using
WFMR's IE instead of the tracker's would make the residual $33,882 bigger,
not smaller.

### The tracker's direct $69,800, verified committee by committee (pas2 bulk)

Recomputed from the staged pas2 files (`data/raw/pas2/2024` and `2026`,
pinned snapshot), not just read off the dataset:

- **2024, $59,800:** NorPAC (C00247403) $43,550 + AIPAC PAC own money
  $10,000 + JACPAC (C00139659) $5,250 + DMFI PAC (C00710848) $1,000.
  - AIPAC's raw pas2 rows are $5,000 − $1,000 − $1,000 − $1,000 + $5,000
    = $7,000 net. The three −$1,000 rows are "VOID: REFUNDED EARMARK"
    rows (Geri Schwartz, Tzipora Renbaum, Steven Tennenbaum), excluded per
    methodology §2 (negative earmark rows are excluded from every total
    because their originals are not in pas2) — hence $10,000, not $7,000.
  - JACPAC's $5,250 is $2,750 filed under Latimer's candidate ID plus a
    $2,500 row filed 02/02/2024 under the **wrong candidate ID**
    (H2AR01063, an Arkansas candidate) with name "GEORGE LATIMER FOR
    CONGRESS" and OTHER_ID C00859041. The tracker captures it, so its join
    is not CAND_ID-only — keep that behaviour in the re-derivation.
- **2026, $10,000:** AIPAC PAC $5,000 (02/12/2026) + $5,000 (09/30/2026);
  a −$6 void and a $0 void (Howard Welinsky earmark) excluded by the same
  rule (raw net $9,994).
- **No other listed PAC** contributed directly to Latimer in either pas2
  file. The direct layer is fully reconciled; there is no missing
  listed-PAC direct money in the tracker's own source files.

### Live FEC cross-checks (direct curl, DEMO_KEY, Nov 25, 2026)

- **AIPAC PAC Schedule B, `by_recipient`, to "GEORGE LATIMER FOR
  CONGRESS":** 2024 **$2,818,638.95** (4,336 rows); 2026 **$94,333.40**
  (89 rows); career **$2,912,972.35**. Identical to the Nov 13 live pull
  to the cent. WFMR's AIPAC figure ($2,915,742) exceeds live direct by
  $2,769.65 — WFMR already counts slightly *more* AIPAC money than live
  direct, leaving no room for a $610k AIPAC layer WFMR missed.
- **Latimer's federal career is 2024 + 2026 only.** FEC candidate
  H4NY16087: `cycles: [2024, 2026]`, first filed 2023-12-04. There is no
  pre-2024 federal money for TA to count, and no state-level money in a
  federal total.
- **2026 totals in the live API still end Oct 14, 2026** (coverage_end
  2026-10-14; receipts $681,937.92 — identical to the tracker). No
  post-general report has been filed yet (due Dec 3).
- **OpenSecrets 2024 sub-question (open, tangential):** OS's AIPAC-org
  2024 figure for Latimer is $2,448,899 (individuals $2,438,899 + org
  $10,000), which is **$369,739.95 below** live 2024 direct
  ($2,818,638.95). Tested and excluded: 2025-dated AIPAC→Latimer
  2024-cycle rows = **0** (API `recipient_name` + `min_date=2025-01-01`
  query, Nov 25). OS is the outlier here — live direct is corroborated by
  WFMR ($2,915,742) and ChamberLight ($2.91M, 3,927 donors, "FEC filings
  through Oct 14"). Why OS is $370k low is not established; it does not
  enter the residual arithmetic.

## 2. The decisive new evidence — Track AIPAC's own graphic for Latimer

TA's candidate page publishes no split, but it links a downloadable
graphic, fetched Nov 25, 2026 from
`https://www.trackaipac.com/assets/graphics/0687_NY-16+George+Latimer.jpg`
(dated **4/23/26**, "via fec.gov"):

| Graphic figure | Amount |
|---|---|
| Headline: "SPENT BY PRO-ISRAEL PACS" | $19,155,439 |
| PACs | $2,955,299 |
| Ind. Expenditures | $16,200,140 |
| Check: $2,955,299 + $16,200,140 | $19,155,439 ✓ internally consistent |

Current page total ($19,195,523) is $40,084 above the April graphic. The
residual decomposes **exactly** through the graphic's own split:

| Component | Amount |
|---|---|
| TA graphic IE − FEC-reconcilable listed IE (support $5,593,241.85 + opp $9,960,740.16 = $15,553,982.01) | **+$646,157.99** |
| TA graphic PACs − WFMR direct ($2,955,299 − $3,031,053) | −$75,754.00 |
| Drift, graphic (Apr 23) → current page total ($19,195,523 − $19,155,439) | +$40,084.00 |
| **Sum** | **+$610,487.99 = the residual ✓** |

Two things follow. First, the residual lives **entirely in TA's IE
layer**; TA's direct layer runs the *other* way (TA counts $75,754 less
direct money than WFMR). Second, the question narrows to: **what is the
$646,157.99 of "Ind. Expenditures" in TA's April graphic that no
FEC-reconcilable combination contains?**

### The 2024 IE universe is closed — and $16,200,140 cannot be built from it

Enumerated from the staged IE bulk files (pinned snapshot), deduped on
(`spe_id`, `tran_id`) the tracker's way, cross-checked both by candidate
name and by candidate ID (Bowman H0NY16143, Latimer H4NY16087). All
NY-16 2024 rows are primary-phase (`ele_type` P); there are no
general-phase rows and no blank-`cand_id` rows mentioning either man:

| IE bucket, 2024 NY-16 | Amount |
|---|---|
| Support Latimer, all spenders | $5,594,161.85 (UDP $4,682,560.29; DMFI $910,681.56; Wake Up Enterprises $920) |
| Oppose Bowman, all spenders | $12,038,763.16 (UDP $9,865,492.96; **Fairshake $2,078,023.00**; DMFI $95,247.20) |
| Oppose Latimer, all spenders | $1,144,974.15 (WFP $569,035; Justice Democrats $391,613.31; EMGAGE $100,000; UDP $84,325.84) |
| Support Bowman, all spenders | $1,913,380.38 (all unlisted PACs) |
| **2026 NY-16 IE, all spenders** | **$0 — the 2026 IE file has no NY-16 rows at all** |

Combinations tested against TA's graphic IE ($16,200,140):

- Listed support + listed oppose (the tracker's layers): $15,553,982.01
  → short **$646,157.99**.
- All-spender support + all-spender oppose-Bowman: $17,632,925.01 →
  over by $1,432,785.01. (Fairshake, the only unlisted oppose-Bowman
  spender at $2,078,023, is far too big to be the missing piece in any
  combination.)
- Listed support + listed oppose + UDP-oppose-Latimer ($84,325.84) +
  WFP-oppose-Latimer ($569,035.00): $16,207,342.85 → overshoots TA's IE
  by **$7,202.85**. This is the closest combination found, and it still
  misses — and it requires counting spending *against* Latimer as money
  *for* him, which no stated methodology does.
- Listed support + listed oppose + UDP-oppose-Latimer only: $15,638,307.85
  → short $561,832.15. No FEC figure of $561,832.15 or $646,157.99 was
  found anywhere in the NY-16 IE data.

Note also, against the residual's direction: the tracker's UDP support
($4,682,560.29, IE file) is **$38,723 above** UDP's own Schedule B 24E
rows in pas2 ($4,643,833) and $38,727 above WFMR/ChamberLight
($4,643,837) — an amended-report/dedup difference worth a look in
square-one (IE dedup handling), but it makes the tracker *higher*, so it
cannot explain TA being higher still.

## 3. Hypothesis verdicts

### (a) TA's donor-network layer still present for this member — RULED OUT

TA's V3 methodology (2026) added a donor-network layer, but an April 28,
2026 update says TA reverted to its earlier method (567politics; Nov 25
comparison §7). The cross-member test now rules it out as a live layer:

| Member | Donor network (primarydemocrats.com, FEC thru Sep 30, 2026) | TA residual (Nov 25 comparison §3) |
|---|---|---|
| Stevens | +$3.98M | −$36,751 |
| Bell | +$1.05M | −$350,686 |
| Gottheimer | +$1.51M | −$134,975 |
| Jeffries | +$363K | −$83,818 |
| Aguilar | +$95.4K | ~+$246,895 (approx) |
| **Latimer** | **+$1.06M** | **+$610,488** |

If TA's totals included donor-network money, residuals would scale with
network size. Instead the largest network (Stevens, $3.98M) has the
smallest residual (−$37k), and three members with $1M+ networks have
negative residuals. Latimer's own network (+$1.06M, primarydemocrats.com
list page, fetched Nov 25, 2026) is also larger than the residual and does
not match it. (Caveat: primarydemocrats' donor definition is its own, not
TA's unpublished V3 definition — but the orders of magnitude and the
cross-member pattern are decisive against a general live layer. A
Latimer-only remnant would need TA's donor list to show it, and TA
publishes none.)

Primarydemocrats' backing totals also corroborate the direct+IE layer
independently of WFMR: Latimer $8,545,263 vs WFMR $8,590,413 (−$45,150,
as-of Sep 30 vs Oct 14); Stevens $15,777,643; Bell $10,018,475;
Gottheimer $2,353,722; Jeffries $1,432,101; Aguilar $1,341,510. Its list
states "Spending against a member is never added" and shows the donor
network as a separate "+" line — the same separation TA's FAQ claims.

### (b) JFC earmarks that WhoFundsMyRep does not count — RULED OUT

- **No Latimer JFC exists.** FEC committee search `q=LATIMER`: 3 results
  — C00859041 GEORGE LATIMER FOR CONGRESS (his); C00844365 LATIMER FOR
  CONGRESS (a Texas candidate, H4TX31065); C00484352 LATIMER FOR US SENATE
  COMMITTEE. Search `q=LATIMER VICTORY`: 0 results. Latimer has exactly
  one committee (FEC candidate/committees endpoint, cycles 2024 and 2026).
- **No JFC money reached the campaign.** Tracker's
  `transfers_from_auth_career` = $0 in both cycles; pas2 shows no
  committee contribution to C00859041 from any joint fundraiser.
- **WFMR already counts more AIPAC money than live direct** ($2,915,742
  vs $2,912,972.35), so there is no $610k JFC-shaped hole in WFMR's
  direct figure. And OpenSecrets — which *does* count JFC earmarks per
  the Nov 25 comparison — is $369,739.95 *below* live direct for 2024,
  the opposite direction from a missing-JFC story.

### (c) Post-cutoff filings after Oct 14, 2026 — RULED OUT (quantified, not just capped)

- The only post-cutoff filings are two F6 48-hour notices, read in full
  from docquery.fec.gov (CSV, Nov 25, 2026):
  - F6 2042270, filed Oct 26, 2026: **$8,500.00** (SEIU COPE $5,000;
    United Pilots PAC $1,000; Steven Kessner $2,500).
  - F6 2045870, filed Nov 2, 2026: **$19,816.66** (Mastercard PAC $4,000;
    MEBA-PAF $1,658.33; Seafarers $1,658.33; Kaidanow $1,000; Milstein
    $3,500 × 2; Thever $3,500; Wilcox $1,000).
  - **Combined: $28,316.66 from all sources; $0 from any listed
    pro-Israel committee; $0 from AIPAC.** (A Schedule A query for
    C00859041 with `min_date=2026-10-15` returned 0 rows — F6 contents
    are not in Schedule A until the post-general report.)
- The live candidate totals still end Oct 14 ($681,937.92, identical to
  the tracker). 2026 IE is $0 in the bulk file and $0 for/against in
  WFMR's 2026-race line. Even the absolute ceiling — the whole 2026 race's
  pro-Israel figure, $99,704 (WFMR) — is 6× too small, and the actual
  post-cutoff pro-Israel figure is $0.

### (d) Other listed PACs' money — RULED OUT

- The tracker's pas2 direct is reconciled committee-by-committee above
  (§1); WFMR's direct already includes NORPAC $96,950, JACPAC $11,361,
  DMFI direct (~$7,672, implied by WFMR DMFI $918,354 minus IE-file DMFI
  support $910,681.56) and AIPAC $2,915,742. No listed PAC's money is
  missing from WFMR's direct at anything near $610k.
- The largest unaccounted listed-PAC item anywhere is ~$42k: TA's graphic
  PACs ($2,955,299) minus live AIPAC direct ($2,912,972.35) = $42,326.65 —
  *smaller* than WFMR's NORPAC+JACPAC alone, i.e. TA's PACs figure does
  not even contain all of WFMR's non-AIPAC direct money. The direct layer
  cannot produce a +$610k residual; on TA's own graphic it produces
  −$75,754.

### (e) A Track AIPAC-side error or stale graphic figure — SUPPORTED AS THE LOCATION; MECHANISM UNKNOWN

What is established:

- The residual sits in TA's IE layer on TA's own published split
  (+$646,157.99 on the April graphic; the current total's residual is
  that plus the −$75,754 direct shortfall plus $40,084 drift).
- The complete FEC IE universe for Latimer's races cannot reproduce TA's
  IE figure: no combination of listed, all-spender, or
  ±oppose-Latimer rows hits $16,200,140 (closest miss $7,202.85), and
  2026 IE is $0 in every source.
- TA's graphics have a documented inconsistency record: the June Stevens
  graphic was internally inconsistent by ~$28.3M (Nov 25 comparison §7),
  and TA totals drift between crawls without explanation (Latimer's own
  total moved +$40,084 between the April graphic and today; Collins's
  moved −$24,816 between its Oct 25 graphic and today).
- The same signature appears for the second positive residual, Collins
  (see §4).

What is **not** established: whether the $646,157.99 is a stale-data
artifact (the graphic is 7 months old; the current $19,195,523 has no
published split), a computation/double-counting error, an unpublished data
source, or a broader IE definition (e.g. electioneering communications or
non-Schedule-E spending counted as "Ind. Expenditures"). TA publishes no
transaction list, no per-cycle split, no as-of date for the current total,
and no methodology for the graphic splits, so none of these can be
distinguished from public sources. Do not assert a mechanism.

## 4. Item 3 — does the same residual pattern appear for any other member?

Basis: Nov 25 comparison report §3 residuals (TA vs tracker-comparable,
crawled Nov 23–25, 2026), with fresh Nov 25 re-checks of the TA totals
noted. Only Latimer and Collins are positive at scale; the rest are
negative (TA *below* the WFMR-implied figure) or trivial.

| Member | TA − tracker comparable | Residual (TA gap − direct gap) | Status Nov 25 |
|---|---|---|---|
| Stevens | +$1,299,444 | −$36,751 | Explained (timing/refunds) |
| Bell | +$5,200,990 | −$350,686 | Explained (list/timing) |
| Gottheimer | +$2,097,045 | −$134,975 | Explained |
| **Latimer** | **+$3,571,741** | **+$610,488** | **This note** |
| **S. Collins** | **+$4,378,636** | **+$293,670** | **Same TA-side IE signature — see below** |
| Boafo | +$3,382 | +$382 | Timing only; method reconciles (§6 of comparison) |
| Aguilar | +$1,474,555 | ~+$246,895 (approx; no WFMR split fetched) | Not re-tested here. Plausibly 2022-cycle AIPAC + other listed PACs (in office since 2015); primarydemocrats gives $1,341,510 backing + $95.4K donor network (Sep 30) vs TA $1,537,090 |
| Jeffries | +$1,415,347 | −$83,818 | Explained |
| Warner | +$689,936 | −$81,756 | Explained |
| Fetterman | +$166,498 | −$65,539 | Explained — IE difference, decomposition closes (§5 of comparison) |

Fresh TA totals re-checked Nov 25, 2026: Latimer $19,195,523
(unchanged), Collins $4,613,803 (unchanged), Aguilar $1,537,090
(unchanged, CA state page + candidate page).

**Collins re-analysis — corrects the Nov 25 comparison's hypothesis.**
The comparison (§3) called Collins's +$293,670 "most likely post-Oct-14
earmarks". TA's own graphic now refutes that as the mechanism. TA's Oct
25, 2026 Collins graphic (via @TRACKAIPAC social posts, Nov 4, 2026)
splits its then-total $4,638,619 as **donations $4,073,619 + IE
$565,000**. Exact reconciliation of Collins's residual:

| Component | Amount |
|---|---|
| TA graphic IE | +$565,000.00 |
| TA donations shortfall vs WFMR direct ($4,073,619 − $4,320,133) | −$246,514.00 |
| Drift, graphic (Oct 25) → current total ($4,613,803 − $4,638,619) | −$24,816.00 |
| **Sum** | **+$293,670.00 = Collins residual ✓** |

And TA's $565,000 IE has **no FEC footprint**: the staged IE bulk file
through Nov 3 contains zero listed-PAC IE rows in the Maine Senate race;
live FEC Schedule E for Collins 2026 (candidate S6ME00159, all 900 rows,
9 pages, Nov 25) contains zero listed-PAC rows (UDP: 0 rows); live
Schedule E for Troy Jackson 2026 (S6ME00464, all 700 rows, 7 pages)
contains zero listed-PAC rows. The graphic predates the election, so
post-cutoff filings cannot explain it either. Collins is therefore a
second instance of the same phenomenon: a TA-published IE figure that no
FEC source reproduces, partly offset by TA counting *less* direct money
than WFMR. (The Nov 25 comparison's post-cutoff reasoning for Collins
rested on live AIPAC direct already exceeding OS by $571,056 — real late
earmarks, but they sit in the *donations* layer, where TA is $246,514
below WFMR, not above it.)

## 5. Final verdict

**DOCUMENTED-UNKNOWN.** The +$610,488 Latimer residual is fully located
but not explained:

- **Located:** in Track AIPAC's "Independent Expenditures" layer.
  TA's own April 23, 2026 graphic attributes $16,200,140 to IE against
  $15,553,982.01 of FEC-reconcilable listed IE — an excess of $646,157.99
  — while its PACs figure ($2,955,299) is $75,754 *below* WFMR's direct
  ($3,031,053). With $40,084 of total drift since April, the arithmetic
  closes exactly on $610,487.99.
- **Ruled out with dollars:** (a) donor-network layer — cross-member
  test (Stevens $3.98M network, −$37k residual) refutes a live layer;
  (b) JFC earmarks — no Latimer JFC exists, no JFC money reached the
  campaign, WFMR already exceeds live AIPAC direct; (c) post-cutoff
  filings — the only post-Oct-14 filings total $28,316.66 with $0
  pro-Israel; (d) other listed PACs — direct layer fully reconciled
  committee-by-committee, and WFMR's direct already contains every
  listed PAC's money.
- **Unknown:** what TA's IE layer counts beyond FEC Schedule E. The
  complete 2024 IE universe is enumerated and closed; no combination
  reproduces TA's figure; 2026 IE is $0 everywhere. Whether the excess is
  stale data, a computation error, double-counting, or an unpublished
  definition/source cannot be determined from public sources.

**Consequence for the tracker:** do not treat Track AIPAC as a
like-for-like cross-check on the IE layer. Its direct layer cross-checks
well (within ~$76k–$350k of WFMR-implied figures for 8 of 10 members),
but its IE layer contains money no FEC source reproduces for at least
two members (Latimer +$646k, Collins +$565k on TA's own graphics). The
December re-pull's API merge of listed-committee Schedule B (Nov 25
comparison rec. 1) should close the direct layer exactly; if the Latimer
residual survives that merge unchanged, it is confirmed TA-side.

## 6. What would settle it

1. **A current TA split for Latimer** (direct vs IE as of Nov 25, not the
   April 23 graphic). The current $19,195,523 has no published split;
   the April graphic is stale by $40,084 and predates the 2026 race.
2. **TA's IE transaction list** — which spenders, races, and dates make
   up the $16,200,140. In particular: does it include Fairshake's
   $2,078,023 against Bowman, spending *against* Latimer ($1,144,974.15),
   or non-Schedule-E spending?
3. **The December re-pull API merge** (all listed committees' Schedule B
   via FEC API): if the residual survives the merge, it is confirmed
   TA-side and the tracker can document TA's IE layer as non-reconcilable.
4. **OpenSecrets 2024 sub-question:** why OS's Latimer 2024 ($2,448,899)
   is $369,739.95 below live direct ($2,818,638.95). Needs OS's
   transaction list or a full date distribution of the 4,336 AIPAC
   Schedule B rows (retrievable via the API's `recipient_name` filter,
   44 pages — not pulled here). Does not affect the residual.

## 7. Side findings for square-one (not part of the residual)

- **Tracker UDP support is $38,723 above UDP's own Schedule B.**
  IE-file UDP support for Latimer $4,682,560.29 vs UDP pas2 24E rows
  $4,643,833.00 (and WFMR/ChamberLight $4,643,837). Same direction for
  DMFI is reversed (IE file $910,681.56 vs pas2 24E $914,851.00). Check IE
  dedup/amendment handling in the re-derivation; it runs against the
  residual's direction, so it is not an explanation, but it is a real
  ~$39k methods difference.
- **Misfiled-row capture works.** The $2,500 JACPAC row filed under
  candidate ID H2AR01063 (name "GEORGE LATIMER FOR CONGRESS",
  OTHER_ID C00859041) is in the tracker's $59,800 — verify the join that
  catches it survives the re-derivation.
- **TA page URLs changed.** Old slug `/member-<name>` 404s; current
  pattern is `/tracker/people/member-<name>`. Update any crawler
  references.

## Appendix — sources with as-of dates

- Tracker dataset: `congress-money-tracker.json`, remote master `2f65cb5`,
  pinned snapshot `fec-bulk-2026-11-22`; Latimer row `person_key`
  L000606, FEC ID H4NY16087, committee C00859041.
- Staged bulk files read directly: `data/raw/pas2/2024/itpas2.txt`
  (703,163 rows), `data/raw/pas2/2026/itpas2.txt` (239,201 rows),
  `data/raw/ie/2024/independent_expenditure_2024.csv` (73,449 rows),
  `data/raw/ie/2026/independent_expenditure_2026.csv` (51,243 rows);
  `data/source/pro_israel_pacs.csv` (66 committees).
- Track AIPAC: candidate page
  `https://www.trackaipac.com/tracker/people/member-george-latimer-ny-16-d`
  ($19,195,523, fetched Nov 25, 2026); NY state page same figure; Latimer
  graphic `https://www.trackaipac.com/assets/graphics/0687_NY-16+George+Latimer.jpg`
  ($19,155,439 = PACs $2,955,299 + IE $16,200,140, dated 4/23/26);
  Collins candidate page ($4,613,803, fetched Nov 25, 2026); Collins
  Oct 25, 2026 graphic via @TRACKAIPAC posts ($4,638,619 = donations
  $4,073,619 + IE $565,000); Aguilar candidate/CA state pages
  ($1,537,090, fetched Nov 25, 2026).
- WhoFundsMyRep: `https://whofundsmyrep.com/rep/george-latimer`
  (fetched Nov 25, 2026): direct $3,031,053, IE support $5,559,360,
  spent against opponents $9,960,740, total $8,590,413; 2026 race received
  $99,704, spent for $0, spent against $0; most recent filing 2026-10-14.
- Live FEC API (direct curl, DEMO_KEY, Nov 25, 2026):
  `schedule_b/by_recipient` C00797670 → Latimer 2024 $2,818,638.95,
  2026 $94,333.40; `candidate/H4NY16087` cycles [2024, 2026];
  `candidate/H4NY16087/totals` cycle 2026 coverage_end 2026-10-14,
  receipts $681,937.92; `candidate/H4NY16087/committees` (C00859041
  only); `committees?q=LATIMER` (3 results) and `q=LATIMER VICTORY` (0);
  `schedule_b` with `recipient_name=GEORGE LATIMER` +
  `min_date=2025-01-01` (0 rows); `schedules/schedule_e` Collins 2026
  S6ME00159 (900 rows, 0 listed) and Jackson 2026 S6ME00464 (700 rows,
  0 listed); F6 filings 2042270 (Oct 26) and 2045870 (Nov 2) CSVs from
  docquery.fec.gov ($8,500.00 + $19,816.66).
- OpenSecrets AIPAC org recipients page, 2024 cycle: Latimer $2,448,899
  (individuals $2,438,899 + org $10,000) — as cited in the Nov 25
  comparison report (fetched Nov 25, 2026).
- PrimaryDemocrats: `https://primarydemocrats.com/list.html` (fetched
  Nov 25, 2026; FEC data through Sep 30, 2026): Latimer $8,545,263
  backing + $1.06M donor network; Stevens $15,777,643 + $3.98M; Bell
  $10,018,475 + $1.05M; Gottheimer $2,353,722 + $1.51M; Jeffries
  $1,432,101 + $363K; Aguilar $1,341,510 + $95.4K; Torres $2,090,700 +
  $2.12M.
- ChamberLight: `https://chamberlight.com/money/aipac/since-2021`
  (FEC filings through Oct 14): Latimer AIPAC net $2.91M (3,927 donors);
  UDP supporting Latimer $4.64M; UDP opposing Bowman $9.87M.
- Nov 25 comparison report:
  `~/workspace/user/trackaipac-opensecrets-comparison-2026.md` (§3
  residuals, §5 Fetterman, §6 Boafo, §7 TA graphics/methodology/drift).
- Methodology: `methodology.md` §2 (negative-earmark-row exclusion rule),
  §4 (pas2 dedup, UDP/IE rules, opposition-credit rule), §8 item 22
  (conduit checks not covered); `research/pro-israel-pacs.md` (TA list
  provenance, V3 donor-network description, Fetterman case).
