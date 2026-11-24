/* Runtime smoke test: runs inside the built page in headless Chromium.
 * receipts/site/checks/runtime.py loads the page, then calls each phase;
 * EXP is what the page should show (receipts/site/expectations.py). */
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
// A real browser fires hashchange after the current task; wait for it.
const setHash = (value) => new Promise((resolve) => {
  const target = value === "" ? "" : "#" + String(value).replace(/^#/, "");
  if (location.hash === target) return resolve();
  window.addEventListener("hashchange", () => resolve(), { once: true });
  location.hash = value;
});

window.smoke = {
  async main(EXP) {

        observe("rows", PEOPLE.length);
        const TOP5 = EXP.headline.top5.map((x) => x[0]);
        const T28 = EXP.targets_2028;
        const seatLabel = (k) => k.charAt(0).toUpperCase() + k.slice(1);
        /* ---- FE7: hidden Explore does not render at load ---- */
        assert.strictEqual(
          document.getElementById("stats").innerHTML, "",
          "stats do not render at load on the front door");
        assert.strictEqual(
          document.querySelector("#main-table tbody").innerHTML, "",
          "table does not render at load on the front door");
        assert.strictEqual(
          document.getElementById("totals").innerHTML, "",
          "totals strip does not render at load on the front door");

        /* ---- front door (landing-first): dirtiest, clean story, default mode ---- */
        const headlineHtml = document.getElementById("dirtiest-headline").innerHTML;
        assert.ok(headlineHtml.includes(TOP5[0]), "headline leads with the dirtiest member: " + headlineHtml);
        assert.ok(headlineHtml.includes(EXP.headline.top1_compact), "headline shows #1's dirty 2026 " + EXP.headline.top1_compact);
        assert.strictEqual(headlineHtml.includes("next four combined"), EXP.headline.exceeds_next_four, "headline compares #1 to next four only if it holds");
        if (EXP.headline.exceeds_next_four) {
          assert.ok(headlineHtml.includes(EXP.headline.ratio), "headline ratio is " + EXP.headline.ratio + "x");
          assert.ok(headlineHtml.includes(EXP.headline.next_four_compact), "headline shows next-four total " + EXP.headline.next_four_compact);
        }

        /* ---- U6: one-line dirty definition under the hook ---- */
        const hookDef = document.getElementById("hook-definition").textContent;
        assert.ok(
          hookDef.includes("Dirty money is money from sources other than individual contributors"),
          "hook definition uses the explainer phrasing");
        assert.ok(
          hookDef.includes("over $100k and over 5% of receipts"),
          "hook definition states the Balanced rule");
        assert.ok(
          hookDef.includes("any AIPAC direct or UDP benefit dollar always counts"),
          "hook definition states the flag rule");
        const dirtiestHtml = document.getElementById("dirtiest-list").innerHTML;
        TOP5.forEach((n) =>
          assert.ok(dirtiestHtml.includes(n), "dirtiest list has " + n));
        assert.ok(
          TOP5.every((n, i) => i === 0 || dirtiestHtml.indexOf(TOP5[i - 1]) < dirtiestHtml.indexOf(n)),
          "dirtiest list is in dirty-2026 order");
        if (!EXP.headline.top1_returning) {
          assert.ok(dirtiestHtml.includes("Not returning"), "#1 row says Not returning");
        }
        assert.ok(dirtiestHtml.includes("pchip d"), "dirtiest rows carry party chips");
        assert.strictEqual(
          document.getElementById("front-door").hidden, false,
          "default mode is the front door (no hash)");
        assert.strictEqual(
          document.getElementById("main").hidden, true,
          "full-data workspace hidden in front-door mode");
        assert.strictEqual(
          document.getElementById("explore-head").hidden, true,
          "stat cards hidden in front-door mode");
        setMode("explore");
        assert.strictEqual(
          document.getElementById("front-door").hidden, true,
          "explore mode hides the front door");
        assert.strictEqual(
          document.getElementById("main").hidden, false,
          "explore mode shows the full-data workspace");
        /* ---- FE7: first entry into Explore renders the workspace ---- */
        const statsHtml = document.getElementById("stats").innerHTML;
        assert.ok(statsHtml.includes(String(PEOPLE.length)), "stats mention every person: " + statsHtml.slice(0, 120));
        assert.ok(statsHtml.includes(String(EXP.tiers.not_dirty_120.balanced)) && statsHtml.includes("not dirty"), "stats mention the Balanced not-dirty count");
        assert.strictEqual(
          document.querySelectorAll("#stats .stat").length, 3,
          "D7: Explore stats are 3 cards");
        assert.ok(statsHtml.includes("not judged"), "D7: third card is the combined not-judged card");
        assert.ok(statsHtml.includes("Elaine Luria"), "D7: not-judged card names the unverified member");
        const tbodyHtml = document.querySelector("#main-table tbody").innerHTML;
        assert.ok(tbodyHtml.includes("Warnock"), "default table contains Warnock");
        assert.ok(
          tbodyHtml.indexOf(TOP5[0]) < tbodyHtml.indexOf(TOP5[1]),
          "default sort is Dirty 2026 desc (#1 before #2)");
        assert.ok(
          document.getElementById("totals").innerHTML.includes("Total accepted"),
          "totals strip rendered");
        setPreset("strict");
        assert.ok(
          document.getElementById("hook-definition").textContent.includes("any dirty dollar counts"),
          "hook definition follows the Strict preset");
        setPreset("balanced");
        setMode("front");
        assert.strictEqual(
          document.getElementById("front-door").hidden, false,
          "back to front door");

        /* ---- U1: one return control — the masthead title links home ---- */
        assert.ok(document.getElementById("home-link"), "masthead title is a link");
        setMode("explore");
        document.getElementById("home-link").click();
        assert.strictEqual(
          document.getElementById("front-door").hidden, false,
          "home link returns to the front door");
        assert.strictEqual(
          document.activeElement, document.querySelector("header h1"),
          "returning to front focuses the masthead");
        setMode("explore");
        assert.strictEqual(
          document.activeElement, document.getElementById("tabs-nav"),
          "entering explore focuses the tab bar");
        showTab("leaders");
        assert.strictEqual(
          document.activeElement, document.getElementById("tab-leaders"),
          "switching tabs focuses the panel");
        assert.ok(
          document.querySelector("#main-table thead").innerHTML.includes("Outcome"),
          "core table has an Outcome column");

        showTab("leaders");
        const leadersHtml = document.getElementById("leaders").innerHTML;
        assert.ok(leadersHtml.includes("Top 20 — dirtiest in 2026"), "first board is dirtiest 2026");
        assert.ok(
          leadersHtml.indexOf("dirtiest in 2026") < leadersHtml.indexOf("dirtiest, career") &&
          leadersHtml.indexOf("dirtiest, career") < leadersHtml.indexOf("total accepted (career)"),
          "leaderboards lead with dirty, total accepted after");
        assert.ok(leadersHtml.includes(EXP.career_dirty.top1_exact), "career dirty board shows the #1 career figure");
        EXP.career_dirty.top3.forEach((n) =>
          assert.ok(leadersHtml.includes(n), "career dirty board has " + n));
        assert.ok(leadersHtml.includes("Warnock"), "leaderboard has Warnock");
        assert.ok(leadersHtml.includes("Stevens"), "UDP-benefit board has Stevens");
        assert.ok(leadersHtml.includes("Rick Scott"), "self-funding board has Rick Scott");
        assert.ok(leadersHtml.includes("Talarico"), "all-IE board has Talarico");

        /* ---- composition charts: House waffle grid, Senate state tiles ---- */
        const compHtml = document.getElementById("composition").innerHTML;
        assert.ok(compHtml.includes("House — 435 voting seats"), "House chart captioned 435");
        assert.ok(compHtml.includes("Senate — 100 seats"), "Senate chart captioned 100");
        const countDots = (html, cls, party) =>
          (html.match(new RegExp('<g class="dot ' + cls + '" data-party="' + party + '"', "g")) || []).length;
        // The House svg sits before its figcaption; the Senate svg sits after the
        // House figcaption and before its own, so split on the captions.
        const housePart = compHtml.split("House — 435 voting seats")[0];
        const senPart = compHtml.split("House — 435 voting seats")[1].split("Senate — 100 seats")[0];
        // House waffle: 15 rows x 29 cols, column-major fill, grouped
        // Clean D, Dirty D, Dirty R, Clean R, then the small categories.
        assert.ok(housePart.includes('viewBox="0 0 348 180"'), "House waffle is 29x15");
        assert.strictEqual((housePart.match(/<g class="dot/g) || []).length, 435, "House chart has 435 dots");
        assert.ok(housePart.indexOf('class="dot clean" data-party="D"') < housePart.indexOf('class="dot dirty" data-party="D"'), "waffle starts with Clean D");
        assert.ok(housePart.indexOf('class="dot dirty" data-party="D"') < housePart.indexOf('class="dot dirty" data-party="R"'), "waffle: Dirty D before Dirty R");
        assert.ok(housePart.indexOf('class="dot dirty" data-party="R"') < housePart.indexOf('class="dot clean" data-party="R"'), "waffle: Dirty R before Clean R");
        assert.ok(housePart.indexOf('class="dot clean" data-party="R"') < housePart.indexOf('class="dot uncalled"'), "waffle: small categories at the far right");
        Object.entries(EXP.charts.house).forEach(([k, n]) => {
          const [status, party] = k.split(" ");
          assert.strictEqual(countDots(housePart, status, party), n, "House " + seatLabel(k) + " " + n);
        });
        assert.strictEqual(countDots(housePart, "uncalled", ""), 435 - EXP.charts.house_named, "House Uncalled");
        // Senate state tiles: 50 tiles, one per state, two seat halves each.
        assert.strictEqual((senPart.match(/<g class="tile"/g) || []).length, 50, "Senate chart has 50 state tiles");
        assert.strictEqual((senPart.match(/class="half/g) || []).length, 100, "Senate chart has 100 seat halves");
        const countHalves = (html, cls, party) =>
          (html.match(new RegExp('class="half ' + cls + '" data-party="' + party + '"', "g")) || []).length;
        Object.entries(EXP.charts.senate).forEach(([k, n]) => {
          const [status, party] = k.split(" ");
          assert.strictEqual(countHalves(senPart, status, party), n, "Senate " + seatLabel(k) + " " + n);
        });
        assert.strictEqual(countHalves(senPart, "uncalled", ""), 100 - EXP.charts.senate_named, "Senate Uncalled");
        // Each state tile shows its senators' halves, plus an uncalled half per unnamed seat.
        const tileStatus = (p) => p.clean_2026 === true ? "clean" : p.clean_2026 === false ? "dirty"
          : (p.unopposed_2026 === true ? "unopposed" : "unverified");
        const tileParty = (p) => ({ Democrat: "D", Republican: "R", Independent: "I" }[p.party_120] || p.party_120);
        const senatorsByState = {};
        PEOPLE.filter((p) => p.in_120th === "yes" && p.chamber_120 === "Senate")
          .forEach((p) => (senatorsByState[p.state] = senatorsByState[p.state] || []).push(p));
        Object.entries(senatorsByState).forEach(([st, sens]) => {
          const tile = senPart.split('data-state="' + st + '"')[1].split('data-state="')[0];
          const want = {};
          sens.forEach((p) => {
            const k = 'class="half ' + tileStatus(p) + '" data-party="' + tileParty(p) + '"';
            want[k] = (want[k] || 0) + 1;
          });
          Object.entries(want).forEach(([k, n]) =>
            assert.strictEqual(tile.split(k).length - 1, n, st + " tile shows " + n + " x " + k));
          assert.strictEqual(tile.split('class="half uncalled"').length - 1, 2 - sens.length, st + " tile uncalled halves");
        });
        assert.ok(compHtml.includes("Dirty D " + EXP.charts.house["dirty D"]), "House legend shows the Dirty D count");
        assert.ok(compHtml.includes("Uncalled " + (435 - EXP.charts.house_named)), "House legend shows the Uncalled count");
        assert.ok(compHtml.includes("Dirty D " + EXP.charts.senate["dirty D"]), "Senate legend shows the Dirty D count");
        assert.ok(compHtml.includes("Not shown: " + Object.values(EXP.charts.delegates).reduce((a, b) => a + b, 0) + " non-voting delegates"), "delegate note present");
        Object.entries(EXP.charts.delegates).forEach(([k, n]) =>
          assert.ok(compHtml.includes(seatLabel(k) + " " + n), "delegate note shows " + seatLabel(k) + " " + n));
        assert.ok(compHtml.includes("visually-hidden"), "FE10: charts have a visually-hidden text alternative");
        assert.ok(compHtml.includes("House: 435 seats"), "FE10: text alternative states the House counts");
        const compDelays = [...compHtml.matchAll(/transition-delay:(\d+)ms/g)].map((m) => +m[1]);
        assert.ok(compDelays.length > 0, "FE10: chart stagger delays present");
        assert.ok(
          Math.max(...compDelays) <= 500,
          "FE10: chart stagger totals stay under ~500ms, max " + Math.max(...compDelays));

        /* ---- U4: charts carry person keys (clicks tested after FE1a,
         * because opening a drill-down decodes that person's lists) ---- */
        assert.ok(
          document.querySelector('#composition .dot[data-key]'),
          "U4: waffle dots carry a person key");
        assert.ok(
          document.querySelector('#composition .half[data-key]'),
          "U4: Senate tile halves carry a person key");

        showTab("clean");
        assert.ok(
          document.getElementById("clean-stats").innerHTML.includes(EXP.tiers.house_not_dirty_balanced[0] + " of " + EXP.tiers.house_not_dirty_balanced[1]),
          "clean stats show the House not-dirty count (Balanced)");
        assert.ok(
          document.querySelector("#clean-table tbody").innerHTML.includes("Constantino"),
          "clean table contains Constantino");

        showTab("breakdown");
        assert.ok(
          document.querySelector("#breakdown-table tbody").innerHTML.includes("Democrat"),
          "breakdown table has Democrat rows");

        showTab("targets");
        const targetsHtml = document.querySelector("#targets-table tbody").innerHTML;
        assert.ok(targetsHtml.includes("Boafo"), "targets table starts with Boafo");
        assert.ok(targetsHtml.includes("Bell"), "targets table contains Bell");

        /* ---- 2028 primary targets ---- */
        showTab("targets28");
        assert.strictEqual(
          document.getElementById("tab-targets28").hidden, false,
          "2028 tab is shown after showTab");
        assert.strictEqual(
          document.getElementById("tab-targets").hidden, true,
          "2026 tab hides when the 2028 tab is shown");
        const t28Intro = document.getElementById("targets28-intro").innerHTML;
        assert.ok(t28Intro.includes("A watchlist, not a prediction"), "2028 intro frames it as a watchlist");
        assert.ok(t28Intro.includes(T28.balanced[0] + " House Democrats"), "2028 intro counts the Balanced House targets");
        assert.ok(t28Intro.includes(T28.balanced[1] + " Democratic senators"), "2028 intro counts the Balanced Senate targets");
        const t28HouseHtml = document.querySelector("#targets28-house-table tbody").innerHTML;
        const [t28H1, t28H2] = T28.balanced_house_order;
        assert.ok(t28HouseHtml.includes(t28H1), "2028 House table starts with " + t28H1);
        assert.ok(
          t28HouseHtml.indexOf(t28H1) < t28HouseHtml.indexOf(t28H2),
          "2028 House table in dirty-2026 order");
        assert.ok(t28HouseHtml.includes(T28.balanced_house_top_dirty_exact), "2028 House table shows the top dirty 2026 figure");
        if (!EXP.headline.top1_returning) {
          assert.ok(t28HouseHtml.includes(TOP5[0]) === false, "2028 House table does not show the overall #1 (not in the 120th)");
        }
        const t28SenHtml = document.querySelector("#targets28-senate-table tbody").innerHTML;
        const t28Sen = T28.balanced_senate_order;
        t28Sen.forEach((n) => assert.ok(t28SenHtml.includes(n), "2028 Senate table has " + n));
        assert.ok(
          t28Sen.every((n, i) => i === 0 || t28SenHtml.indexOf(t28Sen[i - 1]) < t28SenHtml.indexOf(n)),
          "2028 Senate table in dirty-2026 order");
        assert.ok(t28SenHtml.includes(T28.balanced_senate_top_dirty_exact), "2028 Senate table shows the top dirty 2026 figure");
        assert.ok(t28SenHtml.includes(T28.balanced_senate_top_career_exact), "2028 Senate table shows the top member's dirty career");
        assert.ok(t28SenHtml.includes(" · Senate"), "2028 Senate rows show the seat");

        /* ---- tolerance preset switching (methodology §14) ---- */
        // Switching the preset recomputes the watchlist and the story live.
        setPreset("lenient");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.lenient[0] + " House Democrats"),
          "Lenient 2028 intro counts the House Democrats");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.lenient[1] + " Democratic senators"),
          "Lenient 2028 intro counts the Democratic senators");
        setPreset("strict");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.strict[0] + " House Democrats"),
          "Strict 2028 intro counts the House Democrats");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.strict[1] + " Democratic senators"),
          "Strict 2028 intro counts the Democratic senators");
        assert.ok(
          document.getElementById("landing-story").innerHTML.replace(/<[^>]+>/g, "").includes(EXP.clean.all_120 + " of " + EXP.tiers.incoming_total),
          "Strict story shows the verified-clean count of the incoming members");
        setPreset("balanced");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.balanced[0] + " House Democrats"),
          "Balanced 2028 intro counts the House Democrats");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.balanced[1] + " Democratic senators"),
          "Balanced 2028 intro counts the Democratic senators");

        /* ---- FE1a: nested lists decode lazily ----
           Must run before the first openDetail / CSV export below, which
           decode the people they touch. */
        const lazyPerson = PEOPLE.find(p=>p.per_cycle.length && Array.isArray(p.per_cycle[0]));
        assert.ok(lazyPerson, "a person with undecoded nested lists exists");
        assert.ok(
          PEOPLE.every(p=>!p.per_cycle.length || Array.isArray(p.per_cycle[0])),
          "no nested list is decoded at load");
        openDetail(lazyPerson.person_key);
        assert.ok(
          lazyPerson.per_cycle.length && !Array.isArray(lazyPerson.per_cycle[0])
            && typeof lazyPerson.per_cycle[0].cycle === "number",
          "opening the detail decodes that person's nested lists");
        assert.ok(
          PEOPLE.some(p=>p!==lazyPerson && p.per_cycle.length && Array.isArray(p.per_cycle[0])),
          "other people's nested lists stay undecoded");
        closeDetail();

        const constKey = PEOPLE.find((p) => p.full_name.includes("Constantino")).person_key;
        openDetail(constKey);
        const detailHtml = document.getElementById("detail-sheet").innerHTML;
        assert.ok(detailHtml.includes(EXP.detail.constantino_self_funding_exact), "Constantino detail shows his career self-funding");
        assert.ok(detailHtml.includes("Self-funding"), "detail has self-funding section");
        assert.ok(detailHtml.includes("Cycle by cycle"), "detail has cycle tables");
        assert.ok(detailHtml.includes('class="detail-head"'), "D6/FE3: detail header shows exact figures");
        assert.ok(detailHtml.includes("Dirty 2026"), "D6/FE3: detail header names Dirty 2026");
        const detailCycles = document.querySelectorAll("#detail-sheet details.cycle");
        assert.ok(detailCycles.length >= 2, "D9: cycle tables collapse into details elements, got " + detailCycles.length);
        assert.ok(detailCycles[0].hasAttribute("open"), "D9: first cycle table is open");
        assert.ok(!detailCycles[1].hasAttribute("open"), "D9: later cycle tables start closed");
        closeDetail();

        const stevensKey = PEOPLE.find((p) => p.full_name.includes("Stevens")).person_key;
        openDetail(stevensKey);
        const stevensHtml = document.getElementById("detail-sheet").innerHTML;
        assert.ok(
          stevensHtml.includes("UDP opposition credit by race"),
          "Stevens detail shows opposition credit by race");
        assert.ok(stevensHtml.includes("Primary"), "Stevens detail shows the phase");
        EXP.detail.top1_opposition_credit_exact.forEach((amt) =>
          assert.ok(stevensHtml.includes(amt), "#1's detail shows the race-phase credit " + amt));
        assert.ok(
          stevensHtml.includes("pchip d") && stevensHtml.includes("Not returning"),
          "Stevens drill-down header has the D chip and Not returning");
        closeDetail();

        /* ---- U4: clicking a chart opens the drill-down ---- */
        document.querySelector('#composition .dot[data-key]').dispatchEvent("click");
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("Dirty 2026"),
          "U4: clicking a waffle dot opens the drill-down");
        closeDetail();
        document.querySelector('#composition .half[data-key]').dispatchEvent("click");
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("Dirty 2026"),
          "U4: clicking a Senate tile half opens the drill-down");
        closeDetail();

        downloadCsv(); // must not throw (Blob + object URL path)

        /* ---- landing story + finder (Change 1) ---- */
        const incoming120 = PEOPLE.filter((p) => p.in_120th === "yes");
        const notDirty120 = incoming120.filter(
          (p) => p.tier_balanced_2026 === "clean" || p.tier_balanced_2026 === "below_threshold").length;
        const storyHtml = document.getElementById("landing-story").innerHTML;
        // The counts are count-up spans now, so strip tags before matching.
        const storyText = storyHtml.replace(/<[^>]+>/g, "");
        assert.ok(
          storyText.includes(notDirty120 + " of " + incoming120.length),
          "story renders the computed Balanced not-dirty count: " + storyHtml);
        assert.ok(storyText.includes("Balanced tolerance"), "story labels the tolerance");
        assert.ok(storyHtml.includes("story-clean-link"), "story links to the clean list");
        assert.ok(storyHtml.includes("big-number"), "D3: clean story count uses the big-number treatment");
        const findStateHtml = document.getElementById("find-state").innerHTML;
        assert.ok(findStateHtml.includes("Michigan"), "finder state list has Michigan");
        assert.ok(findStateHtml.includes("American Samoa"), "finder state list has American Samoa");
        assert.strictEqual(finderSeats("MI")[0].value, "senate", "MI first seat is Senate");
        observe("finder_mi_house_seats", finderSeats("MI").filter((s) => s.value !== "senate").length);
        assert.deepStrictEqual(
          finderSeats("MP").map((s) => s.label), ["At-large — Delegate"],
          "MP is a delegate seat, no Senate");
        assert.deepStrictEqual(
          finderSeats("PR").map((s) => s.label), ["At-large — Resident Commissioner"],
          "PR is a Resident Commissioner seat");
        assert.strictEqual(
          finderPeople("MI", "11")[0].full_name, "Jeremy Moss", "MI-11 is Moss");
        assert.strictEqual(finderPeople("MI", "senate").length, 2, "MI has two senators");
        const elSayedKey = PEOPLE.find((p) => p.full_name.includes("El-Sayed")).person_key;
        findPerson(elSayedKey);
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("El-Sayed"),
          "finder opens the El-Sayed drill-down");
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("Won"),
          "El-Sayed drill-down header says Won");
        assert.strictEqual(
          document.getElementById("q").value, "Abdul El-Sayed",
          "finder sets the search box to the person");
        closeDetail();

        /* ---- U2: finder handoff lands in Explore on the Tracker tab ---- */
        setMode("front");
        findPerson(elSayedKey);
        assert.strictEqual(
          document.getElementById("front-door").hidden, true,
          "finder handoff hides the front door");
        assert.strictEqual(
          document.getElementById("main").hidden, false,
          "finder handoff shows Explore");
        assert.strictEqual(
          document.getElementById("tab-tracker").hidden, false,
          "finder handoff lands on the Tracker tab");
        assert.ok(
          document.getElementById("filter-chips").innerHTML.includes("Abdul El-Sayed"),
          "finder filters show as chips");
        assert.ok(
          document.getElementById("filter-chips").innerHTML.includes("Reset filters"),
          "chips carry a Reset button");
        closeDetail();
        document.getElementById("filters-reset").click();
        assert.strictEqual(
          document.getElementById("q").value, "",
          "Reset clears the search box");
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
          "Reset restores all all rows");
        assert.strictEqual(
          document.getElementById("filter-chips").innerHTML, "",
          "Reset clears the chips");

        /* ---- finder result buttons carry party chips + outcome ---- */
        const finderState = document.getElementById("find-state");
        finderState.value = "MI";
        finderState.dispatchEvent("change");
        const district = document.getElementById("find-district");
        district.value = "11";
        district.dispatchEvent("change");
        const finderPersonHtml = document.getElementById("find-person").innerHTML;
        assert.ok(finderPersonHtml.includes("Jeremy Moss"), "MI-11 finder result is Moss");
        assert.ok(finderPersonHtml.includes("pchip d"), "finder result has the D chip");
        assert.ok(finderPersonHtml.includes("Won"), "finder result says Won");

        /* ---- scrollytelling: chapters, count-ups, stagger ---- */
        // Chapter order is in the static template.
        const chapterOrder = [...document.querySelectorAll("[data-chapter]")].map((el) => el.dataset.chapter);
        assert.deepStrictEqual(
          chapterOrder,
          ["hook", "dirtiest", "dirty-definition", "clean", "chamber", "finder", "data"],
          "front door chapters in narrative order: " + chapterOrder.join(","));
        // Count-up spans: data-value is the computed figure. With no
        // IntersectionObserver (smoke_prelude.js) reveals run at once.
        const stevens = PEOPLE.find((p) => p.full_name.includes("Stevens"));
        // runCountUp adds data-counted, so the patterns allow later attributes.
        const hookCountups = [...headlineHtml.matchAll(/<span class="countup" data-value="([\d.]+)" data-format="([^"]+)"[^>]*>([^<]+)<\/span>/g)];
        assert.ok(hookCountups.length === 2, "hook has two count-up spans, got " + hookCountups.length);
        assert.strictEqual(parseFloat(hookCountups[0][1]), stevens.dirty_2026, "hook count-up targets Stevens dirty 2026");
        assert.strictEqual(hookCountups[0][3], EXP.headline.top1_compact, "hook count-up shows #1's compact figure");
        const dirtyTop5 = PEOPLE.filter((p) => typeof p.dirty_2026 === "number")
          .sort((a, b) => b.dirty_2026 - a.dirty_2026).slice(0, 5);
        const nextFour = dirtyTop5.slice(1).reduce((s, p) => s + p.dirty_2026, 0);
        assert.strictEqual(parseFloat(hookCountups[1][1]), nextFour, "hook count-up targets the next-four total");
        assert.strictEqual(hookCountups[1][3], EXP.headline.next_four_compact, "hook count-up shows the next-four total");
        const storyCountups = [...storyHtml.matchAll(/<span class="countup" data-value="(\d+)" data-format="int"[^>]*>(\d+)<\/span>/g)].map((m) => m[1]);
        assert.deepStrictEqual(storyCountups, [String(notDirty120), String(incoming120.length)], "story count-ups are the not-dirty and incoming counts");
        // Dirty explainer: big number counts up to the career dirty total;
        // the three components sum to it exactly.
        const explainerHtml = document.getElementById("dirty-explainer").innerHTML;
        const dcTotal = PEOPLE.reduce((s, p) => s + (typeof p.dirty_career === "number" ? p.dirty_career : 0), 0);
        assert.ok(explainerHtml.includes(EXP.career_dirty.total_compact), "explainer shows the career dirty total");
        const explainerCountup = explainerHtml.match(/<span class="countup" data-value="([\d.]+)" data-format="compact"[^>]*>([^<]+)<\/span>/);
        assert.ok(explainerCountup, "explainer has a count-up span");
        assert.strictEqual(parseFloat(explainerCountup[1]), dcTotal, "explainer count-up targets the computed career dirty total");
        assert.strictEqual(explainerCountup[2], EXP.career_dirty.total_compact, "explainer count-up shows the career dirty total");
        assert.ok(explainerHtml.includes("Individual contributions are <b>not</b> dirty money"), "explainer says individual contributions are not dirty");
        const dcParts = ["corporate_pac_career", "aipac_pac_direct_career", "udp_ie_total_benefit_career"]
          .reduce((s, k) => s + PEOPLE.reduce((a, p) => a + (typeof p[k] === "number" ? p[k] : 0), 0), 0);
        assert.ok(Math.abs(dcParts - dcTotal) < 0.01, "explainer components sum to the career dirty total");
        // Stagger: waffle dots carry per-column delays, senate tiles per-tile.
        assert.ok(housePart.includes("transition-delay"), "waffle dots stagger by column");
        assert.ok(senPart.includes("transition-delay"), "senate tiles stagger");
        assert.ok(dirtiestHtml.includes("transition-delay"), "dirtiest rows stagger");

        /* ---- handler coverage ----
         * findPerson (above) left the search box and the congress filter
         * set, so reset the filters first. */
        function resetFilters() {
          // Only dispatch for controls whose value actually changed: every
          // dispatch re-renders the whole table, so no-op dispatches are
          // pure cost (findPerson only moves q and f-congress off default).
          const q = document.getElementById("q");
          if (q.value !== "") { q.value = ""; q.dispatchEvent("input"); }
          for (const [id, val] of [["f-congress", "all"], ["f-chamber", "all"],
              ["f-party", "all"], ["f-state", "all"]]) {
            const sel = document.getElementById(id);
            if (sel.value !== val) { sel.value = val; sel.dispatchEvent("change"); }
          }
          for (const id of ["f-leader", "f-clean"]) {
            const cb = document.getElementById(id);
            if (cb.checked !== false) { cb.checked = false; cb.dispatchEvent("change"); }
          }
        }
        resetFilters();
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
          "reset filters restore all rows");
        assert.ok(
          document.getElementById("showing").textContent.includes("Showing " + PEOPLE.length + " of " + PEOPLE.length),
          "showing line counts every row");

        const hasClick = (el) => (el.__listeners?.click || 0) >= 1;
        const hasListener = (el, type) => (el.__listeners?.[type] || 0) >= 1;
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
          "querySelectorAll finds every table row");
        assert.strictEqual(
          document.querySelectorAll(".chapter").length, 7,
          "querySelectorAll finds all 7 chapters");
        assert.strictEqual(
          document.querySelectorAll("#dirtiest-list .dirty-row").length, 5,
          "querySelectorAll finds the 5 dirtiest rows");
        assert.strictEqual(
          document.querySelectorAll(".tabs button").length, 7,
          "querySelectorAll finds all 7 tab buttons");
        // Listeners the page attaches at render/init time.
        const sortHeaders = document.querySelectorAll("#main-table thead th[data-sort]");
        assert.ok(sortHeaders.length >= 1, "sortable headers exist");
        assert.ok(sortHeaders.every(hasClick), "every sortable header has a click listener");
        assert.ok(
          hasListener(document.querySelector("#main-table tbody"), "click"),
          "table body has one delegated click listener (FE2)");
        assert.ok(
          !document.querySelectorAll("#main-table tbody tr").some(hasClick),
          "no table row carries a listener of its own (FE2)");
        assert.ok(
          document.querySelectorAll("#viewbtns button").every(hasClick),
          "every view button has a click listener");
        assert.ok(
          document.querySelectorAll(".tabs button").every(hasClick),
          "every tab button has a click listener");
        assert.ok(
          document.querySelectorAll("#dirtiest-list .dirty-row").every(hasClick),
          "every dirtiest row has a click listener");
        assert.ok(
          document.querySelectorAll("#targets-table tbody tr").every(hasClick),
          "every 2026 targets row has a click listener");
        assert.ok(
          document.querySelectorAll("#targets28-house-table tbody tr").every(hasClick),
          "every 2028 House targets row has a click listener");
        assert.ok(
          document.querySelectorAll("#targets28-senate-table tbody tr").every(hasClick),
          "every 2028 Senate targets row has a click listener");
        assert.ok(hasClick(document.getElementById("story-clean-link")), "story clean link has a click listener");
        assert.ok(hasClick(document.getElementById("explore-btn")), "explore button has a click listener");
        assert.ok(hasClick(document.getElementById("targets28-btn")), "2028 button has a click listener");
        assert.ok(hasClick(document.getElementById("csv-btn")), "CSV button has a click listener");
        assert.ok(hasListener(document.getElementById("q"), "input"), "search box has an input listener");
        for (const id of ["f-congress", "f-chamber", "f-party", "f-state", "f-tolerance", "f-leader", "f-clean"]) {
          assert.ok(hasListener(document.getElementById(id), "change"), id + " has a change listener");
        }
        assert.ok(hasListener(document.getElementById("find-state"), "change"), "finder state select has a change listener");
        assert.ok(hasListener(document.getElementById("find-district"), "change"), "finder district select has a change listener");
        assert.ok(hasClick(document.getElementById("detail")), "detail backdrop has a click listener");
        assert.ok(hasListener(document, "keydown"), "document has a keydown listener (Escape closes the detail)");
        // U3: leaderboards are clickable — one delegated listener on
        // #leaders, rows are buttons that open the drill-down.
        assert.ok(hasClick(document.getElementById("leaders")), "leaderboards container has a delegated click listener");
        const leaderBtn = document.querySelector("#leaders .leader-row");
        assert.ok(leaderBtn, "leaderboard rows are buttons");
        leaderBtn.click();
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("Stevens"),
          "clicking a leaderboard row opens the Stevens drill-down");
        closeDetail();

        /* ---- tab buttons switch tabs ---- */
        document.querySelector('.tabs button[data-tab="clean"]').dispatchEvent("click");
        assert.strictEqual(
          document.getElementById("tab-clean").hidden, false,
          "clicking the Clean tab shows it");
        assert.strictEqual(
          document.getElementById("tab-tracker").hidden, true,
          "clicking the Clean tab hides the tracker");
        assert.ok(
          document.getElementById("clean-stats").innerHTML.includes(EXP.tiers.house_not_dirty_balanced[0] + " of " + EXP.tiers.house_not_dirty_balanced[1]),
          "Clean tab renders after a click");
        document.querySelector('.tabs button[data-tab="tracker"]').dispatchEvent("click");
        assert.strictEqual(
          document.getElementById("tab-tracker").hidden, false,
          "clicking the Tracker tab shows it again");

        /* ---- view buttons switch column sets ---- */
        document.querySelector('#viewbtns button[data-view="y2026"]').dispatchEvent("click");
        assert.ok(
          document.querySelector("#main-table thead").innerHTML.includes("Individual 2026"),
          "view button switches to the 2026 columns");
        assert.strictEqual(
          document.querySelector('#viewbtns button[data-view="y2026"]').getAttribute("aria-pressed"), "true",
          "active view button is aria-pressed");
        document.querySelector('#viewbtns button[data-view="core"]').dispatchEvent("click");
        assert.ok(
          document.querySelector("#main-table thead").innerHTML.includes("Outcome"),
          "view button switches back to the core columns");

        /* ---- clicking a table row opens the detail sheet ----
         * The first click lands on a cell, so it only reaches the row's
         * listener by bubbling. */
        const firstRow = document.querySelector("#main-table tbody tr");
        const firstCell = firstRow.children[0];
        assert.ok(firstCell.textContent.includes("Stevens"), "first row is Stevens before the click test");
        firstCell.dispatchEvent("click");
        assert.ok(
          document.getElementById("detail").classList.contains("open"),
          "clicking a table row opens the detail sheet");
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("Stevens"),
          "row click opens the Stevens drill-down");
        document.getElementById("detail-close").dispatchEvent("click");
        assert.ok(
          !document.getElementById("detail").classList.contains("open"),
          "detail-close button closes the sheet");
        firstRow.dispatchEvent("click");
        assert.ok(
          document.getElementById("detail").classList.contains("open"),
          "clicking the row itself reopens the sheet");
        document.getElementById("detail-sheet").dispatchEvent("click");
        assert.ok(
          document.getElementById("detail").classList.contains("open"),
          "clicking inside the sheet does not close it");
        document.getElementById("detail").dispatchEvent("click");
        assert.ok(
          !document.getElementById("detail").classList.contains("open"),
          "clicking the backdrop closes the sheet");
        firstRow.dispatchEvent("click");
        document.dispatchEvent("keydown", { key: "Escape" });
        assert.ok(
          !document.getElementById("detail").classList.contains("open"),
          "Escape closes the sheet");

        /* ---- sort headers re-sort ---- */
        const sortTh = () => document.querySelector('#main-table thead th[data-sort="dirty_2026"]');
        const firstRowName = () => document.querySelector("#main-table tbody tr").children[0].textContent;
        assert.ok(firstRowName().includes("Stevens"), "default first row is Stevens");
        sortTh().dispatchEvent("click"); // toggles to ascending
        const minDirty = PEOPLE.filter((p) => typeof p.dirty_2026 === "number")
          .sort((a, b) => a.dirty_2026 - b.dirty_2026 || a.full_name.localeCompare(b.full_name))[0];
        assert.strictEqual(
          firstRowName(), minDirty.full_name,
          "sort header click re-sorts ascending: first row is " + minDirty.full_name);
        sortTh().dispatchEvent("click"); // back to descending
        assert.ok(firstRowName().includes("Stevens"), "sort header click again restores descending");

        /* ---- FE4: keyboard / screen-reader access ---- */
        const nameBtn = document.querySelector("#main-table tbody tr .name-btn");
        assert.ok(nameBtn, "name cells are buttons");
        assert.strictEqual(
          document.querySelector('#main-table thead th[data-sort="dirty_2026"]').getAttribute("aria-sort"),
          "descending",
          "sorted column announces descending");
        nameBtn.focus();
        nameBtn.click(); // bubbles to the row -> openDetail
        assert.strictEqual(
          document.activeElement, document.getElementById("detail-close"),
          "opening the detail focuses Close");
        document.getElementById("detail").dispatchEvent("keydown", { key: "Tab" });
        assert.strictEqual(
          document.activeElement, document.getElementById("detail-close"),
          "Tab cycles within the sheet (only Close is focusable)");
        closeDetail();
        assert.strictEqual(
          document.activeElement, nameBtn,
          "closing the detail restores focus to the opener");

        /* ---- filter select re-renders ---- */
        const partySel = document.getElementById("f-party");
        partySel.value = "Democrat";
        partySel.dispatchEvent("change");
        const demCount = PEOPLE.filter((p) => p.party_119 === "Democrat" || p.party_120 === "Democrat").length;
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, demCount,
          "party filter re-renders to " + demCount + " Democrats");
        assert.strictEqual(
          document.getElementById("csv-btn").textContent,
          "Download CSV — " + demCount + " rows",
          "CSV button is labelled with the filtered row count");
        partySel.value = "all";
        partySel.dispatchEvent("change");
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
          "party filter reset restores all rows");
        assert.strictEqual(
          document.getElementById("csv-btn").textContent,
          "Download CSV — " + PEOPLE.length + " rows",
          "CSV button label follows the reset");

        /* ---- U7: leadership filter excludes TBD (would return everyone) ---- */
        assert.ok(
          document.querySelector("#f-leader").parentNode.textContent.includes("Leadership (119th; 120th TBD)"),
          "leadership filter is labeled 119th; 120th TBD");
        const leaderBox = document.getElementById("f-leader");
        const leaderCount = PEOPLE.filter(
          (p) => p.leadership_119 || (p.leadership_120 && p.leadership_120 !== "TBD")).length;
        leaderBox.checked = true;
        leaderBox.dispatchEvent("change");
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, leaderCount,
          "leadership filter returns the " + leaderCount + " 119th leaders, not every row");
        assert.ok(
          document.getElementById("filter-chips").innerHTML.includes("Leadership (119th; 120th TBD)"),
          "leadership filter shows as a chip");
        leaderBox.checked = false;
        leaderBox.dispatchEvent("change");
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
          "leadership filter reset restores all rows");

        /* ---- D8: filters in two labelled rows, tab bar scrolls ---- */
        assert.strictEqual(
          document.querySelectorAll(".controls-row").length, 2,
          "D8: Tracker filters sit in two labelled rows");
        assert.ok(
          document.querySelector(".controls-row .controls-label").textContent.includes("Filter"),
          "D8: first filter row is labelled Filter");

        /* ---- tolerance select re-renders (targets28 tab must be showing) ---- */
        document.querySelector('.tabs button[data-tab="targets28"]').dispatchEvent("click");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.balanced[0] + " House Democrats"),
          "targets28 tab click shows the Balanced intro");
        const tolSel = document.getElementById("f-tolerance");
        tolSel.value = "strict";
        tolSel.dispatchEvent("change");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.strict[0] + " House Democrats"),
          "tolerance select change to Strict recomputes the watchlist");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.strict[1] + " Democratic senators"),
          "Strict intro counts the senators");
        tolSel.value = "balanced";
        tolSel.dispatchEvent("change");
        assert.ok(
          document.getElementById("targets28-intro").innerHTML.includes(T28.balanced[0] + " House Democrats"),
          "tolerance select change back to Balanced restores the Balanced count");
        document.querySelector('.tabs button[data-tab="tracker"]').dispatchEvent("click");

        /* ---- D6/FE3: compact/exact money toggle (persisted, Compact default) ---- */
        const moneySel = document.getElementById("f-money");
        assert.strictEqual(moneySel.value, "compact", "money toggle defaults to Compact");
        const dirtyCell = document.querySelector("#main-table tbody tr").children[11];
        assert.strictEqual(dirtyCell.textContent, EXP.headline.top1_compact, "money shows compact by default");
        moneySel.value = "exact";
        moneySel.dispatchEvent("change");
        assert.strictEqual(
          document.querySelector("#main-table tbody tr").children[11].textContent,
          EXP.headline.top1_exact, "money toggle to Exact shows dollars and cents");
        moneySel.value = "compact";
        moneySel.dispatchEvent("change");
        assert.strictEqual(
          document.querySelector("#main-table tbody tr").children[11].textContent,
          EXP.headline.top1_compact, "money toggle back to Compact restores the short form");

        /* ---- finder, driven by dispatched change/click events ---- */
        const findStateSel = document.getElementById("find-state");
        findStateSel.value = "MI";
        findStateSel.dispatchEvent("change");
        const findDistSel = document.getElementById("find-district");
        assert.strictEqual(findDistSel.disabled, false, "finder enables the district select after a state change");
        assert.ok(findDistSel.innerHTML.includes("District 11"), "finder lists MI districts after a state change");
        findDistSel.value = "11";
        findDistSel.dispatchEvent("change");
        assert.ok(
          document.getElementById("find-person").innerHTML.includes("Jeremy Moss"),
          "finder district change lists MI-11 Moss");
        document.querySelector("#find-person button").dispatchEvent("click");
        assert.ok(
          document.getElementById("detail-sheet").innerHTML.includes("Jeremy Moss"),
          "finder person button opens the drill-down");
        assert.strictEqual(
          document.getElementById("q").value, "Jeremy Moss",
          "finder person button sets the search box");
        closeDetail();
        resetFilters(); // findPerson left the table filtered to one person + 120th
        assert.strictEqual(
          document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
          "reset after the finder restores all rows");

        /* ---- front-door buttons + hash routing ---- */
        setMode("front");
        assert.strictEqual(document.getElementById("front-door").hidden, false, "back on the front door");
        document.getElementById("explore-btn").dispatchEvent("click");
        assert.strictEqual(document.getElementById("front-door").hidden, true, "explore button leaves the front door");
        assert.strictEqual(document.getElementById("main").hidden, false, "explore button shows the workspace");
        setMode("front");
        document.getElementById("targets28-btn").dispatchEvent("click");
        assert.strictEqual(document.getElementById("tab-targets28").hidden, false, "2028 button opens the 2028 tab");
        assert.strictEqual(document.getElementById("front-door").hidden, true, "2028 button leaves the front door");
        // Setting location.hash fires hashchange, which the page listens for.
        setMode("front");
        await setHash("explore");
        assert.strictEqual(location.hash, "#explore", "location.hash stores the hash with its #");
        assert.strictEqual(document.getElementById("front-door").hidden, true, "hashchange to #explore opens explore mode");
        await setHash("");
        assert.strictEqual(document.getElementById("front-door").hidden, false, "hashchange back to empty shows the front door");

        /* ---- U5: skip link jumps to the data ---- */
        assert.ok(document.getElementById("skip-link"), "U5: skip link exists");
        document.getElementById("skip-link").dispatchEvent("click");
        assert.strictEqual(document.getElementById("front-door").hidden, true, "U5: skip link leaves the front door");
        assert.strictEqual(document.getElementById("main").hidden, false, "U5: skip link shows the workspace");
        setMode("front");

        /* ---- FE5: the hash carries the whole view (Change 2) ---- */
        setMode("explore");
        const partySelFE5 = document.getElementById("f-party");
        partySelFE5.value = "Democrat";
        partySelFE5.dispatchEvent("change");
        assert.ok(location.hash.includes("party=Democrat"), "FE5: party filter lands in the hash: " + location.hash);
        await setHash("explore?party=Republican");
        assert.strictEqual(document.getElementById("f-party").value, "Republican", "FE5: hash restores the party filter");
        await setHash("explore");
        assert.strictEqual(document.getElementById("f-party").value, "all", "FE5: bare #explore resets the filters");
        document.querySelector('.tabs button[data-tab="clean"]').dispatchEvent("click");
        assert.ok(location.hash.includes("tab=clean"), "FE5: tab lands in the hash: " + location.hash);
        await setHash("explore?tab=leaders");
        assert.strictEqual(document.getElementById("tab-leaders").hidden, false, "FE5: hash restores the tab");
        await setHash("explore");
        // The first tracker row is the dirtiest in 2026 (Stevens): open it.
        document.querySelector("#main-table tbody tr").dispatchEvent("click");
        assert.ok(location.hash.includes("detail="), "FE5: open drill-down lands in the hash: " + location.hash);
        assert.strictEqual(document.getElementById("detail").classList.contains("open"), true, "FE5: drill-down is open");
        await setHash("explore");
        assert.strictEqual(document.getElementById("detail").classList.contains("open"), false, "FE5: hash back to explore closes the drill-down");
        await setHash("detail=" + document.querySelector("#main-table tbody tr").getAttribute("data-key"));
        assert.strictEqual(document.getElementById("detail").classList.contains("open"), true, "FE5: direct detail link opens the sheet");
        assert.strictEqual(document.getElementById("front-door").hidden, false, "FE5: direct detail link stays on the front door");
        closeDetail();
        setMode("front");

        /* ---- U10: prev/next, anchor nav, View in Tracker ---- */
        setMode("explore");
        // The first tracker row is Stevens (dirtiest 2026): prev disabled, next live.
        document.querySelector("#main-table tbody tr").dispatchEvent("click");
        assert.strictEqual(document.getElementById("detail-prev").disabled, true, "U10: prev disabled on the first row");
        assert.strictEqual(document.getElementById("detail-next").disabled, false, "U10: next enabled on the first row");
        document.getElementById("detail-next").dispatchEvent("click");
        assert.ok(document.getElementById("detail-sheet").innerHTML.includes("Boafo"), "U10: next opens the second row (Boafo)");
        assert.ok(location.hash.includes("detail="), "U10: prev/next keeps the detail in the hash");
        assert.strictEqual(document.getElementById("detail-prev").disabled, false, "U10: prev enabled after stepping forward");
        // Anchor nav: the 2026 section takes focus.
        document.querySelector('[data-anchor="sec-2026"]').dispatchEvent("click");
        assert.strictEqual(document.activeElement && document.activeElement.id, "sec-2026", "U10: anchor moves focus to the 2026 section");
        // View in Tracker: sheet closes, Tracker tab shows only this person.
        document.getElementById("detail-tracker").dispatchEvent("click");
        assert.strictEqual(document.getElementById("detail").classList.contains("open"), false, "U10: View in Tracker closes the sheet");
        assert.strictEqual(document.getElementById("tab-tracker").hidden, false, "U10: View in Tracker shows the Tracker tab");
        assert.strictEqual(document.getElementById("q").value, "Adrian Boafo", "U10: View in Tracker filters to the person");
        assert.strictEqual(document.querySelectorAll("#main-table tbody tr").length, 1, "U10: filtered table has exactly the person");
        document.getElementById("filters-reset").dispatchEvent("click"); // the Reset chip runs the page's resetFilters (synchronous render)
        assert.strictEqual(document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length, "U10: reset restores all rows");
        setMode("front");

        /* ---- U1 leftovers: sticky tab bar + finder in Explore ---- */
        setMode("explore");
        assert.strictEqual(document.getElementById("finder").parentNode.id, "finder-slot", "U1: entering Explore moves the finder into the slot");
        // The finder still works after the move: its listeners survive it.
        const findStateU1 = document.getElementById("find-state");
        findStateU1.value = "MI";
        findStateU1.dispatchEvent("change");
        assert.strictEqual(document.getElementById("find-district").disabled, false, "U1: finder in the slot enables districts after a state change");
        assert.ok(document.getElementById("find-district").innerHTML.includes("District 11"), "U1: finder in the slot lists MI districts");
        setMode("front");
        assert.strictEqual(document.getElementById("finder").parentNode.getAttribute("data-chapter"), "finder", "U1: returning home moves the finder back to its chapter");

        /* ---- bubbling + closest() (what FE2's delegated tbody listener
         * and U4's delegated chart listener will rely on) ---- */
        const tbodyEl = document.querySelector("#main-table tbody");
        let bubbledTarget = null;
        const probe = (e) => { bubbledTarget = e.target; };
        tbodyEl.addEventListener("click", probe);
        const probeRow = document.querySelector("#main-table tbody tr");
        const probeCell = probeRow.children[1];
        probeCell.dispatchEvent("click"); // bubbles cell -> row (opens detail) -> tbody (probe)
        assert.strictEqual(bubbledTarget, probeCell, "click on a cell bubbles to tbody with target = the cell");
        assert.strictEqual(probeCell.closest("tr"), probeRow, "closest(tr) finds the row");
        assert.strictEqual(probeCell.closest("tbody"), tbodyEl, "closest(tbody) finds the body");
        assert.strictEqual(probeCell.closest("td"), probeCell, "closest includes the element itself");
        assert.strictEqual(probeCell.closest(".does-not-exist"), null, "closest returns null with no match");
        tbodyEl.removeEventListener("click", probe);
        closeDetail();

        /* ---- search input (debounce-tolerant) ----
         * The FE2 wave debounces the search input (~150ms) around
         * renderTable, so this assertion waits instead of expecting a
         * synchronous re-render right after dispatching 'input'. */
          await sleep(50); // let hashchanges the page queued earlier settle first
        const searchBox = document.getElementById("q");
          // FE2: search is debounced ~150ms — no re-render before the delay.
          searchBox.value = "Warnock";
          searchBox.dispatchEvent("input");
          assert.strictEqual(
            document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
            "search waits for the debounce before re-rendering");
          await sleep(250);
          assert.strictEqual(
            document.querySelectorAll("#main-table tbody tr").length, 1,
            "search filters the table to one row for Warnock");
          assert.ok(
            document.querySelector("#main-table tbody").innerHTML.includes("Warnock"),
            "search result is Warnock");
          searchBox.value = "";
          searchBox.dispatchEvent("input");
          await sleep(250);
          assert.strictEqual(
            document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
            "clearing the search restores all rows");
          assert.ok(
            document.getElementById("showing").textContent.includes("Showing " + PEOPLE.length + " of " + PEOPLE.length),
            "showing line counts every row after clearing the search");

          /* ---- U8: search matches state, district, party, chamber ---- */
          searchBox.value = "michigan";
          searchBox.dispatchEvent("input");
          await sleep(250);
          observe("search_michigan", document.querySelectorAll("#main-table tbody tr").length);
          searchBox.value = "11";
          searchBox.dispatchEvent("input");
          await sleep(250);
          observe("search_district_11", document.querySelectorAll("#main-table tbody tr").length);
          searchBox.value = "senate";
          searchBox.dispatchEvent("input");
          await sleep(250);
          observe("search_senate", document.querySelectorAll("#main-table tbody tr").length);
          // Relevance: a name match outranks a state match.
          searchBox.value = "mi";
          searchBox.dispatchEvent("input");
          await sleep(250);
          observe("search_mi", document.querySelectorAll("#main-table tbody tr").length);
          assert.ok(
            document.querySelector("#main-table tbody tr td").textContent.includes("Mike Johnson"),
            "relevance ranks the Mike Johnson name match first for 'mi'");
          searchBox.value = "zzzznope";
          searchBox.dispatchEvent("input");
          await sleep(250);
          assert.strictEqual(
            document.querySelectorAll("#main-table tbody tr").length, 0,
            "search with no match shows zero rows");
          assert.ok(
            document.getElementById("showing").textContent.includes("No matches for"),
            "empty search shows an inline empty state");
          searchBox.value = "";
          searchBox.dispatchEvent("input");
          await sleep(250);
          assert.strictEqual(
            document.querySelectorAll("#main-table tbody tr").length, PEOPLE.length,
            "clearing the search after U8 restores all rows");

          /* ---- escaping: text from the filings, or typed by a visitor, never becomes markup ---- */
          const hostile = '<img src=x onerror="globalThis.__injected=1">';
          const target = PEOPLE[0].person_key;
          BY_KEY[target].full_name = hostile;
          BY_KEY[target].data_notes = hostile;
          openDetail(target);
          const sheet = document.getElementById("detail-sheet");
          assert.strictEqual(sheet.querySelectorAll("img").length, 0,
            "a name or data note holding markup renders as text in the detail sheet");
          assert.ok(sheet.innerHTML.includes("&lt;img src=x"),
            "the detail sheet shows the markup escaped");
          searchBox.value = hostile;
          searchBox.dispatchEvent("input");
          await sleep(250);
          assert.strictEqual(document.querySelectorAll("#filter-chips img").length, 0,
            "a search holding markup renders as text in the filter chip");
          assert.strictEqual(globalThis.__injected, undefined, "no injected handler ran");

        return observed;
  },
  // Viewport phases: runtime.py resizes the browser before each one.
  async narrow() {
    await sleep(250);
    assert.strictEqual(senateCols(), 5, "D1: senateCols is 5 below 560px");
    assert.ok(
      document.getElementById("composition").innerHTML.includes('viewBox="0 0 320 505"'),
      "D1: resize to 500px reflows the Senate tiles to 5 wide (320x505)");
    renderComposition();
    assert.strictEqual(
      (document.getElementById("composition").innerHTML.match(/<g class="tile"/g) || []).length, 50,
      "D1: still 50 state tiles at 5 wide");
  },
  async wide() {
    await sleep(250);
    assert.strictEqual(senateCols(), 10, "D1: senateCols is 10 above 560px");
    assert.ok(
      document.getElementById("composition").innerHTML.includes('viewBox="0 0 645 250"'),
      "D1: resize back to 1024px restores the tiles to 10 wide (645x250)");
  },
  reducedMotion(expected) {
    assert.strictEqual(reducedMotion(), expected, "page reducedMotion() follows the OS preference");
  },
};
