"""Settings the new pipeline code shares, read once from config.yaml."""

from types import SimpleNamespace

from receipts.common.config import load_config
from receipts.common.files import read_json

_CFG = load_config()
ROOT = _CFG['_root']

PATHS = SimpleNamespace(**{name: ROOT / path for name, path in _CFG['paths'].items()})
CAREER_CYCLES = range(_CFG['cycles']['career_start'], _CFG['cycles']['career_end'] + 1, 2)
IE_CYCLES = tuple(_CFG['cycles']['udp'])
CURRENT_CYCLE = _CFG['cycles']['current']
AIPAC_PAC = _CFG['committees']['aipac_pac']
WINRED = _CFG['committees']['winred']
UDP = _CFG['committees']['udp']
DATA_AS_OF = _CFG.get('data_as_of')
COVERAGE_END = _CFG['verification']['coverage_end']


def load_roster():
    return read_json(PATHS.roster)


def load_double_count_records():
    return read_json(PATHS.dedup_applied)
