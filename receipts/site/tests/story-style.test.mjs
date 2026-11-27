// Pin the story's card behaviour in the shipped style.css, so the
// spacing fixes survive a restyle:
//
// - The card switch is instant: no opacity transition on
//   `.scrolly-step .card`, or the outgoing card stays partly visible
//   while the incoming one fades in and two cards show at once.
// - The card sits at the top of its step (`align-items:flex-start`):
//   a step activates when its top crosses the viewport middle
//   (Scrollama offset 0.5), so a centred card only arrives near the
//   viewport bottom and leaves a long white stretch below the pinned
//   graphic. Top-aligned, it appears at the middle on activation.
// - The fallbacks hold: without JS every card stays visible (the
//   opacity:0 hiding rule is scoped under `html.js`), as does static
//   mode.
//
// Run: node --test "receipts/site/tests/*.test.mjs"

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const CSS = readFileSync(
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'templates', 'style.css'),
  'utf8',
);

function rule(selector) {
  const m = CSS.match(new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\{([^}]*)\\}'));
  assert.ok(m, 'missing rule: ' + selector);
  return m[1];
}

test('story cards switch instantly: no opacity transition on the card', () => {
  assert.doesNotMatch(rule('.scrolly-step .card'), /transition\s*:/);
});

test('story cards sit at the top of their step, not centred in it', () => {
  assert.match(rule('.scrolly-step'), /align-items\s*:\s*flex-start/);
});

test('story cards stay visible without JS: hiding is scoped under html.js', () => {
  assert.match(rule('.scrolly-step .card'), /opacity\s*:\s*1/);
  assert.match(rule('html.js .scrolly-step .card'), /opacity\s*:\s*0/);
});

test('story cards stay visible in static mode', () => {
  assert.match(rule('.scrolly.static .scrolly-step .card'), /opacity\s*:\s*1/);
});
