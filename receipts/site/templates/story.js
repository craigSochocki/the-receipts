/* ---- the front-door story: one pinned field of every incoming member ----
   Each step is a layout of the same dots; scrolling a step's card into
   the middle of the screen moves the dots there. Status comes from
   tierOf (the preset and the cycle picker drive it, like the rest of the
   page) and every count is computed here, never typed. Without
   IntersectionObserver (or with reduced motion) every card shows and the
   field holds the clean-vs-dirty layout. */
const STORY_W = 600, STORY_H = 400, DOT_R = 6, DOT_GAP = 15;
const STATUS_ORDER = {dirty:0, below_threshold:1, clean:2, unjudged:3};
const STORY_STEPS = ['all', 'status', 'ranked', 'party', 'chamber', 'targets', 'find'];
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
function chamberGroups(people){
  return [{label:'House', people: people.filter(p=>p.chamber_120==='House')},
          {label:'Senate', people: people.filter(p=>p.chamber_120==='Senate')}];
}

function storyLayout(step, people){
  if(step==='all') return {at: centredGrid(people, 27)};
  if(step==='ranked') return {at: rankCurve(people), r: 4};
  if(step==='party'){ const groups = partyGroups(people); return {at: groupedGrids(groups, 15), groups}; }
  if(step==='chamber'){ const groups = chamberGroups(people); return {at: groupedGrids(groups, 18), groups}; }
  return {at: centredGrid(people.slice().sort(byStatus), 27)};
}

function dotClass(p, step){
  if(step==='all') return 'dot-plain';
  const lit = step==='targets' ? STORY_TARGETS.has(p.person_key)
    : step==='find' ? (storyPick===null || storyPick===p.person_key) : true;
  return 'dot-'+storyStatus(p)+' '+partyClass(p)+(lit ? '' : ' dot-faded')+(step==='find' && storyPick===p.person_key ? ' dot-picked' : '');
}

let STORY_TARGETS = new Set();
function drawStory(){
  const svg = document.getElementById('dotfield');
  if(!svg) return;
  const people = incomingMembers();
  if(!svg.childNodes.length || svg.querySelectorAll('circle').length!==people.length){
    svg.innerHTML = '<g class="dots">'+people.map(p=>'<circle r="'+DOT_R+'" data-key="'+esc(p.person_key)+'"><title>'+esc(p.full_name)+'</title></circle>').join('')+'</g><g class="labels"></g>';
  }
  const layout = storyLayout(storyStep, people);
  svg.querySelectorAll('circle').forEach(c=>{
    const p = BY_KEY[c.getAttribute('data-key')], pos = layout.at[p.person_key];
    c.style.transform = 'translate('+pos.x+'px,'+pos.y+'px)';
    c.setAttribute('r', layout.r || DOT_R);
    c.setAttribute('class', dotClass(p, storyStep));
  });
  svg.querySelector('.labels').innerHTML = (layout.groups||[]).map(g=>
    '<text x="'+g.x+'" y="40" text-anchor="middle">'+esc(g.label)+'</text>').join('')
    + (storyStep==='ranked' ? rankLabel(people) : '');
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
    chamber: 'By chamber, dirty: '+groupLine(chamberGroups(people))+'.',
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
}
function pickInStory(personKey){ storyPick = personKey || null; if(storyStep==='find') drawStory(); }

function initStory(){
  if(!document.getElementById('dotfield')) return;
  document.getElementById('scrolly-steps').addEventListener('click', e=>{
    const go = e.target.getAttribute && e.target.getAttribute('data-story-go');
    if(go==='targets') showTab('targets');
    if(go==='finder'){ const f = document.getElementById('find-state'); if(f){ f.scrollIntoView({block:'center'}); f.focus(); } }
  });
  renderStory();
  const steps = document.querySelectorAll('.scrolly-step');
  if(reducedMotion() || typeof IntersectionObserver==='undefined'){
    document.getElementById('story').classList.add('static');
    setStoryStep('status');
    return;
  }
  const io = new IntersectionObserver(entries=>{
    entries.forEach(e=>{ if(e.isIntersecting) setStoryStep(e.target.getAttribute('data-step')); });
  }, {rootMargin:'-45% 0px -45% 0px'});
  steps.forEach(s=>io.observe(s));
}
