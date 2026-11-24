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

// The config line to copy. Coordinates to 2 decimals (about 1 km), altitude to the metre.
export function siteLine(latitudeDeg, altitudeM, name = '') {
  const label = name ? `, name: "${name.replace(/"/g, "'")}"` : '';
  return `site: {latitude_deg: ${(+latitudeDeg).toFixed(2)}, altitude_m: ${Math.round(+altitudeM)}${label}}`;
}

export const fmtPercent = (p) => `${p >= 0.005 ? '+' : p <= -0.005 ? '−' : ''}${Math.abs(p).toFixed(2)} %`;
