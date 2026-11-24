// node --test site/scripts/gravity.test.mjs   (no packages needed)
// The local-gravity calculator gives the same g as MVIS for every listed place, and the page is in the sidebar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { normalGravity, biasPercent, siteLine, fmtPercent } from '../src/scripts/gravity.js';

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
const { places } = JSON.parse(read('../src/data/gravity-places.json'));

test('matches MVIS normal_gravity for every listed place', () => {
  assert.equal(places.length, 26);
  for (const p of places) assert.ok(Math.abs(normalGravity(p.latitude_deg, p.altitude_m) - p.g) < 1e-5, p.name);
});

test('known values: equator, pole, Shenzhen bias', () => {
  assert.ok(Math.abs(normalGravity(0) - 9.7803) < 1e-4);
  assert.ok(Math.abs(normalGravity(90) - 9.8322) < 1e-4);
  assert.ok(Number.isNaN(normalGravity(91)));
  assert.equal(fmtPercent(biasPercent(normalGravity(22.54, 20))), '+0.23 %');
  assert.equal(fmtPercent(biasPercent(normalGravity(51.51, 15))), '−0.02 %');
});

test('the config line is what MVIS reads', () => {
  assert.equal(siteLine(-31.4167, 400.4, 'Córdoba, Argentina'),
    'site: {latitude_deg: -31.42, altitude_m: 400, name: "Córdoba, Argentina"}');
  assert.equal(siteLine(47.6, 50), 'site: {latitude_deg: 47.60, altitude_m: 50}');
});

test('the page exists and the sidebar links it after Configuration', () => {
  assert.ok(existsSync(new URL('../src/content/docs/reference/local-gravity.mdx', import.meta.url)));
  assert.match(read('../astro.config.mjs'),
    /\{ label: 'Configuration', link: '\/reference\/configuration\/' \},\s*\{ label: 'Local gravity', link: '\/reference\/local-gravity\/' \}/);
});
