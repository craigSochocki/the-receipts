// Pin the new Story front door's behaviour, so the design rules
// survive a restyle:
//
// - Step order: the party split comes before the flagged overlay
//   (waffle_all < waffle_party < waffle_flag), and the step list is
//   exactly the six beats plus the rest beat.
// - The waffle: House and Senate are separate grids; flagged members
//   appear only in state 2, in the lighter tint of their own party's
//   colour, ringed in the full party colour; no amber (the accent)
//   is ever a data colour in the waffle.
// - The waffle order is fixed: party blocks contiguous (Democrats,
//   then Republicans, then others), flagged first inside each block
//   (isWaffleOrdered).
// - Steps are idempotent: every step has a graphic-state entry, the
//   waffle states run 0 -> 1 -> 2 and the stacked states 1 -> 2 -> 3
//   in step order, and storyStepText is a pure function of the
//   aggregates.
// - The card switch is instant (no opacity transition on the card),
//   cards sit at the top of their step, and cards stay visible
//   without JS and without scrolly: the hiding rule is scoped under
//   html.js.scrolly.
// - Step heights come from innerHeight in px (--step-min), never vh.
// - Reduced motion is a first-class path: the CSS kills transitions
//   and story.js checks the media query.
//
// Run: node --test "receipts/site/tests/*.test.mjs"

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const here = path.dirname(fileURLToPath(import.meta.url));
const CSS = readFileSync(path.resolve(here, '..', 'templates', 'style.css'), 'utf8');
const JS = readFileSync(path.resolve(here, '..', 'templates', 'story.js'), 'utf8');

function rule(selector) {
  const m = CSS.match(new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\{([^}]*)\\}'));
  assert.ok(m, 'missing rule: ' + selector);
  return m[1];
}

/* Load story.js in a vm with DOM stubs: initStory() finds no
   #story-data payload and returns, leaving the pure helpers. */
function loadStory() {
  const el = () => ({
    textContent: '{}',
    classList: { add() {}, toggle() {}, contains: () => false },
    style: {},
    getAttribute: () => null,
    setAttribute() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
  });
  const sandbox = {
    document: {
      getElementById: () => el(),
      querySelector: () => null,
      querySelectorAll: () => [],
      documentElement: el(),
      readyState: 'complete',
      addEventListener() {},
    },
    console,
    setTimeout,
    clearTimeout,
  };
  vm.createContext(sandbox);
  vm.runInContext(JS, sandbox);
  return (code) => vm.runInContext(code, sandbox);
}

const EXPECTED_STEPS = [
  'waffle_all', 'waffle_party', 'waffle_flag', 'ranked',
  'stacked_aipac', 'stacked_corp', 'stacked_individual', 'rest',
  'member', 'member_trend', 'member_zoom', 'map', 'targets',
];

test('the step list is the six beats plus the rest beat, party before flag', () => {
  const page = loadStory();
  const steps = page('STORY_STEPS');
  assert.equal([...steps].join(','), EXPECTED_STEPS.join(','));
  assert.ok(steps.indexOf('waffle_party') < steps.indexOf('waffle_flag'));
});

test('waffle: House and Senate are separate grids', () => {
  assert.match(rule('.waffle-grid.house'), /grid-template-columns\s*:\s*repeat\(29,/);
  assert.match(rule('.waffle-grid.senate'), /grid-template-columns\s*:\s*repeat\(20,/);
});

test('waffle: flagged appears only in state 2, lighter tint ringed in full colour', () => {
  assert.match(
    rule('.waffles[data-state="2"] .waffle-grid i.d.flagged'),
    /background\s*:\s*var\(--dem-flagged\)/,
  );
  assert.match(
    rule('.waffles[data-state="2"] .waffle-grid i.d.flagged'),
    /box-shadow\s*:\s*0 0 0 1px var\(--dem-full\)/,
  );
  assert.match(
    rule('.waffles[data-state="2"] .waffle-grid i.r.flagged'),
    /background\s*:\s*var\(--rep-flagged\)/,
  );
  assert.match(
    rule('.waffles[data-state="2"] .waffle-grid i.r.flagged'),
    /box-shadow\s*:\s*0 0 0 1px var\(--rep-full\)/,
  );
  // No flagged styling before the overlay step.
  assert.doesNotMatch(CSS, /\.waffles\[data-state="1"\][^{]*\.flagged/);
  // The amber accent is never a data colour in the waffle.
  for (const m of CSS.matchAll(/\.waffles[^{]*\{[^}]*\}/g)) {
    assert.doesNotMatch(m[0], /--amber|#a35a00/);
  }
});

test('waffle order: party blocks contiguous, flagged first inside each block', () => {
  const page = loadStory();
  const good = [
    { party: 'Democrats', flagged: true },
    { party: 'Democrats', flagged: false },
    { party: 'Republicans', flagged: true },
    { party: 'Republicans', flagged: false },
    { party: 'Independents', flagged: false },
  ];
  assert.equal(page(`isWaffleOrdered(${JSON.stringify(good)})`), true);
  const flaggedLate = [
    { party: 'Democrats', flagged: false },
    { party: 'Democrats', flagged: true },
  ];
  assert.equal(page(`isWaffleOrdered(${JSON.stringify(flaggedLate)})`), false);
  const splitBlock = [
    { party: 'Democrats', flagged: false },
    { party: 'Republicans', flagged: false },
    { party: 'Democrats', flagged: false },
  ];
  assert.equal(page(`isWaffleOrdered(${JSON.stringify(splitBlock)})`), false);
});

test('steps are idempotent: every step maps to a graphic state, in order', () => {
  const page = loadStory();
  const states = page('STEP_STATES');
  for (const step of EXPECTED_STEPS) assert.ok(step in states, 'no state for ' + step);
  assert.deepEqual(
    ['waffle_all', 'waffle_party', 'waffle_flag'].map((s) => states[s].waffle),
    [0, 1, 2],
  );
  assert.deepEqual(
    ['stacked_aipac', 'stacked_corp', 'stacked_individual'].map((s) => states[s].stacked),
    [1, 2, 3],
  );
  assert.deepEqual(
    ['member', 'member_trend', 'member_zoom'].map((s) => states[s].member),
    ['member', 'member_trend', 'member_zoom'],
  );
});

test('storyStepText is a pure function of the aggregates', () => {
  const page = loadStory();
  const fixture = {
    meta: { current_cycle: 2026, next_cycle: 2028, incoming_total: 535 },
    preset: { balanced_short: 'corporate PAC over $100k and over 5% of receipts' },
    counts: { balanced_dirty: 361 },
    waffle: {
      house: { seats: 435, counts: { dem: 2, rep: 1, ind: 0, other: 0, flagged: 2 } },
      senate: { seats: 100, counts: { dem: 1, rep: 1, ind: 1, other: 0, flagged: 1 } },
    },
    ranked: {
      house: [{ name: 'A', rounded: '$1M' }],
      senate: [{ name: 'B', rounded: '$2M' }],
    },
    stacked: {
      house: { aipac: 1e6, corp: 2e6, individual: 3e6, total: 6e6 },
      senate: { aipac: 1e6, corp: 2e6, individual: 3e6, total: 6e6 },
    },
    member: {
      name: 'C D',
      returning: false,
      race_chamber: 'Senate',
      split: { rounded: { dirty: '$3M', udp_benefit: '$2M', individual: '$1M' } },
      trend: [{ cycle: 2026, rounded: '$3M' }],
      zoom: { member_dirty: 3e6, top: [{ name: 'B', rounded: '$2M', dirty: 1e6 }], median: 5e5 },
    },
    map: { districts: [{ tier: 'dirty' }, { tier: null }] },
    targets: [{ name: 'A', rounded: '$1M' }],
    targets_total: 7,
  };
  const arg = JSON.stringify(fixture);
  const flag1 = page(`storyStepText('waffle_flag', ${arg})`);
  const flag2 = page(`storyStepText('waffle_flag', ${arg})`);
  assert.equal(flag1, flag2);
  assert.match(flag1, /<b>2 of 435<\/b>/);
  assert.match(flag1, /<b>361<\/b> of the incoming 535/);
  assert.match(page(`storyStepText('targets', ${arg})`), /<b>7<\/b> incoming members/);
  // Without the tolerance label the flag text is not fabricated.
  const bare = { ...fixture, preset: { balanced_short: null } };
  assert.equal(page(`storyStepText('waffle_flag', ${JSON.stringify(bare)})`), null);
});

test('story cards switch instantly: no opacity transition on the card', () => {
  assert.doesNotMatch(rule('.scrolly-step .card'), /transition\s*:/);
});

test('story cards sit at the top of their step, not centred in it', () => {
  assert.match(rule('.scrolly-step'), /align-items\s*:\s*flex-start/);
});

test('story cards stay visible without JS or scrolly: hiding is scoped under html.js.scrolly', () => {
  assert.match(rule('.scrolly-step .card'), /opacity\s*:\s*1/);
  assert.match(rule('html.js.scrolly .scrolly-step .card'), /opacity\s*:\s*0/);
  assert.match(rule('html.js.scrolly .scrolly-step.active .card'), /opacity\s*:\s*1/);
});

test('step heights are px from innerHeight, never vh', () => {
  assert.match(rule('.scrolly-step'), /min-height\s*:\s*var\(--step-min/);
  assert.match(JS, /--step-min/);
  assert.match(JS, /innerHeight/);
});

test('reduced motion is checked in JS and transitions die in CSS', () => {
  assert.match(JS, /prefers-reduced-motion: reduce/);
  assert.match(JS, /applyFinalStates/);
  const m = CSS.match(/@media \(prefers-reduced-motion: reduce\)\{([\s\S]*?)\n\}/);
  assert.ok(m, 'missing reduced-motion media block');
  assert.match(m[1], /transition\s*:\s*none/);
});
