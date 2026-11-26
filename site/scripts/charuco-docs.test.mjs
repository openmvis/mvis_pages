// node --test site/scripts/charuco-docs.test.mjs   (no packages needed)
// The ChArUco docs: the board guide's ALG example matches the board MVIS solved the ALG device pages with
// (openmvis-internal examples/regression/alg_avs111c/cam_imu_bag1.yaml), the screen board and its config agree,
// and the configuration reference lists the ChArUco keys.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = fileURLToPath(new URL('..', import.meta.url));
const DOCS = join(SITE, 'src/content/docs');
const BOARDS = join(SITE, 'public/downloads/boards');
const read = (p) => readFileSync(p, 'utf8');

// key: value pairs of a YAML board block (comments dropped)
const boardKeys = (yaml) => Object.fromEntries(yaml.split('\n')
  .map((l) => l.replace(/#.*/, '').trim()).filter((l) => l.includes(':') && !l.startsWith('board:'))
  .map((l) => l.split(/:\s*/, 2)));

const ALG = { board_type: 'charuco', rows: '9', cols: '14', square_size: '0.04', marker_size: '0.03',
  aruco_dict: 'DICT_5X5_250' };

test('board guide: ChArUco row, and the ALG example is the ALG regression board', () => {
  const guide = read(join(DOCS, 'guides/board-setup.mdx'));
  assert.match(guide, /^\| ChArUco \| `charuco` \| `rows`, `cols` \(\*\*squares\*\*\)/m);
  const sec = guide.split('### Example: the ALG Tech ChArUco board')[1];
  assert.ok(sec, 'the ALG example heading is missing');
  const fence = sec.match(/```yaml title="config\.yaml"\n([\s\S]*?)```/);
  assert.ok(fence, 'the ALG config fence is missing');
  assert.deepEqual(boardKeys(fence[1]), ALG);
  assert.ok(guide.includes('#example-the-alg-tech-charuco-board'), 'section 1 links the example');
});

test('screen board: 2560 x 1440 PNG, config sizes are 144 / 108 px at 43.47 mm per 160 px', () => {
  const png = readFileSync(join(BOARDS, 'charuco_14x9_2560x1440.png'));
  assert.deepEqual([png.readUInt32BE(16), png.readUInt32BE(20)], [2560, 1440]);
  const k = boardKeys(read(join(BOARDS, 'charuco_14x9_2560x1440_mvis.yaml')));
  const mmPerPx = 43.47 / 160 / 1000;
  assert.equal(Number(k.square_size), Number((144 * mmPerPx).toFixed(5)));
  assert.equal(Number(k.marker_size), Number((108 * mmPerPx).toFixed(5)));
  assert.deepEqual([k.board_type, k.rows, k.cols, k.aruco_dict], ['charuco', '9', '14', 'DICT_5X5_250']);
});

test('configuration reference lists the ChArUco keys', () => {
  const conf = read(join(DOCS, 'reference/configuration.mdx'));
  assert.match(conf, /^\| `board_type` \|[^\n]*`charuco`/m);
  for (const key of ['charuco_legacy', 'charuco_refine']) assert.match(conf, new RegExp(`^\\| \`${key}\` \\|`, 'm'));
});
