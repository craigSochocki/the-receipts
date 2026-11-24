"""The onboarding tour (onboarding/index.html) must describe the code as it is.

Each test names what drifted, so a change that breaks one updates the tour
in the same commit.
"""

import html
import importlib.util
import json
import re

import pytest

from receipts.common import baseline
from receipts.common.settings import repo_root, settings
from receipts.rebuild import STEPS
from receipts.validate.verify_dataset import SECTIONS

ROOT = repo_root()
TOUR = (ROOT / 'onboarding' / 'index.html').read_text()
EXAMPLE_PERSON = 'S001200'  # Darren Soto, the worked example


def plain(fragment, tag=''):
    return html.unescape(re.sub(r'<[^>]+>', tag, fragment))


def code_blocks():
    return [plain(block) for block in re.findall(r'<pre[^>]*>(.*?)</pre>', TOUR, re.S)]


def without_comment(line):
    return re.sub(r'\s+(#|//)\s.*$', '', line).rstrip()


def quoted_source_lines():
    """(file, line) for every line of a snippet whose first line is `# receipts/<file>.py`."""
    for block in code_blocks():
        first, *rest = block.split('\n')
        source = re.fullmatch(r'# (receipts/\S+\.py)', first.strip())
        if not source:
            continue
        for line in rest:
            if not line.strip():
                break
            code = without_comment(line).strip()
            if code and '...' not in code:
                yield source.group(1), code


def test_quoted_code_is_in_the_file_it_names():
    quoted = list(quoted_source_lines())
    assert len(quoted) > 10
    missing = [(path, line) for path, line in quoted if line not in (ROOT / path).read_text()]
    assert not missing, f'the tour quotes code that is no longer in its file: {missing}'


def test_the_step_list_is_the_one_rebuild_runs():
    block = next(b for b in code_blocks() if b.startswith('# receipts/rebuild.py, STEPS'))
    shown = [without_comment(line).strip() for line in block.split('\n')[1:] if line.strip()]
    assert shown == [step.name for step in STEPS]


def test_named_files_and_modules_exist():
    words = plain(TOUR, tag=' ')
    paths = set(re.findall(r'\b(?:receipts|dbt|tests|data/source)/[\w./-]*\w', words))
    modules = set(re.findall(r'\breceipts(?:\.\w+)+', words))
    missing = [p for p in paths if not (ROOT / p).exists()]
    missing += [m for m in modules if importlib.util.find_spec(m) is None]
    assert paths and modules
    assert not missing, f'the tour names files or modules that do not exist: {sorted(missing)}'


def test_the_audit_count_is_verify_datasets():
    counts = {int(n) for n in re.findall(r'(\d+) (?:audit groups|groups of standing audits)', TOUR)}
    assert counts == {len(SECTIONS)}


def test_the_worked_example_figures_are_the_datasets():
    named = re.search(r'fec-bulk-\d{4}-\d{2}-\d{2}', TOUR).group(0)
    if named != baseline.snapshot():
        pytest.skip(
            f'the tour quotes {named}, the baseline is now {baseline.snapshot()}: '
            'refresh the worked example in onboarding/index.html'
        )
    rows = json.loads(settings().paths.dataset_json.read_text())
    soto = next(r for r in rows if r['person_key'] == EXAMPLE_PERSON)
    accepted_2026 = soto['individual_2026'] + soto['corp_2026'] + soto['aipac_direct_2026']
    shown = [
        f'{soto[column]:,.2f}'
        for column in (
            'individual_contribution_total_career',
            'corporate_pac_career',
            'aipac_pac_direct_career',
            'total_accepted_career',
        )
    ]
    shown += [f'#{soto["rank_total_accepted"]}', f'${accepted_2026:,.0f}']
    shown += [f'${soto[c]:,.0f}' for c in ('individual_2026', 'corp_2026', 'dirty_2026')]
    shown += [repr(soto[c]) for c in ('individual_2026', 'corp_2026', 'aipac_direct_2026')]
    shown += [repr(soto['dirty_2026']), f'"{soto["tier_balanced_2026"]}"']
    missing = [figure for figure in shown if figure not in plain(TOUR)]
    assert not missing, f'the worked example no longer matches the dataset: {missing}'
    assert soto['clean_2026'] is False and 'false' in plain(TOUR)
