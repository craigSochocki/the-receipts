"""Every shared value from config.yaml, typed, read on first use.

Code asks for `settings()` where it needs a value, never at import, so
nothing reads the config until a step runs. config.yaml must match these
classes exactly: a missing, unknown or wrongly typed key stops the run
with its dotted name.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, is_dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, get_args, get_origin, get_type_hints

import yaml

from receipts.common.config import repo_root
from receipts.common.files import read_json
from receipts.domain.clean_2026 import TolerancePreset


class ConfigError(SystemExit):
    pass


@dataclass(frozen=True)
class Committees:
    aipac_pac: str
    udp: str
    winred: str


@dataclass(frozen=True)
class Cycles:
    career_start: int
    career_end: int
    udp: tuple[int, ...]
    current: int

    @property
    def career(self) -> range:
        return range(self.career_start, self.career_end + 1, 2)

    @property
    def ie(self) -> tuple[int, ...]:
        """Cycles with staged independent-expenditure files (UDP first filed in 2022)."""
        return self.udp


@dataclass(frozen=True)
class Paths:
    raw: Path
    bulk: Path
    ie: Path
    source: Path
    intermediate: Path
    store: Path
    snapshots: Path
    evidence: Path
    site: Path
    dataset_json: Path
    dataset_csv: Path
    roster: Path
    roster_intermediate: Path
    fec_lookup_results: Path
    baseline: Path
    manual_roster_notes: Path
    other_committees_diagnostics: Path
    all_ie_per_cycle: Path
    freshness_snapshot: Path
    freshness_state: Path
    dedup_applied: Path
    run_history: Path
    roster_facts: Path
    primary_targets: Path
    opposition_computed: Path


@dataclass(frozen=True)
class RetrySettings:
    max_attempts: int
    backoff_base_seconds: float
    backoff_cap_seconds: float
    max_wait_seconds: float


@dataclass(frozen=True)
class FecApiSettings:
    base_url: str
    api_key_env: str
    api_key_default: str
    request_timeout_seconds: float
    sleep_between_requests_seconds: float
    retry: RetrySettings


@dataclass(frozen=True)
class SweepCommittee:
    committee_id: str
    committee_name: str
    note: str


@dataclass(frozen=True)
class Gate:
    families: tuple[str, ...]
    per_page: int
    max_pages_per_family: int
    committee_master_cycle: int


@dataclass(frozen=True)
class Freshness:
    f24_committee_sweep_cycle: int
    f24_committee_sweep: tuple[SweepCommittee, ...]
    gate: Gate


@dataclass(frozen=True)
class RunChecks:
    max_row_drop: float
    max_file_age_days: int


@dataclass(frozen=True)
class CoverageEnd:
    committee_money_pas2: str
    weball: str
    independent_expenditures: str
    freshness_window_start: str


@dataclass(frozen=True)
class Verification:
    coverage_end: CoverageEnd
    tolerance_presets: Mapping[str, TolerancePreset]


@dataclass(frozen=True)
class Dataset:
    csv_columns: tuple[str, ...]
    json_keys: tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    root: Path
    committees: Committees
    cycles: Cycles
    paths: Paths
    data_as_of: str
    fec_api: FecApiSettings
    freshness: Freshness
    party_codes: Mapping[str, str]
    run_checks: RunChecks
    verification: Verification
    dataset: Dataset

    def relative(self, path: Path) -> Path:
        """A path as the repo shows it, for log lines."""
        return path.relative_to(self.root)


@cache
def settings() -> Settings:
    root = repo_root()
    with open(root / 'config.yaml') as f:
        raw = yaml.safe_load(f)
    return parse(raw, root)


def parse(raw: dict, root: Path) -> Settings:
    return _build(Settings, {'root': str(root), **raw}, '', root)


def _build(kind: Any, value: Any, where: str, root: Path) -> Any:
    if is_dataclass(kind):
        return _build_record(kind, value, where, root)
    origin = get_origin(kind)
    if origin is tuple:
        item = get_args(kind)[0]
        _expect(isinstance(value, list), where, 'a list', value)
        return tuple(_build(item, v, f'{where}[{n}]', root) for n, v in enumerate(value))
    if origin is Mapping:
        item = get_args(kind)[1]
        _expect(isinstance(value, dict), where, 'a mapping', value)
        return MappingProxyType(
            {k: _build(item, v, f'{where}.{k}', root) for k, v in value.items()}
        )
    if kind is Path:
        _expect(isinstance(value, str), where, 'a path', value)
        return root / value
    if kind is float:
        _expect(
            isinstance(value, int | float) and not isinstance(value, bool), where, 'a number', value
        )
        return float(value)
    _expect(isinstance(value, kind) and not isinstance(value, bool), where, kind.__name__, value)
    return value


def _build_record(kind: Any, value: Any, where: str, root: Path) -> Any:
    _expect(isinstance(value, dict), where or 'config.yaml', 'a mapping', value)
    names = [f.name for f in fields(kind)]
    missing = [n for n in names if n not in value]
    unknown = [k for k in value if k not in names]
    if missing or unknown:
        raise ConfigError(
            f'config.yaml {where or "top level"}: missing {missing or "nothing"}, '
            f'unknown {unknown or "nothing"}'
        )
    hints = get_type_hints(kind)
    return kind(**{n: _build(hints[n], value[n], f'{where}.{n}'.lstrip('.'), root) for n in names})


def _expect(ok: bool, where: str, wanted: str, value: Any) -> None:
    if not ok:
        raise ConfigError(f'config.yaml {where}: expected {wanted}, got {value!r}')


def load_roster():
    return read_json(settings().paths.roster)


def load_double_count_records():
    return read_json(settings().paths.dedup_applied)


_LEGACY_NAMES = {
    'ROOT': lambda s: s.root,
    'PATHS': lambda s: s.paths,
    'CAREER_CYCLES': lambda s: s.cycles.career,
    'IE_CYCLES': lambda s: s.cycles.ie,
    'CURRENT_CYCLE': lambda s: s.cycles.current,
    'AIPAC_PAC': lambda s: s.committees.aipac_pac,
    'WINRED': lambda s: s.committees.winred,
    'UDP': lambda s: s.committees.udp,
    'DATA_AS_OF': lambda s: s.data_as_of,
    'COVERAGE_END': lambda s: asdict(s.verification.coverage_end),
}


def __getattr__(name):
    """The module constants older code imports; removed once every package uses settings()."""
    if name in _LEGACY_NAMES:
        return _LEGACY_NAMES[name](settings())
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
