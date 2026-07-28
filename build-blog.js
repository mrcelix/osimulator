/* build-blog.js — generate the static blog from blog/posts.json.
   Exported and called by build-static.js so blog URLs land in sitemap.xml.
   Run standalone with: node build-blog.js                                  */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const SITE = 'https://osimulator.com';
const POSTS = JSON.parse(fs.readFileSync(path.join(ROOT, 'blog', 'posts.json'), 'utf8'))
  .slice().sort((a, b) => a.order - b.order);

const CATS = {
  'how-to':    { label: 'How-to',    color: '#0a84ff' },
  'compare':   { label: 'Compare',   color: '#5e5ce6' },
  'explainer': { label: 'Explainer', color: '#30d158' },
  'learn':     { label: 'Learn',     color: '#ff9f0a' }
};

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const attr = s => esc(s).replace(/'/g, '&#39;');
/* the body html is authored, not user input, but it still must not break the
   RSS envelope or a JSON-LD string, so both of those go through strip/CDATA */
const strip = h => String(h).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
const words = p => strip(p.body.map(b => b.html).join(' ')).split(' ').length;
const readMins = p => Math.max(2, Math.round(words(p) / 210));
const url = p => `${SITE}/blog/${p.slug}.html`;
const niceDate = d => new Date(d + 'T09:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const rfc822 = d => new Date(d + 'T09:00:00Z').toUTCString();
const anchorId = h => h.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/* ------------------------------------------------------------------ CSS  */
const CSS = `
:root{--sf:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;--ink:#e8e8ee;--dim:#a9a9b6;--faint:#7c7c88;--line:rgba(255,255,255,.10);--card:rgba(255,255,255,.045);--accent:#8b8bff}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:var(--sf);background:#0b0b0f;color:var(--ink);line-height:1.62;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;background:radial-gradient(120% 80% at 50% 0%,#1c1c2b 0%,#0b0b0f 62%);z-index:-1}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header.site{position:sticky;top:0;z-index:30;backdrop-filter:blur(16px);background:rgba(11,11,15,.82);border-bottom:1px solid var(--line)}
.hin{display:flex;align-items:center;justify-content:space-between;gap:14px;max-width:1080px;margin:0 auto;padding:12px 20px}
.brand{display:inline-flex;align-items:center;gap:9px;font-weight:800;font-size:17px;color:#f5f5f7}
.brand:hover{text-decoration:none}
.mk{width:29px;height:29px;border-radius:9px;background:linear-gradient(135deg,#0a84ff,#5e5ce6);color:#fff;font-weight:800;font-size:14px;display:flex;align-items:center;justify-content:center}
.nav{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:center}
.nav a{color:#b6b6c2;font-weight:600;font-size:14px}
.nav a.on{color:#fff}
.nav .open{padding:7px 14px;border-radius:10px;background:linear-gradient(135deg,#0a84ff,#5e5ce6);color:#fff}
.nav .open:hover{text-decoration:none}
.wrap{max-width:1080px;margin:0 auto;padding:30px 20px 72px}
.narrow{max-width:734px}
.crumb{font-size:13px;color:var(--faint);margin:0 0 14px}
.crumb a{color:var(--faint)}
h1{font-size:clamp(28px,5vw,42px);font-weight:800;letter-spacing:-.025em;line-height:1.16;margin:6px 0 12px}
h2{font-size:clamp(20px,3vw,25px);font-weight:750;letter-spacing:-.015em;margin:38px 0 10px;scroll-margin-top:80px}
.lede{font-size:18.5px;color:#c6c6d2;margin:0 0 22px}
.meta{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;font-size:13px;color:var(--faint);margin:0 0 26px;padding-bottom:22px;border-bottom:1px solid var(--line)}
.chip{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.02em;background:rgba(255,255,255,.07);border:1px solid var(--line);color:#dcdce6}
.chip i{width:7px;height:7px;border-radius:50%;display:block}
article p{margin:0 0 16px;color:#dcdce6}
article ul{margin:0 0 18px;padding-left:22px}
article li{margin:0 0 8px;color:#dcdce6}
article strong{color:#f4f4f8}
table{width:100%;border-collapse:collapse;border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:6px 0 22px;font-size:14.5px}
th,td{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:rgba(255,255,255,.05);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:#9a9aa6}
td:first-child{font-weight:700;color:#f2f2f5;white-space:nowrap}
tr:last-child td{border-bottom:0}
.toc{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 20px;margin:0 0 28px}
.toc h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--faint);margin:0 0 8px}
.toc ol{margin:0;padding-left:20px}
.toc li{margin:4px 0;font-size:14.5px}
.key{background:linear-gradient(180deg,rgba(10,132,255,.10),rgba(94,92,230,.06));border:1px solid rgba(94,92,230,.28);border-radius:16px;padding:18px 22px;margin:30px 0 6px}
.key h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:#a9a9ff;margin:0 0 8px}
.key ul{margin:0;padding-left:20px}
.cta{display:block;margin:34px 0 6px;padding:22px 24px;border-radius:18px;background:linear-gradient(135deg,rgba(10,132,255,.16),rgba(94,92,230,.14));border:1px solid rgba(94,92,230,.34)}
.cta:hover{text-decoration:none}
.cta b{display:block;color:#fff;font-size:18px;margin-bottom:4px}
.cta span{color:#c2c2d4;font-size:14.5px}
.faq{margin-top:34px}
.faq details{border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:0 0 10px;background:var(--card)}
.faq summary{cursor:pointer;font-weight:700;color:#f2f2f6;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";float:right;color:var(--faint);font-weight:700}
.faq details[open] summary::after{content:"\\2212"}
.faq p{margin:10px 0 0;color:#c8c8d4;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(272px,1fr));gap:16px;margin:20px 0 0}
.card{display:flex;flex-direction:column;gap:9px;padding:20px;border-radius:18px;background:var(--card);border:1px solid var(--line);transition:border-color .18s,transform .18s,background .18s}
.card:hover{border-color:rgba(139,139,255,.5);background:rgba(255,255,255,.065);transform:translateY(-2px);text-decoration:none}
.card h3{margin:0;font-size:17px;font-weight:750;letter-spacing:-.012em;color:#f4f4f8;line-height:1.3}
.card p{margin:0;font-size:14px;color:var(--dim);line-height:1.5}
.card .cmeta{margin-top:auto;padding-top:4px;font-size:12px;color:var(--faint);display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 4px}
.fbtn{padding:8px 15px;border-radius:999px;font-size:13.5px;font-weight:650;color:#c2c2d0;background:rgba(255,255,255,.06);border:1px solid var(--line);cursor:pointer}
.fbtn[aria-pressed="true"]{background:#fff;color:#111;border-color:#fff}
.bsearch{width:100%;margin:16px 0 0;padding:13px 16px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.05);color:var(--ink);font-family:inherit;font-size:15px}
.bsearch::placeholder{color:var(--faint)}
.bsearch:focus{outline:2px solid rgba(139,139,255,.55);outline-offset:1px}
.empty{color:var(--faint);padding:26px 2px;display:none}
.related{margin-top:42px;padding-top:22px;border-top:1px solid var(--line)}
.related h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--faint);margin:0 0 12px}
.pn{display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;margin-top:26px;font-size:14.5px}
.tagrow{margin:26px 0 0;display:flex;flex-wrap:wrap;gap:7px}
.tag{font-size:12px;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.055);border:1px solid var(--line);color:#a9a9b6}
footer{border-top:1px solid var(--line);margin-top:52px}
.fin{max-width:1080px;margin:0 auto;padding:24px 20px 40px;color:var(--faint);font-size:12.5px}
.fin nav{margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px 16px}
.fin nav a{color:#9a9aa6;font-weight:600}
@media (prefers-reduced-motion:reduce){*{transition:none!important}html{scroll-behavior:auto}}
`.trim();

/* ---------------------------------------------------------------- shell  */
function shell({ title, desc, canonical, jsonld, body, cls = '', navOn = '' }) {
  const on = k => (navOn === k ? ' class="on"' : '');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(title)}</title>
<meta name="description" content="${attr(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<link rel="canonical" href="${canonical}">
<link rel="alternate" hreflang="x-default" href="${canonical}">
<link rel="alternate" type="application/rss+xml" title="osimulator blog" href="${SITE}/blog/feed.xml">
<link rel="icon" type="image/png" sizes="32x32" href="${SITE}/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="${SITE}/apple-touch-icon.png">
<meta name="theme-color" content="#0b0b0f">
<meta property="og:type" content="${cls === 'post' ? 'article' : 'website'}">
<meta property="og:site_name" content="osimulator">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="${attr(title)}">
<meta property="og:description" content="${attr(desc)}">
<meta property="og:url" content="${canonical}">
<meta property="og:image" content="${SITE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="osimulator — explore the real Settings menus of 43 operating systems">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${attr(title)}">
<meta name="twitter:description" content="${attr(desc)}">
<meta name="twitter:image" content="${SITE}/og.png">
${jsonld ? '<script type="application/ld+json">' + jsonld + '</script>' : ''}
<style>${CSS}</style>
</head>
<body>
<header class="site"><div class="hin">
<a class="brand" href="${SITE}/"><span class="mk">os</span>osimulator</a>
<nav class="nav">
<a href="${SITE}/blog/"${on('blog')}>Blog</a>
<a href="${SITE}/blog/os/"${on('os')}>Systems</a>
<a href="${SITE}/guides/">Guides</a>
<a href="${SITE}/compare/">Compare</a>
<a href="${SITE}/find/">Find a setting</a>
<a class="open" href="${SITE}/">Open the simulator</a>
</nav>
</div></header>
${body}
<footer><div class="fin">
<nav aria-label="Site sections">
<a href="${SITE}/">Simulator</a><a href="${SITE}/blog/">Blog</a><a href="${SITE}/blog/os/">System guides</a><a href="${SITE}/guides/">Guides</a><a href="${SITE}/compare/">Compare</a><a href="${SITE}/find/">Find a setting</a><a href="${SITE}/changes/">Version changes</a><a href="${SITE}/os/">All systems</a><a href="${SITE}/blog/feed.xml">RSS</a>
</nav>
osimulator — explore the real Settings menus of 43 operating systems across 87 versions, free and fully offline.
Independent educational project; not affiliated with Apple, Google, Microsoft or any other OS vendor. All trademarks belong to their owners.
</div></footer>
</body>
</html>`;
}

/* ----------------------------------------------------------- post page  */
function postPage(p, i) {
  const cat = CATS[p.cat] || CATS['how-to'];
  const canonical = url(p);
  const secs = p.body.map(b => {
    const id = anchorId(b.h2);
    return `<h2 id="${id}">${esc(b.h2)}</h2>\n${b.html}`;
  }).join('\n');
  const toc = `<nav class="toc" aria-label="On this page"><h2>On this page</h2><ol>${
    p.body.map(b => `<li><a href="#${anchorId(b.h2)}">${esc(b.h2)}</a></li>`).join('')}</ol></nav>`;
  const key = (p.key && p.key.length)
    ? `<aside class="key"><h2>Key points</h2><ul>${p.key.map(k => `<li>${esc(k)}</li>`).join('')}</ul></aside>` : '';
  const faq = (p.faq && p.faq.length)
    ? `<section class="faq"><h2 id="faq">Frequently asked questions</h2>${
        p.faq.map(f => `<details><summary>${esc(f.q)}</summary><p>${esc(f.a)}</p></details>`).join('')}</section>` : '';
  const tags = (p.tags && p.tags.length)
    ? `<div class="tagrow">${p.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : '';

  /* related: same category first, then nearest neighbours, never itself */
  const pool = POSTS.filter(x => x.slug !== p.slug);
  const rel = pool.filter(x => x.cat === p.cat).concat(pool.filter(x => x.cat !== p.cat)).slice(0, 3);
  const related = `<section class="related"><h2>Keep reading</h2><div class="grid">${rel.map(cardHtml).join('')}</div></section>`;

  const prev = POSTS[i - 1], next = POSTS[i + 1];
  const pn = `<div class="pn">${prev ? `<a href="${url(prev)}">&larr; ${esc(prev.h1 || prev.title)}</a>` : '<span></span>'}${next ? `<a href="${url(next)}">${esc(next.h1 || next.title)} &rarr;</a>` : '<span></span>'}</div>`;

  const jsonld = JSON.stringify({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'BlogPosting',
        '@id': canonical + '#post',
        headline: p.h1 || p.title,
        alternativeHeadline: p.title,
        description: p.desc,
        articleSection: cat.label,
        keywords: (p.tags || []).join(', '),
        wordCount: words(p),
        inLanguage: 'en',
        datePublished: p.date,
        dateModified: p.date,
        image: SITE + '/og.png',
        mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
        isPartOf: { '@id': SITE + '/blog/#blog' },
        author: { '@type': 'Organization', name: 'osimulator', url: SITE + '/' },
        publisher: { '@type': 'Organization', name: 'osimulator', url: SITE + '/', logo: { '@type': 'ImageObject', url: SITE + '/icon-512.png' } }
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: SITE + '/' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: SITE + '/blog/' },
          { '@type': 'ListItem', position: 3, name: p.h1 || p.title, item: canonical }
        ]
      }
    ].concat((p.faq && p.faq.length) ? [{
      '@type': 'FAQPage',
      '@id': canonical + '#faq',
      mainEntity: p.faq.map(f => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } }))
    }] : [])
  });

  const body = `<main class="wrap narrow">
<div class="crumb"><a href="${SITE}/">Home</a> &rsaquo; <a href="${SITE}/blog/">Blog</a> &rsaquo; ${esc(p.h1 || p.title)}</div>
<article>
<h1>${esc(p.h1 || p.title)}</h1>
<p class="lede">${esc(p.lede)}</p>
<div class="meta"><span class="chip"><i style="background:${cat.color}"></i>${esc(cat.label)}</span><time datetime="${p.date}">${niceDate(p.date)}</time><span>${readMins(p)} min read</span></div>
${toc}
${secs}
${key}
<a class="cta" href="${SITE}/"><b>Try it yourself, on the real menus</b><span>Open any of 43 operating systems in your browser and walk the Settings tree exactly as it appears on the device. No download, no account.</span></a>
${faq}
${tags}
</article>
${pn}
${related}
</main>`;

  return shell({ title: `${p.title} — osimulator`, desc: p.desc, canonical, jsonld, body, cls: 'post', navOn: 'blog' });
}

function cardHtml(p) {
  const cat = CATS[p.cat] || CATS['how-to'];
  return `<a class="card" href="${url(p)}" data-cat="${esc(p.cat)}" data-s="${attr(((p.h1 || p.title) + ' ' + p.desc + ' ' + (p.tags || []).join(' ')).toLowerCase())}">
<span class="chip"><i style="background:${cat.color}"></i>${esc(cat.label)}</span>
<h3>${esc(p.h1 || p.title)}</h3>
<p>${esc(p.desc)}</p>
<span class="cmeta"><time datetime="${p.date}">${niceDate(p.date)}</time><span>&middot;</span><span>${readMins(p)} min read</span></span>
</a>`;
}

/* ---------------------------------------------------------- blog index  */
function blogIndex() {
  const canonical = `${SITE}/blog/`;
  const cards = POSTS.map(cardHtml).join('\n');
  const filters = ['all'].concat(Object.keys(CATS)).map((k, i) =>
    `<button class="fbtn" type="button" data-f="${k}" aria-pressed="${i === 0 ? 'true' : 'false'}">${k === 'all' ? 'All' : esc(CATS[k].label)}</button>`).join('');
  const jsonld = JSON.stringify({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Blog', '@id': canonical + '#blog', name: 'osimulator blog', url: canonical,
        description: 'Practical guides and explainers about operating-system settings on phones, desktops, watches, TVs and consoles.',
        inLanguage: 'en',
        publisher: { '@type': 'Organization', name: 'osimulator', url: SITE + '/', logo: { '@type': 'ImageObject', url: SITE + '/icon-512.png' } },
        blogPost: POSTS.map(p => ({ '@type': 'BlogPosting', headline: p.h1 || p.title, description: p.desc, url: url(p), datePublished: p.date }))
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: SITE + '/' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: canonical }
        ]
      }
    ]
  });
  const body = `<main class="wrap">
<div class="crumb"><a href="${SITE}/">Home</a> &rsaquo; Blog</div>
<h1>The osimulator blog</h1>
<p class="lede">Practical, vendor-neutral writing about the Settings menus you actually use — on phones, desktops, watches, TVs, cars and consoles. Every article links straight into the live simulator so you can walk the menu yourself.</p>
<label class="visually-hidden" for="bq" style="position:absolute;left:-9999px">Search articles</label>
<input id="bq" class="bsearch" type="search" placeholder="Search ${POSTS.length} articles — try &quot;dark mode&quot;, &quot;esim&quot;, &quot;privacy&quot;…" autocomplete="off">
<div class="filters" role="group" aria-label="Filter by category">${filters}</div>
<div class="grid" id="bgrid">${cards}</div>
<p class="empty" id="bempty">No article matches that. Try a shorter word, or <a href="${SITE}/find/">look the setting up directly</a>.</p>
<noscript><p style="color:#7c7c88;font-size:13px">Search and filtering need JavaScript; every article is linked above regardless.</p></noscript>
<section class="related">
<h2>One article per operating system</h2>
<p>Beyond the articles above there is a dedicated write-up for every single system in the simulator &mdash; how its Settings menu is organised, what the top level actually contains, which versions you can open and what is worth finding once you are inside.</p>
<a class="cta" href="${SITE}/blog/os/"><b>Browse all 43 systems, explained one by one</b><span>iOS, Android, Windows, macOS, Ubuntu, watchOS, webOS, Symbian, KaiOS and 34 more.</span></a>
</section>
</main>
<script>
(function(){
 var q=document.getElementById('bq'),grid=document.getElementById('bgrid'),
     empty=document.getElementById('bempty'),cards=[].slice.call(grid.children),
     btns=[].slice.call(document.querySelectorAll('.fbtn')),cat='all';
 function apply(){
  var term=(q.value||'').trim().toLowerCase(),n=0;
  cards.forEach(function(c){
   var ok=(cat==='all'||c.dataset.cat===cat)&&(!term||c.dataset.s.indexOf(term)>-1);
   c.style.display=ok?'':'none';if(ok)n++;
  });
  empty.style.display=n?'none':'block';
 }
 q.addEventListener('input',apply);
 btns.forEach(function(b){b.addEventListener('click',function(){
  cat=b.dataset.f;btns.forEach(function(x){x.setAttribute('aria-pressed',String(x===b))});apply();
 })});
})();
</script>`;
  return shell({
    title: 'Blog — operating-system settings, explained — osimulator',
    desc: 'Practical guides and explainers on the Settings menus of iOS, Android, Windows, macOS, ChromeOS, Ubuntu and more — with a live simulator to try each one.',
    canonical, jsonld, body, navOn: 'blog'
  });
}

/* ------------------------------------------------------------------ RSS  */
function feed() {
  const items = POSTS.map(p => `  <item>
    <title>${esc(p.h1 || p.title)}</title>
    <link>${url(p)}</link>
    <guid isPermaLink="true">${url(p)}</guid>
    <pubDate>${rfc822(p.date)}</pubDate>
    <category>${esc((CATS[p.cat] || {}).label || p.cat)}</category>
    <description>${esc(p.desc)}</description>
  </item>`).join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>osimulator blog</title>
  <link>${SITE}/blog/</link>
  <atom:link href="${SITE}/blog/feed.xml" rel="self" type="application/rss+xml"/>
  <description>Practical guides and explainers about operating-system settings.</description>
  <language>en</language>
  <lastBuildDate>${rfc822(POSTS[0].date)}</lastBuildDate>
${items}
</channel>
</rss>
`;
}

/* --------------------------------------------------------------- write  */
function build() {
  const w = (rel, c) => { const f = path.join(ROOT, rel); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, c); };
  w('blog/index.html', blogIndex());
  POSTS.forEach((p, i) => w(`blog/${p.slug}.html`, postPage(p, i)));
  w('blog/feed.xml', feed());
  return [`${SITE}/blog/`].concat(POSTS.map(url));
}

module.exports = { build, POSTS, url, shell, CSS, esc, attr, strip, niceDate, rfc822, anchorId, SITE, CATS };

if (require.main === module) {
  const u = build();
  console.log('blog: wrote', u.length, 'pages +' , 'feed.xml');
}
