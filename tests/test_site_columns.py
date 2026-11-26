"""The site's column lists and JS preset strings stay tied to config.yaml.

`build_site.SCALARS` and the `*_COLS` lists are the page's embed order, so
they are not generated from config: `config.yaml` `json_keys` lists the
same scalar keys in a different order (state/district/chamber are rotated,
and the 2026 trio is ordered differently), so generating `SCALARS` from
config would reorder the embedded arrays and change `docs/index.html`.
What can actually drift is the *set* of columns, so these tests pin
set-equality against config, the assemble lists, and the dataset itself,
and pin the JS preset strings against the config thresholds.
"""

import json
import re

from receipts.common.settings import settings
from receipts.site.build_site import (
    NESTED,
    NESTED_COLS,
    SCALARS,
    SF_COLS,
    cycle_cols,
    template,
)
from receipts.transform.assemble import (
    ACCEPTED,
    ALL_IE,
    OTHER_COMMITTEES,
    PRO_ISRAEL,
    RANKS,
    ROSTER_FIELDS,
    SELF_FUNDING,
    SELF_FUNDING_ENTRY,
)
from receipts.transform.compute_2026 import cycle_fields


def test_scalars_are_the_scalar_json_keys():
    json_keys = settings().dataset.json_keys
    assert len(SCALARS) == len(set(SCALARS)), 'SCALARS repeats a key'
    assert set(SCALARS) == set(json_keys) - set(NESTED)
    # The embed order is its own committed order: it differs from
    # config's json_keys order, so generating SCALARS from config would
    # reorder the embedded arrays and change the page.
    assert [k for k in json_keys if k not in NESTED] != SCALARS


def test_scalars_cover_assemble_column_lists():
    career = (
        set(ROSTER_FIELDS)
        | set(ACCEPTED)
        | set(SELF_FUNDING)
        | set(OTHER_COMMITTEES)
        | set(ALL_IE)
        | set(PRO_ISRAEL)
        | set(RANKS)
    )
    assert career <= set(SCALARS)


def test_self_funding_entry_keys_live_in_sf_cols():
    assert ['cycle', 'candidate_id', *SELF_FUNDING_ENTRY, 'coverage_end_date'] == SF_COLS


def test_cycle_columns_come_from_cycle_fields():
    assert cycle_cols() == ['cycle', *cycle_fields(), 'up_for_election']


def test_nested_column_lists_match_dataset_entries():
    dataset = json.loads(settings().paths.dataset_json.read_text())
    for name, cols in NESTED_COLS.items():
        assert len(cols) == len(set(cols)), f'{name} repeats a key'
        keys = set()
        for row in dataset:
            for entry in row[name] or []:
                keys |= set(entry)
        assert keys == set(cols), name
    cycles = [e for row in dataset for e in (row['cycles'] or [])]
    assert cycles
    assert list(cycles[0]) == cycle_cols()
    assert all(set(e) == set(cycle_cols()) for e in cycles)


def _presets_src():
    src = template('tracker.js')
    start = src.index('const PRESETS = {')
    return src[start : src.index('\n};', start)]


def _preset_block(src, name):
    match = re.search(name + r':\{.*?\n\s*short:\'[^\']*\'', src, re.DOTALL)
    assert match, f'no PRESETS entry for {name}'
    return match.group(0)


def test_tracker_preset_strings_match_config():
    src = _presets_src()
    presets = settings().verification.tolerance_presets
    js_names = set(re.findall(r"  (\w+):\{label:'", src))
    assert js_names == {'strict'} | set(presets)
    for name, preset in presets.items():
        block = _preset_block(src, name)
        assert f'${preset.corp_amount:,}' in block
        assert f'{round(preset.corp_share * 100)}%' in block
    assert '$0' in _preset_block(src, 'strict')
