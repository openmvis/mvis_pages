// Local gravity for the /reference/local-gravity/ calculator. Same formula as MVIS mvis.core.gravity.normal_gravity:
// WGS84 normal gravity (Somigliana) minus the free-air term. Pure functions; site/scripts/gravity.test.mjs checks them
// against the values MVIS computes (src/data/gravity-places.json).

export const STANDARD_MVIS = 9.81;   // what a cam-IMU solve uses without `gravity:` or `site:`

export function normalGravity(latitudeDeg, altitudeM = 0) {
  if (!(latitudeDeg >= -90 && latitudeDeg <= 90)) return NaN;
  const s2 = Math.sin((latitudeDeg * Math.PI) / 180) ** 2;
  const g0 = (9.7803253359 * (1 + 0.00193185265241 * s2)) / Math.sqrt(1 - 0.00669437999013 * s2);
  return g0 - 3.086e-6 * altitudeM;
}

// How far the accelerometer scale reads off if the run keeps 9.81, in percent (+ = reads high).
export const biasPercent = (g) => 100 * (STANDARD_MVIS / g - 1);

// The gravity line to copy: the value to 4 decimals, the place as a comment.
export function gravityLine(g, place = '') {
  return `gravity: ${(+g).toFixed(4)}   # m/s²${place ? `, ${place}` : ''}`;
}

// The optional site line under it (the report then names the place). Coordinates to 2 decimals (about 1 km), altitude to the metre.
export function siteLine(latitudeDeg, altitudeM, name = '') {
  const label = name ? `, name: "${name.replace(/"/g, "'")}"` : '';
  return `site: {latitude_deg: ${(+latitudeDeg).toFixed(2)}, altitude_m: ${Math.round(+altitudeM)}${label}}`;
}

export const fmtPercent = (p) => `${p >= 0.005 ? '+' : p <= -0.005 ? '−' : ''}${Math.abs(p).toFixed(2)} %`;

export const PLACE_PLACEHOLDER = 'your place';

// The copy box: the gravity line, then the site line. Without a picked place both name a placeholder to replace.
export function copyText(latitudeDeg, altitudeM, place = '') {
  const g = normalGravity(latitudeDeg, altitudeM);
  if (!Number.isFinite(g)) return '';
  const name = place || PLACE_PLACEHOLDER;
  return `${gravityLine(g, name)}\n${siteLine(latitudeDeg, altitudeM, name)}`;
}

// --- City search (public/data/gravity-cities.json, GeoNames; rows [name, country code, region code, lat, alt],
// largest population first). Pure functions; the component fetches the list on first use.

const FOLD = { 'ı': 'i', 'ß': 'ss', 'ø': 'o', 'æ': 'ae', 'œ': 'oe', 'đ': 'd', 'ł': 'l', 'þ': 'th' };
// Lower case, accents and apostrophes dropped: "Zürich" -> "zurich", "Xi’an" -> "xian".
export function fold(s) {
  return String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[ıßøæœđłþ]/g, (c) => FOLD[c]).replace(/['’‘`]/g, '').replace(/\s+/g, ' ').trim();
}

// "Córdoba, Andalusia, Spain": a region or country that repeats the name is left out ("Singapore", "Berlin, Germany").
export function cityLabel(row, list) {
  const [name, cc, region] = row;
  const parts = [name];
  for (const x of [list.regions[region] || '', list.countries[cc] || cc]) {
    if (x && !parts.some((p) => fold(p) === fold(x))) parts.push(x);
  }
  return parts.join(', ');
}

// Up to `limit` matches for what was typed: the curated places first, then cities whose name starts with it, then
// cities with a word that starts with it, each in population order. Text after a comma narrows by region or
// country ("cordoba, spain"). A place is not listed twice: a row whose name, without a bracketed part ("Zürich
// (Kreis 11)"), matches one already listed within 0.2° of latitude is skipped. Each match: {label, latitude_deg,
// altitude_m}.
const FOLDED = new WeakMap();   // list -> folded names, built once per list
const base = (folded) => folded.replace(/\s*\(.*$/, '').split(',')[0].trim();

export function searchPlaces(query, places, list, limit = 8) {
  const [q, where = ''] = fold(query).split(/\s*,\s*/, 2);
  if (!q) return [];
  const out = [];
  const seen = [];   // [base name, latitude] of what is listed
  const add = (label, lat, alt, name) => {
    out.push({ label, latitude_deg: lat, altitude_m: alt });
    seen.push([base(name), lat]);
  };
  for (const p of places) {
    const n = fold(p.name);
    if (out.length < limit && n.startsWith(q) && (!where || n.includes(where))) add(p.name, p.latitude_deg, p.altitude_m, n);
  }
  if (!list) return out;
  if (!FOLDED.has(list)) FOLDED.set(list, list.cities.map((row) => fold(row[0])));
  const names = FOLDED.get(list);
  const inWhere = (row) => !where || fold(list.countries[row[1]] || '').startsWith(where) ||
    fold(list.regions[row[2]] || '').startsWith(where) || fold(row[1]) === where;
  const dup = (n, lat) => seen.some(([b, l]) => b === base(n) && Math.abs(l - lat) < 0.2);
  for (const pass of [(n) => n.startsWith(q), (n) => !n.startsWith(q) && n.includes(' ' + q)]) {
    for (let i = 0; i < names.length && out.length < limit; i++) {
      const row = list.cities[i], n = names[i];
      if (pass(n) && inWhere(row) && !dup(n, row[3])) add(cityLabel(row, list), row[3], row[4], n);
    }
  }
  return out;
}
