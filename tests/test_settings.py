import copy

import pytest
import yaml

from receipts.common.config import repo_root
from receipts.common.settings import ConfigError, parse, settings

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
