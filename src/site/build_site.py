#!/usr/bin/env python3
"""The Receipts — static site generator.

Reads the canonical dataset (congress-money-tracker.json at the repo root)
and emits the static site under docs/ for GitHub Pages. The site is a
single self-contained index.html: the dataset is embedded in a compact
positional encoding (column list + array-of-arrays, ~1.6 MB vs 5.5 MB
minified JSON) and every view on the page — table, filters, leaderboards,
clean view, breakdown, primary targets, CSV download — is computed from
that embedded data at runtime, so the figures on the page can never drift
from the dataset. A second, smaller payload carries the race-phase UDP
opposition-credit detail (from data/intermediate/opposition-computed.json,
the race-level record) so a person's drill-down can show the credit split
by primary / general / other phase.

Usage:
    python3 src/site/build_site.py            # regenerate docs/index.html
    python3 src/site/verify_site.py           # verify the generated site

Rules (see AGENTS.md):
- Never hand-edit docs/index.html. Edit this generator and re-run it.
- The generator must be deterministic apart from the generation timestamp
  in the footer (dataset md5 + data_as_of are the stable identifiers).
- Figures are never hardcoded in the template: header stats, leaderboards
  and totals are all computed from the embedded data in the browser.
- Two modes, one page (landing-first, Nov 12, 2026): the front door is
  the default — dirtiest in 2026, the clean story, the finder, one
  freshness line, one "Explore the full data" button — and #explore opens
  the full-data workspace (tabs, filters, table, methodology) with the
  story and finder removed from above the table. Mode only lives in the
  URL hash; filters/tabs get no URL state (Change 2, queued).
"""
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.common.config import load_config

CFG = load_config()
ROOT = CFG["_root"]
SITE_DIR = ROOT / CFG["paths"]["site"]
DATASET_JSON = ROOT / CFG["paths"]["dataset_json"]
DATASET_CSV = ROOT / CFG["paths"]["dataset_csv"]

# ---- compact encoding: column lists (fixed order) ----
# Scalar fields, in the order they appear in each row array. Must cover
# every field the page reads; the verifier checks the round-trip.
SCALARS = [
    "person_key", "full_name", "state",
    "district_119", "district_120", "chamber_119", "chamber_120",
    "party_119", "party_120", "leadership_119", "leadership_120",
    "in_119th", "in_120th", "fec_candidate_ids", "senate_class",
    "individual_contribution_total_career", "aipac_pac_direct_career",
    "aipac_earmark_transmitted_career", "corporate_pac_career",
    "corporate_earmark_transmitted_career",
    "udp_ie_support_career", "udp_ie_opposing_opponents_career",
    "udp_ie_total_benefit_career",
    "cand_contrib_career", "cand_loans_career", "self_funding_career",
    "loan_repayments_career", "debts_owed_by_career", "debts_owed_to_career",
    "total_receipts_career", "total_disbursements_career",
    "transfers_from_auth_career", "transfers_to_auth_career",
    "cash_on_hand_career",
    "party_committees_career", "leadership_pacs_career", "labor_pacs_career",
    "trade_pacs_career", "membership_pacs_career", "cooperative_pacs_career",
    "other_unclassified_career", "other_committees_total_career",
    "party_committees_earmark_transmitted_career",
    "leadership_pacs_earmark_transmitted_career",
    "labor_pacs_earmark_transmitted_career",
    "trade_pacs_earmark_transmitted_career",
    "membership_pacs_earmark_transmitted_career",
    "cooperative_pacs_earmark_transmitted_career",
    "other_unclassified_earmark_transmitted_career",
    "all_ie_support_career", "all_ie_oppose_career", "all_ie_total_career",
    "total_accepted_career",
    "rank_total_accepted", "rank_individual", "rank_corporate_pac",
    "rank_aipac_direct", "rank_udp_support", "rank_udp_opposing_opponents",
    "rank_udp_total_benefit", "rank_self_funding", "rank_all_ie_support",
    "rank_all_ie_oppose", "rank_all_ie_total", "rank_other_committees_total",
    "corp_2026", "aipac_direct_2026", "individual_2026", "udp_support_2026",
    "udp_opp_credit_2026", "udp_benefit_2026", "dirty_2026", "dirty_career", "clean_2026",
    "unopposed_2026", "aipac_udp_flag_2026", "tier_balanced_2026",
    "tier_lenient_2026", "dep_share_2026", "self_funding_2026", "cand_loans_2026",
    "cand_contrib_2026", "total_receipts_2026", "total_disbursements_2026",
    "cash_on_hand_2026", "other_committees_total_2026",
    "all_ie_support_2026", "all_ie_oppose_2026", "all_ie_total_2026",
    "data_notes", "data_as_of",
]
PC_COLS = ["cycle", "candidate_id", "individual", "aipac_pac_direct",
           "aipac_earmark_transmitted", "corporate_pac",
           "corporate_earmark_transmitted"]
UPC_COLS = ["cycle", "candidate_id", "udp_ie_support", "attribution"]
SF_COLS = ["cycle", "candidate_id", "candidate_contributions",
           "candidate_loans", "loan_repayments", "debts_owed_by",
           "debts_owed_to", "total_receipts", "total_disbursements",
           "cash_on_hand", "transfers_from_auth", "transfers_to_auth",
           "coverage_end_date"]
OC_COLS = ["cycle", "candidate_id", "party_committees", "leadership_pacs",
           "labor_pacs", "trade_pacs", "membership_pacs", "cooperative_pacs",
           "other_unclassified", "earmark_transmitted", "winred_included"]
AIE_COLS = ["cycle", "candidate_id", "all_ie_support", "all_ie_oppose",
            "all_ie_total", "no_direction_amount"]
TC_COLS = ["committee_id", "committee_name", "support", "oppose", "total",
           "rows"]
# Nested lists sit at fixed positions after the scalars in each row array.
NESTED = ["per_cycle", "udp_per_cycle", "self_funding_per_cycle",
          "other_committees_per_cycle", "all_ie_per_cycle",
          "all_ie_top_committees"]
NESTED_COLS = {"per_cycle": PC_COLS, "udp_per_cycle": UPC_COLS,
               "self_funding_per_cycle": SF_COLS,
               "other_committees_per_cycle": OC_COLS,
               "all_ie_per_cycle": AIE_COLS,
               "all_ie_top_committees": TC_COLS}


def encode_row(r):
    """One dataset row -> compact array: scalars, then six nested lists."""
    out = [r.get(k) for k in SCALARS]
    for name in NESTED:
        cols = NESTED_COLS[name]
        vals = r.get(name) or []
        out.append([[e.get(k) for k in cols] for e in vals])
    return out


def build_opp_payload():
    """Race-phase UDP opposition credit per roster person, for the drill-down.

    From data/intermediate/opposition-computed.json (the race-level record):
    {person_key: [{cycle, office, state, district, phase, amount, opposed:
    [[name, amount], ...]}, ...]}. Non-roster credits are excluded (no
    drill-down row exists for them). Deterministic: entries sorted by race
    key, opposed names by amount descending.
    """
    opp = json.loads((ROOT / CFG["paths"]["opposition_computed"]).read_text())
    out = {}
    for race, pk, _name, amount, opposed in opp["credit_detail"]:
        if pk.startswith("__nonroster__"):
            continue
        cycle, office, state, district, ele_type = race
        out.setdefault(pk, []).append({
            "cycle": cycle, "office": office, "state": state,
            "district": district, "phase": ele_type,
            "amount": round(float(amount), 2),
            "opposed": sorted(
                [[n, round(float(a), 2)] for n, a in opposed.items()],
                key=lambda x: -x[1]),
        })
    for pk in out:
        out[pk].sort(key=lambda e: (e["cycle"], e["office"], e["state"],
                                    e["district"], e["phase"]))
    return out


def safe_json(obj):
    """Minified JSON safe to embed inside a <script> tag."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace(
        "</", "<\\/")


TEMPLATE_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Receipts — Who funds Congress</title>
<meta name="description" content="Every person in Congress and the money behind them, from FEC filings. Career totals, 2026 clean/dirty flags, self-funding, outside spending.">
<style>
:root{--ink:#1a1a1a;--muted:#5b5b5b;--line:#d8d8d8;--bg:#fff;--soft:#f4f4f2;--accent:#14532d;--accent-soft:#e8f3ec;--warn:#7c2d12;--chip:#eef2f7}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.45}
header{padding:20px 16px 12px;max-width:1120px;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 4px;letter-spacing:-.01em}
h1 a{color:inherit;text-decoration:none}
h1 a:hover{text-decoration:underline}
.sub{color:var(--muted);margin:0 0 12px;max-width:60ch}
.stamp{font-size:.9rem;background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:0 8px 8px 0;padding:8px 12px;margin:0 0 10px}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.stat{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:.9rem}
.stat b{display:block;font-size:1.15rem}
.cutoffs{font-size:.82rem;color:var(--muted);margin:6px 0 0}
.cutoffs b{color:var(--ink)}
.tabs{display:flex;gap:4px;flex-wrap:wrap;max-width:1120px;margin:0 auto;padding:0 16px}
.tabs button{border:1px solid var(--line);background:var(--bg);border-radius:8px 8px 0 0;border-bottom:none;padding:10px 14px;font-size:.95rem;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--accent);color:#fff;border-color:var(--accent)}
main{max-width:1120px;margin:0 auto;padding:16px}
section[hidden]{display:none}
#front-door[hidden],#explore-head[hidden],#tabs-nav[hidden],main[hidden],footer[hidden]{display:none}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.controls input[type="search"],.controls select{padding:9px 10px;font-size:1rem;border:1px solid var(--line);border-radius:8px;background:#fff;min-height:40px}
.controls input[type="search"]{flex:1 1 200px}
.controls label{font-size:.9rem;display:flex;align-items:center;gap:5px}
.btn{padding:9px 14px;font-size:.95rem;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer;min-height:40px}
.btn.ghost{background:#fff;color:var(--accent)}
.viewbtns{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.viewbtns button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 12px;font-size:.88rem;cursor:pointer}
.viewbtns button[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent);font-weight:600}
.totals{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}
.totals .t{background:var(--chip);border-radius:8px;padding:7px 11px;font-size:.88rem}
.totals .t b{display:block;font-size:1rem}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.9rem;min-width:640px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{position:sticky;top:0;background:var(--soft);cursor:pointer;user-select:none}
th.num,td.num{text-align:right;font-variant-numeric:tabular-nums}
tbody tr{cursor:pointer}
tbody tr:hover{background:#f7f9f7}
td.name{font-weight:600;white-space:normal;min-width:150px}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.8rem;font-weight:600}
.badge.clean{background:var(--accent-soft);color:var(--accent)}
.badge.dirty{background:#fdeede;color:var(--warn)}
.badge.unver{background:#f3f3f3;color:var(--muted)}
.badge.unopp{background:#fff3d6;color:#7a5b00}
.badge.below{background:#fef3c7;color:#92400e}
.badge.flag{background:#ede9fe;color:#5b21b6}
.tol-note{font-size:.88rem;color:var(--muted)}
.pchip{display:inline-block;min-width:1.35em;text-align:center;padding:0 6px;border-radius:999px;font-size:.8rem;font-weight:700;line-height:1.55;vertical-align:1px}
.pchip.d{background:#dbeafe;color:#1e40af}
.pchip.r{background:#fee2e2;color:#991b1b}
.pchip.o{background:#e5e7eb;color:#374151}
.ostatus{color:var(--muted);font-size:.85rem;white-space:nowrap}
footer{max-width:1120px;margin:24px auto;padding:0 16px 32px;color:var(--muted);font-size:.85rem}
.foot-totals{font-size:.9rem;color:var(--ink);margin-bottom:8px}
.detail{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;z-index:50}
.detail.open{display:block}
.detail .sheet{position:absolute;inset:auto 0 0 0;max-height:92vh;overflow-y:auto;background:#fff;border-radius:14px 14px 0 0;padding:20px 16px 32px;max-width:900px;margin:0 auto}
@media(min-width:700px){.detail .sheet{inset:5vh 0;max-height:90vh;border-radius:14px}}
.detail h2{margin:0 0 2px}
.detail .meta{color:var(--muted);margin:0 0 14px}
.detail h3{margin:18px 0 6px;font-size:1.05rem}
.detail table{min-width:0}
.detail th{cursor:default}
.detail .close{float:right}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;font-size:.92rem}
.kv div{display:flex;justify-content:space-between;border-bottom:1px solid #eee;padding:4px 0}
.kv span:first-child{color:var(--muted)}
.notes{background:var(--soft);border-radius:8px;padding:10px 12px;font-size:.9rem}
.leader{list-style:none;margin:0 0 20px;padding:0}
.leader li{display:flex;justify-content:space-between;gap:10px;padding:8px 4px;border-bottom:1px solid var(--line);font-size:.95rem}
.leader li b{font-weight:600}
.leader .amt{font-variant-numeric:tabular-nums;white-space:nowrap}
.leader .who{color:var(--muted);font-size:.85rem}
h2.sec{font-size:1.25rem;margin:4px 0 10px}
.method h3{margin:16px 0 4px}
.method p,.method li{font-size:.95rem}
.method ul{padding-left:20px}
.method table{min-width:0}
.method th{cursor:default}
.callout{background:var(--accent-soft);border-left:4px solid var(--accent);padding:10px 14px;border-radius:0 8px 8px 0;margin:12px 0}
.story{background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:0 8px 8px 0;padding:12px 14px;font-size:1.05rem;margin:0 0 10px}
.frontdoor{max-width:680px;margin:0 auto;padding:4px 16px 40px}
.frontdoor h2{font-size:1.05rem;letter-spacing:.02em;margin:32px 0 6px}
.frontdoor h2:first-child{margin-top:12px}
/* Scrollytelling chapters: one chapter per beat of the story, revealed
   as the reader scrolls (see initReveals). Chapters are visible by
   default; the hidden-before-reveal state lives under html.js only,
   so no-JS (or a failed observer) still shows every chapter. */
.frontdoor .chapter{margin:0 0 48px}
.frontdoor .chapter:first-child{margin-top:8px}
html.js .chapter{opacity:0;transform:translateY(16px);transition:opacity .65s ease,transform .65s ease}
html.js .chapter.in{opacity:1;transform:none}
html.js .chapter .dirtiest li{opacity:0;transform:translateY(8px);transition:opacity .5s ease,transform .5s ease}
html.js .chapter.in .dirtiest li{opacity:1;transform:none}
html.js .chapter .dot{opacity:0;transition:opacity .4s ease}
html.js .chapter.in .dot{opacity:1}
html.js .chapter .tile{opacity:0;transition:opacity .45s ease}
html.js .chapter.in .tile{opacity:1}
@media (prefers-reduced-motion: reduce){
html.js .chapter,html.js .chapter .dirtiest li,html.js .chapter .dot,html.js .chapter .tile{opacity:1 !important;transform:none !important;transition:none !important}
}
@media(max-width:560px){.hook{font-size:1.55rem}.big-number{font-size:1.8rem}}
.comp{display:flex;flex-direction:column;gap:18px}
.comp figure{margin:0;min-width:0}
.comp svg{width:100%;height:auto;display:block}
.comp figcaption{text-align:center;font-weight:600;margin-top:2px}
.legend{display:flex;flex-wrap:wrap;gap:4px 12px;justify-content:center;font-size:.85rem;color:var(--muted);margin:6px 0 0}
.legend .lg{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.legend .lg i{width:11px;height:11px;border-radius:50%;display:inline-block;flex:none}
.delegates{color:var(--muted);font-size:.85rem;text-align:center;margin:8px 0 0}
.hook{font-size:1.85rem;line-height:1.35;margin:8px 0 4px;font-weight:600}
.big-number{font-size:2.1rem;font-weight:700;margin:2px 0 0;line-height:1.2}
.big-label{color:var(--muted);margin:2px 0 10px}
.dirtiest{list-style:none;margin:6px 0 0;padding:0}
.dirtiest li{border-bottom:1px solid #ececec}
.dirty-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;width:100%;text-align:left;background:none;border:none;padding:12px 2px;font:inherit;cursor:pointer;color:inherit}
.dirty-row:hover{background:#f7f9f7}
.dirty-row .nm{font-weight:600}
.dirty-row .pl{color:var(--muted);font-size:.88rem;display:block}
.dirty-row .amt{font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:600}
.fine{color:var(--muted);font-size:.88rem;margin:10px 0 0}
.fresh{color:var(--muted);font-size:.88rem;margin:28px 0 12px}
#explore-btn{width:100%}
.story b{font-size:1.2rem}
.linklike{background:none;border:none;color:var(--accent);text-decoration:underline;cursor:pointer;font:inherit;padding:0}
.finder{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.finder label{font-weight:600;font-size:.95rem}
.finder select{padding:9px 10px;font-size:1rem;border:1px solid var(--line);border-radius:8px;background:#fff;min-height:40px;flex:1 1 160px}
.finder .person-btn{white-space:normal;text-align:left}
@media(max-width:560px){.finder select{flex:1 1 100%}.finder label{flex:1 1 100%}}
</style>
</head>
<body>
<header>
<h1 tabindex="-1"><a href="#" id="home-link">The Receipts</a></h1>
<p class="sub">Every person in Congress and the money behind them — from FEC filings, not press releases. Career totals, 2026 clean/dirty flags, self-funding, and outside spending.</p>
<div id="explore-head">
<p class="stamp">%%STAMP%%</p>
<div class="stats" id="stats"></div>
<p class="cutoffs"><b>2026 is partial.</b> Committee money (corporate PAC, AIPAC, other committees) through <b>Sep 30, 2026</b>; individual / self-funding / topline through <b>Oct 14, 2026</b>; independent expenditures through <b>Oct 31, 2026</b>. Post-general reports are due Dec 3, 2026; year-end reports Jan 31, 2027.</p>
<div class="controls" id="tolerance-controls">
<label for="f-tolerance">Corporate PAC tolerance:</label>
<select id="f-tolerance" aria-label="Corporate PAC tolerance preset"><option value="strict">Strict — any dirty dollar</option><option value="balanced" selected>Balanced — over $100k and 5% of receipts</option><option value="lenient">Lenient — over $250k and 10% of receipts</option></select>
<span class="tol-note" id="tolerance-note"></span>
</div>
</div>
</header>
<nav class="tabs" id="tabs-nav" role="tablist" aria-label="Views" tabindex="-1">
<button role="tab" aria-selected="true" data-tab="tracker">Tracker</button>
<button role="tab" aria-selected="false" data-tab="leaders">Leaderboards</button>
<button role="tab" aria-selected="false" data-tab="clean">Clean money</button>
<button role="tab" aria-selected="false" data-tab="breakdown">Party breakdown</button>
<button role="tab" aria-selected="false" data-tab="targets">2026 primary targets</button>
<button role="tab" aria-selected="false" data-tab="targets28">2028 primary targets</button>
<button role="tab" aria-selected="false" data-tab="method">Methodology</button>
</nav>
<main id="main">
"""
TEMPLATE_BODY = """
<section id="tab-tracker" tabindex="-1">
<div class="controls">
<input type="search" id="q" placeholder="Search by name…" aria-label="Search by name">
<select id="f-congress" aria-label="Congress"><option value="all">Everyone</option><option value="119">119th only</option><option value="120">120th only</option><option value="both">In both</option></select>
<select id="f-chamber" aria-label="Chamber"><option value="all">House + Senate</option><option value="House">House</option><option value="Senate">Senate</option></select>
<select id="f-party" aria-label="Party"><option value="all">All parties</option><option value="Democrat">Democrat</option><option value="Republican">Republican</option><option value="Independent">Independent</option><option value="PPD">PPD</option></select>
<select id="f-state" aria-label="State"><option value="all">All states</option></select>
<label><input type="checkbox" id="f-leader"> Leadership only</label>
<label><input type="checkbox" id="f-clean"> Not dirty in 2026 only</label>
<button class="btn" id="csv-btn" type="button">Download CSV</button>
</div>
<div class="viewbtns" id="viewbtns" role="group" aria-label="Column views"></div>
<div class="totals" id="totals"></div>
<div class="tablewrap"><table id="main-table"><thead></thead><tbody></tbody></table></div>
<p id="showing" style="color:var(--muted);font-size:.88rem"></p>
</section>

<section id="tab-leaders" hidden tabindex="-1">
<h2 class="sec">Leaderboards</h2>
<p style="color:var(--muted)">Dirty money leads: the first two lists are the dirtiness measure — corporate PAC + AIPAC PAC direct + UDP benefit, in 2026 and career. Individual contributions are not dirty money. “Total accepted” (individual + corporate PAC + AIPAC direct) measures fundraising scale, not dirtiness. Outside spending is never part of total accepted — it is money spent <i>about</i> a race, never given to the campaign.</p>
<div id="leaders"></div>
</section>

<section id="tab-clean" hidden tabindex="-1">
<h2 class="sec">Clean money</h2>
<div id="clean-stats"></div>
<div class="callout" id="clean-callout"></div>
<div class="tablewrap"><table id="clean-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-breakdown" hidden tabindex="-1">
<h2 class="sec">Party-by-chamber breakdown — 120th Congress</h2>
<p style="color:var(--muted)" id="breakdown-intro"></p>
<div class="tablewrap"><table id="breakdown-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-targets" hidden tabindex="-1">
<h2 class="sec">2026 primary targets — House Democrats, by dirty money in 2026</h2>
<p style="color:var(--muted)">192 House Democrats in the incoming 120th took dirty money in 2026 (corporate PAC + AIPAC direct + UDP benefit). Dirty money is money from sources other than individual contributors; individual contributions are not dirty money. 2026 figures are partial (see cutoffs above).</p>
<div class="tablewrap"><table id="targets-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-targets28" hidden tabindex="-1">
<h2 class="sec">2028 primary targets — the dirtiest Democrats to watch</h2>
<p style="color:var(--muted)" id="targets28-intro"></p>
<h3>House — every seat is up in 2028</h3>
<div class="tablewrap"><table id="targets28-house-table"><thead></thead><tbody></tbody></table></div>
<h3>Senate — Class 3 seats, next up in 2028</h3>
<p style="color:var(--muted)">Class comes from the Senate-term class field in the legislators data — the same derivation that puts every 120th senator in Class 1, 2, or 3. See Methodology §14.</p>
<div class="tablewrap"><table id="targets28-senate-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-method" class="method" hidden tabindex="-1">
<h2 class="sec">Methodology</h2>
<p style="color:var(--muted)">Condensed from <a href="https://github.com/craigSochocki/the-receipts/blob/master/methodology.md">methodology.md</a> in the repo, which is the authoritative version. If this page and methodology.md ever disagree on a number, methodology.md wins.</p>
%%METHOD_HTML%%
</section>
</main>
<div id="front-door" class="frontdoor">
<section class="chapter" data-chapter="hook" aria-label="The dirtiest fact">
<p class="hook" id="dirtiest-headline"></p>
</section>
<section class="chapter" data-chapter="dirtiest" aria-label="Dirtiest in 2026">
<h2>Dirtiest in 2026</h2>
<ol class="dirtiest" id="dirtiest-list"></ol>
<p class="fine">Dirty money in 2026 is corporate PAC + AIPAC PAC direct + UDP benefit — money from sources other than individual contributors. 2026 is partial; see the methodology for the coverage cutoffs.</p>
</section>
<section class="chapter" data-chapter="dirty-definition" aria-label="What counts as dirty">
<h2>What counts as dirty</h2>
<div id="dirty-explainer"></div>
</section>
<section class="chapter" data-chapter="clean" aria-label="Clean money">
<h2>Clean money</h2>
<div class="story" id="landing-story"></div>
</section>
<section class="chapter" data-chapter="chamber" aria-label="Composition of Congress">
<h2>Who sits in the 120th</h2>
<div id="composition"></div>
</section>
<section class="chapter" data-chapter="finder" aria-label="Find your member">
<h2>Find your member</h2>
<div class="finder" id="finder">
<label for="find-state">Your state</label>
<select id="find-state" aria-label="Your state"><option value="">Choose your state…</option></select>
<select id="find-district" aria-label="District" disabled><option value="">Choose a district…</option></select>
<span id="find-person"></span>
</div>
</section>
<section class="chapter" data-chapter="data" aria-label="The data">
<p class="fresh" id="fresh-line">%%FRESH_LINE%%</p>
<p>Looking ahead to 2028: the dirtiest Democrats to watch for 2028 primaries. <button class="btn" id="targets28-btn" type="button">2028 primary targets</button></p>
<p><button class="btn" id="explore-btn" type="button">Explore the full data</button></p>
</section>
</div>
<div class="detail" id="detail" role="dialog" aria-modal="true"><div class="sheet" id="detail-sheet"></div></div>
<footer>
<p class="foot-totals" id="foot-totals"></p>
<p>Data as of %%DATA_AS_OF%%. Source: FEC bulk filings (weball, pas2, committee master, independent-expenditure files) — see Methodology. Dataset md5: <code>%%DATASET_MD5%%</code>. Generated %%GENERATED_AT%% from <code>congress-money-tracker.json</code> by <code>src/site/build_site.py</code>. Live at https://craigsochocki.github.io/the-receipts/.</p>
</footer>
<script id="receipts-cols" type="application/json">%%COLS_JSON%%</script>
<script id="receipts-data" type="application/json">%%DATA_JSON%%</script>
<script id="opp-data" type="application/json">%%OPP_JSON%%</script>
<script>
"use strict";
/* ---- decode ---- */
const COLS = JSON.parse(document.getElementById('receipts-cols').textContent);
const RAW = JSON.parse(document.getElementById('receipts-data').textContent);
const OPP = JSON.parse(document.getElementById('opp-data').textContent);
const PHASE_LABEL = {P:'Primary', G:'General', O:'Other'};
const NS = COLS.scalars.length;
function mkobj(cols, arr){ const o={}; cols.forEach((k,i)=>{ o[k]=arr[i]; }); return o; }
const PEOPLE = RAW.map(a=>{
  const o={}; COLS.scalars.forEach((k,i)=>{ o[k]=a[i]; });
  o.per_cycle=(a[NS]||[]).map(e=>mkobj(COLS.pc,e));
  o.udp_per_cycle=(a[NS+1]||[]).map(e=>mkobj(COLS.upc,e));
  o.self_funding_per_cycle=(a[NS+2]||[]).map(e=>mkobj(COLS.sf,e));
  o.other_committees_per_cycle=(a[NS+3]||[]).map(e=>mkobj(COLS.oc,e));
  o.all_ie_per_cycle=(a[NS+4]||[]).map(e=>mkobj(COLS.aie,e));
  o.all_ie_top_committees=(a[NS+5]||[]).map(e=>mkobj(COLS.tc,e));
  return o;
});
const BY_KEY = {}; PEOPLE.forEach(p=>{ BY_KEY[p.person_key]=p; });

/* ---- formatting ---- */
function num(v){ return (typeof v==='number' && isFinite(v)) ? v : null; }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmtMoney(v){
  if(v===null||v===undefined) return '—';
  if(v==='unknown') return 'unknown';
  if(typeof v!=='number') return String(v);
  const neg=v<0, a=Math.abs(v);
  return (neg?'−$':'$')+a.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
}
function fmtCompact(v){
  if(v===null||v===undefined) return '—';
  if(v==='unknown') return 'unknown';
  if(typeof v!=='number') return String(v);
  const neg=v<0, a=Math.abs(v); let s;
  if(a>=1e9) s='$'+(a/1e9).toFixed(2)+'B';
  else if(a>=1e6) s='$'+(a/1e6).toFixed(2)+'M';
  else if(a>=1e3) s='$'+(a/1e3).toFixed(1)+'K';
  else s='$'+a.toFixed(0);
  return (neg?'−':'')+s;
}
function fmtPct(v){ if(v===null||v===undefined) return '—'; return (v*100).toFixed(1)+'%'; }
function fmtRank(v){ return (v===null||v===undefined)?'—':'#'+v; }
/* ---- corporate PAC tolerance presets (methodology §14) ----
   Strict is clean_2026 itself (any net dirty dollar above $0 is
   dirty); Balanced / Lenient read the stored tier columns. The
   AIPAC/UDP flag is not tolerance-based: any AIPAC direct or UDP
   benefit dollar flags the member under every preset, and a flagged
   member is dirty under every preset. The middle tier is never
   called clean, and its dollar amount (corp_2026) is always shown.
   Default is Balanced. */
const PRESETS = {
  strict:{label:'Strict',
    def:'Strict: any net dirty dollar above $0 is dirty.',
    short:'any dirty dollar counts'},
  balanced:{label:'Balanced',
    def:'Balanced (default): corporate PAC counts as dirty only over $100,000 and over 5% of 2026 receipts; any AIPAC direct or UDP benefit dollar always counts.',
    short:'corporate PAC over $100k and over 5% of receipts'},
  lenient:{label:'Lenient',
    def:'Lenient: corporate PAC counts as dirty only over $250,000 and over 10% of 2026 receipts; any AIPAC direct or UDP benefit dollar always counts.',
    short:'corporate PAC over $250k and over 10% of receipts'}
};
function tierOf(p){
  if(state.preset==='strict')
    return p.clean_2026===true ? 'clean' : (p.clean_2026===null ? null : 'dirty');
  return state.preset==='lenient' ? p.tier_lenient_2026 : p.tier_balanced_2026;
}
function isNotDirty(p){ const t=tierOf(p); return t==='clean'||t==='below_threshold'; }
function flagBadge(p){
  if(p.aipac_udp_flag_2026!==true) return '';
  return ' <span class="badge flag" title="Took AIPAC PAC direct money or UDP benefit in 2026 — flagged under every tolerance preset">AIPAC/UDP</span>';
}
function fmtTierBadge(p){
  const t = tierOf(p);
  if(t===null)
    return p.unopposed_2026===true ? '<span class="badge unopp">Unopposed</span>'
      : '<span class="badge unver">Unverified</span>';
  if(t==='clean') return '<span class="badge clean">Clean</span>';
  if(t==='below_threshold')
    return '<span class="badge below">Below threshold · '+fmtMoney(p.corp_2026)+'</span>';
  return '<span class="badge dirty">Dirty</span>'+flagBadge(p);
}

/* ---- derived fields ---- */
function place(p){
  const d = p.district_120!==''&&p.district_120!=null ? p.district_120 : p.district_119;
  if(p.chamber_120==='Senate'||p.chamber_119==='Senate') return p.state+' · Senate';
  return p.state+(d!==''&&d!=null ? '-'+d : '');
}
function party(p){ return p.party_120||p.party_119||'—'; }
/* ---- person marks: party chip + election outcome ----
   Party: prefer party_120, else party_119; no party known -> no chip
   (never invented). Democrat D blue, Republican R red, Independent I
   gray; any other stored label (e.g. PPD) gets a gray chip showing the
   stored label. Always letter + color, never color alone.
   Outcome: in_120th 'yes' -> Won, 'unknown' -> Uncalled, 'no' ->
   Not returning. "Not returning" is deliberately NOT "Lost": the
   dataset cannot separate lost re-election from retired / didn't run /
   left early; that split is Phase 2 outcomes work. */
function partyName(p){ return p.party_120||p.party_119||''; }
function partyChip(p){
  const name = partyName(p);
  if(!name) return '';
  const map = {Democrat:['D','d'], Republican:['R','r'], Independent:['I','o']};
  const m = map[name] || [name, 'o'];
  return '<span class="pchip '+m[1]+'" title="'+esc(name)+'">'+esc(m[0])+'</span>';
}
function outcomeLabel(p){
  if(p.in_120th==='yes') return 'Won';
  if(p.in_120th==='unknown') return 'Uncalled';
  return 'Not returning';
}
function chamber(p){ return p.chamber_120||p.chamber_119||'—'; }
function congressLabel(p){
  if(p.in_119th==='yes'&&p.in_120th==='yes') return '119th + 120th';
  if(p.in_120th==='yes') return '120th';
  if(p.in_119th==='yes') return '119th';
  return 'TBD';
}
function isCareerClean(p){
  return num(p.corporate_pac_career)===0 && num(p.aipac_pac_direct_career)===0
    && num(p.udp_ie_support_career)===0 && num(p.udp_ie_opposing_opponents_career)===0;
}

/* ---- column views ---- */
const VIEWS = {
  core:{label:'Core money',cols:[
    {k:'full_name',label:'Name',type:'name'},
    {k:'place',label:'State / Dist.',type:'place'},
    {k:'party',label:'Party',type:'party'},
    {k:'outcome',label:'Outcome',type:'outcome'},
    {k:'chamber',label:'Chamber',type:'chamber'},
    {k:'congress',label:'Congress',type:'congress'},
    {k:'individual_contribution_total_career',label:'Individual (career)',type:'money'},
    {k:'corporate_pac_career',label:'Corp PAC (career)',type:'money'},
    {k:'aipac_pac_direct_career',label:'AIPAC direct (career)',type:'money'},
    {k:'total_accepted_career',label:'Total accepted',type:'money'},
    {k:'rank_total_accepted',label:'Rank',type:'rank'},
    {k:'dirty_2026',label:'Dirty 2026',type:'money'},
    {k:'clean_2026',label:'Tier 2026',type:'clean'}]},
  y2026:{label:'2026 cycle',cols:[
    {k:'full_name',label:'Name',type:'name'},
    {k:'place',label:'State / Dist.',type:'place'},
    {k:'party',label:'Party',type:'party'},
    {k:'individual_2026',label:'Individual 2026',type:'money'},
    {k:'corp_2026',label:'Corp PAC 2026',type:'money'},
    {k:'aipac_direct_2026',label:'AIPAC 2026',type:'money'},
    {k:'udp_support_2026',label:'UDP support 2026',type:'money'},
    {k:'udp_benefit_2026',label:'UDP benefit 2026',type:'money'},
    {k:'dirty_2026',label:'Dirty 2026',type:'money'},
    {k:'dep_share_2026',label:'Dep. share 2026',type:'pct'},
    {k:'clean_2026',label:'Tier 2026',type:'clean'}]},
  selffund:{label:'Self-funding & topline',cols:[
    {k:'full_name',label:'Name',type:'name'},
    {k:'place',label:'State / Dist.',type:'place'},
    {k:'self_funding_career',label:'Self-funding (career)',type:'money'},
    {k:'cand_loans_career',label:'Candidate loans',type:'money'},
    {k:'cand_contrib_career',label:'Candidate contrib.',type:'money'},
    {k:'loan_repayments_career',label:'Loan repayments',type:'money'},
    {k:'total_receipts_career',label:'Total receipts',type:'money'},
    {k:'total_disbursements_career',label:'Total disbursements',type:'money'},
    {k:'cash_on_hand_career',label:'Cash on hand',type:'money'},
    {k:'debts_owed_by_career',label:'Debts owed',type:'money'},
    {k:'rank_self_funding',label:'Rank',type:'rank'}]},
  committees:{label:'Other committees',cols:[
    {k:'full_name',label:'Name',type:'name'},
    {k:'place',label:'State / Dist.',type:'place'},
    {k:'party_committees_career',label:'Party',type:'money'},
    {k:'leadership_pacs_career',label:'Leadership PACs',type:'money'},
    {k:'labor_pacs_career',label:'Labor',type:'money'},
    {k:'trade_pacs_career',label:'Trade',type:'money'},
    {k:'membership_pacs_career',label:'Membership',type:'money'},
    {k:'cooperative_pacs_career',label:'Cooperative',type:'money'},
    {k:'other_unclassified_career',label:'Other / unclass.',type:'money'},
    {k:'other_committees_total_career',label:'Other committees total',type:'money'},
    {k:'rank_other_committees_total',label:'Rank',type:'rank'}]},
  outside:{label:'Outside spending',cols:[
    {k:'full_name',label:'Name',type:'name'},
    {k:'place',label:'State / Dist.',type:'place'},
    {k:'udp_ie_support_career',label:'UDP support',type:'money'},
    {k:'udp_ie_opposing_opponents_career',label:'UDP opp. credit',type:'money'},
    {k:'udp_ie_total_benefit_career',label:'UDP total benefit',type:'money'},
    {k:'all_ie_support_career',label:'All IE support',type:'money'},
    {k:'all_ie_oppose_career',label:'All IE oppose',type:'money'},
    {k:'all_ie_total_career',label:'All IE total',type:'money'},
    {k:'rank_all_ie_total',label:'Rank',type:'rank'}]}
};
const SORTABLE = new Set(['individual_contribution_total_career','corporate_pac_career','aipac_pac_direct_career','total_accepted_career','rank_total_accepted','dirty_2026','individual_2026','corp_2026','aipac_direct_2026','udp_support_2026','udp_benefit_2026','dep_share_2026','self_funding_career','cand_loans_career','cand_contrib_career','loan_repayments_career','total_receipts_career','total_disbursements_career','cash_on_hand_career','debts_owed_by_career','rank_self_funding','party_committees_career','leadership_pacs_career','labor_pacs_career','trade_pacs_career','membership_pacs_career','cooperative_pacs_career','other_unclassified_career','other_committees_total_career','rank_other_committees_total','udp_ie_support_career','udp_ie_opposing_opponents_career','udp_ie_total_benefit_career','all_ie_support_career','all_ie_oppose_career','all_ie_total_career','rank_all_ie_total','full_name']);

/* ---- state ---- */
const state = {q:'', congress:'all', chamber:'all', party:'all', state:'all',
  leadership:false, clean:false, view:'core', preset:'balanced',
  sortKey:'dirty_2026', sortDir:'desc', tab:'tracker', mode:'front', rendered:{}};

function getVal(p, key){
  if(key==='place') return place(p);
  if(key==='party') return party(p);
  if(key==='chamber') return chamber(p);
  if(key==='congress') return congressLabel(p);
  return p[key];
}
function cmpVal(a, b, dir){
  const an = num(a), bn = num(b);
  if(an===null && bn===null) return 0;
  if(an===null) return 1;   // null / unknown always sorts last
  if(bn===null) return -1;
  return dir==='asc' ? an-bn : bn-an;
}
function applyFilters(){
  const q = state.q.trim().toLowerCase();
  return PEOPLE.filter(p=>{
    if(q && !p.full_name.toLowerCase().includes(q)) return false;
    if(state.congress==='119' && p.in_119th!=='yes') return false;
    if(state.congress==='120' && p.in_120th!=='yes') return false;
    if(state.congress==='both' && !(p.in_119th==='yes'&&p.in_120th==='yes')) return false;
    if(state.chamber!=='all' && !(p.chamber_119===state.chamber||p.chamber_120===state.chamber)) return false;
    if(state.party!=='all' && !(p.party_119===state.party||p.party_120===state.party)) return false;
    if(state.state!=='all' && p.state!==state.state) return false;
    if(state.leadership && !p.leadership_119) return false;
    if(state.clean && !isNotDirty(p)) return false;
    return true;
  });
}
function sortRows(rows){
  const k = state.sortKey, dir = state.sortDir;
  return rows.slice().sort((a,b)=>{
    const av = getVal(a,k), bv = getVal(b,k);
    if(typeof av==='string' || typeof bv==='string'){
      const as = String(av==null?'':av), bs = String(bv==null?'':bv);
      return dir==='asc' ? as.localeCompare(bs) : bs.localeCompare(as);
    }
    const c = cmpVal(av, bv, dir);
    return c!==0 ? c : a.full_name.localeCompare(b.full_name);
  });
}
function cellHtml(p, col){
  const v = getVal(p, col.k);
  switch(col.type){
    case 'name': return esc(v);
    case 'party': return partyChip(p) || '—';
    case 'outcome': return outcomeLabel(p);
    case 'money': {
      const t = fmtMoney(v);
      return '<span title="'+esc(t)+'">'+fmtCompact(v)+'</span>';
    }
    case 'pct': return fmtPct(v);
    case 'rank': return fmtRank(v);
    case 'clean': return fmtTierBadge(p);
    default: return esc(v==null||v===''?'—':v);
  }
}
function renderTable(){
  const view = VIEWS[state.view];
  const thead = document.querySelector('#main-table thead');
  const tbody = document.querySelector('#main-table tbody');
  thead.innerHTML = '<tr>'+view.cols.map(c=>{
    const arrow = state.sortKey===c.k ? (state.sortDir==='asc'?' ▲':' ▼') : '';
    const sortable = SORTABLE.has(c.k) ? ' data-sort="'+c.k+'"' : '';
    const cls = (c.type==='money'||c.type==='pct'||c.type==='rank') ? ' class="num"' : '';
    return '<th'+cls+sortable+'>'+esc(c.label)+arrow+'</th>';
  }).join('')+'</tr>';
  thead.querySelectorAll('th[data-sort]').forEach(th=>{
    th.addEventListener('click', ()=>{
      const k = th.getAttribute('data-sort');
      if(state.sortKey===k) state.sortDir = state.sortDir==='asc'?'desc':'asc';
      else { state.sortKey=k; state.sortDir='desc'; }
      renderTable();
    });
  });
  const rows = sortRows(applyFilters());
  tbody.innerHTML = rows.map(p=>'<tr data-key="'+p.person_key+'">'+view.cols.map(c=>{
    const cls = c.type==='name' ? ' class="name"' : ((c.type==='money'||c.type==='pct'||c.type==='rank') ? ' class="num"' : '');
    return '<td'+cls+'>'+cellHtml(p,c)+'</td>';
  }).join('')+'</tr>').join('');
  tbody.querySelectorAll('tr').forEach(tr=>{
    tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key')));
  });
  // totals strip + footer for the filtered set
  const sum = k => rows.reduce((s,p)=>s+(num(p[k])||0),0);
  const t = [
    ['People', rows.length],
    ['Individual', fmtCompact(sum('individual_contribution_total_career'))],
    ['Corp PAC', fmtCompact(sum('corporate_pac_career'))],
    ['AIPAC direct', fmtCompact(sum('aipac_pac_direct_career'))],
    ['Total accepted', fmtCompact(sum('total_accepted_career'))],
    ['UDP benefit', fmtCompact(sum('udp_ie_total_benefit_career'))],
    ['Self-funding', fmtCompact(sum('self_funding_career'))],
    ['All IE total', fmtCompact(sum('all_ie_total_career'))]
  ];
  document.getElementById('totals').innerHTML = t.map(x=>'<div class="t">'+esc(x[0])+'<b>'+esc(x[1])+'</b></div>').join('');
  document.getElementById('showing').textContent = 'Showing '+rows.length+' of '+PEOPLE.length+' people. Click a row for the full breakdown.';
  document.getElementById('foot-totals').textContent =
    'Filtered set totals — individual '+fmtMoney(sum('individual_contribution_total_career'))
    +' · corporate PAC '+fmtMoney(sum('corporate_pac_career'))
    +' · AIPAC direct '+fmtMoney(sum('aipac_pac_direct_career'))
    +' · total accepted '+fmtMoney(sum('total_accepted_career'))
    +' · UDP benefit '+fmtMoney(sum('udp_ie_total_benefit_career'))
    +' · self-funding '+fmtMoney(sum('self_funding_career'))
    +' · all IE total '+fmtMoney(sum('all_ie_total_career'))+'.';
}
function renderViewBtns(){
  document.getElementById('viewbtns').innerHTML = Object.entries(VIEWS).map(([k,v])=>
    '<button type="button" data-view="'+k+'" aria-pressed="'+(state.view===k)+'">'+esc(v.label)+'</button>').join('');
  document.querySelectorAll('#viewbtns button').forEach(b=>{
    b.addEventListener('click', ()=>{ state.view=b.getAttribute('data-view'); renderViewBtns(); renderTable(); });
  });
}
/* ---- front door: dirtiest in 2026, computed from the data ----
   The top five and the #1-vs-next-four comparison are computed from
   PEOPLE at render time — no figure is ever typed into this template,
   so a data change cannot strand a stale number on the landing. The
   comparison line appears only if the computed comparison holds (#1
   exceeds the next four combined). Each row opens the drill-down. */
function renderDirtiest(){
  const rows = PEOPLE.filter(p=>num(p.dirty_2026)>0)
    .sort((a,b)=>num(b.dirty_2026)-num(a.dirty_2026)).slice(0,5);
  const top = rows[0];
  const next4 = rows.slice(1).reduce((s,p)=>s+num(p.dirty_2026),0);
  let h = '<b>'+esc(top.full_name)+'</b> took <b><span class="countup" data-value="'+num(top.dirty_2026)+'" data-format="compact">'+fmtCompact(top.dirty_2026)+'</span></b> in dirty money in 2026 — the most of anyone in Congress.';
  if(num(top.dirty_2026) > next4){
    h += ' That is more than the next four combined (<span class="countup" data-value="'+next4+'" data-format="compact">'+fmtCompact(next4)+'</span>) — about '+(num(top.dirty_2026)/next4).toFixed(2)+'× as much.';
  }
  document.getElementById('dirtiest-headline').innerHTML = h;
  document.getElementById('dirtiest-list').innerHTML = rows.map((p,i)=>
    '<li style="transition-delay:'+(i*90)+'ms"><button type="button" class="dirty-row" data-key="'+p.person_key+'">'
    + '<span><span class="nm">'+(i+1)+'. '+esc(p.full_name)+'</span>'
    + '<span class="pl">'+partyChip(p)+' '+esc(place(p))+' · '+outcomeLabel(p)+'</span></span>'
    + '<span class="amt">'+fmtMoney(p.dirty_2026)+'</span></button></li>').join('');
  document.querySelectorAll('#dirtiest-list .dirty-row').forEach(b=>{
    b.addEventListener('click', ()=>openDetail(b.getAttribute('data-key')));
  });
}
/* ---- front door: the clean story, computed from the data ----
   The counts below are computed from PEOPLE at render time under
   the current tolerance preset — no figure is ever typed into this
   template, so a data change cannot strand a stale number on the
   landing. The count is always shown with its preset definition
   (methodology §14: a count is never shown without its definition);
   the default preset is Balanced. */
function renderCleanStory(){
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const nd = incoming.filter(isNotDirty);
  const hND = nd.filter(p=>p.chamber_120==='House').length;
  const sND = nd.filter(p=>p.chamber_120==='Senate').length;
  const preset = PRESETS[state.preset];
  document.getElementById('landing-story').innerHTML =
    '<b><span class="countup" data-value="'+nd.length+'" data-format="int">'+nd.length+'</span> of <span class="countup" data-value="'+incoming.length+'" data-format="int">'+incoming.length+'</span></b> took no dirty money in 2026 — '
    + hND+' House + '+sND+' Senate. '
    + preset.label+' tolerance: '+preset.short+'. Any AIPAC direct or UDP benefit dollar always counts. '
    + '<button type="button" class="linklike" id="story-clean-link">See the list</button>';
  document.getElementById('story-clean-link').addEventListener('click', ()=>showTab('clean'));
}
/* ---- front door: what counts as dirty, computed from the data ----
   The career dirty total and its three components are summed from
   PEOPLE at render time — no figure is ever typed into this template.
   The big number counts up on reveal (see runCountUp). */
function renderDirtyExplainer(){
  const sum = k => PEOPLE.reduce((s,p)=>s+(num(p[k])||0),0);
  const total = sum('dirty_career');
  const corp = sum('corporate_pac_career');
  const aipac = sum('aipac_pac_direct_career');
  const udp = sum('udp_ie_total_benefit_career');
  document.getElementById('dirty-explainer').innerHTML =
    '<p class="big-number"><span class="countup" data-value="'+total+'" data-format="compact">'+fmtCompact(total)+'</span></p>'
    + '<p class="big-label">of dirty money taken over a career by everyone in the tracker</p>'
    + '<p>Dirty money is money from sources other than individual contributors: <b>corporate PAC contributions ('+fmtCompact(corp)+')</b>, <b>AIPAC PAC direct ('+fmtCompact(aipac)+')</b>, and <b>UDP benefit — outside spending for the candidate, or against their opponent ('+fmtCompact(udp)+')</b>. Individual contributions are <b>not</b> dirty money.</p>';
}
/* ---- front door: House waffle + Senate state tiles ----
   House: a 15-row x 29-column waffle grid (435 dots), filled one
   column at a time from left to right, grouped Clean D, Dirty D,
   Dirty R, Clean R, then Unopposed / Unverified / Uncalled at the
   far right. Senate: one tile per state, each half colored for its
   senator. Both computed from PEOPLE at render time — no count is
   ever typed into this template.
   Encoding (see methodology §17): clean = solid party color
   (Democrat blue, Republican red, Independent/other gray); dirty =
   black with the party color inside — a single centered dot on the
   House waffle, a dotted pattern on the Senate tiles. Unopposed and
   unverified are gray hollow rings (not judged); uncalled is a
   dashed gray ring / empty half (no named member yet).
   House plots the 435 voting seats; the 6 non-voting delegates are
   listed under the chart, not plotted. */
const PARTY_DOT_COLOR = {Democrat:'#1e40af', Republican:'#991b1b'};
function dotColor(name){ return PARTY_DOT_COLOR[name] || '#374151'; }
function seatLetter(p){
  const n = partyName(p);
  return {Democrat:'D', Republican:'R', Independent:'I'}[n] || n || '?';
}
function seatStatus(p){
  if(p.clean_2026===true) return 'clean';
  if(p.clean_2026===false) return 'dirty';
  return p.unopposed_2026===true ? 'unopposed' : 'unverified';
}
function compositionSeats(chamber){
  // Named voting members of the incoming 120th in this chamber.
  const named = PEOPLE.filter(p=>p.in_120th==='yes' && p.chamber_120===chamber
    && !(chamber==='House' && TERRITORIES.has(p.state)));
  const total = chamber==='House' ? 435 : 100;
  const seats = named.map(p=>({party:partyName(p), letter:seatLetter(p),
    status:seatStatus(p), name:p.full_name}));
  // Waffle group order, left to right: Clean D, Dirty D, Dirty R,
  // Clean R, then Clean/Dirty I, Unopposed, Unverified, Uncalled.
  const groupRank = s=>{
    if(s.status==='uncalled') return 8;
    if(s.status==='unverified') return 7;
    if(s.status==='unopposed') return 6;
    if(s.status==='clean' && s.letter==='D') return 0;
    if(s.status==='dirty' && s.letter==='D') return 1;
    if(s.status==='dirty' && s.letter==='R') return 2;
    if(s.status==='clean' && s.letter==='R') return 3;
    if(s.status==='clean') return 4;
    return 5;
  };
  seats.sort((a,b)=>groupRank(a)-groupRank(b));
  while(seats.length < total)
    seats.push({party:null, letter:'', status:'uncalled', name:'Uncalled seat'});
  return {seats, total, named: named.length};
}
const WAFFLE_ROWS = 15, WAFFLE_COLS = 29, WAFFLE_STEP = 12, WAFFLE_R = 5;
function waffleDotSVG(s, x, y, col){
  const label = {dirty:'took dirty money in 2026',
    clean:'verified clean in 2026',
    unopposed:'ran unopposed — not judged',
    unverified:'unverified — not judged',
    uncalled:'no named member yet'}[s.status];
  const title = s.status==='uncalled' ? 'Uncalled seat — no named member yet'
    : s.name+' · '+(s.party||'')+' · '+label;
  const c = dotColor(s.party);
  let inner;
  if(s.status==='dirty'){
    // Black bubble with a party-color dot in the middle.
    inner = '<circle cx="'+x+'" cy="'+y+'" r="'+WAFFLE_R+'" fill="#111827"/>'
      + '<circle cx="'+x+'" cy="'+y+'" r="2.1" fill="'+c+'"/>';
  } else if(s.status==='clean'){
    inner = '<circle cx="'+x+'" cy="'+y+'" r="'+WAFFLE_R+'" fill="'+c+'"/>';
  } else if(s.status==='unopposed' || s.status==='unverified'){
    inner = '<circle cx="'+x+'" cy="'+y+'" r="'+WAFFLE_R+'" fill="#fff" stroke="#9ca3af" stroke-width="1.6"/>';
  } else {
    inner = '<circle cx="'+x+'" cy="'+y+'" r="'+WAFFLE_R+'" fill="none" stroke="#d1d5db" stroke-width="1.4" stroke-dasharray="2.5 2"/>';
  }
  // Stagger by column so the waffle fills left to right on reveal.
  return '<g class="dot '+s.status+'" data-party="'+esc(s.letter)+'" style="transition-delay:'+(col*40)+'ms">'+inner
    + '<title>'+esc(title)+'</title></g>';
}
function waffleSVG(seats){
  // Column-major fill: each column top to bottom, then the next
  // column, so the category blocks read left to right.
  const W = WAFFLE_COLS*WAFFLE_STEP, H = WAFFLE_ROWS*WAFFLE_STEP;
  let dots = '';
  for(let i=0;i<seats.length;i++){
    const col = Math.floor(i/WAFFLE_ROWS), row = i%WAFFLE_ROWS;
    dots += waffleDotSVG(seats[i], WAFFLE_STEP/2 + col*WAFFLE_STEP,
      WAFFLE_STEP/2 + row*WAFFLE_STEP, col);
  }
  return '<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'
    + seats.length + ' seats: one dot per seat">'+dots+'</svg>';
}
const TILE_W = 60, TILE_H = 46, TILE_GAP = 5, TILE_COLS = 10;
function senateStates(){
  // One entry per state: its named senators, padded with uncalled
  // halves to two seats. Every state has at least one named senator;
  // Alaska has one named (Murkowski) and one uncalled seat.
  const byState = {};
  PEOPLE.filter(p=>p.in_120th==='yes' && p.chamber_120==='Senate')
    .forEach(p=>{ (byState[p.state] = byState[p.state]||[]).push(p); });
  const partyRank = {Democrat:0, Republican:1, Independent:2};
  return Object.keys(STATE_NAMES).filter(s=>!TERRITORIES.has(s)).sort()
    .map(code=>{
      const sens = (byState[code]||[]).slice().sort((a,b)=>
        (partyRank[partyName(a)] ?? 3) - (partyRank[partyName(b)] ?? 3)
        || a.full_name.localeCompare(b.full_name));
      const halves = sens.map(p=>({party:partyName(p), letter:seatLetter(p),
        status:seatStatus(p), name:p.full_name}));
      while(halves.length < 2)
        halves.push({party:null, letter:'', status:'uncalled', name:'Uncalled seat'});
      return {code, halves};
    });
}
function tileHalfSVG(half, x, y, w, h){
  const label = {dirty:'took dirty money in 2026',
    clean:'verified clean in 2026',
    unopposed:'ran unopposed — not judged',
    unverified:'unverified — not judged',
    uncalled:'no named member yet'}[half.status];
  const title = half.status==='uncalled' ? 'Uncalled seat — no named member yet'
    : half.name+' · '+(half.party||'')+' · '+label;
  let attrs;
  if(half.status==='dirty'){
    // Black with a dotted party-color pattern.
    const pat = {D:'D', R:'R', I:'I'}[half.letter] || 'I';
    attrs = 'fill="url(#dots-'+pat+')"';
  } else if(half.status==='clean'){
    attrs = 'fill="'+dotColor(half.party)+'"';
  } else if(half.status==='unopposed' || half.status==='unverified'){
    attrs = 'fill="#fff" stroke="#9ca3af" stroke-width="1.2"';
  } else {
    attrs = 'fill="#f9fafb" stroke="#d1d5db" stroke-width="1.2" stroke-dasharray="3 2"';
  }
  return '<rect class="half '+half.status+'" data-party="'+esc(half.letter)+'" x="'+x+'" y="'+y
    +'" width="'+w+'" height="'+h+'" '+attrs+'><title>'+esc(title)+'</title></rect>';
}
function senateTilesSVG(){
  const states = senateStates();
  const rows = Math.ceil(states.length/TILE_COLS);
  const W = TILE_COLS*TILE_W + (TILE_COLS-1)*TILE_GAP;
  const H = rows*TILE_H + (rows-1)*TILE_GAP;
  const defs = '<defs>' + ['D','R','I'].map(L=>{
    const c = {D:'#1e40af', R:'#991b1b', I:'#374151'}[L];
    return '<pattern id="dots-'+L+'" width="7" height="7" patternUnits="userSpaceOnUse">'
      + '<rect width="7" height="7" fill="#111827"/>'
      + '<circle cx="3.5" cy="3.5" r="1.4" fill="'+c+'"/></pattern>';
  }).join('') + '</defs>';
  let tiles = '';
  states.forEach((st, i)=>{
    const col = i%TILE_COLS, row = Math.floor(i/TILE_COLS);
    const x = col*(TILE_W+TILE_GAP), y = row*(TILE_H+TILE_GAP);
    const title = (STATE_NAMES[st.code]||st.code)+' — '+st.halves.map(h=>
      h.status==='uncalled' ? 'seat uncalled'
      : h.name+' ('+h.letter+', '+({dirty:'took dirty money in 2026',
        clean:'verified clean in 2026', unopposed:'ran unopposed',
        unverified:'unverified'}[h.status])+')').join('; ');
    tiles += '<g class="tile" data-state="'+st.code+'" style="transition-delay:'+(i*30)+'ms">'
      + tileHalfSVG(st.halves[0], x, y, TILE_W/2, TILE_H)
      + tileHalfSVG(st.halves[1], x+TILE_W/2, y, TILE_W/2, TILE_H)
      + '<rect x="'+x+'" y="'+y+'" width="'+TILE_W+'" height="'+TILE_H+'" fill="none" stroke="#6b7280" stroke-width="1"/>'
      + '<text x="'+(x+TILE_W/2)+'" y="'+(y+TILE_H/2+4.5)+'" text-anchor="middle" font-size="13" font-weight="700" fill="#fff" stroke="#111827" stroke-width="2.5" paint-order="stroke" stroke-linejoin="round">'+st.code+'</text>'
      + '<title>'+esc(title)+'</title></g>';
  });
  return '<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Senate: '
    + states.length + ' state tiles, ' + states.length*2 + ' seats">'+defs+tiles+'</svg>';
}
function legendSwatch(kind, color){
  if(kind==='solid') return 'background:'+color;
  // Black disc with one party-color dot in the middle (House waffle).
  if(kind==='dot') return 'background:radial-gradient(circle at center,'+color+' 0 30%,#111827 31%)';
  // Black with a party-color dotted pattern (Senate tiles).
  if(kind==='dots') return 'background-color:#111827;background-image:radial-gradient(circle,'+color+' 1.1px,transparent 1.3px);background-size:5px 5px';
  if(kind==='gray') return 'background:#fff;border:2px solid #9ca3af';
  return 'background:#fff;border:2px dashed #d1d5db';
}
function legendHTML(seats, dirtyStyle){
  const count = (letter, status)=>seats.filter(s=>s.letter===letter && s.status===status).length;
  const parties = [...new Set(seats.filter(s=>s.letter).map(s=>s.letter))];
  const items = [];
  parties.forEach(L=>{
    const party = seats.find(s=>s.letter===L).party;
    const c = dotColor(party);
    items.push({label:'Dirty '+L, n:count(L,'dirty'), sw:legendSwatch(dirtyStyle, c)});
    items.push({label:'Clean '+L, n:count(L,'clean'), sw:legendSwatch('solid', c)});
  });
  const unopp = seats.filter(s=>s.status==='unopposed').length;
  const unver = seats.filter(s=>s.status==='unverified').length;
  const unc = seats.filter(s=>s.status==='uncalled').length;
  if(unopp) items.push({label:'Unopposed', n:unopp, sw:legendSwatch('gray')});
  if(unver) items.push({label:'Unverified', n:unver, sw:legendSwatch('gray')});
  if(unc) items.push({label:'Uncalled', n:unc, sw:legendSwatch('dashed')});
  return '<div class="legend">'+items.map(e=>'<span class="lg"><i style="'+e.sw+'"></i>'+esc(e.label)+' '+e.n+'</span>').join('')+'</div>';
}
function renderComposition(){
  const h = compositionSeats('House'), s = compositionSeats('Senate');
  const delegates = PEOPLE.filter(p=>p.in_120th==='yes' && p.chamber_120==='House'
    && TERRITORIES.has(p.state));
  const dCount = {};
  delegates.forEach(p=>{
    const key = (seatStatus(p)==='dirty' ? 'Dirty ' : seatStatus(p)==='clean' ? 'Clean '
      : seatStatus(p)==='unopposed' ? 'Unopposed ' : 'Unverified ') + seatLetter(p);
    dCount[key] = (dCount[key]||0) + 1;
  });
  const dNote = 'Not shown: '+delegates.length+' non-voting delegates — '
    + Object.entries(dCount).map(([k,v])=>k+' '+v).join(' · ') + '.';
  document.getElementById('composition').innerHTML =
    '<div class="comp">'
    + '<figure>'+waffleSVG(h.seats)
    + '<figcaption>House — '+h.total+' voting seats</figcaption>'+legendHTML(h.seats,'dot')+'</figure>'
    + '<figure>'+senateTilesSVG()
    + '<figcaption>Senate — '+s.total+' seats</figcaption>'+legendHTML(s.seats,'dots')+'</figure>'
    + '</div><p class="delegates">'+esc(dNote)+'</p>';
}
/* ---- find-your-member finder (120th Congress only, no URL state) ----
   State -> seat -> person. The table is filtered to that person and
   their drill-down opens in-page. Seats come from the 120th members
   present in the data, so a seat with no named incoming member simply
   does not appear. District '0'/'' is at-large; territories have a
   single at-large delegate (PR: Resident Commissioner), never a
   numbered district, whatever the filing's district value says. */
const STATE_NAMES = {AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',CO:'Colorado',CT:'Connecticut',DE:'Delaware',DC:'District of Columbia',FL:'Florida',GA:'Georgia',HI:'Hawaii',ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',KS:'Kansas',KY:'Kentucky',LA:'Louisiana',ME:'Maine',MD:'Maryland',MA:'Massachusetts',MI:'Michigan',MN:'Minnesota',MS:'Mississippi',MO:'Missouri',MT:'Montana',NE:'Nebraska',NV:'Nevada',NH:'New Hampshire',NJ:'New Jersey',NM:'New Mexico',NY:'New York',NC:'North Carolina',ND:'North Dakota',OH:'Ohio',OK:'Oklahoma',OR:'Oregon',PA:'Pennsylvania',RI:'Rhode Island',SC:'South Carolina',SD:'South Dakota',TN:'Tennessee',TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',WV:'West Virginia',WI:'Wisconsin',WY:'Wyoming',AS:'American Samoa',GU:'Guam',MP:'Northern Mariana Islands',PR:'Puerto Rico',VI:'U.S. Virgin Islands'};
const TERRITORIES = new Set(['AS','GU','MP','PR','VI','DC']);
function finderSeats(stateCode){
  const members = PEOPLE.filter(p=>p.in_120th==='yes'&&p.state===stateCode);
  const seats = [];
  if(members.some(p=>p.chamber_120==='Senate')) seats.push({value:'senate', label:'U.S. Senate — statewide'});
  const districts = [...new Set(members.filter(p=>p.chamber_120==='House').map(p=>p.district_120||'0'))]
    .sort((a,b)=>parseInt(a,10)-parseInt(b,10));
  districts.forEach(d=>{
    let label;
    if(!d||d==='0'){
      label = stateCode==='PR' ? 'At-large — Resident Commissioner' : (TERRITORIES.has(stateCode) ? 'At-large — Delegate' : 'At-large');
    } else {
      label = 'District '+parseInt(d,10);
    }
    seats.push({value:d||'0', label});
  });
  return seats;
}
function finderPeople(stateCode, seat){
  const members = PEOPLE.filter(p=>p.in_120th==='yes'&&p.state===stateCode);
  if(seat==='senate') return members.filter(p=>p.chamber_120==='Senate');
  return members.filter(p=>p.chamber_120==='House'&&(p.district_120||'0')===seat);
}
function initFinder(){
  const sel = document.getElementById('find-state');
  const states = [...new Set(PEOPLE.filter(p=>p.in_120th==='yes').map(p=>p.state))]
    .sort((a,b)=>(STATE_NAMES[a]||a).localeCompare(STATE_NAMES[b]||b));
  sel.innerHTML = '<option value="">Choose your state…</option>'
    + states.map(s=>'<option value="'+esc(s)+'">'+esc(STATE_NAMES[s]||s)+'</option>').join('');
  sel.addEventListener('change', ()=>{
    const dist = document.getElementById('find-district');
    const person = document.getElementById('find-person');
    person.innerHTML = '';
    if(!sel.value){ dist.innerHTML = '<option value="">Choose a district…</option>'; dist.disabled = true; return; }
    const seats = finderSeats(sel.value);
    dist.innerHTML = '<option value="">Choose a district…</option>'
      + seats.map(s=>'<option value="'+esc(s.value)+'">'+esc(s.label)+'</option>').join('');
    dist.disabled = false;
    if(!seats.some(s=>s.value!=='senate')){
      person.innerHTML = '<span style="color:var(--muted);font-size:.9rem">House seat uncalled — no incoming member named yet.</span>';
    }
  });
  document.getElementById('find-district').addEventListener('change', e=>{
    const person = document.getElementById('find-person');
    const seat = e.target.value;
    person.innerHTML = '';
    if(!seat) return;
    const people = finderPeople(sel.value, seat);
    if(!people.length){
      person.innerHTML = '<span style="color:var(--muted);font-size:.9rem">No incoming member listed for this seat yet.</span>';
      return;
    }
    person.innerHTML = people.map(p=>
      '<button type="button" class="btn person-btn" data-key="'+p.person_key+'">'
      + partyChip(p)+' '+esc(p.full_name)+' · '+outcomeLabel(p)+' '+fmtTierBadge(p)+'</button>').join(' ');
    person.querySelectorAll('button').forEach(b=>{
      b.addEventListener('click', ()=>findPerson(b.getAttribute('data-key')));
    });
  });
}
function findPerson(key){
  const p = BY_KEY[key]; if(!p) return;
  state.q = p.full_name; state.congress = '120'; state.chamber = 'all';
  state.party = 'all'; state.state = 'all'; state.leadership = false; state.clean = false;
  document.getElementById('q').value = p.full_name;
  document.getElementById('f-congress').value = '120';
  document.getElementById('f-chamber').value = 'all';
  document.getElementById('f-party').value = 'all';
  document.getElementById('f-state').value = 'all';
  document.getElementById('f-leader').checked = false;
  document.getElementById('f-clean').checked = false;
  renderTable();
  openDetail(key);
}
</script>
"""

TEMPLATE_JS2 = """
<script>
"use strict";
/* ---- detail overlay ---- */
function cycleTable(title, rows, cols){
  if(!rows || !rows.length) return '';
  let h = '<h3>'+esc(title)+'</h3><div class="tablewrap"><table><thead><tr>'
    + cols.map(c=>'<th class="'+(c.type==='money'?'num':'')+'">'+esc(c.label)+'</th>').join('') + '</tr></thead><tbody>';
  rows.forEach(r=>{
    h += '<tr>'+cols.map(c=>{
      const v = r[c.k];
      let cell;
      if(c.type==='money') cell = fmtMoney(v);
      else if(c.type==='text') cell = esc(v==null||v===''?'—':v);
      else cell = esc(v==null?'—':v);
      return '<td class="'+(c.type==='money'?'num':'')+'">'+cell+'</td>';
    }).join('')+'</tr>';
  });
  return h + '</tbody></table></div>';
}
function kvRow(label, value){ return '<div><span>'+esc(label)+'</span><span>'+value+'</span></div>'; }
function openDetail(key){
  const p = BY_KEY[key]; if(!p) return;
  const leader = [p.leadership_119, (p.leadership_120 && p.leadership_120!=='TBD') ? p.leadership_120 : null].filter(Boolean).join('; ');
  let h = '<button class="btn ghost close" id="detail-close" type="button">Close ✕</button>';
  h += '<h2>'+esc(p.full_name)+'</h2>';
  h += '<p class="meta">'+partyChip(p)+' '+esc(party(p))+' · '+esc(chamber(p))+' · '+esc(place(p))+' · '+outcomeLabel(p)+' · '+esc(congressLabel(p))
    + (leader ? ' · '+esc(leader) : '') + ' · FEC ID'+(p.fec_candidate_ids.length>1?'s':'')+': '
    + esc(p.fec_candidate_ids.join(', ')||'none') + '</p>';
  h += '<h3>Career money</h3><div class="kv">'
    + kvRow('Individual contributions', fmtMoney(p.individual_contribution_total_career)+' ('+fmtRank(p.rank_individual)+')')
    + kvRow('Corporate PAC', fmtMoney(p.corporate_pac_career)+' ('+fmtRank(p.rank_corporate_pac)+')')
    + kvRow('AIPAC PAC direct', fmtMoney(p.aipac_pac_direct_career)+' ('+fmtRank(p.rank_aipac_direct)+')')
    + kvRow('— of which earmarked (individuals’ money, passed through)', fmtMoney(p.aipac_earmark_transmitted_career))
    + kvRow('Total accepted', '<b>'+fmtMoney(p.total_accepted_career)+'</b> ('+fmtRank(p.rank_total_accepted)+')')
    + kvRow('Dirty money (career)', fmtMoney(p.dirty_career))
    + kvRow('UDP support', fmtMoney(p.udp_ie_support_career)+' ('+fmtRank(p.rank_udp_support)+')')
    + kvRow('UDP opposition credit', fmtMoney(p.udp_ie_opposing_opponents_career)+' ('+fmtRank(p.rank_udp_opposing_opponents)+')')
    + kvRow('UDP total benefit', fmtMoney(p.udp_ie_total_benefit_career)+' ('+fmtRank(p.rank_udp_total_benefit)+')')
    + kvRow('Self-funding', fmtMoney(p.self_funding_career)+' ('+fmtRank(p.rank_self_funding)+')')
    + kvRow('— candidate loans', fmtMoney(p.cand_loans_career))
    + kvRow('— candidate contributions', fmtMoney(p.cand_contrib_career))
    + kvRow('Loan repayments', fmtMoney(p.loan_repayments_career))
    + kvRow('Total receipts', fmtMoney(p.total_receipts_career))
    + kvRow('Total disbursements', fmtMoney(p.total_disbursements_career))
    + kvRow('Cash on hand (latest cycle)', fmtMoney(p.cash_on_hand_career))
    + kvRow('Debts owed (latest cycle)', fmtMoney(p.debts_owed_by_career))
    + kvRow('Other committees total', fmtMoney(p.other_committees_total_career)+' ('+fmtRank(p.rank_other_committees_total)+')')
    + kvRow('All IE support / oppose / total (2022–2026)', fmtMoney(p.all_ie_support_career)+' / '+fmtMoney(p.all_ie_oppose_career)+' / <b>'+fmtMoney(p.all_ie_total_career)+'</b> ('+fmtRank(p.rank_all_ie_total)+')')
    + '</div>';
  const oppRows = OPP[p.person_key];
  if(oppRows && oppRows.length){
    h += cycleTable('UDP opposition credit by race — phase by phase', oppRows.map(e=>({
      race: e.cycle+' · '+(e.office==='S'?'Senate':'House')+' · '+e.state+(e.office==='H'?'-'+e.district:''),
      phase: PHASE_LABEL[e.phase]||e.phase,
      amount: e.amount,
      opposed: e.opposed.map(o=>o[0]+' ('+fmtMoney(o[1])+')').join(', ')
    })), [
      {k:'race',label:'Race',type:'text'},
      {k:'phase',label:'Phase',type:'text'},
      {k:'amount',label:'Credited',type:'money'},
      {k:'opposed',label:'Opposed',type:'text'}]);
  }
  h += '<h3>2026 cycle (partial)</h3><div class="kv">'
    + kvRow('Tier in 2026 ('+PRESETS[state.preset].label+')', fmtTierBadge(p))
    + kvRow('AIPAC/UDP flag', p.aipac_udp_flag_2026===true ? 'Yes — AIPAC PAC direct money or UDP benefit in 2026; flagged under every tolerance preset' : 'No')
    + kvRow('Unopposed in 2026', p.unopposed_2026===true?'Yes — no opponent with receipts over $0':'No')
    + kvRow('Dirty 2026', fmtMoney(p.dirty_2026))
    + kvRow('Individual 2026', fmtMoney(p.individual_2026))
    + kvRow('Corporate PAC 2026', fmtMoney(p.corp_2026))
    + kvRow('AIPAC direct 2026', fmtMoney(p.aipac_direct_2026))
    + kvRow('UDP support 2026', fmtMoney(p.udp_support_2026))
    + kvRow('UDP opposition credit 2026', fmtMoney(p.udp_opp_credit_2026))
    + kvRow('UDP benefit 2026', fmtMoney(p.udp_benefit_2026))
    + kvRow('Dependence share 2026', fmtPct(p.dep_share_2026))
    + kvRow('Self-funding 2026', fmtMoney(p.self_funding_2026))
    + kvRow('Total receipts / disbursements 2026', fmtMoney(p.total_receipts_2026)+' / '+fmtMoney(p.total_disbursements_2026))
    + kvRow('Other committees 2026', fmtMoney(p.other_committees_total_2026))
    + kvRow('All IE 2026 (support / oppose)', fmtMoney(p.all_ie_support_2026)+' / '+fmtMoney(p.all_ie_oppose_2026))
    + '</div>';
  h += cycleTable('Cycle by cycle — individual / AIPAC / corporate PAC', p.per_cycle, [
    {k:'cycle',label:'Cycle',type:'text'},{k:'candidate_id',label:'Candidate ID',type:'text'},
    {k:'individual',label:'Individual',type:'money'},{k:'aipac_pac_direct',label:'AIPAC direct',type:'money'},
    {k:'aipac_earmark_transmitted',label:'AIPAC earmark',type:'money'},
    {k:'corporate_pac',label:'Corp PAC',type:'money'},{k:'corporate_earmark_transmitted',label:'Corp earmark',type:'money'}]);
  h += cycleTable('Cycle by cycle — self-funding & topline', p.self_funding_per_cycle, [
    {k:'cycle',label:'Cycle',type:'text'},{k:'candidate_id',label:'Candidate ID',type:'text'},
    {k:'candidate_contributions',label:'Cand. contrib.',type:'money'},{k:'candidate_loans',label:'Cand. loans',type:'money'},
    {k:'loan_repayments',label:'Loan repay.',type:'money'},{k:'debts_owed_by',label:'Debts owed',type:'money'},
    {k:'total_receipts',label:'Receipts',type:'money'},{k:'total_disbursements',label:'Disbursements',type:'money'},
    {k:'cash_on_hand',label:'Cash on hand',type:'money'},{k:'coverage_end_date',label:'Coverage ends',type:'text'}]);
  h += cycleTable('Cycle by cycle — other committees', p.other_committees_per_cycle, [
    {k:'cycle',label:'Cycle',type:'text'},{k:'candidate_id',label:'Candidate ID',type:'text'},
    {k:'party_committees',label:'Party',type:'money'},{k:'leadership_pacs',label:'Leadership',type:'money'},
    {k:'labor_pacs',label:'Labor',type:'money'},{k:'trade_pacs',label:'Trade',type:'money'},
    {k:'membership_pacs',label:'Membership',type:'money'},{k:'cooperative_pacs',label:'Cooperative',type:'money'},
    {k:'other_unclassified',label:'Other',type:'money'},{k:'winred_included',label:'WinRed incl.',type:'money'}]);
  h += cycleTable('Cycle by cycle — all independent expenditures (2022–2026)', p.all_ie_per_cycle, [
    {k:'cycle',label:'Cycle',type:'text'},{k:'candidate_id',label:'Candidate ID',type:'text'},
    {k:'all_ie_support',label:'Support',type:'money'},{k:'all_ie_oppose',label:'Oppose',type:'money'},
    {k:'all_ie_total',label:'Total',type:'money'}]);
  h += cycleTable('Cycle by cycle — UDP support', p.udp_per_cycle, [
    {k:'cycle',label:'Cycle',type:'text'},{k:'candidate_id',label:'Candidate ID',type:'text'},
    {k:'udp_ie_support',label:'UDP support',type:'money'},{k:'attribution',label:'Attribution',type:'text'}]);
  if(p.all_ie_top_committees && p.all_ie_top_committees.length){
    h += cycleTable('Top outside spenders on this race (career, 2022–2026)', p.all_ie_top_committees, [
      {k:'committee_name',label:'Committee',type:'text'},{k:'support',label:'Support',type:'money'},
      {k:'oppose',label:'Oppose',type:'money'},{k:'total',label:'Total',type:'money'}]);
  }
  if(p.data_notes) h += '<h3>Data notes</h3><div class="notes">'+esc(p.data_notes)+'</div>';
  h += '<p style="color:var(--muted);font-size:.85rem">Data as of '+esc(p.data_as_of)+' · Person key '+esc(p.person_key)+' · Figures trace to FEC filings; see Methodology.</p>';
  document.getElementById('detail-sheet').innerHTML = h;
  document.getElementById('detail').classList.add('open');
  document.getElementById('detail-close').addEventListener('click', closeDetail);
}
function closeDetail(){ document.getElementById('detail').classList.remove('open'); }

/* ---- leaderboards ---- */
function topByRank(rankKey, amountKey, n){
  return PEOPLE.filter(p=>num(p[rankKey])!==null)
    .sort((a,b)=>a[rankKey]-b[rankKey]).slice(0,n)
    .map(p=>({name:p.full_name, who:partyChip(p)+' '+esc(party(p))+' · '+esc(place(p))+' · '+outcomeLabel(p), amount:p[amountKey]}));
}
function boardHtml(title, sub, entries){
  let h = '<h3>'+esc(title)+'</h3><p style="color:var(--muted);font-size:.9rem">'+esc(sub)+'</p><ol class="leader">';
  entries.forEach((e,i)=>{
    h += '<li><span><b>'+(i+1)+'.</b> '+esc(e.name)+' <span class="who">'+e.who+'</span></span><span class="amt">'+fmtMoney(e.amount)+'</span></li>';
  });
  return h + '</ol>';
}
/* ---- leaderboards: dirty leads ----
   The first two boards are the dirtiness measure (2026, then career);
   total accepted is fundraising scale, not dirtiness, so it comes
   after. The dirty boards sort by amount at render time from the
   embedded data — no rank column is needed for them. */
function topByAmount(amountKey, n){
  return PEOPLE.filter(p=>num(p[amountKey])!==null && num(p[amountKey])>0)
    .sort((a,b)=>num(b[amountKey])-num(a[amountKey])).slice(0,n)
    .map(p=>({name:p.full_name, who:partyChip(p)+' '+esc(party(p))+' · '+esc(place(p))+' · '+outcomeLabel(p), amount:p[amountKey]}));
}
function renderLeaders(){
  document.getElementById('leaders').innerHTML =
    boardHtml('Top 20 — dirtiest in 2026', 'Corporate PAC + AIPAC PAC direct + UDP benefit in the 2026 cycle. Individual contributions are not dirty money.',
      topByAmount('dirty_2026',20))
    + boardHtml('Top 20 — dirtiest, career', 'Career dirty money: corporate PAC + AIPAC PAC direct + UDP benefit, all cycles.',
      topByAmount('dirty_career',20))
    + boardHtml('Top 20 — total accepted (career)', 'Individual contributions + corporate PAC + AIPAC PAC direct. Total accepted measures fundraising scale, not dirtiness — the two lists above are the dirtiness measure.',
      topByRank('rank_total_accepted','total_accepted_career',20))
    + boardHtml('Top 10 — UDP total benefit (career)', 'UDP spending supporting the candidate plus opposition credit for spending against their opponent. Money spent about the race, never given to the campaign.',
      topByRank('rank_udp_total_benefit','udp_ie_total_benefit_career',10))
    + boardHtml('Top 10 — self-funding (career)', 'Candidate contributions + candidate loans. The candidate’s own money.',
      topByRank('rank_self_funding','self_funding_career',10))
    + boardHtml('Top 10 — all independent expenditures (career, 2022–2026)', 'All outside spending for and against the candidate, every registered committee — not just UDP.',
      topByRank('rank_all_ie_total','all_ie_total_career',10));
}

/* ---- clean view (preset-aware) ----
   Under Strict the tab lists verified-clean members; under Balanced
   / Lenient it lists everyone not dirty under the preset — clean
   plus the below-threshold middle tier, whose corporate PAC amount
   is always shown. Counts are computed from PEOPLE at render time
   and always labeled with the preset. */
function renderClean(){
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const nd = incoming.filter(isNotDirty);
  const hND = nd.filter(p=>p.chamber_120==='House').length;
  const sND = nd.filter(p=>p.chamber_120==='Senate').length;
  const careerCleanHouse = incoming.filter(p=>p.chamber_120==='House'&&isCareerClean(p));
  const ndAll = PEOPLE.filter(isNotDirty);
  const unopp = PEOPLE.filter(p=>p.unopposed_2026===true);
  const unver = PEOPLE.filter(p=>p.clean_2026===null && p.unopposed_2026!==true);
  const preset = PRESETS[state.preset];
  const word = state.preset==='strict' ? 'verified clean' : 'not dirty';
  document.getElementById('clean-stats').innerHTML =
    '<div class="stats">'
    + '<div class="stat"><b>'+hND+' of 436</b>incoming House '+word+' in 2026 ('+preset.label+')</div>'
    + '<div class="stat"><b>'+sND+' of 99</b>incoming Senate '+word+' in 2026 ('+preset.label+')</div>'
    + '<div class="stat"><b>'+nd.length+' total</b>'+word+' in the incoming 120th ('+preset.label+')</div>'
    + '<div class="stat"><b>'+careerCleanHouse.length+'</b>career-clean incoming House members</div>'
    + '<div class="stat"><b>'+unopp.length+' ran unopposed</b>in 2026 — no opponent with receipts over $0, so not counted clean: '+esc(unopp.map(p=>p.full_name).join(', '))+'</div>'
    + '<div class="stat"><b>'+unver.length+' unverified</b>'+esc(unver.map(p=>p.full_name).join(', '))+'</div>'
    + '</div>'
    + '<p style="color:var(--muted)">'+ndAll.length+' people in the whole tracker are '+word+' in 2026 under the '+preset.label+' tolerance — the '+nd.length+' above plus '
    + (ndAll.length-nd.length) + ' outgoing 119th-only members. Click a row for the full breakdown.</p>';
  const mid = state.preset==='strict' ? ''
    : ' The middle tier — “Below threshold” — took corporate PAC money below those thresholds; it is never called clean, and the dollar amount is always shown.';
  document.getElementById('clean-callout').innerHTML =
    '<b>What “'+word+' in 2026” means under the '+preset.label+' tolerance:</b> '+preset.def
    + ' It is a cycle test, not a career test — a member can be '+word+' in 2026 while having taken such money in earlier cycles.'+mid
    + ' A member is shown as <b>unverified</b> only if they have no 2026 entries in <i>any</i> money source; Elaine Luria is the one unverified member — her real 2026 campaign is not linked in the roster yet.';
  const thead = document.querySelector('#clean-table thead');
  const tbody = document.querySelector('#clean-table tbody');
  thead.innerHTML = '<tr><th>Name</th><th>State / Dist.</th><th>Party</th><th>Chamber</th><th>Incoming 120th?</th><th>Tier 2026</th><th class="num">Corp PAC 2026</th><th class="num">Dirty 2026</th><th>Career-clean?</th></tr>';
  const rows = ndAll.slice().sort((a,b)=>a.full_name.localeCompare(b.full_name));
  tbody.innerHTML = rows.map(p=>'<tr data-key="'+p.person_key+'"><td class="name">'+esc(p.full_name)+'</td><td>'+esc(place(p))+'</td><td>'+partyChip(p)+' '+esc(party(p))+'</td><td>'+esc(chamber(p))+'</td><td>'+(p.in_120th==='yes'?'Yes':'No — 119th only')+'</td><td>'+fmtTierBadge(p)+'</td><td class="num">'+fmtCompact(p.corp_2026)+'</td><td class="num">'+fmtCompact(p.dirty_2026)+'</td><td>'+(isCareerClean(p)?'Yes':'No')+'</td></tr>').join('');
  tbody.querySelectorAll('tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- party breakdown ---- */
function renderBreakdown(){
  document.getElementById('breakdown-intro').textContent =
    'Members of the incoming 120th Congress, grouped by party and chamber. Money columns are career totals; the not-dirty column counts members with no dirty money in 2026 under the '+PRESETS[state.preset].label+' tolerance ('+PRESETS[state.preset].short+').';
  const groups = {};
  PEOPLE.filter(p=>p.in_120th==='yes').forEach(p=>{
    const k = (p.party_120||'—')+'|'+(p.chamber_120||'—');
    groups[k] = groups[k]||{party:p.party_120||'—', chamber:p.chamber_120||'—', n:0, ind:0, corp:0, aipac:0, tot:0, udp:0, self:0, ie:0, clean:0};
    const g = groups[k]; g.n++;
    g.ind+=num(p.individual_contribution_total_career)||0;
    g.corp+=num(p.corporate_pac_career)||0;
    g.aipac+=num(p.aipac_pac_direct_career)||0;
    g.tot+=num(p.total_accepted_career)||0;
    g.udp+=num(p.udp_ie_total_benefit_career)||0;
    g.self+=num(p.self_funding_career)||0;
    g.ie+=num(p.all_ie_total_career)||0;
    if(isNotDirty(p)) g.clean++;
  });
  const rows = Object.values(groups).sort((a,b)=>b.n-a.n);
  const tot = {n:0,ind:0,corp:0,aipac:0,tot:0,udp:0,self:0,ie:0,clean:0};
  rows.forEach(g=>{ tot.n+=g.n; tot.ind+=g.ind; tot.corp+=g.corp; tot.aipac+=g.aipac; tot.tot+=g.tot; tot.udp+=g.udp; tot.self+=g.self; tot.ie+=g.ie; tot.clean+=g.clean; });
  const rowHtml = g=>'<tr><td>'+esc(g.party)+'</td><td>'+esc(g.chamber)+'</td><td class="num">'+g.n+'</td><td class="num">'+fmtCompact(g.ind)+'</td><td class="num">'+fmtCompact(g.corp)+'</td><td class="num">'+fmtCompact(g.aipac)+'</td><td class="num">'+fmtCompact(g.tot)+'</td><td class="num">'+fmtCompact(g.udp)+'</td><td class="num">'+fmtCompact(g.self)+'</td><td class="num">'+fmtCompact(g.ie)+'</td><td class="num">'+g.clean+'</td></tr>';
  document.querySelector('#breakdown-table thead').innerHTML =
    '<tr><th>Party</th><th>Chamber</th><th class="num">Members</th><th class="num">Individual (career)</th><th class="num">Corp PAC (career)</th><th class="num">AIPAC (career)</th><th class="num">Total accepted</th><th class="num">UDP benefit</th><th class="num">Self-funding</th><th class="num">All IE total</th><th class="num">Not dirty 2026 ('+PRESETS[state.preset].label+')</th></tr>';
  document.querySelector('#breakdown-table tbody').innerHTML =
    rows.map(rowHtml).join('') + '<tr><td><b>All</b></td><td><b>120th</b></td><td class="num"><b>'+tot.n+'</b></td><td class="num"><b>'+fmtCompact(tot.ind)+'</b></td><td class="num"><b>'+fmtCompact(tot.corp)+'</b></td><td class="num"><b>'+fmtCompact(tot.aipac)+'</b></td><td class="num"><b>'+fmtCompact(tot.tot)+'</b></td><td class="num"><b>'+fmtCompact(tot.udp)+'</b></td><td class="num"><b>'+fmtCompact(tot.self)+'</b></td><td class="num"><b>'+fmtCompact(tot.ie)+'</b></td><td class="num"><b>'+tot.clean+'</b></td></tr>';
}

/* ---- primary targets ---- */
function renderTargets(){
  const rows = PEOPLE.filter(p=>p.in_120th==='yes'&&p.chamber_120==='House'&&p.party_120==='Democrat'&&num(p.dirty_2026)>0)
    .sort((a,b)=>num(b.dirty_2026)-num(a.dirty_2026));
  document.querySelector('#targets-table thead').innerHTML =
    '<tr><th>#</th><th>Name</th><th>District</th><th class="num">Dirty 2026</th><th class="num">Corp PAC 2026</th><th class="num">AIPAC 2026</th><th class="num">UDP benefit 2026</th><th class="num">Individual 2026</th></tr>';
  document.querySelector('#targets-table tbody').innerHTML = rows.map((p,i)=>
    '<tr data-key="'+p.person_key+'"><td>'+(i+1)+'</td><td class="name">'+esc(p.full_name)+'</td><td>'+esc(place(p))+'</td><td class="num">'+fmtMoney(p.dirty_2026)+'</td><td class="num">'+fmtMoney(p.corp_2026)+'</td><td class="num">'+fmtMoney(p.aipac_direct_2026)+'</td><td class="num">'+fmtMoney(p.udp_benefit_2026)+'</td><td class="num">'+fmtMoney(p.individual_2026)+'</td></tr>').join('');
  document.querySelectorAll('#targets-table tbody tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- 2028 primary targets: same rule, seats up in 2028 ----
   House: every seat is up, so the 2026 pool carries over. Senate:
   Class 3 Democrats only (senate_class 3, from the dataset — the
   legislators yaml's Senate-term class field; see methodology §14).
   Under a tolerance preset the target rule is tier dirty (flagged
   OR corporate-PAC-material under that preset) instead of
   dirty_2026 > 0 — Strict 192 / 13, Balanced 133 / 6, Lenient
   103 / 3. The intro is computed at render, never typed: counts
   change with the data and the preset, and the framing is a
   watchlist, not a ballot prediction. */
function renderTargets2028(){
  const house = PEOPLE.filter(p=>p.in_120th==='yes'&&p.chamber_120==='House'&&p.party_120==='Democrat'&&tierOf(p)==='dirty')
    .sort((a,b)=>num(b.dirty_2026)-num(a.dirty_2026));
  const senate = PEOPLE.filter(p=>p.in_120th==='yes'&&p.chamber_120==='Senate'&&p.party_120==='Democrat'&&p.senate_class===3&&tierOf(p)==='dirty')
    .sort((a,b)=>num(b.dirty_2026)-num(a.dirty_2026));
  const preset = PRESETS[state.preset];
  document.getElementById('targets28-intro').innerHTML =
    'A watchlist, not a prediction. '+house.length+' House Democrats and '+senate.length+' Democratic senators in the incoming 120th took dirty money in 2026 (corporate PAC + AIPAC direct + UDP benefit) and hold seats up in 2028, under the '+preset.label+' tolerance ('+preset.short+'; any AIPAC direct or UDP benefit dollar always counts). Retirements are unknown, 2028 filings are not open, and 2026 is partial (see the cutoffs above). The rule is mechanical — dirty money only; the tracker does not judge electability or anything else.';
  const rowHtml = (p,i)=>'<tr data-key="'+p.person_key+'"><td>'+(i+1)+'</td><td class="name">'+esc(p.full_name)+flagBadge(p)+'</td><td>'+esc(place(p))+'</td><td class="num">'+fmtMoney(p.dirty_2026)+'</td><td class="num">'+fmtMoney(p.corp_2026)+'</td><td class="num">'+fmtMoney(p.aipac_direct_2026)+'</td><td class="num">'+fmtMoney(p.udp_benefit_2026)+'</td><td class="num">'+fmtMoney(p.dirty_career)+'</td><td class="num">'+fmtMoney(p.individual_2026)+'</td></tr>';
  document.querySelector('#targets28-house-table thead').innerHTML =
    '<tr><th>#</th><th>Name</th><th>District</th><th class="num">Dirty 2026</th><th class="num">Corp PAC 2026</th><th class="num">AIPAC 2026</th><th class="num">UDP benefit 2026</th><th class="num">Dirty career</th><th class="num">Individual 2026</th></tr>';
  document.querySelector('#targets28-house-table tbody').innerHTML = house.map(rowHtml).join('');
  document.querySelector('#targets28-senate-table thead').innerHTML =
    '<tr><th>#</th><th>Name</th><th>Seat</th><th class="num">Dirty 2026</th><th class="num">Corp PAC 2026</th><th class="num">AIPAC 2026</th><th class="num">UDP benefit 2026</th><th class="num">Dirty career</th><th class="num">Individual 2026</th></tr>';
  document.querySelector('#targets28-senate-table tbody').innerHTML = senate.map(rowHtml).join('');
  document.querySelectorAll('#targets28-house-table tbody tr, #targets28-senate-table tbody tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- tolerance preset switching ----
   Recomputes every preset-dependent surface live: header stats, the
   table badges, the front-door story, and the clean / breakdown /
   2028-targets tabs (re-rendered on next show if not current). The
   leaderboards and the 2026 targets tab are Strict history and do
   not move with the preset. */
function setPreset(preset){
  if(!PRESETS[preset]) return;
  state.preset = preset;
  document.getElementById('tolerance-note').textContent = PRESETS[preset].def;
  renderStats(); renderTable(); renderCleanStory();
  ['clean','breakdown','targets28'].forEach(t=>{
    if(state.tab===t){
      if(t==='clean') renderClean();
      if(t==='breakdown') renderBreakdown();
      if(t==='targets28') renderTargets2028();
      state.rendered[t]=true;
    } else {
      state.rendered[t]=false;
    }
  });
}

/* ---- CSV download (from the same embedded figures) ---- */
function csvCell(v){
  if(v===null||v===undefined) return '';
  if(Array.isArray(v)) return JSON.stringify(v);
  if(typeof v==='object') return JSON.stringify(v);
  if(typeof v==='string') return v;
  if(typeof v==='boolean') return v?'true':'false';
  return String(v);
}
function downloadCsv(){
  const cols = COLS.csv;
  const escCsv = s => /[",\\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
  const lines = [cols.map(escCsv).join(',')];
  PEOPLE.forEach(p=>{
    lines.push(cols.map(k=>{
      let v;
      if(k==='fec_candidate_ids') v = p.fec_candidate_ids.join(';');
      else if(k==='per_cycle') v = p.per_cycle;
      else if(k==='udp_per_cycle') v = p.udp_per_cycle;
      else if(k==='self_funding_per_cycle') v = p.self_funding_per_cycle;
      else if(k==='other_committees_per_cycle') v = p.other_committees_per_cycle;
      else if(k==='all_ie_per_cycle') v = p.all_ie_per_cycle;
      else v = p[k];
      return escCsv(csvCell(v));
    }).join(','));
  });
  const blob = new Blob([lines.join('\\n')], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'congress-money-tracker.csv';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 1000);
}

/* ---- header stats ---- */
function renderStats(){
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const nd = incoming.filter(isNotDirty);
  const hND = nd.filter(p=>p.chamber_120==='House').length;
  const sND = nd.filter(p=>p.chamber_120==='Senate').length;
  const sum = k => PEOPLE.reduce((s,p)=>s+(num(p[k])||0),0);
  const unopp = PEOPLE.filter(p=>p.unopposed_2026===true);
  const unver = PEOPLE.filter(p=>p.clean_2026===null && p.unopposed_2026!==true);
  const word = state.preset==='strict' ? 'verified clean' : 'not dirty';
  document.getElementById('stats').innerHTML =
    '<div class="stat"><b>'+PEOPLE.length+'</b>people tracked</div>'
    + '<div class="stat"><b>'+nd.length+' '+word+'</b>in 2026 — '+hND+' House + '+sND+' Senate ('+PRESETS[state.preset].label+' tolerance)</div>'
    + '<div class="stat"><b>'+unopp.length+' ran unopposed</b>in 2026 — no opponent with receipts over $0: '+esc(unopp.map(p=>p.full_name).join(', '))+'</div>'
    + '<div class="stat"><b>'+unver.length+' unverified</b>'+esc(unver.map(p=>p.full_name).join(', '))+'</div>'
    + '<div class="stat"><b>'+fmtCompact(sum('individual_contribution_total_career'))+'</b>individual contributions, career</div>'
    + '<div class="stat"><b>'+fmtCompact(sum('all_ie_total_career'))+'</b>outside spending, 2022–2026</div>'
    + '<div class="stat"><b>'+fmtCompact(sum('self_funding_career'))+'</b>self-funding, career</div>';
}

/* ---- front door vs full-data mode (hash: #explore) ----
   Default (no hash) is the front door; #explore opens the full-data
   workspace. Mode only lives in the URL hash; filters/tabs get no URL
   state (Change 2, queued). No-JS fallback shows the full-data page:
   the hidden flags are applied by init(), never baked into the HTML. */
function modeFromHash(){
  let h = '';
  try{ h = (typeof location!=='undefined' && location.hash) || ''; }catch(e){ h = ''; }
  return h.replace(/^#/,'')==='explore' ? 'explore' : 'front';
}
function setMode(mode, updateHash){
  state.mode = mode;
  const front = mode==='front';
  document.getElementById('front-door').hidden = !front;
  document.getElementById('explore-head').hidden = front;
  document.getElementById('tabs-nav').hidden = front;
  document.getElementById('main').hidden = front;
  document.querySelector('footer').hidden = front;
  if(updateHash!==false){
    try{ if(typeof location!=='undefined'){ location.hash = front ? '' : 'explore'; } }catch(e){}
  }
  // One return control (U1): the masthead title is the way back to the
  // front door, so a mode change also moves the reader there — scroll
  // to the top and focus the new region. Only on user-initiated
  // transitions: hashchange / back-forward pass updateHash===false and
  // must not scroll (the browser restores the position).
  if(updateHash!==false){
    try{ if(typeof window!=='undefined' && typeof window.scrollTo==='function') window.scrollTo(0,0); }catch(e){}
    const target = front ? document.querySelector('header h1') : document.getElementById('tabs-nav');
    if(target && typeof target.focus==='function') target.focus();
  }
}

/* ---- scrollytelling reveals ----
   Chapters reveal as the reader scrolls: an IntersectionObserver adds
   .in when a chapter enters view; CSS transitions do the work (fade +
   slight rise). The hidden-before-reveal state lives under html.js
   only (see the stylesheet), so with JS disabled — or if the observer
   never fires — every chapter is fully visible. prefers-reduced-motion
   reveals everything instantly with no animation (the stylesheet kills
   the transitions). No scroll-jacking, no pinned sections, no parallax. */
function reducedMotion(){
  try{
    return typeof window!=='undefined' && window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }catch(e){ return false; }
}
function revealChapter(el){
  el.classList.add('in');
  el.querySelectorAll('.countup').forEach(runCountUp);
}
function initReveals(){
  const chapters = Array.prototype.slice.call(
    document.querySelectorAll('.chapter'));
  if(!chapters.length) return;
  if(reducedMotion() || typeof IntersectionObserver==='undefined'){
    chapters.forEach(revealChapter);
    return;
  }
  const io = new IntersectionObserver(entries=>{
    entries.forEach(en=>{
      if(en.isIntersecting){ revealChapter(en.target); io.unobserve(en.target); }
    });
  }, {threshold: 0.12, rootMargin: '0px 0px -6% 0px'});
  chapters.forEach(ch=>io.observe(ch));
}

/* ---- count-up numbers (headline figures) ----
   A .countup span carries its computed target in data-value and its
   formatter in data-format; the span's initial text IS the final
   formatted value, so the figure is correct even if the animation
   never runs. On reveal, the number animates from 0 to the target
   and lands on the exact formatted figure. Reduced motion (or no
   requestAnimationFrame) skips the animation and keeps the final
   text. */
function formatCountUp(v, format){
  if(format==='int') return String(Math.round(v));
  if(format==='money') return fmtMoney(v);
  return fmtCompact(v);
}
function runCountUp(el){
  if(el.getAttribute('data-counted')) return;
  el.setAttribute('data-counted','1');
  const target = parseFloat(el.getAttribute('data-value'));
  const format = el.getAttribute('data-format')||'compact';
  const finalText = formatCountUp(target, format);
  if(reducedMotion() || typeof requestAnimationFrame==='undefined'){
    el.textContent = finalText;
    return;
  }
  const start = performance.now(), dur = 900;
  (function frame(now){
    const t = Math.min(1, (now-start)/dur);
    const eased = 1-Math.pow(1-t,3);
    el.textContent = formatCountUp(target*eased, format);
    if(t<1) requestAnimationFrame(frame);
    else el.textContent = finalText;
  })(start);
}

/* ---- tabs + init ---- */
function showTab(name){
  if(state.mode!=='explore') setMode('explore');
  state.tab = name;
  document.querySelectorAll('.tabs button').forEach(b=>b.setAttribute('aria-selected', String(b.getAttribute('data-tab')===name)));
  ['tracker','leaders','clean','breakdown','targets','targets28','method'].forEach(t=>{
    document.getElementById('tab-'+t).hidden = (t!==name);
  });
  if(!state.rendered[name]){
    state.rendered[name]=true;
    if(name==='leaders') renderLeaders();
    if(name==='clean') renderClean();
    if(name==='breakdown') renderBreakdown();
    if(name==='targets') renderTargets();
    if(name==='targets28') renderTargets2028();
  }
  // Tab change: top of the page, focus on the panel.
  try{ if(typeof window!=='undefined' && typeof window.scrollTo==='function') window.scrollTo(0,0); }catch(e){}
  const panel = document.getElementById('tab-'+name);
  if(panel && typeof panel.focus==='function') panel.focus();
}
function init(){
  // Gate the hidden-before-reveal state on JS actually running: no-JS
  // never gets the .js class, so every chapter stays visible.
  try{ if(document.documentElement && document.documentElement.classList) document.documentElement.classList.add('js'); }catch(e){}
  const states = [...new Set(PEOPLE.map(p=>p.state))].sort();
  document.getElementById('f-state').innerHTML = '<option value="all">All states</option>'
    + states.map(s=>'<option value="'+esc(s)+'">'+esc(s)+'</option>').join('');
  renderStats(); renderDirtiest(); renderDirtyExplainer(); renderCleanStory(); renderComposition(); initFinder(); renderViewBtns(); renderTable();
  initReveals();
  state.rendered.tracker = true;
  setMode(modeFromHash(), false);
  document.getElementById('home-link').addEventListener('click', e=>{
    e.preventDefault();
    setMode('front');
  });
  document.getElementById('explore-btn').addEventListener('click', ()=>setMode('explore'));
  document.getElementById('targets28-btn').addEventListener('click', ()=>showTab('targets28'));
  if(typeof window!=='undefined' && typeof window.addEventListener==='function'){
    window.addEventListener('hashchange', ()=>setMode(modeFromHash(), false));
  }
  document.getElementById('q').addEventListener('input', e=>{ state.q=e.target.value; renderTable(); });
  document.getElementById('f-congress').addEventListener('change', e=>{ state.congress=e.target.value; renderTable(); });
  document.getElementById('f-chamber').addEventListener('change', e=>{ state.chamber=e.target.value; renderTable(); });
  document.getElementById('f-party').addEventListener('change', e=>{ state.party=e.target.value; renderTable(); });
  document.getElementById('f-state').addEventListener('change', e=>{ state.state=e.target.value; renderTable(); });
  document.getElementById('f-leader').addEventListener('change', e=>{ state.leadership=e.target.checked; renderTable(); });
  document.getElementById('f-clean').addEventListener('change', e=>{ state.clean=e.target.checked; renderTable(); });
  document.getElementById('f-tolerance').addEventListener('change', e=>{ setPreset(e.target.value); });
  document.getElementById('tolerance-note').textContent = PRESETS[state.preset].def;
  document.getElementById('csv-btn').addEventListener('click', downloadCsv);
  document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click', ()=>showTab(b.getAttribute('data-tab'))));
  document.getElementById('detail').addEventListener('click', e=>{ if(e.target.id==='detail') closeDetail(); });
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDetail(); });
}
init();
</script>
</body>
</html>
"""

METHOD_HTML = """
<h3>How to read this page</h3>
<p>One row per person — 664 people, the union of the 119th Congress (540 served) and the incoming 120th (535 named). Career columns cover FEC cycles 1980–2026. “Total accepted” is the headline career figure: <b>individual contributions + corporate PAC money + AIPAC PAC direct</b>. Everything else is shown separately and never added into it.</p>
<h3>Definitions</h3>
<ul>
<li><b>Individual contributions</b> — itemized + unitemized contributions from individuals to the person’s campaign(s) (FEC weball <code>TTL_INDIV_CONTRIB</code>).</li>
<li><b>Corporate PAC</b> — direct contributions from corporate-connected PACs: committee type Q/N and org type C/W in the same cycle’s committee-master file. Trade, labor, membership, cooperative and hybrid PACs are excluded; they live in the “Other committees” view.</li>
<li><b>AIPAC PAC direct (headline)</b> — total Schedule B disbursements from the AIPAC PAC (C00797670), 2022–2026: the PAC’s own money <i>plus</i> earmarked individual checks transmitted through it. The earmark part is broken out separately — subtract it to get PAC own-money ($7,376,200 career vs $7,567,773 headline). Earmarked money is also inside the individual-contributions column (it is individuals’ money); never add the two columns together.</li>
<li><b>UDP support / benefit</b> — United Democracy Project (C00799031) independent expenditures, 2022–2026. Support is spending <i>for</i> the candidate; benefit adds opposition credit — UDP spending <i>against</i> a candidate’s opponent, credited only when UDP backed exactly one candidate in that race. This is money spent <i>about</i> a race, never given to the campaign, and it is never part of total accepted. UDP spending <i>against</i> a person is never netted; it is noted on their row.</li>
<li><b>Self-funding</b> — candidate contributions + candidate loans (weball). Top: Rick Scott $89.99M, Darrell Issa $27.88M, David McCormick $22.09M, Pete Ricketts $19.44M, Shri Thanedar $17.46M, Anthony Constantino $17.00M.</li>
<li><b>Topline</b> — total receipts and disbursements (career sums), cash on hand and debts owed (latest cycle’s value — a stock, not a sum). Debts <i>owed to</i> the committee are null for everyone: no weball column carries them.</li>
<li><b>Other committees</b> — contributions from committees that are not corporate PACs and not the AIPAC PAC, classified by committee type: party, leadership, labor, trade, membership, cooperative, unclassified. Career total $1,568,735,747.</li>
<li><b>All independent expenditures</b> — every registered committee’s spending for/against the person, 2022–2026 only (the 2010–2020 IE files are not staged). Career total $3,842,257,481 (support $1.49B / oppose $2.35B). Filtered to registered committees + identified candidates: IE files contain tens of billions in bogus filings, and the excluded amounts are documented in methodology.md §4/§8.</li>
</ul>
<h3>Clean in 2026</h3>
<p>Zero corporate PAC money, zero AIPAC PAC direct money, and zero UDP benefit in the 2026 cycle. <b>%%CLEAN_TOTAL_120%% verified clean in the incoming 120th: %%HOUSE_CLEAN%% House (%%HOUSE_CLEAN_D%% D, %%HOUSE_CLEAN_R%% R) + %%SEN_CLEAN%% Senate (%%SEN_CLEAN_D%% D, %%SEN_CLEAN_I%% I, %%SEN_CLEAN_R%% R).</b> %%CLEAN_HOUSE_R_SENTENCE%% A member is <b>unverified</b> only if they have no 2026 entries in <i>any</i> money source — %%UNVERIFIED_SENTENCE%% %%UNOPPOSED_SENTENCE%% %%CAREER_CLEAN_HOUSE%% incoming House members are career-clean (no corporate PAC, AIPAC direct, UDP support, or UDP opposition credit in any cycle).</p>
<h3>Corporate PAC tolerance presets</h3>
<p>Dirty money always includes any AIPAC PAC direct dollar and any UDP benefit dollar — that flag (%%FLAG_120%% of the incoming 120th) is not tolerance-based and is always on. Corporate PAC money counts as dirty under a tolerance preset: <b>Strict</b> — any net dirty dollar above $0 is dirty (the verified-clean count is in the paragraph above); <b>Balanced (default)</b> — corporate PAC over $100,000 and over 5% of 2026 receipts (%%BALANCED_NOT_DIRTY%% of 535 not dirty); <b>Lenient</b> — corporate PAC over $250,000 and over 10% of 2026 receipts (%%LENIENT_NOT_DIRTY%% of 535 not dirty). The middle tier — “Below threshold” — took corporate PAC money below the preset’s thresholds; it is never called clean, and the dollar amount is always shown. The full definitions are in methodology.md §14, which wins if this page ever disagrees.</p>
<h3>Coverage end dates</h3>
<table><thead><tr><th>Column family</th><th>Source</th><th>Coverage ends</th></tr></thead><tbody>
<tr><td>Individual, self-funding, topline</td><td>weball</td><td>Oct 14, 2026</td></tr>
<tr><td>Corporate PAC, AIPAC, other committees</td><td>pas2</td><td>Sep 30, 2026</td></tr>
<tr><td>UDP + all independent expenditures</td><td>IE bulk files</td><td>Oct 31, 2026</td></tr>
</tbody></table>
<p>2026 is partial. Re-pull plan: mid-Dec 2026 (after the Dec 3 post-general deadline) and Feb 2027 (after the Jan 31 year-end deadline). A freshness layer reports late money (Form 6 48-Hour Notices, F24 24/48-hour IE) between pulls; it is never merged into these totals.</p>
<h3>Known limitations — read before quoting a number</h3>
<ul>
<li><b>2026 is partial</b> (see cutoffs above). Do not compare 2026 figures head-to-head with full cycles.</li>
<li><b>Elaine Luria is unverified, not clean and not dirty</b> — her real 2026 campaign (H6VA02198, $8.04M receipts) is unlinked; linking it is a roster change.</li>
<li><b>Melissa Bean and Hilda Solis</b> show $0 individual contributions in 2026 alongside real corporate PAC money — a missing-committee-linkage gap, not a real zero.</li>
<li><b>Alan Armstrong</b> (appointed senator, never ran) has no FEC record: all money cells read “unknown,” not zero, and he is unranked.</li>
<li><b>All-IE “career” means 2022–2026 only.</b> The 2010–2020 IE files are not staged.</li>
<li><b>Weball is a lower bound where the FEC API runs ahead</b> (Constantino: weball loans $14.4M vs API $17M). The freshness layer closes that gap for late money.</li>
<li><b>Weball double-count corrected:</b> where weball repeats an identical individual-contribution total under a chamber-switcher’s House and Senate IDs in the same cycle, it is counted once ($451,776,015.34 across 32 persons).</li>
<li><b>UDP reconciliation:</b> the deduped 2024 UDP total is $38,044,932.69 vs OpenSecrets’ $37,860,200 (+0.49%, unresolved).</li>
<li><b>16 people who served in the 119th but left before Nov 2026 are excluded</b> (Vance, Rubio, Graham, D. Scott, Turner, Grijalva, Connolly, Green, Sherrill, Greene, LaMalfa, Gonzales, Swalwell, Cherfilus-McCormick, Mullin, Waltz). 5 seats are TBD/uncalled; 120th results are media calls, uncertified; 120th leadership is TBD (elections Nov 18–19, 2026).</li>
<li><b>Opposition credit is conservative:</b> race = cycle + office + state + district + election phase (primary / general / other, from the filing's ele_type — expenditure dates are blank on UDP rows, so no date split is possible); credit only when UDP backed exactly one candidate in that phase of the race.</li>
</ul>
<h3>Sources &amp; reproducibility</h3>
<p>FEC bulk files are the source of truth for every figure; the FEC API was used for spot-checks; OpenSecrets is a cross-check only. The full method, reconciliation tables, and every limitation are in <a href="https://github.com/craigSochocki/the-receipts/blob/master/methodology.md">methodology.md</a>. The pipeline that builds this dataset is scripted (<code>python3 src/rebuild.py</code>) and reproduces the committed dataset byte-identically; this page is generated from that dataset (plus the race-level opposition-credit record in <code>data/intermediate/opposition-computed.json</code>, shown in the drill-down) by <code>src/site/build_site.py</code> — never hand-edited.</p>
"""


def human_list(names):
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} and {names[1]}'
    return ', '.join(names[:-1]) + f', and {names[-1]}'


def is_career_clean(r):
    """Same four-component rule as the site's isCareerClean."""
    return (r['corporate_pac_career'] == 0 and r['aipac_pac_direct_career'] == 0
            and r['udp_ie_support_career'] == 0
            and r['udp_ie_opposing_opponents_career'] == 0)


def clean_method_html(dataset):
    """The methodology clean paragraph, computed from the dataset.

    Every figure in the paragraph is computed here — never hardcoded —
    so a data change cannot strand stale numbers in the live page.
    Tokens are replaced in main(); verify_site.py fails the build if
    any %%TOKEN%% survives unreplaced.
    """
    incoming = [r for r in dataset if r['in_120th'] == 'yes']
    house = [r for r in incoming if r['chamber_120'] == 'House']
    sen = [r for r in incoming if r['chamber_120'] == 'Senate']
    h_clean = [r for r in house if r['clean_2026'] is True]
    s_clean = [r for r in sen if r['clean_2026'] is True]
    h_r = [r['full_name'] for r in h_clean if r['party_120'] == 'Republican']
    if h_r:
        n = len(h_r)
        r_sentence = (f"The {n} clean House Republican{'s are' if n > 1 else ' is'} "
                      f"{human_list(h_r)}.")
    else:
        r_sentence = "No House Republican is verified clean."
    unver = [r['full_name'] for r in dataset
             if r['clean_2026'] is None and not r['unopposed_2026']]
    if len(unver) == 1:
        unver_sentence = f"{unver[0]} is the one unverified member."
    elif unver:
        unver_sentence = f"{len(unver)} members are unverified: {human_list(unver)}."
    else:
        unver_sentence = "No member is unverified."
    excluded = [r['full_name'] for r in dataset
                if r['unopposed_2026'] and r['clean_2026'] is None]
    if excluded:
        n = len(excluded)
        unopp_sentence = (f"{n} {'members ran' if n > 1 else 'member ran'} unopposed in 2026 — "
                          f"no opponent with receipts over $0 — so $0 dirty money there is not "
                          f"counted as verified-clean: {human_list(excluded)}.")
    else:
        unopp_sentence = "No member ran unopposed in 2026."
    tokens = {
        '%%CLEAN_TOTAL_120%%': str(len(h_clean) + len(s_clean)),
        '%%HOUSE_CLEAN%%': str(len(h_clean)),
        '%%HOUSE_CLEAN_D%%': str(sum(1 for r in h_clean if r['party_120'] == 'Democrat')),
        '%%HOUSE_CLEAN_R%%': str(len(h_r)),
        '%%SEN_CLEAN%%': str(len(s_clean)),
        '%%SEN_CLEAN_D%%': str(sum(1 for r in s_clean if r['party_120'] == 'Democrat')),
        '%%SEN_CLEAN_I%%': str(sum(1 for r in s_clean if r['party_120'] == 'Independent')),
        '%%SEN_CLEAN_R%%': str(sum(1 for r in s_clean if r['party_120'] == 'Republican')),
        '%%CLEAN_HOUSE_R_SENTENCE%%': r_sentence,
        '%%UNVERIFIED_SENTENCE%%': unver_sentence,
        '%%UNOPPOSED_SENTENCE%%': unopp_sentence,
        '%%CAREER_CLEAN_HOUSE%%': str(sum(1 for r in house if is_career_clean(r))),
        '%%BALANCED_NOT_DIRTY%%': str(sum(1 for r in incoming
                                          if r['tier_balanced_2026'] in ('clean', 'below_threshold'))),
        '%%LENIENT_NOT_DIRTY%%': str(sum(1 for r in incoming
                                         if r['tier_lenient_2026'] in ('clean', 'below_threshold'))),
        '%%FLAG_120%%': str(sum(1 for r in incoming if r['aipac_udp_flag_2026'] is True)),
    }
    html = METHOD_HTML
    for token, value in tokens.items():
        html = html.replace(token, value)
    return html


def main():
    dataset = json.loads(DATASET_JSON.read_text())
    if not isinstance(dataset, list):
        raise SystemExit("dataset JSON is not a list")
    with open(DATASET_CSV, newline="") as f:
        csv_cols = next(csv.reader(f))
    missing = [k for k in SCALARS if k not in dataset[0]]
    if missing:
        raise SystemExit(f"dataset rows missing scalar fields: {missing}")
    rows = [encode_row(r) for r in dataset]
    opp_payload = build_opp_payload()
    cols_payload = {
        "scalars": SCALARS,
        "pc": PC_COLS, "upc": UPC_COLS, "sf": SF_COLS,
        "oc": OC_COLS, "aie": AIE_COLS, "tc": TC_COLS,
        "csv": csv_cols,
    }
    dataset_md5 = hashlib.md5(DATASET_JSON.read_bytes()).hexdigest()
    data_as_of = sorted({r.get("data_as_of", "") for r in dataset})
    # Visible data-as-of stamp (header). Coverage end dates come from
    # config.yaml verification.coverage_end — never hardcoded here.
    # The build time reuses the exact "Generated <ts>" string the footer
    # uses, so the verifier's strip_ts regex normalizes both occurrences
    # and the generator stays deterministic apart from that timestamp.
    coverage = CFG["verification"]["coverage_end"]
    def fmt_cov(iso):
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d, %Y")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stamp = (
        "Data as of \u2014 committee money through "
        f"{fmt_cov(coverage['committee_money_pas2'])}; "
        "individual / self-funding / topline through "
        f"{fmt_cov(coverage['weball'])}; "
        "independent expenditures through "
        f"{fmt_cov(coverage['independent_expenditures'])}. "
        f"2026 is partial. Generated {generated_at}."
    )
    # Front-door freshness line: one line, from the same config dates —
    # the latest coverage end across families, never a typed date.
    fresh_line = (
        "Data through "
        f"{fmt_cov(max(coverage.values()))}"
        " \u2014 2026 is partial. Full coverage dates in the methodology."
    )
    html = TEMPLATE_HEAD + TEMPLATE_BODY + TEMPLATE_JS2
    html = html.replace("%%METHOD_HTML%%", clean_method_html(dataset))
    html = html.replace("%%COLS_JSON%%", safe_json(cols_payload))
    html = html.replace("%%DATA_JSON%%", safe_json(rows))
    html = html.replace("%%OPP_JSON%%", safe_json(opp_payload))
    html = html.replace("%%DATASET_MD5%%", dataset_md5)
    html = html.replace("%%DATA_AS_OF%%", ", ".join(data_as_of))
    html = html.replace("%%STAMP%%", stamp)
    html = html.replace("%%FRESH_LINE%%", fresh_line)
    html = html.replace("%%GENERATED_AT%%", generated_at)
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    out = SITE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"rows: {len(rows)}")
    print(f"dataset md5: {dataset_md5}")
    print(f"embedded payload bytes: {len(safe_json(rows))}")
    print(f"opposition detail: {len(opp_payload)} persons, "
          f"{sum(len(v) for v in opp_payload.values())} race-phases")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
