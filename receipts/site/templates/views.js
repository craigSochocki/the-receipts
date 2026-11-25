
"use strict";
/* ---- detail overlay ---- */
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
function openDetail(key, opts){
  const p = BY_KEY[key]; if(!p) return;
  // Loading state first (FE1a): the sheet opens with the name and a
  // loading line; the nested lists then decode synchronously (trivial
  // for one person) and the full breakdown fills in the same task.
  lastFocused = document.activeElement || null;
  document.getElementById('detail-sheet').innerHTML = '<h2>'+esc(p.full_name)+'</h2><p>Loading the full breakdown…</p>';
  document.getElementById('detail').classList.add('open');
  decodeNested(p);
  // D9: cycle tables collapse into <details>, the first one open —
  // the drill-down is otherwise a wall of tables on a phone. The
  // U10 anchor nav opens the target <details> before jumping to it.
  let firstCycle = true;
  function cycle(title, rows, cols, id){
    const h = cycleTable(title, rows, cols, firstCycle, id);
    if(h) firstCycle = false;
    return h;
  }
  const leader = [p.leadership_119, (p.leadership_120 && p.leadership_120!=='TBD') ? p.leadership_120 : null].filter(Boolean).join('; ');
  // U10: prev/next walk the filtered, sorted tracker set — the rows
  // the table is showing. Disabled at the ends, or when this person
  // is not in the set at all. Navigation replaces the URL, not pushes.
  const set = sortRows(applyFilters());
  const idx = set.findIndex(x=>x.person_key===key);
  const prevKey = idx>0 ? set[idx-1].person_key : null;
  const nextKey = idx>=0 && idx<set.length-1 ? set[idx+1].person_key : null;
  let h = '<div class="detail-top"><h2>'+esc(p.full_name)+'</h2><div class="detail-actions">'
    + '<button class="btn ghost" id="detail-prev" type="button"'+(prevKey?'':' disabled')+'>← Prev</button>'
    + '<button class="btn ghost" id="detail-next" type="button"'+(nextKey?'':' disabled')+'>Next →</button>'
    + '<button class="btn ghost close" id="detail-close" type="button">Close ✕</button>'
    + '</div></div>';
  // U10: anchor nav — jumps to a section, opening its <details>
  // first, and moves focus there. Buttons, not href="#…" links, so a
  // jump never fights the FE5 hash scheme.
  h += '<div class="detail-nav">'
    + '<button class="btn ghost" type="button" data-anchor="sec-career">Career</button>'
    + '<button class="btn ghost" type="button" data-anchor="sec-cycle">'+esc(CY)+'</button>'
    + '<button class="btn ghost" type="button" data-anchor="sec-cycle-money">By cycle</button>'
    + (p.all_ie_top_committees && p.all_ie_top_committees.length ? '<button class="btn ghost" type="button" data-anchor="sec-spenders">Outside spenders</button>' : '')
    + (p.data_notes ? '<button class="btn ghost" type="button" data-anchor="sec-notes">Notes</button>' : '')
    + '<button class="btn ghost" id="detail-tracker" type="button">View in Tracker →</button>'
    + '</div>';
  h += '<p class="meta">'+partyChip(p)+' '+esc(party(p))+' · '+esc(chamber(p))+' · '+esc(place(p))+' · '+outcomeLabel(p)+' · '+esc(congressLabel(p))
    + (leader ? ' · '+esc(leader) : '') + ' · FEC ID'+(p.fec_candidate_ids.length>1?'s':'')+': '
    + esc(p.fec_candidate_ids.join(', ')||'none') + '</p>';
  // D6/FE3: the detail header always shows exact figures — Dirty
  // the selected cycle and total accepted — whatever the compact/exact toggle says.
  h += '<p class="detail-head">Dirty '+esc(CY)+' <b>'+fmtMoney(p.cy_dirty)+'</b> · Total accepted (career) <b>'+fmtMoney(p.total_accepted_career)+'</b></p>';
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
  h += '<p style="color:var(--muted);font-size:.85rem">Data as of '+esc(p.data_as_of)+' · Person key '+esc(p.person_key)+' · Figures trace to FEC filings; see Methodology.</p>';
  document.getElementById('detail-sheet').innerHTML = h;
  document.getElementById('detail-close').addEventListener('click', closeDetail);
  if(prevKey) document.getElementById('detail-prev').addEventListener('click', ()=>openDetail(prevKey, {push:false}));
  if(nextKey) document.getElementById('detail-next').addEventListener('click', ()=>openDetail(nextKey, {push:false}));
  document.getElementById('detail-tracker').addEventListener('click', ()=>viewInTracker(key));
  // U10: anchor buttons jump to their section (open its <details>
  // first) and move focus there.
  Array.prototype.slice.call(document.getElementById('detail-sheet').querySelectorAll('[data-anchor]')).forEach(b=>{
    b.addEventListener('click', ()=>goAnchor(b.getAttribute('data-anchor')));
  });
  const closeBtn = document.getElementById('detail-close');
  if(closeBtn && typeof closeBtn.focus==='function') closeBtn.focus();
  // FE5: the open sheet lives in the URL — a push for a fresh open
  // (Back closes it), a replace for prev/next and hash restores.
  detailKey = key;
  if(!opts || opts.push!==false) syncHash(false);
  else syncHash(true);
}
/* ---- detail focus trap + restore (FE4) ----
   Opening the sheet remembers what had focus and moves focus to
   Close; Tab cycles within the sheet; closing hands focus back. */
let lastFocused = null;
function detailFocusable(){
  const sheet = document.getElementById('detail-sheet');
  if(!sheet) return [];
  // querySelectorAll returns a NodeList in browsers (no .filter),
  // a plain array in the smoke-test DOM — slice handles both.
  const els = sheet.querySelectorAll('button, a[href], [tabindex]');
  return Array.prototype.slice.call(els).filter(el=>!el.disabled);
}
/* ---- drill-down anchor nav + View in Tracker (U10) ----
   Anchors are buttons, not href="#…" links: a hash change would fight
   the FE5 hash scheme. A <details> target opens first; focus moves to
   the section so keyboard readers land where they jumped. */
function goAnchor(id){
  const target = document.getElementById(id);
  if(!target) return;
  if(target.tagName==='DETAILS') target.open = true;
  const focusEl = target.tagName==='DETAILS' ? target.querySelector('summary') : target;
  if(focusEl && typeof focusEl.focus==='function') focusEl.focus();
  else if(typeof target.scrollIntoView==='function') target.scrollIntoView();
}
function viewInTracker(key){
  const p = BY_KEY[key]; if(!p) return;
  // Close without a hash write, then filter the Tracker tab to this
  // person — like findPerson, but without reopening the sheet.
  closeDetail({pop:false});
  state.q = p.full_name;
  document.getElementById('q').value = state.q;
  showTab('tracker');
  renderTable();
}
function closeDetail(opts){
  const sheet = document.getElementById('detail');
  if(!sheet.classList.contains('open') && detailKey===null) return;
  detailKey = null;
  sheet.classList.remove('open');
  if(lastFocused && typeof lastFocused.focus==='function') lastFocused.focus();
  lastFocused = null;
  // From the hashchange handler the hash already moved (Back/forward):
  // write nothing. Otherwise strip the detail from the URL (replace —
  // the Close button should not add a history entry).
  if(!(opts && opts.pop===false)) syncHash(true);
}

/* ---- leaderboards ---- */
function topByRank(rankKey, amountKey, n){
  return PEOPLE.filter(p=>num(p[rankKey])!==null)
    .sort((a,b)=>a[rankKey]-b[rankKey]).slice(0,n)
    .map(p=>({key:p.person_key, name:p.full_name, who:partyChip(p)+' '+esc(party(p))+' · '+esc(place(p))+' · '+outcomeLabel(p), amount:p[amountKey]}));
}
function boardHtml(title, sub, entries){
  let h = '<h3>'+esc(title)+'</h3><p style="color:var(--muted);font-size:.9rem">'+esc(sub)+'</p><ol class="leader">';
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
  document.getElementById('leaders').innerHTML =
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
  // U3: leaderboards are clickable — one delegated listener, so the
  // rows need no per-row handlers.
  document.getElementById('leaders').addEventListener('click', e=>{
    const b = e.target.closest('.leader-row');
    if(b) openDetail(b.getAttribute('data-key'));
  });
}

/* ---- clean view (preset-aware) ----
   Under Strict the tab lists verified-clean members; under Balanced
   / Lenient it lists everyone not dirty under the preset — clean
   plus the below-threshold middle tier, whose corporate PAC amount
   is always shown. Counts are computed from PEOPLE at render time
   and always labeled with the preset. */
function renderClean(){
  const {incoming, nd, hND, sND} = notDirtyCounts();
  const careerCleanHouse = incoming.filter(p=>p.chamber_120==='House'&&isCareerClean(p));
  const ndAll = PEOPLE.filter(isNotDirty);
  const unopp = PEOPLE.filter(p=>p.cy_unopposed===true);
  const unver = PEOPLE.filter(p=>p.cy_clean===null && p.cy_unopposed!==true);
  const preset = PRESETS[state.preset];
  const word = state.preset==='strict' ? 'verified clean' : 'not dirty';
  document.getElementById('clean-stats').innerHTML =
    '<div class="stats">'
    + '<div class="stat"><b>'+hND+' of 436</b>incoming House '+word+' '+IN_CY+' ('+preset.label+')</div>'
    + '<div class="stat"><b>'+sND+' of 99</b>incoming Senate '+word+' '+IN_CY+' ('+preset.label+')</div>'
    + '<div class="stat"><b>'+nd.length+' total</b>'+word+' in the incoming 120th ('+preset.label+')</div>'
    + '<div class="stat"><b>'+careerCleanHouse.length+'</b>career-clean incoming House members</div>'
    + '<div class="stat"><b>'+unopp.length+' ran unopposed</b>'+IN_CY+' — no opponent with receipts over $0, so not counted clean: '+esc(unopp.map(p=>p.full_name).join(', '))+'</div>'
    + '<div class="stat"><b>'+unver.length+' unverified</b>'+esc(unver.map(p=>p.full_name).join(', '))+'</div>'
    + '</div>'
    + '<p style="color:var(--muted)">'+ndAll.length+' people in the whole tracker are '+word+' '+IN_CY+' under the '+preset.label+' tolerance — the '+nd.length+' above plus '
    + (ndAll.length-nd.length) + ' outgoing 119th-only members. Click a row for the full breakdown.</p>';
  const mid = state.preset==='strict' ? ''
    : ' The middle tier — “Below threshold” — took corporate PAC money below those thresholds; it is never called clean, and the dollar amount is always shown.';
  document.getElementById('clean-callout').innerHTML =
    '<b>What “'+word+' '+IN_CY+'” means under the '+preset.label+' tolerance:</b> '+preset.def
    + ' It is a cycle test, not a career test — a member can be '+word+' '+IN_CY+' while having taken such money in earlier cycles.'+mid
    + ' A member is shown as <b>unverified</b> only if they have no entries '+IN_CY+' in <i>any</i> money source — usually because their real campaign is not linked in the roster.';
  const thead = document.querySelector('#clean-table thead');
  const tbody = document.querySelector('#clean-table tbody');
  thead.innerHTML = '<tr><th>Name</th><th>State / Dist.</th><th>Party</th><th>Chamber</th><th>Incoming 120th?</th><th>Tier '+esc(CY)+'</th><th class="num">Corp PAC '+esc(CY)+'</th><th class="num">Dirty '+esc(CY)+'</th><th>Career-clean?</th></tr>';
  const rows = ndAll.slice().sort((a,b)=>a.full_name.localeCompare(b.full_name));
  tbody.innerHTML = rows.map(p=>'<tr data-key="'+esc(p.person_key)+'"><td class="name">'+esc(p.full_name)+'</td><td>'+esc(place(p))+'</td><td>'+partyChip(p)+' '+esc(party(p))+'</td><td>'+esc(chamber(p))+'</td><td>'+(p.in_120th==='yes'?'Yes':'No — 119th only')+'</td><td>'+fmtTierBadge(p)+'</td><td class="num">'+moneyShort(p.cy_corp)+'</td><td class="num">'+moneyShort(p.cy_dirty)+'</td><td>'+(isCareerClean(p)?'Yes':'No')+'</td></tr>').join('');
  tbody.querySelectorAll('tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- party breakdown ---- */
function renderBreakdown(){
  document.getElementById('breakdown-intro').textContent =
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
  document.querySelector('#breakdown-table thead').innerHTML =
    '<tr><th>Party</th><th>Chamber</th><th class="num">Members</th><th class="num">Individual (career)</th><th class="num">Corp PAC (career)</th><th class="num">AIPAC (career)</th><th class="num">Total accepted</th><th class="num">UDP benefit</th><th class="num">Self-funding</th><th class="num">All IE total</th><th class="num">Not dirty '+esc(CY)+' ('+PRESETS[state.preset].label+')</th></tr>';
  document.querySelector('#breakdown-table tbody').innerHTML =
    rows.map(rowHtml).join('') + '<tr><td><b>All</b></td><td><b>120th</b></td><td class="num"><b>'+tot.n+'</b></td><td class="num"><b>'+moneyShort(tot.ind)+'</b></td><td class="num"><b>'+moneyShort(tot.corp)+'</b></td><td class="num"><b>'+moneyShort(tot.aipac)+'</b></td><td class="num"><b>'+moneyShort(tot.tot)+'</b></td><td class="num"><b>'+moneyShort(tot.udp)+'</b></td><td class="num"><b>'+moneyShort(tot.self)+'</b></td><td class="num"><b>'+moneyShort(tot.ie)+'</b></td><td class="num"><b>'+tot.clean+'</b></td></tr>';
}

/* ---- primary targets for the next cycle ----
   Incoming members of any party whose seat is up next cycle (every
   House seat; Senate seats of that cycle's class) and who took dirty
   money in their latest election under the preset. The rule is
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
  const rows = primaryTargets();
  const preset = PRESETS[state.preset];
  const house = rows.filter(p=>p.chamber_120==='House').length;
  document.getElementById('targets-intro').innerHTML =
    'A watchlist, not a prediction. '+rows.length+' incoming members whose seat is up in '+NEXT_CYCLE
    +' took dirty money in their latest election ('+house+' House + '+(rows.length-house)+' Senate), any party, under the '
    +preset.label+' tolerance ('+preset.short+'; any AIPAC direct or UDP benefit dollar always counts). Retirements are unknown and '
    +NEXT_CYCLE+' filings are barely open. The rule is mechanical — dirty money only; the tracker does not judge electability or anything else.';
  document.querySelector('#targets-table thead').innerHTML =
    '<tr><th>#</th><th>Name</th><th>Party</th><th>Seat</th><th class="num">Election</th><th class="num">Dirty</th><th class="num">Corp PAC</th><th class="num">AIPAC</th><th class="num">UDP benefit</th><th class="num">Dirty career</th><th class="num">Individual</th></tr>';
  document.querySelector('#targets-table tbody').innerHTML = rows.map((p,i)=>{
    const r = cycleRecord(p, 'latest');
    const flag = r.aipac_udp_flag===true ? ' <span class="badge flag" title="AIPAC PAC direct money or UDP benefit in their latest election">AIPAC/UDP</span>' : '';
    return '<tr data-key="'+esc(p.person_key)+'"><td>'+(i+1)+'</td><td class="name">'+esc(p.full_name)+flag+'</td><td>'+esc(party(p))+'</td><td>'+esc(place(p))+'</td><td class="num">'+r.cycle+'</td>'
      + ['dirty','corp','aipac_direct','udp_benefit'].map(k=>'<td class="num">'+fmtMoney(r[k])+'</td>').join('')
      + '<td class="num">'+fmtMoney(p.dirty_career)+'</td><td class="num">'+fmtMoney(r.individual)+'</td></tr>';
  }).join('');
  document.querySelectorAll('#targets-table tbody tr').forEach(tr=>tr.addEventListener('click', ()=>openDetail(tr.getAttribute('data-key'))));
}

/* ---- tolerance preset switching ----
   Recomputes every preset-dependent surface live: header stats, the
   table badges, the front-door story, and the clean / breakdown /
   targets tabs (re-rendered on next show if not current). The
   leaderboards are Strict and do not move with the preset. */
const TAB_RENDER = {leaders:renderLeaders, clean:renderClean, breakdown:renderBreakdown,
  targets:renderTargets};
// Re-render the shown tab now; the others re-render when next shown.
function refreshTabs(tabs){
  tabs.forEach(t=>{
    state.rendered[t] = (state.tab===t);
    if(state.tab===t) TAB_RENDER[t]();
  });
}
function setPreset(preset){
  if(!PRESETS[preset]) return;
  state.preset = preset;
  document.getElementById('tolerance-note').textContent = PRESETS[preset].def;
  renderStats(); renderTable(); renderCleanStory(); renderDirtiest();
  refreshTabs(['clean','breakdown','targets']);
}

/* ---- cycle switching: every board, chart and table reads the
   selected cycle's record through the cy_ fields. ---- */
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
  renderViewBtns(); renderStats(); renderTable(); renderCleanStory();
  renderDirtiest(); renderDirtyExplainer(); renderComposition();
  refreshTabs(Object.keys(TAB_RENDER));
}

/* ---- money format switching (D6/FE3) ----
   Re-renders the surfaces moneyShort feeds (table, clean and
   breakdown tabs); the leaderboards, targets and front-door
   headlines already show exact figures or stay compact by design. */
function setMoneyFmt(fmt){
  if(fmt!=='exact' && fmt!=='compact') return;
  state.moneyFmt = fmt;
  saveMoneyFmt(fmt);
  renderTable();
  ['clean','breakdown'].forEach(t=>{
    if(state.tab===t){
      if(t==='clean') renderClean();
      if(t==='breakdown') renderBreakdown();
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

/* ---- header stats ---- */
// Pure function of (preset, PEOPLE) — cached per preset (FE2).
const statsCache = {};
function renderStats(){
  const statsKey = state.preset+'|'+state.cycle;
  if(statsCache[statsKey]){ document.getElementById('stats').innerHTML = statsCache[statsKey]; return; }
  const {incoming, nd, hND, sND} = notDirtyCounts();
  const unopp = PEOPLE.filter(p=>p.cy_unopposed===true);
  const unver = PEOPLE.filter(p=>p.cy_clean===null && p.cy_unopposed!==true);
  const word = state.preset==='strict' ? 'verified clean' : 'not dirty';
  // D7: three cards only — the two that matter plus one combined
  // "not judged" card (ran unopposed + unverified, with names).
  // The dropped totals (individual, outside spending, self-funding)
  // already live in the filtered totals strip below the table.
  const h =
    '<div class="stat"><b>'+PEOPLE.length+'</b>people tracked</div>'
    + '<div class="stat"><b>'+nd.length+' '+word+'</b>'+IN_CY+' — '+hND+' House + '+sND+' Senate ('+PRESETS[state.preset].label+' tolerance)</div>'
    + '<div class="stat"><b>'+(unopp.length+unver.length)+' not judged</b>'+unopp.length+' ran unopposed '+IN_CY+' — no opponent with receipts over $0: '+esc(unopp.map(p=>p.full_name).join(', '))+' · '+unver.length+' unverified: '+esc(unver.map(p=>p.full_name).join(', '))+'</div>';
  statsCache[statsKey] = h;
  document.getElementById('stats').innerHTML = h;
}

/* ---- front door vs full-data mode, and the URL hash (FE5) ----
   Default (no hash) is the front door; #explore opens the full-data
   workspace. The hash carries the whole view — mode, tab, filters,
   preset, view, sort, and the open drill-down — so a view is
   shareable and Back/forward restores it. Only non-default values are
   written, so a plain #explore still means "defaults".
   Mode changes and drill-down opens push a history entry (Back
   returns); filter/tab/preset changes replace the current entry, so
   typing in the search box does not spam history. No-JS fallback shows
   the full-data page: the hidden flags are applied by init(), never
   baked into the HTML. */
function modeFromHash(){
  let h = '';
  try{ h = (typeof location!=='undefined' && location.hash) || ''; }catch(e){ h = ''; }
  h = h.replace(/^#/,'');
  return (h==='explore' || h.indexOf('explore?')===0) ? 'explore' : 'front';
}
function safeDecode(s){
  try{ return decodeURIComponent(s); }catch(e){ return s; }
}
function currentHash(){
  try{ return (typeof location!=='undefined' && location.hash) || ''; }catch(e){ return ''; }
}
function hashFromState(){
  const parts = [];
  if(state.tab!=='tracker') parts.push('tab='+encodeURIComponent(state.tab));
  if(state.q.trim()) parts.push('q='+encodeURIComponent(state.q.trim()));
  if(state.congress!=='all') parts.push('congress='+state.congress);
  if(state.chamber!=='all') parts.push('chamber='+state.chamber);
  if(state.party!=='all') parts.push('party='+encodeURIComponent(state.party));
  if(state.state!=='all') parts.push('state='+state.state);
  if(state.leadership) parts.push('leader=1');
  if(state.clean) parts.push('clean=1');
  if(state.view!=='core') parts.push('view='+state.view);
  if(state.preset!=='balanced') parts.push('preset='+state.preset);
  if(state.cycle!=='latest') parts.push('cycle='+state.cycle);
  if(state.sortKey!=='cy_dirty') parts.push('sort='+encodeURIComponent(state.sortKey));
  if(state.sortDir!=='desc') parts.push('dir='+state.sortDir);
  if(detailKey) parts.push('detail='+encodeURIComponent(detailKey));
  if(state.mode==='explore') return 'explore'+(parts.length ? '?'+parts.join('&') : '');
  return detailKey ? 'detail='+encodeURIComponent(detailKey) : '';
}
function writeHash(h, replace){
  const target = h ? '#'+h : '';
  // No-op guard: the serialized state already matches the URL, so
  // there is nothing to write — and no hashchange to loop on.
  if(target===currentHash()) return;
  try{
    if(replace && typeof history!=='undefined' && history.replaceState){
      history.replaceState(null, '', target || '#');
      return;
    }
  }catch(e){}
  try{ location.hash = target; }catch(e){}
}
function syncHash(replace){ writeHash(hashFromState(), !!replace); }
function parseHash(){
  const out = {mode:'front', tab:'tracker', q:'', congress:'all', chamber:'all',
    party:'all', state:'all', leadership:false, clean:false, view:'core',
    preset:'balanced', cycle:'latest', sortKey:'cy_dirty', sortDir:'desc', detail:null};
  let h = currentHash().replace(/^#/,'');
  if(!h) return out;
  out.mode = modeFromHash();
  let params = '';
  if(h==='explore'){ /* defaults */ }
  else if(h.indexOf('explore?')===0){ params = h.slice('explore?'.length); }
  else if(h.indexOf('detail=')===0){
    const d = safeDecode(h.slice('detail='.length));
    if(BY_KEY[d]) out.detail = d;
    return out;
  }
  else if(h.indexOf('?')>=0){ params = h.slice(h.indexOf('?')+1); }
  else { return out; }
  params.split('&').forEach(pair=>{
    if(!pair) return;
    const eq = pair.indexOf('=');
    const k = eq<0 ? pair : pair.slice(0,eq);
    const v = eq<0 ? '' : safeDecode(pair.slice(eq+1));
    if(k==='tab' && ['tracker','leaders','clean','breakdown','targets','method'].indexOf(v)>=0) out.tab = v;
    else if(k==='q') out.q = v;
    else if(k==='congress' && ['119','120','both','all'].indexOf(v)>=0) out.congress = v;
    else if(k==='chamber' && ['House','Senate','all'].indexOf(v)>=0) out.chamber = v;
    else if(k==='party' && ['Democrat','Republican','Independent','PPD','all'].indexOf(v)>=0) out.party = v;
    else if(k==='state' && /^[A-Z]{2}$/.test(v)) out.state = v;
    else if(k==='leader' && v==='1') out.leadership = true;
    else if(k==='clean' && v==='1') out.clean = true;
    else if(k==='view' && VIEWS[v]) out.view = v;
    else if(k==='preset' && PRESETS[v]) out.preset = v;
    else if(k==='cycle' && isCycleChoice(cycleValue(v))) out.cycle = cycleValue(v);
    else if(k==='sort' && SORTABLE.has(v)) out.sortKey = v;
    else if(k==='dir' && (v==='asc' || v==='desc')) out.sortDir = v;
    else if(k==='detail' && BY_KEY[v]) out.detail = v;
  });
  return out;
}
function applyHash(){
  const p = parseHash();
  // Detail first: open the hashed person, or close a sheet the hash
  // no longer names (this is how Back closes the sheet).
  if(p.detail && BY_KEY[p.detail]){
    if(detailKey!==p.detail) openDetail(p.detail, {push:false});
  } else if(document.getElementById('detail').classList.contains('open')){
    closeDetail({pop:false});
  }
  // Unconditional: on load the mode already matches the default, but
  // the hidden flags still need applying (no-JS fallback leaves the
  // full-data page visible in the HTML). updateHash===false, so this
  // never scrolls or moves focus.
  setMode(p.mode, false);
  // Only touch what differs, and never scroll or move focus — a
  // hashchange / back-forward must restore the view without yanking
  // the reader (U1).
  let filtersChanged = false, presetChanged = false;
  const setField = (key, val)=>{ if(state[key]!==val){ state[key]=val; filtersChanged=true; } };
  setField('q', p.q); setField('congress', p.congress); setField('chamber', p.chamber);
  setField('party', p.party); setField('state', p.state); setField('leadership', p.leadership);
  setField('clean', p.clean); setField('view', p.view);
  setField('sortKey', p.sortKey); setField('sortDir', p.sortDir);
  if(p.cycle!==state.cycle){ setCycle(p.cycle); document.getElementById('f-cycle').value = String(p.cycle); }
  if(p.preset!==state.preset){ setPreset(p.preset); presetChanged = true; }
  if(filtersChanged || presetChanged){
    // Push the parsed values into the controls (setting .value fires
    // no change event) and re-render the table — unless setPreset
    // already did.
    document.getElementById('q').value = state.q;
    document.getElementById('f-congress').value = state.congress;
    document.getElementById('f-chamber').value = state.chamber;
    document.getElementById('f-party').value = state.party;
    document.getElementById('f-state').value = state.state;
    document.getElementById('f-leader').checked = state.leadership;
    document.getElementById('f-clean').checked = state.clean;
    if(!presetChanged) renderTable();
  }
  // The tab only exists in Explore: a front-door hash carries no tab,
  // and showTab would force the mode back to Explore if called here.
  if(p.mode==='explore' && p.tab!==state.tab) showTab(p.tab, {scroll:false});
}
/* ---- U1 (leftovers): the finder, reachable from Explore ----
   One finder node, moved between the front-door chapter and an
   Explore <details> slot in the tracker section. Moving a node keeps
   its listeners (initFinder), so there is still exactly one finder;
   its input and results survive the move. */
let finderHome = null;
function placeFinder(){
  const finder = document.getElementById('finder');
  const slot = document.getElementById('finder-slot');
  if(!finder || !slot) return;
  if(!finderHome) finderHome = {parent: finder.parentNode, next: finder.nextSibling};
  if(state.mode==='explore'){
    if(finder.parentNode!==slot) slot.appendChild(finder);
  } else if(finder.parentNode!==finderHome.parent){
    finderHome.parent.insertBefore(finder, finderHome.next);
  }
}
function setMode(mode, updateHash){
  state.mode = mode;
  // Push the mode change first: ensureExplore renders the table, and
  // renderTable syncs the hash — if that replace landed first, the
  // push below would be a no-op and Back would skip the front door.
  if(updateHash!==false) syncHash(false);
  if(mode==='explore') ensureExplore();
  const front = mode==='front';
  document.getElementById('front-door').hidden = !front;
  document.getElementById('explore-head').hidden = front;
  document.getElementById('tabs-nav').hidden = front;
  document.getElementById('main').hidden = front;
  document.querySelector('footer').hidden = front;
  placeFinder();
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

/* ---- deferred Explore render (FE7) ----
   The full-data workspace is hidden on the front door, so its table,
   stats, and view buttons render on first entry into Explore instead
   of at load. Entering Explore — setMode, showTab, or the finder
   handoff — renders it; a #explore load renders it eagerly at init
   because setMode runs from the hash there. */
let exploreRendered = false;
function ensureExplore(){
  if(exploreRendered) return;
  exploreRendered = true;
  renderStats(); renderViewBtns(); renderTable();
  state.rendered.tracker = true;
}

/* ---- tabs + init ---- */
function showTab(name, opts){
  if(state.mode!=='explore') setMode('explore');
  state.tab = name;
  document.querySelectorAll('.tabs button').forEach(b=>b.setAttribute('aria-selected', String(b.getAttribute('data-tab')===name)));
  ['tracker','leaders','clean','breakdown','targets','method'].forEach(t=>{
    document.getElementById('tab-'+t).hidden = (t!==name);
  });
  if(!state.rendered[name] && TAB_RENDER[name]){
    state.rendered[name]=true;
    TAB_RENDER[name]();
  }
  syncHash(true);
  // Tab change: top of the page, focus on the panel — but not on
  // hashchange / back-forward (U1): applyHash passes scroll:false.
  if(!opts || opts.scroll!==false){
    try{ if(typeof window!=='undefined' && typeof window.scrollTo==='function') window.scrollTo(0,0); }catch(e){}
    const panel = document.getElementById('tab-'+name);
    if(panel && typeof panel.focus==='function') panel.focus();
  }
}
function init(){
  // Gate the hidden-before-reveal state on JS actually running: no-JS
  // never gets the .js class, so every chapter stays visible.
  try{ if(document.documentElement && document.documentElement.classList) document.documentElement.classList.add('js'); }catch(e){}
  const states = [...new Set(PEOPLE.map(p=>p.state))].sort();
  document.getElementById('f-state').innerHTML = '<option value="all">All states</option>'
    + states.map(s=>'<option value="'+esc(s)+'">'+esc(s)+'</option>').join('');
  renderDirtiest(); renderDirtyExplainer(); renderCleanStory(); renderComposition(); initFinder();
  // D1: a resize that crosses the 560px breakpoint reflows the
  // Senate tiles (5 wide on phones, 10 wide otherwise). Debounced,
  // and only when the column count actually changes.
  let lastSenateCols = senateCols();
  let resizeTimer = null;
  if(typeof window!=='undefined' && typeof window.addEventListener==='function'){
    window.addEventListener('resize', ()=>{
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(()=>{
        const c = senateCols();
        if(c!==lastSenateCols){ lastSenateCols = c; renderComposition(); }
      }, 150);
    });
  }
  // U4: the charts are tappable — one delegated listener on the
  // composition container opens the drill-down for the dot or tile
  // half clicked. Attached once, on the container, so it survives
  // re-renders (D1) and works while the reveal is still running
  // (opacity never blocks pointer events). Per-dot keyboard focus
  // was cut: 435 dots would be ~535 tab stops.
  document.getElementById('composition').addEventListener('click', e=>{
    const t = e.target && e.target.closest ? e.target.closest('[data-key]') : null;
    if(t) openDetail(t.getAttribute('data-key'));
  });
  initReveals();
  // FE5: the hash is the state — restore mode, tab, filters, preset
  // and the open drill-down from it on load.
  applyHash();
  document.getElementById('home-link').addEventListener('click', e=>{
    e.preventDefault();
    setMode('front');
  });
  // U5: skip link — one Tab from the top of the page jumps straight
  // to the data (Explore), with focus on the tab bar.
  document.getElementById('skip-link').addEventListener('click', e=>{
    e.preventDefault();
    setMode('explore');
  });
  document.getElementById('explore-btn').addEventListener('click', ()=>setMode('explore'));
  document.getElementById('targets-btn').addEventListener('click', ()=>showTab('targets'));
  if(typeof window!=='undefined' && typeof window.addEventListener==='function'){
    window.addEventListener('hashchange', ()=>applyHash());
  }
  let searchTimer = null;
  document.getElementById('q').addEventListener('input', e=>{
    state.q = e.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(renderTable, 150);
  });
  // One delegated listener on the table body (FE2) — it survives
  // every innerHTML re-render, so rows need no listeners of their own.
  document.querySelector('#main-table tbody').addEventListener('click', e=>{
    const row = e.target.closest ? e.target.closest('tr') : null;
    if(row) openDetail(row.getAttribute('data-key'));
  });
  document.getElementById('f-congress').addEventListener('change', e=>{ state.congress=e.target.value; renderTable(); });
  document.getElementById('f-chamber').addEventListener('change', e=>{ state.chamber=e.target.value; renderTable(); });
  document.getElementById('f-party').addEventListener('change', e=>{ state.party=e.target.value; renderTable(); });
  document.getElementById('f-state').addEventListener('change', e=>{ state.state=e.target.value; renderTable(); });
  document.getElementById('f-leader').addEventListener('change', e=>{ state.leadership=e.target.checked; renderTable(); });
  document.getElementById('f-clean').addEventListener('change', e=>{ state.clean=e.target.checked; renderTable(); });
  document.getElementById('f-tolerance').addEventListener('change', e=>{ setPreset(e.target.value); });
  const cyclePicker = document.getElementById('f-cycle');
  cyclePicker.innerHTML = CYCLE_CHOICES.map(c=>'<option value="'+c+'">'+(c==='latest' ? 'Latest election' : c)+'</option>').join('');
  cyclePicker.value = String(state.cycle);
  cyclePicker.addEventListener('change', e=>{ setCycle(cycleValue(e.target.value)); syncHash(true); });
  document.getElementById('f-money').value = state.moneyFmt;
  document.getElementById('f-money').addEventListener('change', e=>{ setMoneyFmt(e.target.value); });
  document.getElementById('tolerance-note').textContent = PRESETS[state.preset].def;
  document.getElementById('csv-btn').addEventListener('click', downloadCsv);
  document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click', ()=>showTab(b.getAttribute('data-tab'))));
  document.getElementById('detail').addEventListener('click', e=>{ if(e.target.id==='detail') closeDetail(); });
  document.getElementById('detail').addEventListener('keydown', e=>{
    if(e.key!=='Tab' || !document.getElementById('detail').classList.contains('open')) return;
    const f = detailFocusable();
    if(!f.length) return;
    const first = f[0], last = f[f.length-1];
    if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); }
    else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); }
  });
  document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDetail(); });
}
init();
