/* build-static.js — generate crawlable static pages for guides & comparisons
   from the data embedded in index.html. Run: node build-static.js         */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const SITE = 'https://osimulator.com';
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

/* ---- extract a JS array literal by name, quote/escape aware ---- */
function extractArray(name) {
  const key = 'const ' + name + '=[';
  const i = html.indexOf(key);
  if (i < 0) throw new Error('not found: ' + name);
  const start = i + key.length - 1; // at '['
  let depth = 0, q = null, esc = false;
  for (let j = start; j < html.length; j++) {
    const c = html[j];
    if (esc) { esc = false; continue; }
    if (q) {
      if (c === '\\') esc = true;
      else if (c === q) q = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { q = c; continue; }
    if (c === '[') depth++;
    else if (c === ']') { depth--; if (depth === 0) { return eval('(' + html.slice(start, j + 1) + ')'); } }
  }
  throw new Error('unbalanced: ' + name);
}

const GUIDES = extractArray('GUIDES');
const COMPARES = extractArray('COMPARES');

const OSN = { ipados:'iPadOS', ios:'iOS', macos:'macOS', windows:'Windows', android:'Android', ubuntu:'Ubuntu', chromeos:'ChromeOS', harmony:'HarmonyOS', watchos:'watchOS', wearos:'Wear OS', tvos:'tvOS', androidtv:'Google TV', carplay:'CarPlay', androidauto:'Android Auto', visionos:'visionOS', playstation:'PlayStation', xbox:'Xbox', win7:'Windows 7', macosx:'Mac OS X' };
const GCAT = { connectivity:'Connectivity', personalize:'Personalize', maintenance:'Maintenance', security:'Security', tips:'Tips & tricks' };

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
const attr = s => esc(s).replace(/'/g, '&#39;');

/* ---- shared page shell ---- */
function shell({ title, desc, canonical, jsonld, body, lang = 'en' }) {
  return `<!DOCTYPE html>
<html lang="${lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(title)}</title>
<meta name="description" content="${attr(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="${canonical}">
<link rel="icon" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='15' fill='%230a84ff'/><text x='32' y='44' font-family='Arial' font-size='30' font-weight='700' fill='%23fff' text-anchor='middle'>os</text></svg>">
<meta property="og:type" content="article">
<meta property="og:site_name" content="osimulator">
<meta property="og:title" content="${attr(title)}">
<meta property="og:description" content="${attr(desc)}">
<meta property="og:url" content="${canonical}">
<meta property="og:image" content="${SITE}/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${attr(title)}">
<meta name="twitter:description" content="${attr(desc)}">
<meta name="twitter:image" content="${SITE}/og.png">
${jsonld ? '<script type="application/ld+json">' + jsonld + '</script>' : ''}
<style>
:root{--sf:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sf);background:radial-gradient(120% 90% at 50% 0%,#1c1c2b 0%,#0b0b0f 60%);color:#e8e8ee;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:#8b8bff;text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:760px;margin:0 auto;padding:26px 20px 70px}
header.site{display:flex;align-items:center;justify-content:space-between;max-width:760px;margin:0 auto;padding:16px 20px}
.brand{display:inline-flex;align-items:center;gap:9px;font-weight:800;font-size:18px;color:#f5f5f7}
.mk{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#0a84ff,#5e5ce6);color:#fff;font-weight:800;font-size:15px;display:flex;align-items:center;justify-content:center}
.nav a{color:#b6b6c2;font-weight:600;font-size:14px;margin-left:16px}
.crumb{font-size:13px;color:#8b8b96;margin-bottom:16px}
h1{font-size:clamp(26px,4.5vw,36px);font-weight:800;letter-spacing:-.02em;margin:6px 0 10px}
.intro{font-size:17px;color:#b6b6c2;margin:0 0 24px}
.cta{display:inline-flex;align-items:center;gap:8px;padding:12px 22px;border-radius:12px;background:linear-gradient(135deg,#0a84ff,#5e5ce6);color:#fff;font-weight:700;font-size:15px;margin:2px 0 26px}
.osb{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);border-radius:16px;padding:18px 20px 6px;margin:0 0 16px}
.osb h2{font-size:18px;margin:0 0 10px}
.osb ol{margin:0 0 14px;padding-left:22px}
.osb li{padding:5px 0;color:#dcdce4}
table{width:100%;border-collapse:collapse;border:1px solid rgba(255,255,255,.1);border-radius:14px;overflow:hidden;margin:8px 0 20px}
th,td{padding:12px 14px;text-align:left;font-size:14.5px;border-bottom:1px solid rgba(255,255,255,.08);vertical-align:top}
th{background:rgba(255,255,255,.05);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#9a9aa6}
td:first-child{font-weight:700;color:#f2f2f5}
tr:last-child td{border-bottom:0}
.related{margin-top:30px}
.related h3{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#8b8b96}
.related a{display:block;padding:9px 0}
footer{max-width:760px;margin:40px auto 0;padding:22px 20px 0;border-top:1px solid rgba(255,255,255,.08);color:#6b6b73;font-size:12.5px}
</style>
</head>
<body>
<header class="site"><a class="brand" href="${SITE}/"><span class="mk">os</span>osimulator</a><nav class="nav"><a href="${SITE}/#/guides">Guides</a><a href="${SITE}/#/compare">Compare</a><a href="${SITE}/">Open app</a></nav></header>
<main class="wrap">
${body}
</main>
<footer>osimulator — explore the real Settings menus of 19 operating systems. Independent educational project; not affiliated with Apple, Google, Microsoft or any OS vendor. <a href="${SITE}/">osimulator.com</a></footer>
</body>
</html>`;
}

/* ---- guides ---- */
function guidePage(g) {
  const canonical = `${SITE}/guides/${g.slug}.html`;
  const app = `${SITE}/#/guides/${g.slug}`;
  const osBlocks = g.os.map(o => {
    const name = OSN[o.os] || o.os;
    const steps = (o.en || []).map(l => `<li>${esc(l)}</li>`).join('');
    return `<section class="osb"><h2>${esc(name)}</h2><ol>${steps}</ol></section>`;
  }).join('\n');
  const related = GUIDES.filter(x => x.group === g.group && x.slug !== g.slug).slice(0, 4)
    .map(x => `<a href="${SITE}/guides/${x.slug}.html">${esc(x.title.en)}</a>`).join('');
  const jsonld = JSON.stringify({ '@context':'https://schema.org','@graph':[
    { '@type':'HowTo','name':g.title.en,'description':g.intro.en,
      'step': g.os.map(o => ({ '@type':'HowToStep','name':(OSN[o.os]||o.os),'text':(o.en||[]).join('. ') })) },
    { '@type':'Article','headline':g.title.en,'description':g.intro.en,'inLanguage':'en','author':{'@type':'Organization','name':'osimulator'},'publisher':{'@type':'Organization','name':'osimulator','logo':{'@type':'ImageObject','url':SITE+'/icon-512.png'}},'mainEntityOfPage':canonical },
    { '@type':'BreadcrumbList','itemListElement':[
      {'@type':'ListItem','position':1,'name':'Home','item':SITE+'/'},
      {'@type':'ListItem','position':2,'name':'Guides','item':SITE+'/guides/'},
      {'@type':'ListItem','position':3,'name':g.title.en,'item':canonical} ] }
  ]});
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › <a href="${SITE}/#/guides">Guides</a> › ${esc(g.title.en)}</div>
<h1>${esc(g.title.en)}</h1>
<p class="intro">${esc(g.intro.en)}</p>
<a class="cta" href="${app}">Try it live in the simulator →</a>
${osBlocks}
<div class="related"><h3>Related guides</h3>${related}</div>`;
  return shell({ title: `${g.title.en} — osimulator`, desc: g.intro.en, canonical, jsonld, body });
}

function guidesIndex() {
  const canonical = `${SITE}/guides/`;
  const groups = {};
  GUIDES.forEach(g => (groups[g.group] = groups[g.group] || []).push(g));
  const secs = Object.keys(GCAT).filter(k => groups[k]).map(k =>
    `<h2 style="font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:#8b8bff;margin:26px 0 10px">${esc(GCAT[k])}</h2>` +
    groups[k].map(g => `<p><a href="${SITE}/guides/${g.slug}.html"><strong>${esc(g.title.en)}</strong></a> — ${esc(g.intro.en)}</p>`).join('')
  ).join('');
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › Guides</div>
<h1>How-to guides for every OS</h1>
<p class="intro">Step-by-step help for iOS, Android, macOS, Windows and more — then try it live.</p>
<a class="cta" href="${SITE}/#/guides">Open interactive guides →</a>${secs}`;
  return shell({ title: 'How-to guides for 19 operating systems — osimulator', desc: 'Step-by-step Settings guides for iOS, Android, macOS, Windows, Linux and more.', canonical, body });
}

/* ---- comparisons ---- */
function comparePage(c) {
  const A = OSN[c.a] || c.a, B = OSN[c.b] || c.b;
  const canonical = `${SITE}/compare/${c.slug}.html`;
  const app = `${SITE}/#/compare/${c.slug}`;
  const rows = c.rows.map(r => `<tr><td>${esc(r.topic.en)}</td><td>${esc(r.a.en)}</td><td>${esc(r.b.en)}</td></tr>`).join('');
  const related = COMPARES.filter(x => x.slug !== c.slug).slice(0, 4)
    .map(x => `<a href="${SITE}/compare/${x.slug}.html">${esc((OSN[x.a]||x.a))} vs ${esc((OSN[x.b]||x.b))}</a>`).join('');
  const jsonld = JSON.stringify({ '@context':'https://schema.org','@graph':[
    { '@type':'Article','headline':c.title.en,'description':c.intro.en,'inLanguage':'en','author':{'@type':'Organization','name':'osimulator'},'publisher':{'@type':'Organization','name':'osimulator','logo':{'@type':'ImageObject','url':SITE+'/icon-512.png'}},'mainEntityOfPage':canonical },
    { '@type':'BreadcrumbList','itemListElement':[
      {'@type':'ListItem','position':1,'name':'Home','item':SITE+'/'},
      {'@type':'ListItem','position':2,'name':'Compare','item':SITE+'/compare/'},
      {'@type':'ListItem','position':3,'name':`${A} vs ${B}`,'item':canonical} ] }
  ]});
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › <a href="${SITE}/#/compare">Compare</a> › ${esc(A)} vs ${esc(B)}</div>
<h1>${esc(c.title.en)}</h1>
<p class="intro">${esc(c.intro.en)}</p>
<a class="cta" href="${app}">Compare them live →</a>
<table><thead><tr><th>Setting</th><th>${esc(A)}</th><th>${esc(B)}</th></tr></thead><tbody>${rows}</tbody></table>
<div class="related"><h3>More comparisons</h3>${related}</div>`;
  return shell({ title: `${c.title.en} — osimulator`, desc: c.intro.en, canonical, jsonld, body });
}

function compareIndex() {
  const canonical = `${SITE}/compare/`;
  const items = COMPARES.map(c => `<p><a href="${SITE}/compare/${c.slug}.html"><strong>${esc((OSN[c.a]||c.a))} vs ${esc((OSN[c.b]||c.b))}</strong></a> — ${esc(c.intro.en)}</p>`).join('');
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › Compare</div>
<h1>Compare operating systems</h1>
<p class="intro">See how two systems handle the same settings, side by side.</p>
<a class="cta" href="${SITE}/#/compare">Open interactive comparisons →</a>${items}`;
  return shell({ title: 'Compare operating systems — osimulator', desc: 'Side-by-side Settings comparisons: iOS vs Android, macOS vs Windows and more.', canonical, body });
}

/* ---- cross-OS "where is this setting?" finder pages ---- */
function findPage(g) {
  const canonical = `${SITE}/find/${g.slug}.html`;
  const rows = g.os.map(o => `<tr><td>${esc(OSN[o.os] || o.os)}</td><td>${esc((o.en || []).join(' → '))}</td></tr>`).join('');
  const jsonld = JSON.stringify({ '@context':'https://schema.org','@graph':[
    { '@type':'WebPage','name':`Where is ${g.title.en} on every operating system`,'description':`Where the ${g.title.en} setting is located on each OS.`,'inLanguage':'en','mainEntityOfPage':canonical },
    { '@type':'BreadcrumbList','itemListElement':[
      {'@type':'ListItem','position':1,'name':'Home','item':SITE+'/'},
      {'@type':'ListItem','position':2,'name':'Find a setting','item':SITE+'/find/'},
      {'@type':'ListItem','position':3,'name':g.title.en,'item':canonical} ] }
  ]});
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › <a href="${SITE}/find/">Find a setting</a> › ${esc(g.title.en)}</div>
<h1>Where is “${esc(g.title.en)}” on every operating system?</h1>
<p class="intro">${esc(g.intro.en)} Here is exactly where to find it on each system.</p>
<a class="cta" href="${SITE}/#/find/${encodeURIComponent(g.title.en)}">Open the interactive finder →</a>
<table><thead><tr><th>Operating system</th><th>Where to find it</th></tr></thead><tbody>${rows}</tbody></table>
<div class="related"><a href="${SITE}/guides/${g.slug}.html">Step-by-step guide →</a></div>`;
  return shell({ title: `Where is ${g.title.en}? — every OS — osimulator`, desc: `Where the ${g.title.en} setting lives on iOS, Android, macOS, Windows and more.`, canonical, jsonld, body });
}
function findIndex() {
  const canonical = `${SITE}/find/`;
  const items = GUIDES.map(g => `<a class="tile" href="${SITE}/find/${g.slug}.html">${esc(g.title.en)}</a>`).join('');
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › Find a setting</div>
<h1>Where is this setting? Find it on every OS</h1>
<p class="intro">Look up any setting and see exactly where it lives across 19 operating systems, side by side.</p>
<a class="cta" href="${SITE}/#/find">Open the interactive finder →</a>
<div class="grid">${items}</div>`;
  return shell({ title: 'Find a setting on any operating system — osimulator', desc: 'Look up where any setting lives across iOS, Android, macOS, Windows and 15 more systems.', canonical, jsonld: JSON.stringify({ '@context':'https://schema.org','@type':'CollectionPage','name':'Find a setting on any OS','url':canonical }), body });
}
/* ---- version-changes landing ---- */
function changesIndex() {
  const canonical = `${SITE}/changes/`;
  const OSV = [['iOS','ios','StandBy and Journal were added in iOS 17'],['macOS','macos','VPN became a top-level item in macOS 14 Sonoma'],['Android','android','Security and Privacy were split into separate sections'],['iPadOS','ipados','Health arrived on iPad in iPadOS 17']];
  const items = OSV.map(o => `<p><strong>${esc(o[0])}</strong> — ${esc(o[2])}. <a href="${SITE}/#/changes/${o[1]}">Compare its versions →</a></p>`).join('');
  const jsonld = JSON.stringify({ '@context':'https://schema.org','@graph':[
    { '@type':'WebPage','name':'What changed between OS versions','description':'Settings sections added, removed or renamed between OS versions.','inLanguage':'en','mainEntityOfPage':canonical },
    { '@type':'BreadcrumbList','itemListElement':[
      {'@type':'ListItem','position':1,'name':'Home','item':SITE+'/'},
      {'@type':'ListItem','position':2,'name':'Version changes','item':canonical} ] }
  ]});
  const body = `<div class="crumb"><a href="${SITE}/">Home</a> › Version changes</div>
<h1>What changed between operating-system versions</h1>
<p class="intro">See which Settings sections were added, removed or renamed between versions of each OS.</p>
<a class="cta" href="${SITE}/#/changes">Open the interactive version diff →</a>${items}`;
  return shell({ title: 'What changed between OS versions — osimulator', desc: 'Which Settings sections were added, removed or renamed between iOS, macOS, Android and iPadOS versions.', canonical, jsonld, body });
}

/* ---- write files ---- */
function w(rel, content) { const p = path.join(ROOT, rel); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, content); }

const urls = [`${SITE}/`];
w('guides/index.html', guidesIndex()); urls.push(`${SITE}/guides/`);
GUIDES.forEach(g => { w(`guides/${g.slug}.html`, guidePage(g)); urls.push(`${SITE}/guides/${g.slug}.html`); });
w('compare/index.html', compareIndex()); urls.push(`${SITE}/compare/`);
COMPARES.forEach(c => { w(`compare/${c.slug}.html`, comparePage(c)); urls.push(`${SITE}/compare/${c.slug}.html`); });
w('find/index.html', findIndex()); urls.push(`${SITE}/find/`);
GUIDES.forEach(g => { w(`find/${g.slug}.html`, findPage(g)); urls.push(`${SITE}/find/${g.slug}.html`); });
w('changes/index.html', changesIndex()); urls.push(`${SITE}/changes/`);

/* ---- sitemap (preserve any /os/ per-screen URLs added by prerender.js) ---- */
const today = new Date().toISOString().slice(0, 10);
let osUrls = [];
try {
  const prev = fs.readFileSync(path.join(ROOT, 'sitemap.xml'), 'utf8');
  osUrls = (prev.match(/<loc>([^<]+)<\/loc>/g) || []).map(m => m.replace(/<\/?loc>/g, '')).filter(u => u.includes('/os/'));
} catch (e) {}
const allUrls = Array.from(new Set(urls.concat(osUrls)));
const sm = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
  allUrls.map(u => `  <url><loc>${u}</loc><lastmod>${today}</lastmod><changefreq>weekly</changefreq><priority>${u === SITE + '/' ? '1.0' : '0.8'}</priority></url>`).join('\n') +
  `\n</urlset>\n`;
fs.writeFileSync(path.join(ROOT, 'sitemap.xml'), sm);

/* ---- inject crawlable internal links into index.html <noscript> ---- */
const links = `<a href="/find/">Find a setting</a> · <a href="/changes/">Version changes</a> · ` +
  GUIDES.map(g => `<a href="/guides/${g.slug}.html">${esc(g.title.en)}</a>`).join(' · ') +
  ' · ' + COMPARES.map(c => `<a href="/compare/${c.slug}.html">${esc((OSN[c.a]||c.a))} vs ${esc((OSN[c.b]||c.b))}</a>`).join(' · ');
let idx = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const block = `\n    <nav aria-label="All guides and comparisons"><p>${links}</p></nav>`;
idx = idx.replace(/\n\s*<nav aria-label="All guides and comparisons">[\s\S]*?<\/nav>/, '');
idx = idx.replace('  </main>\n</noscript>', `  ${block}\n  </main>\n</noscript>`);
fs.writeFileSync(path.join(ROOT, 'index.html'), idx);

console.log('Generated', urls.length, 'URLs;', GUIDES.length, 'guides,', COMPARES.length, 'comparisons. sitemap.xml updated; noscript links injected.');
