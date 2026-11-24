"""The page carries the dataset exactly: the coverage stamp, every field, the opposition detail."""

import json
from dataclasses import asdict
from datetime import datetime

from receipts.common.settings import settings
from receipts.site.build_site import SCALARS, build_opp_payload
from receipts.site.checks.page import values_equal


def coverage_stamp(audit, page):
    """The data-as-of stamp shows config.yaml's coverage end dates."""
    cov = asdict(settings().verification.coverage_end)
    cov_dates = [
        datetime.strptime(cov[k], '%Y-%m-%d').strftime('%b %d, %Y')
        for k in ('committee_money_pas2', 'weball', 'independent_expenditures')
    ]
    audit.check(
        'stamp shows config coverage end dates',
        all(d in page.html for d in cov_dates),
        f'looking for {cov_dates}',
    )
    audit.check('stamp says 2026 is partial', '2026 is partial' in page.html)


def data_round_trip(audit, page):
    """The embedded rows decode to exactly the published dataset."""
    dataset = json.loads(settings().paths.dataset_json.read_text())
    audit.pin('embedded row count', 'rows.count', len(page.rows))
    audit.check(
        'column lists match generator',
        page.cols['scalars'] == SCALARS
        and page.cols['pc']
        and page.cols['sf']
        and page.cols['oc']
        and page.cols['aie']
        and page.cols['tc'],
    )

    mismatches = 0
    for i, (d_row, j_row) in enumerate(zip(page.rows, dataset, strict=True)):
        for k, v in j_row.items():
            if k == 'all_ie_top_committees' and v is None:
                v = []
            if not values_equal(d_row.get(k), v, k):
                mismatches += 1
                if mismatches <= 5:
                    print(
                        f'  mismatch row {i} {j_row.get("full_name")} field {k}: '
                        f'site={d_row.get(k)!r} dataset={v!r}'
                    )
    audit.check(
        'embedded data round-trips exactly (all rows, all fields)',
        mismatches == 0,
        f'{mismatches} mismatched fields',
    )


def opposition_detail(audit, page):
    """opposition-credit detail payload (race-phase level)"""
    opp_expected = build_opp_payload()
    audit.check(
        'embedded opposition detail matches opposition-computed.json',
        values_equal(page.opposition, opp_expected, 'opp'),
        f'{len(page.opposition)} persons, {sum(len(v) for v in page.opposition.values())} race-phases',
    )
    # Dataset-level counts use the same baseline keys as verify_dataset.py,
    # so the site and the dataset cannot disagree.
    for section in ('headline', 'career_dirty', 'charts', 'detail'):
        audit.pin(f'site figures: {section}', f'site.{section}', page.expected[section])
    c, t, t28 = page.expected['clean'], page.expected['tiers'], page.expected['targets_2028']
    audit.pin('clean True', 'clean_2026.true_total', c['true_total'])
    audit.pin('incoming House clean', 'clean_2026.house_120th_verified_clean', c['house_120'])
    audit.pin(
        'incoming House clean D',
        'clean_2026.house_120th_verified_clean_democrat',
        c['house_120_democrat'],
    )
    audit.pin(
        'incoming House clean R',
        'clean_2026.house_120th_verified_clean_republican',
        c['house_120_republican'],
    )
    audit.pin('incoming Senate clean', 'site.clean.senate_120', c['senate_120'])
    audit.pin(
        'clean None: unopposed / unverified names',
        'site.clean.null_names',
        {'unopposed': c['null_unopposed'], 'unverified': c['null_unverified']},
    )
    audit.pin('unopposed in 2026', 'site.clean.unopposed_total', c['unopposed_total'])
    audit.pin(
        'career-clean incoming House (incl. opposition credit)',
        'site.clean.career_clean_house_120',
        c['career_clean_house_120'],
    )
    audit.pin('AIPAC/UDP flag in the 120th', 'tiered_2026.aipac_udp_flag_120th', t['flag_120'])
    audit.pin('AIPAC/UDP flag roster-wide', 'tiered_2026.aipac_udp_flag_all', t['flag_all'])
    for preset in ('balanced', 'lenient'):
        for tier_name, n in t[preset].items():
            audit.pin(
                f'{preset} tier {tier_name} in the 120th', f'tiered_2026.{preset}.{tier_name}', n
            )
        audit.pin(
            f'not-dirty in the 120th under {preset}',
            f'tiered_2026.{preset}.not_dirty',
            t['not_dirty_120'][preset],
        )
    audit.pin(
        'House not dirty under Balanced (of incoming House incl. delegates)',
        'site.tiers.house_not_dirty_balanced',
        t['house_not_dirty_balanced'],
    )
    for preset in ('strict', 'balanced', 'lenient'):
        audit.pin(
            f'2028 targets {preset} House',
            f'tiered_2026.targets_2028_{preset}_house',
            t28[preset][0],
        )
        audit.pin(
            f'2028 targets {preset} Senate Class 3',
            f'tiered_2026.targets_2028_{preset}_senate_class3',
            t28[preset][1],
        )
    audit.pin(
        '2028 watchlist order + lead figures',
        'site.targets_2028.order',
        {k: v for k, v in t28.items() if k not in ('strict', 'balanced', 'lenient')},
    )

    king_hinds = [r for r in page.rows if 'King-Hinds' in r['full_name']]
    audit.check(
        'King-Hinds contested, not unopposed (MP district 01)',
        len(king_hinds) == 1 and king_hinds[0]['unopposed_2026'] is False,
    )
    audit.check(
        '2026 primary-target intro states the computed count',
        f'{t28["targets_2026_house"]} House Democrats in the incoming 120th '
        'took dirty money in 2026' in page.html,
    )
    audit.check(
        'methodology clean paragraph is computed, not stale',
        f'{c["all_120"]} verified clean in the incoming 120th' in page.html
        and f'{c["house_120"]} House ({c["house_120_democrat"]} D, {c["house_120_republican"]} R)'
        in page.html,
        'the methodology paragraph does not state the computed clean counts',
    )
