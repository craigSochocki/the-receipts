"""The page carries the dataset exactly: the coverage stamp, every field, the opposition detail."""

import json
from dataclasses import asdict
from datetime import datetime

from receipts.common.log import log
from receipts.common.settings import settings
from receipts.domain.targets import DIRTY_UNDER
from receipts.site.build_site import SCALARS, build_opp_payload
from receipts.site.checks.page import values_equal


def coverage_stamp(audit, site):
    """Every page's stamp shows config.yaml's coverage end dates."""
    cov = asdict(settings().verification.coverage_end)
    cov_dates = [
        datetime.strptime(cov[k], '%Y-%m-%d').strftime('%b %d, %Y')
        for k in ('committee_money_pas2', 'weball', 'independent_expenditures')
    ]
    current = settings().cycles.current
    for page in site.pages():
        audit.check(
            f'stamp shows config coverage end dates ({page.kind})',
            all(d in page.html for d in cov_dates),
            f'looking for {cov_dates}',
        )
        audit.check(
            f'stamp says the current cycle is partial ({page.kind})',
            f'{current} is partial' in page.html,
        )


def data_round_trip(audit, site):
    """The embedded rows decode to exactly the published dataset."""
    page = site.explore
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
                    log.info(
                        f'  mismatch row {i} {j_row.get("full_name")} field {k}: '
                        f'site={d_row.get(k)!r} dataset={v!r}'
                    )
    audit.check(
        'embedded data round-trips exactly (all rows, all fields)',
        mismatches == 0,
        f'{mismatches} mismatched fields',
    )


def opposition_detail(audit, site):
    """opposition-credit detail payload (race-phase level)"""
    page = site.explore
    opp_expected = build_opp_payload()
    audit.check(
        'embedded opposition detail matches opposition-computed.json',
        values_equal(page.opposition, opp_expected, 'opp'),
        f'{len(page.opposition)} persons, {sum(len(v) for v in page.opposition.values())} race-phases',
    )
    for section in ('headline', 'career_dirty', 'detail', 'clean', 'tiers'):
        audit.pin(f'site figures: {section}', f'site.{section}', page.expected[section])
    # The dataset audit pins the same target keys, so the site and the dataset cannot disagree.
    targets = page.expected['targets']
    for preset in DIRTY_UNDER:
        audit.pin(
            f'next-cycle targets {preset} (House, Senate)', f'targets.{preset}', targets[preset]
        )
    audit.pin(
        'next-cycle targets: order and lead figures',
        'site.targets',
        {k: v for k, v in targets.items() if k not in DIRTY_UNDER},
    )

    king_hinds = [r for r in page.rows if 'King-Hinds' in r['full_name']]
    audit.check(
        'King-Hinds contested, not unopposed (MP district 01)',
        len(king_hinds) == 1 and king_hinds[0]['unopposed_2026'] is False,
    )
    c = page.expected['clean']
    audit.check(
        'methodology clean paragraph is computed, not stale',
        f'{c["all_120"]} are verified clean' in site.methodology.html
        and f'{c["house_120"]} in the House ({c["house_120_democrat"]} D, '
        f'{c["house_120_republican"]} R)'
        in site.methodology.html,
        'the methodology paragraph does not state the computed clean counts',
    )
