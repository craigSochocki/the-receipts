#!/usr/bin/env python3
"""Verify the generated static site (docs/index.html) against the canonical
dataset (congress-money-tracker.json).

Checks:
 1. docs/index.html exists and contains no unreplaced template placeholders.
 2. The embedded compact payload decodes back to the dataset exactly —
    every field of every row, including nested per-cycle lists.
 3. Headline figures recomputed from the embedded data match the dataset:
    664 rows; clean True 98 / None 4 (Luria unverified + 3 unopposed);
    incoming House clean 70 (67 D, 3 R); incoming Senate clean 14;
    Constantino verified clean; Luria null; King-Hinds verified clean
    and contested; 9 ran unopposed; Armstrong "unknown" money cells;
    top-10 total-accepted names; 192 primary targets; 53 career-clean
    incoming House members; dirtiest top 5 in 2026 with the #1-vs-next-
    four comparison; party/outcome derivation (535 Won / 124 Not
    returning / 5 Uncalled, every row with a party source);
    leaderboards lead with dirty (2026, then career) and the default
    table sort is Dirty 2026; dirty_career recomputes and Stevens is
    the career dirty #1; composition charts reconcile to 435 / 100
    with per-category counts matching the dataset exactly. 2028
    primary targets: House 192 (same rule as 2026), Senate 13 Class 3
    Democrats led by Hassan; the tab's intro is computed at render,
    never typed; the front-door pointer opens it via showTab.
    Tolerance presets (methodology §14): AIPAC/UDP flag 231 in the
    120th (291 roster-wide); Balanced tiers clean 84 / below_threshold
    119 / dirty 328 (not-dirty 203), Lenient 84 / 173 / 274 (not-dirty
    257); 2028 targets under presets Strict 192/13, Balanced 133/6,
    Lenient 103/3; the front-door story defaults to Balanced not-dirty
    with the tolerance labeled; the Explore tolerance control
    (Strict / Balanced / Lenient) recomputes the counts, badges, and
    the 2028 tab live.
    Scrollytelling: 7 front-door chapters in narrative order
    (hook, dirtiest, dirty-definition, clean, chamber, finder, data);
    IntersectionObserver reveals gated on html.js (no-JS shows
    everything); prefers-reduced-motion renders everything visible;
    count-up end values equal the computed figures (career dirty total
    $1,070,633,247.20, components reconciling); waffle dots and senate
    tiles stagger on reveal.
 4. The page's JavaScript parses (node --check on both app scripts).
 5. docs/ serves over HTTP (200 + key strings present).
 6. The generator is deterministic apart from the generation timestamp.
 7. The embedded opposition-credit detail matches
    data/intermediate/opposition-computed.json exactly (race-phase level),
    including Stevens' two credited phases.

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
from src.site.build_site import (SCALARS, NESTED, NESTED_COLS, build_opp_payload,
                               main as build_main)

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

    # Visible data-as-of stamp: the coverage end dates it shows must be
    # the ones in config.yaml verification.coverage_end (formatted
    # "Sep 30, 2026" style), and it must carry the "Data as of" label.
    cov = CFG["verification"]["coverage_end"]
    from datetime import datetime as _dt
    cov_dates = [_dt.strptime(cov[k], "%Y-%m-%d").strftime("%b %d, %Y")
                 for k in ("committee_money_pas2", "weball",
                           "independent_expenditures")]
    check("stamp shows config coverage end dates",
          all(d in html for d in cov_dates), f"looking for {cov_dates}")
    check("stamp says 2026 is partial", "2026 is partial" in html)

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

    # ---- opposition-credit detail payload (race-phase level) ----
    opp_embedded = extract_payload(html, "opp-data")
    opp_expected = build_opp_payload()
    check("embedded opposition detail matches opposition-computed.json",
          values_equal(opp_embedded, opp_expected, "opp"),
          f"{len(opp_embedded)} persons, "
          f"{sum(len(v) for v in opp_embedded.values())} race-phases")
    stevens_opp = { (e["cycle"], e["phase"]): e["amount"]
                    for e in opp_embedded.get("S001215", []) }
    check("Stevens drill-down detail: 2022 P $341,792.98, 2026 P $20,139,904.21",
          stevens_opp.get((2022, "P")) == 341792.98
          and stevens_opp.get((2026, "P")) == 20139904.21
          and len(stevens_opp) == 2, f"got {stevens_opp}")

    # ---- headline figures, recomputed from the embedded (decoded) data ----
    def num(v):
        return v if isinstance(v, (int, float)) else 0

    clean_true = [r for r in decoded if r["clean_2026"] is True]
    clean_none = [r for r in decoded if r["clean_2026"] is None]
    check("clean True = 98", len(clean_true) == 98, f"got {len(clean_true)}")
    unopp_none = [r for r in clean_none if r["unopposed_2026"] is True]
    unver_none = [r for r in clean_none if r["unopposed_2026"] is not True]
    check("clean None = 4 (Luria unverified + 3 unopposed)",
          len(clean_none) == 4
          and len(unopp_none) == 3
          and sorted(r["full_name"] for r in unopp_none)
          == ["Aumua Amata Coleman Radewagen", "Ayanna Pressley", "Sara Jacobs"]
          and len(unver_none) == 1
          and unver_none[0]["full_name"] == "Elaine Luria",
          f"got {len(clean_none)}")
    check("unopposed in 2026 = 9",
          sum(1 for r in decoded if r["unopposed_2026"] is True) == 9,
          f"got {sum(1 for r in decoded if r['unopposed_2026'] is True)}")
    king_hinds = [r for r in decoded if "King-Hinds" in r["full_name"]]
    check("King-Hinds verified clean and contested (MP district 01)",
          len(king_hinds) == 1 and king_hinds[0]["clean_2026"] is True
          and king_hinds[0]["unopposed_2026"] is False)
    incoming = [r for r in decoded if r["in_120th"] == "yes"]
    h_clean = [r for r in incoming
               if r["chamber_120"] == "House" and r["clean_2026"] is True]
    s_clean = [r for r in incoming
               if r["chamber_120"] == "Senate" and r["clean_2026"] is True]
    check("incoming House clean = 70 (67 D, 3 R)", len(h_clean) == 70
          and sum(1 for r in h_clean if r["party_120"] == "Democrat") == 67
          and sum(1 for r in h_clean if r["party_120"] == "Republican") == 3,
          f"got {len(h_clean)}")
    check("incoming Senate clean = 14", len(s_clean) == 14, f"got {len(s_clean)}")
    check("methodology clean paragraph is computed, not stale",
          "84 verified clean in the incoming 120th" in html
          and "70 House (67 D, 3 R)" in html
          and "77 verified clean" not in html
          and "67 House (63 D, 4 R)" not in html)

    # ---- landing story + finder (Change 1): computed, never hardcoded ----
    # The story headline is rendered by JavaScript from the embedded
    # dataset, so no "<N> of <M> incoming members" literal may appear in
    # the built page at all: if one does, somebody typed the figure into
    # the template and the next data change will strand it stale. The
    # prose below is the page with the JSON payloads stripped, so raw
    # data numbers cannot trip the check.
    check("landing story block exists",
          'id="landing-story"' in html and 'id="story-clean-link"' in html)
    check("finder controls exist",
          all(x in html for x in ('id="find-state"', 'id="find-district"',
                                  'id="find-person"', 'Find your member')))
    prose = re.sub(
        r'<script id="(receipts-cols|receipts-data|opp-data)" '
        r'type="application/json">.*?</script>', "", html, flags=re.DOTALL)
    check("story headline figure is computed, not hardcoded",
          re.search(r"\d+ of \d+ incoming members", prose) is None
          and re.search(r"\d+ House \+ \d+ Senate", prose) is None,
          "a literal story figure survives in the built page")

    # ---- front door (landing-first): structure, mode, computed figures ----
    check("front-door section exists",
          all(x in html for x in ('id="front-door"', 'id="dirtiest-headline"',
                                  'id="dirtiest-list"', 'id="explore-btn"',
                                  'id="fresh-line"', 'id="explore-head"',
                                  'id="tabs-nav"', 'id="main"')))
    check("mode lives in the URL hash (#explore)",
          "location.hash" in html and "modeFromHash" in html
          and "setMode" in html and "'explore'" in html)
    front = html[html.index('id="front-door"'):html.index('<footer>')]
    check("front door carries no stat cards or totals strip",
          'id="stats"' not in front and 'id="totals"' not in front)
    DIRTY_LITERALS = ["31,025,889", "5,745,013", "4,161,286", "3,446,667",
                      "1,860,780", "15,213,747", "$31.03M", "$15.21M"]
    def has_dirty_literal(text):
        return any(lit in text for lit in DIRTY_LITERALS)
    check("dirtiest figures are computed, not hardcoded",
          not has_dirty_literal(prose),
          "a literal dirtiest figure survives in the built page")
    # Negative test: an injected literal must trip the same detector,
    # proving the clean-page result above is not vacuous.
    check("negative test: injected dirtiest literal trips the check",
          has_dirty_literal(prose + "Stevens took $31,025,889.44"))
    dirty = sorted([r for r in decoded if num(r["dirty_2026"]) > 0],
                   key=lambda r: -num(r["dirty_2026"]))[:5]
    check("dirtiest top 5 in 2026 (names + order)",
          [r["full_name"] for r in dirty] == ["Haley M. Stevens", "Adrian Boafo",
           "Ed Gallrein", "Wesley Bell", "Brett Guthrie"],
          f"got {[r['full_name'] for r in dirty]}")
    top1 = num(dirty[0]["dirty_2026"])
    next4 = sum(num(r["dirty_2026"]) for r in dirty[1:])
    check("headline comparison holds: #1 exceeds next four combined (~2.04x)",
          top1 > next4 and 2.0 < top1 / next4 < 2.1,
          f"#1 {top1} vs next four {next4}, ratio {top1/next4:.3f}")
    check("Stevens headline row is MI-11 and not in the 120th",
          dirty[0]["in_120th"] == "no" and dirty[0]["state"] == "MI"
          and dirty[0]["district_119"] == "11")

    # ---- scrollytelling: chapters, reveals, count-ups, stagger ----
    found_chapters = re.findall(r'data-chapter="([^"]+)"', html)
    check("front door has 7 chapters in narrative order",
          found_chapters == ["hook", "dirtiest", "dirty-definition", "clean",
                             "chamber", "finder", "data"],
          f"got {found_chapters}")
    check("chapter order: hook, dirtiest, explainer, clean, chamber, finder, data",
          html.index('data-chapter="hook"') < html.index('data-chapter="dirtiest"')
          < html.index('data-chapter="dirty-definition"')
          < html.index('data-chapter="clean"')
          < html.index('data-chapter="chamber"')
          < html.index('data-chapter="finder"')
          < html.index('data-chapter="data"'))
    check("scroll reveals use IntersectionObserver; hidden state is JS-gated",
          "IntersectionObserver" in html and "initReveals" in html
          and "html.js .chapter" in html
          and "document.documentElement.classList.add('js')" in html)
    check("reduced-motion path renders everything visible",
          "@media (prefers-reduced-motion: reduce)" in html
          and "opacity:1 !important" in html
          and "matchMedia('(prefers-reduced-motion: reduce)')" in html)
    check("count-up mechanism present (data-value + formatter + rAF)",
          "data-value" in html and "data-format" in html
          and "requestAnimationFrame" in html
          and "function runCountUp" in html
          and "function formatCountUp" in html)
    check("waffle dots and senate tiles stagger on reveal",
          "transition-delay" in html)
    # Explainer: career dirty total recomputes from the embedded data,
    # and its three components sum to it exactly.
    dc_total = sum(num(r["dirty_career"]) for r in decoded)
    dc_parts = (sum(num(r["corporate_pac_career"]) for r in decoded)
                + sum(num(r["aipac_pac_direct_career"]) for r in decoded)
                + sum(num(r["udp_ie_total_benefit_career"]) for r in decoded))
    check("career dirty total is $1,070,633,247.20 (components reconcile)",
          abs(dc_total - 1070633247.20) < 0.01
          and abs(dc_parts - dc_total) < 0.01,
          f"total {dc_total}, parts {dc_parts}")
    check("dirty explainer chapter exists",
          'id="dirty-explainer"' in html and "What counts as dirty" in html
          and "Individual contributions are <b>not</b> dirty money" in html)
    # The explainer's $1.07B must be computed at render, never typed:
    # extend the literal scan the same way the dirtiest figures are
    # guarded, with a negative test proving the detector works.
    EXPLAINER_LITERALS = ["$1.07B", "1,070,633,247", "1,070,633,247.20"]
    check("explainer figures are computed, not hardcoded",
          not any(lit in prose for lit in EXPLAINER_LITERALS),
          "a literal explainer figure survives in the built page")
    check("negative test: injected explainer literal trips the check",
          any(lit in (prose + "career dirty totals $1,070,633,247.20")
              for lit in EXPLAINER_LITERALS))

    # ---- leaderboards lead with dirty; default sort is Dirty 2026 ----
    check("leaderboard order: dirtiest 2026, dirtiest career, total accepted",
          html.index("Top 20 — dirtiest in 2026")
          < html.index("Top 20 — dirtiest, career")
          < html.index("Top 20 — total accepted (career)"))
    check("leaderboards intro frames dirty first",
          "Dirty money leads" in html
          and "Individual contributions are not dirty money" in html)
    check("default table sort is Dirty 2026 desc",
          "sortKey:'dirty_2026'" in html
          and "sortKey:'total_accepted_career'" not in html)
    dc_top = sorted([r for r in decoded
                     if isinstance(r["dirty_career"], (int, float))],
                    key=lambda r: -r["dirty_career"])[:3]
    check("career dirty top 3: Stevens, Hoyer, Latimer",
          [r["full_name"] for r in dc_top]
          == ["Haley M. Stevens", "Steny H. Hoyer", "George Latimer"],
          f"got {[r['full_name'] for r in dc_top]}")
    check("dirty_career is null only for Armstrong",
          [r["full_name"] for r in decoded if r["dirty_career"] is None]
          == ["Alan Armstrong"])

    # ---- composition charts (House waffle, Senate state tiles): reconcile to 435 / 100 ----
    check("composition section exists on the front door",
          'id="composition"' in html and "renderComposition" in html
          and "waffleSVG" in html and "senateTilesSVG" in html
          and "compositionSeats" in html)
    check("composition sits after the clean story, before the finder",
          html.index('id="landing-story"') < html.index('id="composition"')
          < html.index('id="finder"'))
    COMP_LITERALS = ["Dirty D 192", "Clean D 64", "Dirty R 169",
                     "Clean R 2", "Dirty D 40", "Clean D 13", "Dirty R 44",
                     "Clean I 1", "Dirty I 1", "Unopposed 2",
                     "Unverified 1", "Uncalled 5"]
    check("House waffle is 15 rows x 29 columns, column-major fill",
          "WAFFLE_ROWS = 15" in html and "WAFFLE_COLS = 29" in html
          and "Math.floor(i/WAFFLE_ROWS)" in html,
          "waffle geometry missing from the built page")
    check("composition counts are computed, not hardcoded",
          not any(lit in prose for lit in COMP_LITERALS),
          "a literal composition count survives in the built page")
    TERR = {"AS", "GU", "MP", "PR", "VI", "DC"}
    def party_letter(r):
        p = r["party_120"] or r["party_119"] or "?"
        return {"Democrat": "D", "Republican": "R",
                "Independent": "I"}.get(p, p)
    def seat_status(r):
        if r["clean_2026"] is True:
            return "clean"
        if r["clean_2026"] is False:
            return "dirty"
        return "unopposed" if r["unopposed_2026"] is True else "unverified"
    from collections import Counter as _Counter
    house_voting = [r for r in incoming if r["chamber_120"] == "House"
                    and r["state"] not in TERR]
    sen = [r for r in incoming if r["chamber_120"] == "Senate"]
    h_counts = _Counter((party_letter(r), seat_status(r))
                        for r in house_voting)
    s_counts = _Counter((party_letter(r), seat_status(r)) for r in sen)
    check("House composition reconciles: 430 named voting + 5 uncalled = 435",
          len(house_voting) == 430 and 435 - len(house_voting) == 5,
          f"named {len(house_voting)}")
    check("House chart counts: Dirty D 192, Clean D 64, Dirty R 169, Clean R 2, Unopposed 2, Unverified 1",
          h_counts == {("D", "dirty"): 192, ("D", "clean"): 64,
                       ("D", "unopposed"): 2, ("D", "unverified"): 1,
                       ("R", "dirty"): 169, ("R", "clean"): 2},
          f"got {dict(h_counts)}")
    check("Senate composition reconciles: 99 named + 1 uncalled = 100",
          len(sen) == 99 and 100 - len(sen) == 1, f"named {len(sen)}")
    check("Senate chart counts: Dirty D 40, Clean D 13, Dirty R 44, Dirty I 1, Clean I 1",
          s_counts == {("D", "dirty"): 40, ("D", "clean"): 13,
                       ("R", "dirty"): 44, ("I", "dirty"): 1,
                       ("I", "clean"): 1},
          f"got {dict(s_counts)}")
    check("Senate tiles cover 50 states: 49 with two named, Alaska with one + uncalled",
          len({r["state"] for r in sen}) == 50 and len(sen) == 99
          and sum(1 for r in sen if r["state"] == "AK") == 1,
          f"states {len({r['state'] for r in sen})}, named {len(sen)}")
    check("Senate tile renderer present (state tiles + dotted patterns)",
          "senateTilesSVG" in html and "dots-" in html
          and "TILE_COLS = 10" in html,
          "senateTilesSVG or dotted patterns missing from the built page")
    delegates = [r for r in incoming if r["chamber_120"] == "House"
                 and r["state"] in TERR]
    d_counts = _Counter((party_letter(r), seat_status(r))
                        for r in delegates)
    check("delegates not plotted: 6 (Clean D 3, Clean R 1, Unopposed R 1, Dirty PPD 1)",
          len(delegates) == 6
          and d_counts == {("D", "clean"): 3, ("R", "clean"): 1,
                           ("R", "unopposed"): 1, ("PPD", "dirty"): 1},
          f"got {dict(d_counts)}")

    # ---- party chips + outcome labels (person marks) ----
    # The chips render in JS at runtime (asserted in the smoke test);
    # here: the helpers exist, and the derivation inputs recomputed
    # from the embedded data cover every row with no per-person cases.
    check("party chip + outcome helpers present",
          "function partyChip" in html and "function outcomeLabel" in html
          and "'Not returning'" in html and "'Uncalled'" in html
          and 'class="pchip ' in html
          and "Democrat:['D','d']" in html and "Republican:['R','r']" in html
          and "Independent:['I','o']" in html)
    no_party = [r for r in decoded if not r["party_120"] and not r["party_119"]]
    check("every row has a party source (party_120 else party_119)",
          len(no_party) == 0, f"{len(no_party)} rows with no party")
    outcomes = {v: sum(1 for r in decoded if r["in_120th"] == v)
                for v in ("yes", "no", "unknown")}
    check("outcome mapping covers all 664 (Won 535 / Not returning 124 / Uncalled 5)",
          outcomes == {"yes": 535, "no": 124, "unknown": 5}, f"got {outcomes}")
    def mark_spot(name, party, outcome):
        rows = [r for r in decoded if name in r["full_name"]]
        return (len(rows) == 1
                and (rows[0]["party_120"] or rows[0]["party_119"]) == party
                and {"yes": "Won", "unknown": "Uncalled",
                     "no": "Not returning"}[rows[0]["in_120th"]] == outcome)
    check("marks spot-check: Stevens D / Not returning",
          mark_spot("Stevens", "Democrat", "Not returning"))
    check("marks spot-check: El-Sayed D / Won",
          mark_spot("El-Sayed", "Democrat", "Won"))
    check("marks spot-check: Guthrie R / Won",
          mark_spot("Guthrie", "Republican", "Won"))
    check("marks spot-check: Hernández PPD / Won (other gray chip)",
          mark_spot("Hernández", "PPD", "Won"))
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
    targets28_h = [r for r in decoded if r["in_120th"] == "yes"
                   and r["chamber_120"] == "House"
                   and r["party_120"] == "Democrat"
                   and num(r["dirty_2026"]) > 0]
    targets28_s = [r for r in decoded if r["in_120th"] == "yes"
                   and r["chamber_120"] == "Senate"
                   and r["party_120"] == "Democrat"
                   and r["senate_class"] == 3
                   and num(r["dirty_2026"]) > 0]
    check("2028 targets: House 192, Senate 13",
          len(targets28_h) == 192 and len(targets28_s) == 13,
          f"got House {len(targets28_h)}, Senate {len(targets28_s)}")
    check("2028 Senate targets led by Hassan, Wyden, Schatz",
          [r["full_name"] for r in sorted(
              targets28_s, key=lambda r: -num(r["dirty_2026"]))[:3]]
          == ["Margaret Wood Hassan", "Ron Wyden", "Brian Schatz"],
          f"got {[r['full_name'] for r in sorted(targets28_s, key=lambda r: -num(r['dirty_2026']))[:3]]}")
    check("2028 Senate targets are all corporate-PAC dirty in 2026",
          all(num(r["corp_2026"]) == num(r["dirty_2026"])
              and num(r["aipac_direct_2026"]) == 0
              and num(r["udp_benefit_2026"]) == 0 for r in targets28_s))
    check("2028 tab exists (both tables + intro + renderer + Class 3 filter)",
          all(x in html for x in ('id="tab-targets28"',
                                  'id="targets28-house-table"',
                                  'id="targets28-senate-table"',
                                  'id="targets28-intro"',
                                  "renderTargets2028", "senate_class===3",
                                  "Dirty career"))
          and "renderTargets2028" in html)
    check("2028 tab sits after the 2026 tab, before Methodology",
          html.index('data-tab="targets"')
          < html.index('data-tab="targets28"')
          < html.index('data-tab="method"'))
    check("2028 front-door pointer exists (Data chapter, onclick)",
          'id="targets28-btn"' in html
          and "showTab('targets28')" in html
          and html.index('id="targets28-btn"')
          > html.index('data-chapter="finder"')
          and html.index('id="targets28-btn"')
          < html.index('id="explore-btn"'))
    # The 2028 intro is rendered from the filtered rows, so its counts
    # must not appear as literals in the tab's static HTML (the 2026
    # tab's typed "192 House Democrats" intro is pre-existing and
    # untouched — the scan below is scoped to the 2028 section only).
    t28 = html[html.index('id="tab-targets28"'):html.index('id="tab-method"')]
    check("2028 intro counts are computed, not hardcoded",
          re.search(r"\d+ House Democrats", t28) is None
          and re.search(r"\d+ Democratic senators", t28) is None
          and "house.length" in html and "senate.length" in html
          and "A watchlist, not a prediction" in html,
          "a literal 2028 count survives in the built page")
    check("negative test: injected 2028 count trips the check",
          re.search(r"\d+ House Democrats",
                    t28 + "192 House Democrats") is not None)
    career_clean_house = [r for r in incoming
                          if r["chamber_120"] == "House"
                          and num(r["corporate_pac_career"]) == 0
                          and num(r["aipac_pac_direct_career"]) == 0
                          and num(r["udp_ie_support_career"]) == 0
                          and num(r["udp_ie_opposing_opponents_career"]) == 0]
    check("career-clean incoming House = 53",
          len(career_clean_house) == 53, f"got {len(career_clean_house)}")

    # ---- tolerance presets (methodology §14): flag + tiers ----
    check("embedded payload carries the tolerance columns",
          all(k in cols["scalars"] for k in
              ("aipac_udp_flag_2026", "tier_balanced_2026",
               "tier_lenient_2026")))
    flag120 = [r for r in incoming if r["aipac_udp_flag_2026"] is True]
    flag_all = [r for r in decoded if r["aipac_udp_flag_2026"] is True]
    check("AIPAC/UDP flag: 231 in the 120th, 291 roster-wide",
          len(flag120) == 231 and len(flag_all) == 291,
          f"got {len(flag120)} / {len(flag_all)}")
    check("tier nulls align with clean nulls exactly",
          all((r["tier_balanced_2026"] is None) == (r["clean_2026"] is None)
              for r in decoded)
          and all((r["tier_lenient_2026"] is None) == (r["clean_2026"] is None)
                  for r in decoded))
    bal = _Counter(r["tier_balanced_2026"] for r in incoming)
    leni = _Counter(r["tier_lenient_2026"] for r in incoming)
    check("Balanced tiers in the 120th: clean 84 / below 119 / dirty 328",
          bal == {"clean": 84, "below_threshold": 119, "dirty": 328, None: 4},
          f"got {dict(bal)}")
    check("Lenient tiers in the 120th: clean 84 / below 173 / dirty 274",
          leni == {"clean": 84, "below_threshold": 173, "dirty": 274, None: 4},
          f"got {dict(leni)}")

    def not_dirty(rows, tier_key):
        return [r for r in rows if r[tier_key] in ("clean", "below_threshold")]

    check("not-dirty in the 120th: Balanced 203, Lenient 257",
          len(not_dirty(incoming, "tier_balanced_2026")) == 203
          and len(not_dirty(incoming, "tier_lenient_2026")) == 257)

    def targets28_preset(rows, rule):
        h = [r for r in rows if r["chamber_120"] == "House"
             and r["party_120"] == "Democrat" and rule(r)]
        s = [r for r in rows if r["chamber_120"] == "Senate"
             and r["party_120"] == "Democrat" and r["senate_class"] == 3
             and rule(r)]
        return len(h), len(s)

    check("2028 targets under presets: Strict 192/13, Balanced 133/6, Lenient 103/3",
          targets28_preset(incoming, lambda r: num(r["dirty_2026"]) > 0) == (192, 13)
          and targets28_preset(
              incoming, lambda r: r["tier_balanced_2026"] == "dirty") == (133, 6)
          and targets28_preset(
              incoming, lambda r: r["tier_lenient_2026"] == "dirty") == (103, 3))
    check("tolerance control exists (Strict / Balanced / Lenient, Balanced default)",
          'id="f-tolerance"' in html and 'id="tolerance-note"' in html
          and 'value="strict"' in html and 'value="balanced" selected' in html
          and 'value="lenient"' in html
          and "over $100,000 and over 5% of 2026 receipts" in html
          and "over $250,000 and over 10% of 2026 receipts" in html
          and "setPreset" in html)
    check("flag badge + below-threshold badge exist (not the Dirty badge)",
          'badge flag' in html and 'AIPAC/UDP' in html
          and 'badge below' in html and 'Below threshold' in html
          and "Corporate PAC tolerance presets" in html)

    # ---- Wave 2 (redesign): D2 masthead demotion ----
    # The masthead title used to be bigger than the hook (1.7rem vs
    # 1.55rem on mobile) — the wordmark led, not the story. D2 shrinks
    # the title to ~1.15rem and lets the hook lead at 1.9rem on mobile.
    check("D2: masthead title demoted to 1.15rem, hook leads at 1.9rem on mobile",
          "h1{font-size:1.15rem" in html
          and ".hook{font-size:1.9rem}" in html
          and "h1{font-size:1.7rem" not in html)

    # ---- Wave 2 (redesign): D3 orientation ----
    # Chapter headings at 1.3rem with eyebrow kickers (one per
    # chapter with an h2), the clean count in the same .big-number
    # treatment as the dirty total, and a slim footer that lives
    # inside #front-door (the page footer stays hidden there).
    check("D3: chapter h2s are 1.3rem with eyebrow kickers",
          ".frontdoor h2{font-size:1.3rem" in html
          and html.count('class="kicker"') == 5
          and ".frontdoor .kicker{" in html)
    check("D3: slim front-door footer lives inside #front-door",
          'class="frontfoot"' in html
          and html.index('id="front-door"')
          < html.index('class="frontfoot"')
          < html.index('<footer>'))
    _cs = html.index('function renderCleanStory')
    _ce = html.index('function renderDirtyExplainer', _cs)
    check("D3: clean story count uses the same big-number treatment",
          'big-number' in html[_cs:_ce])

    # ---- Wave 2 (redesign): D4/D5 colour semantics ----
    # Green means clean and only clean: the only remaining green
    # uses are the Clean badge and the two clean boxes (story,
    # callout). Actions, the selected tab, the pressed view button
    # and the Dirty badge are ink; the selected tab also gets a
    # non-colour cue (bold + underline). The "Not clean" label was
    # already renamed to "Dirty" (eddcb1c) — verified absent here,
    # not duplicated.
    check("D4/D5: green is clean-only; actions, selected tab, Dirty badge are ink",
          'button[aria-selected="true"]{background:var(--ink);color:#fff;border-color:var(--ink);font-weight:700;text-decoration:underline' in html
          and '.badge.dirty{background:var(--ink);color:#fff}' in html
          and 'border:1px solid var(--ink);background:var(--ink)' in html
          and html.count('var(--accent)') == 3
          and html.count('var(--accent-soft)') == 3
          and 'Not clean' not in html)

    # ---- Wave 2 (redesign): D8 tab strip + labelled filter rows ----
    # The tab bar is one horizontal scroll strip (no wrapping); the
    # Tracker filters sit in two labelled rows (Filter / Show only).
    # Tabs keep the squared-top radius — never pill-shaped.
    check("D8: tab bar is one horizontal scroll strip, tabs not pill-shaped",
          '.tabs{display:flex;gap:4px;flex-wrap:nowrap;overflow-x:auto' in html
          and '.tabs button{flex:none;border:1px solid var(--line);background:var(--bg);border-radius:8px 8px 0 0' in html)
    check("D8: Tracker filters in two labelled rows",
          'class="controls controls-rows"' in html
          and html.count('class="controls-row"') == 2
          and 'class="controls-label">Filter<' in html
          and 'class="controls-label">Show only<' in html)

    # ---- Wave 2 (redesign): D1 Senate tiles reflow on phones ----
    # Below 560px the Senate tiles render 5 wide x 10 tall (320x505
    # viewBox); at desktop width they stay 10 wide (645x250). The
    # waffle geometry is untouched (D1's waffle changes were cut).
    check("D1: Senate tiles reflow to 5 wide below 560px, 10 wide above",
          "TILE_COLS = 10" in html and "TILE_COLS_NARROW = 5" in html
          and "function senateCols" in html
          and "matchMedia('(max-width: 560px)')" in html
          and "addEventListener('resize'" in html)

    # ---- Wave 2 (redesign): D9 drill-down collapses on mobile ----
    # The key-value grid is one column on phones, and every cycle
    # table in the drill-down is a <details> element (first one
    # open) instead of a wall of expanded tables.
    check("D9: cycle tables are <details> (first open); kv is 1 column on mobile",
          "function cycleTable(title, rows, cols, open)" in html
          and "'<details'+(open?' open':'')+' class=\"cycle\">" in html
          and '.detail .kv{grid-template-columns:1fr}' in html)

    # ---- Wave 2 (redesign): D10 tabular numerals now ----
    # Figures align in their columns: tabular numerals on the table
    # itself (every cell, not just the .num money columns) and on
    # the display numbers (hook, big-number, stat and totals
    # figures). The full 6-step type scale + 4-step gray remap stay
    # deferred to their own commit with a screenshot review.
    check("D10: tabular numerals on tables and display numbers",
          re.search(r"table\{[^}]*font-variant-numeric:tabular-nums",
                    html) is not None
          and '.big-number{font-size:2.1rem;font-weight:700;margin:2px 0 0;line-height:1.2;font-variant-numeric:tabular-nums}' in html
          and html.count('font-variant-numeric:tabular-nums') == 8)

    # ---- Wave 2 (redesign): D7 Explore stats 7 -> 3 ----
    # Only three cards: people tracked, the not-dirty count, and one
    # combined "not judged" card (9 ran unopposed + 1 unverified,
    # Luria, with names). The cutoffs paragraph is NOT deleted — the
    # veto stands (AGENTS.md §4 requires cutoffs labelled
    # everywhere); it collapses into a <details> instead.
    check("D7: Explore stats are 3 cards incl. a combined not-judged card",
          "not judged" in html and "ran unopposed in 2026" in html
          and "unverified: " in html)
    check("D7: cutoffs survive, collapsed into a details element",
          '<details class="cutoffs">' in html
          and "2026 is partial — coverage end dates" in html
          and "Sep 30, 2026" in html and "Oct 14, 2026" in html
          and "Oct 31, 2026" in html)

    # ---- Wave 2 (redesign): D6/FE3 compact/exact money toggle ----
    # A persisted toggle (Compact default, Exact shows dollars and
    # cents) governs the Explore data views; the drill-down header
    # always shows exact figures. The option labels use format
    # examples ($1.23M / $1,234,567.89), never a real figure.
    check("D6/FE3: compact/exact money toggle exists, Compact default, persisted",
          'id="f-money"' in html and 'value="compact" selected' in html
          and 'value="exact"' in html and 'localStorage' in html
          and "function moneyShort" in html and "function setMoneyFmt" in html
          and "return 'compact';" in html)
    check("D6/FE3: detail header always shows exact figures",
          'class="detail-head"' in html
          and "fmtMoney(p.dirty_2026)" in html
          and "fmtMoney(p.total_accepted_career)" in html)

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
                           "primary targets", "2028 primary targets",
                           "Clean money", "Leaderboards",
                           "Data as of", "Find your member",
                           "took no dirty money in 2026",
                           "Dirtiest in 2026", "Explore the full data"]:
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
