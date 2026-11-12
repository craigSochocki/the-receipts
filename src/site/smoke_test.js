#!/usr/bin/env node
/* Runtime smoke test for the generated static site.
 *
 * Loads docs/index.html, runs its two app scripts in Node against a
 * minimal DOM stub, and asserts the rendered output: header stats,
 * default table order, each tab's content, the detail overlay, and the
 * CSV download path (no-throw). This catches runtime errors that a
 * syntax check (node --check) cannot — undefined functions, bad
 * selectors, broken data decoding.
 *
 * Usage: node src/site/smoke_test.js [path/to/docs/index.html]
 * Exit non-zero on any failed assertion.
 *
 * Also covers the landing-first front door (dirtiest top 5 + headline
 * comparison, clean story, default front-door mode, #explore switching)
 * and the person marks (party chips + outcome labels) on the front-door
 * lists, finder results, drill-down header, and full table; the
 * dirty-first leaderboards and Dirty-2026 default sort; and the
 * composition charts: the House waffle grid and the Senate state
 * tiles (dot/tile counts per party/status category).
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const htmlPath = process.argv[2] || "docs/index.html";
const html = fs.readFileSync(htmlPath, "utf8");

function extract(re, label) {
  const m = html.match(re);
  if (!m) throw new Error("missing " + label + " in " + htmlPath);
  return m[1];
}
const colsJson = extract(
  /<script id="receipts-cols" type="application\/json">(.*?)<\/script>/s,
  "receipts-cols payload");
const dataJson = extract(
  /<script id="receipts-data" type="application\/json">(.*?)<\/script>/s,
  "receipts-data payload");
const oppJson = extract(
  /<script id="opp-data" type="application\/json">(.*?)<\/script>/s,
  "opp-data payload");
const appScripts = [...html.matchAll(/<script>(.*?)<\/script>/gs)].map((m) => m[1]);
assert.strictEqual(appScripts.length, 2, "expected 2 app scripts, got " + appScripts.length);

/* ---- minimal DOM stub ---- */
class El {
  constructor() {
    this.children = [];
    this.attrs = {};
    this._html = "";
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.classList = { add() {}, remove() {}, toggle() {} };
    this.listeners = {};
  }
  set innerHTML(v) { this._html = v; this.children = []; }
  get innerHTML() { return this._html; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  querySelector() { return new El(); }
  querySelectorAll() { return []; }
  appendChild(c) { this.children.push(c); return c; }
  remove() {}
  click() {}
}
const byId = {};
function elFor(id) { if (!byId[id]) byId[id] = new El(); return byId[id]; }
byId["receipts-cols"] = Object.assign(new El(), { textContent: colsJson });
byId["receipts-data"] = Object.assign(new El(), { textContent: dataJson });
byId["opp-data"] = Object.assign(new El(), { textContent: oppJson });
const queryCache = {};
global.document = {
  getElementById: (id) => elFor(id),
  querySelector: (sel) => (queryCache[sel] = queryCache[sel] || new El()),
  querySelectorAll: () => [],
  createElement: () => new El(),
  addEventListener: () => {},
  body: new El(),
};
global.window = global;

/* ---- run the page's scripts (init() runs at the end of script 2) ---- */
vm.runInThisContext(appScripts[0], { filename: "site-app-1.js" });
vm.runInThisContext(appScripts[1], { filename: "site-app-2.js" });

/* ---- assertions ---- */
assert.strictEqual(PEOPLE.length, 664, "PEOPLE.length");
const statsHtml = document.getElementById("stats").innerHTML;
assert.ok(statsHtml.includes("664"), "stats mention 664 people: " + statsHtml.slice(0, 120));
assert.ok(statsHtml.includes("74"), "stats mention 74 verified clean");
const tbodyHtml = document.querySelector("#main-table tbody").innerHTML;
assert.ok(tbodyHtml.includes("Warnock"), "default table contains Warnock");
assert.ok(
  tbodyHtml.indexOf("Stevens") < tbodyHtml.indexOf("Boafo"),
  "default sort is Dirty 2026 desc (Stevens before Boafo)");
assert.ok(
  document.getElementById("totals").innerHTML.includes("Total accepted"),
  "totals strip rendered");

/* ---- front door (landing-first): dirtiest, clean story, default mode ---- */
const headlineHtml = document.getElementById("dirtiest-headline").innerHTML;
assert.ok(headlineHtml.includes("Stevens"), "headline leads with Stevens: " + headlineHtml);
assert.ok(headlineHtml.includes("$31.03M"), "headline shows Stevens $31.03M");
assert.ok(headlineHtml.includes("next four combined"), "headline compares #1 to next four");
assert.ok(headlineHtml.includes("2.04"), "headline ratio is about 2.04x");
assert.ok(headlineHtml.includes("$15.21M"), "headline shows next-four total $15.21M");
const dirtiestHtml = document.getElementById("dirtiest-list").innerHTML;
["Stevens", "Boafo", "Gallrein", "Bell", "Guthrie"].forEach((n) =>
  assert.ok(dirtiestHtml.includes(n), "dirtiest list has " + n));
assert.ok(
  dirtiestHtml.indexOf("Stevens") < dirtiestHtml.indexOf("Boafo") &&
  dirtiestHtml.indexOf("Boafo") < dirtiestHtml.indexOf("Gallrein") &&
  dirtiestHtml.indexOf("Gallrein") < dirtiestHtml.indexOf("Bell") &&
  dirtiestHtml.indexOf("Bell") < dirtiestHtml.indexOf("Guthrie"),
  "dirtiest list is in dirty-2026 order");
assert.ok(dirtiestHtml.includes("Not returning"), "Stevens row says Not returning");
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
setMode("front");
assert.strictEqual(
  document.getElementById("front-door").hidden, false,
  "back to front door");
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
assert.ok(leadersHtml.includes("$36,864,670.88"), "career dirty board shows Stevens $36.86M");
assert.ok(leadersHtml.includes("Hoyer"), "career dirty board has Hoyer");
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
assert.strictEqual(countDots(housePart, "dirty", "D"), 198, "House Dirty D 198");
assert.strictEqual(countDots(housePart, "clean", "D"), 58, "House Clean D 58");
assert.strictEqual(countDots(housePart, "dirty", "R"), 169, "House Dirty R 169");
assert.strictEqual(countDots(housePart, "clean", "R"), 2, "House Clean R 2");
assert.strictEqual(countDots(housePart, "unopposed", "D"), 2, "House Unopposed 2");
assert.strictEqual(countDots(housePart, "unverified", "D"), 1, "House Unverified 1");
assert.strictEqual(countDots(housePart, "uncalled", ""), 5, "House Uncalled 5");
// Senate state tiles: 50 tiles, one per state, two seat halves each.
assert.strictEqual((senPart.match(/<g class="tile"/g) || []).length, 50, "Senate chart has 50 state tiles");
assert.strictEqual((senPart.match(/class="half/g) || []).length, 100, "Senate chart has 100 seat halves");
const countHalves = (html, cls, party) =>
  (html.match(new RegExp('class="half ' + cls + '" data-party="' + party + '"', "g")) || []).length;
assert.strictEqual(countHalves(senPart, "dirty", "D"), 44, "Senate Dirty D 44");
assert.strictEqual(countHalves(senPart, "clean", "D"), 9, "Senate Clean D 9");
assert.strictEqual(countHalves(senPart, "dirty", "R"), 44, "Senate Dirty R 44");
assert.strictEqual(countHalves(senPart, "clean", "R"), 0, "Senate Clean R 0");
assert.strictEqual(countHalves(senPart, "dirty", "I"), 1, "Senate Dirty I 1");
assert.strictEqual(countHalves(senPart, "clean", "I"), 1, "Senate Clean I 1");
assert.strictEqual(countHalves(senPart, "uncalled", ""), 1, "Senate Uncalled 1");
// AK tile: half Murkowski (dirty R), half uncalled.
const akTile = senPart.split('data-state="AK"')[1].split('data-state="')[0];
assert.ok(akTile.includes('class="half dirty" data-party="R"'), "AK tile has Murkowski dirty R half");
assert.ok(akTile.includes('class="half uncalled"'), "AK tile has uncalled half");
// PA tile: both dirty, split D/R. AZ tile: same-party clean/dirty split.
const paTile = senPart.split('data-state="PA"')[1].split('data-state="')[0];
assert.ok(paTile.includes('class="half dirty" data-party="D"') && paTile.includes('class="half dirty" data-party="R"'), "PA tile splits dirty D / dirty R");
const azTile = senPart.split('data-state="AZ"')[1].split('data-state="')[0];
assert.ok(azTile.includes('class="half clean" data-party="D"') && azTile.includes('class="half dirty" data-party="D"'), "AZ tile splits clean D / dirty D");
assert.ok(compHtml.includes("Dirty D 198"), "House legend shows Dirty D 198");
assert.ok(compHtml.includes("Uncalled 5"), "House legend shows Uncalled 5");
assert.ok(compHtml.includes("Dirty D 44"), "Senate legend shows Dirty D 44");
assert.ok(compHtml.includes("Not shown: 6 non-voting delegates"), "delegate note present");
assert.ok(compHtml.includes("Clean D 3"), "delegate note shows Clean D 3");
assert.ok(compHtml.includes("Dirty PPD 1"), "delegate note shows Dirty PPD 1");

showTab("clean");
assert.ok(
  document.getElementById("clean-stats").innerHTML.includes("64 of 436"),
  "clean stats show 64 of 436 House");
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

const constKey = PEOPLE.find((p) => p.full_name.includes("Constantino")).person_key;
openDetail(constKey);
const detailHtml = document.getElementById("detail-sheet").innerHTML;
assert.ok(detailHtml.includes("$17,000,000.00"), "Constantino detail shows $17M self-funding");
assert.ok(detailHtml.includes("Self-funding"), "detail has self-funding section");
assert.ok(detailHtml.includes("Cycle by cycle"), "detail has cycle tables");
closeDetail();

const stevensKey = PEOPLE.find((p) => p.full_name.includes("Stevens")).person_key;
openDetail(stevensKey);
const stevensHtml = document.getElementById("detail-sheet").innerHTML;
assert.ok(
  stevensHtml.includes("UDP opposition credit by race"),
  "Stevens detail shows opposition credit by race");
assert.ok(stevensHtml.includes("Primary"), "Stevens detail shows the phase");
assert.ok(
  stevensHtml.includes("$20,139,904.21"),
  "Stevens detail shows the 2026 primary-phase credit");
assert.ok(
  stevensHtml.includes("$341,792.98"),
  "Stevens detail shows the 2022 primary-phase credit");
assert.ok(
  stevensHtml.includes("pchip d") && stevensHtml.includes("Not returning"),
  "Stevens drill-down header has the D chip and Not returning");
closeDetail();

downloadCsv(); // must not throw (Blob + object URL path)

/* ---- landing story + finder (Change 1) ---- */
const incoming120 = PEOPLE.filter((p) => p.in_120th === "yes");
const clean120 = incoming120.filter((p) => p.clean_2026 === true).length;
const storyHtml = document.getElementById("landing-story").innerHTML;
assert.ok(
  storyHtml.includes(clean120 + " of " + incoming120.length),
  "story renders the computed clean count: " + storyHtml);
assert.ok(storyHtml.includes("story-clean-link"), "story links to the clean list");
const findStateHtml = document.getElementById("find-state").innerHTML;
assert.ok(findStateHtml.includes("Michigan"), "finder state list has Michigan");
assert.ok(findStateHtml.includes("American Samoa"), "finder state list has American Samoa");
assert.strictEqual(finderSeats("MI")[0].value, "senate", "MI first seat is Senate");
assert.strictEqual(
  finderSeats("MI").filter((s) => s.value !== "senate").length, 13,
  "MI has 13 House districts");
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

/* ---- finder result buttons carry party chips + outcome ---- */
document.getElementById("find-state").value = "MI";
document.getElementById("find-district").listeners.change.forEach((f) =>
  f({ target: { value: "11" } }));
const finderPersonHtml = document.getElementById("find-person").innerHTML;
assert.ok(finderPersonHtml.includes("Jeremy Moss"), "MI-11 finder result is Moss");
assert.ok(finderPersonHtml.includes("pchip d"), "finder result has the D chip");
assert.ok(finderPersonHtml.includes("Won"), "finder result says Won");

console.log("Smoke test passed: 664 rows render, all tabs render, detail + CSV + landing work.");
