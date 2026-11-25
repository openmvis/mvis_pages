// node --test site/scripts/guides-gravity.test.mjs   (no packages needed)
// The guides set the local gravity the way the Local gravity page says, link that page, and the hosted guide reports
// match the guide's config and carry no path from the machine they ran on.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = fileURLToPath(new URL('..', import.meta.url));
const DOCS = join(SITE, 'src/content/docs');
const MEDIA = join(SITE, 'public/media/guides');
const read = (p) => readFileSync(p, 'utf8');
const NEWARK = 'gravity: 9.8013   # m/s², Newark, Delaware';
const PAGE = '](/reference/local-gravity/)';

const walk = (dir) => readdirSync(dir, { withFileTypes: true })
  .flatMap((e) => (e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)]));

test('guide 4: the full config starts with the Newark gravity line, and the bullet links the Local gravity page', () => {
  const guide = read(join(DOCS, 'guides/camera-imu-calibration.mdx'));
  const full = guide.match(/```yaml title="virig_4imus_4cams_cam_imu\.yaml" \{[^}]*\}\n([^\n]*)\n/);
  assert.ok(full, 'the highlighted full config fence is missing');
  assert.equal(full[1], NEWARK);
  assert.ok(guide.includes(`[Local gravity${PAGE}`));
});

test('guide 2 and the quickstart link the Local gravity page', () => {
  for (const f of ['guides/calibration-motion.mdx', 'getting-started/quickstart.mdx']) {
    assert.ok(read(join(DOCS, f)).includes(`[Local gravity${PAGE}`), f);
  }
});

test('no page sends readers to the GitHub gravity doc in place of the site page', () => {
  const bad = walk(DOCS).filter((f) => /\.mdx?$/.test(f) && /github\.com\/openmvis\/openmvis\/[^)\s]*local_gravity\.md/.test(read(f)));
  assert.deepEqual(bad, []);
});

test('hosted guide files carry no local path', () => {
  const text = walk(MEDIA).filter((f) => /\.(html|txt|yaml|json)$/.test(f));
  assert.ok(text.length >= 5);
  for (const f of text) assert.doesNotMatch(read(f), /\/home\/|\/Users\/|[A-Z]:\\Users\\/, f);
});

test('the hosted cam-IMU and round-trip reports used the guide config gravity', () => {
  for (const f of ['cam_imu_report.html', 'roundtrip_recal_report.html']) {
    const html = read(join(MEDIA, 'virig-4imus-4cams', f));
    assert.ok(html.includes('9.8013 m/s² — set in config for Newark, Delaware'), f);
  }
  // the cam-IMU report echoes the guide's config as written; the round-trip recal config is rewritten without comments
  assert.ok(read(join(MEDIA, 'virig-4imus-4cams/cam_imu_report.html')).includes(NEWARK));
});
