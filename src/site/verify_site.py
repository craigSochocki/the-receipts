#!/usr/bin/env python3
"""Verify the generated static site (docs/index.html) against the canonical
dataset (congress-money-tracker.json).

Checks:
 1. docs/index.html exists and contains no unreplaced template placeholders.
 2. The embedded compact payload decodes back to the dataset exactly —
    every field of every row, including nested per-cycle lists.
 3. Headline figures recomputed from the embedded data match the dataset:
    664 rows; clean True 84 / None 1; incoming House clean 67 (63 D, 4 R);
    incoming Senate clean 10; Constantino verified clean; Luria null;
    Armstrong "unknown" money cells; top-10 total-accepted names;
    192 primary targets; 53 career-clean incoming House members.
 4. The page's JavaScript parses (node --check on both app scripts).
 5. docs/ serves over HTTP (200 + key strings present).
 6. The generator is deterministic apart from the generation timestamp.

Usage: python3 src/site/verify_site.py [--skip-serve]
Exit non-zero on any failure.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config
from src.site.build_site import (SCALARS, NESTED, NESTED_COLS, main as build_main)

CFG = load_config()
ROOT = CFG["_root"]
SITE_DIR = ROOT / CFG["paths"]["site"]
DATASET_JSON = ROOT / CFG["paths"]["dataset_json"]

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def extract_payload(html, script_id):
    m = re.search(
        r'<script id="%s" type="application/json">(.*?)</script>' % script_id,
        html, re.DOTALL)
    if not m:
        raise SystemExit(f"missing embedded payload: {script_id}")
    return json.loads(m.group(1))


def decode_row(cols, arr):
    o = {k: arr[i] for i, k in enumerate(cols["scalars"])}
    base = len(cols["scalars"])
    nested_names = ["per_cycle", "udp_per_cycle", "self_funding_per_cycle",
                    "other_committees_per_cycle", "all_ie_per_cycle",
                    "all_ie_top_committees"]
    nested_cols = [cols["pc"], cols["upc"], cols["sf"], cols["oc"],
                   cols["aie"], cols["tc"]]
    for j, (name, ccols) in enumerate(zip(nested_names, nested_cols)):
        o[name] = [{k: e[i] for i, k in enumerate(ccols)}
                   for e in (arr[base + j] or [])]
    return o


def values_equal(a, b, path=""):
    """Exact equality after a JSON round-trip (floats survive it)."""
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        # Positional encoding writes None for an absent optional key
        # (e.g. udp_per_cycle 'attribution'), so missing == None here.
        keys = set(a) | set(b)
        return all(values_equal(a.get(k), b.get(k), path + "." + k) for k in keys)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            values_equal(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b)))
    return a == b


def main():
    skip_serve = "--skip-serve" in sys.argv
    html_path = SITE_DIR / "index.html"
    check("docs/index.html exists", html_path.exists())
    if not html_path.exists():
        sys.exit(1)
    html = html_path.read_text(encoding="utf-8")
    check("no unreplaced placeholders", "%%" not in html)

    dataset = json.loads(DATASET_JSON.read_text())
    cols = extract_payload(html, "receipts-cols")
    raw = extract_payload(html, "receipts-data")
    check("embedded row count is 664", len(raw) == 664, f"got {len(raw)}")
    check("column lists match generator",
          cols["scalars"] == SCALARS and cols["pc"] and cols["sf"]
          and cols["oc"] and cols["aie"] and cols["tc"])

    decoded = [decode_row(cols, arr) for arr in raw]
    mismatches = 0
    for i, (d_row, j_row) in enumerate(zip(decoded, dataset)):
        for k, v in j_row.items():
            if k == "all_ie_top_committees" and v is None:
                v = []
            if not values_equal(d_row.get(k), v, k):
                mismatches += 1
                if mismatches <= 5:
                    print(f"  mismatch row {i} {j_row.get('full_name')} field {k}: "
                          f"site={d_row.get(k)!r} dataset={v!r}")
    check("embedded data round-trips exactly (all rows, all fields)",
          mismatches == 0, f"{mismatches} mismatched fields")

    # ---- headline figures, recomputed from the embedded (decoded) data ----
    def num(v):
        return v if isinstance(v, (int, float)) else 0

    clean_true = [r for r in decoded if r["clean_2026"] is True]
    clean_none = [r for r in decoded if r["clean_2026"] is None]
    check("clean True = 84", len(clean_true) == 84, f"got {len(clean_true)}")
    check("clean None = 1 (Luria)",
          len(clean_none) == 1 and clean_none[0]["full_name"] == "Elaine Luria")
    incoming = [r for r in decoded if r["in_120th"] == "yes"]
    h_clean = [r for r in incoming
               if r["chamber_120"] == "House" and r["clean_2026"] is True]
    s_clean = [r for r in incoming
               if r["chamber_120"] == "Senate" and r["clean_2026"] is True]
    check("incoming House clean = 67 (63 D, 4 R)", len(h_clean) == 67
          and sum(1 for r in h_clean if r["party_120"] == "Democrat") == 63
          and sum(1 for r in h_clean if r["party_120"] == "Republican") == 4,
          f"got {len(h_clean)}")
    check("incoming Senate clean = 10", len(s_clean) == 10, f"got {len(s_clean)}")
    const = [r for r in decoded if "Constantino" in r["full_name"]]
    check("Constantino verified clean",
          len(const) == 1 and const[0]["clean_2026"] is True
          and const[0]["self_funding_career"] == 17000000.0)
    arm = [r for r in decoded if "Armstrong" in r["full_name"]]
    check("Armstrong money cells are 'unknown'",
          len(arm) == 1 and arm[0]["individual_contribution_total_career"] == "unknown"
          and arm[0]["total_accepted_career"] is None)
    top10 = [r["full_name"] for r in sorted(
        [x for x in decoded if x["rank_total_accepted"] is not None],
        key=lambda x: x["rank_total_accepted"])[:10]]
    check("top-10 total accepted names",
          top10 == ["Raphael G. Warnock", "Jon Ossoff", "Mark Kelly",
                    "Sherrod Brown", "Ted Cruz", "James Talarico",
                    "Mitch McConnell", "Charles E. Schumer", "Adam B. Schiff",
                    "Tammy Baldwin"], f"got {top10[:3]}")
    targets = [r for r in decoded if r["in_120th"] == "yes"
               and r["chamber_120"] == "House" and r["party_120"] == "Democrat"
               and num(r["dirty_2026"]) > 0]
    check("primary targets = 192", len(targets) == 192, f"got {len(targets)}")
    career_clean_house = [r for r in incoming
                          if r["chamber_120"] == "House"
                          and num(r["corporate_pac_career"]) == 0
                          and num(r["aipac_pac_direct_career"]) == 0
                          and num(r["udp_ie_support_career"]) == 0
                          and num(r["udp_ie_opposing_opponents_career"]) == 0]
    check("career-clean incoming House = 53",
          len(career_clean_house) == 53, f"got {len(career_clean_house)}")

    # ---- JS syntax ----
    app_scripts = re.findall(
        r'<script>(.*?)</script>', html, re.DOTALL)
    check("two app scripts present", len(app_scripts) == 2,
          f"got {len(app_scripts)}")
    node_ok = True
    for i, src in enumerate(app_scripts):
        with tempfile.NamedTemporaryFile("w", suffix=".js",
                                        delete=False) as f:
            f.write(src)
            tmp = f.name
        r = subprocess.run(["node", "--check", tmp],
                           capture_output=True, text=True)
        if r.returncode != 0:
            node_ok = False
            print(f"  node --check script {i} failed:\n{r.stderr[:2000]}")
        Path(tmp).unlink(missing_ok=True)
    check("page JavaScript parses (node --check)", node_ok)

    # ---- serve docs/ locally ----
    if not skip_serve:
        handler = partial(SimpleHTTPRequestHandler, directory=str(SITE_DIR))
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/index.html", timeout=10) as resp:
                body = resp.read().decode("utf-8")
                status = resp.status
            check("local serve returns 200", status == 200, f"got {status}")
            for needle in ["The Receipts", "receipts-data", "Methodology",
                           "primary targets", "Clean money", "Leaderboards"]:
                check(f"served page contains {needle!r}", needle in body)
            check("served page size matches file",
                  len(body.encode("utf-8")) == html_path.stat().st_size)
        except Exception as e:  # noqa: BLE001 - report as a failed check
            check(f"local serve works ({e})", False)
        finally:
            srv.shutdown()

    # ---- runtime smoke test (runs the page's JS against a DOM stub) ----
    import shutil
    smoke = ROOT / "src" / "site" / "smoke_test.js"
    if shutil.which("node") is None:
        print("SKIP runtime smoke test (node not found)")
    else:
        r = subprocess.run(["node", str(smoke), str(html_path)],
                           capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr[:2000])
        check("runtime smoke test (render, tabs, detail, CSV)", r.returncode == 0)

    # ---- determinism (apart from the generation timestamp) ----
    before = html_path.read_bytes()
    build_main()
    after = html_path.read_bytes()
    def strip_ts(b):
        return re.sub(rb"Generated [0-9-]+ [0-9:]+ UTC", b"Generated TS", b)
    check("generator deterministic apart from timestamp",
          strip_ts(before) == strip_ts(after))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        sys.exit(1)
    print("All site checks passed.")
    print(f"dataset md5: {hashlib.md5(DATASET_JSON.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
