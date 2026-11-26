/* ---- the front-door story: one pinned graphic of every incoming member ----
   Each step is a view of the same people; scrolling a step's card into
   the middle of the screen moves the graphic there. Status comes from
   tierOf (the preset and the cycle picker drive it, like the rest of the
   page) and every count is computed here, never typed. Standard steps
   render with Observable Plot into #story-plot; the three bespoke steps
   (House hemicycle, district map, Senate tiles) keep the hand-rolled SVG
   in #dotfield. Without Plot, or without a step library (or with reduced
   motion), the story falls back to the dot field and the static layout. */
const STORY_W = 600, STORY_H = 400, DOT_R = 6, DOT_GAP = 15;
const STATUS_ORDER = {dirty:0, below_threshold:1, clean:2, unjudged:3};
const STORY_STEPS = ['all', 'status', 'ranked', 'party', 'house', 'districts', 'senate', 'targets', 'find'];
/* Steps drawn by Observable Plot; the rest keep the bespoke dot field. */
const PLOT_STEPS = ['all', 'status', 'ranked', 'party', 'targets', 'find'];
const STATUS_KEYS = ['dirty', 'below_threshold', 'clean', 'unjudged'];
const STATUS_LABELS = {dirty:'Dirty', below_threshold:'Below threshold', clean:'Clean', unjudged:'Not judged'};
/* Same greys as the site's key: dirty solid, below-threshold mid grey,
   clean white, unjudged pale grey — labels always accompany the colour. */
const STATUS_FILL = {dirty:'#4b5563', below_threshold:'#9ca3af', clean:'#ffffff', unjudged:'#e5e7eb'};
const US_STATES = JSON.parse(document.getElementById('us-states').textContent);
const US_DISTRICTS = JSON.parse(document.getElementById('us-districts').textContent);
// The outlines' Albers frame (975 x 610), fitted into the story's field.
const MAP_SCALE = Math.min(STORY_W/975, STORY_H/610), MAP_X = (STORY_W-975*MAP_SCALE)/2, MAP_Y = (STORY_H-610*MAP_SCALE)/2;
let storyStep = 'all', storyPick = null;

function storyStatus(p){ return tierOf(p) || 'unjudged'; }
function partyClass(p){ return {Democrat:'party-d', Republican:'party-r'}[party(p)] || 'party-o'; }
function incomingMembers(){ return PEOPLE.filter(p=>p.in_120th==='yes'); }
function byStatus(a, b){
  return STATUS_ORDER[storyStatus(a)]-STATUS_ORDER[storyStatus(b)] || num(b.cy_dirty)-num(a.cy_dirty);
}

/* Lay people out row by row in a block of `cols` columns starting at (x0, y0). */
function gridAt(people, cols, x0, y0, at){
  people.forEach((p, i)=>{ at[p.person_key] = {x: x0+(i%cols)*DOT_GAP, y: y0+Math.floor(i/cols)*DOT_GAP}; });
  return at;
}
function centredGrid(people, cols){
  const width = (cols-1)*DOT_GAP, rows = Math.ceil(people.length/cols);
  return gridAt(people, cols, (STORY_W-width)/2, (STORY_H-(rows-1)*DOT_GAP)/2, {});
}
/* Side-by-side blocks, one per group, each sorted by status. */
function groupedGrids(groups, cols){
  const at = {}, widths = groups.map(g=>Math.min(cols, g.people.length)*DOT_GAP);
  let x = (STORY_W - widths.reduce((s, w)=>s+w, 0) - DOT_GAP*2*(groups.length-1))/2;
  groups.forEach((g, i)=>{
    gridAt(g.people.slice().sort(byStatus), cols, x+DOT_GAP/2, 60, at);
    g.x = x + widths[i]/2;
    x += widths[i] + DOT_GAP*2;
  });
  return at;
}
/* Every member at (rank, height by dirty money): the curve of who took the most. */
function rankCurve(people){
  const ranked = people.slice().sort((a, b)=>num(b.cy_dirty)-num(a.cy_dirty));
  const top = Math.log10(1+Math.max(1, num(ranked[0].cy_dirty)));
  const at = {};
  ranked.forEach((p, i)=>{
    const h = Math.log10(1+Math.max(0, num(p.cy_dirty)))/top;
    at[p.person_key] = {x: 30+(STORY_W-60)*i/(ranked.length-1), y: STORY_H-30-(STORY_H-80)*h};
  });
  return at;
}

function partyGroups(people){
  const name = p=>({Democrat:'Democrats', Republican:'Republicans'})[party(p)] || 'Others';
  return ['Democrats', 'Republicans', 'Others']
    .map(label=>({label, people: people.filter(p=>name(p)===label)}))
    .filter(g=>g.people.length);
}
const PARTY_SIDE = {Democrat:0, Republican:2};
function partySide(p){ return PARTY_SIDE[party(p)] ?? 1; }
/* A parliament arc: seats on concentric rows, filled left to right with
   Democrats, others, then Republicans, each party's dirty seats first. */
function hemicycle(people, cx, cy, inner, outer, rows){
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
  const order = people.slice().sort((a, b)=>partySide(a)-partySide(b) || byStatus(a, b));
  const at = {};
  order.forEach((p, i)=>{ at[p.person_key] = seats[i]; });
  return at;
}
function houseMembers(people){ return people.filter(p=>p.chamber_120==='House'); }
function senators(people){ return people.filter(p=>p.chamber_120==='Senate'); }
/* Each senator's dot on their state, the pair side by side. */
function senateMap(people){
  const at = {}, byState = {};
  senators(people).forEach(p=>{ (byState[p.state] = byState[p.state] || []).push(p); });
  Object.entries(byState).forEach(([st, pair])=>{
    const c = US_STATES[st];
    pair.sort((a, b)=>partySide(a)-partySide(b)).forEach((p, i)=>{
      at[p.person_key] = {x: MAP_X+c.cx*MAP_SCALE+(i-(pair.length-1)/2)*11, y: MAP_Y+c.cy*MAP_SCALE};
    });
  });
  people.filter(p=>!at[p.person_key]).forEach(p=>{ at[p.person_key] = {x: STORY_W/2, y: STORY_H/2, hidden: true}; });
  return at;
}
/* A state's shade: its senators' parties (both D, both R, split, other). */
function stateShade(st, people){
  const sides = senators(people).filter(p=>p.state===st).map(partySide);
  if(!sides.length) return 'state-none';
  if(sides.every(s=>s===0)) return 'state-d';
  if(sides.every(s=>s===2)) return 'state-r';
  return sides.includes(0) && sides.includes(2) ? 'state-split' : 'state-other';
}
function mapLayer(people){
  return '<g class="states" transform="translate('+MAP_X+','+MAP_Y+') scale('+MAP_SCALE+')">'
    + Object.entries(US_STATES).map(([st, s])=>'<path class="'+stateShade(st, people)+'" d="'+s.d+'"><title>'+esc(STATE_NAMES[st]||st)+'</title></path>').join('')
    + '</g>';
}
/* The Census district key for a House member: at-large seats are 00, DC's is 98. */
function districtKey(p){
  const n = Number(p.district_120);
  return p.state+'-'+(p.state==='DC' ? '98' : String(n).padStart(2, '0'));
}
/* Every district shaded by its member: party colour, status by strength. */
function districtLayer(people){
  const member = {};
  houseMembers(people).forEach(p=>{ member[districtKey(p)] = p; });
  return '<g class="districts" transform="translate('+MAP_X+','+MAP_Y+') scale('+MAP_SCALE+')">'
    + Object.entries(US_DISTRICTS).map(([key, d])=>{
        const p = member[key];
        const cls = p ? 'district dot-'+storyStatus(p)+' '+partyClass(p) : 'district district-open';
        return '<path class="'+cls+'"'+(p ? ' data-key="'+esc(p.person_key)+'"' : '')+' d="'+d.d+'"><title>'+esc(key)+(p ? ' · '+esc(p.full_name) : ' · no member named')+'</title></path>';
      }).join('')
    + '</g><g class="district-states" transform="translate('+MAP_X+','+MAP_Y+') scale('+MAP_SCALE+')">'
    + Object.values(US_STATES).map(s=>'<path d="'+s.d+'"/>').join('')
    + '</g>';
}
function mapsOnly(people){
  const at = {};
  people.forEach(p=>{ at[p.person_key] = {x: STORY_W/2, y: STORY_H/2, hidden: true}; });
  return at;
}
function houseArc(people){
  const house = houseMembers(people), at = hemicycle(house, STORY_W/2, STORY_H-30, 110, 290, 12);
  people.filter(p=>!at[p.person_key]).forEach(p=>{ at[p.person_key] = {x: STORY_W/2, y: STORY_H-30, hidden: true}; });
  return at;
}

function storyLayout(step, people){
  if(step==='all') return {at: centredGrid(people, 27)};
  if(step==='ranked') return {at: rankCurve(people), r: 4};
  if(step==='party'){ const groups = partyGroups(people); return {at: groupedGrids(groups, 15), groups}; }
  if(step==='house') return {at: houseArc(people), r: 5.5, center: houseMembers(people).length};
  if(step==='senate') return {at: senateMap(people), r: 5};
  if(step==='districts') return {at: mapsOnly(people)};
  return {at: centredGrid(people.slice().sort(byStatus), 27)};
}

function dotClass(p, step){
  if(step==='all') return 'dot-plain';
  const lit = step==='targets' ? STORY_TARGETS.has(p.person_key)
    : step==='find' ? (storyPick===null || storyPick===p.person_key) : true;
  return 'dot-'+storyStatus(p)+' '+partyClass(p)+(lit ? '' : ' dot-faded')+(step==='find' && storyPick===p.person_key ? ' dot-picked' : '');
}

let STORY_TARGETS = new Set();
/* Observable Plot is vendored and inlined before this script; the Node
   vm tests load this file with no Plot global, so guard every use. */
function hasPlot(){ return typeof Plot !== 'undefined' && Plot && typeof Plot.plot === 'function'; }
/* The waffle's rows, sorted by status so the blocks read dirty first. */
function waffleRows(people){
  return people.slice().sort(byStatus).map(p=>({key: p.person_key, status: storyStatus(p), n: 1}));
}
function storyPlotLabel(step){
  return storyTexts()[step].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}
function wafflePlot(rows, fill){
  const cols = 27, lines = Math.ceil(rows.length/cols), cell = (STORY_W-16)/cols;
  return Plot.plot({
    width: STORY_W, height: Math.round(lines*cell+16),
    axis: null, label: null, marginTop: 8, marginBottom: 8, marginLeft: 8, marginRight: 8,
    color: {domain: STATUS_KEYS, range: STATUS_KEYS.map(k=>STATUS_FILL[k])},
    marks: [Plot.waffleX(rows, {x: 'n', unit: 1, fill: fill, multiple: cols})],
  });
}
function waffleLegend(people){
  const counts = {dirty: 0, below_threshold: 0, clean: 0, unjudged: 0};
  people.forEach(p=>{ counts[storyStatus(p)]++; });
  return STATUS_KEYS.map(s=>
    '<span><span class="k dot-'+s+'"></span>'
    +STATUS_LABELS[s]+' — <b>'+counts[s]+'</b></span>').join(' ');
}
/* Plot renders one <rect> per waffle cell, in data order (verified
   against the pinned Plot 0.6.19 in jsdom): tag each cell with its
   member so clicks open the drill-down, and outline the cells the
   step is about — targets on the targets step, the picked member on
   the find step. If Plot's output ever stops matching the rows, skip
   the tagging rather than mislabelling cells. */
function tagWaffleCells(plotEl, rows, step){
  const rects = plotEl.querySelectorAll('svg rect');
  if(rects.length!==rows.length) return;
  rects.forEach((r, i)=>{
    r.setAttribute('data-key', rows[i].key);
    if(step==='targets' && STORY_TARGETS.has(rows[i].key)){
      r.setAttribute('data-target', '1');
      r.setAttribute('stroke', '#111827'); r.setAttribute('stroke-width', '2.5');
    }
    if(step==='find' && storyPick && storyPick===rows[i].key){
      r.setAttribute('data-picked', '1');
      r.setAttribute('stroke', '#111827'); r.setAttribute('stroke-width', '3.5');
    }
  });
}
function rankedPlot(people){
  const ranked = people.slice().sort((a, b)=>(num(b.cy_dirty)||0)-(num(a.cy_dirty)||0));
  const vals = ranked.map(p=>({key: p.person_key, dirty: Math.max(0, num(p.cy_dirty)||0), status: storyStatus(p)}));
  const amounts = vals.map(v=>v.dirty).sort((a, b)=>a-b);
  const median = amounts.length ? amounts[Math.floor(amounts.length/2)] : 0;
  const top = Math.max(10, 1+(num(ranked[0].cy_dirty)||0));
  return Plot.plot({
    width: STORY_W, height: 240,
    x: {type: 'log', label: 'Dirty money, $ (log scale)', domain: [1, top]},
    y: {axis: null},
    color: {domain: STATUS_KEYS, range: STATUS_KEYS.map(k=>STATUS_FILL[k])},
    marks: [
      /* One dot per member; $0 plots at $1, as log(1+x). The jitter is
         a fixed function of the rank, so the strip is stable. */
      Plot.dot(vals, {x: d=>1+d.dirty, y: (d, i)=>((i*2654435761)%100)/100, r: 3.5, fill: 'status', fillOpacity: 0.85}),
      Plot.ruleX([1+median], {stroke: '#b91c1c', strokeWidth: 2}),
      Plot.text(['median '+fmtCompact(median)], {x: 1+median, y: 0.92, dy: -8, fill: '#b91c1c', fontWeight: 'bold', fontSize: 12}),
      Plot.text(['log scale — each step is 10×'], {frameAnchor: 'top-left', dx: 6, dy: 14, fontWeight: 'bold', fontSize: 13}),
    ],
  });
}
function partyPlot(people){
  const groups = partyGroups(people);
  const rows = [];
  STATUS_KEYS.forEach(st=>groups.forEach(g=>{
    rows.push({party: g.label, status: st, n: g.people.filter(p=>storyStatus(p)===st).length});
  }));
  return Plot.plot({
    width: STORY_W, height: 260,
    x: {label: 'Members'},
    y: {label: null, domain: groups.map(g=>g.label)},
    color: {domain: STATUS_KEYS, range: STATUS_KEYS.map(k=>STATUS_FILL[k])},
    marks: [
      Plot.barX(rows, {x: 'n', y: 'party', fill: 'status'}),
      Plot.text(rows, Plot.stackX({
        x: 'n', y: 'party', text: d=>d.n>0 ? String(d.n) : '',
        fill: d=>d.status==='dirty' ? '#fff' : '#111827', fontWeight: 'bold',
      })),
    ],
  });
}
/* Render a Plot step into #story-plot. The targets and find steps reuse
   the status waffle: same sorted layout, with their cells outlined. */
function drawPlotChart(plotEl, step, people){
  plotEl.innerHTML = '';
  let plot;
  if(step==='all') plot = wafflePlot(waffleRows(people), '#9ca3af');
  else if(step==='ranked') plot = rankedPlot(people);
  else if(step==='party') plot = partyPlot(people);
  else plot = wafflePlot(waffleRows(people), 'status');
  plotEl.appendChild(plot);
  if(step==='all' || step==='status' || step==='targets' || step==='find'){
    const legend = document.createElement('div');
    legend.className = 'plot-legend';
    legend.innerHTML = step==='all'
      ? '<p>Each cell is one member.</p>'
      : '<p>'+waffleLegend(people)+'</p>';
    plotEl.appendChild(legend);
    tagWaffleCells(plotEl, waffleRows(people), step);
  }
}
function drawStory(){
  const people = incomingMembers();
  const plotEl = document.getElementById('story-plot');
  const svg = document.getElementById('dotfield');
  if(plotEl){
    plotEl.setAttribute('aria-label', storyPlotLabel(storyStep));
    plotEl.setAttribute('aria-describedby', 'step-'+storyStep);
  }
  if(PLOT_STEPS.indexOf(storyStep)!==-1 && hasPlot() && plotEl){
    drawPlotChart(plotEl, storyStep, people);
    plotEl.style.display = '';
    if(svg) svg.style.display = 'none';
    return;
  }
  /* Bespoke step, or Plot unavailable: the dot field, as before. */
  if(plotEl) plotEl.style.display = 'none';
  if(svg) svg.style.display = '';
  if(!svg) return;
  if(!svg.childNodes.length || svg.querySelectorAll('circle').length!==people.length){
    svg.innerHTML = districtLayer(people)+mapLayer(people)+'<g class="dots">'+people.map(p=>'<circle r="'+DOT_R+'" data-key="'+esc(p.person_key)+'"><title>'+esc(p.full_name)+'</title></circle>').join('')+'</g><g class="labels"></g>';
  }
  const layout = storyLayout(storyStep, people);
  svg.querySelector('.states').classList.toggle('shown', storyStep==='senate');
  svg.classList.toggle('hemi', storyStep==='house');
  svg.querySelectorAll('.districts, .district-states').forEach(g=>g.classList.toggle('shown', storyStep==='districts'));
  svg.querySelectorAll('circle').forEach(c=>{
    const p = BY_KEY[c.getAttribute('data-key')], pos = layout.at[p.person_key];
    c.style.transform = 'translate('+pos.x+'px,'+pos.y+'px)';
    c.setAttribute('r', layout.r || DOT_R);
    c.setAttribute('class', dotClass(p, storyStep)+(pos.hidden ? ' dot-hidden' : ''));
  });
  svg.querySelector('.labels').innerHTML = (layout.groups||[]).map(g=>
    '<text x="'+g.x+'" y="40" text-anchor="middle">'+esc(g.label)+'</text>').join('')
    + (storyStep==='ranked' ? rankLabel(people) : '')
    + (layout.center ? '<text class="arc-count" x="'+STORY_W/2+'" y="'+(STORY_H-34)+'" text-anchor="middle">'+layout.center+'</text>' : '');
}
function rankLabel(people){
  const top = people.slice().sort((a, b)=>num(b.cy_dirty)-num(a.cy_dirty))[0];
  return '<text x="38" y="44">'+esc(top.full_name)+' · '+esc(fmtCompact(top.cy_dirty))+'</text>';
}

function countWhere(people, test){ return people.filter(test).length; }
function storyTexts(){
  const people = incomingMembers(), preset = PRESETS[state.preset];
  const dirty = p=>storyStatus(p)==='dirty', notDirty = p=>isNotDirty(p);
  const word = state.preset==='strict' ? 'took no dirty money' : 'were not dirty';
  const top = people.slice().sort((a, b)=>num(b.cy_dirty)-num(a.cy_dirty))[0];
  const groupLine = groups=>groups.map(g=>'<b>'+countWhere(g.people, dirty)+' of '+g.people.length+'</b> '+esc(g.label)).join(' · ');
  const targets = primaryTargets();
  return {
    all: 'These are the <b>'+people.length+'</b> members of the incoming 120th Congress. Each dot is one person.',
    status: '<b>'+countWhere(people, dirty)+'</b> of them took dirty money '+esc(IN_CY)+' — corporate PAC, AIPAC PAC direct or UDP benefit. <b>'+countWhere(people, notDirty)+'</b> '+word+'. The rest were not judged (unopposed or unlinked). '+esc(preset.label)+' tolerance: '+esc(preset.short)+'.',
    ranked: 'Lined up by how much: <b>'+esc(top.full_name)+'</b> took <b>'+esc(fmtCompact(top.cy_dirty))+'</b> '+esc(IN_CY)+', the most of anyone arriving in the 120th.',
    party: 'By party, dirty: '+groupLine(partyGroups(people))+'.',
    house: 'The House, seat by seat: '+groupLine(partyGroups(houseMembers(people)))+' took dirty money.',
    districts: 'District by district: each House seat shaded by its member — party colour, strong when dirty, light when below threshold, white when clean. The five territorial delegates are not on the map.',
    senate: 'The Senate, state by state: '+groupLine(partyGroups(senators(people)))+' took dirty money. Each state is shaded by its senators’ parties; each dot is one senator.',
    targets: '<b>'+targets.length+'</b> hold seats on the ballot in '+NEXT_CYCLE+' and took dirty money — the primary targets. <button type="button" class="linklike" data-story-go="targets">See the list</button>',
    find: 'Which one is yours? <button type="button" class="linklike" data-story-go="finder">Find your member</button> and their dot lights up.',
  };
}
function renderStory(){
  STORY_TARGETS = new Set(primaryTargets().map(p=>p.person_key));
  const texts = storyTexts();
  STORY_STEPS.forEach(s=>{ const el = document.getElementById('step-'+s); if(el) el.innerHTML = texts[s]; });
  drawStory();
}
function setStoryStep(step){
  if(step===storyStep) return;
  storyStep = step;
  document.querySelectorAll('.scrolly-step').forEach(el=>el.classList.toggle('active', el.getAttribute('data-step')===step));
  drawStory();
  syncStepper();
}
function pickInStory(personKey){ storyPick = personKey || null; if(storyStep==='find') drawStory(); }

/* ---- the stepper: the reduced-motion / static fallback control ----
   Shown only in static mode; prev/next move to the neighbouring step
   card and set the step. Wiring is defensive: the template may not
   have the stepper yet, and the vm stubs return placeholder elements. */
let stepperEl = null, stepperPrev = null, stepperNext = null, stepperLabel = null;
function initStepper(){
  stepperEl = document.querySelector('.story-stepper');
  if(!stepperEl) return;
  stepperPrev = stepperEl.querySelector('[data-stepper="prev"]');
  stepperNext = stepperEl.querySelector('[data-stepper="next"]');
  stepperLabel = stepperEl.querySelector('.stepper-label');
  if(stepperPrev) stepperPrev.addEventListener('click', ()=>stepStory(-1));
  if(stepperNext) stepperNext.addEventListener('click', ()=>stepStory(1));
  syncStepper();
}
function showStepper(){ if(stepperEl) stepperEl.hidden = false; }
function syncStepper(){
  if(!stepperEl) return;
  const i = STORY_STEPS.indexOf(storyStep);
  if(stepperLabel) stepperLabel.textContent = 'Step '+(i+1)+' of '+STORY_STEPS.length;
  if(stepperPrev) stepperPrev.disabled = i<=0;
  if(stepperNext) stepperNext.disabled = i>=STORY_STEPS.length-1;
}
function stepStory(delta){
  const i = STORY_STEPS.indexOf(storyStep);
  const j = Math.min(STORY_STEPS.length-1, Math.max(0, i+delta));
  if(j===i) return;
  const el = document.getElementById('step-'+STORY_STEPS[j]);
  if(el && typeof el.scrollIntoView==='function') el.scrollIntoView({block: 'center'});
  setStoryStep(STORY_STEPS[j]);
}
function showStaticStory(){
  document.getElementById('story').classList.add('static');
  showStepper();
  setStoryStep('status');
}

function initStory(){
  if(!document.getElementById('dotfield')) return;
  document.getElementById('scrolly-steps').addEventListener('click', e=>{
    const go = e.target.getAttribute && e.target.getAttribute('data-story-go');
    if(go==='targets') showTab('targets');
    if(go==='finder'){ const f = document.getElementById('find-state'); if(f){ f.scrollIntoView({block:'center'}); f.focus(); } }
  });
  /* A Plot waffle cell opens its member's drill-down, like a dot. */
  const plotEl = document.getElementById('story-plot');
  if(plotEl) plotEl.addEventListener('click', e=>{
    const t = e.target && e.target.closest ? e.target.closest('[data-key]') : null;
    if(t) openDetail(t.getAttribute('data-key'));
  });
  renderStory();
  initStepper();
  if(reducedMotion()){
    showStaticStory();
    return;
  }
  /* Scrollama is the step logic; plain IntersectionObserver is only the
     fallback when its script failed to load. Never both at once. */
  if(typeof scrollama !== 'undefined' && typeof IntersectionObserver !== 'undefined'){
    const scroller = scrollama();
    scroller.setup({step: '.scrolly-step', offset: 0.5});
    scroller.onStepEnter(resp=>{
      if(resp && resp.element) setStoryStep(resp.element.getAttribute('data-step'));
    });
    if(typeof window !== 'undefined' && typeof window.addEventListener === 'function'){
      window.addEventListener('resize', ()=>{ try{ scroller.resize(); }catch(e){} });
    }
    return;
  }
  const steps = document.querySelectorAll('.scrolly-step');
  if(typeof IntersectionObserver !== 'undefined'){
    const io = new IntersectionObserver(entries=>{
      entries.forEach(e=>{ if(e.isIntersecting) setStoryStep(e.target.getAttribute('data-step')); });
    }, {rootMargin:'-45% 0px -45% 0px'});
    steps.forEach(s=>io.observe(s));
    return;
  }
  showStaticStory();
}
