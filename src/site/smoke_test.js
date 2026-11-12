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
assert.ok(statsHtml.includes("77"), "stats mention 77 verified clean");
const tbodyHtml = document.querySelector("#main-table tbody").innerHTML;
assert.ok(tbodyHtml.includes("Warnock"), "default table contains Warnock");
assert.ok(
  tbodyHtml.indexOf("Warnock") < tbodyHtml.indexOf("Ossoff"),
  "default sort is total accepted desc (Warnock before Ossoff)");
assert.ok(
  document.getElementById("totals").innerHTML.includes("Total accepted"),
  "totals strip rendered");

showTab("leaders");
const leadersHtml = document.getElementById("leaders").innerHTML;
assert.ok(leadersHtml.includes("Warnock"), "leaderboard has Warnock");
assert.ok(leadersHtml.includes("Stevens"), "UDP-benefit board has Stevens");
assert.ok(leadersHtml.includes("Rick Scott"), "self-funding board has Rick Scott");
assert.ok(leadersHtml.includes("Talarico"), "all-IE board has Talarico");

showTab("clean");
assert.ok(
  document.getElementById("clean-stats").innerHTML.includes("67 of 436"),
  "clean stats show 67 of 436 House");
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

downloadCsv(); // must not throw (Blob + object URL path)

console.log("Smoke test passed: 664 rows render, all tabs render, detail + CSV work.");
