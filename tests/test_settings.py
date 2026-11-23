import copy
import subprocess
import sys

import pytest
import yaml

from receipts.common.settings import ConfigError, parse, repo_root, settings

ROOT = repo_root()


def raw_config():
    with open(ROOT / 'config.yaml') as f:
        return yaml.safe_load(f)


def test_the_committed_config_parses():
    loaded = settings()
    assert loaded.paths.roster == ROOT / 'data/intermediate/roster.json'
    assert loaded.cycles.career == range(1980, 2028, 2)
    assert loaded.freshness.f24_committee_sweep[0].committee_id.startswith('C00')
    assert loaded.verification.tolerance_presets['balanced'].corp_share == 0.05


def test_settings_cannot_be_changed():
    with pytest.raises(AttributeError):
        settings().cycles.current = 2028  # type: ignore[misc]
    with pytest.raises(TypeError):
        settings().party_codes['Green'] = 'GRE'  # type: ignore[index]


def test_a_missing_key_names_itself():
    raw = copy.deepcopy(raw_config())
    del raw['fec_api']['retry']['max_attempts']
    with pytest.raises(ConfigError, match=r"fec_api\.retry: missing \['max_attempts'\]"):
        parse(raw, ROOT)


def test_an_unknown_key_names_itself():
    raw = copy.deepcopy(raw_config())
    raw['paths']['rooster'] = 'data/intermediate/roster.json'
    with pytest.raises(ConfigError, match=r"paths: missing nothing, unknown \['rooster'\]"):
        parse(raw, ROOT)


def test_a_wrong_type_names_itself():
    raw = copy.deepcopy(raw_config())
    raw['cycles']['current'] = '2026'
    with pytest.raises(ConfigError, match=r"cycles\.current: expected int, got '2026'"):
        parse(raw, ROOT)


def test_no_module_reads_the_config_at_import():
    script = (
        'import importlib, pkgutil, receipts\n'
        'from receipts.common import settings\n'
        'for m in pkgutil.walk_packages(receipts.__path__, "receipts."):\n'
        '    importlib.import_module(m.name)\n'
        'print(settings.settings.cache_info().currsize)\n'
    )
    result = subprocess.run(
        [sys.executable, '-c', script], capture_output=True, text=True, check=True, cwd=ROOT
    )
    assert result.stdout.strip() == '0', 'a module called settings() at import'
