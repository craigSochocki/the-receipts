"""The all-IE diagnostic report; nothing here changes a published figure."""

from collections import defaultdict

from receipts.common.files import write_json
from receipts.common.settings import settings
from receipts.domain.blank_candidates import name_key, roster_matches
from receipts.store.ie_rows import (
    BLANK,
    NOT_IDENTIFIED,
    REPLACED,
    UNREGISTERED,
    Roster,
    dollars,
    tally,
    total,
)

BOGUS_FILINGS = [
    (2022, 'C00800508', 'H2NY05118', 'Committee of 300 / Akhlaghy 2022'),
    (2024, 'C00874586', 'P40007304', 'Committee of 300 / Akhlaghy 2024'),
    (2024, 'C00785352', 'P40019226', 'Nader Akhlaghy committee 2024'),
    (2026, 'C00946087', '', 'Warren Buffet / Bettis 2026 (blank cand)'),
    (2026, 'C00944025', '', 'TANKING / APPLE INC DJIA / Bettis 2026 (blank cand)'),
]


FORM_TYPE_COLUMNS = ('form_type', 'form_tp', 'filing_form')


def near_duplicates(kept):
    """Same committee, candidate, date, amount and direction under different transaction IDs."""
    groups = defaultdict(set)
    for x in kept:
        if x.candidate_id:
            groups[x.spender_id, x.candidate_id, x.date, x.cents, x.direction].add(x.transaction_id)
    repeated = {key: ids for key, ids in groups.items() if len(ids) > 1}
    return {
        'groups': len(repeated),
        'extra_amount_if_collapsed': dollars(
            sum((len(ids) - 1) * key[3] for key, ids in repeated.items())
        ),
    }


def file_exclusions(rows, columns):
    kept = [x for x in rows if x.excluded_because != REPLACED]
    included = [x for x in kept if x.counted]
    return {
        'raw_rows': len(rows),
        'raw_amount': dollars(total(rows)),
        'deduped_rows': len(kept),
        'deduped_amount': dollars(total(kept)),
        'dedup_removed': tally(x for x in rows if x.excluded_because == REPLACED),
        'unregistered_committee': tally(x for x in kept if x.excluded_because == UNREGISTERED),
        'blank_candidate': tally(x for x in kept if x.excluded_because == BLANK),
        'candidate_not_identified': tally(x for x in kept if x.excluded_because == NOT_IDENTIFIED),
        'included': tally(included),
        'has_form_type_column': any(c in FORM_TYPE_COLUMNS for c in columns),
        'near_duplicates_distinct_tran_id': near_duplicates(kept),
        'blank_sup_opp_included': tally(x for x in included if not x.direction),
        'negative_amount_included': tally(x for x in included if x.cents < 0),
    }


def name_index(included):
    index, collisions = {}, 0
    for x in included:
        key = name_key(x.candidate_name, x.state, x.district, x.office)
        if key in index and index[key] != x.candidate_id:
            collisions += 1
        index.setdefault(key, x.candidate_id)
    return index, collisions


def blank_attribution(blank_rows, index, roster):
    resolved_all = resolved_roster = fallback_roster = unresolved = 0
    by_committee = defaultdict(int)
    for x in blank_rows:
        candidate_id = index.get(name_key(x.candidate_name, x.state, x.district, x.office))
        if candidate_id:
            resolved_all += x.cents
            if candidate_id in roster.person_of:
                resolved_roster += x.cents
                by_committee[x.spender_id, x.spender_name] += x.cents
            continue
        matches = roster_matches(x.candidate_name, x.state, x.district, roster.people)
        if len(matches) == 1 and len(matches[0].get('fec_candidate_ids') or []) == 1:
            fallback_roster += x.cents
        else:
            unresolved += x.cents
    return {
        'blank_registered_rows': len(blank_rows),
        'blank_registered_amount': dollars(total(blank_rows)),
        'name_index_resolved_all_candidates': dollars(resolved_all),
        'name_index_resolved_roster': dollars(resolved_roster),
        'roster_fallback_resolved_roster': dollars(fallback_roster),
        'unresolved': dollars(unresolved),
        'note': 'DIAGNOSTIC ONLY — none of these amounts is added to any published total.',
        'top_committees_behind_roster_resolved': [
            {'committee_id': committee_id, 'committee_name': name, 'amount': dollars(cents)}
            for (committee_id, name), cents in sorted(by_committee.items(), key=lambda kv: -kv[1])[
                :5
            ]
        ],
    }


def bogus_examples(kept):
    examples = {}
    for cycle, committee_id, candidate_id, label in BOGUS_FILINGS:
        hit = [
            x
            for x in kept
            if x.cycle == cycle
            and x.spender_id == committee_id
            and (not candidate_id or x.candidate_id == candidate_id)
        ]
        examples[label] = {
            'committee_id': committee_id,
            'candidate_id': candidate_id or '(blank)',
            'rows_in_file_after_dedup': len(hit),
            'amount_in_file_after_dedup': dollars(total(hit)),
            'amount_included': dollars(total(x for x in hit if x.counted)),
            'excluded_because': 'unregistered committee (not in same-cycle cm.txt)'
            + ('' if candidate_id else '; candidate ID blank'),
        }
    return examples


def roster_career_totals(roster, per_person, totals):
    """Roster totals with a candidate ID shared by two entries counted once."""
    sharing = defaultdict(set)
    for p in roster.people:
        for candidate_id in Roster.ids(p):
            sharing[candidate_id].add(p['person_key'])
    names = {p['person_key']: p['full_name'] for p in roster.people}
    shared, overcount = [], [0, 0, 0]
    for candidate_id, person_keys in sorted(sharing.items()):
        if len(person_keys) < 2:
            continue
        amounts = totals.of({candidate_id}, set(settings().cycles.ie))
        extra = len(person_keys) - 1
        overcount = [o + extra * a for o, a in zip(overcount, amounts, strict=True)]
        shared.append(
            {
                'candidate_id': candidate_id,
                'person_keys': sorted(person_keys),
                'full_names': sorted({names[k] for k in person_keys}),
                'shared_id_career_total': dollars(amounts[2]),
                'overcounted_in_row_sums': dollars(extra * amounts[2]),
            }
        )
    found = [v for v in per_person.values() if v]
    row_sums = [sum(v[field] for v in found) for field in ('support', 'oppose', 'total')]
    return {
        'support': dollars(row_sums[0]),
        'oppose': dollars(row_sums[1]),
        'total': dollars(row_sums[2]),
        'n_persons_with_spending': sum(1 for v in found if v['total'] != 0),
        'n_persons_unknown_no_fec_id': sum(1 for v in per_person.values() if v is None),
        'duplicate_roster_entries': shared,
        'distinct_person_totals': {
            field: dollars(row_sum - over)
            for field, row_sum, over in zip(
                ('support', 'oppose', 'total'), row_sums, overcount, strict=True
            )
        },
    }


def meta():
    return {
        'script': 'receipts/store/all_ie.py',
        'data_as_of': settings().data_as_of,
        'cycles': list(settings().cycles.ie),
        'current_cycle': settings().cycles.current,
        'note': 'Career totals cover the staged IE cycles (2022+2024+2026) ONLY. '
        'No IE files are staged for earlier cycles; these are not full-career totals. '
        'All-IE columns are separate from total_accepted and are never blended into it.',
        'filter_rules': [
            'dedup by (spe_id, tran_id): keep latest receipt_dat, tie-break highest file_num; '
            'blank tran_id never deduped against another row',
            'registered committee only: spe_id in same-cycle data/raw/cm/<cycle>/cm.txt',
            'identified candidate only: non-blank cand_id in any staged weball file (1980-2026) '
            'OR a roster FEC candidate ID; blank cand_id rows excluded from published totals',
            'support and oppose summed separately, never netted; blank sup_opp rows count in total only',
        ],
    }


FORM_TYPE_FINDING = (
    'No form-type column exists in the bulk IE files, so F24/F3X cannot be '
    'separated by form. The bulk file carries ONE copy per expenditure (the '
    'notice copy; pull-log-b §7 verified file_num/image_num match the F24 '
    'filing), and (spe_id, tran_id) dedup removes any same-transaction repeat. '
    'Proof: UDP 2024 deduped S+O reproduces the tracker total $38,044,932.69 '
    'to the cent — a file that double-counted across form types would be ~2x. '
    'Near-duplicate rows (same committee/candidate/date/amount/direction, '
    'different tran_id AND different image_num = different filings) are '
    'treated as separate expenditures and quantified per cycle in exclusions[].'
)


def coverage():
    return {
        'staged_cycles': list(settings().cycles.ie),
        'earlier_cycles_available': 'Per the FEC independent-expenditures file description '
        '(fetched Nov 12, 2026), historical data is available beginning with the 2010 '
        'cycle, and the FEC bulk-data index publishes independent_expenditure_YYYY.csv '
        'per cycle. Files for 2010/2012/2014/2016/2018/2020 exist and are NOT staged '
        'here (each ~14-19 MB, same format) — expanding to them is a follow-up, not '
        'done in this pull. Pre-2010 cycles have no such file.',
        'files_not_staged': [2010, 2012, 2014, 2016, 2018, 2020],
    }


def blank_attribution_by_cycle(included, kept, roster):
    """({cycle: what the blank-ID rows would attribute by name}, name-index collisions)."""
    diagnostic, collisions = {}, 0
    for cycle in settings().cycles.ie:
        index, found = name_index(x for x in included if x.cycle == cycle)
        collisions += found
        diagnostic[cycle] = blank_attribution(
            [x for x in kept if x.cycle == cycle and x.excluded_because == BLANK], index, roster
        )
    return diagnostic, collisions


def write_report(spending, roster, kept, exclusions, blank_diagnostic, collisions):
    cycles = settings().cycles.ie
    write_json(
        settings().paths.intermediate / 'all_ie_per_cycle.json',
        {
            'meta': {
                **meta(),
                'form_type_double_count_check': {
                    'bulk_file_has_form_type_column': any(
                        e['has_form_type_column'] for e in exclusions.values()
                    ),
                    'finding': FORM_TYPE_FINDING,
                },
                'coverage': coverage(),
            },
            'exclusions_by_cycle': {str(c): exclusions[c] for c in cycles},
            'blank_attribution_diagnostic': {str(c): blank_diagnostic[c] for c in cycles},
            'name_index_collisions': collisions,
            'per_cycle_summaries': {str(c): spending.summaries[c] for c in cycles},
            'per_candidate_per_cycle': spending.by_candidate,
            'bogus_examples': bogus_examples(kept),
            'roster_career_totals': roster_career_totals(
                roster, spending.per_person, spending.totals
            ),
        },
    )
