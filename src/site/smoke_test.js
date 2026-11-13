#!/usr/bin/env node
/* Runtime smoke test for the generated static site.
 *
 * Loads docs/index.html, parses it into a real DOM (hand-rolled,
 * dependency-free, in this file), runs its two app scripts in Node
 * against that DOM, and asserts the rendered output: header stats,
 * default table order, each tab's content, the detail overlay, and the
 * CSV download path (no-throw). This catches runtime errors that a
 * syntax check (node --check) cannot — undefined functions, bad
 * selectors, broken data decoding.
 *
 * The DOM is real, not a stub: elements parsed from the generated
 * HTML keep parents/children, innerHTML re-parses into real children,
 * querySelector(All) matches real CSS selectors, and events bubble
 * from the target up through ancestors (with event.target and
 * closest()), so handler changes are exercised instead of silently
 * skipped — the old stub's querySelectorAll() returned [] always,
 * which made every forEach(addEventListener) loop in the page a
 * no-op in the test. The test therefore also asserts handler
 * behavior directly: clicking a row opens the detail sheet, tab and
 * view buttons switch views, typing in the search box and changing
 * a filter select re-render the table, and the listeners the page
 * attaches are actually present. window.innerWidth is settable and
 * window.matchMedia evaluates (max-width: ...) and
 * (prefers-reduced-motion: ...) against it, so viewport hooks are
 * covered too (the page has no JS width breakpoint yet — D1, a later
 * wave — so the viewport assertions cover the harness capability,
 * not a breakpoint that does not exist).
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
 * tiles (dot/tile counts per party/status category). And the
 * scrollytelling front door: 7 chapters in narrative order, count-up
 * spans whose data-values are the computed figures (hook, clean story,
 * dirty explainer), and staggered waffle/tile/row reveals. And the 2028
 * primary targets tab: the computed watchlist intro (133 House Democrats,
 * 6 Class 3 Democratic senators under the Balanced default), both tables in dirty-2026 order with
 * the Dirty career column, and the front-door pointer button. And the
 * tolerance preset switching: Lenient 103 / 3, Strict 192 / 13, back to
 * Balanced 133 / 6, with the front-door story following the preset.
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

/* ---- a real DOM, hand-rolled and dependency-free ----
 *
 * The generated page is regular, machine-produced markup, so a small
 * parser for the elements/attributes it uses is enough. No npm
 * dependency: CI runs this file with a bare `node` and nothing else.
 *
 * What it supports (only what the page + this test use):
 * - parsing docs/index.html into a real element tree (text nodes,
 *   void elements, self-closing SVG, raw-text <script>/<style>);
 * - getElementById, querySelector(All) with real CSS matching (tag,
 *   #id, .class, [attr], [attr="value"], descendant and child
 *   combinators, comma groups); createElement, appendChild,
 *   insertBefore, removeChild, remove;
 * - innerHTML (getter serializes, setter re-parses into real
 *   children), textContent, classList, dataset, style (property
 *   access + setProperty, synced with the style attribute),
 *   set/get/has/removeAttribute, hidden/disabled/checked/value
 *   (selects resolve their selected option);
 * - addEventListener/removeEventListener + dispatchEvent with
 *   bubbling (event.target is the original target, currentTarget
 *   tracks the node handling it), el.click(), closest(),
 *   focus()/blur() + document.activeElement;
 * - document.documentElement/body, document.addEventListener,
 *   window.addEventListener, window.matchMedia (width-aware;
 *   window.innerWidth is settable, window.__reducedMotion toggles
 *   the prefers-reduced-motion query), location.hash (setting it
 *   fires a synchronous hashchange, as the page's listener expects).
 * - What it deliberately does NOT fake: IntersectionObserver and
 *   requestAnimationFrame stay undefined, so the page keeps its
 *   reveal-all / skip-animation fallbacks; timers are Node's real
 *   setTimeout/clearTimeout (no fake timers).
 */
const VOID_TAGS = new Set(["area", "base", "br", "col", "embed", "hr",
  "img", "input", "link", "meta", "param", "source", "track", "wbr"]);
const RAW_TEXT_TAGS = new Set(["script", "style"]);

function decodeEntities(s) {
  // Fast path: most text nodes contain no entities at all.
  if (s.indexOf("&") === -1) return s;
  return s.replace(/&(#x[0-9a-fA-F]+|#\d+|amp|lt|gt|quot|apos|nbsp);/g, (m, e) => {
    if (e === "amp") return "&";
    if (e === "lt") return "<";
    if (e === "gt") return ">";
    if (e === "quot") return '"';
    if (e === "apos") return "'";
    if (e === "nbsp") return "\u00a0";
    if (e[0] === "#") {
      const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isNaN(n) ? m : String.fromCodePoint(n);
    }
    return m;
  });
}
function escapeText(s) {
  s = String(s);
  if (s.indexOf("&") === -1 && s.indexOf("<") === -1 && s.indexOf(">") === -1) return s;
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function escapeAttr(s) {
  s = String(s);
  if (s.indexOf("&") === -1 && s.indexOf('"') === -1 && s.indexOf("<") === -1) return s;
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}
function parseAttrs(str) {
  const attrs = {};
  const re = /([^\s=\/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  let m;
  while ((m = re.exec(str)) !== null) {
    // Keep the name's case as written: SVG attributes like viewBox
    // are case-sensitive, and serialization must round-trip them.
    const name = m[1];
    const val = m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3]
      : m[4] !== undefined ? m[4] : "";
    attrs[name] = decodeEntities(val);
  }
  return attrs;
}

class TextNode {
  constructor(data) {
    this.nodeType = 3;
    this.data = String(data);
    this.parentNode = null;
    this._doc = null;
  }
  get textContent() { return this.data; }
  set textContent(v) { this.data = String(v == null ? "" : v); }
  remove() {
    if (!this.parentNode) return;
    const p = this.parentNode;
    const i = p.childNodes.indexOf(this);
    if (i >= 0) p.childNodes.splice(i, 1);
    this.parentNode = null;
  }
}

class ClassList {
  constructor(el) { this._el = el; this._cache = null; this._cacheFor = undefined; }
  // The class string is re-split only when it actually changed;
  // selector matching calls contains() on every node.
  _read() {
    const cur = this._el.attrs.class || "";
    if (this._cacheFor !== cur) {
      this._cache = cur.split(/\s+/).filter(Boolean);
      this._cacheFor = cur;
    }
    return this._cache;
  }
  _write(list) {
    if (list.length) this._el.attrs.class = list.join(" ");
    else delete this._el.attrs.class;
  }
  add(...names) {
    const s = new Set(this._read());
    names.forEach((n) => s.add(n));
    this._write([...s]);
  }
  remove(...names) {
    const s = new Set(this._read());
    names.forEach((n) => s.delete(n));
    this._write([...s]);
  }
  toggle(name, force) {
    const s = new Set(this._read());
    if (force === undefined) force = !s.has(name);
    if (force) s.add(name); else s.delete(name);
    this._write([...s]);
    return force;
  }
  contains(name) { return this._read().includes(name); }
}

function parseStyleString(s, map) {
  map.clear();
  s.split(";").forEach((part) => {
    const i = part.indexOf(":");
    if (i > 0) map.set(part.slice(0, i).trim(), part.slice(i + 1).trim());
  });
}
function styleToString(map) {
  return [...map].map(([k, v]) => k + ": " + v).join("; ");
}
function toKebab(prop) {
  return String(prop).replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
}
function makeStyle(el) {
  el._styleMap = new Map();
  if (el.attrs.style) parseStyleString(el.attrs.style, el._styleMap);
  const sync = () => {
    const s = styleToString(el._styleMap);
    if (s) el.attrs.style = s;
    else delete el.attrs.style;
  };
  return new Proxy({}, {
    get(_t, prop) {
      if (prop === "cssText") return styleToString(el._styleMap);
      if (prop === "setProperty") return (k, v) => { el._styleMap.set(k, String(v)); sync(); };
      if (prop === "getPropertyValue") return (k) => el._styleMap.get(k) || "";
      if (prop === "removeProperty") {
        return (k) => { const old = el._styleMap.get(k) || ""; el._styleMap.delete(k); sync(); return old; };
      }
      if (typeof prop === "symbol") return undefined;
      return el._styleMap.get(toKebab(prop)) ?? el._styleMap.get(String(prop)) ?? "";
    },
    set(_t, prop, v) {
      el._styleMap.set(toKebab(prop), String(v));
      sync();
      return true;
    },
  });
}

/* ---- CSS selector matching (tag, #id, .class, [attr], [attr="v"],
 * descendant + child combinators, comma groups) ----
 * Parsed selectors/compounds are cached: querySelectorAll walks the
 * whole tree, and re-parsing the selector per node dominated runtime. */
const compoundCache = new Map();
function parseCompound(comp) {
  const hit = compoundCache.get(comp);
  if (hit) return hit;
  const out = { tag: null, id: null, classes: [], attrs: [] };
  let rest = comp;
  const tagM = rest.match(/^(\*|[a-zA-Z][a-zA-Z0-9-]*)/);
  if (tagM) { out.tag = tagM[1].toLowerCase(); rest = rest.slice(tagM[0].length); }
  const re = /(?:#([a-zA-Z0-9_-]+))|(?:\.([a-zA-Z0-9_-]+))|(?:\[([^\]=]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\]]+)))?\])/g;
  let m;
  while ((m = re.exec(rest)) !== null) {
    if (m[1] !== undefined) out.id = m[1];
    else if (m[2] !== undefined) out.classes.push(m[2]);
    else if (m[3] !== undefined) {
      out.attrs.push({
        name: m[3].toLowerCase(),
        value: m[4] !== undefined ? m[4] : m[5] !== undefined ? m[5]
          : m[6] !== undefined ? m[6] : null,
      });
    }
  }
  compoundCache.set(comp, out);
  return out;
}
function matchesCompound(el, comp) {
  if (!el || el.nodeType !== 1) return false;
  const p = parseCompound(comp);
  if (p.tag && p.tag !== "*" && el._tag !== p.tag) return false;
  if (p.id && el.getAttribute("id") !== p.id) return false;
  for (const c of p.classes) if (!el.classList.contains(c)) return false;
  for (const a of p.attrs) {
    const v = el.getAttribute(a.name);
    if (v === null || v === undefined) return false;
    if (a.value !== null && v !== a.value) return false;
  }
  return true;
}
function parseSelectorGroup(group) {
  const parts = []; // [{compound, combinator}] left to right
  group.split(/\s*>\s*/).forEach((seg, si) => {
    seg.trim().split(/\s+/).filter(Boolean).forEach((comp, ci) => {
      parts.push({
        compound: comp,
        combinator: si === 0 ? (ci === 0 ? null : " ") : (ci === 0 ? ">" : " "),
      });
    });
  });
  return parts;
}
function matchFromRight(el, parts, idx) {
  if (!el || el.nodeType !== 1) return false;
  if (!matchesCompound(el, parts[idx].compound)) return false;
  if (idx === 0) return true;
  if (parts[idx].combinator === ">") return matchFromRight(el.parentNode, parts, idx - 1);
  let anc = el.parentNode;
  while (anc) {
    if (matchFromRight(anc, parts, idx - 1)) return true;
    anc = anc.parentNode;
  }
  return false;
}
function matchesSelector(el, selector) {
  return parseSelector(selector)
    .some((parts) => matchFromRight(el, parts, parts.length - 1));
}
const selectorCache = new Map();
function parseSelector(selector) {
  let parsed = selectorCache.get(selector);
  if (!parsed) {
    parsed = String(selector).split(",").map((s) => s.trim()).filter(Boolean)
      .map(parseSelectorGroup).filter((p) => p.length > 0);
    selectorCache.set(selector, parsed);
  }
  return parsed;
}
function collectDescendants(root, out) {
  for (const child of root.childNodes || []) {
    if (child.nodeType === 1) { out.push(child); collectDescendants(child, out); }
  }
}
function queryAllInTree(root, selector, includeSelf) {
  if (!root) return [];
  const all = [];
  if (includeSelf && root.nodeType === 1) all.push(root);
  collectDescendants(root, all);
  return all.filter((el) => matchesSelector(el, selector));
}
function serializeNode(node) {
  if (node.nodeType === 3) return escapeText(node.data);
  const attrs = Object.keys(node.attrs)
    .map((k) => " " + k + '="' + escapeAttr(node.attrs[k]) + '"').join("");
  if (VOID_TAGS.has(node._tag)) return "<" + node._tag + attrs + ">";
  return "<" + node._tag + attrs + ">" + node.childNodes.map(serializeNode).join("")
    + "</" + node._tag + ">";
}

/* ---- HTML parsing (elements/attributes the generated page uses) ----
 * Stack-based, lenient about mismatched closes. <script>/<style>
 * are raw text (no entity decoding, no tag parsing inside), so the
 * embedded JSON payloads survive byte-identically. */
const OPEN_RE = /<\s*([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s=\/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*(\/?)>/y;
const CLOSE_RE = /<\/\s*([a-zA-Z][a-zA-Z0-9-]*)\s*>/y;
function parseFragment(htmlStr, doc) {
  const root = new El("div"); // dummy container, discarded by callers
  root._doc = doc;
  const stack = [root];
  const lower = htmlStr.toLowerCase();
  const n = htmlStr.length;
  let i = 0;
  const addText = (s, raw) => {
    if (!s) return;
    const t = new TextNode(raw ? s : decodeEntities(s));
    t._doc = doc;
    stack[stack.length - 1].appendChild(t);
  };
  while (i < n) {
    const lt = htmlStr.indexOf("<", i);
    if (lt === -1) { addText(htmlStr.slice(i)); break; }
    if (lt > i) addText(htmlStr.slice(i, lt));
    if (htmlStr.startsWith("<!--", lt)) {
      const end = htmlStr.indexOf("-->", lt + 4);
      i = end === -1 ? n : end + 3;
      continue;
    }
    if (htmlStr.startsWith("<!", lt)) {
      const end = htmlStr.indexOf(">", lt);
      i = end === -1 ? n : end + 1;
      continue;
    }
    CLOSE_RE.lastIndex = lt;
    const closeM = CLOSE_RE.exec(htmlStr);
    if (closeM) {
      const tag = closeM[1].toLowerCase();
      for (let s = stack.length - 1; s > 0; s--) {
        if (stack[s]._tag === tag) { stack.length = s; break; }
      }
      i = lt + closeM[0].length;
      continue;
    }
    OPEN_RE.lastIndex = lt;
    const openM = OPEN_RE.exec(htmlStr);
    if (!openM) { addText("<"); i = lt + 1; continue; } // stray "<"
    const tag = openM[1].toLowerCase();
    const el = new El(tag);
    el._doc = doc;
    el.attrs = parseAttrs(openM[2] || "");
    el._checked = el.hasAttribute("checked");
    el._selected = el.hasAttribute("selected");
    stack[stack.length - 1].appendChild(el);
    i = lt + openM[0].length;
    if (RAW_TEXT_TAGS.has(tag)) {
      const closeIdx = lower.indexOf("</" + tag, i);
      let text, next;
      if (closeIdx === -1) { text = htmlStr.slice(i); next = n; }
      else {
        const gt = htmlStr.indexOf(">", closeIdx);
        text = htmlStr.slice(i, closeIdx);
        next = gt === -1 ? n : gt + 1;
      }
      if (text) {
        // Raw text belongs to the script/style element itself, not to
        // whatever is on top of the stack (the element is never pushed).
        const t = new TextNode(text);
        t._doc = doc;
        el.appendChild(t);
      }
      i = next;
      continue;
    }
    if (!VOID_TAGS.has(tag) && openM[3] !== "/") stack.push(el);
  }
  return root.childNodes.slice();
}
function parseDocument(htmlStr, doc) {
  const nodes = parseFragment(htmlStr, doc);
  const htmlEl = nodes.find((x) => x.nodeType === 1 && x._tag === "html");
  if (!htmlEl) throw new Error("no <html> element in " + htmlPath);
  htmlEl.parentNode = null; // detach from the parser's dummy container
  return htmlEl;
}

class DomEvent {
  constructor(type, init) {
    this.type = type;
    this.target = null;
    this.currentTarget = null;
    this.defaultPrevented = false;
    this._stopped = false;
    this.bubbles = true;
    this.cancelable = true;
    if (init) Object.assign(this, init);
  }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() { this._stopped = true; }
}

class El {
  constructor(tagName) {
    this.nodeType = 1;
    this._tag = String(tagName).toLowerCase();
    this.tagName = this._tag.toUpperCase();
    this.attrs = {};
    this.children = [];
    this.childNodes = [];
    this.parentNode = null;
    this.listeners = {}; // kept public: the test reads listeners.<type>
    this._doc = null;
    this._value = undefined;
    this._checked = false;
    this._selected = false;
    this._classList = null;
    this._style = null;
    this._styleMap = null;
    this._dataset = null;
  }
  /* ---- attributes ----
   * Names are matched case-insensitively (HTML), but the stored
   * spelling is the source spelling, so serialization round-trips
   * case-sensitive names like viewBox. */
  _attrKey(k) {
    const key = String(k);
    if (Object.prototype.hasOwnProperty.call(this.attrs, key)) return key;
    const lower = key.toLowerCase();
    if (lower !== key && Object.prototype.hasOwnProperty.call(this.attrs, lower)) return lower;
    return lower;
  }
  setAttribute(k, v) {
    const key = this._attrKey(k);
    this.attrs[key] = String(v);
    if (key.toLowerCase() === "style" && this._styleMap) parseStyleString(String(v), this._styleMap);
  }
  getAttribute(k) {
    const key = this._attrKey(k);
    const v = this.attrs[key];
    return v === undefined ? null : v;
  }
  hasAttribute(k) {
    return Object.prototype.hasOwnProperty.call(this.attrs, this._attrKey(k));
  }
  removeAttribute(k) {
    const key = this._attrKey(k);
    delete this.attrs[key];
    if (key.toLowerCase() === "style" && this._styleMap) this._styleMap.clear();
  }
  get id() { return this.attrs.id || ""; }
  set id(v) { this.attrs.id = String(v); }
  get className() { return this.attrs.class || ""; }
  set className(v) {
    if (v) this.attrs.class = String(v);
    else delete this.attrs.class;
  }
  get classList() {
    if (!this._classList) this._classList = new ClassList(this);
    return this._classList;
  }
  get style() {
    if (!this._style) this._style = makeStyle(this);
    return this._style;
  }
  get dataset() {
    if (!this._dataset) {
      const el = this;
      this._dataset = new Proxy({}, {
        get(_t, prop) {
          if (typeof prop !== "string") return undefined;
          return el.getAttribute("data-" + toKebab(prop));
        },
        set(_t, prop, v) {
          el.setAttribute("data-" + toKebab(prop), String(v));
          return true;
        },
      });
    }
    return this._dataset;
  }
  /* ---- tree ---- */
  get parentElement() {
    return this.parentNode && this.parentNode.nodeType === 1 ? this.parentNode : null;
  }
  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get firstElementChild() { return this.children[0] || null; }
  get nextSibling() {
    if (!this.parentNode) return null;
    const sibs = this.parentNode.childNodes;
    return sibs[sibs.indexOf(this) + 1] || null;
  }
  get previousSibling() {
    if (!this.parentNode) return null;
    const sibs = this.parentNode.childNodes;
    return sibs[sibs.indexOf(this) - 1] || null;
  }
  appendChild(node) {
    if (node.parentNode) node.remove();
    node.parentNode = this;
    this.childNodes.push(node);
    if (node.nodeType === 1) this.children.push(node);
    if (node._doc == null) node._doc = this._doc;
    return node;
  }
  insertBefore(node, ref) {
    if (node.parentNode) node.remove();
    node.parentNode = this;
    const idx = ref ? this.childNodes.indexOf(ref) : -1;
    if (idx === -1) this.childNodes.push(node);
    else this.childNodes.splice(idx, 0, node);
    if (node.nodeType === 1) {
      let eidx = this.children.length;
      if (ref) {
        eidx = ref.nodeType === 1 ? this.children.indexOf(ref)
          : this.childNodes.slice(0, idx === -1 ? this.childNodes.length : idx)
            .filter((c) => c.nodeType === 1).length;
      }
      this.children.splice(eidx, 0, node);
    }
    if (node._doc == null) node._doc = this._doc;
    return node;
  }
  removeChild(node) {
    const ci = this.childNodes.indexOf(node);
    if (ci >= 0) this.childNodes.splice(ci, 1);
    if (node.nodeType === 1) {
      const ei = this.children.indexOf(node);
      if (ei >= 0) this.children.splice(ei, 1);
    }
    node.parentNode = null;
    return node;
  }
  remove() {
    if (this.parentNode) this.parentNode.removeChild(this);
  }
  /* ---- content ---- */
  get innerHTML() { return this.childNodes.map(serializeNode).join(""); }
  set innerHTML(v) {
    const nodes = parseFragment(String(v), this._doc);
    this.childNodes = [];
    this.children = [];
    for (const n of nodes) this.appendChild(n);
  }
  get textContent() {
    return this.childNodes.map((n) => (n.nodeType === 3 ? n.data : n.textContent)).join("");
  }
  set textContent(v) {
    this.childNodes = [];
    this.children = [];
    this.appendChild(new TextNode(String(v == null ? "" : v)));
  }
  get outerHTML() { return serializeNode(this); }
  /* ---- form state ---- */
  get value() {
    if (this._tag === "select") {
      if (this._value !== undefined) return this._value;
      for (const opt of this.children) {
        if (opt._tag === "option" && opt._selected) return opt.value;
      }
      const first = this.children.find((c) => c._tag === "option");
      return first ? first.value : "";
    }
    if (this._tag === "option" && this._value === undefined
      && this.getAttribute("value") === null) return this.textContent;
    return this._value !== undefined ? this._value : (this.getAttribute("value") ?? "");
  }
  set value(v) {
    const s = String(v);
    if (this._tag === "select") {
      this._value = s;
      for (const opt of this.children) {
        if (opt._tag !== "option") continue;
        const on = opt.value === s;
        opt._selected = on;
        if (on) opt.setAttribute("selected", "");
        else opt.removeAttribute("selected");
      }
    } else {
      this._value = s;
    }
  }
  get checked() { return this._checked; }
  set checked(v) { this._checked = !!v; }
  get selected() { return this._selected; }
  set selected(v) {
    this._selected = !!v;
    if (v) this.setAttribute("selected", "");
    else this.removeAttribute("selected");
  }
  get hidden() { return this.hasAttribute("hidden"); }
  set hidden(v) {
    if (v) this.setAttribute("hidden", "");
    else this.removeAttribute("hidden");
  }
  get disabled() { return this.hasAttribute("disabled"); }
  set disabled(v) {
    if (v) this.setAttribute("disabled", "");
    else this.removeAttribute("disabled");
  }
  /* ---- events: dispatch bubbles to ancestors, then document, then window ---- */
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  removeEventListener(t, f) {
    const a = this.listeners[t];
    if (a) {
      const i = a.indexOf(f);
      if (i >= 0) a.splice(i, 1);
    }
  }
  dispatchEvent(type, init) {
    const event = typeof type === "string" ? new DomEvent(type, init || {}) : type;
    if (!event.target) event.target = this;
    let node = this;
    while (node) {
      event.currentTarget = node;
      const list = (node.listeners && node.listeners[event.type]) || [];
      for (const fn of list.slice()) {
        fn.call(node, event);
        if (event._stopped) break;
      }
      if (event._stopped) break;
      node = node.parentNode;
    }
    // Document + window listeners fire only if this node is in the tree.
    const doc = this._doc;
    let connected = false;
    let up = this;
    while (up) {
      if (doc && up === doc.documentElement) { connected = true; break; }
      up = up.parentNode;
    }
    if (connected && doc && !event._stopped) {
      event.currentTarget = doc;
      const list = (doc.listeners && doc.listeners[event.type]) || [];
      for (const fn of list.slice()) {
        fn.call(doc, event);
        if (event._stopped) break;
      }
    }
    if (connected && !event._stopped) fireWindowListeners(event);
    event.currentTarget = null;
    return !event.defaultPrevented;
  }
  click() { this.dispatchEvent("click"); }
  focus() {
    const d = this._doc;
    if (d) d.activeElement = this;
  }
  blur() {
    const d = this._doc;
    if (d && d.activeElement === this) d.activeElement = null;
  }
  closest(selector) {
    let node = this;
    while (node && node.nodeType === 1) {
      if (matchesSelector(node, selector)) return node;
      node = node.parentNode;
    }
    return null;
  }
  querySelector(sel) {
    const r = queryAllInTree(this, sel, false);
    return r.length ? r[0] : null;
  }
  querySelectorAll(sel) { return queryAllInTree(this, sel, false); }
}

/* ---- document + window ---- */
const windowListeners = {};
function fireWindowListeners(event) {
  event.currentTarget = global;
  const list = windowListeners[event.type] || [];
  for (const fn of list.slice()) {
    fn.call(global, event);
    if (event._stopped) break;
  }
}
const doc = {
  nodeType: 9,
  listeners: {},
  activeElement: null, // null until something is focused
  documentElement: null,
  body: null,
  getElementById(id) {
    const walk = (node) => {
      if (node.nodeType === 1) {
        // Direct attr read: getAttribute's case handling is pure
        // overhead on a hot walk, and ids are lowercase in source.
        if (node.attrs.id === id) return node;
        for (const c of node.children) {
          const f = walk(c);
          if (f) return f;
        }
      }
      return null;
    };
    return this.documentElement ? walk(this.documentElement) : null;
  },
  querySelector(sel) {
    const r = this.querySelectorAll(sel);
    return r.length ? r[0] : null;
  },
  querySelectorAll(sel) { return queryAllInTree(this.documentElement, sel, true); },
  createElement(tag) {
    const el = new El(tag);
    el._doc = doc;
    return el;
  },
  createTextNode(text) {
    const t = new TextNode(String(text));
    t._doc = doc;
    return t;
  },
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
  removeEventListener(t, f) {
    const a = this.listeners[t];
    if (a) {
      const i = a.indexOf(f);
      if (i >= 0) a.splice(i, 1);
    }
  },
  dispatchEvent(type, init) {
    const event = typeof type === "string" ? new DomEvent(type, init || {}) : type;
    if (!event.target) event.target = doc;
    event.currentTarget = doc;
    const list = (doc.listeners[event.type]) || [];
    for (const fn of list.slice()) {
      fn.call(doc, event);
      if (event._stopped) break;
    }
    if (!event._stopped) fireWindowListeners(event);
    event.currentTarget = null;
    return !event.defaultPrevented;
  },
};
global.document = doc;
global.window = global;
global.addEventListener = (t, f) => { (windowListeners[t] = windowListeners[t] || []).push(f); };
global.removeEventListener = (t, f) => {
  const a = windowListeners[t];
  if (a) {
    const i = a.indexOf(f);
    if (i >= 0) a.splice(i, 1);
  }
};
global.dispatchEvent = (type, init) => {
  const event = typeof type === "string" ? new DomEvent(type, init || {}) : type;
  if (!event.target) event.target = global;
  fireWindowListeners(event);
  event.currentTarget = null;
  return !event.defaultPrevented;
};
// Viewport: innerWidth is settable; matchMedia evaluates width and
// reduced-motion queries against it. __reducedMotion is the test
// harness's stand-in for the OS preference (default: off).
global.innerWidth = 1024;
global.__reducedMotion = false;
global.matchMedia = (query) => {
  const q = String(query || "");
  let matches = true;
  for (const part of q.split(/\s+and\s+/i).map((s) => s.trim()).filter(Boolean)) {
    const m = part.match(/^\(\s*(max|min)-width\s*:\s*(\d+(?:\.\d+)?)px\s*\)$/i);
    if (m) {
      const w = global.innerWidth;
      matches = matches && (m[1].toLowerCase() === "max"
        ? w <= parseFloat(m[2]) : w >= parseFloat(m[2]));
      continue;
    }
    const r = part.match(/^\(\s*prefers-reduced-motion\s*:\s*(reduce|no-preference)\s*\)$/i);
    if (r) {
      matches = matches && (r[1].toLowerCase() === "reduce"
        ? global.__reducedMotion === true : global.__reducedMotion !== true);
      continue;
    }
    if (/^(screen|all|print)$/i.test(part)) continue;
    matches = false; // unknown feature: cannot match
  }
  return {
    matches, media: q,
    addEventListener() {}, removeEventListener() {},
    addListener() {}, removeListener() {},
  };
};
// location.hash drives front-door/explore mode; setting it fires a
// synchronous hashchange (the page's listener expects one). Values
// are stored with the leading "#" a real browser adds.
let _hash = "";
let _firingHashchange = false;
global.location = {};
Object.defineProperty(global.location, "hash", {
  get() { return _hash; },
  set(v) {
    const raw = v == null ? "" : String(v);
    const nv = raw === "" ? "" : raw.startsWith("#") ? raw : "#" + raw;
    if (nv === _hash) return;
    _hash = nv;
    if (!_firingHashchange) {
      _firingHashchange = true;
      try { global.dispatchEvent("hashchange"); } finally { _firingHashchange = false; }
    }
  },
  configurable: true,
});

/* ---- parse the page, then run its scripts against the real DOM ---- */
doc.documentElement = parseDocument(html, doc);
doc.body = doc.documentElement.querySelector("body");

/* The parsed <script> payloads must be byte-identical to the raw HTML:
 * the page JSON.parses them, so any entity decoding or whitespace
 * change in the parser would corrupt the dataset. */
assert.strictEqual(
  document.getElementById("receipts-cols").textContent, colsJson,
  "parsed receipts-cols payload is byte-identical");
assert.strictEqual(
  document.getElementById("receipts-data").textContent, dataJson,
  "parsed receipts-data payload is byte-identical");
assert.strictEqual(
  document.getElementById("opp-data").textContent, oppJson,
  "parsed opp-data payload is byte-identical");

/* ---- run the page's scripts (init() runs at the end of script 2) ---- */
vm.runInThisContext(appScripts[0], { filename: "site-app-1.js" });
vm.runInThisContext(appScripts[1], { filename: "site-app-2.js" });

/* ---- assertions ---- */
assert.strictEqual(PEOPLE.length, 664, "PEOPLE.length");
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
assert.ok(headlineHtml.includes("Stevens"), "headline leads with Stevens: " + headlineHtml);
assert.ok(headlineHtml.includes("$31.03M"), "headline shows Stevens $31.03M");
assert.ok(headlineHtml.includes("next four combined"), "headline compares #1 to next four");
assert.ok(headlineHtml.includes("2.04"), "headline ratio is about 2.04x");
assert.ok(headlineHtml.includes("$15.21M"), "headline shows next-four total $15.21M");

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
/* ---- FE7: first entry into Explore renders the workspace ---- */
const statsHtml = document.getElementById("stats").innerHTML;
assert.ok(statsHtml.includes("664"), "stats mention 664 people: " + statsHtml.slice(0, 120));
assert.ok(statsHtml.includes("203") && statsHtml.includes("not dirty"), "stats mention 203 not dirty (Balanced)");
assert.strictEqual(
  document.querySelectorAll("#stats .stat").length, 3,
  "D7: Explore stats are 3 cards");
assert.ok(statsHtml.includes("not judged"), "D7: third card is the combined not-judged card");
assert.ok(statsHtml.includes("Elaine Luria"), "D7: not-judged card names the unverified member");
const tbodyHtml = document.querySelector("#main-table tbody").innerHTML;
assert.ok(tbodyHtml.includes("Warnock"), "default table contains Warnock");
assert.ok(
  tbodyHtml.indexOf("Stevens") < tbodyHtml.indexOf("Boafo"),
  "default sort is Dirty 2026 desc (Stevens before Boafo)");
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
assert.strictEqual(countDots(housePart, "dirty", "D"), 192, "House Dirty D 192");
assert.strictEqual(countDots(housePart, "clean", "D"), 64, "House Clean D 64");
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
assert.strictEqual(countHalves(senPart, "dirty", "D"), 40, "Senate Dirty D 40");
assert.strictEqual(countHalves(senPart, "clean", "D"), 13, "Senate Clean D 13");
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
assert.ok(compHtml.includes("Dirty D 192"), "House legend shows Dirty D 192");
assert.ok(compHtml.includes("Uncalled 5"), "House legend shows Uncalled 5");
assert.ok(compHtml.includes("Dirty D 40"), "Senate legend shows Dirty D 40");
assert.ok(compHtml.includes("Not shown: 6 non-voting delegates"), "delegate note present");
assert.ok(compHtml.includes("Clean D 3"), "delegate note shows Clean D 3");
assert.ok(compHtml.includes("Dirty PPD 1"), "delegate note shows Dirty PPD 1");

showTab("clean");
assert.ok(
  document.getElementById("clean-stats").innerHTML.includes("150 of 436"),
  "clean stats show 150 of 436 House not dirty (Balanced)");
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
assert.ok(t28Intro.includes("133 House Democrats"), "2028 intro counts 133 House Democrats (Balanced)");
assert.ok(t28Intro.includes("6 Democratic senators"), "2028 intro counts 6 Democratic senators (Balanced)");
const t28HouseHtml = document.querySelector("#targets28-house-table tbody").innerHTML;
assert.ok(t28HouseHtml.includes("Boafo"), "2028 House table starts with Boafo");
assert.ok(
  t28HouseHtml.indexOf("Boafo") < t28HouseHtml.indexOf("Bell"),
  "2028 House table in dirty-2026 order");
assert.ok(t28HouseHtml.includes("$5,745,013.28"), "2028 House table shows Boafo dirty 2026");
assert.ok(t28HouseHtml.includes("$36,864,670.88") === false, "2028 House table does not show Stevens (not in 120th)");
const t28SenHtml = document.querySelector("#targets28-senate-table tbody").innerHTML;
assert.ok(t28SenHtml.includes("Hassan"), "2028 Senate table has Hassan");
assert.ok(
  t28SenHtml.indexOf("Hassan") < t28SenHtml.indexOf("Wyden") &&
  t28SenHtml.indexOf("Wyden") < t28SenHtml.indexOf("Schatz"),
  "2028 Senate table in dirty-2026 order");
assert.ok(t28SenHtml.includes("Schumer"), "2028 Senate table has Schumer");
assert.ok(t28SenHtml.includes("$407,388.00"), "2028 Senate table shows Hassan dirty 2026");
assert.ok(t28SenHtml.includes("$2,148,341.00"), "2028 Senate table shows Hassan dirty career");
assert.ok(t28SenHtml.includes("NH · Senate"), "2028 Senate rows show the seat");

/* ---- tolerance preset switching (methodology §14) ---- */
// Default is Balanced: 133 House / 6 Senate targets. Switching the
// preset recomputes the watchlist and the front-door story live;
// Strict restores 192 / 13 and Lenient gives 103 / 3.
setPreset("lenient");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("103 House Democrats"),
  "Lenient 2028 intro counts 103 House Democrats");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("3 Democratic senators"),
  "Lenient 2028 intro counts 3 Democratic senators");
setPreset("strict");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("192 House Democrats"),
  "Strict 2028 intro counts 192 House Democrats");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("13 Democratic senators"),
  "Strict 2028 intro counts 13 Democratic senators");
assert.ok(
  document.getElementById("landing-story").innerHTML.replace(/<[^>]+>/g, "").includes("84 of 535"),
  "Strict story shows 84 of 535 verified clean");
setPreset("balanced");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("133 House Democrats"),
  "Balanced 2028 intro counts 133 House Democrats");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("6 Democratic senators"),
  "Balanced 2028 intro counts 6 Democratic senators");

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
assert.ok(detailHtml.includes("$17,000,000.00"), "Constantino detail shows $17M self-funding");
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
  document.querySelectorAll("#main-table tbody tr").length, 664,
  "Reset restores all 664 rows");
assert.strictEqual(
  document.getElementById("filter-chips").innerHTML, "",
  "Reset clears the chips");

/* ---- finder result buttons carry party chips + outcome ---- */
document.getElementById("find-state").value = "MI";
document.getElementById("find-district").listeners.change.forEach((f) =>
  f({ target: { value: "11" } }));
const finderPersonHtml = document.getElementById("find-person").innerHTML;
assert.ok(finderPersonHtml.includes("Jeremy Moss"), "MI-11 finder result is Moss");
assert.ok(finderPersonHtml.includes("pchip d"), "finder result has the D chip");
assert.ok(finderPersonHtml.includes("Won"), "finder result says Won");

/* ---- scrollytelling: chapters, count-ups, stagger ---- */
// Chapter order is in the static template.
const chapterOrder = [...html.matchAll(/data-chapter="([^"]+)"/g)].map((m) => m[1]);
assert.deepStrictEqual(
  chapterOrder,
  ["hook", "dirtiest", "dirty-definition", "clean", "chamber", "finder", "data"],
  "front door chapters in narrative order: " + chapterOrder.join(","));
// Count-up spans: data-value is the computed figure, initial text is
// the final formatted figure. The stub has no IntersectionObserver,
// so reveals run immediately — values must already be final.
const stevens = PEOPLE.find((p) => p.full_name.includes("Stevens"));
// runCountUp marks counted spans with data-counted, so the live DOM
// carries an extra attribute the old stub's frozen innerHTML string
// never had (in a real browser it would too) — the patterns allow
// for attributes after data-format.
const hookCountups = [...headlineHtml.matchAll(/<span class="countup" data-value="([\d.]+)" data-format="([^"]+)"[^>]*>([^<]+)<\/span>/g)];
assert.ok(hookCountups.length === 2, "hook has two count-up spans, got " + hookCountups.length);
assert.strictEqual(parseFloat(hookCountups[0][1]), stevens.dirty_2026, "hook count-up targets Stevens dirty 2026");
assert.strictEqual(hookCountups[0][3], "$31.03M", "hook count-up shows $31.03M");
const dirtyTop5 = PEOPLE.filter((p) => typeof p.dirty_2026 === "number")
  .sort((a, b) => b.dirty_2026 - a.dirty_2026).slice(0, 5);
const nextFour = dirtyTop5.slice(1).reduce((s, p) => s + p.dirty_2026, 0);
assert.strictEqual(parseFloat(hookCountups[1][1]), nextFour, "hook count-up targets the next-four total");
assert.strictEqual(hookCountups[1][3], "$15.21M", "hook count-up shows $15.21M next-four total");
const storyCountups = [...storyHtml.matchAll(/<span class="countup" data-value="(\d+)" data-format="int"[^>]*>(\d+)<\/span>/g)].map((m) => m[1]);
assert.deepStrictEqual(storyCountups, [String(notDirty120), String(incoming120.length)], "story count-ups are 203 and 535");
// Dirty explainer: big number counts up to the career dirty total;
// the three components sum to it exactly.
const explainerHtml = document.getElementById("dirty-explainer").innerHTML;
const dcTotal = PEOPLE.reduce((s, p) => s + (typeof p.dirty_career === "number" ? p.dirty_career : 0), 0);
assert.ok(explainerHtml.includes("$1.07B"), "explainer shows $1.07B career dirty");
const explainerCountup = explainerHtml.match(/<span class="countup" data-value="([\d.]+)" data-format="compact"[^>]*>([^<]+)<\/span>/);
assert.ok(explainerCountup, "explainer has a count-up span");
assert.strictEqual(parseFloat(explainerCountup[1]), dcTotal, "explainer count-up targets the computed career dirty total");
assert.strictEqual(explainerCountup[2], "$1.07B", "explainer count-up shows $1.07B");
assert.ok(explainerHtml.includes("Individual contributions are <b>not</b> dirty money"), "explainer says individual contributions are not dirty");
const dcParts = ["corporate_pac_career", "aipac_pac_direct_career", "udp_ie_total_benefit_career"]
  .reduce((s, k) => s + PEOPLE.reduce((a, p) => a + (typeof p[k] === "number" ? p[k] : 0), 0), 0);
assert.ok(Math.abs(dcParts - dcTotal) < 0.01, "explainer components sum to the career dirty total");
// Stagger: waffle dots carry per-column delays, senate tiles per-tile.
assert.ok(housePart.includes("transition-delay"), "waffle dots stagger by column");
assert.ok(senPart.includes("transition-delay"), "senate tiles stagger");
assert.ok(dirtiestHtml.includes("transition-delay"), "dirtiest rows stagger");

/* ---- NEW (FE9): handler coverage on the real DOM ----
 * The old stub's querySelectorAll() returned [] always, so none of
 * this could be tested. findPerson (above) left the search box and
 * the congress filter set, so reset the filters first. */
function resetFilters() {
  // Only dispatch for controls whose value actually changed: every
  // dispatch re-renders the 664-row table, so no-op dispatches are
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
  document.querySelectorAll("#main-table tbody tr").length, 664,
  "reset filters restore 664 rows");
assert.ok(
  document.getElementById("showing").textContent.includes("Showing 664 of 664"),
  "showing line counts 664 of 664");

const hasClick = (el) => (el.listeners.click || []).length >= 1;
const hasListener = (el, type) => (el.listeners[type] || []).length >= 1;
// querySelectorAll is real now: the old stub returned [] for all of these.
assert.strictEqual(
  document.querySelectorAll("#main-table tbody tr").length, 664,
  "querySelectorAll finds all 664 table rows");
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
  document.getElementById("clean-stats").innerHTML.includes("150 of 436"),
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
  document.querySelectorAll("#main-table tbody tr").length, 664,
  "party filter reset restores 664 rows");
assert.strictEqual(
  document.getElementById("csv-btn").textContent,
  "Download CSV — 664 rows",
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
  "leadership filter returns the " + leaderCount + " 119th leaders, not all 664");
assert.ok(
  document.getElementById("filter-chips").innerHTML.includes("Leadership (119th; 120th TBD)"),
  "leadership filter shows as a chip");
leaderBox.checked = false;
leaderBox.dispatchEvent("change");
assert.strictEqual(
  document.querySelectorAll("#main-table tbody tr").length, 664,
  "leadership filter reset restores 664 rows");

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
  document.getElementById("targets28-intro").innerHTML.includes("133 House Democrats"),
  "targets28 tab click shows the Balanced intro");
const tolSel = document.getElementById("f-tolerance");
tolSel.value = "strict";
tolSel.dispatchEvent("change");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("192 House Democrats"),
  "tolerance select change to Strict recomputes the watchlist");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("13 Democratic senators"),
  "Strict intro counts 13 senators");
tolSel.value = "balanced";
tolSel.dispatchEvent("change");
assert.ok(
  document.getElementById("targets28-intro").innerHTML.includes("133 House Democrats"),
  "tolerance select change back to Balanced restores 133");
document.querySelector('.tabs button[data-tab="tracker"]').dispatchEvent("click");

/* ---- D6/FE3: compact/exact money toggle (persisted, Compact default) ---- */
const moneySel = document.getElementById("f-money");
assert.strictEqual(moneySel.value, "compact", "money toggle defaults to Compact");
const dirtyCell = document.querySelector("#main-table tbody tr").children[11];
assert.strictEqual(dirtyCell.textContent, "$31.03M", "money shows compact by default");
moneySel.value = "exact";
moneySel.dispatchEvent("change");
assert.strictEqual(
  document.querySelector("#main-table tbody tr").children[11].textContent,
  "$31,025,889.44", "money toggle to Exact shows dollars and cents");
moneySel.value = "compact";
moneySel.dispatchEvent("change");
assert.strictEqual(
  document.querySelector("#main-table tbody tr").children[11].textContent,
  "$31.03M", "money toggle back to Compact restores the short form");

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
  document.querySelectorAll("#main-table tbody tr").length, 664,
  "reset after the finder restores 664 rows");

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
location.hash = "explore";
assert.strictEqual(location.hash, "#explore", "location.hash stores the hash with its #");
assert.strictEqual(document.getElementById("front-door").hidden, true, "hashchange to #explore opens explore mode");
location.hash = "";
assert.strictEqual(document.getElementById("front-door").hidden, false, "hashchange back to empty shows the front door");

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

/* ---- focus() + document.activeElement (FE4's keyboard wave) ---- */
// NOTE: never assert.strictEqual on a harness element object against a
// value it will not equal — a failing assertion on an El hangs while
// Node builds the failure message (found in U1: the null check below
// failed once mode/tab changes started focusing panels, and the test
// OOM'd instead of reporting). Compare tagName/id strings instead.
// U1 focuses panels during mode/tab changes, so something is usually
// focused by the time this block runs — blur first, then check.
if (document.activeElement) document.activeElement.blur();
assert.strictEqual(document.activeElement, null, "nothing focused after blur");
const qBox = document.getElementById("q");
qBox.focus();
assert.strictEqual(document.activeElement, qBox, "focus() sets document.activeElement");
const csvBtn = document.getElementById("csv-btn");
csvBtn.focus();
assert.strictEqual(document.activeElement, csvBtn, "focus() moves document.activeElement");
csvBtn.blur();
assert.strictEqual(document.activeElement, null, "blur() clears document.activeElement");

/* ---- style + createElement/appendChild/remove ---- */
const styleProbe = document.createElement("div");
styleProbe.style.transitionDelay = "90ms";
assert.strictEqual(styleProbe.style.transitionDelay, "90ms", "style property round-trips");
assert.ok(styleProbe.outerHTML.includes("transition-delay: 90ms"), "style property is serialized into the style attribute");
styleProbe.setAttribute("style", "transition-delay: 45ms");
assert.strictEqual(styleProbe.style.transitionDelay, "45ms", "style attribute parses back into the style object");
const tmpNode = document.createElement("span");
tmpNode.textContent = "probe-node";
document.body.appendChild(tmpNode);
assert.strictEqual(tmpNode.parentNode, document.body, "appendChild parents the node");
assert.ok(document.body.children.indexOf(tmpNode) !== -1, "appendChild lists the node in children");
tmpNode.remove();
assert.strictEqual(tmpNode.parentNode, null, "remove() detaches the node");
assert.ok(document.body.children.indexOf(tmpNode) === -1, "remove() drops the node from children");

/* ---- viewport: width-aware matchMedia + reduced motion ----
 * The page has no JS width breakpoint yet (D1, a later wave), so
 * this asserts the harness capability, not a breakpoint that does
 * not exist. reducedMotion() is the page's own viewport hook. */
window.innerWidth = 500;
assert.strictEqual(window.matchMedia("(max-width: 560px)").matches, true, "560px breakpoint matches at width 500");
assert.strictEqual(window.matchMedia("(min-width: 700px)").matches, false, "700px min-width does not match at width 500");
window.innerWidth = 800;
assert.strictEqual(window.matchMedia("(max-width: 560px)").matches, false, "560px breakpoint does not match at width 800");
assert.strictEqual(window.matchMedia("(min-width: 700px)").matches, true, "700px min-width matches at width 800");
window.__reducedMotion = true;
assert.strictEqual(window.matchMedia("(prefers-reduced-motion: reduce)").matches, true, "reduced-motion query follows the harness flag");
assert.strictEqual(reducedMotion(), true, "page reducedMotion() sees the reduced-motion query");
window.__reducedMotion = false;
assert.strictEqual(window.matchMedia("(prefers-reduced-motion: reduce)").matches, false, "reduced-motion query clears with the flag");
assert.strictEqual(reducedMotion(), false, "page reducedMotion() clears with the flag");
window.innerWidth = 1024;

/* ---- D1: Senate tiles reflow to 5x10 below 560px ---- */
window.innerWidth = 500;
assert.strictEqual(senateCols(), 5, "D1: senateCols is 5 below 560px");
renderComposition();
assert.ok(
  document.getElementById("composition").innerHTML.includes('viewBox="0 0 320 505"'),
  "D1: Senate tiles render 5 wide (320x505) at width 500");
assert.strictEqual(
  (document.getElementById("composition").innerHTML.match(/<g class="tile"/g) || []).length, 50,
  "D1: still 50 state tiles at 5 wide");
window.innerWidth = 1024;
assert.strictEqual(senateCols(), 10, "D1: senateCols is 10 above 560px");
renderComposition();
assert.ok(
  document.getElementById("composition").innerHTML.includes('viewBox="0 0 645 250"'),
  "D1: Senate tiles render 10 wide (645x250) at width 1024");

/* ---- search input (debounce-tolerant) ----
 * The FE2 wave debounces the search input (~150ms) around
 * renderTable, so this assertion waits instead of expecting a
 * synchronous re-render right after dispatching 'input'. */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const searchBox = document.getElementById("q");
  // FE2: search is debounced ~150ms — no re-render before the delay.
  searchBox.value = "Warnock";
  searchBox.dispatchEvent("input");
  assert.strictEqual(
    document.querySelectorAll("#main-table tbody tr").length, 664,
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
    document.querySelectorAll("#main-table tbody tr").length, 664,
    "clearing the search restores 664 rows");
  assert.ok(
    document.getElementById("showing").textContent.includes("Showing 664 of 664"),
    "showing line counts 664 of 664 after clearing the search");

  /* ---- U8: search matches state, district, party, chamber ---- */
  searchBox.value = "michigan";
  searchBox.dispatchEvent("input");
  await sleep(250);
  assert.strictEqual(
    document.querySelectorAll("#main-table tbody tr").length, 21,
    "search 'michigan' finds the 21-person Michigan delegation");
  searchBox.value = "11";
  searchBox.dispatchEvent("input");
  await sleep(250);
  assert.strictEqual(
    document.querySelectorAll("#main-table tbody tr").length, 17,
    "search '11' finds the 17 district-11 members");
  searchBox.value = "senate";
  searchBox.dispatchEvent("input");
  await sleep(250);
  assert.strictEqual(
    document.querySelectorAll("#main-table tbody tr").length, 118,
    "search 'senate' finds the 118 senators");
  // Relevance: a name match outranks a state match — "mi" is 113 rows
  // (name matches plus Michigan, Minnesota, Mississippi, Missouri,
  // Wyoming by state name) and the first is Mike Johnson (name starts
  // with "mi"), not a Michigan member.
  searchBox.value = "mi";
  searchBox.dispatchEvent("input");
  await sleep(250);
  assert.strictEqual(
    document.querySelectorAll("#main-table tbody tr").length, 113,
    "search 'mi' finds 113 rows");
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
    document.querySelectorAll("#main-table tbody tr").length, 664,
    "clearing the search after U8 restores 664 rows");

  /* ---- D1: a resize across the breakpoint re-renders the tiles ---- */
  window.innerWidth = 500;
  global.dispatchEvent("resize");
  await sleep(250);
  assert.ok(
    document.getElementById("composition").innerHTML.includes('viewBox="0 0 320 505"'),
    "D1: resize to 500px reflows the Senate tiles to 5 wide");
  window.innerWidth = 1024;
  global.dispatchEvent("resize");
  await sleep(250);
  assert.ok(
    document.getElementById("composition").innerHTML.includes('viewBox="0 0 645 250"'),
    "D1: resize back to 1024px restores the tiles to 10 wide");
  console.log("Smoke test passed: 664 rows render, all tabs render, detail + CSV + landing work; handlers, bubbling/focus, and viewport covered.");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
