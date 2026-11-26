"""Joint-fundraising variants: corrected AIPAC / pro-Israel figures under both JFC rules.

The by_recipient classifier splits a listed conduit's disbursements into
direct (to a candidate's own committee) and joint-fundraising (to a JFC).
Whether JFC money counts as money "from" the conduit is decided: variant A
is the headline (JFC shares count as direct). The derivation still carries
both variants as parallel columns, so the choice stays visible:

- Variant A (JFC counts): AIPAC = API direct + AIPAC-funded JFC shares;
  pro-Israel = API direct from all listed committees + all JFC shares.
- Variant B (JFC excluded): AIPAC = API direct; pro-Israel = API direct
  from all listed committees.

JFC shares come from two routes: name-attributed JFCs (the JFC's name
names one roster member) and outflow splits (a multi-candidate JFC's
own Schedule B outflows, shared pro-rata to the listed conduits that
funded it). The memo layer — by_recipient totals exclude memo rows —
is tracked separately and belongs to neither variant.
"""

import json
from collections import defaultdict
from pathlib import Path

AIPAC = 'C00797670'


def combine_jfc(attribution_path: Path, shares_path: Path) -> dict:
    """Per-person per-cycle JFC shares, in cents: {person_key: {cycle: {'aipac', 'other'}}}.

    Recombines the JFC pilot's attribution (name-attributed JFCs) and
    outflow shares (multi-candidate JFCs split by their own outflows),
    splitting each share across the funding conduits pro-rata to inflow.
    """
    with open(attribution_path) as f:
        attribution = json.load(f)
    with open(shares_path) as f:
        shares = json.load(f)
    acc = attribution['acc']
    jfc: dict[str, dict[int, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {'aipac': 0.0, 'other': 0.0})
    )
    for key, (_name, person_key, total, _rule) in attribution['attr'].items():
        _cmte, cycle = key.split('|')
        for spender, amount in acc[key]['spenders'].items():
            inflow_total = sum(acc[key]['spenders'].values())
            share = total * amount / inflow_total if inflow_total else 0.0
            jfc[person_key][int(cycle)]['aipac' if spender == AIPAC else 'other'] += share
    for key, share in shares.items():
        _cmte, cycle = key.split('|')
        inflow = acc[key]['spenders']
        inflow_total = sum(inflow.values())
        for person_key, amount in share['shares'].items():
            for spender, spender_amount in inflow.items():
                part = amount * spender_amount / inflow_total if inflow_total else 0.0
                jfc[person_key][int(cycle)]['aipac' if spender == AIPAC else 'other'] += part
    return {
        person_key: {
            cycle: {
                'aipac': round(values['aipac'] * 100),
                'other': round(values['other'] * 100),
            }
            for cycle, values in cycles.items()
        }
        for person_key, cycles in jfc.items()
    }


def corrected_figures(direct: dict, jfc: dict) -> dict:
    """Per (person_key, cycle) corrected AIPAC / pro-Israel, both variants, in cents."""
    aipac_direct: dict[tuple, int] = defaultdict(int)
    other_direct: dict[tuple, int] = defaultdict(int)
    for (person_key, committee, cycle), cents in direct.items():
        if committee == AIPAC:
            aipac_direct[(person_key, cycle)] += cents
        else:
            other_direct[(person_key, cycle)] += cents
    keys = (
        set(aipac_direct)
        | set(other_direct)
        | {(person_key, cycle) for person_key, cycles in jfc.items() for cycle in cycles}
    )
    figures = {}
    for person_key, cycle in sorted(keys):
        aipac = aipac_direct.get((person_key, cycle), 0)
        other = other_direct.get((person_key, cycle), 0)
        jfc_aipac = jfc.get(person_key, {}).get(cycle, {}).get('aipac', 0)
        jfc_other = jfc.get(person_key, {}).get(cycle, {}).get('other', 0)
        figures[(person_key, cycle)] = {
            'aipac_a_cents': aipac + jfc_aipac,
            'aipac_b_cents': aipac,
            'pro_israel_a_cents': aipac + other + jfc_aipac + jfc_other,
            'pro_israel_b_cents': aipac + other,
            'jfc_aipac_cents': jfc_aipac,
            'jfc_other_cents': jfc_other,
        }
    return figures


def load_pas2_base(dataset_path: Path) -> tuple[dict, dict]:
    """The tracker's own recorded pas2 figures, per person per cycle and career.

    Returns ({(person_key, cycle): {'aipac', 'pro_israel'}} in cents,
    {person_key: {'aipac', 'pro_israel'}} career in cents). The square-one
    money derivation reproduces these figures to the cent from the bulk
    files (see test_square_one_money.py); they are the base the API
    correction substitutes into for 2022–2026, per recount.py's formula.
    """
    with open(dataset_path) as f:
        rows = json.load(f)
    per_cycle: dict[tuple, dict] = {}
    career: dict[str, dict] = {}
    for row in rows:
        person_key = row['person_key']
        aipac_by_cycle = {c['cycle']: c['aipac_direct'] for c in row['cycles']}
        pro_by_cycle = {
            entry['cycle']: entry['pro_israel_pac'] for entry in row['pro_israel_per_cycle']
        }
        for cycle in set(aipac_by_cycle) | set(pro_by_cycle):
            per_cycle[(person_key, cycle)] = {
                'aipac': round(aipac_by_cycle.get(cycle, 0.0) * 100),
                'pro_israel': round(pro_by_cycle.get(cycle, 0.0) * 100),
            }
        career[person_key] = {
            # People with no FEC ID read 'unknown' for career money.
            'aipac': round(float(row['aipac_pac_direct_career'] or 0.0) * 100)
            if isinstance(row['aipac_pac_direct_career'], (int, float))
            else 0,
            'pro_israel': round(float(row['pro_israel_pac_career'] or 0.0) * 100)
            if isinstance(row['pro_israel_pac_career'], (int, float))
            else 0,
        }
    return per_cycle, career


def corrected_career_for_person(
    figures: dict, pas2_per_cycle: dict, pas2_career: dict, person_key: str
) -> dict:
    """One person's career totals under both variants, in cents (recount formula)."""
    api_cycles = (2022, 2024, 2026)
    base = pas2_career.get(person_key, {'aipac': 0, 'pro_israel': 0})
    pas2_3cy = {'aipac': 0, 'pro_israel': 0}
    for cycle in api_cycles:
        entry = pas2_per_cycle.get((person_key, cycle), {'aipac': 0, 'pro_israel': 0})
        pas2_3cy['aipac'] += entry['aipac']
        pas2_3cy['pro_israel'] += entry['pro_israel']
    api_3cy = {'aipac': 0, 'pro_israel': 0, 'jfc_aipac': 0, 'jfc_other': 0}
    for cycle in api_cycles:
        entry = figures.get((person_key, cycle))
        if entry is None:
            continue
        api_3cy['aipac'] += entry['aipac_b_cents']
        api_3cy['pro_israel'] += entry['pro_israel_b_cents']
        api_3cy['jfc_aipac'] += entry['jfc_aipac_cents']
        api_3cy['jfc_other'] += entry['jfc_other_cents']
    return {
        'aipac_a_cents': base['aipac']
        - pas2_3cy['aipac']
        + api_3cy['aipac']
        + api_3cy['jfc_aipac'],
        'aipac_b_cents': base['aipac'] - pas2_3cy['aipac'] + api_3cy['aipac'],
        'pro_israel_a_cents': base['pro_israel']
        - pas2_3cy['pro_israel']
        + api_3cy['pro_israel']
        + api_3cy['jfc_aipac']
        + api_3cy['jfc_other'],
        'pro_israel_b_cents': base['pro_israel'] - pas2_3cy['pro_israel'] + api_3cy['pro_israel'],
        'jfc_aipac_cents': api_3cy['jfc_aipac'],
        'jfc_other_cents': api_3cy['jfc_other'],
    }


def corrected_career_totals(
    figures: dict, pas2_per_cycle: dict, pas2_career: dict, person_keys: set
) -> dict:
    """Career totals under both variants, in cents, by the recount formula.

    Career = pas2 career − pas2 (2022+2024+2026) + API (2022+2024+2026),
    with JFC shares added on top under variant A only. The pre-2022 pas2
    money stays: the API correction only covers 2022 onward.
    """
    totals = {
        'aipac_a_cents': 0,
        'aipac_b_cents': 0,
        'pro_israel_a_cents': 0,
        'pro_israel_b_cents': 0,
        'jfc_aipac_cents': 0,
        'jfc_other_cents': 0,
    }
    for person_key in person_keys:
        per_person = corrected_career_for_person(figures, pas2_per_cycle, pas2_career, person_key)
        for field in totals:
            totals[field] += per_person[field]
    return totals
