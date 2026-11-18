// node --test site/scripts/llms.test.mjs   (no packages needed)
// The llms.txt / llms-full.txt / sitemap / FAQPage writers in llms.mjs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as L from './llms.mjs';

const page = (body) => `<html><head><title>T | OpenMVIS</title><meta name="description" content="D &amp; more"/></head><body>`
  + `<main><div class="sl-markdown-content">${body}</div><footer>Edit page <time datetime="2026-11-01T00:00:00.000Z">x</time></footer></main></body></html>`;
const h3 = (id, q) => `<div class="sl-heading-wrapper level-h3"><h3 id="${id}">${q}</h3><a class="sl-anchor-link" href="#${id}"><span class="sr-only">Section titled</span></a></div>`;

test('page fields: title, description, time, content without footer', () => {
  const h = page('<p>Hi</p>');
  assert.equal(L.pageTitle(h), 'T | OpenMVIS');
  assert.equal(L.pageDescription(h), 'D & more');
  assert.equal(L.pageTime(h), '2026-11-01T00:00:00.000Z');
  assert.ok(!L.mainContent(h).includes('Edit page'));
});

test('htmlToText keeps headings, lists, cells and drops scripts and anchor links', () => {
  const t = L.htmlToText('<h2 id="a">Head</h2><a class="sl-anchor-link" href="#a">#</a><p>x &lt; y&nbsp;&#8722;1</p>'
    + '<script>var a=1</script><ul><li>one</li><li>two</li></ul><table><tr><td>a</td><td>b</td></tr></table>'
    + '<dl><div><dt>Key</dt><dd>Val</dd></div></dl><p><a href="/g">Guide</a><a href="/w">Why</a></p>');
  assert.equal(t, '## Head\n\nx < y −1\n\n- one\n- two\na | b |\n\nKey: Val\n\nGuide Why');
});

test('KaTeX becomes $tex$; nested spans removed', () => {
  const k = '<span class="katex"><span class="katex-mathml"><math><annotation encoding="application/x-tex">t_\\text{cam}</annotation></math></span>'
    + '<span class="katex-html" aria-hidden="true"><span class="base"><span>t</span></span></span></span>';
  assert.equal(L.katexToTex(`a ${k} b`), 'a $t_\\text{cam}$ b');
  assert.equal(L.htmlToText(`<p>a ${k} b</p>`), 'a $t_\\text{cam}$ b');
});

test('FAQ: entries from h3s; JSON-LD only for "?" questions with an Answer: paragraph', () => {
  const h = page(h3('q1', 'Does it run?') + '<p><strong>Answer:</strong> yes, on\nLinux.</p><p>More.</p>'
    + h3('q2', 'Segfault when it starts') + '<p><strong>Answer:</strong> update.</p>'
    + h3('q3', 'Why?') + '<p>No answer prefix.</p>'
    + h3('q4', 'Which sign?') + '<p><strong>Answer:</strong> <code dir="auto">td</code> is +.</p>');
  const e = L.faqEntries(h);
  assert.deepEqual(e.map((x) => x.id), ['q1', 'q2', 'q3', 'q4']);
  const ld = L.faqJsonLd(e, 'https://openmvis.com/about/faq/');
  assert.equal(ld.mainEntity.length, 2);
  assert.equal(ld.mainEntity[0].acceptedAnswer.text, 'Yes, on Linux.');
  assert.equal(ld.mainEntity[1].acceptedAnswer.text, 'td is +.');
  assert.equal(ld.mainEntity[0].url, 'https://openmvis.com/about/faq/#q1');
  assert.equal(L.faqJsonLd([], 'u'), null);
  assert.ok(!L.ldScript({ a: '</script>' }).slice(0, -9).includes('</script>'));
});

test('template: every {{name}} line filled; missing data or a stray marker stops the build', () => {
  assert.equal(L.fillTemplate('a\n{{x}}\nb', { x: ['1', '2'] }), 'a\n1\n2\nb');
  assert.throws(() => L.fillTemplate('{{x}}', { x: [] }), /no lines/);
  assert.throws(() => L.fillTemplate('{{x}}\n{{y}}', { x: ['1'] }), /no lines for \{\{y\}\}/);
  assert.throws(() => L.fillTemplate('a {{x}}', { x: ['1'] }), /not on a line/);
  assert.throws(() => L.fillTemplate('a', { x: ['1'] }), /no \{\{x\}\} line/);
});

test('device lines follow sensor-nav order and every nav entry has a card', () => {
  const nav = JSON.parse(readFileSync(new URL('../src/data/sensor-nav.json', import.meta.url), 'utf8'));
  const cards = nav.map((n) => ({ href: n.link, title: 'X', maker: 'M', type: 'T' }));
  const lines = L.deviceLines(nav, cards);
  assert.equal(lines.length, nav.length);
  assert.equal(lines[0], `- [M X](https://openmvis.com${nav[0].link}): T`);
  assert.equal(L.deviceLines([{ link: '/d/' }], [{ href: '/d/', title: 'GI Ego1', maker: 'GI', type: 't' }])[0], '- [GI Ego1](https://openmvis.com/d/): t');
  assert.throws(() => L.deviceLines([{ link: '/none/' }], []), /no device card/);
});

test('sitemap lastmod is added once, only where a page has a time', () => {
  const xml = '<urlset><url><loc>https://openmvis.com/a/</loc></url><url><loc>https://openmvis.com/b/</loc></url></urlset>';
  const out = L.addLastmod(xml, (loc) => (loc.endsWith('/a/') ? '2026-11-01T00:00:00.000Z' : ''));
  assert.equal(out, '<urlset><url><loc>https://openmvis.com/a/</loc><lastmod>2026-11-01T00:00:00.000Z</lastmod></url><url><loc>https://openmvis.com/b/</loc></url></urlset>');
  assert.equal(L.addLastmod(out, () => 'x'), out.replace('<url><loc>https://openmvis.com/b/</loc>', '<url><loc>https://openmvis.com/b/</loc><lastmod>x</lastmod>'));
  assert.deepEqual(L.sitemapLocs(xml), ['https://openmvis.com/a/', 'https://openmvis.com/b/']);
});

test('llms-full keeps the given order and skips pages past the size limit', () => {
  const pages = new Map([['u1', { title: 'One', text: 'a'.repeat(50) }], ['u2', { title: 'Two', text: 'b'.repeat(500) }], ['u3', { title: 'Three', text: 'c' }]]);
  const { text, skipped } = L.fullText(['u3', 'u2', 'u1', 'missing'], pages, 400);
  assert.equal(skipped, 1);
  assert.ok(text.indexOf('# Three') < text.indexOf('# One'));
  assert.ok(!text.includes('# Two'));
});
