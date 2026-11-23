"""The audit re-derives the tier rules on its own; it must agree with domain/ everywhere.

verify_dataset.py keeps a second, independent copy of the AIPAC/UDP flag, the
corporate-PAC threshold and the tier, so a wrong rule in domain/ cannot pass
by being checked against itself. This test stops the two copies drifting apart.
"""

import itertools

import pytest

from receipts.common.settings import settings
from receipts.domain.clean_2026 import aipac_udp_flagged, corporate_money_material, tier
from receipts.validate import verify_dataset as audit

PRESETS = ('balanced', 'lenient')
AMOUNTS = (-15000.0, 0, 0.01, 2500.0, 100000, 100000.01, 250000, 250000.01, 1_000_000)
RECEIPTS = (None, 'unknown', True, -10, 0, 1, 2_000_000, 2_500_000, 5_000_000, 20_000_000)


@pytest.mark.parametrize('aipac, udp', list(itertools.product(AMOUNTS, AMOUNTS)))
def test_the_flag_agrees(aipac, udp):
    assert audit.flag_for(aipac, udp) == aipac_udp_flagged(aipac, udp)


@pytest.mark.parametrize('preset', PRESETS)
def test_the_corporate_threshold_agrees(preset):
    thresholds = settings().verification.tolerance_presets[preset]
    for corp, receipts in itertools.product(AMOUNTS, RECEIPTS):
        domain = corporate_money_material(corp, receipts, thresholds)
        assert audit.corp_material(corp, receipts, preset) == domain, (corp, receipts)


@pytest.mark.parametrize('preset', PRESETS)
def test_the_tier_agrees(preset):
    thresholds = settings().verification.tolerance_presets[preset]
    cases = itertools.product((True, False, None), (True, False), AMOUNTS, RECEIPTS)
    for clean, flag, corp, receipts in cases:
        domain = tier(clean, flag, corp, receipts, thresholds)
        assert audit.tier_for(clean, flag, corp, receipts, preset) == domain, (
            clean,
            flag,
            corp,
            receipts,
        )
