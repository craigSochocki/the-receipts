// Loads the shipped site scripts (receipts/site/templates/tracker.js,
// views.js, story.js) in a Node vm context with a stubbed document, so the
// JS unit tests exercise the exact code the page embeds — never a copy.
//
// Run: node --test "receipts/site/tests/*.test.mjs"
// (the bare directory form does not work on this Node build: it tries to
// load the directory as a module, so the glob is the command.)
//
// The stubs are deliberately permissive: every element is a plain object
// with the properties the scripts touch (innerHTML, value, classList,
// addEventListener, querySelector(All), ...), cached per id so a value
// written in one place reads back in another. The page's init() runs on
// load against these stubs, exactly as it runs in the browser.

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATES = path.resolve(HERE, '..', 'templates');
const read = (name) => readFileSync(path.join(TEMPLATES, name), 'utf8');

/* ---- fixture column lists (the decode layer's contract) ---- */
export const CY = [
  'cycle', 'corp', 'aipac_direct', 'individual', 'udp_support', 'udp_opp_credit',
  'udp_benefit', 'dirty', 'clean', 'unopposed', 'aipac_udp_flag', 'tier_balanced',
  'tier_lenient', 'dep_share', 'self_funding', 'cand_loans', 'cand_contrib',
  'total_receipts', 'total_disbursements', 'cash_on_hand', 'other_committees_total',
  'all_ie_support', 'all_ie_oppose', 'all_ie_total', 'up_for_election',
];
export const SCALARS = [
  'person_key', 'full_name', 'state', 'district_119', 'district_120',
  'chamber_119', 'chamber_120', 'party_119', 'party_120', 'leadership_119',
  'leadership_120', 'in_119th', 'in_120th', 'fec_candidate_ids', 'senate_class',
  'verdict_cycle', 'clean', 'dirty', 'tier_balanced', 'tier_lenient',
];
const PC = [
  'cycle', 'candidate_id', 'individual', 'aipac_pac_direct',
  'aipac_earmark_transmitted', 'corporate_pac', 'corporate_earmark_transmitted',
];

export const COLS = {
  scalars: SCALARS,
  pc: PC,
  upc: ['cycle', 'candidate_id', 'udp_ie_support', 'attribution'],
  sf: ['cycle', 'candidate_id'],
  oc: ['cycle', 'candidate_id'],
  aie: ['cycle', 'candidate_id'],
  tc: ['committee_id', 'committee_name', 'support', 'oppose', 'total', 'rows'],
  cy: CY,
  pi: ['cycle', 'pro_israel_pac', 'pro_israel_ie_support', 'pro_israel_opp_credit'],
  current_cycle: 2026,
  next_cycle: 2028,
  next_senate_class: 2,
  picker_cycles: [2026, 2024, 2022],
  ie_span: '2022–2026',
  csv: [...SCALARS, 'per_cycle'],
};

/* ---- fixture people (synthetic money, chosen to keep sums exact) ---- */
function cycleRow(cycle, over = {}) {
  return {
    cycle, corp: 0, aipac_direct: 0, individual: 0, udp_support: 0,
    udp_opp_credit: 0, udp_benefit: 0, dirty: 0, clean: null, unopposed: false,
    aipac_udp_flag: false, tier_balanced: null, tier_lenient: null,
    dep_share: null, self_funding: 0, cand_loans: 0, cand_contrib: 0,
    total_receipts: 0, total_disbursements: 0, cash_on_hand: null,
    other_committees_total: 0, all_ie_support: 0, all_ie_oppose: 0,
    all_ie_total: 0, up_for_election: true, ...over,
  };
}

function person(scalars, cycles, perCycle = []) {
  return { ...scalars, cycles, per_cycle: perCycle };
}

const ALICE = person(
  {
    person_key: 'alice', full_name: 'Alice Adams', state: 'MI', district_119: '8',
    district_120: '8', chamber_119: 'House', chamber_120: 'House',
    party_119: 'Democrat', party_120: 'Democrat', leadership_119: null,
    leadership_120: null, in_119th: 'yes', in_120th: 'yes',
    fec_candidate_ids: ['H4MI08123'], senate_class: null, verdict_cycle: 2024,
    clean: true, dirty: 14700, tier_balanced: 'clean', tier_lenient: 'clean',
  },
  [
    cycleRow(2022, { corp: 100, individual: 1000, dirty: 100, clean: false,
      tier_balanced: 'dirty', tier_lenient: 'dirty', dep_share: 0.0909,
      total_receipts: 1100, total_disbursements: 900, cash_on_hand: 200 }),
    cycleRow(2024, { corp: 5000, aipac_direct: 2000, individual: 50000,
      udp_support: 100, udp_opp_credit: 50, udp_benefit: 300, dirty: 7300,
      clean: true, aipac_udp_flag: true, tier_balanced: 'clean',
      tier_lenient: 'clean', dep_share: 0.1228, self_funding: 1000,
      cand_loans: 500, cand_contrib: 500, total_receipts: 60000,
      total_disbursements: 55000, cash_on_hand: 5000,
      other_committees_total: 200, all_ie_support: 400, all_ie_total: 400 }),
    cycleRow(2026, { corp: 7000, individual: 80000, udp_benefit: 400, dirty: 7400,
      clean: false, aipac_udp_flag: true, tier_balanced: 'dirty',
      tier_lenient: 'below_threshold', dep_share: 0.0805, total_receipts: 90000,
      total_disbursements: 85000, cash_on_hand: 5000 }),
  ],
  [[2024, 'H4MI08123', 50000, 2000, 0, 5000, 0]],
);
const BOB = person(
  {
    person_key: 'bob', full_name: 'Bob Baker', state: 'OH', district_119: '1',
    district_120: '1', chamber_119: 'House', chamber_120: 'House',
    party_119: 'Republican', party_120: 'Republican', leadership_119: null,
    leadership_120: null, in_119th: 'yes', in_120th: 'yes',
    fec_candidate_ids: ['H4OH01123'], senate_class: null, verdict_cycle: null,
    clean: null, dirty: null, tier_balanced: null, tier_lenient: null,
  },
  [],
);
const CAROL = person(
  {
    person_key: 'carol', full_name: 'Carol Chen', state: 'CA', district_119: null,
    district_120: null, chamber_119: 'Senate', chamber_120: 'Senate',
    party_119: 'Democrat', party_120: 'Democrat', leadership_119: null,
    leadership_120: null, in_119th: 'yes', in_120th: 'yes',
    fec_candidate_ids: ['S4CA00123'], senate_class: 2, verdict_cycle: 2026,
    clean: true, dirty: 0, tier_balanced: 'clean', tier_lenient: 'clean',
  },
  [cycleRow(2026, { individual: 200000, dirty: 0, clean: true,
    tier_balanced: 'clean', tier_lenient: 'clean', dep_share: 0,
    total_receipts: 200000, total_disbursements: 150000, cash_on_hand: 30000 })],
);
const DAVE = person(
  {
    person_key: 'dave', full_name: 'Dave Diaz', state: 'TX', district_119: '3',
    district_120: '3', chamber_119: 'House', chamber_120: 'House',
    party_119: 'Republican', party_120: 'Republican', leadership_119: null,
    leadership_120: null, in_119th: 'yes', in_120th: 'yes',
    fec_candidate_ids: ['H4TX03123'], senate_class: null, verdict_cycle: 2024,
    clean: false, dirty: 60000, tier_balanced: 'below_threshold',
    tier_lenient: 'clean',
  },
  [cycleRow(2024, { corp: 60000, individual: 400000, dirty: 60000, clean: false,
    tier_balanced: 'below_threshold', tier_lenient: 'clean', dep_share: 0.12,
    total_receipts: 500000, total_disbursements: 450000, cash_on_hand: 10000 })],
);
const EVE = person(
  {
    person_key: 'eve', full_name: 'Eve Evans', state: 'NY', district_119: null,
    district_120: null, chamber_119: 'Senate', chamber_120: 'Senate',
    party_119: 'Democrat', party_120: 'Democrat', leadership_119: null,
    leadership_120: null, in_119th: 'yes', in_120th: 'yes',
    fec_candidate_ids: ['S4NY00123'], senate_class: 1, verdict_cycle: 2026,
    clean: false, dirty: 9000, tier_balanced: 'dirty', tier_lenient: 'dirty',
  },
  [cycleRow(2026, { corp: 9000, individual: 100000, dirty: 9000, clean: false,
    tier_balanced: 'dirty', tier_lenient: 'dirty', dep_share: 0.075,
    total_receipts: 120000, total_disbursements: 100000, cash_on_hand: 5000 })],
);

const PEOPLE = [ALICE, BOB, CAROL, DAVE, EVE];

/* ---- positional encoding, mirroring build_site.encode_row ---- */
function encodePerson(p) {
  const row = SCALARS.map((k) => p[k] ?? null);
  const nested = [
    p.per_cycle ?? [],
    [], [], [], [], [],
    (p.cycles ?? []).map((c) => CY.map((k) => c[k] ?? null)),
    [],
  ];
  return [...row, ...nested];
}

const RAW = PEOPLE.map(encodePerson);
const OPP = {};
const GEO = { type: 'FeatureCollection', features: [] };

/* ---- stub DOM ---- */
function makeElement() {
  return {
    innerHTML: '',
    textContent: '',
    value: '',
    disabled: false,
    checked: false,
    hidden: false,
    childNodes: [],
    style: {},
    dataset: {},
    classList: {
      add() {}, remove() {}, toggle() {}, contains() { return false; },
    },
    addEventListener() {},
    removeEventListener() {},
    appendChild() {},
    remove() {},
    focus() {},
    click() {},
    querySelector() { return makeElement(); },
    querySelectorAll() { return []; },
    getAttribute() { return null; },
    setAttribute() {},
    removeAttribute() {},
    closest() { return null; },
    scrollIntoView() {},
  };
}

/** Load the shipped scripts into a fresh vm context and run init(). */
export function loadPage() {
  const byId = new Map();
  const payloads = {
    'receipts-cols': COLS,
    'receipts-data': RAW,
    'opp-data': OPP,
    'us-states': GEO,
    'us-districts': GEO,
  };
  const documentStub = {
    getElementById(id) {
      if (!byId.has(id)) {
        const el = makeElement();
        if (id in payloads) el.textContent = JSON.stringify(payloads[id]);
        byId.set(id, el);
      }
      return byId.get(id);
    },
    querySelector() { return makeElement(); },
    querySelectorAll() { return []; },
    createElement() { return makeElement(); },
    addEventListener() {},
    documentElement: makeElement(),
    body: makeElement(),
  };
  const locationStub = { hash: '', pathname: '/' };
  const historyStub = {
    replaceState(_state, _title, url) {
      if (typeof url === 'string') locationStub.hash = url === '#' ? '' : url;
    },
    pushState(_state, _title, url) {
      if (typeof url === 'string') locationStub.hash = url === '#' ? '' : url;
    },
  };
  const sandbox = {
    document: documentStub,
    location: locationStub,
    history: historyStub,
    setTimeout,
    clearTimeout,
    console,
  };
  sandbox.window = sandbox;
  const ctx = vm.createContext(sandbox);
  // Page order (templates/page.html): tracker.js, then story.js, then
  // views.js — views.js ends with init(), which calls initStory().
  vm.runInContext(read('tracker.js'), ctx, { filename: 'tracker.js' });
  vm.runInContext(read('story.js'), ctx, { filename: 'story.js' });
  vm.runInContext(read('views.js'), ctx, { filename: 'views.js' });
  return {
    ctx,
    /** Evaluate an expression inside the page context. */
    eval(expr) {
      return vm.runInContext(expr, ctx);
    },
    /** The same expression, deep-copied out as plain JSON. */
    json(expr) {
      const raw = vm.runInContext(`JSON.stringify(${expr})`, ctx);
      return raw === undefined ? undefined : JSON.parse(raw);
    },
    /** Call a page function with plain arguments; result deep-copied out. */
    call(fn, ...args) {
      ctx.__args = args;
      const raw = vm.runInContext(`JSON.stringify(${fn}(...__args))`, ctx);
      return raw === undefined ? undefined : JSON.parse(raw);
    },
  };
}
