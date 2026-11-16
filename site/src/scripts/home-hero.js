// Homepage hero (HomeHero.astro): the decisions the player makes, as pure functions so they can be tested
// with `node --test` (site/scripts/home-hero.test.mjs). The component keeps the DOM and video wiring and calls
// these. Formulas are the ones the inline script used; the browser suites (site/scripts/hero_sync_check.py,
// hero_labels_check.py) check the assembled player.

export const WIDE_MIN_PX = 1100;          // wide layout from this viewport width
export const POSTER_FRACTION = 0.6;       // the poster shows the loop at 60 %
export const SEEK_DRIFT = 0.5;            // companion drift (s) above which it seeks instead of nudging its rate
export const SEEK_COOLDOWN = 1000;        // ms between seeks of one companion
export const NUDGE_DRIFT = 0.04;          // below this drift (s) the rate goes back to 1
export const STALL_MS = 1500;             // a companion that has not advanced this long is stalled
export const RECOVER_GAP_MS = 3000;       // ms between reloads of one companion
export const MAX_RECOVERIES = 6;          // reloads per companion
export const PRELOAD_AT = 0.6;            // warm the next recording once the loop is 60 % through

/** The media URL with its content hash, so a changed file is never served stale. */
export function mediaUrl(file, hashes) {
  return '/media/hero/' + file + '?v=' + ((hashes && hashes[file]) || '0');
}

export function isWide(innerWidth) {
  return innerWidth >= WIDE_MIN_PX;
}

/** The loop to play: the 1920 px one on a wide screen with a normal connection, else the 960 px one. */
export function heroFile(key, wide, lean) {
  return (wide && !lean) ? 'hero_' + key + '.mp4' : 'hero_' + key + '_960.mp4';
}

export function heroPosterFile(key, wide) {
  return wide ? 'hero_' + key + '.jpg' : 'hero_' + key + '_960.jpg';
}

/** A camera tile's file stem: the 400 px tile, or the 240 px one in the phone Details strip. */
export function tileBase(key, cam, small) {
  return key + '_' + cam + (small ? '_240' : '');
}

/** The recording after `current`, wrapping to the first. */
export function nextKey(order, current) {
  return order[(order.indexOf(current) + 1) % order.length];
}

/** The order of rigs.json and a key -> rig map. */
export function indexRigs(rigData) {
  const order = [], rigs = {};
  for (const r of rigData) { order.push(r.key); rigs[r.key] = r; }
  return { order, rigs };
}

/** The value a readout element (data-k) shows for a rig; null leaves the element as it is. */
export function readoutValue(rig, k) {
  const v = k === 'caption' ? rig.caption : rig[k];
  return v == null ? null : v;
}

/** The hero clock: at the poster (paused, never started) the loop's poster moment, else the video time. */
export function heroClock({ paused, currentTime, duration, loop }) {
  const d = duration || loop;
  const atPoster = paused && !(currentTime > 0);
  return { d, atPoster, t: atPoster ? POSTER_FRACTION * d : (currentTime || 0) };
}

/** Companions wait while the hero is paused or still buffering. */
export function heroHeld(paused, readyState) {
  return paused || readyState < 3;
}

/** The camera outlined in 3-D at loop time t: each camera for `cycle` seconds in turn. */
export function liveIndex(t, cycle, n) {
  return Math.floor(t / cycle) % n;
}

/**
 * Keep one companion on the hero clock. Returns {seek: time} for one seek aimed ahead by the measured seek
 * latency (at most once per SEEK_COOLDOWN, never in the last second of the loop), {rate: r} to nudge it
 * (0.8–1.25), {rate: 1} to reset a nudged one, or null to leave it alone.
 */
export function syncAction({ ct, t, d, lat, now, lastSeek, rate }) {
  const drift = (ct || 0) - t;
  if (Math.abs(drift) > SEEK_DRIFT && now - lastSeek > SEEK_COOLDOWN && t < d - 1) {
    return { seek: Math.min(d - 0.05, t + lat) };
  }
  if (Math.abs(drift) > NUDGE_DRIFT) return { rate: Math.max(0.8, Math.min(1.25, 1 - drift)) };
  if (rate !== 1) return { rate: 1 };
  return null;
}

/** Whether a companion that stopped advancing (or errored) should be reloaded now. */
export function shouldRecover({ error, now, lastAdvance, lastRecover, recoveries, t, d }) {
  return (!!error || now - lastAdvance > STALL_MS) && now - lastRecover > RECOVER_GAP_MS
    && recoveries < MAX_RECOVERIES && t < d - 1;
}

/** The seek-latency estimate after a seek that took `ms`: a running mean, capped at 1.5 s. */
export function seekLatency(lat, ms) {
  return Math.min(1.5, 0.5 * lat + 0.5 * ms / 1000);
}

/**
 * Wide layout, tile column: 1 column (2 from four cameras), its width from the height left for the rows
 * (each row as tall as its tallest tile), within 110–240 px and 24 % of the viewport.
 * tiles: [name, label, shutter, colour, width, height], as in rigs.json.
 */
export function tileGrid(tiles, heroH, barH, innerWidth) {
  const cols = tiles.length >= 4 ? 2 : 1, rows = Math.ceil(tiles.length / cols), pad = 24;
  const avail = heroH - barH - 2 * pad;
  let aspectSum = 0;
  for (let r = 0; r < rows; r++) {
    let m = 0;
    for (let c = 0; c < cols; c++) { const cam = tiles[r * cols + c]; if (cam) m = Math.max(m, cam[5] / cam[4]); }
    aspectSum += m;
  }
  let colW = (avail - rows * 24 - (rows - 1) * 10) / aspectSum;
  colW = Math.max(110, Math.min(colW, 240, (innerWidth * 0.24 - (cols - 1) * 10) / cols));
  return { cols, rows, colW: Math.floor(colW) };
}

/**
 * Wide layout, the loop's box: 16:9, as tall as the hero minus the bar, right edge at `right`, shrunk so it
 * starts no further left than `minLeft`, centred vertically. All in px relative to the hero.
 */
export function videoBox({ heroH, barH, right, minLeft }) {
  const pad = 24;
  let h = heroH - barH - 2 * pad, w = h * 16 / 9;
  if (right - w < minLeft) { w = right - minLeft; h = w * 9 / 16; }
  return { left: Math.round(right - w), top: Math.round((heroH - barH - h) / 2), width: Math.round(w), height: Math.round(h) };
}

/** The files to warm for the next recording: its loop, and on a wide screen its 400 px tiles. */
export function preloadFiles(key, rig, wide, lean) {
  return [heroFile(key, wide, lean)].concat(wide ? rig.tiles.map((c) => key + '_' + c[0] + '.mp4') : []);
}
