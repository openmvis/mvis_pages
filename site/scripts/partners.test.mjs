// node --test site/scripts/partners.test.mjs   (no packages needed)
// The partner list (src/data/partners.ts, read as text: it imports images) feeds the Acknowledgements cards and the
// homepage band. Its image files must exist, and its links must be web, mail or site links.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const SRC = readFileSync(new URL('../src/data/partners.ts', import.meta.url), 'utf8');

test('every imported partner image exists', () => {
  const files = [...SRC.matchAll(/^import \w+ from '(\.\.\/assets\/partners\/[^']+)';$/gm)].map((m) => m[1]);
  assert.ok(files.length >= 5, 'partner image imports not found');
  for (const f of files) assert.ok(existsSync(new URL(`../src/data/${f}`, import.meta.url)), `missing ${f}`);
});

test('every link is https, mailto or a site path', () => {
  const hrefs = [...SRC.matchAll(/(?:href|site): '([^']*)'/g), ...SRC.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
  assert.ok(hrefs.length > 10, 'links not found');
  for (const h of hrefs) assert.match(h, /^(https:\/\/|mailto:|\/)/, h);
});

test('a name card repeats its partner\'s email as text', () => {
  const cards = SRC.split(/\n  \{\n/).filter((b) => b.includes('card: {'));
  assert.ok(cards.length >= 1, 'no partner with a name card');
  for (const b of cards) {
    for (const [, mail] of b.matchAll(/contact: \[[^\]]*mailto:([^']+)'/g)) assert.ok(b.includes(`text: '${mail}'`), `${mail} not in card lines`);
    assert.match(b, /front: \w+, back: \w+/, 'card needs both sides');
  }
});
