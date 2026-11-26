"""The derive CLI wires every step together; the smoke run checks it end to end."""

from pathlib import Path

from receipts.square_one import derive

ROOT = Path(__file__).resolve().parents[1]


def test_smoke_run_writes_schema_and_2026_counts(tmp_path):
    out = tmp_path / 'derived.json'
    output = derive.run(ROOT, out, [2026], [2026])
    assert out.exists()
    assert output['snapshot'] == '2026-11-22'
    assert output['audits_passed'] is True
    assert output['counts']['baseline']['c26_flag'] == 231
    assert output['counts']['baseline']['c26_strict_clean'] == 83
    assert output['counts']['A']['c26_flag'] == 258
    assert output['counts']['B']['c26_flag'] == 256
    assert output['ryan_election_attributed']['H8NY19223|2026'] == 0
    assert output['ryan_pas2_net_2026_cents'] == -1500000
    assert output['career']['B001324']['aipac_b_cents'] > 0
    assert set(output) >= {
        'counts',
        'audits_passed',
        'audit_results',
        'career',
        'corrected_per_cycle',
        'transfer_dedup',
        'transfers_from_corrected',
        'ryan_election_attributed',
        'merge_report',
        'cm_stats',
        'ie_stats',
    }
