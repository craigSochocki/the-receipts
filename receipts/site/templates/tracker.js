
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
  return o;
});
const BY_KEY = {}; PEOPLE.forEach(p=>{ BY_KEY[p.person_key]=p; });

/* ---- lazy-decode nested lists (FE1a) ----
   Each nested list is a positional array until decoded; decodeNested
   maps it to named objects once and caches the result on the person,
   so a second drill-down (or the CSV export) pays nothing. */
const NESTED_MAP = {per_cycle:'pc', udp_per_cycle:'upc', self_funding_per_cycle:'sf', other_committees_per_cycle:'oc', all_ie_per_cycle:'aie', all_ie_top_committees:'tc'};
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
  sortKey:'dirty_2026', sortDir:'desc', tab:'tracker', mode:'front', rendered:{}};
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
  const totalsKey = [state.q, state.congress, state.chamber, state.party, state.state, state.leadership, state.clean].join('|');
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
  if(state.clean) chips.push({k:'clean', label:'Not dirty in 2026 only'});
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
  // U6: one line under the hook saying what counts as dirty, in the
  // explainer's exact phrasing, under the current tolerance preset.
  const preset = PRESETS[state.preset];
  document.getElementById('hook-definition').textContent =
    'Dirty money is money from sources other than individual contributors — '
    + preset.short
    + (state.preset==='strict' ? '.' : '; any AIPAC direct or UDP benefit dollar always counts.');
  document.getElementById('dirtiest-list').innerHTML = rows.map((p,i)=>
    '<li style="transition-delay:'+(i*90)+'ms"><button type="button" class="dirty-row" data-key="'+esc(p.person_key)+'">'
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
    '<p class="big-number"><span class="countup" data-value="'+nd.length+'" data-format="int">'+nd.length+'</span> of <span class="countup" data-value="'+incoming.length+'" data-format="int">'+incoming.length+'</span></p>'
    + '<p class="big-label">took no dirty money in 2026</p>'
    + '<p>'+hND+' House + '+sND+' Senate. '
    + preset.label+' tolerance: '+preset.short+'. Any AIPAC direct or UDP benefit dollar always counts. '
    + '<button type="button" class="linklike" id="story-clean-link">See the list</button></p>';
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
function chartAltText(seats, label){
  // A sentence-form text alternative for the chart (FE10): the
  // legend already shows the same counts visually.
  const count = (letter, status)=>seats.filter(s=>s.letter===letter && s.status===status).length;
  const parts = [];
  ['D','R','I'].forEach(L=>{
    const d = count(L,'dirty'), c = count(L,'clean');
    if(d) parts.push(d+' Dirty '+L);
    if(c) parts.push(c+' Clean '+L);
  });
  const unopp = seats.filter(s=>s.status==='unopposed').length;
  const unver = seats.filter(s=>s.status==='unverified').length;
  const unc = seats.filter(s=>s.status==='uncalled').length;
  if(unopp) parts.push(unopp+' unopposed');
  if(unver) parts.push(unver+' unverified');
  if(unc) parts.push(unc+' uncalled');
  return label+': '+seats.length+' seats — '+parts.join(', ')+'.';
}
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
    status:seatStatus(p), name:p.full_name, key:p.person_key}));
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
  // Stagger by column so the waffle fills left to right on reveal —
  // scaled so the whole stagger stays under ~500ms (FE10).
  return '<g class="dot '+s.status+'" data-party="'+esc(s.letter)+'"'+(s.key?' data-key="'+esc(s.key)+'"':'')+' style="transition-delay:'+(Math.round(col*480/(WAFFLE_COLS-1)))+'ms">'+inner
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
const TILE_W = 60, TILE_H = 46, TILE_GAP = 5, TILE_COLS = 10, TILE_COLS_NARROW = 5;
/* ---- Senate tiles: 5 columns below 560px (D1) ----
   Ten tiles across is unreadable on a phone, so the grid reflows
   to 5 x 10 under the 560px breakpoint. The column count is read
   at render time; a resize that crosses the breakpoint re-renders
   the composition (see init). */
function senateCols(){
  try{
    return (typeof window!=='undefined' && window.matchMedia
      && window.matchMedia('(max-width: 560px)').matches)
      ? TILE_COLS_NARROW : TILE_COLS;
  }catch(e){ return TILE_COLS; }
}
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
        status:seatStatus(p), name:p.full_name, key:p.person_key}));
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
  return '<rect class="half '+half.status+'" data-party="'+esc(half.letter)+'"'+(half.key?' data-key="'+esc(half.key)+'"':'')+' x="'+x+'" y="'+y
    +'" width="'+w+'" height="'+h+'" '+attrs+'><title>'+esc(title)+'</title></rect>';
}
function senateTilesSVG(){
  const states = senateStates();
  const cols = senateCols();
  const rows = Math.ceil(states.length/cols);
  const W = cols*TILE_W + (cols-1)*TILE_GAP;
  const H = rows*TILE_H + (rows-1)*TILE_GAP;
  const defs = '<defs>' + ['D','R','I'].map(L=>{
    const c = {D:'#1e40af', R:'#991b1b', I:'#374151'}[L];
    return '<pattern id="dots-'+L+'" width="7" height="7" patternUnits="userSpaceOnUse">'
      + '<rect width="7" height="7" fill="#111827"/>'
      + '<circle cx="3.5" cy="3.5" r="1.4" fill="'+c+'"/></pattern>';
  }).join('') + '</defs>';
  let tiles = '';
  states.forEach((st, i)=>{
    const col = i%cols, row = Math.floor(i/cols);
    const x = col*(TILE_W+TILE_GAP), y = row*(TILE_H+TILE_GAP);
    const title = (STATE_NAMES[st.code]||st.code)+' — '+st.halves.map(h=>
      h.status==='uncalled' ? 'seat uncalled'
      : h.name+' ('+h.letter+', '+({dirty:'took dirty money in 2026',
        clean:'verified clean in 2026', unopposed:'ran unopposed',
        unverified:'unverified'}[h.status])+')').join('; ');
    // Stagger the tiles on reveal, scaled so the whole stagger stays
    // under ~500ms (FE10).
    tiles += '<g class="tile" data-state="'+esc(st.code)+'" style="transition-delay:'+(Math.round(i*480/49))+'ms">'
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
    + '<figcaption>House — '+h.total+' voting seats</figcaption>'+legendHTML(h.seats,'dot')
    + '<p class="visually-hidden">'+esc(chartAltText(h.seats, 'House'))+'</p></figure>'
    + '<figure>'+senateTilesSVG()
    + '<figcaption>Senate — '+s.total+' seats</figcaption>'+legendHTML(s.seats,'dots')
    + '<p class="visually-hidden">'+esc(chartAltText(s.seats, 'Senate'))+'</p></figure>'
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
