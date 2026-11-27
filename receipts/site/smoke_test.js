/* Runtime smoke test: runs inside the built pages in headless Chromium.
 * receipts/site/checks/runtime.py loads the Explore page and calls
 * main(), then loads the Story page and calls story() and
 * reducedMotion(). EXP is what the pages should show
 * (receipts/site/expectations.py, computed from the Explore payload). */
"use strict";
const assert = {
  ok(value, message) {
    if (!value) throw new Error("assert.ok failed: " + message);
  },
  strictEqual(actual, expected, message) {
    if (actual !== expected) {
      throw new Error(message + ": got " + String(actual) + ", want " + String(expected));
    }
  },
  deepStrictEqual(actual, expected, message) {
    const a = JSON.stringify(actual), e = JSON.stringify(expected);
    if (a !== e) throw new Error(message + ": got " + a + ", want " + e);
  },
};
// The checks treat element lists as arrays.
for (const list of [NodeList, HTMLCollection]) {
  for (const m of ["every", "some", "map", "filter", "find", "indexOf", "includes", "slice"]) {
    list.prototype[m] = list.prototype[m] || Array.prototype[m];
  }
}
// Counts the page computes in the browser are reported back and pinned in baseline.json.
const observed = {};
const observe = (key, value) => { observed[key] = value; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

window.smoke = {
  /* ---- Explore: decode, first page, search, pagination, drawer ---- */
  async main(EXP) {
    observe("rows", PEOPLE.length);

    /* The table renders one page of 25, in the grouped default order:
       House before Senate, party blocks together, flagged first in
       each block, then dirty money. The rendered first row is the
       pipeline's first row. */
    const tbody = document.getElementById("explore-tbody");
    const rendered = tbody.querySelectorAll("tr");
    assert.strictEqual(rendered.length, 25, "the table renders one page of 25 rows");
    assert.strictEqual(
      rendered[0].getAttribute("data-key"),
      sortRows(applyFilters())[0].person_key,
      "the rendered first row is the grouped order's first row");
    assert.ok(
      document.getElementById("showing").textContent.includes("of " + PEOPLE.length),
      "the showing line counts every row");

    /* Search, through the real input and its debounce; the counts are
       observed and pinned, so a search change fails the build. */
    const searchCount = async (q) => {
      const box = document.getElementById("q");
      box.value = q;
      box.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(SEARCH_DEBOUNCE_MS + 300);
      return applyFilters().length;
    };
    observe("search_michigan", await searchCount("michigan"));
    observe("search_district_11", await searchCount("11"));
    observe("search_senate", await searchCount("senate"));
    observe("search_mi", await searchCount("mi"));
    const ranked = sortRows(applyFilters());
    assert.ok(
      ranked[0].full_name.toLowerCase().startsWith("mi"),
      "relevance ranks a name match for 'mi' ahead of state matches");
    assert.strictEqual(await searchCount(""), PEOPLE.length, "clearing the search restores everyone");

    /* The old finder's Michigan House seats, as a dataset count: the
       incoming Michigan House delegation. */
    observe(
      "finder_mi_house_seats",
      PEOPLE.filter((p) => p.state === "MI" && chamber(p) === "House" && p.in_120th === "yes").length);

    /* Pagination moves the slice the showing line reports. */
    document.getElementById("page-next").click();
    assert.ok(
      document.getElementById("showing").textContent.includes("Showing 26–50 of " + PEOPLE.length),
      "page 2 shows the second slice");
    document.getElementById("page-prev").click();
    assert.ok(
      document.getElementById("showing").textContent.includes("Showing 1–25 of " + PEOPLE.length),
      "page back shows the first slice");

    /* The drawer: a row click opens it (one delegated listener on the
       table body), the API opens it for the dirtiest member, and the
       figures inside are the dataset's. */
    const firstKey = tbody.querySelector("tr").getAttribute("data-key");
    tbody.querySelector("tr .name-btn").click();
    assert.ok(
      document.getElementById("detail").classList.contains("open"),
      "clicking a row opens the drawer");
    assert.ok(
      document.getElementById("detail-sheet").textContent.includes(BY_KEY[firstKey].full_name),
      "the drawer shows the clicked member");
    closeDetail();
    assert.ok(
      !document.getElementById("detail").classList.contains("open"),
      "closeDetail closes the drawer");
    openDetail(EXP.headline.top1_key);
    const sheet = document.getElementById("detail-sheet");
    assert.ok(sheet.textContent.includes("Stevens"), "the drawer opens for the dirtiest member");
    assert.ok(
      sheet.textContent.includes(EXP.headline.top1_exact),
      "the drawer shows the dirtiest member's exact figure " + EXP.headline.top1_exact);
    closeDetail();

    downloadCsv(); // must not throw (Blob + object URL path)

    /* Escaping: text from the filings, or typed by a visitor, never
       becomes markup. */
    const hostile = '<img src=x onerror="globalThis.__injected=1">';
    const target = PEOPLE[0].person_key;
    BY_KEY[target].full_name = hostile;
    BY_KEY[target].data_notes = hostile;
    openDetail(target);
    assert.strictEqual(
      sheet.querySelectorAll("img").length, 0,
      "a name or data note holding markup renders as text in the drawer");
    assert.ok(sheet.innerHTML.includes("&lt;img src=x"), "the drawer shows the markup escaped");
    assert.strictEqual(globalThis.__injected, undefined, "no injected handler ran");
    closeDetail();

    return observed;
  },

  /* ---- Story: the payload agrees with the dataset, every step runs ---- */
  async story(EXP) {
    const data = loadStoryData();
    assert.ok(data, "the story payload parses");
    assert.strictEqual(
      data.hero.flagged, EXP.tiers.flag_120,
      "the hero flagged count is the dataset's incoming flag count");
    assert.strictEqual(
      data.hero.members, EXP.tiers.incoming_total,
      "the hero member count is the incoming 120th");
    assert.strictEqual(data.waffle.house.seats, 435, "the House waffle plots seats, not members");
    assert.strictEqual(data.waffle.senate.seats, 100, "the Senate waffle plots seats, not members");
    assert.strictEqual(
      data.targets_total, EXP.targets.balanced[0] + EXP.targets.balanced[1],
      "the targets total is the dataset's Balanced watchlist size");
    assert.ok(
      data.targets.length > 0 && data.targets.length <= data.targets_total,
      "the story shows the head of the targets list");
    assert.ok(
      document.body.textContent.includes(data.hero.dirty_total_rounded),
      "the hero shows the computed dirty total " + data.hero.dirty_total_rounded);
    const domSteps = [...document.querySelectorAll(".scrolly-step")].map(
      (el) => el.getAttribute("data-step"));
    assert.deepStrictEqual(domSteps, STORY_STEPS, "the story steps stand in the payload's order");
    for (const step of STORY_STEPS) {
      const card = document.getElementById("step-" + step);
      assert.ok(card && card.textContent.trim().length > 0, "the step card has text: " + step);
      setStoryStep(step); // every step renders without throwing
    }
  },

  reducedMotion(expected) {
    assert.strictEqual(
      storyReducedMotion(), expected,
      "the story's reduced-motion answer follows the OS preference");
  },
};
