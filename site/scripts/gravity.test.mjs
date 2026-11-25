// node --test site/scripts/gravity.test.mjs   (no packages needed)
// The local-gravity calculator gives the same g as MVIS for every listed place, and the page is in the sidebar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { normalGravity, biasPercent, gravityLine, siteLine, fmtPercent, copyText } from '../src/scripts/gravity.js';

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
const { places } = JSON.parse(read('../src/data/gravity-places.json'));

test('matches MVIS normal_gravity for every listed place', () => {
  assert.equal(places.length, 27);
  for (const p of places) assert.ok(Math.abs(normalGravity(p.latitude_deg, p.altitude_m) - p.g) < 1e-5, p.name);
});

test('known values: equator, pole, Shenzhen bias', () => {
  assert.ok(Math.abs(normalGravity(0) - 9.7803) < 1e-4);
  assert.ok(Math.abs(normalGravity(90) - 9.8322) < 1e-4);
  assert.ok(Number.isNaN(normalGravity(91)));
  assert.equal(fmtPercent(biasPercent(normalGravity(22.54, 20))), '+0.23 %');
  assert.equal(fmtPercent(biasPercent(normalGravity(51.51, 15))), '−0.02 %');
});

test('the gravity line comes first: 4 decimals, the place as a comment', () => {
  assert.equal(gravityLine(normalGravity(39.68, 40), 'Newark, Delaware'), 'gravity: 9.8013   # m/s², Newark, Delaware');
  assert.equal(gravityLine(normalGravity(22.54, 20), 'Shenzhen'), 'gravity: 9.7879   # m/s², Shenzhen');
  assert.equal(gravityLine(9.80845), 'gravity: 9.8085   # m/s²');
});

test('the page leads with the gravity line and the calculator copies gravity, then site', () => {
  const page = read('../src/content/docs/reference/local-gravity.mdx');
  assert.match(page, /```yaml[^\n]*\ngravity: 9\.8013   # m\/s², Newark, Delaware\n```/);
  assert.ok(page.indexOf('gravity: 9.8013') < page.indexOf('site: {'));
});

test('the copy box gives the gravity line, then the site line; no place picked gives a name placeholder', () => {
  assert.equal(copyText(39.68, 40, 'Newark, Delaware'),
    'gravity: 9.8013   # m/s², Newark, Delaware\nsite: {latitude_deg: 39.68, altitude_m: 40, name: "Newark, Delaware"}');
  assert.equal(copyText(47.61, 50), 'gravity: 9.8084   # m/s², your place\nsite: {latitude_deg: 47.61, altitude_m: 50, name: "your place"}');
  assert.equal(copyText(91, 0), '');
  assert.match(read('../src/components/GravityCalculator.astro'), /copyText\(lat, alt, place\)/);
});

test('Dübendorf (UZH-FPV) is listed, as in the MVIS doc', () => {
  const p = places.find((x) => x.name === 'Dübendorf (UZH-FPV)');
  assert.ok(p && p.latitude_deg === 47.4 && p.altitude_m === 440 && p.g.toFixed(4) === '9.8070');
});

test('the site line is what MVIS reads', () => {
  assert.equal(siteLine(-31.4167, 400.4, 'Córdoba, Argentina'),
    'site: {latitude_deg: -31.42, altitude_m: 400, name: "Córdoba, Argentina"}');
  assert.equal(siteLine(47.6, 50), 'site: {latitude_deg: 47.60, altitude_m: 50}');
});

test('the page exists and the sidebar links it after Configuration', () => {
  assert.ok(existsSync(new URL('../src/content/docs/reference/local-gravity.mdx', import.meta.url)));
  assert.match(read('../astro.config.mjs'),
    /\{ label: 'Configuration', link: '\/reference\/configuration\/' \},\s*\{ label: 'Local gravity', link: '\/reference\/local-gravity\/' \}/);
});
