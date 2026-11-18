// LLM- and crawler-facing files, written into the built site by post-build.mjs:
//   - llms.txt: public/llms.txt (hand-written) with its {{devices}} {{results}} {{examples}} {{datasets}} {{faq}}
//     lines filled from the site's data files and the built pages, so new pages show up by themselves.
//   - llms-full.txt: the text of every page in the sitemap, llms.txt pages first.
//   - sitemap lastmod: each page's "Last updated" <time datetime>.
//   - FAQPage JSON-LD on /about/faq/: every "…?" question whose first paragraph starts "Answer:".
// Pure string functions here (tested in llms.test.mjs); file reading and writing in writeLlmsFiles().

import { readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export const SITE = 'https://openmvis.com';
const FULL_LIMIT = 1_000_000;   // bytes; llms-full.txt stays under about 1 MB

const NAMED = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', middot: '·', mdash: '—', ndash: '–',
  hellip: '…', times: '×', deg: '°', micro: 'µ', copy: '©', rarr: '→', larr: '←', le: '≤', ge: '≥', minus: '−', plusmn: '±' };
export const decode = (s) => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
  if (e[0] === '#') return String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
  return NAMED[e.toLowerCase()] ?? m;
});

// Each KaTeX formula as $tex$ (its annotation), not the rendered glyph spans.
export function katexToTex(html) {
  let out = '', i = 0;
  for (;;) {
    const start = html.indexOf('<span class="katex', i);
    if (start < 0) return out + html.slice(i);
    let depth = 0, j = start;
    const tag = /<span\b|<\/span>/g;
    tag.lastIndex = start;
    for (let m; (m = tag.exec(html));) {
      depth += m[0] === '</span>' ? -1 : 1;
      if (depth === 0) { j = tag.lastIndex; break; }
    }
    if (depth !== 0) return out + html.slice(i);   // unbalanced: leave the rest as it is
    const tex = html.slice(start, j).match(/<annotation encoding="application\/x-tex">([\s\S]*?)<\/annotation>/);
    out += html.slice(i, start) + (tex ? `$${tex[1].trim()}$` : '');
    i = j;
  }
}

// Plain text of an HTML fragment: headings as #, list items as "- ", table cells split by " | ".
export function htmlToText(html) {
  let s = katexToTex(html)
    .replace(/<(script|style|svg|template|noscript|button)\b[\s\S]*?<\/\1>/gi, '')
    .replace(/<span class="sr-only"[^>]*>[\s\S]*?<\/span>/gi, '')
    .replace(/<a class="sl-anchor-link"[\s\S]*?<\/a>/gi, '')
    .replace(/<h([1-6])\b[^>]*>/gi, (_, n) => `\n\n${'#'.repeat(Number(n))} `)
    .replace(/<\/h[1-6]>/gi, '\n\n')
    .replace(/<\/(a|span|b|strong|small)>(?=<(a|span|b|strong|small)\b)/gi, '</$1> ')
    .replace(/<\/dt>/gi, ': ')
    .replace(/<li\b[^>]*>(?=\s*<h[1-6]\b)/gi, '\n')
    .replace(/<li\b[^>]*>/gi, '\n- ')
    .replace(/<\/t[dh]>/gi, ' | ')
    .replace(/<br\s*\/?>|<\/(p|div|tr|pre|ul|ol|table|figure|figcaption|details|summary|dt|dd|blockquote)>/gi, '\n')
    .replace(/<[^>]+>/g, '');
  s = decode(s);
  return s.split('\n').map((l) => l.replace(/[ \t]+/g, ' ').trim()).join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

const attr = (html, re) => { const m = html.match(re); return m ? decode(m[1]) : ''; };
export const pageTitle = (html) => attr(html, /<title>([^<]*)<\/title>/i);
export const pageDescription = (html) => attr(html, /<meta name="description" content="([^"]*)"/i);
export const pageTime = (html) => attr(html, /<time datetime="([^"]+)"/i);

// The page's own content: the markdown body, without the footer (edit link, pagination).
export function mainContent(html) {
  const start = html.indexOf('<div class="sl-markdown-content">');
  if (start < 0) return '';
  const end = html.indexOf('<footer', start);
  return html.slice(start, end < 0 ? undefined : end);
}

// FAQ entries of the built FAQ page: every h3 with its id, and the first paragraph after it.
export function faqEntries(html) {
  const out = [];
  const re = /<h3 id="([^"]+)">([\s\S]*?)<\/h3>([\s\S]*?)(?=<div class="sl-heading-wrapper|<footer|$)/g;
  for (const m of mainContent(html).matchAll(re)) {
    const p = m[3].match(/<p>([\s\S]*?)<\/p>/);
    // Code (td, t_ga) right after "Answer:" keeps its case; a plain first word gets a capital.
    const code = p ? /^<strong>Answer:<\/strong>\s*<(code|span class="katex)/.test(p[1]) : false;
    out.push({ id: m[1], question: htmlToText(m[2]), answer: p ? htmlToText(p[1]) : '', code });
  }
  return out;
}

const sentence = (t, cap) => { const s = t.replace(/\s+/g, ' ').trim(); return cap ? s.charAt(0).toUpperCase() + s.slice(1) : s; };

export function faqJsonLd(entries, url) {
  const main = entries.filter((e) => e.question.endsWith('?') && /^Answer:\s*\S/.test(e.answer)).map((e) => ({
    '@type': 'Question', name: e.question, url: `${url}#${e.id}`,
    acceptedAnswer: { '@type': 'Answer', text: sentence(e.answer.replace(/^Answer:\s*/, ''), !e.code) },
  }));
  return main.length ? { '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: main } : null;
}

export const ldScript = (obj) => `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, '\\u003c')}</script>`;

// Fill every {{name}} line of the template; a missing or empty section stops the build.
export function fillTemplate(template, sections) {
  const used = new Set();
  const out = template.replace(/^\{\{(\w+)\}\}$/gm, (m, name) => {
    const lines = sections[name];
    if (!lines || !lines.length) throw new Error(`llms.txt: no lines for {{${name}}}`);
    used.add(name);
    return lines.join('\n');
  });
  const left = out.match(/\{\{\w+\}\}/);
  if (left) throw new Error(`llms.txt: ${left[0]} is not on a line of its own`);
  for (const k of Object.keys(sections)) if (!used.has(k)) throw new Error(`llms.txt: template has no {{${k}}} line`);
  return out;
}

const line = (label, href, desc) => `- [${label}](${SITE}${href})${desc ? `: ${desc.replace(/\s+/g, ' ').trim()}` : ''}`;

// Device lines: sidebar order (sensor-nav.json), text from each page's card (title, maker, type, href).
export function deviceLines(nav, cards) {
  const byHref = new Map(cards.map((c) => [c.href, c]));
  return nav.map((n) => {
    const c = byHref.get(n.link);
    if (!c) throw new Error(`llms.txt: no device card for ${n.link}`);
    const name = c.title.startsWith(c.maker) ? c.title : `${c.maker} ${c.title}`;
    return line(name, c.href, c.type);
  });
}

// Sitemap: add <lastmod> to each <url> whose page has a time.
export function addLastmod(xml, timeOf) {
  return xml.replace(/<url><loc>([^<]+)<\/loc>(?!<lastmod>)/g, (m, loc) => {
    const t = timeOf(loc);
    return t ? `<url><loc>${loc}</loc><lastmod>${t}</lastmod>` : m;
  });
}

export const sitemapLocs = (xml) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
const linksIn = (text) => [...text.matchAll(/\]\((https:\/\/openmvis\.com\/[^)#\s]*)\)/g)].map((m) => m[1]);

// Pages in llms.txt order first, then the rest of the sitemap; each with its title, URL and text.
export function fullText(order, pages, limit = FULL_LIMIT) {
  const head = '# OpenMVIS: every page as text\n\nGenerated from https://openmvis.com at build time. Index: https://openmvis.com/llms.txt\n';
  const parts = [head];
  let size = Buffer.byteLength(head), skipped = 0;
  for (const url of order) {
    const p = pages.get(url);
    if (!p || !p.text) continue;
    const part = `\n\n---\n\n# ${p.title}\n\nURL: ${url}\n\n${p.text}\n`;
    const n = Buffer.byteLength(part);
    if (size + n > limit) { skipped++; continue; }
    parts.push(part); size += n;
  }
  return { text: parts.join(''), skipped };
}

export async function writeLlmsFiles(out, src) {
  const read = (p) => readFile(p, 'utf8');
  const fileOf = (url) => join(out, new URL(url).pathname, 'index.html');
  const htmlCache = new Map();
  const html = async (url) => {
    if (!htmlCache.has(url)) htmlCache.set(url, existsSync(fileOf(url)) ? await read(fileOf(url)) : '');
    return htmlCache.get(url);
  };
  const described = async (label, href) => line(label, href, pageDescription(await html(SITE + href)));

  // llms.txt
  const nav = (f) => read(join(src, 'data', f)).then(JSON.parse);
  const sensorDir = join(src, 'data', 'sensors');
  const cards = await Promise.all((await readdir(sensorDir)).filter((f) => f.endsWith('.json')).sort()
    .map(async (f) => JSON.parse(await read(join(sensorDir, f))).card));
  const datasetDir = join(src, 'content', 'docs', 'datasets');
  const datasets = [];
  for (const f of (await readdir(datasetDir)).filter((f) => f.endsWith('.mdx') && f !== 'index.mdx')) {
    const order = Number((await read(join(datasetDir, f))).match(/^\s+order:\s*(\d+)/m)?.[1] ?? 99);
    datasets.push({ order, href: `/datasets/${f.replace(/\.mdx$/, '')}/` });
  }
  datasets.sort((a, b) => a.order - b.order || a.href.localeCompare(b.href));
  const titled = async (href) => (pageTitle(await html(SITE + href)).replace(/ \| OpenMVIS$/, ''));
  const faqHtml = await html(`${SITE}/about/faq/`);
  const faq = faqEntries(faqHtml);
  const sections = {
    results: await Promise.all((await nav('results-nav.json')).map((n) => described(n.label, n.link))),
    examples: await Promise.all((await nav('examples-nav.json')).filter((n) => n.link !== '/benchmark/examples/')
      .map((n) => described(n.label, n.link))),
    devices: deviceLines(await nav('sensor-nav.json'), cards),
    datasets: await Promise.all(datasets.map(async (d) => described(await titled(d.href), d.href))),
    faq: faq.map((e) => line(e.question, `/about/faq/#${e.id}`)),
  };
  const llms = fillTemplate(await read(join(out, 'llms.txt')), sections);
  await writeFile(join(out, 'llms.txt'), llms);

  // FAQPage JSON-LD
  const ld = faqJsonLd(faq, `${SITE}/about/faq/`);
  if (ld) await writeFile(fileOf(`${SITE}/about/faq/`), faqHtml.replace('</head>', `${ldScript(ld)}</head>`));

  // sitemap lastmod + llms-full.txt
  const sitemaps = (await readdir(out)).filter((f) => /^sitemap-\d+\.xml$/.test(f));
  const locs = [];
  let dated = 0;
  for (const f of sitemaps) {
    const xml = await read(join(out, f));
    locs.push(...sitemapLocs(xml));
    const times = new Map();
    for (const loc of sitemapLocs(xml)) times.set(loc, pageTime(await html(loc)));
    const next = addLastmod(xml, (loc) => times.get(loc));
    dated += [...times.values()].filter(Boolean).length;
    await writeFile(join(out, f), next);
  }
  const pages = new Map();
  for (const loc of locs) {
    const h = await html(loc);
    if (!h || /http-equiv="refresh"/i.test(h)) continue;
    pages.set(loc, { title: pageTitle(h), text: htmlToText(mainContent(h)) });
  }
  const order = [...new Set([`${SITE}/`, ...linksIn(llms).filter((u) => pages.has(u)), ...locs])];
  const full = fullText(order, pages);
  await writeFile(join(out, 'llms-full.txt'), full.text);
  return { faqQuestions: ld ? ld.mainEntity.length : 0, dated, urls: locs.length, fullBytes: Buffer.byteLength(full.text), skipped: full.skipped };
}
