#!/usr/bin/env python3
"""Congress money tracker — other-committee contributions from FEC bulk files (pas2 + cm).

The tracker already counts corporate PAC money (pas2 rows where the contributing
committee has CMTE_TP in (Q,N) and ORG_TP in (C,W)) and AIPAC PAC direct money
(CMTE_ID C00797670), but NOTHING from any other committee — so members funded by
party committees, leadership PACs, labor PACs, or trade-association PACs show $0
there. This script fills that hole with SEPARATE columns, never blended into
total_accepted (individual + corporate PAC + AIPAC direct — that definition is
unchanged). It reads the staged pas2 + cm bulk files (cycles 1980-2026) and
produces work/other_committees_per_cycle.json (per person, per cycle, by class)
and work/other_committees.csv (per person, career totals by class).

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
"""
import json, csv, os, sys
from decimal import Decimal
from collections import defaultdict

from config import load_config

CFG = load_config()
ROOT = CFG['_root']
WORK = str(ROOT / CFG['paths']['work'])
BULK = str(ROOT / CFG['paths']['bulk'])
CYCLES = list(range(CFG['cycles']['career_start'], CFG['cycles']['career_end'] + 1, 2))
AIPAC = CFG['committees']['aipac_pac']
WINRED = 'C00694323'

BUCKETS = ['party_committees', 'leadership_pacs', 'labor_pacs', 'trade_pacs',
           'membership_pacs', 'cooperative_pacs', 'other_unclassified']

def cents(s):
    s = (s or '').strip()
    if not s:
        return 0
    return int((Decimal(s) * 100).to_integral_value())

def fmt(c):
    return f"{c/100:.2f}"

def classify(cmte, tp, org, dsgn):
    """Return bucket name, or 'aipac' / 'corporate' for the excluded columns."""
    if cmte == AIPAC:
        return 'aipac'
    if tp in ('Q', 'N') and org in ('C', 'W'):
        return 'corporate'
    if tp in ('X', 'Y'):
        return 'party_committees'
    if dsgn == 'D':
        return 'leadership_pacs'
    if tp in ('Q', 'N') and org == 'L':
        return 'labor_pacs'
    if tp in ('Q', 'N') and org == 'T':
        return 'trade_pacs'
    if tp in ('Q', 'N') and org == 'M':
        return 'membership_pacs'
    if tp in ('Q', 'N') and org == 'V':
        return 'cooperative_pacs'
    return 'other_unclassified'

roster = json.load(open(os.path.join(WORK, 'roster.json')))
cand_to_persons = defaultdict(list)
for p in roster:
    for cid in (p.get('fec_candidate_ids') or []):
        cand_to_persons[cid].append(p['person_key'])
roster_cands = set(cand_to_persons)
persons = {p['person_key']: p for p in roster}

# per-(cand, cycle, bucket) accumulators (cents)
acc = defaultdict(int)            # (cand, cycle, bucket) -> cents
acc_earmark = defaultdict(int)    # (cand, cycle, bucket) -> earmark-transmitted cents
acc_winred = defaultdict(int)     # (cand, cycle) -> WinRed cents (subset of other_unclassified)
acc_corp = defaultdict(int)       # (cand, cycle) -> corporate cents (cross-check vs pull_money)
acc_corp_earmark = defaultdict(int)
acc_aipac = defaultdict(int)      # (cand, cycle) -> AIPAC direct cents (cross-check)
acc_aipac_earmark = defaultdict(int)
# unclassified composition diagnostics, per cycle: sub-bucket -> cents
unclass_comp = defaultdict(lambda: defaultdict(int))
per_cycle_diag = []

for cy in CYCLES:
    # same-cycle cm: cmte_id -> (tp, org, dsgn)
    cm = {}
    cm_rows = cm_bad = 0
    with open(os.path.join(BULK, 'cm', str(cy), 'cm.txt')) as f:
        for line in f:
            cm_rows += 1
            p = line.rstrip('\n').split('|')
            if len(p) != 15:
                cm_bad += 1
                continue
            cm[p[0]] = (p[9], p[12], p[8])
    rows = bad = matched = 0
    dedup = {}   # key -> (memo, file_num, amount, bucket, is_earmark, cmte)
    dedup_dropped_n = 0
    dedup_dropped_c = 0
    void_earmark_n = 0
    void_earmark_c = 0
    cm_missing = set()
    cm_missing_rows = 0
    with open(os.path.join(BULK, 'pas2', str(cy), 'itpas2.txt')) as f:
        for line in f:
            rows += 1
            p = line.rstrip('\n').split('|')
            if len(p) != 22:
                bad += 1
                continue
            tp = p[5]
            if tp not in ('24K', '24P'):
                continue
            cand = p[16]
            if cand not in roster_cands:
                continue
            matched += 1
            cmte = p[0]
            amt = cents(p[14])
            memo_text = p[20] or ''
            is_earmark = ('EARMARK' in memo_text) or memo_text.startswith('ERMK:')
            if is_earmark and amt < 0:
                void_earmark_n += 1
                void_earmark_c += amt
                continue  # conduit-earmark void; originals not in pas2 (see header)
            rec = cm.get(cmte)
            if rec is None:
                cm_missing.add(cmte)
                cm_missing_rows += 1
                continue  # cannot classify without a cm record; measured, never imputed
            bucket = classify(cmte, rec[0], rec[1], rec[2])
            tran = p[17] or p[21]  # TRAN_ID, fallback SUB_ID
            try:
                filenum = int(p[18] or 0)
            except ValueError:
                filenum = 0
            memo = 1 if p[19] == 'X' else 0
            key = (cmte, tran, cand, amt, p[13], p[3])
            prev = dedup.get(key)
            if prev is None:
                dedup[key] = (memo, filenum, amt, bucket, is_earmark, cmte)
            else:
                # prefer non-memo; tie-break FILE_NUM (same comparison as pull_money.py)
                if (memo, filenum) < (prev[0], prev[1]):
                    dedup[key] = (memo, filenum, amt, bucket, is_earmark, cmte)
                    dedup_dropped_n += 1
                    dedup_dropped_c += prev[2]
                else:
                    dedup_dropped_n += 1
                    dedup_dropped_c += amt
    kept = defaultdict(int)
    kept_earmark = defaultdict(int)
    kept_winred = 0
    kept_corp = kept_corp_e = kept_aipac = kept_aipac_e = 0
    comp = defaultdict(int)
    for (cmte, tran, cand, amt0, dt, rptyr), (memo, filenum, amt, bucket, is_earmark, cmte2) in dedup.items():
        if bucket == 'aipac':
            acc_aipac[(cand, cy)] += amt
            kept_aipac += amt
            if is_earmark:
                acc_aipac_earmark[(cand, cy)] += amt
                kept_aipac_e += amt
        elif bucket == 'corporate':
            acc_corp[(cand, cy)] += amt
            kept_corp += amt
            if is_earmark:
                acc_corp_earmark[(cand, cy)] += amt
                kept_corp_e += amt
        else:
            acc[(cand, cy, bucket)] += amt
            kept[bucket] += amt
            if is_earmark:
                acc_earmark[(cand, cy, bucket)] += amt
                kept_earmark[bucket] += amt
            if cmte == WINRED:
                acc_winred[(cand, cy)] += amt
                kept_winred += amt
            # unclassified composition (measured, not a separate bucket)
            if bucket == 'other_unclassified':
                tp, org, dsgn = cm[cmte]
                if cmte == WINRED:
                    comp['winred_conduit'] += amt
                elif tp in ('H', 'S', 'P'):
                    comp['candidate_committees'] += amt
                elif dsgn == 'J':
                    comp['joint_fundraisers'] += amt
                elif tp in ('V', 'W'):
                    comp['hybrid_pacs'] += amt
                elif tp == 'O':
                    comp['super_pacs'] += amt
                elif tp in ('Q', 'N'):
                    comp['qn_blank_org'] += amt
                else:
                    comp['other_types'] += amt
    for k, v in comp.items():
        unclass_comp[cy][k] += v
    per_cycle_diag.append({'cycle': cy, 'cm_rows': cm_rows, 'cm_bad_fields': cm_bad,
                           'pas2_rows': rows, 'pas2_bad_fields': bad,
                           'pas2_matched_roster': matched,
                           'cm_missing_committees': len(cm_missing),
                           'cm_missing_rows': cm_missing_rows,
                           'dedup_dropped_rows': dedup_dropped_n,
                           'dedup_dropped_cents': dedup_dropped_c,
                           'void_earmark_rows': void_earmark_n,
                           'void_earmark_cents': void_earmark_c,
                           'kept_cents': {b: kept[b] for b in BUCKETS},
                           'kept_earmark_cents': {b: kept_earmark[b] for b in BUCKETS if kept_earmark[b]},
                           'kept_winred_cents': kept_winred,
                           'kept_corporate_cents': kept_corp,
                           'kept_corporate_earmark_cents': kept_corp_e,
                           'kept_aipac_cents': kept_aipac,
                           'kept_aipac_earmark_cents': kept_aipac_e,
                           'unclassified_composition_cents': dict(comp)})

# ---------------- cross-check vs pull_money / config methodology totals ----------------
meth = CFG['verification']['methodology_totals']
tot_corp = sum(acc_corp.values())
tot_corp_e = sum(acc_corp_earmark.values())
tot_aipac = sum(acc_aipac.values())
tot_aipac_e = sum(acc_aipac_earmark.values())
checks = {
    'corporate_pac_career': (tot_corp, int(Decimal(str(meth['corporate_pac_career'])) * 100)),
    'corporate_earmark_transmitted_career': (tot_corp_e, int(Decimal(str(meth['corporate_earmark_transmitted_career'])) * 100)),
    'aipac_pac_direct_career': (tot_aipac, int(Decimal(str(meth['aipac_pac_direct_career'])) * 100)),
    'aipac_earmark_transmitted_career': (tot_aipac_e, int(Decimal(str(meth['aipac_earmark_transmitted_career'])) * 100)),
}

# ---------------- reconciliation vs weball OTHER_POL_CMTE_CONTRIB (col 26) ----------------
# dedup-applied.json corrects the weball double-count for individual contributions;
# the same whole-summary duplication affects col 26. It is NOT applied to these
# pas2 columns (transaction-level); it is applied here ONLY to the weball side
# of the reconciliation, guarded by the same equality check apply_dedup.py uses.
dedup_applied = json.load(open(os.path.join(WORK, 'dedup-applied.json')))
drop_by_cycle = defaultdict(set)   # cycle -> dropped cand ids
for e in dedup_applied:
    for did in e['dropped_ids']:
        drop_by_cycle[e['cycle']].add(did)
recon = []
for cy in CYCLES:
    yy = f"{cy % 100:02d}"
    web_raw = {}
    for line in open(os.path.join(BULK, 'weball', f'weball{yy}.txt')):
        p = line.rstrip('\n').split('|')
        if len(p) == 30 and p[0] in roster_cands:
            web_raw[p[0]] = cents(p[25])
    web_corr = dict(web_raw)
    dropped_zeroed = 0
    dropped_mismatch = 0
    for e in dedup_applied:
        if e['cycle'] != cy:
            continue
        kept_id = e['kept_id']
        for did in e['dropped_ids']:
            if did in web_corr and kept_id in web_corr:
                if web_corr[did] == web_corr[kept_id]:
                    web_corr[did] = 0
                    dropped_zeroed += 1
                else:
                    dropped_mismatch += 1
    # pas2 non-party total per cand: other buckets + corporate + aipac (earmarks in,
    # and net of earmarks, for comparison — the recipient reports earmarks as
    # individual money, line 11(a), not line 11(c))
    pas_gross = defaultdict(int)
    pas_earm = defaultdict(int)
    for (cand, cyc, bucket), v in acc.items():
        if cyc == cy:
            pas_gross[cand] += v
            pas_earm[cand] += acc_earmark.get((cand, cy, bucket), 0)
    for (cand, cyc), v in acc_corp.items():
        if cyc == cy:
            pas_gross[cand] += v
            pas_earm[cand] += acc_corp_earmark.get((cand, cy), 0)
    for (cand, cyc), v in acc_aipac.items():
        if cyc == cy:
            pas_gross[cand] += v
            pas_earm[cand] += acc_aipac_earmark.get((cand, cy), 0)
    cands = set(web_raw) | set(pas_gross)
    res_raw = res_corr = res_corr_net = 0
    exact_raw = exact_corr = exact_corr_net = 0
    n = 0
    largest_pos = []
    largest_neg = []
    for cand in cands:
        w_raw = web_raw.get(cand, 0)
        w_corr = web_corr.get(cand, 0)
        g = pas_gross.get(cand, 0)
        net = g - pas_earm.get(cand, 0)
        if w_raw or g:
            n += 1
            res_raw += w_raw - g
            res_corr += w_corr - g
            res_corr_net += w_corr - net
            if w_raw - g == 0:
                exact_raw += 1
            if w_corr - g == 0:
                exact_corr += 1
            if w_corr - net == 0:
                exact_corr_net += 1
            largest_pos.append((w_corr - net, cand, w_corr, net))
            largest_neg.append((w_corr - net, cand, w_corr, net))
    largest_pos.sort(reverse=True)
    largest_neg.sort()
    recon.append({'cycle': cy, 'candidates_with_weball_or_pas2': n,
                  'weball_other_pol_total_cents': sum(web_raw.values()),
                  'weball_corrected_total_cents': sum(web_corr.values()),
                  'pas2_nonparty_gross_cents': sum(pas_gross.values()),
                  'pas2_nonparty_net_of_earmarks_cents': sum(pas_gross.values()) - sum(pas_earm.values()),
                  'pas2_earmark_transmitted_cents': sum(pas_earm.values()),
                  'residual_weball_raw_minus_pas2_gross_cents': res_raw,
                  'residual_weball_corrected_minus_pas2_gross_cents': res_corr,
                  'residual_weball_corrected_minus_pas2_net_cents': res_corr_net,
                  'exact_matches_raw': exact_raw, 'exact_matches_corrected': exact_corr,
                  'exact_matches_corrected_net': exact_corr_net,
                  'dedup_dropped_ids_zeroed': dropped_zeroed,
                  'dedup_dropped_ids_col26_mismatch': dropped_mismatch,
                  'largest_positive_residuals': [
                      {'candidate_id': c, 'residual_cents': r, 'weball_corrected_cents': w, 'pas2_net_cents': p}
                      for r, c, w, p in largest_pos[:5]],
                  'largest_negative_residuals': [
                      {'candidate_id': c, 'residual_cents': r, 'weball_corrected_cents': w, 'pas2_net_cents': p}
                      for r, c, w, p in largest_neg[:5]]})

# ---------------- aggregate to persons ----------------
def person_bucket_total(p, bucket):
    return sum(acc.get((cid, cy, bucket), 0) for cid in (p.get('fec_candidate_ids') or []) for cy in CYCLES)

def person_earmark_total(p, bucket):
    return sum(acc_earmark.get((cid, cy, bucket), 0) for cid in (p.get('fec_candidate_ids') or []) for cy in CYCLES)

def person_winred_total(p):
    return sum(acc_winred.get((cid, cy), 0) for cid in (p.get('fec_candidate_ids') or []) for cy in CYCLES)

out_rows = []
per_cycle = {}
for p in roster:
    pk = p['person_key']
    ids = p.get('fec_candidate_ids') or []
    totals = {b: person_bucket_total(p, b) for b in BUCKETS}
    earmarks = {b: person_earmark_total(p, b) for b in BUCKETS}
    total_other = sum(totals.values())
    winred = person_winred_total(p)
    notes = []
    if not ids:
        notes.append('no FEC candidate IDs in roster')
    else:
        any_row = any(
            acc.get((cid, cy, b), 0) or acc_corp.get((cid, cy), 0) or acc_aipac.get((cid, cy), 0)
            for cid in ids for cy in CYCLES for b in BUCKETS)
        if not any_row:
            notes.append('no FEC activity found')
        elif total_other == 0:
            notes.append('FEC activity found; all other-committee totals zero')
    dup = [q for cid in ids for q in cand_to_persons[cid] if q != pk]
    if dup:
        notes.append('duplicate roster entry: FEC ID shared with ' + ', '.join(sorted(set(dup))))
    if winred != 0:
        notes.append(f'other_unclassified includes WinRed conduit net {fmt(winred)} (see diagnostics)')
    if not ids:
        # unknown, not zero: nulls (empty strings) for every money column
        row = {'person_key': pk, 'full_name': p['full_name'],
               'fec_candidate_ids': ';'.join(ids)}
        for b in BUCKETS:
            row[f'{b}_career'] = ''
            row[f'{b}_earmark_transmitted_career'] = ''
        row['other_committees_total_career'] = ''
        row['data_notes'] = ' | '.join(notes)
    else:
        row = {'person_key': pk, 'full_name': p['full_name'],
               'fec_candidate_ids': ';'.join(ids)}
        for b in BUCKETS:
            row[f'{b}_career'] = fmt(totals[b])
            row[f'{b}_earmark_transmitted_career'] = fmt(earmarks[b])
        row['other_committees_total_career'] = fmt(total_other)
        row['data_notes'] = ' | '.join(notes)
    out_rows.append(row)
    entries = []
    for cy in CYCLES:
        for cid in ids:
            vals = {b: acc.get((cid, cy, b), 0) for b in BUCKETS}
            em = {b: acc_earmark.get((cid, cy, b), 0) for b in BUCKETS if acc_earmark.get((cid, cy, b), 0)}
            wr = acc_winred.get((cid, cy), 0)
            if any(vals.values()) or em:
                entries.append({'cycle': cy, 'candidate_id': cid,
                                **{b: fmt(vals[b]) for b in BUCKETS},
                                'earmark_transmitted': {b: fmt(v) for b, v in em.items()},
                                'winred_included': fmt(wr)})
    per_cycle[pk] = {'person_key': pk, 'full_name': p['full_name'], 'per_cycle': entries}

csv_fields = (['person_key', 'full_name', 'fec_candidate_ids']
              + [f'{b}_career' for b in BUCKETS]
              + ['other_committees_total_career']
              + [f'{b}_earmark_transmitted_career' for b in BUCKETS]
              + ['data_notes'])
with open(os.path.join(WORK, 'other_committees.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=csv_fields)
    w.writeheader()
    w.writerows(out_rows)

with open(os.path.join(WORK, 'other_committees_per_cycle.json'), 'w') as f:
    json.dump(per_cycle, f, indent=1)

# Lamb validation (2026, candidate H6AZ05265): pas2-derived vs weball col 26
lamb_cy = 2026
lamb_cid = 'H6AZ05265'
lamb_breakdown = {b: acc.get((lamb_cid, lamb_cy, b), 0) for b in BUCKETS}
lamb_earmark = {b: acc_earmark.get((lamb_cid, lamb_cy, b), 0) for b in BUCKETS if acc_earmark.get((lamb_cid, lamb_cy, b), 0)}
lamb_pas2_total = sum(lamb_breakdown.values())
lamb_weball = None
for line in open(os.path.join(BULK, 'weball', 'weball26.txt')):
    pp = line.rstrip('\n').split('|')
    if len(pp) == 30 and pp[0] == lamb_cid:
        lamb_weball = cents(pp[25])
        break
lamb_check = {'candidate_id': lamb_cid, 'cycle': lamb_cy,
              'pas2_breakdown_cents': lamb_breakdown,
              'pas2_earmark_transmitted_cents': lamb_earmark,
              'pas2_total_cents': lamb_pas2_total,
              'pas2_corporate_cents': acc_corp.get((lamb_cid, lamb_cy), 0),
              'pas2_aipac_cents': acc_aipac.get((lamb_cid, lamb_cy), 0),
              'weball_other_pol_cmte_contrib_cents': lamb_weball,
              'weball_minus_pas2_cents': (lamb_weball - lamb_pas2_total) if lamb_weball is not None else None}

roster_totals = {b: sum(person_bucket_total(p, b) for p in roster) for b in BUCKETS}
roster_earmarks = {b: sum(person_earmark_total(p, b) for p in roster) for b in BUCKETS}
diag = {'per_cycle': per_cycle_diag,
        'unclassified_composition_career_cents': {k: sum(unclass_comp[cy][k] for cy in CYCLES)
                                                  for k in set().union(*[set(unclass_comp[cy]) for cy in CYCLES])},
        'roster_totals_cents': roster_totals,
        'roster_earmark_transmitted_cents': roster_earmarks,
        'roster_winred_included_cents': sum(acc_winred.values()),
        'cross_checks_vs_methodology': {
            k: {'recomputed_cents': a, 'methodology_cents': b, 'match': a == b}
            for k, (a, b) in checks.items()},
        'reconciliation_vs_weball_col26': recon,
        'lamb_validation': lamb_check,
        'dedup_applied_finding': (
            'dedup-applied.json corrects the WEBALL double-count (identical '
            'TTL_INDIV_CONTRIB repeated under a chamber-switcher\'s House and '
            'Senate IDs). It does NOT change any pas2-derived column in this '
            'script: pas2 is transaction-level, so per-ID amounts differ and '
            'there is no duplicate copy to drop — the same finding '
            'apply_dedup.py records for AIPAC/corporate. It DOES affect the '
            'weball side of the reconciliation: col 26 (OTHER_POL_CMTE_CONTRIB) '
            'is duplicated under both IDs the same way, so the reconciliation '
            'zeroes the dropped IDs\' col-26 copies (guarded by the same '
            'equality check apply_dedup.py uses) and reports raw vs corrected '
            'residuals separately. No correction was invented for these columns.')}
with open(os.path.join(WORK, 'other_committees_diagnostics.json'), 'w') as f:
    json.dump(diag, f, indent=1)

print('persons:', len(out_rows))
print('null (no FEC IDs):', sum(1 for r in out_rows if r['other_committees_total_career'] == ''))
for b in BUCKETS:
    print(f'TOTAL {b} career $:', fmt(roster_totals[b]),
          f'(earmark transmitted ${fmt(roster_earmarks[b])})')
print('TOTAL other-committee career $:', fmt(sum(roster_totals.values())))
print('TOTAL WinRed included in other_unclassified $:', fmt(sum(acc_winred.values())))
print('TOTAL dedup dropped rows:', sum(d['dedup_dropped_rows'] for d in per_cycle_diag),
      'cents:', sum(d['dedup_dropped_cents'] for d in per_cycle_diag))
print('TOTAL VOID-earmark rows excluded:', sum(d['void_earmark_rows'] for d in per_cycle_diag),
      'cents:', sum(d['void_earmark_cents'] for d in per_cycle_diag))
print('TOTAL cm-missing rows:', sum(d['cm_missing_rows'] for d in per_cycle_diag))
for k, (a, b) in checks.items():
    print(f"CHECK {k}: recomputed ${fmt(a)} vs methodology ${fmt(b)} -> {'MATCH' if a == b else 'MISMATCH'}")
print('LAMB 2026 pas2 breakdown:', {b: fmt(v) for b, v in lamb_breakdown.items()},
      'earmark:', {b: fmt(v) for b, v in lamb_earmark.items()})
print(f"LAMB 2026 pas2 total ${fmt(lamb_pas2_total)} vs weball ${fmt(lamb_weball)} "
      f"residual ${fmt(lamb_weball - lamb_pas2_total)}")
for r in recon:
    print(f"RECON {r['cycle']}: weball_raw ${fmt(r['weball_other_pol_total_cents'])} "
          f"weball_corr ${fmt(r['weball_corrected_total_cents'])} "
          f"pas2_net ${fmt(r['pas2_nonparty_net_of_earmarks_cents'])} "
          f"resid_corr_net ${fmt(r['residual_weball_corrected_minus_pas2_net_cents'])} "
          f"exact_corr_net {r['exact_matches_corrected_net']}/{r['candidates_with_weball_or_pas2']}")
ok = all(a == b for a, b in checks.values())
if not ok:
    sys.exit('CROSS-CHECK FAILED: recomputed corporate/AIPAC totals do not match methodology totals')
print('wrote work/other_committees.csv, work/other_committees_per_cycle.json, work/other_committees_diagnostics.json')
