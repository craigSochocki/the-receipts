#!/usr/bin/env python3
"""2026-cycle columns, clean/dirty flags, and the primary-target list.

For each person, from the 2026 entries in `per_cycle` / `udp_per_cycle`
and the 2026 opposition credit in `opposition-computed.json`:
- `individual_2026` / `corp_2026` / `aipac_direct_2026` — the 2026
  per-cycle sums, rounded to 2dp; an int `0` when the person has no
  2026 per-cycle entries at all (plain `sum([])` is int 0 — this
  int/float split is how the committed dataset stores it).
- `udp_support_2026` — the 2026 `udp_per_cycle` sum, same rule.
- `udp_opp_credit_2026` — the person's 2026 share of UDP opposition
  credit (float, `0.0` when none).
- `udp_benefit_2026` = support + credit; `dirty_2026` = corp + AIPAC
  direct + benefit. Individual contributions are NOT dirty money.
  (`dirty_career`, the career analog, is computed in
  `compute_ranking.py` — it runs first and rewrites the dataset in
  final column order.)
- `self_funding_2026`, `cand_loans_2026`, `cand_contrib_2026`,
  `total_receipts_2026`, `total_disbursements_2026` — the 2026
  `self_funding_per_cycle` sums, same int-0-when-empty rule.
  `cash_on_hand_2026` — the 2026 `self_funding_per_cycle` cash on
  hand (a stock, not a sum); null when the person has no 2026
  self-funding entry.
- `other_committees_total_2026` — the 2026
  `other_committees_per_cycle` total (all seven classes), same rule.
- `all_ie_support_2026`, `all_ie_oppose_2026`, `all_ie_total_2026` —
  the 2026 `all_ie_per_cycle` sums (total includes blank-direction
  rows), same rule.
- `dep_share_2026` = round((corp + AIPAC) / (individual + corp +
  AIPAC), 4) when the denominator is positive, else null. (The
  denominator is zero for people with no 2026 data, and negative for
  three people with negative 2026 corporate PAC refunds — McConnell,
  Peters, Tina Smith.) Negative shares are kept when the denominator
  is positive.
- `clean_2026` — True when corp, AIPAC direct, UDP support, and UDP
  opposition credit are ALL zero in 2026. Individual contributions
  are ALLOWED: a candidate can raise millions from individuals and
  still be clean. A person is clean ONLY when 2026 linkage exists —
  absence of linkage means UNVERIFIED (null), never clean by absence
  of data. Linkage evidence is a 2026 entry in a committee-money
  source: a tracked `per_cycle` / `udp_per_cycle` 2026 entry, or a
  `self_funding_per_cycle` 2026 entry whose coverage end date falls
  in calendar 2026 (the candidate's own committee filed a 2026-cycle
  report covering 2026 activity). Other-committee and all-IE 2026
  entries do NOT establish linkage on their own: they are third-party
  reports about a race and can be filed under a stale candidate ID —
  the proof case is Elaine Luria (see below), whose linked ID carries
  $85,610 of other-committee money and $685,786 of all-IE support in
  2026 while her real 2026 campaign (H6VA02198, $8,044,063.94
  receipts, coverage through 10/14/2026) is unlinked. Her linked ID's
  2026 weball row covers only through 07/15/2025 (a dormant committee
  winding down, $590.89 receipts), so she stays null. Anthony
  Constantino is the positive case: his tracked 2026 $0s are real —
  his self-funding 2026 entry (loans $14,400,000, coverage
  10/14/2026) plus all-IE support $459,491.94 / oppose $3,721,257.82
  prove the committee is linked — so he is verified clean=True WITH
  evidence (his True used to rest on having no per-cycle entries at
  all, which the old has_pre_2026 guard could not catch).
- `unopposed_2026` — True when the person ran unopposed in 2026: every
  2026 candidate ID of theirs in weball26 sits in a race where no OTHER
  candidate has total receipts over $0. A filed opponent with $0
  receipts does not make the race contested; a write-in opponent who
  never filed does not appear. The race comes from the filing's own
  weball row (office prefix + state + district), NOT the roster
  district — the two disagree for the Northern Mariana Islands
  delegate (roster district 0; the FEC files the 2026 MP race under
  district 01, with two stale H8 IDs under district 00). Kimberlyn
  King-Hinds faced Galvin Deleon Guerrero (IND, $31,476.11 receipts;
  36.3% of the vote Nov 3, 2026), so she is contested and stays
  verified-clean — an early roster-district lookup wrongly read her as
  unopposed. Three people are unopposed and therefore null, not clean:
  Ayanna Pressley (MA-07, no opponent filed), Sara Jacobs (CA-51, one
  $0 opponent), Aumua Amata Coleman Radewagen (AS, no opponent filed).
  Six more ran unopposed but took dirty money, so they stay
  clean=False — `unopposed_2026` is a race fact, independent of the
  clean verdict. Career-clean is untouched by this rule: it is derived
  from career money columns only, so a career-clean member who runs
  unopposed keeps career-clean status (King-Hinds is the proof case:
  career-clean AND contested-clean in 2026).
  In practice the rule leaves: exactly four nulls (Luria unverified +
  three unopposed); True 81 / False 579; 120th House clean 64
  (61 D, 3 R).

Gap notes appended to `data_notes` (exact committed text):
- corp_2026 > 0 and individual_2026 == 0: the $0 individual figure is
  a likely missing-committee-linkage gap (Melissa Bean, Hilda Solis —
  both $3,500 corporate PAC, $0 individual; the amount is formatted
  from the data).
- the unverified person gets two segments: the original 2026-step
  DATA GAP note (written when clean_2026 was still True — its wording
  is preserved verbatim) and the later UNVERIFIED note that records
  the fix. Both are appended, in that order.

Also writes `data/intermediate/primary-targets.md`: House Democrats in the 120th
with dirty_2026 > 0, ranked by dirty_2026 descending — the
primary-challenge research list (public-facing use needs Craig's
explicit go-ahead; see STATUS.md).

Reads the dataset written by `compute_ranking.py` and rewrites both
files in the FINAL column order (note: the CSV and JSON orders differ
in the 2026 trio — CSV is individual/corp/AIPAC, JSON is
corp/AIPAC/individual; both orders come from config). Fails loudly if
the clean counts do not match the expectations in config
(verification.clean_2026).
"""
import json

import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG['_root']

opp = json.load(open(ROOT / CFG['paths']['opposition_computed']))
credit_2026 = {}
for race, pk, _name, amount, _detail in opp['credit_detail']:
    if race[0] == CFG['cycles']['current'] and not pk.startswith('__nonroster__'):
        # Sum across phases: one person can now be credited in two phases
        # of the same race (the race key includes ele_type).
        credit_2026[pk] = round(credit_2026.get(pk, 0.0) + float(amount), 2)

records = json.load(open(ROOT / CFG['paths']['dataset_json']))

BEAN_SOLIS_GAP = (' | 2026 DATA GAP: corporate PAC ${corp} in 2026 but $0 individual contributions — '
                  'the $0 individual figure is a likely missing-committee-linkage gap, not a real zero; '
                  'do not present as $0 raised from individuals.')
LURIA_GAP = (' | 2026 DATA GAP: no 2026 per-cycle data found under the roster\'s linked candidate ID '
             '(returning former member; 2026 committee ID not linked) — clean_2026=True reflects '
             'absence of data, NOT verified zero fundraising; do not present as confirmed clean.')
LURIA_UNVERIFIED = (' | 2026 clean status UNVERIFIED — no 2026 per-cycle data under linked candidate ID '
                    '(returning former member; 2026 committee ID not linked). '
                    'Not counted as verified-clean.')
UNOPPOSED_NOTE = (' | 2026 clean status UNOPPOSED — ran unopposed in 2026 ({race}): '
                  'no opponent with receipts over $0, so $0 dirty money reflects no contest, '
                  'not a verified-clean campaign. Not counted as verified-clean.')


def load_weball_2026_races():
    """2026 races from the FEC all-candidates file (weball26).

    Returns (race_map, by_cid): race_map maps (office, state, district)
    to [(candidate_id, total_receipts)]; by_cid maps candidate_id to
    its (office, state, district). weball is pipe-delimited, 30 fields,
    no header: p[0] candidate ID (H/S/P prefix = office), p[5] total
    receipts, p[18] state, p[19] district. The race comes from the
    filing's own row, not the roster district (see module docstring —
    the MP delegate race is filed under district 01, not the roster's 0).
    """
    yy = f"{CFG['cycles']['current'] % 100:02d}"
    path = ROOT / CFG['paths']['bulk'] / 'weball' / f'weball{yy}.txt'
    race_map = {}
    by_cid = {}
    with open(path) as f:
        for line in f:
            p = line.rstrip('\n').split('|')
            if len(p) != 30:
                continue
            try:
                receipts = float(p[5] or 0)
            except ValueError:
                receipts = 0.0
            race = (p[0][0], p[18], p[19])
            race_map.setdefault(race, []).append((p[0], receipts))
            by_cid[p[0]] = race
    return race_map, by_cid


def unopposed_2026_races(r, race_map, by_cid):
    """The person's 2026 races, and the subset with no funded opponent.

    Returns (races, unopposed): races is every (office, state,
    district) race behind a 2026 candidate ID of theirs in weball26;
    unopposed is the subset in which no OTHER candidate has total
    receipts over $0. Both are empty when they filed no 2026
    candidacy at all. A filed opponent with $0 receipts does not
    contest the race; a write-in opponent who never filed does not
    appear.
    """
    ids = set(r['fec_candidate_ids'] or [])
    races = sorted({by_cid[cid] for cid in ids if cid in by_cid})
    unopposed = [race for race in races
                 if not any(cid not in ids and receipts > 0
                            for cid, receipts in race_map.get(race, []))]
    return races, unopposed


def format_race(race):
    office, state, district = race
    return f'{state} Senate' if office == 'S' else f'{state}-{district}'


def cycle_sum(entries, field):
    vals = [e[field] for e in entries if e['cycle'] == CFG['cycles']['current']]
    return round(sum(vals), 2) if vals else 0


def has_2026_linkage(r):
    """2026 committee linkage evidence (see module docstring).

    True when the person's 2026 campaign committee is verifiably
    linked: a tracked per_cycle / udp_per_cycle 2026 entry, or a
    self-funding 2026 entry whose coverage end date falls in calendar
    2026. Other-committee and all-IE 2026 entries do not count on
    their own (third-party reports; Luria's stale-ID case).
    """
    if any(e['cycle'] == CFG['cycles']['current'] for e in r['per_cycle']):
        return True
    if any(e['cycle'] == CFG['cycles']['current'] for e in r['udp_per_cycle']):
        return True
    for e in r['self_funding_per_cycle']:
        if (e['cycle'] == CFG['cycles']['current']
                and str(e.get('coverage_end_date', '')).endswith('/2026')):
            return True
    return False


race_map, by_cid = load_weball_2026_races()

for r in records:
    r['individual_2026'] = cycle_sum(r['per_cycle'], 'individual')
    r['corp_2026'] = cycle_sum(r['per_cycle'], 'corporate_pac')
    r['aipac_direct_2026'] = cycle_sum(r['per_cycle'], 'aipac_pac_direct')
    r['udp_support_2026'] = cycle_sum(r['udp_per_cycle'], 'udp_ie_support')
    r['udp_opp_credit_2026'] = credit_2026.get(r['person_key'], 0.0)
    r['udp_benefit_2026'] = round(r['udp_support_2026'] + r['udp_opp_credit_2026'], 2)
    r['dirty_2026'] = round(r['corp_2026'] + r['aipac_direct_2026'] + r['udp_benefit_2026'], 2)
    denom = r['individual_2026'] + r['corp_2026'] + r['aipac_direct_2026']
    r['dep_share_2026'] = (round((r['corp_2026'] + r['aipac_direct_2026']) / denom, 4)
                           if denom > 0 else None)

    # New 2026 columns (complete-financial-picture build).
    sf26 = [e for e in r['self_funding_per_cycle'] if e['cycle'] == CFG['cycles']['current']]
    r['self_funding_2026'] = (round(sum(e['candidate_contributions'] + e['candidate_loans']
                                        for e in sf26), 2) if sf26 else 0)
    r['cand_loans_2026'] = cycle_sum(r['self_funding_per_cycle'], 'candidate_loans')
    r['cand_contrib_2026'] = cycle_sum(r['self_funding_per_cycle'], 'candidate_contributions')
    r['total_receipts_2026'] = cycle_sum(r['self_funding_per_cycle'], 'total_receipts')
    r['total_disbursements_2026'] = cycle_sum(r['self_funding_per_cycle'], 'total_disbursements')
    r['cash_on_hand_2026'] = (round(sum(e['cash_on_hand'] for e in sf26), 2)
                              if sf26 else None)
    oc26 = [e for e in r['other_committees_per_cycle'] if e['cycle'] == CFG['cycles']['current']]
    r['other_committees_total_2026'] = (
        round(sum(sum(e[b] for b in ('party_committees', 'leadership_pacs', 'labor_pacs',
                                     'trade_pacs', 'membership_pacs', 'cooperative_pacs',
                                     'other_unclassified')) for e in oc26), 2) if oc26 else 0)
    aie26 = [e for e in r['all_ie_per_cycle'] if e['cycle'] == CFG['cycles']['current']]
    r['all_ie_support_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_support')
    r['all_ie_oppose_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_oppose')
    r['all_ie_total_2026'] = cycle_sum(r['all_ie_per_cycle'], 'all_ie_total')

    # Unopposed in 2026 (methodology §14): a race with no funded
    # opponent is not a clean campaign — $0 dirty money there reflects
    # no contest. Unopposed is a race fact for everyone (nine people
    # ran unopposed, six of them dirty); only a would-be-clean
    # unopposed verdict becomes null. Career-clean is derived from
    # career money columns only and is untouched by this rule.
    races_2026, unopp_races = unopposed_2026_races(r, race_map, by_cid)
    r['unopposed_2026'] = bool(races_2026) and len(unopp_races) == len(races_2026)

    # Clean rule (methodology §14): all four dirty components zero,
    # and only when 2026 linkage exists (generalized Nov 12, 2026 —
    # the old rule hardcoded the Luria exception via has_pre_2026).
    # An unopposed would-be-clean verdict is null, not True.
    if r['in_120th'] == 'yes' and not has_2026_linkage(r):
        r['clean_2026'] = None
        r['data_notes'] = r['data_notes'] + LURIA_GAP + LURIA_UNVERIFIED
    elif (r['unopposed_2026'] and r['corp_2026'] == 0 and r['aipac_direct_2026'] == 0
            and r['udp_support_2026'] == 0 and r['udp_opp_credit_2026'] == 0):
        r['clean_2026'] = None
        race_label = ', '.join(format_race(race) for race in unopp_races)
        r['data_notes'] = r['data_notes'] + UNOPPOSED_NOTE.format(race=race_label)
    else:
        r['clean_2026'] = (r['corp_2026'] == 0 and r['aipac_direct_2026'] == 0
                           and r['udp_support_2026'] == 0 and r['udp_opp_credit_2026'] == 0)

    # Gap note: corporate PAC money with $0 individual in 2026.
    if r['corp_2026'] > 0 and r['individual_2026'] == 0:
        r['data_notes'] = r['data_notes'] + BEAN_SOLIS_GAP.format(corp=f'{r["corp_2026"]:,.0f}')

# ---- Assert the expected clean counts (config verification.clean_2026) ----
exp = CFG['verification']['clean_2026']
counts = {'true_total': sum(1 for r in records if r['clean_2026'] is True),
          'false_total': sum(1 for r in records if r['clean_2026'] is False),
          'null_total': sum(1 for r in records if r['clean_2026'] is None)}
for key in ('true_total', 'false_total', 'null_total'):
    if counts[key] != exp[key]:
        raise SystemExit(f'clean_2026 {key} count {counts[key]} != expected {exp[key]}')
house120 = [r for r in records if r['in_120th'] == 'yes' and r['chamber_120'] == 'House']
house_clean = [r for r in house120 if r['clean_2026'] is True]
if len(house_clean) != exp['house_120th_verified_clean']:
    raise SystemExit(f"120th House clean {len(house_clean)} != expected "
                     f"{exp['house_120th_verified_clean']}")
by_party = {'Democrat': sum(1 for r in house_clean if r['party_120'] == 'Democrat'),
            'Republican': sum(1 for r in house_clean if r['party_120'] == 'Republican')}
for party in ('Democrat', 'Republican'):
    key = f"house_120th_verified_clean_{party.lower()}"
    if by_party[party] != exp[key]:
        raise SystemExit(f'120th House clean {party} {by_party[party]} != expected {exp[key]}')
career_clean = [r for r in house120 if r['corporate_pac_career'] == 0
                and r['aipac_pac_direct_career'] == 0 and r['udp_ie_support_career'] == 0]
if len(career_clean) != exp['house_120th_career_clean']:
    raise SystemExit(f"career-clean 120th House {len(career_clean)} != expected "
                     f"{exp['house_120th_career_clean']}")
career_by_party = {'Democrat': sum(1 for r in career_clean if r['party_120'] == 'Democrat'),
                   'Republican': sum(1 for r in career_clean if r['party_120'] == 'Republican')}
for party in ('Democrat', 'Republican'):
    key = f"house_120th_career_clean_{party.lower()}"
    if career_by_party[party] != exp[key]:
        raise SystemExit(f'career-clean 120th House {party} {career_by_party[party]} '
                         f'!= expected {exp[key]}')
career_keys = {r['person_key'] for r in career_clean}
not_career = sum(1 for r in house_clean if r['person_key'] not in career_keys)
if not_career != exp['house_120th_clean_2026_not_career_clean']:
    raise SystemExit(f'2026-clean but not career-clean {not_career} != expected '
                     f"{exp['house_120th_clean_2026_not_career_clean']}")
print(f"clean_2026: True {counts['true_total']}, False {counts['false_total']}, "
      f"None {counts['null_total']}; "
      f"unopposed_2026 True {sum(1 for r in records if r['unopposed_2026'])}; "
      f"120th House clean {len(house_clean)} "
      f"({by_party['Democrat']} D, {by_party['Republican']} R); "
      f"career-clean 120th House {len(career_clean)}")

# ---- Primary-target list ----
targets = [r for r in house120 if r['party_120'] == 'Democrat' and r['dirty_2026'] > 0]
targets.sort(key=lambda r: -r['dirty_2026'])
lines = [
    '# Primary targets — House Democrats in the 120th Congress, by dirty money in 2026',
    '',
    f"Generated from the tracker dataset (data as of {CFG['data_as_of']}). "
    f"{len(targets)} House Democrats in the incoming 120th took dirty money in 2026 "
    f"(corporate PAC + AIPAC direct + UDP benefit). Dirty money is money from sources "
    f"other than individual contributors; individual contributions are not dirty money.",
    '',
    'A public-facing version of this list needs Craig\'s explicit go-ahead.',
    '',
    '| # | Name | District | Dirty 2026 | Corp PAC 2026 | AIPAC 2026 | UDP benefit 2026 | Individual 2026 |',
    '|---|------|----------|-----------:|--------------:|-----------:|-----------------:|---------------:|',
]
for i, r in enumerate(targets, 1):
    lines.append(f"| {i} | {r['full_name']} | {r['state']}-{r['district_120']} | "
                 f"${r['dirty_2026']:,.2f} | ${r['corp_2026']:,.2f} | "
                 f"${r['aipac_direct_2026']:,.2f} | ${r['udp_benefit_2026']:,.2f} | "
                 f"${r['individual_2026']:,.2f} |")
with open(ROOT / CFG['paths']['primary_targets'], 'w') as f:
    f.write('\n'.join(lines) + '\n')
print(f"wrote {CFG['paths']['primary_targets']} ({len(targets)} targets)")

# ---- Write the dataset in the final column order ----
csv_cols = CFG['dataset']['csv_columns']
json_keys = CFG['dataset']['json_keys']
ordered = [{k: r[k] for k in json_keys} for r in records]
with open(ROOT / CFG['paths']['dataset_json'], 'w') as f:
    json.dump(ordered, f, indent=1)
print(f"wrote {CFG['paths']['dataset_json']} ({len(ordered)} rows)")
pd.DataFrame(ordered, columns=csv_cols).to_csv(ROOT / CFG['paths']['dataset_csv'], index=False)
print(f"wrote {CFG['paths']['dataset_csv']} ({len(ordered)} rows)")
