# Other-committee money — classification evidence and reconciliation notes

Moved verbatim from the header of `src/ingest/pull_other_committees.py` (Nov 22, 2026), where it had grown into a research note. The rules themselves now live in `src/domain/committee_classes.py`; the figures below are as of the Nov 12, 2026 pull.

```text
Congress money tracker — other-committee contributions from FEC bulk files (pas2 + cm).

The tracker already counts corporate PAC money (pas2 rows where the contributing
committee has CMTE_TP in (Q,N) and ORG_TP in (C,W)) and AIPAC PAC direct money
(CMTE_ID C00797670), but NOTHING from any other committee — so members funded by
party committees, leadership PACs, labor PACs, or trade-association PACs show $0
there. This script fills that hole with SEPARATE columns, never blended into
total_accepted (individual + corporate PAC + AIPAC direct — that definition is
unchanged). It reads the staged pas2 + cm bulk files (cycles 1980-2026) and
produces data/intermediate/other_committees_per_cycle.json (per person, per cycle, by class)
and data/intermediate/other_committees.csv (per person, career totals by class).

Classification — derived from the data, verified Nov 12, 2026 (see evidence below).
Every contributing committee is classified from its SAME-CYCLE cm record
(a committee's type can change across cycles, e.g. N -> Q), in this precedence
order (first match wins; AIPAC and corporate are excluded here because they are
already counted in other columns):
  1. AIPAC PAC (CMTE_ID = config committees.aipac_pac) — excluded, counted elsewhere.
  2. Corporate PAC (CMTE_TP in (Q,N) and ORG_TP in (C,W)) — excluded, counted
     elsewhere. Same rule as pull_money.py / fec-sources.md section 2.
  3. party_committees — CMTE_TP in (X, Y). FEC committee-type codes
     (fec.gov, fetched Nov 12, 2026): X = Party-nonqualified, Y = Party-qualified.
     That is the whole rule: party committees ARE the X/Y types, national and
     state alike. Verified: the six national party committees are all type Y in
     cm — DCCC C00000935, DSCC C00042366, DNC C00010603, RNC C00003418, NRSC
     C00027466, NRCC C00075820 — and DNC/RNC were confirmed by direct FEC API
     lookup Nov 12, 2026 (both committee_type Y; DNC name "DNC SERVICES CORP /
     DEMOCRATIC NATIONAL COMMITTEE", RNC "REPUBLICAN NATIONAL COMMITTEE").
     No name-pattern rule is needed, and none is used. Career total $12.45M
     across 256 distinct committees; ORG_TP is blank for $12.43M of it.
  4. leadership_pacs — CMTE_DSGN == 'D' (Leadership PAC). The cm file description
     (fec.gov, fetched Nov 12, 2026) defines the designation codes:
     A = Authorized by a candidate, B = Lobbyist/Registrant PAC,
     D = Leadership PAC, J = Joint fundraiser,
     P = Principal campaign committee, U = Unauthorized.
     CORRECTION to the task brief: leadership PACs are NOT identified by a
     CAND_ID in cm col 15. The same cm description states CAND_ID is entered
     only "when a committee has a committee type designation of H, S, or P"
     (i.e. for candidate committees themselves). Empirically, only $7.8M of
     $661M in Q/N + blank/M money has a CAND_ID in cm, and those rows are old
     or misfiled records (e.g. "SYMMS FOR SENATE COMMITTEE" filed as type Q in
     1992); the designation-D rule captures $232.6M career and matches the
     FEC's own flag, including the Lamb test case (RAPTOR PAC, EYE OF THE TIGER
     PAC are both designation D). Precedence note: D is checked after corporate
     and party, so the $16,200 of D-designation committees with ORG_TP C and the
     $239,500 with ORG_TP L land in corporate / labor respectively, not here;
     D + ORG_TP M ($37,000) lands in membership. Net effect under $0.3M.
  5. labor_pacs — CMTE_TP in (Q,N) and ORG_TP == 'L' (Labor organization).
  6. trade_pacs — CMTE_TP in (Q,N) and ORG_TP == 'T' (Trade association).
     Trade associations are NOT corporations (fec-sources.md section 2).
  7. membership_pacs — CMTE_TP in (Q,N) and ORG_TP == 'M' (Membership org).
     (AIPAC PAC itself is Q/M but is excluded by rule 1.)
  8. cooperative_pacs — CMTE_TP in (Q,N) and ORG_TP == 'V' (Cooperative).
  9. other_unclassified — everything else. Its composition is measured, not
     assumed (see diagnostics): the largest parts are Q/N PACs whose ORG_TP is
     blank in cm (the bulk file leaves ORG_TP blank for many nonconnected PACs,
     including trade/corporate ones such as the National Association of
     Realtors PAC and Ernst & Young PAC — blank does NOT mean unclassifiable
     in principle, it means cm does not say; classifying them would need the
     API organization_type per committee, thousands of calls, out of scope),
     candidate committees of OTHER candidates giving from their own campaign
     accounts (CMTE_TP H/S/P, $68.9M career), joint fundraising committees
     (CMTE_DSGN J, $8.1M+), hybrid PACs (CMTE_TP V/W, $35M+), super PACs
     (CMTE_TP O, $0.19M — legally barred from contributing; refunds/errors),
     and WinRed (see below). NOTHING is silently dropped: every matched pas2
     row lands in exactly one bucket, and the unclassified share is reported.

Earmark handling — exactly as pull_money.py: rows whose MEMO_TEXT contains
'EARMARK' (or starts 'ERMK:') AND whose amount is NEGATIVE are dropped (voided/
refunded conduit earmarks; the original transmissions are not in pas2). POSITIVE
earmark rows are individual donors' money passed through by the committee, NOT
the committee's own funds: they stay in the bucket's primary total (as in
pull_money.py and OpenSecrets) but are ALSO broken out into per-bucket
*_earmark_transmitted columns, so the committee's own money is recoverable as
primary minus earmark. They are already inside the candidate's individual total
(weball), i.e. double-counted across the tracker's own columns if added.

Dedup — exactly as pull_money.py, per cycle file: key (CMTE_ID, TRAN_ID,
CAND_ID, TRANSACTION_AMT, TRANSACTION_DT, RPT_YR); prefer non-memo row,
tie-break by FILE_NUM (same comparison as pull_money.py, replicated verbatim).
TRAN_ID alone is not a safe key (some filers reuse line-number-style TRAN_IDs).

WinRed (C00694323) — a known conduit, not a real committee contributor. It
files as a hybrid PAC (CMTE_TP V, ORG_TP blank), so it lands in
other_unclassified. Its pas2 rows are small-dollar earmarked individual
contributions ($5-$50) with EMPTY memo text, so the earmark rule cannot flag
them. Worse, its amended filings re-report old transactions as negative rows
(RPT_TP P2020 in the 2022/2024 files), so its per-cycle net is wildly
negative in 2022 (-$5.13M) and 2024 (-$5.67M) and positive in 2020 (+$5.57M):
cross-cycle void noise, not real committee money. It is KEPT in
other_unclassified (never silently dropped) and its subtotal is carried as a
diagnostic (`winred_included` per cycle, and in the diagnostics file) so the
reader can see exactly how much of other_unclassified is WinRed noise.
ActBlue (C00401224) is effectively absent from pas2 (4 rows in 2024, all
negative earmark refunds, dropped by the void-earmark rule).

Reconciliation vs weball OTHER_POL_CMTE_CONTRIB (col 26) — the recipient-side
summary (Form 3 line 11(c): contributions from other political committees
EXCLUDING party committees, which are line 11(b)). The comparable pas2 figure
is therefore other-committee + corporate + AIPAC direct, with party_committees
EXCLUDED and earmark-transmitted money netted out (the recipient reports
earmarks as individual contributions, line 11(a), not line 11(c)). It does NOT
reconcile to the dollar, in any cycle (see diagnostics + report):
  (a) weball repeats the identical candidate summary under both a chamber-
      switcher's House and Senate IDs — the same double-count dedup-applied.json
      corrects for individual contributions. It affects col 26 the same way.
      The dedup record itself is NOT applied to these columns (pas2 is
      transaction-level; per-ID amounts differ — same finding as apply_dedup.py
      for AIPAC/corporate), but the reconciliation zeroes the dropped IDs'
      col-26 copies by analogy, guarded by the same equality check
      apply_dedup.py uses. That removes most of the positive residual
      (2024: +$22.4M -> +$3.4M).
  (b) 2026 is partial and the staged pas2 file lags weball: the pas2 2026 zip
      was generated Nov 8, 2026 and contains only 991 rows dated Oct 2026,
      while weball26 covers through Oct 14, 2026 (pre-general reports, due
      Oct 22). The Lamb gap (+$32,650) is Oct 2026 transactions present in
      weball but absent from staged pas2.
  (c) A persistent NEGATIVE residual concentrates in leaders with large
      joint-fundraising / authorized-committee transfer operations (Scalise:
      -$1.3M to -$2.2M every cycle 2018-2026; McConnell, Collins, Johnson
      similar). It is NOT earmarks (only $10,010 of Scalise's $1.60M 2026 gap),
      NOT memo rows ($26k), NOT dedup (same-date/same-amount pairs are genuine
      primary+general splits), and NOT JFC recipients (zero pas2 rows name a
      JFC as OTHER_ID). Mechanism unresolved — reported, not adjusted.
All amounts summed as integer cents; output in dollars with 2 decimals.
```
