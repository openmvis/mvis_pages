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

// --- City search (public/data/gravity-cities.json, GeoNames) ---
import { fold, cityLabel, searchPlaces } from '../src/scripts/gravity.js';
import { statSync } from 'node:fs';

const CITIES_PATH = new URL('../public/data/gravity-cities.json', import.meta.url);
const cities = JSON.parse(readFileSync(CITIES_PATH, 'utf8'));
const labels = (q, n = 8) => searchPlaces(q, places, cities, n).map((m) => m.label);

test('fold drops case, accents and apostrophes', () => {
  assert.equal(fold('Zürich'), 'zurich');
  assert.equal(fold('São Paulo'), 'sao paulo');
  assert.equal(fold('Xi’an'), 'xian');
  assert.equal(fold('Diyarbakır'), 'diyarbakir');
  assert.equal(fold('  Köln  '), 'koln');
});

test('the shipped city list: GeoNames, sorted rows of valid numbers, small enough to fetch', () => {
  assert.match(cities.source, /GeoNames/);
  assert.ok(cities.cities.length > 30000, String(cities.cities.length));
  assert.ok(statSync(CITIES_PATH).size < 1.6e6);
  for (const [name, cc, region, lat, alt] of cities.cities) {
    assert.ok(name && cc in cities.countries && (!region || region in cities.regions), name);
    assert.ok(lat >= -90 && lat <= 90 && Number.isInteger(alt) && alt > -500 && alt < 6000, name);
  }
});

test('search: curated places first, then the biggest cities; a country after the comma narrows it', () => {
  assert.deepEqual(labels('cordoba', 3), ['Córdoba, Argentina', 'Córdoba, Andalusia, Spain', 'Córdoba, Veracruz, Mexico']);
  assert.equal(labels('Cordoba, spain', 1)[0], 'Córdoba, Andalusia, Spain');
  assert.equal(labels('newark', 2)[1], 'Newark, New Jersey, United States');
  assert.equal(labels('koln')[0], 'Köln, North Rhine-Westphalia, Germany');
  assert.equal(labels('sao paulo')[0], 'São Paulo');
  assert.deepEqual(labels(''), []);
});

test('search: one entry per place (no curated twin, no city districts)', () => {
  assert.deepEqual(labels('seattle'), ['Seattle']);
  assert.ok(!labels('zurich').some((l) => /Kreis/.test(l)), labels('zurich').join(' | '));
});

test('a picked city gives the copy line with its name and the same g as MVIS', () => {
  const [denver] = searchPlaces('denver, united states', places, cities, 1);
  assert.equal(denver.label, 'Denver, Colorado, United States');
  assert.ok(Math.abs(normalGravity(denver.latitude_deg, denver.altitude_m) - 9.7965) < 2e-4);
  assert.match(copyText(denver.latitude_deg, denver.altitude_m, denver.label),
    /^gravity: 9\.79\d\d   # m\/s², Denver, Colorado, United States\nsite: \{latitude_deg: 39\.74, altitude_m: \d+, name: "Denver, Colorado, United States"\}$/);
});

test('cityLabel leaves out a region that repeats the name', () => {
  const list = { countries: { SG: 'Singapore', DE: 'Germany' }, regions: { 'SG.01': 'Singapore', 'DE.16': 'Berlin' } };
  assert.equal(cityLabel(['Singapore', 'SG', 'SG.01', 1.29, 15], list), 'Singapore');
  assert.equal(cityLabel(['Berlin', 'DE', 'DE.16', 52.52, 74], list), 'Berlin, Germany');
});

test('the calculator searches, fetches the list on first use, and offers the location button', () => {
  const c = read('../src/components/GravityCalculator.astro');
  assert.match(c, /searchPlaces\(typed, data\.places, all\)/);
  assert.match(c, /fetch\(CITIES\)/);
  assert.match(c, /getCurrentPosition/);
  assert.match(read('../src/content/docs/reference/local-gravity.mdx'), /\[GeoNames\]\(https:\/\/www\.geonames\.org\/\) \(CC BY 4\.0\)/);
});
