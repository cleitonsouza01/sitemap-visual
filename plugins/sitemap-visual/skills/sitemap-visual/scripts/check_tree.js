// Check a rendered Site Tree without a browser: node check_tree.js <index.html> <manifest.json>
// Site text is untrusted: this prints counts and shapes, never the text itself.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const manifest = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const block = /<script type="application\/json" id="site-data">([\s\S]*?)<\/script>/.exec(html);
if (!block) { console.log('FAILED: no data block'); process.exit(1); }
const d = JSON.parse(block[1]);
const fails = [];
const need = (ok, what) => { if (!ok) fails.push(what); };

need(!/__[A-Z]+__/.test(html.replace(block[0], '')), 'an unfilled placeholder');
need(d.pages.length === manifest.pages, `pages ${d.pages.length}, manifest says ${manifest.pages}`);
need(d.big === manifest.total, `big number ${d.big}, manifest total ${manifest.total}`);

const keys = new Set(d.sections.map((s) => s.k));
need(keys.size === d.sections.length, 'two sections share a key');
const count = (k) => d.pages.filter((p) => p.s === k).length;
d.sections.forEach((s) => {
  need(count(s.k) === s.n, `section ${s.k}: says ${s.n}, holds ${count(s.k)}`);
  need(d.pages.filter((p) => p.s === s.k && p.hub).length <= 1, `section ${s.k} has more than one main page`);
});
need(d.pages.every((p) => p.s === 'home' || keys.has(p.s)), 'a page points at a missing section');
need(d.pages.filter((p) => p.s === 'home').length <= 1, 'more than one home page');

const urls = d.pages.flatMap((p) => Object.values(p.tx).map((t) => t[3]));
need(new Set(urls).size === urls.length, 'two rows share a URL');
need(urls.every((u) => /^https?:\/\//.test(u)), 'a URL is not http(s)');
d.pages.forEach((p) => Object.values(p.tx).forEach((t) => need(t[0] && t[1], 'a row has no label or title')));
need(d.pages.every((p) => p.sp == null || (Number.isInteger(p.sp) && p.sp >= 0)), 'a bad photo cell');
need(html.includes('const SPRITE="data:') || !d.pages.some((p) => p.sp != null), 'pages have photos but the sheet is missing');

console.log('pages', d.pages.length, '| big', d.big, '| languages', d.langs.length, '| photos', d.pages.filter((p) => p.sp != null).length,
  '| prices', d.pages.filter((p) => p.price).length, '| size', Math.round(html.length / 1024) + ' KB');
console.log('sections', d.sections.map((s) => `${s.k}:${s.n}${s.article ? ' (articles)' : ''}`).join(', '));
fails.forEach((f) => console.log('  !', f));
console.log(fails.length ? 'FAILED' : 'OK');
process.exit(fails.length ? 1 : 0);
