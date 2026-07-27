/* prerender.js — generate crawlable, path-based static pages for every OS screen,
   plus a per-OS/version OG image. Run:  node prerender.js
   Requires the local Playwright + Chromium already set up in this environment. */
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW || '/home/claude/.npm-global/lib/node_modules/playwright');

const SITE = 'https://osimulator.com';
const ROOT = __dirname;
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const slug = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
const mkdir = d => fs.mkdirSync(d, { recursive: true });
const write = (rel, html) => { const f = path.join(ROOT, rel); mkdir(path.dirname(f)); fs.writeFileSync(f, html); };

function shell({ title, desc, canonical, og, jsonld, body }) {
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${canonical}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="article"><meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}"><meta property="og:url" content="${canonical}">
<meta property="og:image" content="${og}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="${og}">
<link rel="icon" href="/favicon-32.png">
${jsonld ? '<script type="application/ld+json">' + jsonld + '</script>' : ''}
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0b0b0f;color:#e9e9ee;font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:34px 20px 70px}
a{color:#7ab8ff;text-decoration:none}a:hover{text-decoration:underline}
.crumb{font-size:13px;color:#9a9aa6;margin-bottom:16px}.crumb a{color:#9a9aa6}
h1{font-size:clamp(24px,4vw,34px);letter-spacing:-.02em;margin:6px 0 8px}
h2{font-size:19px;margin:26px 0 8px}.intro{color:#b6b6c2;font-size:17px}
.cta{display:inline-block;margin:16px 0 8px;background:linear-gradient(135deg,#0a84ff,#5e5ce6);color:#fff;font-weight:700;padding:11px 20px;border-radius:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:16px}
.tile{display:block;padding:13px 15px;border-radius:12px;background:#15151e;border:1px solid rgba(255,255,255,.08);color:#e9e9ee;font-weight:600}
.tile:hover{border-color:#0a84ff;text-decoration:none}
ul.rows{list-style:none;padding:0;margin:14px 0;border:1px solid rgba(255,255,255,.08);border-radius:12px;overflow:hidden}
ul.rows li{padding:11px 15px;border-top:1px solid rgba(255,255,255,.06);color:#d6d6df}ul.rows li:first-child{border-top:0}
.rel{margin-top:34px;display:flex;flex-wrap:wrap;gap:8px}.rel a{background:#15151e;border:1px solid rgba(255,255,255,.09);padding:7px 13px;border-radius:100px;font-size:13px}
footer{margin-top:44px;border-top:1px solid rgba(255,255,255,.08);padding-top:16px;color:#7a7a86;font-size:13px}
img.hero{width:100%;max-width:520px;border-radius:16px;border:1px solid rgba(255,255,255,.08);margin:10px 0}
</style></head><body><div class="wrap">${body}
<footer>osimulator — an independent educational project. Explore the real Settings of 19 operating systems. Not affiliated with any OS vendor.</footer>
</div></body></html>`;
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1.5 });
  const page = await ctx.newPage();
  const file = 'file://' + path.join(ROOT, 'index.html');
  await page.goto(file);
  await page.waitForTimeout(500);

  const list = await page.evaluate(() => window.__osList());
  const urls = []; // for sitemap: {loc}
  mkdir(path.join(ROOT, 'og'));
  let osPages = 0, secPages = 0, ogs = 0;

  // hub page listing every OS
  const hubTiles = list.map(o => `<a class="tile" href="${SITE}/os/${o.id}/${slug(o.versions[0])}/">${esc(o.name)} ${esc(o.versions[0])}</a>`).join('');
  write('os/index.html', shell({
    title: 'All operating systems & versions — osimulator',
    desc: 'Browse the real Settings menus of 19 operating systems across every version — iOS, Android, macOS, Windows and more.',
    canonical: `${SITE}/os/`, og: `${SITE}/og.png`,
    jsonld: JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: 'All operating systems', url: `${SITE}/os/` }),
    body: `<div class="crumb"><a href="${SITE}/">Home</a> › Operating systems</div><h1>Operating systems &amp; versions</h1><p class="intro">Explore the real Settings menus of every system, screen by screen.</p><div class="grid">${hubTiles}</div>`
  }));
  urls.push(`${SITE}/os/`);

  for (const o of list) {
    for (const ver of o.versions) {
      const data = await page.evaluate(([id, v]) => window.__osExport(id, v), [o.id, ver]);
      if (!data || !data.sections.length) continue;
      const vslug = slug(ver);
      const base = `os/${o.id}/${vslug}`;
      const canonical = `${SITE}/${base}/`;
      const appLink = `${SITE}/#/${o.id}/${encodeURIComponent(ver)}`;
      const ogPath = `og/${o.id}-${vslug}.png`;
      const ogUrl = `${SITE}/${ogPath}`;

      // OG screenshot of the booted device (embed+bare hides all chrome)
      try {
        await page.goto(file + '?embed=1&bare=1#/' + o.id + '/' + encodeURIComponent(ver));
        await page.waitForTimeout(750);
        await page.screenshot({ path: path.join(ROOT, ogPath) });
        ogs++;
      } catch (e) {}

      // per-section pages
      const secTiles = [];
      for (const s of data.sections) {
        const sid = s.id;
        const scanon = `${SITE}/${base}/${sid}/`;
        secTiles.push(`<a class="tile" href="${scanon}">${esc(s.title)}</a>`);
        const rows = s.rows.length ? `<ul class="rows">${s.rows.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : '';
        const scJson = JSON.stringify({ '@context': 'https://schema.org', '@graph': [
          { '@type': 'TechArticle', headline: `${s.title} on ${data.name} ${ver}`, description: `The ${s.title} settings on ${data.name} ${ver} and the options inside it.`, inLanguage: 'en', image: ogUrl, publisher: { '@type': 'Organization', name: 'osimulator', logo: { '@type': 'ImageObject', url: `${SITE}/icon-512.png` } }, mainEntityOfPage: scanon },
          { '@type': 'BreadcrumbList', itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: `${SITE}/` },
            { '@type': 'ListItem', position: 2, name: 'Operating systems', item: `${SITE}/os/` },
            { '@type': 'ListItem', position: 3, name: `${data.name} ${ver}`, item: canonical },
            { '@type': 'ListItem', position: 4, name: s.title, item: scanon } ] }
        ]});
        write(`${base}/${sid}/index.html`, shell({
          title: `${s.title} — ${data.name} ${ver} Settings — osimulator`,
          desc: `Where the ${s.title} settings live on ${data.name} ${ver}, and every option inside — explore it live in the interactive simulator.`,
          canonical: scanon, og: ogUrl, jsonld: scJson,
          body: `<div class="crumb"><a href="${SITE}/">Home</a> › <a href="${SITE}/os/">Systems</a> › <a href="${canonical}">${esc(data.name)} ${esc(ver)}</a> › ${esc(s.title)}</div>
<h1>${esc(s.title)} on ${esc(data.name)} ${esc(ver)}</h1>
<p class="intro">The ${esc(s.title)} section of the ${esc(data.name)} ${esc(ver)} Settings app${s.rows.length ? ' includes the following options:' : '.'}</p>
${rows}
<a class="cta" href="${appLink}/${sid}">Open this screen in the simulator →</a>`
        }));
        urls.push(scanon);
        secPages++;
      }

      // OS/version overview page
      const osJson = JSON.stringify({ '@context': 'https://schema.org', '@graph': [
        { '@type': 'TechArticle', headline: `${data.name} ${ver} Settings`, description: `Every Settings section on ${data.name} ${ver}.`, inLanguage: 'en', image: ogUrl, publisher: { '@type': 'Organization', name: 'osimulator' }, mainEntityOfPage: canonical },
        { '@type': 'BreadcrumbList', itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: `${SITE}/` },
          { '@type': 'ListItem', position: 2, name: 'Operating systems', item: `${SITE}/os/` },
          { '@type': 'ListItem', position: 3, name: `${data.name} ${ver}`, item: canonical } ] }
      ]});
      const others = list.filter(x => x.id !== o.id).slice(0, 6).map(x => `<a href="${SITE}/os/${x.id}/${slug(x.versions[0])}/">${esc(x.name)}</a>`).join('');
      write(`${base}/index.html`, shell({
        title: `${data.name} ${ver} Settings — every screen — osimulator`,
        desc: `Explore the real ${data.name} ${ver} Settings menus — ${data.sections.length} sections, screen by screen. Free, interactive, offline.`,
        canonical, og: ogUrl, jsonld: osJson,
        body: `<div class="crumb"><a href="${SITE}/">Home</a> › <a href="${SITE}/os/">Systems</a> › ${esc(data.name)} ${esc(ver)}</div>
<h1>${esc(data.name)} ${esc(ver)} — Settings</h1>
<p class="intro">${esc(data.tagline || '')}. Browse every one of the ${data.sections.length} Settings sections, then try it live.</p>
<img class="hero" src="/${ogPath}" alt="${esc(data.name)} ${esc(ver)} Settings screen" loading="lazy">
<a class="cta" href="${appLink}">Open ${esc(data.name)} ${esc(ver)} in the simulator →</a>
<h2>All Settings sections</h2>
<div class="grid">${secTiles.join('')}</div>
<div class="rel">${others}</div>`
      }));
      urls.push(canonical);
      osPages++;
    }
  }

  await browser.close();

  // Merge into sitemap.xml (keep existing guide/compare/root entries, add os pages)
  let existing = [];
  try {
    const xml = fs.readFileSync(path.join(ROOT, 'sitemap.xml'), 'utf8');
    existing = (xml.match(/<loc>([^<]+)<\/loc>/g) || []).map(m => m.replace(/<\/?loc>/g, ''))
      .filter(u => !u.includes('/os/')); // drop old os entries, re-add fresh
  } catch (e) {}
  const all = Array.from(new Set(existing.concat(urls)));
  const body = all.map(u => `  <url><loc>${u}</loc><changefreq>monthly</changefreq></url>`).join('\n');
  fs.writeFileSync(path.join(ROOT, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`);

  console.log(`Generated ${osPages} OS/version pages, ${secPages} section pages, ${ogs} OG images. Sitemap now has ${all.length} URLs.`);
})();
