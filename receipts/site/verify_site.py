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

Usage: python3 receipts/site/verify_site.py [--skip-serve]
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
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from receipts.common.config import load_config
from receipts.common.baseline import expected as baseline_figure
from receipts.site.expectations import figure_literals, site_expectations
from receipts.site.build_site import SCALARS, build_opp_payload, main as build_main

CFG = load_config()
ROOT = CFG["_root"]
SITE_DIR = ROOT / CFG["paths"]["site"]
DATASET_JSON = ROOT / CFG["paths"]["dataset_json"]

FAILURES = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def pin(name, key, observed):
    """Check a figure that new FEC data can move against the baseline."""
    want = baseline_figure(key, observed)
    check(f"{name} [{key}]", observed == want,
          "" if observed == want else f"got {observed!r}, baseline {want!r}")


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
    # Dataset-level counts use the same baseline keys as verify_dataset.py,
    # so the site and the dataset cannot disagree.
    EXP = site_expectations(decoded, opp_embedded)
    for section in ("headline", "career_dirty", "charts", "detail"):
        pin(f"site figures: {section}", f"site.{section}", EXP[section])
    c, t, t28 = EXP["clean"], EXP["tiers"], EXP["targets_2028"]
    pin("clean True", "clean_2026.true_total", c["true_total"])
    pin("incoming House clean", "clean_2026.house_120th_verified_clean", c["house_120"])
    pin("incoming House clean D", "clean_2026.house_120th_verified_clean_democrat",
        c["house_120_democrat"])
    pin("incoming House clean R", "clean_2026.house_120th_verified_clean_republican",
        c["house_120_republican"])
    pin("incoming Senate clean", "site.clean.senate_120", c["senate_120"])
    pin("clean None: unopposed / unverified names", "site.clean.null_names",
        {"unopposed": c["null_unopposed"], "unverified": c["null_unverified"]})
    pin("unopposed in 2026", "site.clean.unopposed_total", c["unopposed_total"])
    pin("career-clean incoming House (incl. opposition credit)",
        "site.clean.career_clean_house_120", c["career_clean_house_120"])
    pin("AIPAC/UDP flag in the 120th", "tiered_2026.aipac_udp_flag_120th", t["flag_120"])
    pin("AIPAC/UDP flag roster-wide", "tiered_2026.aipac_udp_flag_all", t["flag_all"])
    for preset in ("balanced", "lenient"):
        for tier_name, n in t[preset].items():
            pin(f"{preset} tier {tier_name} in the 120th",
                f"tiered_2026.{preset}.{tier_name}", n)
        pin(f"not-dirty in the 120th under {preset}",
            f"tiered_2026.{preset}.not_dirty", t["not_dirty_120"][preset])
    pin("House not dirty under Balanced (of incoming House incl. delegates)",
        "site.tiers.house_not_dirty_balanced", t["house_not_dirty_balanced"])
    for preset in ("strict", "balanced", "lenient"):
        pin(f"2028 targets {preset} House",
            f"tiered_2026.targets_2028_{preset}_house", t28[preset][0])
        pin(f"2028 targets {preset} Senate Class 3",
            f"tiered_2026.targets_2028_{preset}_senate_class3", t28[preset][1])
    pin("2028 watchlist order + lead figures", "site.targets_2028.order",
        {k: v for k, v in t28.items() if k not in ("strict", "balanced", "lenient")})

    def num(v):
        return v if isinstance(v, (int, float)) else 0

    king_hinds = [r for r in decoded if "King-Hinds" in r["full_name"]]
    check("King-Hinds contested, not unopposed (MP district 01)",
          len(king_hinds) == 1 and king_hinds[0]["unopposed_2026"] is False)
    incoming = [r for r in decoded if r["in_120th"] == "yes"]
    check("2026 primary-target intro states the computed count",
          f"{t28['targets_2026_house']} House Democrats in the incoming 120th "
          "took dirty money in 2026" in html)
    check("methodology clean paragraph is computed, not stale",
          f"{c['all_120']} verified clean in the incoming 120th" in html
          and f"{c['house_120']} House ({c['house_120_democrat']} D, "
              f"{c['house_120_republican']} R)" in html,
          "the methodology paragraph does not state the computed clean counts")

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
    # ---- FE5: the hash carries the whole view (Change 2) ----
    check("FE5: hash serializes/parses/restores the full view",
          "function parseHash" in html and "function applyHash" in html
          and "function hashFromState" in html and "function syncHash" in html
          and "function writeHash" in html)
    check("FE5: hashchange restores state (not just the mode)",
          "addEventListener('hashchange', ()=>applyHash())" in html)
    check("FE5: open drill-down lives in the URL (detail=key)",
          "parts.push('detail='+encodeURIComponent(detailKey))" in html)
    check("FE5: mode changes push, filter/tab changes replace",
          "syncHash(false)" in html and "syncHash(true)" in html)
    check("FE5: Back (hashchange) closes the sheet without a hash write",
          "closeDetail({pop:false})" in html)
    # ---- U1 leftovers: sticky tab bar + finder in Explore ----
    check("U1: tab bar sticks in Explore (hidden in front-door mode)",
          "position:sticky;top:0;z-index:10;background:var(--bg)" in html)
    check("U1: finder reachable from Explore via a slot (one node, moved)",
          'id="finder-slot"' in html and "function placeFinder" in html
          and "slot.appendChild(finder)" in html
          and "finderHome.parent.insertBefore(finder, finderHome.next)" in html)
    # ---- U10: prev/next, View in Tracker, anchor nav ----
    check("U10: prev/next walk the filtered set, View in Tracker, anchor nav",
          'id="detail-prev"' in html and 'id="detail-next"' in html
          and "View in Tracker" in html and 'class="detail-nav"' in html
          and "sortRows(applyFilters())" in html and "data-anchor" in html)
    check("U10: anchors are buttons, not hash links",
          'data-anchor="sec-career"' in html and 'href="#sec-' not in html)
    check("U10: sticky sheet header (name + Close + prev/next)",
          ".detail-top{position:sticky" in html)
    front = html[html.index('id="front-door"'):html.index('<footer>')]
    check("front door carries no stat cards or totals strip",
          'id="stats"' not in front and 'id="totals"' not in front)
    DIRTY_LITERALS = figure_literals(EXP)
    def has_dirty_literal(text):
        return any(lit in text for lit in DIRTY_LITERALS)
    check("dirtiest figures are computed, not hardcoded",
          not has_dirty_literal(prose),
          "a literal dirtiest figure survives in the built page")
    # Negative test: an injected literal must trip the same detector,
    # proving the clean-page result above is not vacuous.
    check("negative test: injected dirtiest literal trips the check",
          has_dirty_literal(prose + "took $" + DIRTY_LITERALS[0] + ".00"))
    dirty = sorted([r for r in decoded if num(r["dirty_2026"]) > 0],
                   key=lambda r: -num(r["dirty_2026"]))[:5]
    top1 = num(dirty[0]["dirty_2026"])
    next4 = sum(num(r["dirty_2026"]) for r in dirty[1:])
    check("headline comparison line appears only if #1 exceeds the next four",
          EXP["headline"]["exceeds_next_four"] == (top1 > next4))

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
    check("career dirty total: components reconcile",
          abs(dc_parts - dc_total) < 0.01,
          f"total {dc_total}, parts {dc_parts}")
    check("dirty explainer chapter exists",
          'id="dirty-explainer"' in html and "What counts as dirty" in html
          and "Individual contributions are <b>not</b> dirty money" in html)
    # The explainer's $1.07B must be computed at render, never typed:
    # extend the literal scan the same way the dirtiest figures are
    # guarded, with a negative test proving the detector works.
    EXPLAINER_LITERALS = [EXP["career_dirty"]["total_compact"],
                          f"{dc_total:,.2f}".rsplit(".", 1)[0], f"{dc_total:,.2f}"]
    check("explainer figures are computed, not hardcoded",
          not any(lit in prose for lit in EXPLAINER_LITERALS),
          "a literal explainer figure survives in the built page")
    check("negative test: injected explainer literal trips the check",
          any(lit in (prose + "career dirty totals $" + EXPLAINER_LITERALS[2])
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
    check("career dirty top 3 are in descending order",
          [r["full_name"] for r in dc_top] == EXP["career_dirty"]["top3"])
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
    def _legend(counts):
        return [f"{k.split()[0].capitalize()} {k.split()[1]} {n}" for k, n in counts.items()]
    COMP_LITERALS = (_legend(EXP["charts"]["house"]) + _legend(EXP["charts"]["senate"])
                     + [f"Uncalled {435 - EXP['charts']['house_named']}"])
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
    house_voting = [r for r in incoming if r["chamber_120"] == "House"
                    and r["state"] not in TERR]
    sen = [r for r in incoming if r["chamber_120"] == "Senate"]
    check("House composition reconciles: 430 named voting + 5 uncalled = 435",
          len(house_voting) == 430 and 435 - len(house_voting) == 5,
          f"named {len(house_voting)}")
    check("Senate composition reconciles: 99 named + 1 uncalled = 100",
          len(sen) == 99 and 100 - len(sen) == 1, f"named {len(sen)}")
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
    check("delegates not plotted: 6", len(delegates) == 6, f"got {len(delegates)}")

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
    check("Constantino is a single row", len(const) == 1)
    arm = [r for r in decoded if "Armstrong" in r["full_name"]]
    check("Armstrong money cells are 'unknown'",
          len(arm) == 1 and arm[0]["individual_contribution_total_career"] == "unknown"
          and arm[0]["total_accepted_career"] is None)
    targets28_s = [r for r in decoded if r["in_120th"] == "yes"
                   and r["chamber_120"] == "Senate"
                   and r["party_120"] == "Democrat"
                   and r["senate_class"] == 3
                   and num(r["dirty_2026"]) > 0]
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
    # The 2028 intro counts are rendered at runtime; none may be typed.
    t28_html = html[html.index('id="tab-targets28"'):html.index('id="tab-method"')]
    check("2028 intro counts are computed, not hardcoded",
          re.search(r"\d+ House Democrats", t28_html) is None
          and re.search(r"\d+ Democratic senators", t28_html) is None
          and "house.length" in html and "senate.length" in html
          and "A watchlist, not a prediction" in html,
          "a literal 2028 count survives in the built page")
    check("negative test: injected 2028 count trips the check",
          re.search(r"\d+ House Democrats",
                    t28_html + "999 House Democrats") is not None)
    # ---- tolerance presets (methodology §14): flag + tiers ----
    check("embedded payload carries the tolerance columns",
          all(k in cols["scalars"] for k in
              ("aipac_udp_flag_2026", "tier_balanced_2026",
               "tier_lenient_2026")))
    check("tier nulls align with clean nulls exactly",
          all((r["tier_balanced_2026"] is None) == (r["clean_2026"] is None)
              for r in decoded)
          and all((r["tier_lenient_2026"] is None) == (r["clean_2026"] is None)
                  for r in decoded))
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
          "function cycleTable(title, rows, cols, open, id)" in html
          and "'<details'+(id?' id=\"'+id+'\"':'')+(open?' open':'')+' class=\"cycle\">" in html
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
          and all(f"<b>{datetime.strptime(str(cov[k]), '%Y-%m-%d').strftime('%b %d, %Y')}</b>"
                  in html for k in ("committee_money_pas2", "weball",
                                    "independent_expenditures")))

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

    # ---- Wave 2 (redesign): U4 charts are tappable ----
    # Waffle dots and Senate tile halves carry the person's key,
    # and one delegated listener on the composition container opens
    # the drill-down. Uncalled seats carry no key and stay inert.
    # Per-dot keyboard focus was cut (435 dots ~ 535 tab stops).
    check("U4: charts are tappable via a delegated SVG listener",
          "data-key" in html
          and "getElementById('composition').addEventListener('click'" in html
          and "closest('[data-key]')" in html)

    # ---- Wave 2 (redesign): FE10 stagger cap + text alternative ----
    # The waffle and tile staggers are scaled so the whole sequence
    # stays under ~500ms (was ~1.1s / ~1.5s); the dirtiest rows were
    # already 360ms. Each chart also gets a visually-hidden
    # sentence-form text alternative. The sticky-th clause is NOT
    # done here: the only concrete fix (a 70vh inner scroller) was
    # cut, and no other pure-CSS fix exists — see the wave report.
    check("FE10: chart staggers capped under ~500ms",
          '480/(WAFFLE_COLS-1)' in html and '480/49' in html
          and 'col*40' not in html and 'i*30' not in html)
    check("FE10: charts have a visually-hidden text alternative",
          '.visually-hidden{' in html and 'function chartAltText' in html
          and 'class="visually-hidden"' in html)

    # ---- U5: skip link ----
    # One Tab from the top of the page jumps straight to the data
    # (Explore). Hidden until focused; the slim sticky front-door
    # header stays dropped this round.
    check("U5: skip link to the data exists, hidden until focused",
          'id="skip-link"' in html and 'Skip to the data' in html
          and '.skip-link{position:absolute' in html
          and '.skip-link:focus{top:0}' in html)

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
    smoke = ROOT / "receipts" / "site" / "smoke_test.js"
    if shutil.which("node") is None:
        print("SKIP runtime smoke test (node not found)")
    else:
        exp_path = ROOT / CFG["paths"]["intermediate"] / "site_expectations.json"
        exp_path.parent.mkdir(parents=True, exist_ok=True)
        exp_path.write_text(json.dumps(EXP, indent=1))
        r = subprocess.run(["node", str(smoke), str(html_path), str(exp_path)],
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
