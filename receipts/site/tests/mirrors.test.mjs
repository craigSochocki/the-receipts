// Direct unit tests for the JS mirrors of the Python rules:
// termRecord (receipts/domain/term.py), tierOf / dirtyUnderPreset
// (receipts/domain/clean_2026.py), and the cycle picker (applyCycle /
// setCycle / cycleRecord). The Playwright smoke test only asserts rendered
// DOM; these tests pin the logic itself, on the shipped template files
// loaded through ./load_page.mjs. They also cover the story's pure
// helpers: the party-chart label plan (partyLabelPlan) and the
// scroll-step derivation (stepAtScroll).
//
// Run: node --test "receipts/site/tests/*.test.mjs"

import assert from 'node:assert/strict';
import test from 'node:test';

import { CY, loadPage } from './load_page.mjs';

// Alice's term (verdict 2024): the 2024 and 2026 cycles summed, the 2022
// cycle excluded. corp 5000+7000, aipac 2000+0, individual 50000+80000,
// udp_benefit 300+400, dirty 7300+7400; dep_share (12000+2000)/144000.
const ALICE_TERM = {
  cycle: 2024,
  unopposed: false,
  cash_on_hand: 5000,
  corp: 12000,
  aipac_direct: 2000,
  individual: 130000,
  udp_support: 100,
  udp_opp_credit: 50,
  udp_benefit: 700,
  dirty: 14700,
  self_funding: 1000,
  cand_loans: 500,
  cand_contrib: 500,
  total_receipts: 150000,
  total_disbursements: 140000,
  other_committees_total: 200,
  all_ie_support: 400,
  all_ie_oppose: 0,
  all_ie_total: 400,
  dep_share: 0.0972,
  aipac_udp_flag: true,
};

test('termRecord sums cycles since the verdict cycle, not earlier ones', () => {
  const page = loadPage();
  assert.deepEqual(page.json("termRecord(BY_KEY['alice'])"), ALICE_TERM);
});

test('termRecord takes unopposed from the verdict cycle, cash from the last', () => {
  const page = loadPage();
  const term = page.json("termRecord(BY_KEY['alice'])");
  assert.equal(term.unopposed, false);
  assert.equal(term.cash_on_hand, 5000);
  assert.equal(term.cycle, 2024);
});

test('termRecord returns {} with no verdict cycle or no cycles since it', () => {
  const page = loadPage();
  assert.deepEqual(page.json("termRecord(BY_KEY['bob'])"), {});
  assert.deepEqual(
    page.call('termRecord', { verdict_cycle: 2026, cycles: [{ cycle: 2024 }] }),
    {},
  );
});

test('termRecord leaves dep_share null when nothing was accepted', () => {
  const page = loadPage();
  const cycles = CY.map((k) => [k, k === 'cycle' ? 2026 : 0]);
  const person = { verdict_cycle: 2026, cycles: [Object.fromEntries(cycles)] };
  const term = page.call('termRecord', person);
  assert.equal(term.dep_share, null);
  assert.equal(term.aipac_udp_flag, false);
  assert.equal(term.dirty, 0);
});

test('cycleRecord latest is the term plus the stored verdict columns', () => {
  const page = loadPage();
  const record = page.json("cycleRecord(BY_KEY['alice'], 'latest')");
  assert.deepEqual(record, {
    ...ALICE_TERM,
    clean: true,
    dirty: 14700,
    tier_balanced: 'clean',
    tier_lenient: 'clean',
  });
});

test('cycleRecord returns one cycle verbatim, and {} for a missing cycle', () => {
  const page = loadPage();
  const record = page.json("cycleRecord(BY_KEY['alice'], 2024)");
  assert.equal(record.cycle, 2024);
  assert.equal(record.corp, 5000);
  assert.equal(record.dirty, 7300);
  assert.deepEqual(page.json("cycleRecord(BY_KEY['alice'], 1999)"), {});
});

test('tierOf reads cy_clean under Strict and the stored tiers otherwise', () => {
  const page = loadPage();
  const p = { cy_clean: true, cy_tier_balanced: 'dirty', cy_tier_lenient: 'dirty' };
  page.eval("state.preset = 'strict'");
  assert.equal(page.call('tierOf', p), 'clean');
  page.eval("state.preset = 'balanced'");
  assert.equal(page.call('tierOf', p), 'dirty');
  page.eval("state.preset = 'lenient'");
  assert.equal(page.call('tierOf', p), 'dirty');
  page.eval("state.preset = 'strict'");
  assert.equal(page.call('tierOf', { ...p, cy_clean: false }), 'dirty');
  assert.equal(page.call('tierOf', { ...p, cy_clean: null }), null);
});

test('isNotDirty treats clean and below_threshold as not dirty', () => {
  const page = loadPage();
  page.eval("state.preset = 'balanced'");
  assert.equal(page.call('isNotDirty', { cy_tier_balanced: 'clean' }), true);
  assert.equal(
    page.call('isNotDirty', { cy_tier_balanced: 'below_threshold' }),
    true,
  );
  assert.equal(page.call('isNotDirty', { cy_tier_balanced: 'dirty' }), false);
  assert.equal(page.call('isNotDirty', { cy_tier_balanced: null }), false);
});

test('dirtyUnderPreset: Strict is any dirty dollar; presets read the tier', () => {
  const page = loadPage();
  page.eval("state.preset = 'strict'");
  assert.equal(page.call('dirtyUnderPreset', { dirty: 1 }), true);
  assert.equal(page.call('dirtyUnderPreset', { dirty: 0 }), false);
  assert.equal(page.call('dirtyUnderPreset', { dirty: -5 }), false);
  page.eval("state.preset = 'balanced'");
  assert.equal(
    page.call('dirtyUnderPreset', { tier_balanced: 'dirty' }),
    true,
  );
  assert.equal(
    page.call('dirtyUnderPreset', { tier_balanced: 'below_threshold' }),
    false,
  );
  assert.equal(page.call('dirtyUnderPreset', { tier_balanced: null }), false);
  page.eval("state.preset = 'lenient'");
  assert.equal(page.call('dirtyUnderPreset', { tier_lenient: 'dirty' }), true);
  assert.equal(page.call('dirtyUnderPreset', { tier_lenient: 'clean' }), false);
});

test('cycle picker offers latest plus the configured cycles only', () => {
  const page = loadPage();
  assert.deepEqual(page.json('CYCLE_CHOICES'), ['latest', 2026, 2024, 2022]);
  assert.equal(page.eval("isCycleChoice('latest')"), true);
  assert.equal(page.eval('isCycleChoice(2024)'), true);
  assert.equal(page.eval('isCycleChoice(1999)'), false);
  assert.equal(page.eval("cycleValue('2024')"), 2024);
  assert.equal(page.eval("cycleValue('latest')"), 'latest');
});

test('applyCycle copies one cycle into the cy_ fields, with NO_RECORD defaults', () => {
  const page = loadPage();
  page.eval('applyCycle(2024)');
  assert.equal(page.eval('CY'), '2024');
  assert.equal(page.eval('IN_CY'), 'in 2024');
  assert.equal(page.json("BY_KEY['alice'].cy_dirty"), 7300);
  assert.equal(page.json("BY_KEY['alice'].cy_cycle"), 2024);
  assert.equal(page.json("BY_KEY['alice'].cy_clean"), true);
  // Bob has no 2024 record: money defaults to 0, verdict columns to null.
  assert.equal(page.json("BY_KEY['bob'].cy_dirty"), 0);
  assert.equal(page.json("BY_KEY['bob'].cy_clean"), null);
  assert.equal(page.json("BY_KEY['bob'].cy_cycle"), null);
  page.eval("applyCycle('latest')");
  assert.equal(page.eval('CY'), 'latest');
  assert.equal(page.eval('IN_CY'), 'since their last election');
  assert.equal(page.json("BY_KEY['alice'].cy_dirty"), 14700);
});

test('setCycle switches the picker and ignores choices outside it', () => {
  const page = loadPage();
  page.eval('setCycle(2024)');
  assert.equal(page.json('state.cycle'), 2024);
  assert.equal(page.json("BY_KEY['alice'].cy_dirty"), 7300);
  page.eval('setCycle(1999)');
  assert.equal(page.json('state.cycle'), 2024);
  page.eval("setCycle('latest')");
  assert.equal(page.json('state.cycle'), 'latest');
  assert.equal(page.json("BY_KEY['alice'].cy_dirty"), 14700);
});

test('seatUpNext is every House seat and the next-cycle Senate class only', () => {
  const page = loadPage();
  assert.equal(page.eval("seatUpNext(BY_KEY['alice'])"), true);
  assert.equal(page.eval("seatUpNext(BY_KEY['carol'])"), true);
  assert.equal(page.eval("seatUpNext(BY_KEY['eve'])"), false);
});

test('primaryTargets lists dirty incoming members with a seat up, dirtiest first', () => {
  const page = loadPage();
  // Balanced (the default): Alice is clean, Dave is below threshold.
  assert.deepEqual(
    page.json('primaryTargets().map(p => p.person_key)'),
    [],
  );
  page.eval("state.preset = 'strict'");
  // Dave (60000) then Alice (14700); Eve is dirty but her class is not up.
  assert.deepEqual(
    page.json('primaryTargets().map(p => p.person_key)'),
    ['dave', 'alice'],
  );
});

test('decode maps scalars and cycle records to named objects', () => {
  const page = loadPage();
  assert.equal(page.json('PEOPLE.length'), 5);
  assert.equal(page.json("BY_KEY['alice'].full_name"), 'Alice Adams');
  assert.equal(page.json("BY_KEY['alice'].verdict_cycle"), 2024);
  assert.equal(page.json("BY_KEY['alice'].cycles[0].corp"), 100);
  assert.equal(page.json("BY_KEY['alice'].cycles[2].corp"), 7000);
  // Nested lists stay positional until decodeNested runs.
  assert.equal(page.eval("Array.isArray(BY_KEY['alice'].per_cycle[0])"), true);
  assert.equal(
    page.eval("decodeNested(BY_KEY['alice']).per_cycle[0].individual"),
    50000,
  );
});

// Fixture story statuses (latest cycle = each member's term): Alice
// clean, Carol clean, Eve dirty, Bob unjudged, Dave below threshold.
// Democrats total 3, Republicans 2, so the plan's domain leaves room
// past the longest bar.
test('partyLabelPlan keeps fitting counts inside and lists small ones past the bar', () => {
  const page = loadPage();
  const plan = page.json('partyLabelPlan(partyGroups(PEOPLE))');
  assert.equal(plan.domainMax, 63);
  assert.deepEqual(plan.inside, [
    { party: 'Democrats', status: 'clean', n: 2 },
  ]);
  assert.deepEqual(
    plan.outside.map((o) => ({ party: o.party, text: o.text })),
    [
      { party: 'Democrats', text: '1 dirty' },
      { party: 'Republicans', text: '1 below threshold, 1 not judged' },
    ],
  );
  // Past each party's bar end (3 and 2 in data units), inside the plot.
  assert.ok(plan.outside[0].x > 3 && plan.outside[0].x < 4);
  assert.ok(plan.outside[1].x > 2 && plan.outside[1].x < 3);
});

test('stepAtScroll is the last step at or above the middle, else the first', () => {
  const page = loadPage();
  assert.equal(
    page.eval("stepAtScroll([{step:'all',top:100},{step:'status',top:500},{step:'ranked',top:900}], 400)"),
    'all',
  );
  assert.equal(
    page.eval("stepAtScroll([{step:'all',top:-100},{step:'status',top:300},{step:'ranked',top:800}], 400)"),
    'status',
  );
  // Instant jump to the top: no step has crossed the middle yet.
  assert.equal(
    page.eval("stepAtScroll([{step:'all',top:500},{step:'status',top:900},{step:'ranked',top:1300}], 400)"),
    'all',
  );
  // Instant jump to the bottom: every step has crossed it.
  assert.equal(
    page.eval("stepAtScroll([{step:'all',top:-1000},{step:'status',top:-900},{step:'ranked',top:-800},{step:'party',top:-700},{step:'house',top:-600},{step:'districts',top:-500},{step:'senate',top:-400},{step:'targets',top:-300},{step:'find',top:-200}], 400)"),
    'find',
  );
});
