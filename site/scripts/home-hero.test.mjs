// node --test site/scripts/home-hero.test.mjs   (no packages needed)
// The homepage hero's decisions (site/src/scripts/home-hero.js): which recording plays next, which files load,
// which camera is outlined, what the readouts show, and how a camera tile is kept on the hero's clock.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as H from '../src/scripts/home-hero.js';

const RIGS = JSON.parse(readFileSync(new URL('../public/media/hero/rigs.json', import.meta.url), 'utf8')).rigs;

test('recordings play in rigs.json order and wrap to the first', () => {
  const { order, rigs } = H.indexRigs(RIGS);
  assert.deepEqual(order, RIGS.map((r) => r.key));
  assert.equal(rigs[order[1]], RIGS[1]);
  for (let i = 0; i < order.length; i++) assert.equal(H.nextKey(order, order[i]), order[(i + 1) % order.length]);
  assert.equal(H.nextKey(['a'], 'a'), 'a');
});

test('media URLs carry the content hash, 0 when unknown', () => {
  assert.equal(H.mediaUrl('hero_x.mp4', { 'hero_x.mp4': 'abc' }), '/media/hero/hero_x.mp4?v=abc');
  assert.equal(H.mediaUrl('hero_x.mp4', {}), '/media/hero/hero_x.mp4?v=0');
});

test('the 1920 px loop only on a wide screen with a normal connection', () => {
  assert.equal(H.isWide(1100), true); assert.equal(H.isWide(1099), false);
  assert.equal(H.heroFile('k', true, false), 'hero_k.mp4');
  assert.equal(H.heroFile('k', true, true), 'hero_k_960.mp4');        // data saver / 2g
  assert.equal(H.heroFile('k', false, false), 'hero_k_960.mp4');
  assert.equal(H.heroPosterFile('k', true), 'hero_k.jpg'); assert.equal(H.heroPosterFile('k', false), 'hero_k_960.jpg');
  assert.equal(H.tileBase('k', 'cam1', false), 'k_cam1'); assert.equal(H.tileBase('k', 'cam1', true), 'k_cam1_240');
});

test('every rig in rigs.json resolves to files the media folder has', () => {
  const dir = new URL('../public/media/hero/', import.meta.url);
  const has = (f) => { try { readFileSync(new URL(f, dir)); return true; } catch { return false; } };
  for (const r of RIGS) {
    for (const wide of [true, false]) {
      assert.ok(has(H.heroFile(r.key, wide, false)), H.heroFile(r.key, wide, false));
      assert.ok(has(H.heroPosterFile(r.key, wide)), H.heroPosterFile(r.key, wide));
    }
    for (const c of r.tiles) for (const small of [true, false]) {
      for (const ext of ['.mp4', '.jpg']) assert.ok(has(H.tileBase(r.key, c[0], small) + ext), H.tileBase(r.key, c[0], small) + ext);
    }
  }
});

test('readouts: the rig field, the caption, and null leaves the element', () => {
  const rig = { caption: 'cap', rms: '0.25 <small>px</small>', td: null };
  assert.equal(H.readoutValue(rig, 'caption'), 'cap');
  assert.equal(H.readoutValue(rig, 'rms'), '0.25 <small>px</small>');
  assert.equal(H.readoutValue(rig, 'td'), null); assert.equal(H.readoutValue(rig, 'missing'), null);
});

test('hero clock: the poster moment before the first play, the video time after', () => {
  assert.deepEqual(H.heroClock({ paused: true, currentTime: 0, duration: 15, loop: 15 }), { d: 15, atPoster: true, t: 9 });
  assert.deepEqual(H.heroClock({ paused: true, currentTime: 4, duration: 15, loop: 15 }), { d: 15, atPoster: false, t: 4 });
  assert.equal(H.heroClock({ paused: false, currentTime: 0, duration: NaN, loop: 15 }).d, 15);   // metadata not loaded yet
  assert.equal(H.heroHeld(false, 4), false); assert.equal(H.heroHeld(false, 2), true); assert.equal(H.heroHeld(true, 4), true);
});

test('each camera is outlined for one cycle in turn', () => {
  assert.deepEqual([0, 4.9, 5, 10, 15, 20].map((t) => H.liveIndex(t, 5, 3)), [0, 0, 1, 2, 0, 1]);
});

test('sync: seek on a large drift (aimed ahead), nudge a small one, reset, or leave alone', () => {
  const base = { t: 5, d: 15, lat: 0.2, now: 10000, lastSeek: 0, rate: 1 };
  assert.deepEqual(H.syncAction({ ...base, ct: 4 }), { seek: 5.2 });
  assert.deepEqual(H.syncAction({ ...base, ct: 4, lastSeek: 9500 }), { rate: 1.25 });        // in cooldown: nudge only
  assert.deepEqual(H.syncAction({ ...base, ct: 4, t: 14.5 }), { rate: 1.25 });               // last second: no seek
  assert.ok(Math.abs(H.syncAction({ ...base, ct: 5.1 }).rate - 0.9) < 1e-9);               // ahead: slow down
  assert.ok(Math.abs(H.syncAction({ ...base, ct: 4.9 }).rate - 1.1) < 1e-9);               // behind: speed up
  assert.deepEqual(H.syncAction({ ...base, ct: 5.02, rate: 1.1 }), { rate: 1 });
  assert.equal(H.syncAction({ ...base, ct: 5.02 }), null);
  assert.deepEqual(H.syncAction({ ...base, ct: 14, t: 3, d: 15, lat: 20 }), { seek: 14.95 });  // seek never past the end
});

test('watchdog: reload a stalled or broken tile, spaced out and limited', () => {
  const s = { error: null, now: 10000, lastAdvance: 8000, lastRecover: 0, recoveries: 0, t: 5, d: 15 };
  assert.equal(H.shouldRecover(s), true);                                    // 2 s without advancing
  assert.equal(H.shouldRecover({ ...s, lastAdvance: 9000 }), false);         // 1 s: not yet
  assert.equal(H.shouldRecover({ ...s, lastAdvance: 9900, error: { code: 3 } }), true);
  assert.equal(H.shouldRecover({ ...s, lastRecover: 8000 }), false);         // reloaded 2 s ago
  assert.equal(H.shouldRecover({ ...s, recoveries: 6 }), false);
  assert.equal(H.shouldRecover({ ...s, t: 14.5 }), false);                   // the loop is about to end
});

test('seek latency: running mean, capped at 1.5 s', () => {
  assert.equal(H.seekLatency(0.15, 250), 0.2);
  assert.equal(H.seekLatency(1.4, 5000), 1.5);
});

test('wide layout: tile columns and widths', () => {
  const four = RIGS.find((r) => r.tiles.length >= 4), two = RIGS.find((r) => r.tiles.length === 2);
  const g4 = H.tileGrid(four.tiles, 800, 90, 1440), g2 = H.tileGrid(two.tiles, 800, 90, 1440);
  assert.equal(g4.cols, 2); assert.equal(g2.cols, 1);
  for (const g of [g4, g2]) assert.ok(g.colW >= 110 && g.colW <= 240, String(g.colW));
  assert.equal(H.tileGrid(two.tiles, 2000, 90, 600).colW, 144);             // capped at 24 % of a 600 px viewport
});

test('wide layout: the loop is 16:9 and starts no further left than minLeft', () => {
  const big = H.videoBox({ heroH: 800, barH: 90, right: 1200, minLeft: 0 });   // full height: 800 - 90 - 2 x 24
  assert.deepEqual(big, { left: 23, top: 24, width: 1177, height: 662 });
  const fit = H.videoBox({ heroH: 800, barH: 90, right: 1000, minLeft: 400 });
  assert.equal(fit.left, 400); assert.equal(fit.width, 600); assert.equal(fit.height, 338);
  assert.equal(fit.top, Math.round((800 - 90 - 337.5) / 2));
});

test('preload: the next loop, and its tiles only on a wide screen', () => {
  const r = { tiles: [['cam0'], ['cam1']] };
  assert.deepEqual(H.preloadFiles('k', r, true, false), ['hero_k.mp4', 'k_cam0.mp4', 'k_cam1.mp4']);
  assert.deepEqual(H.preloadFiles('k', r, false, false), ['hero_k_960.mp4']);
});
