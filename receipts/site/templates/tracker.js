
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
  // Nested lists stay positional until a drill-down (or the CSV
  // export) needs them — decodeNested maps them to named objects
  // on demand (FE1a), so first paint skips 664 people's cycle detail.
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
// A selected-cycle column: its heading names the cycle the page shows.
const cyCol = (k, name, type)=>({k, type, get label(){ return name+' '+CY; }});
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

/* ---- lazy-decode nested lists (FE1a) ----
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

/* ---- column views ---- */
const WHO = [{k:'full_name',label:'Name',type:'name'}, {k:'place',label:'State / Dist.',type:'place'}];
const VIEWS = {
  core:{label:'Core money',cols:[...WHO,
    {k:'party',label:'Party',type:'party'},
    {k:'outcome',label:'Outcome',type:'outcome'},
    {k:'chamber',label:'Chamber',type:'chamber'},
    {k:'congress',label:'Congress',type:'congress'},
    {k:'individual_contribution_total_career',label:'Individual (career)',type:'money'},
    {k:'corporate_pac_career',label:'Corp PAC (career)',type:'money'},
    {k:'aipac_pac_direct_career',label:'AIPAC direct (career)',type:'money'},
    {k:'total_accepted_career',label:'Total accepted',type:'money'},
    {k:'rank_total_accepted',label:'Rank',type:'rank'},
    cyCol('cy_dirty','Dirty','money'),
    cyCol('cy_clean','Tier','clean')]},
  cycle:{get label(){ return CY+' cycle'; }, cols:[...WHO,
    {k:'party',label:'Party',type:'party'},
    cyCol('cy_individual','Individual','money'),
    cyCol('cy_corp','Corp PAC','money'),
    cyCol('cy_aipac_direct','AIPAC','money'),
    cyCol('cy_udp_support','UDP support','money'),
    cyCol('cy_udp_benefit','UDP benefit','money'),
    cyCol('cy_dirty','Dirty','money'),
    cyCol('cy_dep_share','Dep. share','pct'),
    cyCol('cy_clean','Tier','clean')]},
  selffund:{label:'Self-funding & topline',cols:[...WHO,
    {k:'self_funding_career',label:'Self-funding (career)',type:'money'},
    {k:'cand_loans_career',label:'Candidate loans',type:'money'},
    {k:'cand_contrib_career',label:'Candidate contrib.',type:'money'},
    {k:'loan_repayments_career',label:'Loan repayments',type:'money'},
    {k:'total_receipts_career',label:'Total receipts',type:'money'},
    {k:'total_disbursements_career',label:'Total disbursements',type:'money'},
    {k:'cash_on_hand_career',label:'Cash on hand',type:'money'},
    {k:'debts_owed_by_career',label:'Debts owed',type:'money'},
    {k:'rank_self_funding',label:'Rank',type:'rank'}]},
  committees:{label:'Other committees',cols:[...WHO,
    {k:'party_committees_career',label:'Party',type:'money'},
    {k:'leadership_pacs_career',label:'Leadership PACs',type:'money'},
    {k:'labor_pacs_career',label:'Labor',type:'money'},
    {k:'trade_pacs_career',label:'Trade',type:'money'},
    {k:'membership_pacs_career',label:'Membership',type:'money'},
    {k:'cooperative_pacs_career',label:'Cooperative',type:'money'},
    {k:'other_unclassified_career',label:'Other / unclass.',type:'money'},
    {k:'other_committees_total_career',label:'Other committees total',type:'money'},
    {k:'rank_other_committees_total',label:'Rank',type:'rank'}]},
  outside:{label:'Outside spending',cols:[...WHO,
    {k:'udp_ie_support_career',label:'UDP support',type:'money'},
    {k:'udp_ie_opposing_opponents_career',label:'UDP opp. credit',type:'money'},
    {k:'udp_ie_total_benefit_career',label:'UDP total benefit',type:'money'},
    {k:'all_ie_support_career',label:'All IE support',type:'money'},
    {k:'all_ie_oppose_career',label:'All IE oppose',type:'money'},
    {k:'all_ie_total_career',label:'All IE total',type:'money'},
    {k:'rank_all_ie_total',label:'Rank',type:'rank'}]}
};
const SORTABLE = new Set(['full_name', ...Object.values(VIEWS).flatMap(v=>v.cols)
  .filter(c=>['money','rank','pct'].includes(c.type)).map(c=>c.k)]);

/* ---- money format: compact / exact (D6/FE3) ----
   Compact is the default ($1.23M); Exact shows dollars and cents
   ($1,234,567.89). The choice persists in localStorage; the guards
   keep it working where storage is unavailable. The toggle governs
   the Explore data views (table, totals strip, clean, breakdown);
   the front-door headlines stay compact, and the drill-down always
   shows exact figures. */
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
const state = {q:'', congress:'all', chamber:'all', party:'all', state:'all',
  leadership:false, clean:false, view:'core', preset:'balanced',
  moneyFmt:loadMoneyFmt(),
  sortKey:'cy_dirty', sortDir:'desc', tab:'tracker', mode:'front', rendered:{},
  cycle:'latest'};
// The drill-down's person key, when a sheet is open (FE5: it lives
// in the URL hash, so Back closes the sheet).
let detailKey = null;

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
/* ---- search relevance (U8) ----
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
    if(state.leadership && !(p.leadership_119 || (p.leadership_120 && p.leadership_120!=='TBD'))) return false;
    if(state.clean && !isNotDirty(p)) return false;
    return true;
  });
}
function sortRows(rows){
  const k = state.sortKey, dir = state.sortDir;
  const q = state.q.trim().toLowerCase();
  return rows.slice().sort((a,b)=>{
    // Relevance ranking only while a query is active: best match
    // first, then the current sort order within a relevance band.
    if(q){
      const sa = matchScore(a,q), sb = matchScore(b,q);
      if(sa!==sb) return sa-sb;
    }
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
    case 'name': return '<button type="button" class="name-btn" data-key="'+esc(p.person_key)+'">'+esc(v)+'</button>';
    case 'party': return partyChip(p) || '—';
    case 'outcome': return outcomeLabel(p);
    case 'money': {
      const t = fmtMoney(v);
      return '<span title="'+esc(t)+'">'+moneyShort(v)+'</span>';
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
    const ariaSort = SORTABLE.has(c.k) ? ' aria-sort="'+(state.sortKey===c.k ? (state.sortDir==='asc'?'ascending':'descending') : 'none')+'"' : '';
    const cls = (c.type==='money'||c.type==='pct'||c.type==='rank') ? ' class="num"' : '';
    return '<th'+cls+sortable+ariaSort+'>'+esc(c.label)+arrow+'</th>';
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
  tbody.innerHTML = rows.map(p=>'<tr data-key="'+esc(p.person_key)+'">'+view.cols.map(c=>{
    const cls = c.type==='name' ? ' class="name"' : ((c.type==='money'||c.type==='pct'||c.type==='rank') ? ' class="num"' : '');
    return '<td'+cls+'>'+cellHtml(p,c)+'</td>';
  }).join('')+'</tr>').join('');
  // totals strip + footer for the filtered set (FE2: memoised — the
  // sums depend only on which rows the filters select, not on their
  // sort order, so the filter state is the cache key)
  const totalsKey = [state.cycle, state.q, state.congress, state.chamber, state.party, state.state, state.leadership, state.clean].join('|');
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
  document.getElementById('totals').innerHTML = totals.strip;
  document.getElementById('csv-btn').textContent = 'Download CSV — '+rows.length+' rows';
  document.getElementById('showing').textContent = rows.length===0
    ? 'No matches for “'+state.q.trim()+'” — try a name, state, district, party, or chamber.'
    : 'Showing '+rows.length+' of '+PEOPLE.length+' people. Click a row for the full breakdown.';
  renderChips();
  document.getElementById('foot-totals').textContent = totals.foot;
  // FE5: every filter/preset/sort change lands in the URL (replace,
  // not push — typing in the search box must not spam history).
  syncHash(true);
}
const totalsCache = {};
function renderChips(){
  const chips = [];
  const q = state.q.trim();
  if(q) chips.push({k:'q', label:'Search: “'+q+'”'});
  if(state.congress!=='all') chips.push({k:'congress', label:'Congress: '+({119:'119th',120:'120th',both:'In both'})[state.congress]});
  if(state.chamber!=='all') chips.push({k:'chamber', label:'Chamber: '+state.chamber});
  if(state.party!=='all') chips.push({k:'party', label:'Party: '+state.party});
  if(state.state!=='all') chips.push({k:'state', label:'State: '+state.state});
  if(state.leadership) chips.push({k:'leadership', label:'Leadership (119th; 120th TBD)'});
  if(state.clean) chips.push({k:'clean', label:'Not dirty '+IN_CY+' only'});
  const el = document.getElementById('filter-chips');
  if(!chips.length){ el.innerHTML=''; return; }
  el.innerHTML = chips.map(c=>'<button type="button" class="chip" data-filter="'+c.k+'" title="Clear this filter">'+esc(c.label)+' ✕</button>').join(' ')
    + ' <button type="button" class="chip reset" id="filters-reset">Reset filters</button>';
  el.querySelectorAll('.chip[data-filter]').forEach(b=>{
    b.addEventListener('click', ()=>clearFilter(b.getAttribute('data-filter')));
  });
  document.getElementById('filters-reset').addEventListener('click', resetFilters);
}
function clearFilter(k){
  if(k==='q'){ state.q=''; document.getElementById('q').value=''; }
  if(k==='congress'){ state.congress='all'; document.getElementById('f-congress').value='all'; }
  if(k==='chamber'){ state.chamber='all'; document.getElementById('f-chamber').value='all'; }
  if(k==='party'){ state.party='all'; document.getElementById('f-party').value='all'; }
  if(k==='state'){ state.state='all'; document.getElementById('f-state').value='all'; }
  if(k==='leadership'){ state.leadership=false; document.getElementById('f-leader').checked=false; }
  if(k==='clean'){ state.clean=false; document.getElementById('f-clean').checked=false; }
  renderTable();
}
function resetFilters(){
  state.q=''; state.congress='all'; state.chamber='all'; state.party='all';
  state.state='all'; state.leadership=false; state.clean=false;
  document.getElementById('q').value='';
  document.getElementById('f-congress').value='all';
  document.getElementById('f-chamber').value='all';
  document.getElementById('f-party').value='all';
  document.getElementById('f-state').value='all';
  document.getElementById('f-leader').checked=false;
  document.getElementById('f-clean').checked=false;
  renderTable();
}
function renderViewBtns(){
  document.getElementById('viewbtns').innerHTML = Object.entries(VIEWS).map(([k,v])=>
    '<button type="button" data-view="'+k+'" aria-pressed="'+(state.view===k)+'">'+esc(v.label)+'</button>').join('');
  document.querySelectorAll('#viewbtns button').forEach(b=>{
    b.addEventListener('click', ()=>{ state.view=b.getAttribute('data-view'); renderViewBtns(); renderTable(); });
  });
}
/* ---- front door: the hook, computed from the data ----
   The #1 member and the #1-vs-next-four comparison are computed from
   PEOPLE at render time — no figure is ever typed into this template.
   The comparison line appears only if it holds (#1 exceeds the next
   four combined). The line under it says what counts as dirty under
   the current tolerance preset. */
function renderHook(){
  const rows = PEOPLE.filter(p=>num(p.cy_dirty)>0).sort(byDirty).slice(0,5);
  const top = rows[0];
  const next4 = rows.slice(1).reduce((s,p)=>s+num(p.cy_dirty),0);
  let h = '<b>'+esc(top.full_name)+'</b> took <b><span class="countup" data-value="'+num(top.cy_dirty)+'" data-format="compact">'+fmtCompact(top.cy_dirty)+'</span></b> in dirty money '+IN_CY+' — the most of anyone in Congress.';
  if(num(top.cy_dirty) > next4){
    h += ' That is more than the next four combined (<span class="countup" data-value="'+next4+'" data-format="compact">'+fmtCompact(next4)+'</span>) — about '+(num(top.cy_dirty)/next4).toFixed(2)+'× as much.';
  }
  document.getElementById('dirtiest-headline').innerHTML = h;
  const preset = PRESETS[state.preset];
  document.getElementById('hook-definition').textContent =
    'Dirty money is money from sources other than individual contributors — corporate PAC, AIPAC PAC direct and UDP benefit; '
    + preset.short
    + (state.preset==='strict' ? '.' : '; any AIPAC direct or UDP benefit dollar always counts.');
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
    if(!sel.value){ dist.innerHTML = '<option value="">Choose a seat…</option>'; dist.disabled = true; return; }
    const seats = finderSeats(sel.value);
    dist.innerHTML = '<option value="">Choose a seat…</option>'
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
    if(typeof pickInStory==='function') pickInStory(people[0].person_key);
    person.innerHTML = people.map(p=>
      '<button type="button" class="btn person-btn" data-key="'+esc(p.person_key)+'">'
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
  // U2: the handoff lands in Explore on the Tracker tab, so the
  // filtered table is what the reader sees behind the drill-down.
  showTab('tracker');
  renderTable();
  openDetail(key);
}
