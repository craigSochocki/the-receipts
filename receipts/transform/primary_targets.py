#!/usr/bin/env python3
"""Write the next cycle's primary-target list from the published dataset."""

from receipts.common.files import read_json
from receipts.common.log import log, run
from receipts.common.settings import settings
from receipts.domain.targets import latest_record
from receipts.domain.targets import primary_targets as find_primary_targets
from receipts.transform.records import PersonRecord


def seat_label(r: PersonRecord):
    return (
        f'{r["state"]}-{r["district_120"]}'
        if r['chamber_120'] == 'House'
        else f'{r["state"]} Senate'
    )


def write_primary_targets(records: list[PersonRecord]):
    """The next cycle's primary targets under the default (Balanced) preset."""
    cycle = settings().cycles.next
    targets = find_primary_targets(records, 'balanced', cycle)
    lines = [
        f'# Primary targets — {cycle}: incoming members, any party, by dirty money',
        '',
        f'Generated from the tracker dataset (data as of {settings().data_as_of}). '
        f'{len(targets)} incoming members whose seat is up in {cycle} took dirty money in '
        f'their latest election under the Balanced preset (corporate PAC + AIPAC direct + '
        f'UDP benefit). Individual contributions are not dirty money.',
        '',
        "A public-facing version of this list needs Craig's explicit go-ahead.",
        '',
        '| # | Name | Party | Seat | Election | Dirty | Corp PAC | AIPAC | UDP benefit | Individual |',
        '|---|------|-------|------|---------:|------:|---------:|------:|------------:|-----------:|',
    ]
    for i, r in enumerate(targets, 1):
        record = latest_record(r)
        lines.append(
            f'| {i} | {r["full_name"]} | {r["party_120"]} | {seat_label(r)} | {record["cycle"]} | '
            + ' | '.join(
                f'${record[k]:,.2f}'
                for k in ('dirty', 'corp', 'aipac_direct', 'udp_benefit', 'individual')
            )
            + ' |'
        )
    settings().paths.primary_targets.write_text('\n'.join(lines) + '\n')
    log.info(
        f'wrote {settings().relative(settings().paths.primary_targets)} ({len(targets)} targets)'
    )


def main():
    write_primary_targets(read_json(settings().paths.dataset_json))


if __name__ == '__main__':
    run(main)
