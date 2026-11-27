// Explore page unit tests: pagination, grouped default order, URL
// filter-state round-trip, drawer open/close via ?member=, search
// debounce, overview waffles, hemicycles, and the five default
// columns. The shipped explore.js runs in a vm through ./load_page.mjs,
// exactly as the page embeds it.
//
// Run: node --test "receipts/site/tests/*.test.mjs"

import assert from 'node:assert/strict';
import test from 'node:test';

import { loadPage } from './load_page.mjs';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test('pagination: 25 per page, "Showing 1–25 of N" label shape', () => {
  const page = loadPage();
  assert.deepEqual(page.json('PAGE_SIZES'), [25, 50, 100]);
  assert.equal(page.eval('state.pageSize'), 25);
  assert.equal(page.eval('pageLabel(664, 1, 25)'), 'Showing 1–25 of 664');
  assert.equal(page.eval('pageLabel(664, 27, 25)'), 'Showing 651–664 of 664');
  assert.equal(page.eval('pageLabel(0, 1, 25)'), 'Showing 0 of 0');
  assert.equal(page.eval('pageCount(664, 25)'), 27);
  assert.equal(page.eval('pageCount(0, 25)'), 1);
  // The fixture table renders all five people on one page, grouped.
  assert.equal(
    page.eval("document.getElementById('showing').textContent"),
    'Showing 1–5 of 5 · Grouped: House, then Senate, by party — flagged first in each party block.',
  );
  assert.equal(page.eval("document.getElementById('explore-tbody').innerHTML.match(/<tr /g).length"), 5);
});

test('grouped default order: House then Senate, party-grouped, flagged first in the party block', () => {
  const page = loadPage();
  assert.deepEqual(
    page.json('sortRows(applyFilters()).map(p=>p.person_key)'),
    ['alice', 'dave', 'bob', 'eve', 'carol'],
  );
  // With the flagged filter on, only the flagged member remains.
  page.eval("state.flag='flagged'");
  assert.deepEqual(
    page.json('sortRows(applyFilters()).map(p=>p.person_key)'),
    ['alice'],
  );
});

test('URL filter state round-trips through parse/build', () => {
  const page = loadPage();
  const q =
    '?q=alice&chamber=House&flag=flagged&preset=strict&cycle=2024' +
    '&sort=total_accepted_career&dir=asc&page=2&size=50&view=leaders';
  const parsed = page.json(`parseExploreUrl('${q}', '')`);
  assert.equal(parsed.q, 'alice');
  assert.equal(parsed.chamber, 'House');
  assert.equal(parsed.flag, 'flagged');
  assert.equal(parsed.preset, 'strict');
  assert.equal(parsed.cycle, 2024);
  assert.equal(parsed.sortKey, 'total_accepted_career');
  assert.equal(parsed.sortDir, 'asc');
  assert.equal(parsed.page, 2);
  assert.equal(parsed.pageSize, 50);
  assert.equal(parsed.view, 'leaders');
  page.eval(`Object.assign(state, parseExploreUrl('${q}', ''))`);
  const rebuilt = page.eval('buildExploreUrl()');
  assert.deepEqual(page.json(`parseExploreUrl(${JSON.stringify(rebuilt)}, '')`), parsed);
  // A bare URL parses to the defaults.
  const defaults = page.eval("parseExploreUrl('', '')");
  assert.equal(defaults.preset, 'balanced');
  assert.equal(defaults.sortKey, 'grouped');
  assert.equal(defaults.page, 1);
  assert.equal(defaults.pageSize, 25);
});

test('drawer opens via ?member= and closes again', () => {
  const page = loadPage({ search: '?member=alice' });
  assert.equal(page.eval('detailKey'), 'alice');
  const sheet = page.eval("document.getElementById('detail-sheet').innerHTML");
  assert.ok(sheet.includes('Alice Adams'));
  assert.ok(sheet.includes('AIPAC PAC direct'));
  assert.ok(sheet.includes('Flagged: took AIPAC PAC direct money or UDP benefit money'));
  assert.ok(sheet.includes('fec.gov/data/candidate/H4MI08123'));
  page.eval('closeDetail()');
  assert.equal(page.eval('detailKey'), null);
  assert.equal(
    page.eval("document.getElementById('detail').classList.contains('open')"),
    false,
  );
});

test('search is debounced: skeletons first, results after the delay', async () => {
  const page = loadPage();
  assert.equal(page.eval('SEARCH_DEBOUNCE_MS'), 300);
  page.eval("state.q='alice'; state.page=1; scheduleSearchRender()");
  assert.ok(
    page.eval("document.getElementById('explore-tbody').innerHTML").includes('skeleton'),
    'skeletons show while the search settles',
  );
  await sleep(450);
  assert.equal(
    page.eval("document.getElementById('showing').textContent"),
    'Showing 1–1 of 1 · Grouped: House, then Senate, by party — flagged first in each party block.',
  );
  assert.ok(page.eval("document.getElementById('explore-tbody').innerHTML").includes('Alice Adams'));
});

test('overview strip: two chamber waffles, one dot per seat', () => {
  const page = loadPage();
  const html = page.eval("document.getElementById('explore-overview').innerHTML");
  assert.equal((html.match(/<i class="/g) || []).length, 535);
  // 530 seats are uncalled in the five-person fixture; one is flagged.
  assert.equal((html.match(/<i class="uncalled"/g) || []).length, 530);
  assert.equal((html.match(/<i class="dem flagged"/g) || []).length, 1);
  assert.ok(html.includes('House'));
  assert.ok(html.includes('Senate'));
});

test('hemicycles: one dot per seat per chamber, uncalled last', () => {
  const page = loadPage();
  page.eval('renderHemicycle()');
  const house = page.eval("document.getElementById('hemi-house').innerHTML");
  const senate = page.eval("document.getElementById('hemi-senate').innerHTML");
  assert.equal((house.match(/<circle/g) || []).length, 435);
  assert.equal((senate.match(/<circle/g) || []).length, 100);
  assert.equal((house.match(/dot-uncalled/g) || []).length, 432);
  assert.equal((senate.match(/dot-uncalled/g) || []).length, 98);
});

test('five default columns, and search finds by name', () => {
  const page = loadPage();
  assert.equal(page.eval('currentCols().length'), 5);
  const head = page.eval("document.getElementById('explore-thead').innerHTML");
  assert.equal((head.match(/<th/g) || []).length, 5);
  for (const label of ['Member', 'Verdict', 'Total', 'AIPAC $', 'Corporate PAC $']) {
    assert.ok(head.includes(label), `header has ${label}`);
  }
  // 'adams' matches Alice's name only ('ali' would also match California).
  page.eval("state.q='adams'");
  assert.deepEqual(
    page.json('applyFilters().map(p=>p.person_key)'),
    ['alice'],
  );
});

test('#search loads without error and leaves the query empty', () => {
  const page = loadPage({ hash: '#search' });
  assert.equal(page.eval('state.q'), '');
});
