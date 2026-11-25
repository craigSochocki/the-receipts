"""The built page as the checks read it: its embedded payloads, decoded, and shared helpers."""

import json
import re

from receipts.site.expectations import site_expectations


def extract_payload(html, script_id):
    m = re.search(
        rf'<script id="{script_id}" type="application/json">(.*?)</script>', html, re.DOTALL
    )
    if not m:
        raise SystemExit(f'missing embedded payload: {script_id}')
    return json.loads(m.group(1))


def decode_row(cols, arr):
    o = {k: arr[i] for i, k in enumerate(cols['scalars'])}
    base = len(cols['scalars'])
    nested_names = [
        'per_cycle',
        'udp_per_cycle',
        'self_funding_per_cycle',
        'other_committees_per_cycle',
        'all_ie_per_cycle',
        'all_ie_top_committees',
        'cycles',
        'pro_israel_per_cycle',
    ]
    nested_cols = [
        cols['pc'],
        cols['upc'],
        cols['sf'],
        cols['oc'],
        cols['aie'],
        cols['tc'],
        cols['cy'],
        cols['pi'],
    ]
    for j, (name, ccols) in enumerate(zip(nested_names, nested_cols, strict=True)):
        o[name] = [{k: e[i] for i, k in enumerate(ccols)} for e in (arr[base + j] or [])]
    return o


def values_equal(a, b, path=''):
    """Exact equality after a JSON round-trip (floats survive it)."""
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        # Positional encoding writes None for an absent optional key
        # (e.g. udp_per_cycle 'attribution'), so missing == None here.
        keys = set(a) | set(b)
        return all(values_equal(a.get(k), b.get(k), path + '.' + k) for k in keys)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            values_equal(x, y, f'{path}[{i}]') for i, (x, y) in enumerate(zip(a, b, strict=True))
        )
    return a == b


class BuiltPage:
    """docs/index.html as the site checks read it: the HTML, its prose and its embedded data."""

    def __init__(self, path):
        self.path = path
        self.html = path.read_text(encoding='utf-8')
        # The page without its JSON payloads, so raw data numbers cannot trip
        # the checks for typed-in figures.
        self.prose = re.sub(
            r'<script id="(receipts-cols|receipts-data|opp-data|us-states)" '
            r'type="application/json">.*?</script>',
            '',
            self.html,
            flags=re.DOTALL,
        )
        self.cols = extract_payload(self.html, 'receipts-cols')
        self.rows = [
            decode_row(self.cols, arr) for arr in extract_payload(self.html, 'receipts-data')
        ]
        self.incoming = [r for r in self.rows if r['in_120th'] == 'yes']
        self.opposition = extract_payload(self.html, 'opp-data')
        self.expected = site_expectations(self.rows, self.opposition)


def num(v):
    return v if isinstance(v, (int, float)) else 0
