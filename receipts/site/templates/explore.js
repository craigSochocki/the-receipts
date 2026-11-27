"use strict";
/* ---- Explore: the news app at /explore ----
   Refactored from tracker.js + views.js (master at fbd7a37): the decode,
   cycle, tier and drill-down logic is carried over; the front-door
   story, the finder and the mode/hash scheme are gone. Explore is its
   own page, so filter state lives in the query string (?q=&chamber=...),
   the drawer opens via ?member=<person_key>, and #search focuses the
   search field. The default table order is the grouped order
   (House section, then Senate; party blocks; flagged first inside
   their party's block) — an explicit sort replaces it and is labelled.
   Five default columns; everything else is a column-chooser extra or
   a drill-down. */

/* ---- decode ---- */
const COLS = JSON.parse(document.getElementById('receipts-cols').textContent);
const RAW = JSON.parse(document.getElementById('receipts-data').textContent);
const OPP = JSON.parse(document.getElementById('opp-data').textContent);
const PHASE_LABEL = {P:'Primary', G:'General', O:'Other'};
const NS = COLS.scalars.length;
function mkobj(cols, arr){ const o={}; cols.forEach((k,i)=>{ o[k]=arr[i]; }); return o; }
const PEOPLE = RAW.map(a=>{
  const o={}; COLS.scalars.forEach((k,i)=>{ o[k]=a[i]; });
  // Nested lists stay positional until a drill-down (or the CSV
  // export) needs them — decodeNested maps them to named objects
  // on demand, so first paint skips 664 people's cycle detail.
  o.per_cycle=a[NS]||[];
  o.udp_per_cycle=a[NS+1]||[];
  o.self_funding_per_cycle=a[NS+2]||[];
  o.other_committees_per_cycle=a[NS+3]||[];
  o.all_ie_per_cycle=a[NS+4]||[];
  o.all_ie_top_committees=a[NS+5]||[];
  o.cycles=(a[NS+6]||[]).map(e=>mkobj(COLS.cy, e));
  o.pro_israel_per_cycle=a[NS+7]||[];
  return o;
});
const BY_KEY = {}; PEOPLE.forEach(p=>{ BY_KEY[p.person_key]=p; });

/* ---- the selected cycle ----
   Every view reads one cycle's figures through the cy_* fields, which
   applyCycle copies from the person's record for state.cycle. 'latest'
   is each person's headline verdict: their latest election. */
const CURRENT_CYCLE = COLS.current_cycle;
const IE_SPAN = COLS.ie_span;
const CYCLE_FIELDS = COLS.cy.filter(k=>k!=='cycle' && k!=='up_for_election');
const NO_RECORD = {clean:null, tier_balanced:null, tier_lenient:null, dep_share:null,
  cash_on_hand:null, unopposed:false, aipac_udp_flag:false};
// The latest election's cycle and every cycle since, as one record
// (receipts/domain/term.py is the rule; this mirrors it).
const NOT_SUMMED = new Set(['cycle','clean','unopposed','aipac_udp_flag','tier_balanced',
  'tier_lenient','dep_share','cash_on_hand','up_for_election']);
const round2 = x=>Math.round(x*100)/100;
function termRecord(p){
  const since = p.cycles.filter(c=>c.cycle>=p.verdict_cycle).sort((a,b)=>a.cycle-b.cycle);
  if(p.verdict_cycle===null || !since.length) return {};
  const t = {cycle:p.verdict_cycle, unopposed:since[0].unopposed, cash_on_hand:since[since.length-1].cash_on_hand};
  Object.keys(since[0]).forEach(k=>{ if(!NOT_SUMMED.has(k)) t[k] = round2(since.reduce((s,c)=>s+(c[k]||0),0)); });
  const accepted = t.individual+t.corp+t.aipac_direct;
  t.dep_share = accepted>0 ? Math.round((t.corp+t.aipac_direct)/accepted*10000)/10000 : null;
  t.aipac_udp_flag = t.aipac_direct>0 || t.udp_benefit>0;
  return t;
}
function cycleRecord(p, cycle){
  if(cycle==='latest'){
    return Object.assign(termRecord(p), {clean:p.clean, dirty:p.dirty,
      tier_balanced:p.tier_balanced, tier_lenient:p.tier_lenient});
  }
  return p.cycles.find(c=>c.cycle===cycle) || {};
}
const CYCLE_CHOICES = ['latest', ...COLS.picker_cycles];
const cycleValue = v=>(v==='latest' ? v : Number(v));
const isCycleChoice = c=>CYCLE_CHOICES.indexOf(c)>=0;
// The selected cycle in words: CY heads columns, IN_CY reads in prose.
let CY = '', IN_CY = '';
function applyCycle(cycle){
  CY = cycle==='latest' ? 'latest' : String(cycle);
  IN_CY = cycle==='latest' ? 'since their last election' : 'in '+cycle;
  PEOPLE.forEach(p=>{
    const r = cycleRecord(p, cycle);
    CYCLE_FIELDS.forEach(k=>{
      p['cy_'+k] = (k in r) ? r[k] : (k in NO_RECORD ? NO_RECORD[k] : 0);
    });
    p.cy_cycle = (r.cycle===undefined) ? null : r.cycle;
  });
}
applyCycle('latest');

/* ---- lazy-decode nested lists ----
   Each nested list is a positional array until decoded; decodeNested
   maps it to named objects once and caches the result on the person,
   so a second drill-down (or the CSV export) pays nothing. */
const NESTED_MAP = {per_cycle:'pc', udp_per_cycle:'upc', self_funding_per_cycle:'sf', other_committees_per_cycle:'oc', all_ie_per_cycle:'aie', all_ie_top_committees:'tc', pro_israel_per_cycle:'pi'};
function decodeNested(p){
  Object.keys(NESTED_MAP).forEach(k=>{
    if(Array.isArray(p[k]) && p[k].length && Array.isArray(p[k][0])){
      p[k] = p[k].map(e=>mkobj(COLS[NESTED_MAP[k]], e));
    }
  });
  return p;
}

/* ---- formatting ---- */
function num(v){ return (typeof v==='number' && isFinite(v)) ? v : null; }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
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
   Strict is cy_clean itself (any net dirty dollar above $0 is
   dirty); Balanced / Lenient read the stored tier columns. The
   AIPAC/UDP flag is not tolerance-based: any AIPAC direct or UDP
   benefit dollar flags the member under every preset, and a flagged
   member is dirty under every preset. The middle tier is never
   called clean, and its dollar amount (cy_corp) is always shown.
   Default is Balanced. */
const PRESETS = {
  strict:{label:'Strict',
    def:'Strict: any net dirty dollar above $0 is dirty.',
    short:'any dirty dollar counts'},
  balanced:{label:'Balanced',
    def:'Balanced (default): corporate PAC counts as dirty only over $100,000 and over 5% of the cycle’s receipts; any AIPAC direct or UDP benefit dollar always counts.',
    short:'corporate PAC over $100k and over 5% of receipts'},
  lenient:{label:'Lenient',
    def:'Lenient: corporate PAC counts as dirty only over $250,000 and over 10% of the cycle’s receipts; any AIPAC direct or UDP benefit dollar always counts.',
    short:'corporate PAC over $250k and over 10% of receipts'}
};
function tierOf(p){
  if(state.preset==='strict')
    return p.cy_clean===true ? 'clean' : (p.cy_clean===null ? null : 'dirty');
  return state.preset==='lenient' ? p.cy_tier_lenient : p.cy_tier_balanced;
}
function isNotDirty(p){ const t=tierOf(p); return t==='clean'||t==='below_threshold'; }
function flagBadge(p){
  if(p.cy_aipac_udp_flag!==true) return '';
  return ' <span class="badge flag" title="Took AIPAC PAC direct money or UDP benefit '+IN_CY+' — flagged under every tolerance preset">AIPAC/UDP</span>';
}
function fmtTierBadge(p){
  const t = tierOf(p);
  if(t===null)
    return p.cy_unopposed===true ? '<span class="badge unopp">Unopposed</span>'
      : '<span class="badge unver">Unverified</span>';
  if(t==='clean') return '<span class="badge clean">Clean</span>';
  if(t==='below_threshold')
    return '<span class="badge below">Below threshold · '+fmtMoney(p.cy_corp)+'</span>';
  return '<span class="badge dirty">Dirty</span>'+flagBadge(p);
}
/* The plain-English rule behind one member's verdict (mirrors
   receipts/site/explore_data.py verdict_reason). Shown in the drawer
   beside the verdict, so a verdict never reads as an accusation. */
function verdictReason(p){
  const t = tierOf(p);
  if(t===null)
    return p.cy_unopposed===true
      ? 'Unopposed: no opponent raised money, so no dirty money here is not a clean verdict.'
      : 'Unverified: no linked campaign filed money, so there is nothing to judge.';
  if(p.cy_aipac_udp_flag===true)
    return 'Flagged: took AIPAC PAC direct money or UDP benefit money. Any such dollar flags a member under every preset.';
  if(t==='dirty')
    return 'Dirty under the '+PRESETS[state.preset].label+' tolerance: '+PRESETS[state.preset].short+'.';
  if(t==='below_threshold')
    return 'Below threshold under the '+PRESETS[state.preset].label+' tolerance: took corporate PAC money, but below the dirty line ('+PRESETS[state.preset].short+'). Below threshold is never called clean, and the amount is shown.';
  return 'Clean: took no net dirty money — no corporate PAC, AIPAC PAC direct, or UDP benefit money in the term judged.';
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
const byDirty = (a,b)=>num(b.cy_dirty)-num(a.cy_dirty);
const CYCLE_ID = [{k:'cycle',label:'Cycle',type:'text'}, {k:'candidate_id',label:'Candidate ID',type:'text'}];
/* The incoming members not dirty under the current preset, by chamber. */
function notDirtyCounts(){
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const nd = incoming.filter(isNotDirty);
  return {incoming, nd,
    hND: nd.filter(p=>p.chamber_120==='House').length,
    sND: nd.filter(p=>p.chamber_120==='Senate').length};
}

/* ---- money format: compact / exact ----
   Compact is the default ($1.23M); Exact shows dollars and cents
   ($1,234,567.89). The choice persists in localStorage; the guards
   keep it working where storage is unavailable. The toggle governs
   the Explore data views (table, totals strip, clean, breakdown);
   the leaderboards and targets show exact figures, and the drill-down
   always shows exact figures. */
function loadMoneyFmt(){
  try{
    if(typeof localStorage!=='undefined'){
      const v = localStorage.getItem('receipts-money-fmt');
      if(v==='exact' || v==='compact') return v;
    }
  }catch(e){}
  return 'compact';
}
function saveMoneyFmt(fmt){
  try{
    if(typeof localStorage!=='undefined') localStorage.setItem('receipts-money-fmt', fmt);
  }catch(e){}
}
function moneyShort(v){
  return state.moneyFmt==='exact' ? fmtMoney(v) : fmtCompact(v);
}

/* ---- state ---- */
const state = {q:'', congress:'all', chamber:'all', party:'all', flag:'all',
  source:'all', state:'all', preset:'balanced', moneyFmt:loadMoneyFmt(),
  sortKey:'grouped', sortDir:'desc', view:'table', page:1, pageSize:25,
  extraCols:[], cycle:'latest'};
const PAGE_SIZES = [25, 50, 100];
// The drill-down's person key, when the drawer is open (it lives in
// the URL as ?member=, so Back closes the drawer).
let detailKey = null;

/* ---- columns: five defaults, the rest by chooser ----
   Member carries name + state/district + party dot; Verdict carries
   the tier badge; Total is total accepted (individual + corporate
   PAC + AIPAC direct, career). */
const DEFAULT_COLS = [
  {k:'member', label:'Member', type:'member'},
  {k:'verdict', label:'Verdict', type:'verdict'},
  {k:'total_accepted_career', label:'Total', type:'money'},
  {k:'aipac_pac_direct_career', label:'AIPAC $', type:'money'},
  {k:'corporate_pac_career', label:'Corporate PAC $', type:'money'},
];
const EXTRA_COLS = [
  {k:'individual_contribution_total_career', label:'Individual $', type:'money'},
  {k:'cy_dirty', label:'Dirty', type:'money', cycle:true},
  {k:'cy_udp_benefit', label:'UDP benefit', type:'money', cycle:true},
  {k:'self_funding_career', label:'Self-funding', type:'money'},
  {k:'total_receipts_career', label:'Total receipts', type:'money'},
  {k:'cash_on_hand_career', label:'Cash on hand', type:'money'},
  {k:'rank_total_accepted', label:'Rank (total accepted)', type:'rank'},
  {k:'outcome', label:'Outcome', type:'outcome'},
  {k:'congress', label:'Congress', type:'congress'},
];
function colLabel(c){ return c.cycle ? c.label+' '+CY : c.label; }
function currentCols(){
  return DEFAULT_COLS.concat(EXTRA_COLS.filter(c=>state.extraCols.indexOf(c.k)>=0));
}
const SORTABLE = new Set(['member', 'verdict',
  ...DEFAULT_COLS.filter(c=>['money','rank'].includes(c.type)).map(c=>c.k),
  ...EXTRA_COLS.filter(c=>['money','rank'].includes(c.type)).map(c=>c.k)]);
/* Tier order for sorting the Verdict column: dirty first. */
const TIER_RANK = {dirty:0, below_threshold:1, clean:2};
function tierRank(p){ const t=tierOf(p); return t===null ? 3 : TIER_RANK[t]; }

function getVal(p, key){
  if(key==='member') return p.full_name;
  if(key==='verdict') return tierRank(p);
  if(key==='place') return place(p);
  if(key==='party') return party(p);
  if(key==='chamber') return chamber(p);
  if(key==='congress') return congressLabel(p);
  if(key==='outcome') return outcomeLabel(p);
  return p[key];
}
function cmpVal(a, b, dir){
  const an = num(a), bn = num(b);
  if(an===null && bn===null) return 0;
  if(an===null) return 1;   // null / unknown always sorts last
  if(bn===null) return -1;
  return dir==='asc' ? an-bn : bn-an;
}
/* ---- search relevance ----
   Name first (starts-with, then contains), then state / district,
   then party / chamber. -1 means no match. */
function matchScore(p, q){
  if(!q) return -1;
  const name = p.full_name.toLowerCase();
  if(name.startsWith(q)) return 0;
  if(name.includes(q)) return 1;
  if(p.state.toLowerCase()===q || (STATE_NAMES[p.state]||'').toLowerCase().includes(q)) return 2;
  if(place(p).toLowerCase().includes(q)) return 2;
  if(party(p).toLowerCase().includes(q)) return 3;
  if(chamber(p).toLowerCase().includes(q)) return 3;
  return -1;
}
function applyFilters(){
  const q = state.q.trim().toLowerCase();
  return PEOPLE.filter(p=>{
    if(q && matchScore(p,q)<0) return false;
    if(state.congress==='119' && p.in_119th!=='yes') return false;
    if(state.congress==='120' && p.in_120th!=='yes') return false;
    if(state.congress==='both' && !(p.in_119th==='yes'&&p.in_120th==='yes')) return false;
    if(state.chamber!=='all' && !(p.chamber_119===state.chamber||p.chamber_120===state.chamber)) return false;
    if(state.party!=='all' && !(p.party_119===state.party||p.party_120===state.party)) return false;
    if(state.state!=='all' && p.state!==state.state) return false;
    if(state.flag==='flagged' && p.cy_aipac_udp_flag!==true) return false;
    if(state.flag==='clean' && !isNotDirty(p)) return false;
    if(state.source==='aipac' && !(num(p.cy_aipac_direct)>0)) return false;
    if(state.source==='corporate' && !(num(p.cy_corp)>0)) return false;
    if(state.source==='udp' && !(num(p.cy_udp_benefit)>0)) return false;
    if(state.source==='individual' && !(num(p.cy_individual)>0 && num(p.cy_corp)===0 && num(p.cy_aipac_direct)===0 && num(p.cy_udp_benefit)===0)) return false;
    return true;
  });
}
/* ---- the grouped default order (mirrors explore_data.grouped_order) ----
   House rows as one section, then Senate rows — never interleaved.
   Inside a section, each party sits together (Democrats, then
   Republicans, then Independents, then others), flagged members at
   the head of their party's block, then by dirty money, then by name.
   Members with no chamber sit after both sections. */
const CHAMBER_RANK = {House:0, Senate:1};
const PARTY_RANK = {Democrat:0, Republican:1, Independent:2};
function groupedCmp(a, b){
  const ca = CHAMBER_RANK[chamber(a)] ?? 2, cb = CHAMBER_RANK[chamber(b)] ?? 2;
  if(ca!==cb) return ca-cb;
  const pa = PARTY_RANK[party(a)] ?? 3, pb = PARTY_RANK[party(b)] ?? 3;
  if(pa!==pb) return pa-pb;
  const fa = a.cy_aipac_udp_flag===true ? 0 : 1, fb = b.cy_aipac_udp_flag===true ? 0 : 1;
  if(fa!==fb) return fa-fb;
  const d = cmpVal(b.cy_dirty, a.cy_dirty, 'desc');
  return d!==0 ? d : a.full_name.localeCompare(b.full_name);
}
function groupedOrder(rows){
  return rows.slice().sort(groupedCmp);
}
function sortRows(rows){
  const k = state.sortKey, dir = state.sortDir;
  const q = state.q.trim().toLowerCase();
  if(k==='grouped' && !q) return groupedOrder(rows);
  return rows.slice().sort((a,b)=>{
    // Relevance ranking only while a query is active: best match
    // first, then the current sort order within a relevance band.
    if(q){
      const sa = matchScore(a,q), sb = matchScore(b,q);
      if(sa!==sb) return sa-sb;
    }
    if(k==='grouped') return groupedCmp(a, b);
    const av = getVal(a,k), bv = getVal(b,k);
    if(typeof av==='string' || typeof bv==='string'){
      const as = String(av==null?'':av), bs = String(bv==null?'':bv);
      return dir==='asc' ? as.localeCompare(bs) : bs.localeCompare(as);
    }
    const c = cmpVal(av, bv, dir);
    return c!==0 ? c : a.full_name.localeCompare(b.full_name);
  });
}
/* ---- pagination: 25 rows a page by default, 25/50/100 offered ----
   paginateRows is pure (rows, page, size) so the tests pin it without
   the DOM; pageLabel is the "Showing A–B of N" line. */
function paginateRows(rows, page, size){
  const start = (page-1)*size;
  return rows.slice(start, start+size);
}
function pageLabel(total, page, size){
  if(total===0) return 'Showing 0 of 0';
  const first = (page-1)*size+1, last = Math.min(total, page*size);
  return 'Showing '+first+'–'+last+' of '+total;
}
function pageCount(total, size){ return Math.max(1, Math.ceil(total/size)); }

const STATE_NAMES = {AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',CO:'Colorado',CT:'Connecticut',DE:'Delaware',DC:'District of Columbia',FL:'Florida',GA:'Georgia',HI:'Hawaii',ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',KS:'Kansas',KY:'Kentucky',LA:'Louisiana',ME:'Maine',MD:'Maryland',MA:'Massachusetts',MI:'Michigan',MN:'Minnesota',MS:'Mississippi',MO:'Missouri',MT:'Montana',NE:'Nebraska',NV:'Nevada',NH:'New Hampshire',NJ:'New Jersey',NM:'New Mexico',NY:'New York',NC:'North Carolina',ND:'North Dakota',OH:'Ohio',OK:'Oklahoma',OR:'Oregon',PA:'Pennsylvania',RI:'Rhode Island',SC:'South Carolina',SD:'South Dakota',TN:'Tennessee',TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',WV:'West Virginia',WI:'Wisconsin',WY:'Wyoming',AS:'American Samoa',GU:'Guam',MP:'Northern Mariana Islands',PR:'Puerto Rico',VI:'U.S. Virgin Islands'};
const TERRITORIES = new Set(['AS','GU','MP','PR','VI','DC']);
function isVotingHouse(p){ return p.chamber_120==='House' && !TERRITORIES.has(p.state); }

/* ---- overview strip (Step 1) ----
   One panel per chamber, never combined: total raised, flagged
   count/share, top source total — then a static waffle per chamber
   with party and flagged groups kept together in blocks. House
   waffle plots voting seats only; the territorial delegates are
   listed under it, and uncalled seats fill the chamber to its size. */
const HOUSE_SEATS = 435, SENATE_SEATS = 100;
function chamberStats(members){
  const sum = k => members.reduce((s,p)=>s+(num(p[k])||0),0);
  const families = [
    ['individual', sum('individual_contribution_total_career')],
    ['corporate PAC', sum('corporate_pac_career')],
    ['AIPAC direct', sum('aipac_pac_direct_career')],
    ['UDP benefit', sum('udp_ie_total_benefit_career')],
  ];
  const top = families.reduce((a,b)=>b[1]>a[1]?b:a);
  const flagged = members.filter(p=>p.cy_aipac_udp_flag===true).length;
  return {total: sum('total_accepted_career'), flagged, top, members: members.length};
}
function waffleHtml(members, seats, cols, id){
  // Blocks in display order: each party's flagged members first,
  // then its unflagged members, then unjudged, then uncalled.
  const order = ['Democrat','Republican','Independent'];
  const blocks = [];
  order.forEach(name=>{
    const group = members.filter(p=>party(p)===name);
    const judged = group.filter(p=>tierOf(p)!==null);
    blocks.push(...judged.filter(p=>p.cy_aipac_udp_flag===true).map(()=>({cls:'dem', flag:true, party:name})));
    blocks.push(...judged.filter(p=>p.cy_aipac_udp_flag!==true).map(()=>({cls:'dem', flag:false, party:name})));
  });
  const others = members.filter(p=>order.indexOf(party(p))<0);
  blocks.push(...others.filter(p=>p.cy_aipac_udp_flag===true).map(()=>({cls:'ind', flag:true, party:party(p)})));
  blocks.push(...others.filter(p=>p.cy_aipac_udp_flag!==true).map(()=>({cls:'ind', flag:false, party:party(p)})));
  const unjudged = members.filter(p=>tierOf(p)===null).length;
  for(let i=0;i<unjudged;i++) blocks.push({cls:'unjudged', flag:false, party:''});
  const uncalled = seats - members.length;
  for(let i=0;i<uncalled;i++) blocks.push({cls:'uncalled', flag:false, party:''});
  const clsFor = b=>{
    if(b.cls==='uncalled') return 'uncalled';
    if(b.cls==='unjudged') return 'unjudged';
    const base = b.party==='Democrat' ? 'dem' : b.party==='Republican' ? 'rep' : 'ind';
    return base + (b.flag ? ' flagged' : '');
  };
  return '<div id="'+id+'" class="waffle-grid '+(cols>=29?'house':'senate')+'" role="img" aria-label="Waffle chart: each dot is one member, grouped by party with flagged members first in their party block">'
    + blocks.map(b=>'<i class="'+clsFor(b)+'"></i>').join('') + '</div>';
}
function renderOverview(){
  const el = document.getElementById('explore-overview');
  if(!el) return;
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const panels = [['House', incoming.filter(isVotingHouse), incoming.filter(p=>p.chamber_120==='House' && !isVotingHouse(p)), HOUSE_SEATS, 29],
    ['Senate', incoming.filter(p=>p.chamber_120==='Senate'), [], SENATE_SEATS, 20]];
  el.innerHTML = panels.map(([name, members, delegates, seats, cols])=>{
    const s = chamberStats(members.concat(name==='House' ? delegates : []));
    const share = s.members ? Math.round(s.flagged/s.members*1000)/10 : 0;
    return '<article class="overview-panel"><div class="chamber-head"><span class="ch-name">'+name+'</span><span class="ch-count">'+members.length+' named members</span></div>'
      + '<div class="overview-stats">'
      + '<div class="overview-stat"><span>Total raised</span><b>'+fmtCompact(s.total)+'</b></div>'
      + '<div class="overview-stat"><span>Flagged</span><b>'+s.flagged+' · '+share+'%</b></div>'
      + '<div class="overview-stat"><span>Top source</span><b>'+esc(s.top[0])+' · '+fmtCompact(s.top[1])+'</b></div>'
      + '</div>'
      + waffleHtml(members, seats, cols, 'waffle-'+name.toLowerCase())
      + '<p class="waffle-legend"><span><b class="dot dem"></b>Democrat</span><span><b class="dot dem flagged"></b>Democrat, flagged — lighter blue</span><span><b class="dot rep"></b>Republican</span><span><b class="dot rep flagged"></b>Republican, flagged — lighter red</span><span><b class="dot unjudged"></b>Not judged</span><span><b class="dot uncalled"></b>Uncalled seat</span></p>'
      + (delegates.length ? '<p class="delegates-note">Non-voting delegates not plotted: '+esc(delegates.map(p=>p.full_name).join(', '))+'. Total raised and flagged counts above cover all '+esc(name)+' members, delegates included.</p>' : '')
      + '<p class="src">Source: FEC filings. Career totals; flagged means any AIPAC direct or UDP benefit dollar since the last election.</p></article>';
  }).join('');
}

/* ---- hemicycle view ----
   Re-implemented from the story's House arc (story.js hemicycle):
   seats on concentric rows, filled left to right with Democrats,
   others, then Republicans, each party's flagged seats first. Two
   hemicycles, one per chamber; party seats grouped in their arc.
   Uncalled seats are hollow placeholders at the arc's end. */
const HEMI_W = 600, HEMI_H = 340;
const EXPLORE_PARTY_SIDE = {Democrat:0, Republican:2};
function explorePartySide(p){ return EXPLORE_PARTY_SIDE[party(p)] ?? 1; }
const EXPLORE_STATUS_ORDER = {dirty:0, below_threshold:1, clean:2, unjudged:3};
function hemiStatus(p){ return tierOf(p) || 'unjudged'; }
function hemiByStatus(a, b){
  return EXPLORE_STATUS_ORDER[hemiStatus(a)]-EXPLORE_STATUS_ORDER[hemiStatus(b)] || num(b.cy_dirty)-num(a.cy_dirty);
}
function hemicycleLayout(people, cx, cy, inner, outer, rows){
  const radii = Array.from({length: rows}, (_, i)=>inner+(outer-inner)*i/(rows-1));
  const total = radii.reduce((s, r)=>s+r, 0);
  const counts = radii.map(r=>Math.floor(people.length*r/total));
  counts[rows-1] += people.length - counts.reduce((s, c)=>s+c, 0);
  const seats = [];
  radii.forEach((r, i)=>{
    for(let j=0; j<counts[i]; j++){
      const a = Math.PI*(1 - j/Math.max(1, counts[i]-1));
      seats.push({x: cx+r*Math.cos(a), y: cy-r*Math.sin(a), a});
    }
  });
  seats.sort((s, t)=>t.a-s.a || s.y-t.y);
  // Uncalled placeholder seats sort last, at the arc's end.
  const order = people.slice().sort((a, b)=>
    ((a.uncalled?1:0)-(b.uncalled?1:0)) || explorePartySide(a)-explorePartySide(b) || hemiByStatus(a, b));
  const at = {};
  order.forEach((p, i)=>{ at[p.person_key] = seats[i]; });
  return {at, order};
}
function hemiDotClass(p){
  const side = explorePartySide(p)===0 ? 'party-d' : explorePartySide(p)===2 ? 'party-r' : 'party-o';
  return 'hemi-dot dot-'+hemiStatus(p)+' '+side+(p.cy_aipac_udp_flag===true ? ' flagged' : '');
}
function renderHemicycle(){
  const svgH = document.getElementById('hemi-house');
  const svgS = document.getElementById('hemi-senate');
  const note = document.getElementById('hemicycle-note');
  if(!svgH || !svgS) return;
  const incoming = PEOPLE.filter(p=>p.in_120th==='yes');
  const panels = [
    [svgH, incoming.filter(isVotingHouse), HOUSE_SEATS, 12, 110, 290],
    [svgS, incoming.filter(p=>p.chamber_120==='Senate'), SENATE_SEATS, 6, 130, 290],
  ];
  panels.forEach(([svg, members, seats, rows, inner, outer])=>{
    const uncalled = seats - members.length;
    const all = members.concat(Array.from({length: uncalled}, (_, i)=>({person_key:'__uncalled_'+i, uncalled:true})));
    const {at, order} = hemicycleLayout(all, HEMI_W/2, HEMI_H-30, inner, outer, rows);
    const dots = order.map(p=>{
      const pos = at[p.person_key];
      if(p.uncalled) return '<circle class="hemi-dot dot-uncalled" cx="'+pos.x.toFixed(1)+'" cy="'+pos.y.toFixed(1)+'" r="5.5"><title>Uncalled seat</title></circle>';
      return '<circle class="'+hemiDotClass(p)+'" cx="'+pos.x.toFixed(1)+'" cy="'+pos.y.toFixed(1)+'" r="5.5" data-key="'+esc(p.person_key)+'"><title>'+esc(p.full_name)+'</title></circle>';
    }).join('');
    svg.innerHTML = dots + '<text class="arc-count" x="'+(HEMI_W/2)+'" y="'+(HEMI_H-34)+'" text-anchor="middle">'+members.length+'</text>';
  });
  if(note){
    const h = incoming.filter(isVotingHouse).length, s = incoming.filter(p=>p.chamber_120==='Senate').length;
    note.textContent = 'House: '+h+' named voting members plus '+(HOUSE_SEATS-h)+' uncalled seats; Senate: '+s+' named senators plus '+(SENATE_SEATS-s)+' uncalled seat. Non-voting delegates are not plotted.';
  }
}

/* ---- table ----
   Five default columns; the frozen first column is the member, the
   header sticks, text is left-aligned and numbers right-aligned with
   tabular figures (see explore.css). Sorting is explicit: clicking a
   sortable header replaces the grouped order, and the showing line
   says which order is in force. */
function cellHtml(p, col){
  const v = getVal(p, col.k);
  switch(col.type){
    case 'member':
      return '<button type="button" class="name-btn" data-key="'+esc(p.person_key)+'">'+esc(p.full_name)+'</button>'
        + '<span class="member-sub">'+esc(place(p))+' · '+partyChip(p)+' '+esc(party(p))+'</span>';
    case 'verdict': return fmtTierBadge(p);
    case 'party': return partyChip(p) || '—';
    case 'outcome': return outcomeLabel(p);
    case 'money': {
      const t = fmtMoney(v);
      return '<span title="'+esc(t)+'">'+moneyShort(v)+'</span>';
    }
    case 'pct': return fmtPct(v);
    case 'rank': return fmtRank(v);
    default: return esc(v==null||v===''?'—':v);
  }
}
function renderSkeletons(){
  const tbody = document.getElementById('explore-tbody');
  if(!tbody) return;
  const cols = currentCols().length;
  tbody.innerHTML = Array.from({length: state.pageSize}, ()=>
    '<tr class="skeleton-row" aria-hidden="true">'+('<td><span class="skeleton"></span></td>').repeat(cols)+'</tr>').join('');
}
function renderTable(){
  const thead = document.getElementById('explore-thead');
  const tbody = document.getElementById('explore-tbody');
  if(!thead || !tbody) return;
  const cols = currentCols();
  thead.innerHTML = '<tr>'+cols.map(c=>{
    const arrow = state.sortKey===c.k ? (state.sortDir==='asc'?' ▲':' ▼') : '';
    const sortable = SORTABLE.has(c.k) ? ' data-sort="'+c.k+'"' : '';
    const ariaSort = SORTABLE.has(c.k) ? ' aria-sort="'+(state.sortKey===c.k ? (state.sortDir==='asc'?'ascending':'descending') : 'none')+'"' : '';
    const cls = (c.type==='money'||c.type==='pct'||c.type==='rank') ? ' class="num"' : '';
    return '<th'+cls+sortable+ariaSort+'>'+esc(colLabel(c))+arrow+'</th>';
  }).join('')+'</tr>';
  thead.querySelectorAll('th[data-sort]').forEach(th=>{
    th.addEventListener('click', ()=>{
      const k = th.getAttribute('data-sort');
      if(state.sortKey===k) state.sortDir = state.sortDir==='asc'?'desc':'asc';
      else { state.sortKey=k; state.sortDir='desc'; }
      state.page = 1;
      renderTable();
    });
  });
  const rows = sortRows(applyFilters());
  const total = rows.length;
  const pages = pageCount(total, state.pageSize);
  if(state.page > pages) state.page = pages;
  const pageRows = paginateRows(rows, state.page, state.pageSize);
  const empty = document.getElementById('table-empty');
  if(total===0){
    tbody.innerHTML = '';
    if(empty) empty.hidden = false;
  } else {
    if(empty) empty.hidden = true;
    tbody.innerHTML = pageRows.map(p=>'<tr data-key="'+esc(p.person_key)+'">'+cols.map(c=>{
      const cls = c.type==='member' ? ' class="name"' : ((c.type==='money'||c.type==='pct'||c.type==='rank') ? ' class="num"' : '');
      return '<td'+cls+'>'+cellHtml(p,c)+'</td>';
    }).join('')+'</tr>').join('');
  }
  // Totals strip + footer for the filtered set: the sums depend only
  // on which rows the filters select, not on their sort order or page,
  // so the filter state is the cache key.
  const totalsKey = [state.cycle, state.q, state.congress, state.chamber, state.party, state.flag, state.source, state.state].join('|');
  let totals = totalsCache[totalsKey];
  if(!totals){
    const sum = k => rows.reduce((s,p)=>s+(num(p[k])||0),0);
    const t = [
      ['People', rows.length],
      ['Individual', moneyShort(sum('individual_contribution_total_career'))],
      ['Corp PAC', moneyShort(sum('corporate_pac_career'))],
      ['AIPAC direct', moneyShort(sum('aipac_pac_direct_career'))],
      ['Total accepted', moneyShort(sum('total_accepted_career'))],
      ['UDP benefit', moneyShort(sum('udp_ie_total_benefit_career'))],
      ['Self-funding', moneyShort(sum('self_funding_career'))],
      ['All IE total', moneyShort(sum('all_ie_total_career'))]
    ];
    totals = {
      strip: t.map(x=>'<div class="t">'+esc(x[0])+'<b>'+esc(x[1])+'</b></div>').join(''),
      foot: 'Filtered set totals — individual '+fmtMoney(sum('individual_contribution_total_career'))
        +' · corporate PAC '+fmtMoney(sum('corporate_pac_career'))
        +' · AIPAC direct '+fmtMoney(sum('aipac_pac_direct_career'))
        +' · total accepted '+fmtMoney(sum('total_accepted_career'))
        +' · UDP benefit '+fmtMoney(sum('udp_ie_total_benefit_career'))
        +' · self-funding '+fmtMoney(sum('self_funding_career'))
        +' · all IE total '+fmtMoney(sum('all_ie_total_career'))+'.'
    };
    totalsCache[totalsKey] = totals;
  }
  const totalsEl = document.getElementById('totals');
  if(totalsEl) totalsEl.innerHTML = totals.strip;
  const csvBtn = document.getElementById('csv-btn');
  if(csvBtn) csvBtn.textContent = 'Download CSV — '+total+' rows';
  const orderNote = state.sortKey==='grouped'
    ? 'Grouped: House, then Senate, by party — flagged first in each party block.'
    : 'Sorted by '+esc(sortLabel(state.sortKey))+' '+(state.sortDir==='asc'?'↑':'↓')+'. ';
  const showing = document.getElementById('showing');
  if(showing){
    showing.textContent = pageLabel(total, state.page, state.pageSize)+' · '+orderNote;
    if(state.sortKey!=='grouped'){
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'linklike'; b.id = 'sort-reset';
      b.textContent = 'Back to grouped order';
      b.addEventListener('click', ()=>{ state.sortKey='grouped'; state.sortDir='desc'; state.page=1; renderTable(); });
      showing.appendChild(document.createTextNode(' '));
      showing.appendChild(b);
    }
  }
  renderChips();
  const foot = document.getElementById('foot-totals');
  if(foot) foot.textContent = totals.foot;
  renderPagination(total);
  syncUrl(true);
}
const totalsCache = {};
function sortLabel(key){
  if(key==='member') return 'name';
  if(key==='verdict') return 'verdict';
  const col = DEFAULT_COLS.concat(EXTRA_COLS).find(c=>c.k===key);
  return col ? colLabel(col) : key;
}
function renderPagination(total){
  const pages = pageCount(total, state.pageSize);
  const prev = document.getElementById('page-prev');
  const next = document.getElementById('page-next');
  const list = document.getElementById('page-list');
  if(prev) prev.disabled = state.page<=1;
  if(next) next.disabled = state.page>=pages;
  if(!list) return;
  // A window of page buttons around the current page, never the
  // whole run: first, last, and two either side of the current page.
  const windowPages = [];
  for(let i=1;i<=pages;i++){
    if(i===1 || i===pages || Math.abs(i-state.page)<=2) windowPages.push(i);
  }
  let html = '', last = 0;
  windowPages.forEach(i=>{
    if(i-last>1) html += '<span class="page-gap">…</span>';
    html += '<button type="button" class="page-btn" data-page="'+i+'" aria-current="'+(i===state.page)+'"'+(i===state.page?' disabled':'')+'>'+i+'</button>';
    last = i;
  });
  list.innerHTML = html;
  list.querySelectorAll('.page-btn').forEach(b=>{
    b.addEventListener('click', ()=>{ state.page = Number(b.getAttribute('data-page')); renderTable(); });
  });
}
function renderChips(){
  const chips = [];
  const q = state.q.trim();
  if(q) chips.push({k:'q', label:'Search: “'+q+'”'});
  if(state.congress!=='all') chips.push({k:'congress', label:'Congress: '+({119:'119th',120:'120th',both:'In both'})[state.congress]});
  if(state.chamber!=='all') chips.push({k:'chamber', label:'Chamber: '+state.chamber});
  if(state.party!=='all') chips.push({k:'party', label:'Party: '+state.party});
  if(state.flag!=='all') chips.push({k:'flag', label: state.flag==='flagged' ? 'Flagged only' : 'Not dirty only'});
  if(state.source!=='all') chips.push({k:'source', label:'Source: '+({aipac:'AIPAC direct', corporate:'corporate PAC', udp:'UDP benefit', individual:'individual only'})[state.source]});
  if(state.state!=='all') chips.push({k:'state', label:'State: '+state.state});
  const el = document.getElementById('filter-chips');
  if(!el) return;
  if(!chips.length){ el.innerHTML=''; return; }
  el.innerHTML = chips.map(c=>'<button type="button" class="chip" data-filter="'+c.k+'" title="Clear this filter">'+esc(c.label)+' ✕</button>').join(' ')
    + ' <button type="button" class="chip reset" id="filters-reset-chip">Clear all</button>';
  el.querySelectorAll('.chip[data-filter]').forEach(b=>{
    b.addEventListener('click', ()=>clearFilter(b.getAttribute('data-filter')));
  });
  const reset = document.getElementById('filters-reset-chip');
  if(reset) reset.addEventListener('click', resetFilters);
}
function clearFilter(k){
  if(k==='q'){ state.q=''; const q=document.getElementById('q'); if(q) q.value=''; }
  if(k==='congress'){ state.congress='all'; const e=document.getElementById('f-congress'); if(e) e.value='all'; }
  if(k==='chamber'){ state.chamber='all'; const e=document.getElementById('f-chamber'); if(e) e.value='all'; }
  if(k==='party'){ state.party='all'; const e=document.getElementById('f-party'); if(e) e.value='all'; }
  if(k==='flag'){ state.flag='all'; const e=document.getElementById('f-flag'); if(e) e.value='all'; }
  if(k==='source'){ state.source='all'; const e=document.getElementById('f-source'); if(e) e.value='all'; }
  if(k==='state'){ state.state='all'; const e=document.getElementById('f-state'); if(e) e.value='all'; }
  state.page = 1;
  renderTable();
}
function resetFilters(){
  state.q=''; state.congress='all'; state.chamber='all'; state.party='all';
  state.flag='all'; state.source='all'; state.state='all';
  state.sortKey='grouped'; state.sortDir='desc'; state.page=1;
  const set = (id, v)=>{ const e=document.getElementById(id); if(e) e.value=v; };
  set('q',''); set('f-congress','all'); set('f-chamber','all'); set('f-party','all');
  set('f-flag','all'); set('f-source','all'); set('f-state','all');
  renderTable();
}
/* ---- column chooser: extra columns, kept in localStorage ---- */
function loadExtraCols(){
  try{
    if(typeof localStorage!=='undefined'){
      const raw = localStorage.getItem('receipts-extra-cols');
      if(raw) return JSON.parse(raw).filter(k=>EXTRA_COLS.some(c=>c.k===k));
    }
  }catch(e){}
  return [];
}
function saveExtraCols(){
  try{
    if(typeof localStorage!=='undefined') localStorage.setItem('receipts-extra-cols', JSON.stringify(state.extraCols));
  }catch(e){}
}
function renderColumnChooser(){
  const list = document.getElementById('column-chooser-list');
  if(!list) return;
  list.innerHTML = EXTRA_COLS.map(c=>
    '<label><input type="checkbox" data-col="'+c.k+'"'+(state.extraCols.indexOf(c.k)>=0?' checked':'')+'> '+esc(colLabel(c))+'</label>').join('');
  list.querySelectorAll('input[data-col]').forEach(box=>{
    box.addEventListener('change', ()=>{
      const k = box.getAttribute('data-col');
      if(box.checked && state.extraCols.indexOf(k)<0) state.extraCols.push(k);
      if(!box.checked) state.extraCols = state.extraCols.filter(x=>x!==k);
      saveExtraCols();
      renderTable();
    });
  });
}
/* ---- search: debounced, with skeletons while the reader types ----
   The debounce is 300 ms; the table shows skeleton rows for that
   window instead of a spinner over a blank page. scheduleSearchRender
   is the testable seam: the input handler calls it, the tests call it. */
const SEARCH_DEBOUNCE_MS = 300;
let searchTimer = null;
function scheduleSearchRender(){
  if(searchTimer) clearTimeout(searchTimer);
  renderSkeletons();
  searchTimer = setTimeout(()=>{ state.page = 1; renderTable(); }, SEARCH_DEBOUNCE_MS);
}

/* ---- leaderboards ---- */
function topByRank(rankKey, amountKey, n){
  return PEOPLE.filter(p=>num(p[rankKey])!==null)
    .sort((a,b)=>a[rankKey]-b[rankKey]).slice(0,n)
    .map(p=>({key:p.person_key, name:p.full_name, who:partyChip(p)+' '+esc(party(p))+' · '+esc(place(p))+' · '+outcomeLabel(p), amount:p[amountKey]}));
}
function boardHtml(title, sub, entries){
  let h = '<h3>'+esc(title)+'</h3><p class="view-intro">'+esc(sub)+'</p><ol class="leader">';
  entries.forEach((e,i)=>{
    h += '<li><button type="button" class="leader-row" data-key="'+esc(e.key)+'"><span><b>'+(i+1)+'.</b> '+esc(e.name)+' <span class="who">'+e.who+'</span></span><span class="amt">'+fmtMoney(e.amount)+'</span></button></li>';
  });
  return h + '</ol>';
}
/* ---- leaderboards: dirty leads ----
   The first two boards are the dirtiness measure (selected cycle, then career);
   total accepted is fundraising scale, not dirtiness, so it comes
   after. The dirty boards sort by amount at render time from the
   embedded data — no rank column is needed for them. */
function topByAmount(amountKey, n){
  return PEOPLE.filter(p=>num(p[amountKey])!==null && num(p[amountKey])>0)
    .sort((a,b)=>num(b[amountKey])-num(a[amountKey])).slice(0,n)
    .map(p=>({key:p.person_key, name:p.full_name, who:partyChip(p)+' '+esc(party(p))+' · '+esc(place(p))+' · '+outcomeLabel(p), amount:p[amountKey]}));
}
function renderLeaders(){
  const el = document.getElementById('leaders');
  if(!el) return;
  el.innerHTML =
    boardHtml('Top 20 — dirtiest '+IN_CY, 'Corporate PAC + AIPAC PAC direct + UDP benefit '+IN_CY+'. Individual contributions are not dirty money.',
      topByAmount('cy_dirty',20))
    + boardHtml('Top 20 — dirtiest, career', 'Career dirty money: corporate PAC + AIPAC PAC direct + UDP benefit, all cycles.',
      topByAmount('dirty_career',20))
    + boardHtml('Top 20 — total accepted (career)', 'Individual contributions + corporate PAC + AIPAC PAC direct. Total accepted measures fundraising scale, not dirtiness — the two lists above are the dirtiness measure.',
      topByRank('rank_total_accepted','total_accepted_career',20))
    + boardHtml('Top 10 — UDP total benefit (career)', 'UDP spending supporting the candidate plus opposition credit for spending against their opponent. Money spent about the race, never given to the campaign.',
      topByRank('rank_udp_total_benefit','udp_ie_total_benefit_career',10))
    + boardHtml('Top 10 — self-funding (career)', 'Candidate contributions + candidate loans. The candidate’s own money.',
      topByRank('rank_self_funding','self_funding_career',10))
    + boardHtml('Top 10 — all independent expenditures (career, '+IE_SPAN+')', 'All outside spending for and against the candidate, every registered committee — not just UDP.',
      topByRank('rank_all_ie_total','all_ie_total_career',10));
  // Leaderboard rows are clickable — one delegated listener, so the
  // rows need no per-row handlers.
  el.addEventListener('click', e=>{
    const b = e.target.closest('.leader-row');
    if(b) openDetail(b.getAttribute('data-key'));
  });
}

/* ---- clean view (preset-aware) ----
   Under Strict the view lists verified-clean members; under Balanced
   / Lenient it lists everyone not dirty under the preset — clean
   plus the below-threshold middle tier, whose corporate PAC amount
   is always shown. Counts are computed from PEOPLE at render time
   and always labeled with the preset. */
function renderClean(){
  const statsEl = document.getElementById('clean-stats');
  if(!statsEl) return;
  const {incoming, nd, hND, sND} = notDirtyCounts();
  const careerCleanHouse = incoming.filter(p=>p.chamber_120==='House'&&isCareerClean(p));
  const ndAll = PEOPLE.filter(isNotDirty);
  const unopp = PEOPLE.filter(p=>p.cy_unopposed===true);
  const unver = PEOPLE.filter(p=>p.cy_clean===null && p.cy_unopposed!==true);
  const preset = PRESETS[state.preset];
  const word = state.preset==='strict' ? 'verified clean' : 'not dirty';
  statsEl.innerHTML =
    '<div class="stats">'
    + '<div class="stat"><b>'+hND+' of '+incoming.filter(p=>p.chamber_120==='House').length+'</b>incoming House '+word+' '+IN_CY+' ('+preset.label+')</div>'
    + '<div class="stat"><b>'+sND+' of '+incoming.filter(p=>p.chamber_120==='Senate').length+'</b>incoming Senate '+word+' '+IN_CY+' ('+preset.label+')</div>'
    + '<div class="stat"><b>'+nd.length+' total</b>'+word+' in the incoming 120th ('+preset.label+')</div>'
    + '<div class="stat"><b>'+careerCleanHouse.length+'</b>career-clean incoming House members</div>'
    + '<div class="stat"><b>'+unopp.length+' ran unopposed</b>'+IN_CY+' — no opponent with receipts over $0, so not counted clean: '+esc(unopp.map(p=>p.full_name).join(', '))+'</div>'
    + '<div class="stat"><b>'+unver.length+' unverified</b>'+esc(unver.map(p=>p.full_name).join(', '))+'</div>'
    + '</div>'
    + '<p class="view-intro">'+ndAll.length+' people in the whole tracker are '+word+' '+IN_CY+' under the '+preset.label+' tolerance — the '+nd.length+' above plus '
    + (ndAll.length-nd.length) + ' outgoing 119th-only members. Click a row for the full breakdown.</p>';
  const mid = state.preset==='strict' ? ''
    : ' The middle tier — “Below threshold” — took corporate PAC money below those thresholds; it is never called clean, and the dollar amount is always shown.';
  document.getElementById('clean-callout').innerHTML =
    '<b>What “'+word+' '+IN_CY+'” means under the '+preset.label+' tolerance:</b> '+preset.def
    + ' It is a cycle test, not a career test — a member can be '+word+' '+IN_CY+' while having taken such money in earlier cycles.'+mid
    + ' A member is shown as <b>unverified</b> only if they have no entries '+IN_CY+' in <i>any</i> money source — usually because their real campaign is not linked in the roster.';
  const table = document.getElementById('clean-table');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  thead.innerHTML = '<tr><th>Name</th><th>State / Dist.</th><th>Party</th><th>Chamber</th><th>Incoming 120th?</th><th>Tier '+esc(CY)+'</th><th class="num">Corp PAC '+esc(CY)+'</th><th class="num">Dirty '+esc(CY)+'</th><th>Career-clean?</th></tr>';
  const rows = ndAll.slice().sort((a,b)=>a.full_name.localeCompare(b.full_name));
  tbody.innerHTML = rows.map(p=>'<tr data-key="'+esc(p.person_key)+'"><td class="name">'+esc(p.full_name)+'</td><td>'+esc(place(p))+'</td><td>'+partyChip(p)+' '+esc(party(p))+'</td><td>'+esc(chamber(p))+'</td><td>'+(p.in_120th==='yes'?'Yes':'No — 119th only')+'</td><td>'+fmtTierBadge(p)+'</td><td class="num">'+moneyShort(p.cy_corp)+'</td><td class="num">'+moneyShort(p.cy_dirty)+'</td><td>'+(isCareerClean(p)?'Yes':'No')+'</td></tr>').join('');
  tbody.querySelectorAll('tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- party breakdown ---- */
function renderBreakdown(){
  const intro = document.getElementById('breakdown-intro');
  if(!intro) return;
  intro.textContent =
    'Members of the incoming 120th Congress, grouped by party and chamber. Money columns are career totals; the not-dirty column counts members with no dirty money '+IN_CY+' under the '+PRESETS[state.preset].label+' tolerance ('+PRESETS[state.preset].short+').';
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
  const rowHtml = g=>'<tr><td>'+esc(g.party)+'</td><td>'+esc(g.chamber)+'</td><td class="num">'+g.n+'</td><td class="num">'+moneyShort(g.ind)+'</td><td class="num">'+moneyShort(g.corp)+'</td><td class="num">'+moneyShort(g.aipac)+'</td><td class="num">'+moneyShort(g.tot)+'</td><td class="num">'+moneyShort(g.udp)+'</td><td class="num">'+moneyShort(g.self)+'</td><td class="num">'+moneyShort(g.ie)+'</td><td class="num">'+g.clean+'</td></tr>';
  const table = document.getElementById('breakdown-table');
  table.querySelector('thead').innerHTML =
    '<tr><th>Party</th><th>Chamber</th><th class="num">Members</th><th class="num">Individual (career)</th><th class="num">Corp PAC (career)</th><th class="num">AIPAC (career)</th><th class="num">Total accepted</th><th class="num">UDP benefit</th><th class="num">Self-funding</th><th class="num">All IE total</th><th class="num">Not dirty '+esc(CY)+' ('+PRESETS[state.preset].label+')</th></tr>';
  table.querySelector('tbody').innerHTML =
    rows.map(rowHtml).join('') + '<tr><td><b>All</b></td><td><b>120th</b></td><td class="num"><b>'+tot.n+'</b></td><td class="num"><b>'+moneyShort(tot.ind)+'</b></td><td class="num"><b>'+moneyShort(tot.corp)+'</b></td><td class="num"><b>'+moneyShort(tot.aipac)+'</b></td><td class="num"><b>'+moneyShort(tot.tot)+'</b></td><td class="num"><b>'+moneyShort(tot.udp)+'</b></td><td class="num"><b>'+moneyShort(tot.self)+'</b></td><td class="num"><b>'+moneyShort(tot.ie)+'</b></td><td class="num"><b>'+tot.clean+'</b></td></tr>';
}

/* ---- primary targets for the next cycle ----
   Incoming members of any party whose seat is up next cycle (every
   House seat; Senate seats of that cycle's class) and who took dirty
   money since their last election under the preset. The rule is
   receipts/domain/targets.py; it ignores the cycle picker. Counts are
   computed at render, never typed: a watchlist, not a prediction. */
const NEXT_CYCLE = COLS.next_cycle;
function seatUpNext(p){
  return p.chamber_120==='House' || (p.chamber_120==='Senate' && p.senate_class===COLS.next_senate_class);
}
function dirtyUnderPreset(r){
  if(state.preset==='strict') return num(r.dirty)>0;
  return (state.preset==='lenient' ? r.tier_lenient : r.tier_balanced)==='dirty';
}
function primaryTargets(){
  const latest = p=>cycleRecord(p, 'latest');
  return PEOPLE.filter(p=>p.in_120th==='yes' && seatUpNext(p) && p.verdict_cycle!==null && dirtyUnderPreset(latest(p)))
    .sort((a,b)=>num(latest(b).dirty)-num(latest(a).dirty));
}
function renderTargets(){
  const intro = document.getElementById('targets-intro');
  if(!intro) return;
  const rows = primaryTargets();
  const preset = PRESETS[state.preset];
  const house = rows.filter(p=>p.chamber_120==='House').length;
  intro.innerHTML =
    'A watchlist, not a prediction. '+rows.length+' incoming members whose seat is up in '+NEXT_CYCLE
    +' took dirty money since their last election ('+house+' House + '+(rows.length-house)+' Senate), any party, under the '
    +preset.label+' tolerance ('+preset.short+'; any AIPAC direct or UDP benefit dollar always counts). Retirements are unknown and '
    +NEXT_CYCLE+' filings are barely open. The rule is mechanical — dirty money only; the tracker does not judge electability or anything else.';
  const table = document.getElementById('targets-table');
  table.querySelector('thead').innerHTML =
    '<tr><th>#</th><th>Name</th><th>Party</th><th>Seat</th><th class="num">Election</th><th class="num">Dirty</th><th class="num">Corp PAC</th><th class="num">AIPAC</th><th class="num">UDP benefit</th><th class="num">Dirty career</th><th class="num">Individual</th></tr>';
  table.querySelector('tbody').innerHTML = rows.map((p,i)=>{
    const r = cycleRecord(p, 'latest');
    const flag = r.aipac_udp_flag===true ? ' <span class="badge flag" title="AIPAC PAC direct money or UDP benefit since their last election">AIPAC/UDP</span>' : '';
    return '<tr data-key="'+esc(p.person_key)+'"><td>'+(i+1)+'</td><td class="name">'+esc(p.full_name)+flag+'</td><td>'+esc(party(p))+'</td><td>'+esc(place(p))+'</td><td class="num">'+r.cycle+'</td>'
      + ['dirty','corp','aipac_direct','udp_benefit'].map(k=>'<td class="num">'+fmtMoney(r[k])+'</td>').join('')
      + '<td class="num">'+fmtMoney(p.dirty_career)+'</td><td class="num">'+fmtMoney(r.individual)+'</td></tr>';
  }).join('');
  table.querySelectorAll('tbody tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- tolerance preset / cycle / money-format switching ----
   Recomputes every preset-dependent surface live: the overview, the
   table badges, and the clean / breakdown / targets / hemicycle views
   (re-rendered on next show if not current). The leaderboards are
   cycle-driven and do not move with the preset. */
const VIEW_RENDER = {leaders:renderLeaders, clean:renderClean, breakdown:renderBreakdown,
  targets:renderTargets, hemicycle:renderHemicycle};
function refreshViews(views){
  views.forEach(v=>{
    if(state.view===v && VIEW_RENDER[v]) VIEW_RENDER[v]();
  });
}
function setPreset(preset){
  if(!PRESETS[preset]) return;
  state.preset = preset;
  const note = document.getElementById('tolerance-note');
  if(note) note.textContent = PRESETS[preset].def;
  renderOverview(); renderTable();
  refreshViews(['clean','breakdown','targets','hemicycle']);
}
function labelCycle(){
  document.querySelectorAll('[data-cy]').forEach(el=>{
    el.textContent = el.getAttribute('data-cy')==='in' ? IN_CY : CY;
  });
}
function setCycle(cycle){
  if(!isCycleChoice(cycle)) return;
  state.cycle = cycle;
  applyCycle(cycle);
  labelCycle();
  renderOverview(); renderTable();
  refreshViews(Object.keys(VIEW_RENDER));
}
function setMoneyFmt(fmt){
  if(fmt!=='exact' && fmt!=='compact') return;
  state.moneyFmt = fmt;
  saveMoneyFmt(fmt);
  renderTable();
  ['clean','breakdown'].forEach(v=>{
    if(state.view===v) VIEW_RENDER[v]();
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
  const escCsv = s => /[",\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
  const lines = [cols.map(escCsv).join(',')];
  sortRows(applyFilters()).forEach(p=>{
    decodeNested(p);
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
  const blob = new Blob([lines.join('\n')], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'congress-money-tracker.csv';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 1000);
}

/* ---- detail drawer (details on demand) ---- */
function cycleTable(title, rows, cols, open, id){
  if(!rows || !rows.length) return '';
  let h = '<details'+(id?' id="'+id+'"':'')+(open?' open':'')+' class="cycle"><summary>'+esc(title)+'</summary><div class="tablewrap"><table><thead><tr>'
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
  return h + '</tbody></table></div></details>';
}
function kvRow(label, value){ return '<div><span>'+esc(label)+'</span><span>'+value+'</span></div>'; }
/* The proportional stacked bar of sources: AIPAC / corporate PAC /
   individual, as shares of total accepted (career). UDP benefit is
   outside spending, never accepted, so it is not in this bar. */
function sourceBar(p){
  const aipac = num(p.aipac_pac_direct_career)||0;
  const corp = num(p.corporate_pac_career)||0;
  const indiv = num(p.individual_contribution_total_career)||0;
  const total = aipac+corp+indiv;
  if(total<=0) return '<p class="view-intro">No accepted money on record (career).</p>';
  const pct = v=>Math.round(v/total*1000)/10;
  const seg = (label, value, cls)=>'<span class="src-seg '+cls+'" style="width:'+(value/total*100)+'%" title="'+esc(label)+' '+fmtMoney(value)+' ('+pct(value)+'%)"></span>';
  return '<div class="src-bar" role="img" aria-label="Career money split: individual '+pct(indiv)+'%, corporate PAC '+pct(corp)+'%, AIPAC direct '+pct(aipac)+'%">'
    + seg('Individual', indiv, 'src-indiv') + seg('Corporate PAC', corp, 'src-corp') + seg('AIPAC direct', aipac, 'src-aipac') + '</div>'
    + '<p class="src-legend"><span><b class="dot src-indiv"></b>Individual '+fmtMoney(indiv)+' ('+pct(indiv)+'%)</span>'
    + '<span><b class="dot src-corp"></b>Corporate PAC '+fmtMoney(corp)+' ('+pct(corp)+'%)</span>'
    + '<span><b class="dot src-aipac"></b>AIPAC direct '+fmtMoney(aipac)+' ('+pct(aipac)+'%)</span></p>';
}
function fecLink(p){
  // The FEC candidate profile for the person's first candidate ID,
  // for the selected cycle (latest election when that is selected).
  const id = (p.fec_candidate_ids||[])[0];
  if(!id) return '';
  const cycle = state.cycle==='latest' ? (p.verdict_cycle || CURRENT_CYCLE) : state.cycle;
  return '<a href="https://www.fec.gov/data/candidate/'+esc(id)+'/?cycle='+cycle+'" target="_blank" rel="noopener">FEC filing — candidate '+esc(id)+' ('+cycle+' cycle)</a>';
}
function shareUrl(p){
  try{
    const base = (typeof location!=='undefined' && location.origin && location.pathname)
      ? location.origin+location.pathname : '';
    return base+'?member='+encodeURIComponent(p.person_key);
  }catch(e){ return '?member='+encodeURIComponent(p.person_key); }
}
function openDetail(key, opts){
  const p = BY_KEY[key]; if(!p) return;
  // The drawer opens with the name and a loading line; the nested
  // lists then decode synchronously (trivial for one person) and the
  // full breakdown fills in the same task.
  lastFocused = document.activeElement || null;
  document.getElementById('detail-sheet').innerHTML = '<h2>'+esc(p.full_name)+'</h2><p>Loading the full breakdown…</p>';
  document.getElementById('detail').classList.add('open');
  decodeNested(p);
  let firstCycle = true;
  function cycle(title, rows, cols, id){
    const h = cycleTable(title, rows, cols, firstCycle, id);
    if(h) firstCycle = false;
    return h;
  }
  const leader = [p.leadership_119, (p.leadership_120 && p.leadership_120!=='TBD') ? p.leadership_120 : null].filter(Boolean).join('; ');
  // Prev/next walk the filtered, sorted table set — the rows the
  // table is showing. Disabled at the ends, or when this person is
  // not in the set at all. Navigation replaces the URL, not pushes.
  const set = sortRows(applyFilters());
  const idx = set.findIndex(x=>x.person_key===key);
  const prevKey = idx>0 ? set[idx-1].person_key : null;
  const nextKey = idx>=0 && idx<set.length-1 ? set[idx+1].person_key : null;
  let h = '<div class="detail-top"><h2>'+esc(p.full_name)+'</h2><div class="detail-actions">'
    + '<button class="btn ghost" id="detail-prev" type="button"'+(prevKey?'':' disabled')+'>← Prev</button>'
    + '<button class="btn ghost" id="detail-next" type="button"'+(nextKey?'':' disabled')+'>Next →</button>'
    + '<button class="btn ghost close" id="detail-close" type="button">Close ✕</button>'
    + '</div></div>';
  // Anchor nav — jumps to a section, opening its <details> first,
  // and moves focus there. Buttons, not href="#…" links, so a jump
  // never fights the URL scheme.
  h += '<div class="detail-nav">'
    + '<button class="btn ghost" type="button" data-anchor="sec-career">Career</button>'
    + '<button class="btn ghost" type="button" data-anchor="sec-cycle">'+esc(CY)+'</button>'
    + '<button class="btn ghost" type="button" data-anchor="sec-cycle-money">By cycle</button>'
    + (p.all_ie_top_committees && p.all_ie_top_committees.length ? '<button class="btn ghost" type="button" data-anchor="sec-spenders">Outside spenders</button>' : '')
    + (p.data_notes ? '<button class="btn ghost" type="button" data-anchor="sec-notes">Notes</button>' : '')
    + '<button class="btn ghost" id="detail-table" type="button">View in table →</button>'
    + '</div>';
  h += '<p class="meta">'+partyChip(p)+' '+esc(party(p))+' · '+esc(chamber(p))+' · '+esc(place(p))+' · '+outcomeLabel(p)+' · '+esc(congressLabel(p))
    + (leader ? ' · '+esc(leader) : '') + ' · FEC ID'+(p.fec_candidate_ids.length>1?'s':'')+': '
    + esc(p.fec_candidate_ids.join(', ')||'none') + '</p>';
  // The verdict, plus the plain-English rule that produced it.
  h += '<p class="detail-verdict">'+fmtTierBadge(p)+' <span class="verdict-reason">'+esc(verdictReason(p))+'</span></p>';
  h += '<p class="detail-head">Dirty '+esc(CY)+' <b>'+fmtMoney(p.cy_dirty)+'</b> · Total accepted (career) <b>'+fmtMoney(p.total_accepted_career)+'</b></p>';
  h += '<h3>Where the career money came from</h3>' + sourceBar(p);
  h += '<h3 id="sec-career" tabindex="-1">Career money</h3><div class="kv">'
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
    + kvRow('Pro-Israel PACs: direct (career) / supporting IE / opposition credit ('+IE_SPAN+')', fmtMoney(p.pro_israel_pac_career)+' / '+fmtMoney(p.pro_israel_ie_support_career)+' / '+fmtMoney(p.pro_israel_opp_credit_career))
    + kvRow('All IE support / oppose / total ('+IE_SPAN+')', fmtMoney(p.all_ie_support_career)+' / '+fmtMoney(p.all_ie_oppose_career)+' / <b>'+fmtMoney(p.all_ie_total_career)+'</b> ('+fmtRank(p.rank_all_ie_total)+')')
    + '</div>';
  const oppRows = OPP[p.person_key];
  if(oppRows && oppRows.length){
    h += cycle('UDP opposition credit by race — phase by phase', oppRows.map(e=>({
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
  h += '<h3 id="sec-cycle" tabindex="-1">'+esc(CY)+' cycle'+(p.cy_cycle===CURRENT_CYCLE ? ' (partial)' : '')+'</h3><div class="kv">'
    + kvRow('Tier '+IN_CY+' ('+PRESETS[state.preset].label+')', fmtTierBadge(p))
    + kvRow('AIPAC/UDP flag', p.cy_aipac_udp_flag===true ? 'Yes — AIPAC PAC direct money or UDP benefit '+IN_CY+'; flagged under every tolerance preset' : 'No')
    + kvRow('Unopposed '+IN_CY, p.cy_unopposed===true?'Yes — no opponent with receipts over $0':'No')
    + kvRow('Dirty '+CY, fmtMoney(p.cy_dirty))
    + kvRow('Individual '+CY, fmtMoney(p.cy_individual))
    + kvRow('Corporate PAC '+CY, fmtMoney(p.cy_corp))
    + kvRow('AIPAC direct '+CY, fmtMoney(p.cy_aipac_direct))
    + kvRow('UDP support '+CY, fmtMoney(p.cy_udp_support))
    + kvRow('UDP opposition credit '+CY, fmtMoney(p.cy_udp_opp_credit))
    + kvRow('UDP benefit '+CY, fmtMoney(p.cy_udp_benefit))
    + kvRow('Dependence share '+CY, fmtPct(p.cy_dep_share))
    + kvRow('Self-funding '+CY, fmtMoney(p.cy_self_funding))
    + kvRow('Total receipts / disbursements '+CY, fmtMoney(p.cy_total_receipts)+' / '+fmtMoney(p.cy_total_disbursements))
    + kvRow('Other committees '+CY, fmtMoney(p.cy_other_committees_total))
    + kvRow('All IE '+CY+' (support / oppose)', fmtMoney(p.cy_all_ie_support)+' / '+fmtMoney(p.cy_all_ie_oppose))
    + '</div>';
  h += cycle('Cycle by cycle — individual / AIPAC / corporate PAC', p.per_cycle, [
    ...CYCLE_ID,
    {k:'individual',label:'Individual',type:'money'},{k:'aipac_pac_direct',label:'AIPAC direct',type:'money'},
    {k:'aipac_earmark_transmitted',label:'AIPAC earmark',type:'money'},
    {k:'corporate_pac',label:'Corp PAC',type:'money'},{k:'corporate_earmark_transmitted',label:'Corp earmark',type:'money'}], 'sec-cycle-money');
  h += cycle('Cycle by cycle — self-funding & topline', p.self_funding_per_cycle, [
    ...CYCLE_ID,
    {k:'candidate_contributions',label:'Cand. contrib.',type:'money'},{k:'candidate_loans',label:'Cand. loans',type:'money'},
    {k:'loan_repayments',label:'Loan repay.',type:'money'},{k:'debts_owed_by',label:'Debts owed',type:'money'},
    {k:'total_receipts',label:'Receipts',type:'money'},{k:'total_disbursements',label:'Disbursements',type:'money'},
    {k:'cash_on_hand',label:'Cash on hand',type:'money'},{k:'coverage_end_date',label:'Coverage ends',type:'text'}]);
  h += cycle('Cycle by cycle — other committees', p.other_committees_per_cycle, [
    ...CYCLE_ID,
    {k:'party_committees',label:'Party',type:'money'},{k:'leadership_pacs',label:'Leadership',type:'money'},
    {k:'labor_pacs',label:'Labor',type:'money'},{k:'trade_pacs',label:'Trade',type:'money'},
    {k:'membership_pacs',label:'Membership',type:'money'},{k:'cooperative_pacs',label:'Cooperative',type:'money'},
    {k:'other_unclassified',label:'Other',type:'money'},{k:'winred_included',label:'WinRed incl.',type:'money'}]);
  h += cycle('Cycle by cycle — all independent expenditures ('+IE_SPAN+')', p.all_ie_per_cycle, [
    ...CYCLE_ID,
    {k:'all_ie_support',label:'Support',type:'money'},{k:'all_ie_oppose',label:'Oppose',type:'money'},
    {k:'all_ie_total',label:'Total',type:'money'}]);
  h += cycle('Cycle by cycle — UDP support', p.udp_per_cycle, [
    ...CYCLE_ID,
    {k:'udp_ie_support',label:'UDP support',type:'money'},{k:'attribution',label:'Attribution',type:'text'}]);
  if(p.all_ie_top_committees && p.all_ie_top_committees.length){
    h += cycle('Top outside spenders on this race (career, '+IE_SPAN+')', p.all_ie_top_committees, [
      {k:'committee_name',label:'Committee',type:'text'},{k:'support',label:'Support',type:'money'},
      {k:'oppose',label:'Oppose',type:'money'},{k:'total',label:'Total',type:'money'}], 'sec-spenders');
  }
  if(p.data_notes) h += '<h3 id="sec-notes" tabindex="-1">Data notes</h3><div class="notes">'+esc(p.data_notes)+'</div>';
  const link = fecLink(p);
  h += '<p class="detail-links">'+(link ? link+' · ' : '')
    + '<label>Share this member: <input type="text" readonly value="'+esc(shareUrl(p))+'" aria-label="Share link for this member" onclick="this.select()"></label> '
    + '<button class="btn ghost" id="detail-copy" type="button">Copy link</button></p>';
  h += '<p class="detail-foot">Data as of '+esc(p.data_as_of)+' · Person key '+esc(p.person_key)+' · Figures trace to FEC filings; see Methodology.</p>';
  document.getElementById('detail-sheet').innerHTML = h;
  document.getElementById('detail-close').addEventListener('click', closeDetail);
  if(prevKey) document.getElementById('detail-prev').addEventListener('click', ()=>openDetail(prevKey, {push:false}));
  if(nextKey) document.getElementById('detail-next').addEventListener('click', ()=>openDetail(nextKey, {push:false}));
  document.getElementById('detail-table').addEventListener('click', ()=>viewInTable(key));
  Array.prototype.slice.call(document.getElementById('detail-sheet').querySelectorAll('[data-anchor]')).forEach(b=>{
    b.addEventListener('click', ()=>goAnchor(b.getAttribute('data-anchor')));
  });
  const copyBtn = document.getElementById('detail-copy');
  if(copyBtn) copyBtn.addEventListener('click', ()=>{
    const url = shareUrl(p);
    const done = ()=>{ copyBtn.textContent = 'Copied'; };
    try{
      if(typeof navigator!=='undefined' && navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(url).then(done, ()=>{ copyBtn.textContent = 'Copy failed — select the link'; });
      } else {
        copyBtn.textContent = 'Select the link to copy';
      }
    }catch(e){ copyBtn.textContent = 'Select the link to copy'; }
  });
  const closeBtn = document.getElementById('detail-close');
  if(closeBtn && typeof closeBtn.focus==='function') closeBtn.focus();
  // The open drawer lives in the URL — a push for a fresh open
  // (Back closes it), a replace for prev/next and URL restores.
  detailKey = key;
  if(!opts || opts.push!==false) syncUrl(false);
  else syncUrl(true);
}
/* ---- detail focus trap + restore ----
   Opening the drawer remembers what had focus and moves focus to
   Close; Tab cycles within the drawer; closing hands focus back. */
let lastFocused = null;
function detailFocusable(){
  const sheet = document.getElementById('detail-sheet');
  if(!sheet) return [];
  const els = sheet.querySelectorAll('button, a[href], input, [tabindex]');
  return Array.prototype.slice.call(els).filter(el=>!el.disabled);
}
function goAnchor(id){
  const target = document.getElementById(id);
  if(!target) return;
  if(target.tagName==='DETAILS') target.open = true;
  const focusEl = target.tagName==='DETAILS' ? target.querySelector('summary') : target;
  if(focusEl && typeof focusEl.focus==='function') focusEl.focus();
  else if(typeof target.scrollIntoView==='function') target.scrollIntoView();
}
function viewInTable(key){
  const p = BY_KEY[key]; if(!p) return;
  // Close without a URL push, then filter the table to this person —
  // like findPerson, but without reopening the drawer.
  closeDetail({pop:false});
  state.q = p.full_name;
  const q = document.getElementById('q');
  if(q) q.value = state.q;
  showView('table');
  state.page = 1;
  renderTable();
}
function closeDetail(opts){
  const sheet = document.getElementById('detail');
  if(!sheet.classList.contains('open') && detailKey===null) return;
  detailKey = null;
  sheet.classList.remove('open');
  if(lastFocused && typeof lastFocused.focus==='function') lastFocused.focus();
  lastFocused = null;
  // From the popstate handler the URL already moved (Back/forward):
  // write nothing. Otherwise strip the member from the URL (replace —
  // the Close button should not add a history entry).
  if(!(opts && opts.pop===false)) syncUrl(true);
}

/* ---- URL state: query string for the view, #search to focus search ----
   Only non-default values are written, so a plain /explore/ still
   means "defaults". Drawer opens push a history entry (Back closes
   the drawer); filter/view/page changes replace the current entry,
   so typing in the search box does not spam history. */
function safeDecode(s){
  try{ return decodeURIComponent(s); }catch(e){ return s; }
}
function currentSearch(){
  try{ return (typeof location!=='undefined' && location.search) || ''; }catch(e){ return ''; }
}
function currentHash(){
  try{ return (typeof location!=='undefined' && location.hash) || ''; }catch(e){ return ''; }
}
function parseQuery(search){
  const out = {};
  (search||'').replace(/^\?/,'').split('&').forEach(pair=>{
    if(!pair) return;
    const eq = pair.indexOf('=');
    const k = eq<0 ? pair : pair.slice(0,eq);
    const v = eq<0 ? '' : safeDecode(pair.slice(eq+1));
    out[k] = v;
  });
  return out;
}
function buildExploreUrl(){
  const parts = [];
  if(state.view!=='table') parts.push('view='+encodeURIComponent(state.view));
  if(state.q.trim()) parts.push('q='+encodeURIComponent(state.q.trim()));
  if(state.congress!=='all') parts.push('congress='+state.congress);
  if(state.chamber!=='all') parts.push('chamber='+state.chamber);
  if(state.party!=='all') parts.push('party='+encodeURIComponent(state.party));
  if(state.flag!=='all') parts.push('flag='+state.flag);
  if(state.source!=='all') parts.push('source='+state.source);
  if(state.state!=='all') parts.push('state='+state.state);
  if(state.preset!=='balanced') parts.push('preset='+state.preset);
  if(state.cycle!=='latest') parts.push('cycle='+state.cycle);
  if(state.sortKey!=='grouped') parts.push('sort='+encodeURIComponent(state.sortKey));
  if(state.sortDir!=='desc') parts.push('dir='+state.sortDir);
  if(state.page!==1) parts.push('page='+state.page);
  if(state.pageSize!==25) parts.push('size='+state.pageSize);
  if(detailKey) parts.push('member='+encodeURIComponent(detailKey));
  return parts.length ? '?'+parts.join('&') : '';
}
/* parseExploreUrl is pure over its arguments (the tests pin it): the
   hash only carries #search, which focuses the search field. */
function parseExploreUrl(search, hash){
  const out = {view:'table', q:'', congress:'all', chamber:'all',
    party:'all', flag:'all', source:'all', state:'all',
    preset:'balanced', cycle:'latest', sortKey:'grouped', sortDir:'desc',
    page:1, pageSize:25, member:null, focusSearch:false};
  const params = parseQuery(search);
  if(params.view && ['table','leaders','clean','breakdown','targets','hemicycle'].indexOf(params.view)>=0) out.view = params.view;
  if(params.q) out.q = params.q;
  if(params.congress && ['119','120','both','all'].indexOf(params.congress)>=0) out.congress = params.congress;
  if(params.chamber && ['House','Senate','all'].indexOf(params.chamber)>=0) out.chamber = params.chamber;
  if(params.party && ['Democrat','Republican','Independent','PPD','all'].indexOf(params.party)>=0) out.party = params.party;
  if(params.flag && ['flagged','clean','all'].indexOf(params.flag)>=0) out.flag = params.flag;
  if(params.source && ['aipac','corporate','udp','individual','all'].indexOf(params.source)>=0) out.source = params.source;
  if(params.state && /^[A-Z]{2}$/.test(params.state)) out.state = params.state;
  if(params.preset && PRESETS[params.preset]) out.preset = params.preset;
  if(params.cycle && isCycleChoice(cycleValue(params.cycle))) out.cycle = cycleValue(params.cycle);
  if(params.sort && SORTABLE.has(params.sort)) out.sortKey = params.sort;
  if(params.dir && (params.dir==='asc' || params.dir==='desc')) out.sortDir = params.dir;
  if(params.page && Number(params.page)>=1) out.page = Math.floor(Number(params.page));
  if(params.size && PAGE_SIZES.indexOf(Number(params.size))>=0) out.pageSize = Number(params.size);
  if(params.member && BY_KEY[params.member]) out.member = params.member;
  if((hash||'')==='#search') out.focusSearch = true;
  return out;
}
function writeUrl(url, replace){
  // No-op guard: the serialized state already matches the URL, so
  // there is nothing to write — and no popstate to loop on.
  if(url===currentSearch()) return;
  try{
    if(replace && typeof history!=='undefined' && history.replaceState){
      history.replaceState(null, '', url || location.pathname || '/explore/');
      return;
    }
    if(typeof history!=='undefined' && history.pushState){
      history.pushState(null, '', url || location.pathname || '/explore/');
      return;
    }
  }catch(e){}
}
function syncUrl(replace){ writeUrl(buildExploreUrl(), !!replace); }
function applyUrl(){
  const p = parseExploreUrl(currentSearch(), currentHash());
  // Detail first: open the URL's person, or close a drawer the URL
  // no longer names (this is how Back closes the drawer).
  if(p.member && BY_KEY[p.member]){
    if(detailKey!==p.member) openDetail(p.member, {push:false});
  } else if(document.getElementById('detail').classList.contains('open')){
    closeDetail({pop:false});
  }
  let changed = false;
  const setField = (key, val)=>{ if(state[key]!==val){ state[key]=val; changed=true; } };
  setField('q', p.q); setField('congress', p.congress); setField('chamber', p.chamber);
  setField('party', p.party); setField('flag', p.flag); setField('source', p.source);
  setField('state', p.state); setField('sortKey', p.sortKey); setField('sortDir', p.sortDir);
  setField('page', p.page); setField('pageSize', p.pageSize);
  if(p.cycle!==state.cycle){ setCycle(p.cycle); const c=document.getElementById('f-cycle'); if(c) c.value = String(p.cycle); }
  if(p.preset!==state.preset){ setPreset(p.preset); const t=document.getElementById('f-tolerance'); if(t) t.value = p.preset; }
  if(changed){
    const set = (id, v)=>{ const e=document.getElementById(id); if(e) e.value=v; };
    set('q', state.q); set('f-congress', state.congress); set('f-chamber', state.chamber);
    set('f-party', state.party); set('f-flag', state.flag); set('f-source', state.source);
    set('f-state', state.state);
    const ps = document.getElementById('page-size'); if(ps) ps.value = String(state.pageSize);
    renderTable();
  }
  if(p.view!==state.view) showView(p.view, {scroll:false});
  else if(changed) renderTable();
  if(p.focusSearch){
    const q = document.getElementById('q');
    if(q && typeof q.focus==='function') q.focus();
  }
}
/* ---- views (tabs within Explore) ---- */
function showView(name, opts){
  if(!VIEW_RENDER[name] && name!=='table') return;
  state.view = name;
  document.querySelectorAll('#explore-tabs button').forEach(b=>b.setAttribute('aria-selected', String(b.getAttribute('data-view')===name)));
  ['table','leaders','clean','breakdown','targets','hemicycle'].forEach(v=>{
    const el = document.getElementById('view-'+v);
    if(el) el.hidden = (v!==name);
  });
  if(VIEW_RENDER[name]) VIEW_RENDER[name]();
  syncUrl(true);
  // Tab change: top of the page, focus on the panel — but not on
  // popstate (applyUrl passes scroll:false): Back/forward must
  // restore the view without yanking the reader.
  if(!opts || opts.scroll!==false){
    try{ if(typeof window!=='undefined' && typeof window.scrollTo==='function') window.scrollTo(0,0); }catch(e){}
    const panel = document.getElementById('view-'+name);
    if(panel && typeof panel.focus==='function') panel.focus();
  }
}
/* ---- findPerson: the Story's handoff — filter to one person and open them ---- */
function findPerson(key){
  const p = BY_KEY[key]; if(!p) return;
  state.q = p.full_name; state.congress = '120'; state.chamber = 'all';
  state.party = 'all'; state.flag = 'all'; state.source = 'all'; state.state = 'all';
  const set = (id, v)=>{ const e=document.getElementById(id); if(e) e.value=v; };
  set('q', p.full_name); set('f-congress', '120'); set('f-chamber', 'all');
  set('f-party', 'all'); set('f-flag', 'all'); set('f-source', 'all'); set('f-state', 'all');
  showView('table');
  state.page = 1;
  renderTable();
  openDetail(key);
}

/* ---- init ---- */
function init(){
  // Gate the JS-only hiding on JS actually running: no-JS never gets
  // the .js class, so every static row stays visible.
  try{ if(document.documentElement && document.documentElement.classList) document.documentElement.classList.add('js'); }catch(e){}
  state.extraCols = loadExtraCols();
  const states = [...new Set(PEOPLE.map(p=>p.state))].sort();
  const stateSel = document.getElementById('f-state');
  if(stateSel) stateSel.innerHTML = '<option value="all">All states</option>'
    + states.map(s=>'<option value="'+esc(s)+'">'+esc(s)+'</option>').join('');
  renderOverview(); renderColumnChooser(); renderTable();
  // The URL is the state — restore view, filters, preset, page and
  // the open drawer from it on load; #search focuses the field.
  applyUrl();
  if(typeof window!=='undefined' && typeof window.addEventListener==='function'){
    window.addEventListener('popstate', ()=>applyUrl());
  }
  const q = document.getElementById('q');
  if(q) q.addEventListener('input', e=>{ state.q = e.target.value; scheduleSearchRender(); });
  // One delegated listener on the table body — it survives every
  // innerHTML re-render, so rows need no listeners of their own.
  const tbody = document.getElementById('explore-tbody');
  if(tbody) tbody.addEventListener('click', e=>{
    const row = e.target.closest ? e.target.closest('tr') : null;
    if(row) openDetail(row.getAttribute('data-key'));
  });
  // The hemicycle dots open their member the same way.
  document.querySelectorAll('.hemicycle').forEach(svg=>{
    svg.addEventListener('click', e=>{
      const t = e.target && e.target.closest ? e.target.closest('[data-key]') : null;
      if(t) openDetail(t.getAttribute('data-key'));
    });
  });
  const bind = (id, ev, fn)=>{ const e=document.getElementById(id); if(e) e.addEventListener(ev, fn); };
  bind('f-congress','change', e=>{ state.congress=e.target.value; state.page=1; renderTable(); });
  bind('f-chamber','change', e=>{ state.chamber=e.target.value; state.page=1; renderTable(); });
  bind('f-party','change', e=>{ state.party=e.target.value; state.page=1; renderTable(); });
  bind('f-flag','change', e=>{ state.flag=e.target.value; state.page=1; renderTable(); });
  bind('f-source','change', e=>{ state.source=e.target.value; state.page=1; renderTable(); });
  bind('f-state','change', e=>{ state.state=e.target.value; state.page=1; renderTable(); });
  bind('f-tolerance','change', e=>{ setPreset(e.target.value); });
  const cyclePicker = document.getElementById('f-cycle');
  if(cyclePicker){
    cyclePicker.innerHTML = CYCLE_CHOICES.map(c=>'<option value="'+c+'">'+(c==='latest' ? 'Since last election' : c)+'</option>').join('');
    cyclePicker.value = String(state.cycle);
    cyclePicker.addEventListener('change', e=>{ setCycle(cycleValue(e.target.value)); syncUrl(true); });
  }
  const moneySel = document.getElementById('f-money');
  if(moneySel){
    moneySel.value = state.moneyFmt;
    moneySel.addEventListener('change', e=>{ setMoneyFmt(e.target.value); });
  }
  const note = document.getElementById('tolerance-note');
  if(note) note.textContent = PRESETS[state.preset].def;
  bind('csv-btn','click', downloadCsv);
  bind('filters-reset','click', resetFilters);
  bind('empty-clear','click', resetFilters);
  bind('page-prev','click', ()=>{ if(state.page>1){ state.page--; renderTable(); } });
  bind('page-next','click', ()=>{ state.page++; renderTable(); });
  const sizeSel = document.getElementById('page-size');
  if(sizeSel) sizeSel.addEventListener('change', e=>{ state.pageSize = Number(e.target.value); state.page=1; renderTable(); });
  document.querySelectorAll('#explore-tabs button').forEach(b=>b.addEventListener('click', ()=>showView(b.getAttribute('data-view'))));
  const detail = document.getElementById('detail');
  if(detail){
    detail.addEventListener('click', e=>{ if(e.target.id==='detail') closeDetail(); });
    detail.addEventListener('keydown', e=>{
      if(e.key!=='Tab' || !document.getElementById('detail').classList.contains('open')) return;
      const f = detailFocusable();
      if(!f.length) return;
      const first = f[0], last = f[f.length-1];
      if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
    });
  }
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDetail(); });
}
init();
