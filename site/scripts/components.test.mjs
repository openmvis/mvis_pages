// node --test site/scripts/components.test.mjs   (no packages needed)
// The Cameras and IMUs page and the card labels read generated data (python/mvis_site/components.py): every device
// card has its labels, components.json lists exactly the Device wiki's pages, and the page sits in the sidebar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';

const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
const C = JSON.parse(read('../src/data/components.json'));
const NAV = JSON.parse(read('../src/data/sensor-nav.json'));
const SENSORS = readdirSync(new URL('../src/data/sensors/', import.meta.url)).filter((f) => f.endsWith('.json'));

test('every device card has a label per camera and IMU part, as html', () => {
  for (const f of SENSORS) {
    const card = JSON.parse(read(`../src/data/sensors/${f}`)).card;
    for (const kind of ['cameras', 'imus']) {
      assert.ok(card.components?.[kind]?.length, `${f}: no ${kind} labels`);
      for (const x of card.components[kind]) assert.match(x.html, /^<span class="cl (cam|imu)/, `${f}: ${kind} label`);
    }
  }
});

test('components.json lists the sidebar devices once each, in sidebar order', () => {
  assert.deepEqual(C.devices.map((d) => d.href), NAV.map((n) => n.link));
});

test('the tiles count devices only and add up', () => {
  for (const kind of ['cameras', 'imus']) {
    const k = C.counts[kind];
    const parts = C.devices.flatMap((d) => d[kind]);
    assert.equal(k.total, parts.reduce((n, x) => n + x.count, 0));
    assert.equal(k.total, k.not_known + Object.values(k.by_maker).reduce((a, b) => a + b, 0));
  }
});

test('the page exists and the sidebar links it after Overview', () => {
  assert.ok(existsSync(new URL('../src/content/docs/devices/components.mdx', import.meta.url)));
  assert.match(read('../astro.config.mjs'), /\{ label: 'Overview', link: '\/devices\/' \}, \{ label: 'Cameras and IMUs', link: '\/devices\/components\/' \}/);
});

test('every chip maker on the page has a bar colour in both themes', () => {
  const css = read('../src/styles/custom.css');
  for (const m of C.makers) assert.equal(css.split(`--mk-${m.key}:`).length - 1, 3, `--mk-${m.key} needs light, dark and auto-dark values`);
});
