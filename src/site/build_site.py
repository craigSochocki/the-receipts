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
    "in_119th", "in_120th", "fec_candidate_ids",
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
    "udp_opp_credit_2026", "udp_benefit_2026", "dirty_2026", "clean_2026",
    "dep_share_2026", "self_funding_2026", "cand_loans_2026",
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
</style>
</head>
<body>
<header>
<h1>The Receipts</h1>
<p class="sub">Every person in Congress and the money behind them — from FEC filings, not press releases. Career totals, 2026 clean/dirty flags, self-funding, and outside spending.</p>
<p class="stamp">%%STAMP%%</p>
<div class="stats" id="stats"></div>
<p class="cutoffs"><b>2026 is partial.</b> Committee money (corporate PAC, AIPAC, other committees) through <b>Sep 30, 2026</b>; individual / self-funding / topline through <b>Oct 14, 2026</b>; independent expenditures through <b>Oct 31, 2026</b>. Post-general reports are due Dec 3, 2026; year-end reports Jan 31, 2027.</p>
</header>
<nav class="tabs" role="tablist" aria-label="Views">
<button role="tab" aria-selected="true" data-tab="tracker">Tracker</button>
<button role="tab" aria-selected="false" data-tab="leaders">Leaderboards</button>
<button role="tab" aria-selected="false" data-tab="clean">Clean money</button>
<button role="tab" aria-selected="false" data-tab="breakdown">Party breakdown</button>
<button role="tab" aria-selected="false" data-tab="targets">2026 primary targets</button>
<button role="tab" aria-selected="false" data-tab="method">Methodology</button>
</nav>
<main>
"""
TEMPLATE_BODY = """
<section id="tab-tracker">
<div class="controls">
<input type="search" id="q" placeholder="Search by name…" aria-label="Search by name">
<select id="f-congress" aria-label="Congress"><option value="all">Everyone</option><option value="119">119th only</option><option value="120">120th only</option><option value="both">In both</option></select>
<select id="f-chamber" aria-label="Chamber"><option value="all">House + Senate</option><option value="House">House</option><option value="Senate">Senate</option></select>
<select id="f-party" aria-label="Party"><option value="all">All parties</option><option value="Democrat">Democrat</option><option value="Republican">Republican</option><option value="Independent">Independent</option><option value="PPD">PPD</option></select>
<select id="f-state" aria-label="State"><option value="all">All states</option></select>
<label><input type="checkbox" id="f-leader"> Leadership only</label>
<label><input type="checkbox" id="f-clean"> Clean in 2026 only</label>
<button class="btn" id="csv-btn" type="button">Download CSV</button>
</div>
<div class="viewbtns" id="viewbtns" role="group" aria-label="Column views"></div>
<div class="totals" id="totals"></div>
<div class="tablewrap"><table id="main-table"><thead></thead><tbody></tbody></table></div>
<p id="showing" style="color:var(--muted);font-size:.88rem"></p>
</section>

<section id="tab-leaders" hidden>
<h2 class="sec">Leaderboards</h2>
<p style="color:var(--muted)">Career totals unless noted. Rank 1 = most money. “Total accepted” is individual contributions + corporate PAC + AIPAC PAC direct. Outside spending is never part of total accepted — it is money spent <i>about</i> a race, never given to the campaign.</p>
<div id="leaders"></div>
</section>

<section id="tab-clean" hidden>
<h2 class="sec">Clean money</h2>
<div id="clean-stats"></div>
<div class="callout"><b>What “clean in 2026” means:</b> zero corporate PAC money, zero AIPAC PAC direct money, and zero UDP benefit (support + opposition credit) in the 2026 cycle. It is a cycle test, not a career test — a member can be clean in 2026 while having taken such money in earlier cycles. A member is shown as <b>unverified</b> only if they have no 2026 entries in <i>any</i> money source; Elaine Luria is the one unverified member — her real 2026 campaign is not linked in the roster yet.</div>
<div class="tablewrap"><table id="clean-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-breakdown" hidden>
<h2 class="sec">Party-by-chamber breakdown — 120th Congress</h2>
<p style="color:var(--muted)">Members of the incoming 120th Congress, grouped by party and chamber. Money columns are career totals; the clean column counts verified-clean members in 2026.</p>
<div class="tablewrap"><table id="breakdown-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-targets" hidden>
<h2 class="sec">2026 primary targets — House Democrats, by dirty money in 2026</h2>
<p style="color:var(--muted)">192 House Democrats in the incoming 120th took dirty money in 2026 (corporate PAC + AIPAC direct + UDP benefit). Dirty money is money from sources other than individual contributors; individual contributions are not dirty money. 2026 figures are partial (see cutoffs above).</p>
<div class="tablewrap"><table id="targets-table"><thead></thead><tbody></tbody></table></div>
</section>

<section id="tab-method" class="method" hidden>
<h2 class="sec">Methodology</h2>
<p style="color:var(--muted)">Condensed from <a href="https://github.com/craigSochocki/the-receipts/blob/master/methodology.md">methodology.md</a> in the repo, which is the authoritative version. If this page and methodology.md ever disagree on a number, methodology.md wins.</p>
%%METHOD_HTML%%
</section>
</main>
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
function fmtClean(p){
  if(p.clean_2026===true) return '<span class="badge clean">Clean</span>';
  if(p.clean_2026===null) return '<span class="badge unver">Unverified</span>';
  return '<span class="badge dirty">Not clean</span>';
}

/* ---- derived fields ---- */
function place(p){
  const d = p.district_120!==''&&p.district_120!=null ? p.district_120 : p.district_119;
  if(p.chamber_120==='Senate'||p.chamber_119==='Senate') return p.state+' · Senate';
  return p.state+(d!==''&&d!=null ? '-'+d : '');
}
function party(p){ return p.party_120||p.party_119||'—'; }
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
    {k:'chamber',label:'Chamber',type:'chamber'},
    {k:'congress',label:'Congress',type:'congress'},
    {k:'individual_contribution_total_career',label:'Individual (career)',type:'money'},
    {k:'corporate_pac_career',label:'Corp PAC (career)',type:'money'},
    {k:'aipac_pac_direct_career',label:'AIPAC direct (career)',type:'money'},
    {k:'total_accepted_career',label:'Total accepted',type:'money'},
    {k:'rank_total_accepted',label:'Rank',type:'rank'},
    {k:'dirty_2026',label:'Dirty 2026',type:'money'},
    {k:'clean_2026',label:'Clean 2026',type:'clean'}]},
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
    {k:'clean_2026',label:'Clean 2026',type:'clean'}]},
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
  leadership:false, clean:false, view:'core',
  sortKey:'total_accepted_career', sortDir:'desc', tab:'tracker', rendered:{}};

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
    if(state.clean && p.clean_2026!==true) return false;
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
    case 'money': {
      const t = fmtMoney(v);
      return '<span title="'+esc(t)+'">'+fmtCompact(v)+'</span>';
    }
    case 'pct': return fmtPct(v);
    case 'rank': return fmtRank(v);
    case 'clean': return fmtClean(p);
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
  h += '<p class="meta">'+esc(party(p))+' · '+esc(chamber(p))+' · '+esc(place(p))+' · '+esc(congressLabel(p))
    + (leader ? ' · '+esc(leader) : '') + ' · FEC ID'+(p.fec_candidate_ids.length>1?'s':'')+': '
    + esc(p.fec_candidate_ids.join(', ')||'none') + '</p>';
  h += '<h3>Career money</h3><div class="kv">'
    + kvRow('Individual contributions', fmtMoney(p.individual_contribution_total_career)+' ('+fmtRank(p.rank_individual)+')')
    + kvRow('Corporate PAC', fmtMoney(p.corporate_pac_career)+' ('+fmtRank(p.rank_corporate_pac)+')')
    + kvRow('AIPAC PAC direct', fmtMoney(p.aipac_pac_direct_career)+' ('+fmtRank(p.rank_aipac_direct)+')')
    + kvRow('— of which earmarked (individuals’ money, passed through)', fmtMoney(p.aipac_earmark_transmitted_career))
    + kvRow('Total accepted', '<b>'+fmtMoney(p.total_accepted_career)+'</b> ('+fmtRank(p.rank_total_accepted)+')')
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
    + kvRow('Clean in 2026', fmtClean(p))
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
    .map(p=>({name:p.full_name, who:party(p)+' · '+place(p), amount:p[amountKey]}));
}
function boardHtml(title, sub, entries){
  let h = '<h3>'+esc(title)+'</h3><p style="color:var(--muted);font-size:.9rem">'+esc(sub)+'</p><ol class="leader">';
  entries.forEach((e,i)=>{
    h += '<li><span><b>'+(i+1)+'.</b> '+esc(e.name)+' <span class="who">'+esc(e.who)+'</span></span><span class="amt">'+fmtMoney(e.amount)+'</span></li>';
  });
  return h + '</ol>';
}
function renderLeaders(){
  document.getElementById('leaders').innerHTML =
    boardHtml('Top 20 — total accepted (career)', 'Individual contributions + corporate PAC + AIPAC PAC direct. Rank 1 = most money accepted.',
      topByRank('rank_total_accepted','total_accepted_career',20))
    + boardHtml('Top 10 — UDP total benefit (career)', 'UDP spending supporting the candidate plus opposition credit for spending against their opponent. Money spent about the race, never given to the campaign.',
      topByRank('rank_udp_total_benefit','udp_ie_total_benefit_career',10))
    + boardHtml('Top 10 — self-funding (career)', 'Candidate contributions + candidate loans. The candidate’s own money.',
      topByRank('rank_self_funding','self_funding_career',10))
    + boardHtml('Top 10 — all independent expenditures (career, 2022–2026)', 'All outside spending for and against the candidate, every registered committee — not just UDP.',
      topByRank('rank_all_ie_total','all_ie_total_career',10));
}

/* ---- clean view ---- */
function renderClean(){
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const hHouse = incoming.filter(p=>p.chamber_120==='House'&&p.clean_2026===true);
  const hSen = incoming.filter(p=>p.chamber_120==='Senate'&&p.clean_2026===true);
  const careerCleanHouse = incoming.filter(p=>p.chamber_120==='House'&&isCareerClean(p));
  const clean = PEOPLE.filter(p=>p.clean_2026===true);
  const unver = PEOPLE.filter(p=>p.clean_2026===null);
  document.getElementById('clean-stats').innerHTML =
    '<div class="stats">'
    + '<div class="stat"><b>'+hHouse.length+' of 436</b>incoming House verified clean in 2026</div>'
    + '<div class="stat"><b>'+hSen.length+' of 99</b>incoming Senate verified clean in 2026</div>'
    + '<div class="stat"><b>'+(hHouse.length+hSen.length)+' total</b>verified clean in the incoming 120th</div>'
    + '<div class="stat"><b>'+careerCleanHouse.length+'</b>career-clean incoming House members</div>'
    + '<div class="stat"><b>'+unver.length+' unverified</b>'+esc(unver.map(p=>p.full_name).join(', '))+'</div>'
    + '</div>'
    + '<p style="color:var(--muted)">'+clean.length+' people in the whole tracker are clean in 2026 — the 77 above plus '
    + (clean.length-hHouse.length-hSen.length) + ' outgoing 119th-only members. Click a row for the full breakdown.</p>';
  const thead = document.querySelector('#clean-table thead');
  const tbody = document.querySelector('#clean-table tbody');
  thead.innerHTML = '<tr><th>Name</th><th>State / Dist.</th><th>Party</th><th>Chamber</th><th>Incoming 120th?</th><th class="num">Corp PAC (career)</th><th class="num">AIPAC (career)</th><th class="num">UDP support (career)</th><th class="num">Dirty 2026</th><th>Career-clean?</th></tr>';
  const rows = clean.slice().sort((a,b)=>a.full_name.localeCompare(b.full_name));
  tbody.innerHTML = rows.map(p=>'<tr data-key="'+p.person_key+'"><td class="name">'+esc(p.full_name)+'</td><td>'+esc(place(p))+'</td><td>'+esc(party(p))+'</td><td>'+esc(chamber(p))+'</td><td>'+(p.in_120th==='yes'?'Yes':'No — 119th only')+'</td><td class="num">'+fmtCompact(p.corporate_pac_career)+'</td><td class="num">'+fmtCompact(p.aipac_pac_direct_career)+'</td><td class="num">'+fmtCompact(p.udp_ie_support_career)+'</td><td class="num">'+fmtCompact(p.dirty_2026)+'</td><td>'+(isCareerClean(p)?'Yes':'No')+'</td></tr>').join('');
  tbody.querySelectorAll('tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- party breakdown ---- */
function renderBreakdown(){
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
    if(p.clean_2026===true) g.clean++;
  });
  const rows = Object.values(groups).sort((a,b)=>b.n-a.n);
  const tot = {n:0,ind:0,corp:0,aipac:0,tot:0,udp:0,self:0,ie:0,clean:0};
  rows.forEach(g=>{ tot.n+=g.n; tot.ind+=g.ind; tot.corp+=g.corp; tot.aipac+=g.aipac; tot.tot+=g.tot; tot.udp+=g.udp; tot.self+=g.self; tot.ie+=g.ie; tot.clean+=g.clean; });
  const rowHtml = g=>'<tr><td>'+esc(g.party)+'</td><td>'+esc(g.chamber)+'</td><td class="num">'+g.n+'</td><td class="num">'+fmtCompact(g.ind)+'</td><td class="num">'+fmtCompact(g.corp)+'</td><td class="num">'+fmtCompact(g.aipac)+'</td><td class="num">'+fmtCompact(g.tot)+'</td><td class="num">'+fmtCompact(g.udp)+'</td><td class="num">'+fmtCompact(g.self)+'</td><td class="num">'+fmtCompact(g.ie)+'</td><td class="num">'+g.clean+'</td></tr>';
  document.querySelector('#breakdown-table thead').innerHTML =
    '<tr><th>Party</th><th>Chamber</th><th class="num">Members</th><th class="num">Individual (career)</th><th class="num">Corp PAC (career)</th><th class="num">AIPAC (career)</th><th class="num">Total accepted</th><th class="num">UDP benefit</th><th class="num">Self-funding</th><th class="num">All IE total</th><th class="num">Clean 2026</th></tr>';
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
  const cleanH = incoming.filter(p=>p.chamber_120==='House'&&p.clean_2026===true).length;
  const cleanS = incoming.filter(p=>p.chamber_120==='Senate'&&p.clean_2026===true).length;
  const sum = k => PEOPLE.reduce((s,p)=>s+(num(p[k])||0),0);
  const unver = PEOPLE.filter(p=>p.clean_2026===null);
  document.getElementById('stats').innerHTML =
    '<div class="stat"><b>'+PEOPLE.length+'</b>people tracked</div>'
    + '<div class="stat"><b>'+(cleanH+cleanS)+' verified clean</b>in 2026 — '+cleanH+' House + '+cleanS+' Senate</div>'
    + '<div class="stat"><b>'+unver.length+' unverified</b>'+esc(unver.map(p=>p.full_name).join(', '))+'</div>'
    + '<div class="stat"><b>'+fmtCompact(sum('individual_contribution_total_career'))+'</b>individual contributions, career</div>'
    + '<div class="stat"><b>'+fmtCompact(sum('all_ie_total_career'))+'</b>outside spending, 2022–2026</div>'
    + '<div class="stat"><b>'+fmtCompact(sum('self_funding_career'))+'</b>self-funding, career</div>';
}

/* ---- tabs + init ---- */
function showTab(name){
  state.tab = name;
  document.querySelectorAll('.tabs button').forEach(b=>b.setAttribute('aria-selected', String(b.getAttribute('data-tab')===name)));
  ['tracker','leaders','clean','breakdown','targets','method'].forEach(t=>{
    document.getElementById('tab-'+t).hidden = (t!==name);
  });
  if(!state.rendered[name]){
    state.rendered[name]=true;
    if(name==='leaders') renderLeaders();
    if(name==='clean') renderClean();
    if(name==='breakdown') renderBreakdown();
    if(name==='targets') renderTargets();
  }
}
function init(){
  const states = [...new Set(PEOPLE.map(p=>p.state))].sort();
  document.getElementById('f-state').innerHTML = '<option value="all">All states</option>'
    + states.map(s=>'<option value="'+esc(s)+'">'+esc(s)+'</option>').join('');
  renderStats(); renderViewBtns(); renderTable();
  state.rendered.tracker = true;
  document.getElementById('q').addEventListener('input', e=>{ state.q=e.target.value; renderTable(); });
  document.getElementById('f-congress').addEventListener('change', e=>{ state.congress=e.target.value; renderTable(); });
  document.getElementById('f-chamber').addEventListener('change', e=>{ state.chamber=e.target.value; renderTable(); });
  document.getElementById('f-party').addEventListener('change', e=>{ state.party=e.target.value; renderTable(); });
  document.getElementById('f-state').addEventListener('change', e=>{ state.state=e.target.value; renderTable(); });
  document.getElementById('f-leader').addEventListener('change', e=>{ state.leadership=e.target.checked; renderTable(); });
  document.getElementById('f-clean').addEventListener('change', e=>{ state.clean=e.target.checked; renderTable(); });
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
<p>Zero corporate PAC money, zero AIPAC PAC direct money, and zero UDP benefit in the 2026 cycle. <b>77 verified clean in the incoming 120th: 67 House (63 D, 4 R) + 10 Senate (9 D, 1 I, 0 R).</b> The four clean House Republicans are Anthony Constantino, Mark Lamb, Kimberlyn King-Hinds, and Amata Radewagen. A member is <b>unverified</b> only if they have no 2026 entries in <i>any</i> money source — Elaine Luria is the one unverified member; her real 2026 campaign is not linked in the roster yet. 53 incoming House members are career-clean (no corporate PAC, AIPAC direct, UDP support, or UDP opposition credit in any cycle).</p>
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
    html = TEMPLATE_HEAD + TEMPLATE_BODY + TEMPLATE_JS2
    html = html.replace("%%METHOD_HTML%%", METHOD_HTML)
    html = html.replace("%%COLS_JSON%%", safe_json(cols_payload))
    html = html.replace("%%DATA_JSON%%", safe_json(rows))
    html = html.replace("%%OPP_JSON%%", safe_json(opp_payload))
    html = html.replace("%%DATASET_MD5%%", dataset_md5)
    html = html.replace("%%DATA_AS_OF%%", ", ".join(data_as_of))
    html = html.replace("%%STAMP%%", stamp)
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
