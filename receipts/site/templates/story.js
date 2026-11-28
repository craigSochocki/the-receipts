/* ---- the Story front door: six beats, one idea per screen ----

   The static HTML is the final frame: the waffle shows the party
   split with the flag overlay on, the stacked bars show all three
   sources, the map is fully coloured. The script only rewinds
   pictures to earlier steps as the reader scrolls, and refills the
   step texts from the embedded aggregates — the same aggregates the
   static render used (receipts/site/story_data.py). With no
   JavaScript, with reduced motion, or on a narrow screen, the reader
   sees the final frame for every beat.

   Step order is the story order: the party split comes first, the
   flagged overlay goes on after it, and no dot ever moves — steps
   only recolour. Transitions are transform/opacity only, except the
   waffle dots themselves, which change background-color (a paint-only
   change, no layout); the wireframe demo does the same.

   Steps are idempotent: arriving at a step from above or below gives
   the same picture. Step heights are set in px from innerHeight, not
   vh, and the step is re-derived after a scroll jump settles, so
   jumping back to the top lands on the same step again. */

const STORY_STEPS = ['waffle_all', 'waffle_party', 'waffle_flag', 'ranked', 'stacked_aipac', 'stacked_corp', 'stacked_individual', 'rest', 'member', 'member_trend', 'member_zoom', 'map', 'targets'];

/* ---- the old story's pure helpers, kept verbatim ----

   mirrors.test.mjs tests partyLabelPlan / partyGroups / stepAtScroll
   / storyStatus against fixture people, so their behaviour must not
   change. They read tracker.js globals (party, tierOf, num) in the
   test harness; nothing on the Story page calls them. */

const STORY_W = 600, STORY_H = 400, DOT_R = 6, DOT_GAP = 15;
const STATUS_ORDER = {dirty:0, below_threshold:1, clean:2, unjudged:3};
const STATUS_KEYS = ['dirty', 'below_threshold', 'clean', 'unjudged'];
const STATUS_LABELS = {dirty:'Dirty', below_threshold:'Below threshold', clean:'Clean', unjudged:'Not judged'};

function storyStatus(p){ return tierOf(p) || 'unjudged'; }
function byStatus(a, b){
  return STATUS_ORDER[storyStatus(a)]-STATUS_ORDER[storyStatus(b)] || num(b.cy_dirty)-num(a.cy_dirty);
}
function partyGroups(people){
  const name = p=>({Democrat:'Democrats', Republican:'Republicans'})[party(p)] || 'Others';
  return ['Democrats', 'Republicans', 'Others']
    .map(label=>({label, people: people.filter(p=>name(p)===label)}))
    .filter(g=>g.people.length);
}
const PARTY_MARGIN_LEFT = 80, PARTY_MARGIN_RIGHT = 20;
function partyLabelPlan(groups){
  const innerWidth = STORY_W - PARTY_MARGIN_LEFT - PARTY_MARGIN_RIGHT;
  const maxTotal = Math.max(1, ...groups.map(g=>g.people.length));
  const domainMax = maxTotal + 60;
  const pxPerMember = innerWidth / domainMax;
  const inside = [], outside = [];
  groups.forEach(g=>{
    const total = g.people.length, notes = [];
    STATUS_KEYS.forEach(st=>{
      const n = g.people.filter(p=>storyStatus(p)===st).length;
      if(n <= 0) return;
      if(n * pxPerMember >= String(n).length * 6 + 4) inside.push({party: g.label, status: st, n});
      else notes.push(n + ' ' + STATUS_LABELS[st].toLowerCase());
    });
    if(!notes.length) return;
    const text = notes.join(', ');
    let startPx = PARTY_MARGIN_LEFT + total * pxPerMember + 6;
    if(startPx + text.length * 5.5 > STORY_W - 4) startPx = STORY_W - 4 - text.length * 5.5;
    outside.push({party: g.label, text, x: (startPx - PARTY_MARGIN_LEFT) / pxPerMember});
  });
  return {inside, outside, domainMax};
}

/* The step whose card holds the viewport middle, from the step tops:
   the last step at or above the middle, else the first step. */
function stepAtScroll(tops, mid){
  let current = STORY_STEPS[0];
  tops.forEach(t=>{ if(t.top <= mid) current = t.step; });
  return current;
}
function storyStepFromScroll(){
  if(typeof window === 'undefined' || !window.innerHeight) return storyStep;
  const mid = window.innerHeight * 0.5;
  const tops = [];
  document.querySelectorAll('.scrolly-step').forEach(el=>{
    const step = el.getAttribute('data-step');
    const r = step && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    if(r) tops.push({step, top: r.top});
  });
  return stepAtScroll(tops, mid);
}
/* Scrollama (and the IO fallback below) fire per step crossing; an
   instant jump — Home, End, a scrollbar drag — can cross several steps
   at once and leave the chart on a stale step. After scrolling settles,
   re-derive the active step from the scroll position. */
let storyScrollTimer = null;
function initStoryScrollCheck(){
  if(typeof window === 'undefined' || typeof window.addEventListener !== 'function') return;
  window.addEventListener('scroll', ()=>{
    if(storyScrollTimer) clearTimeout(storyScrollTimer);
    storyScrollTimer = setTimeout(()=>{ setStoryStep(storyStepFromScroll()); }, 120);
  }, {passive: true});
}

/* ---- story data and text ----

   The page embeds the aggregates from receipts/site/story_data.py as
   #story-data JSON. The static HTML already carries the same text;
   renderStory() refills the step cards from the payload so a stale
   build cannot show stale figures. storyStepText mirrors Python
   story_texts in receipts/site/static_render.py. */

let STORY_DATA = null;
let storyStep = 'waffle_all';

function loadStoryData(){
  try{
    const el = document.getElementById('story-data');
    const text = el && el.textContent;
    if(!text) return null;
    const data = JSON.parse(text);
    return data && data.meta ? data : null;
  }catch(e){ return null; }
}

function esc(s){
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* Mirror of Python round_money in static_render.py. */
function roundMoney(v){
  if(v === null || v === undefined) return '—';
  if(typeof v !== 'number' || !isFinite(v)) return String(v);
  const neg = v < 0, size = Math.abs(v);
  let text;
  if(size >= 1e9) text = '$' + (size / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
  else if(size >= 1e6) text = '$' + (size / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
  else if(size >= 1e3) text = '$' + Math.round(size / 1e3) + 'K';
  else text = '$' + Math.round(size).toLocaleString('en-US');
  return (neg ? '−' : '') + text;
}

function partyCountsText(counts){
  const parts = [];
  if(counts.dem) parts.push(counts.dem + ' Democrats');
  if(counts.rep) parts.push(counts.rep + ' Republicans');
  if(counts.ind) parts.push(counts.ind + ' independents');
  if(counts.other) parts.push(counts.other + ' others');
  return parts.join(', ');
}

/* The step text for one step, from the aggregates. Returns null when
   the payload cannot supply the text (the static card stays). */
function storyStepText(stepId, data){
  if(!data) return null;
  const meta = data.meta, house = data.waffle.house, senate = data.waffle.senate;
  const member = data.member, zoom = member.zoom, stacked = data.stacked;
  const short = data.preset && data.preset.balanced_short ? data.preset.balanced_short : null;
  if(stepId === 'waffle_all'){
    return 'These are the <b>' + meta.incoming_total + '</b> seats of the incoming '
      + '120th Congress — <b>' + house.seats + '</b> in the House, <b>' + senate.seats
      + '</b> in the Senate. Each dot is one seat.';
  }
  if(stepId === 'waffle_party'){
    return 'First, the party split — Democrats in one block, Republicans in one block, '
      + 'in each chamber. House: <b>' + partyCountsText(house.counts) + '</b>. '
      + 'Senate: <b>' + partyCountsText(senate.counts) + '</b>.';
  }
  if(stepId === 'waffle_flag'){
    if(!short) return null;
    return 'Now who the rules flag — any AIPAC direct dollar or UDP benefit dollar '
      + 'since their last election. House: <b>' + house.counts.flagged + ' of '
      + house.seats + '</b> seats. Senate: <b>' + senate.counts.flagged + ' of '
      + senate.seats + '</b>. Flagged members sit at the head of their party\'s '
      + 'block, in the lighter tint of their own party\'s colour. Under the Balanced '
      + 'tolerance (' + esc(short) + '), '
      + '<b>' + data.counts.balanced_dirty + '</b> of the incoming '
      + meta.incoming_total + ' count as dirty. '
      + 'These flagged counts are seats, not members: a seat whose race is '
      + 'still uncalled counts here, with the person named for it, so the '
      + 'totals can differ from the member counts in Explore. '
      + '<a href="methodology/">How we flagged members</a>.';
  }
  if(stepId === 'ranked'){
    return 'Who takes the most — in each chamber. House: '
      + '<b>' + esc(data.ranked.house[0].name) + '</b>, '
      + '<b>' + data.ranked.house[0].rounded + '</b>. Senate: '
      + '<b>' + esc(data.ranked.senate[0].name) + '</b>, '
      + '<b>' + data.ranked.senate[0].rounded + '</b>. '
      + 'Dirty money since their last election, ranked within each chamber.';
  }
  if(stepId === 'stacked_aipac'){
    return 'Where the money comes from. Start with the AIPAC PAC: '
      + '<b>' + roundMoney(stacked.house.aipac) + '</b> to House campaigns since '
      + 'their last election, <b>' + roundMoney(stacked.senate.aipac) + '</b> to '
      + 'Senate campaigns — direct contributions, earmarked checks included.';
  }
  if(stepId === 'stacked_corp'){
    return 'Add corporate PACs: '
      + '<b>' + roundMoney(stacked.house.corp) + '</b> in the House, '
      + '<b>' + roundMoney(stacked.senate.corp) + '</b> in the Senate. Together '
      + 'with AIPAC, that is '
      + '<b>' + roundMoney(stacked.house.aipac + stacked.house.corp) + '</b> '
      + 'House and <b>' + roundMoney(stacked.senate.aipac + stacked.senate.corp) + '</b> '
      + 'Senate from PACs.';
  }
  if(stepId === 'stacked_individual'){
    return 'And individuals — the rest, and most of it: '
      + '<b>' + roundMoney(stacked.house.individual) + '</b> House, '
      + '<b>' + roundMoney(stacked.senate.individual) + '</b> Senate. Individual '
      + 'contributions are not dirty money. Total accepted since their last '
      + 'election: <b>' + roundMoney(stacked.house.total) + '</b> House, '
      + '<b>' + roundMoney(stacked.senate.total) + '</b> Senate.';
  }
  if(stepId === 'rest'){
    return 'The money is real. The question is what it buys.';
  }
  if(stepId === 'member'){
    const lastCycle = member.trend[member.trend.length - 1].cycle;
    return '<b>' + esc(member.name) + '</b> took '
      + '<b>' + member.split.rounded.dirty + '</b> in dirty money in '
      + lastCycle + ' — the most of anyone in the dataset — '
      + 'almost all of it UDP benefit: '
      + '<b>' + member.split.rounded.udp_benefit + '</b> spent on the '
      + lastCycle + ' Senate race, against '
      + '<b>' + member.split.rounded.individual + '</b> raised '
      + 'from individuals.'
      + (member.returning ? '' : ' She is not returning to Congress.');
  }
  if(stepId === 'member_trend'){
    return 'It was not always like this. Dirty money by election: '
      + member.trend.map(t=>'<b>' + t.rounded + '</b> in ' + t.cycle).join(', ')
      + ', the ' + member.race_chamber + ' race.';
  }
  if(stepId === 'member_zoom'){
    const ratio = Math.trunc(zoom.member_dirty / zoom.top[0].dirty);
    const lastName = member.name.split(' ').pop();
    return 'Zoom back out to the ' + member.race_chamber + '. The incoming member who took '
      + 'the most dirty money, <b>' + esc(zoom.top[0].name) + '</b>, took '
      + '<b>' + zoom.top[0].rounded + '</b> — ' + esc(lastName) + ' took more than '
      + '<b>' + ratio + ' times</b> that. The ' + member.race_chamber + ' median is '
      + '<b>' + roundMoney(zoom.median) + '</b>.';
  }
  if(stepId === 'map'){
    const tiers = {dirty: 0, below_threshold: 0, clean: 0, unjudged: 0};
    data.map.districts.forEach(d=>{
      const key = d.tier === null ? 'unjudged' : d.tier;
      if(tiers[key] !== undefined) tiers[key] += 1;
    });
    return 'Geography. Each district is coloured by its member’s verdict — '
      + '<b>' + tiers.dirty + '</b> dirty, <b>' + tiers.below_threshold + '</b> below '
      + 'threshold, <b>' + tiers.clean + '</b> clean, '
      + '<b>' + tiers.unjudged + '</b> not judged under the Balanced rule — never '
      + 'by raw dollars. Find your district below, and see your member’s money.';
  }
  if(stepId === 'targets'){
    const top = data.targets[0];
    return 'What\'s next: <b>' + data.targets_total + '</b> incoming members whose seat is on the '
      + 'ballot in ' + meta.next_cycle + ' and who took dirty money. The top '
      + 'eight are listed — <b>' + esc(top.name) + '</b> first, '
      + 'at <b>' + top.rounded + '</b>.';
  }
  return null;
}

/* ---- graphic states ----

   Each step maps to the state of the graphics it drives. */

const STEP_STATES = {
  waffle_all: {waffle: 0},
  waffle_party: {waffle: 1},
  waffle_flag: {waffle: 2},
  ranked: {},
  stacked_aipac: {stacked: 1},
  stacked_corp: {stacked: 2},
  stacked_individual: {stacked: 3},
  rest: {},
  member: {member: 'member'},
  member_trend: {member: 'member_trend'},
  member_zoom: {member: 'member_zoom'},
  map: {},
  targets: {},
};

const STEP_BEATS = {
  waffle_all: [1, 'Each chamber, separately'],
  waffle_party: [1, 'Each chamber, separately'],
  waffle_flag: [1, 'Each chamber, separately'],
  ranked: [2, 'Who takes the most'],
  stacked_aipac: [3, 'Where the money comes from'],
  stacked_corp: [3, 'Where the money comes from'],
  stacked_individual: [3, 'Where the money comes from'],
  rest: [null, 'A pause'],
  member: [4, 'One member, then the whole'],
  member_trend: [4, 'One member, then the whole'],
  member_zoom: [4, 'One member, then the whole'],
  map: [5, 'Geography'],
  targets: [6, 'What’s next — 2028'],
};

const WAFFLE_TITLES = [
  ['Every dot is a seat — House above, Senate below.',
   'Two separate pictures, never one combined field: 435 House seats in the top panel, 100 Senate seats in the bottom panel. Nothing highlighted yet.'],
  ['Party, grouped — Democrats together, Republicans together.',
   'The dots re-sort, chamber by chamber: all Democrats form one block, all Republicans form another. This split is the base picture; everything after it is drawn on top.'],
  ['Now the overlay: who the rules flag, on top of the party split.',
   'Nothing moves and no new colour arrives. Unflagged members keep their usual blue or red; the flagged members — already grouped at the head of their own party’s block — switch to the lighter tint of their own party’s colour.'],
];

/* Set the picture for one step. Idempotent: the same step always
   produces the same picture, from above or below. */
function setStoryStep(step){
  if(STORY_STEPS.indexOf(step) === -1) return;
  storyStep = step;
  document.querySelectorAll('.scrolly-step').forEach(el=>{
    el.classList.toggle('active', el.getAttribute('data-step') === step);
  });
  document.querySelectorAll('.beat').forEach(el=>{
    const beat = Number(el.getAttribute('data-beat'));
    const steps = STORY_STEPS.filter(s=>STEP_BEATS[s][0] === beat);
    el.classList.toggle('active', steps.indexOf(step) !== -1);
  });
  const states = STEP_STATES[step] || {};
  const waffleGraphic = document.getElementById('waffle-graphic');
  if(waffleGraphic){
    const waffles = waffleGraphic.querySelector('.waffles');
    if(waffles && states.waffle !== undefined) waffles.setAttribute('data-state', String(states.waffle));
    if(states.waffle !== undefined){
      const title = waffleGraphic.querySelector('.waffle-title');
      const sub = waffleGraphic.querySelector('.waffle-sub');
      if(title) title.textContent = WAFFLE_TITLES[states.waffle][0];
      if(sub) sub.textContent = WAFFLE_TITLES[states.waffle][1];
    }
  }
  if(states.stacked !== undefined){
    document.querySelectorAll('.stacked').forEach(el=>{
      el.setAttribute('data-state', String(states.stacked));
    });
  }
  const memberGraphic = document.querySelector('#beat-member .beat-graphic');
  if(memberGraphic && states.member) memberGraphic.setAttribute('data-state', states.member);
  const label = document.getElementById('progress-label');
  if(label){
    const beat = STEP_BEATS[step];
    label.textContent = beat[0] ? beat[0] + ' / 6 — ' + beat[1] : beat[1];
  }
}

/* Step heights in px from innerHeight, never vh. */
function setStepHeights(){
  const root = document.documentElement;
  if(!root || !root.style || typeof root.style.setProperty !== 'function') return;
  const h = (typeof window !== 'undefined' && window.innerHeight) || 800;
  root.style.setProperty('--step-min', Math.round(h * 0.9) + 'px');
}

function storyReducedMotion(){
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
function storyNarrow(){
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(max-width: 760px)').matches;
}
/* The scrollytelling runs only with motion, room, and an observer. */
function storyScrolly(){
  return !storyReducedMotion() && !storyNarrow() && typeof IntersectionObserver !== 'undefined';
}

/* No scrollytelling: show every beat in its final state. */
function applyFinalStates(){
  document.querySelectorAll('.waffles').forEach(el=>el.setAttribute('data-state', '2'));
  document.querySelectorAll('.stacked').forEach(el=>el.setAttribute('data-state', '3'));
  document.querySelectorAll('#beat-member .beat-graphic').forEach(el=>el.setAttribute('data-state', 'member_zoom'));
  document.querySelectorAll('.scrolly-step').forEach(el=>el.classList.add('active'));
  document.querySelectorAll('.beat').forEach(el=>el.classList.add('active'));
}

/* Refill the step cards from the embedded aggregates, and set the
   waffle heading to its final (static) state. */
function renderStory(){
  STORY_STEPS.forEach(step=>{
    const card = document.getElementById('step-' + step);
    const text = storyStepText(step, STORY_DATA);
    if(card && text) card.innerHTML = text;
  });
  const waffleGraphic = document.getElementById('waffle-graphic');
  if(waffleGraphic){
    const title = waffleGraphic.querySelector('.waffle-title');
    const sub = waffleGraphic.querySelector('.waffle-sub');
    if(title) title.textContent = WAFFLE_TITLES[2][0];
    if(sub) sub.textContent = WAFFLE_TITLES[2][1];
  }
}

const TIER_LABELS = {dirty: 'Dirty', below_threshold: 'Below threshold', clean: 'Clean', unjudged: 'Not judged'};

function districtResult(district){
  const label = TIER_LABELS[district.tier === null ? 'unjudged' : district.tier] || 'Not judged';
  const flagged = district.flagged ? ' · flagged' : '';
  return '<b>' + esc(district.key) + '</b> — ' + esc(district.name) + ' · ' + label
    + flagged + '. <a href="explore/?member=' + encodeURIComponent(district.member_key)
    + '">See them in Explore →</a>';
}

function initFindDistrict(){
  if(!STORY_DATA || !STORY_DATA.map) return;
  const districts = STORY_DATA.map.districts;
  const stateSel = document.getElementById('map-state');
  const distSel = document.getElementById('map-district');
  const result = document.getElementById('map-result');
  if(!stateSel || !distSel) return;
  const states = Array.from(new Set(districts.map(d=>d.key.split('-')[0]))).sort();
  states.forEach(s=>{
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    stateSel.appendChild(opt);
  });
  const showDistrict = key=>{
    const d = districts.filter(x=>x.key === key)[0];
    if(!d) return;
    document.querySelectorAll('.district-map path[data-key]').forEach(p=>{
      p.classList.toggle('picked', p.getAttribute('data-key') === d.member_key);
    });
    if(result) result.innerHTML = districtResult(d);
  };
  const fillDistricts = state=>{
    distSel.innerHTML = '';
    districts
      .filter(d=>d.key.split('-')[0] === state)
      .sort((a, b)=>a.key < b.key ? -1 : 1)
      .forEach(d=>{
        const opt = document.createElement('option');
        opt.value = d.key;
        opt.textContent = d.key + ' — ' + d.name;
        distSel.appendChild(opt);
      });
    if(distSel.value) showDistrict(distSel.value);
  };
  stateSel.addEventListener('change', ()=>{ if(stateSel.value) fillDistricts(stateSel.value); });
  distSel.addEventListener('change', ()=>{ if(distSel.value) showDistrict(distSel.value); });
  const map = document.querySelector('.district-map');
  if(map){
    map.addEventListener('click', e=>{
      const path = e.target && e.target.closest ? e.target.closest('path[data-key]') : null;
      if(!path) return;
      const d = districts.filter(x=>x.member_key === path.getAttribute('data-key'))[0];
      if(!d) return;
      stateSel.value = d.key.split('-')[0];
      fillDistricts(stateSel.value);
      distSel.value = d.key;
      showDistrict(d.key);
    });
  }
  const form = document.getElementById('find-district');
  if(form) form.addEventListener('submit', e=>e.preventDefault());
}

/* The waffle order is fixed at build time: party blocks in the order
   Democrats, Republicans, other; flagged first inside each party
   block; dots never move. This checks that ordering. */
function isWaffleOrdered(members){
  const partyRank = {Democrats: 0, Republicans: 1};
  let lastRank = -1, lastParty = null, lastFlagged = null;
  for(const m of members){
    const rank = partyRank[m.party] === undefined ? 2 : partyRank[m.party];
    if(rank < lastRank) return false;
    if(m.party !== lastParty){ lastParty = m.party; lastFlagged = null; }
    if(lastFlagged === false && m.flagged) return false;
    lastFlagged = m.flagged;
    lastRank = rank;
  }
  return true;
}

function initStory(){
  try{
    if(document.documentElement && document.documentElement.classList){
      document.documentElement.classList.add('js');
    }
  }catch(e){}
  const data = loadStoryData();
  if(!data) return;
  STORY_DATA = data;
  setStepHeights();
  renderStory();
  initFindDistrict();
  if(!storyScrolly()){
    applyFinalStates();
    return;
  }
  document.documentElement.classList.add('scrolly');
  setStoryStep('waffle_all');
  initStoryScrollCheck();
  /* Scrollama is the step logic; plain IntersectionObserver is only the
     fallback when its script failed to load. Never both at once. */
  if(typeof scrollama !== 'undefined'){
    const scroller = scrollama();
    scroller.setup({step: '.scrolly-step', offset: 0.5});
    scroller.onStepEnter(resp=>{
      if(resp && resp.element) setStoryStep(resp.element.getAttribute('data-step'));
    });
    if(typeof window !== 'undefined' && typeof window.addEventListener === 'function'){
      window.addEventListener('resize', ()=>{
        try{ scroller.resize(); }catch(e){}
        setStepHeights();
        setStoryStep(storyStepFromScroll());
      });
    }
    return;
  }
  const io = new IntersectionObserver(entries=>{
    entries.forEach(en=>{
      if(en.isIntersecting) setStoryStep(en.target.getAttribute('data-step'));
    });
  }, {rootMargin: '-45% 0px -45% 0px'});
  document.querySelectorAll('.scrolly-step').forEach(s=>io.observe(s));
}

if(typeof document !== 'undefined' && document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', initStory);
}else{
  initStory();
}
