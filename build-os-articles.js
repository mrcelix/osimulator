/* build-os-articles.js — one long-form, semantically marked-up article per
   operating system, describing what the simulator offers for that system.

   Two inputs, deliberately kept apart:
     blog/os-data.json   structural facts extracted FROM THE RUNNING SIMULATOR
                         (menu titles, order, grouping, depth, row counts).
                         Nothing here is hand-typed, so nothing here can drift
                         away from what a visitor actually sees.
     blog/os-posts.json  the editorial layer (lede, design character, history,
                         audience, FAQ) — prose only, no structural claims.

   Everything the article states as a menu path comes from the first file.
   Run standalone: node build-os-articles.js                                */
const fs = require('fs');
const path = require('path');
const B = require('./build-blog');

const ROOT = __dirname;
const SITE = 'https://osimulator.com';
const esc = B.esc, attr = B.attr, anchorId = B.anchorId, shell = B.shell;

const DATA = JSON.parse(fs.readFileSync(path.join(ROOT, 'blog', 'os-data.json'), 'utf8'));
const COPY = JSON.parse(fs.readFileSync(path.join(ROOT, 'blog', 'os-posts.json'), 'utf8'));
const BY_ID = Object.fromEntries(DATA.map(d => [d.id, d]));
const DATE = '2026-07-28';

/* ---- device families, used for grouping the hub and for related links ---- */
const RETRO = new Set(['ios6', 'symbian', 'winphone', 'blackberry', 'firefoxos', 'winxp', 'win9x', 'macos9', 'macosx', 'win7']);
const FAMILY_BY_FRAME = {
  phone: 'Phones', android: 'Phones', harmony: 'Phones',
  tablet: 'Tablets',
  mac: 'Computers', win: 'Computers', linux: 'Computers', chromeos: 'Computers',
  watch: 'Watches', tv: 'TV and streaming', car: 'In-car', vision: 'Headsets',
  console: 'Consoles', winclassic: 'Retro and classic', macclassic: 'Retro and classic'
};
const FAMILY_ORDER = ['Phones', 'Tablets', 'Computers', 'Watches', 'TV and streaming', 'Consoles', 'Headsets', 'In-car', 'Retro and classic'];
const family = d => RETRO.has(d.id) ? 'Retro and classic' : (FAMILY_BY_FRAME[d.frame] || 'Other');

const FRAME_LABEL = {
  phone: 'phone', android: 'phone', harmony: 'phone', tablet: 'tablet', mac: 'laptop',
  win: 'PC', linux: 'laptop', chromeos: 'laptop', watch: 'watch', tv: 'television',
  car: 'car dashboard', vision: 'headset', console: 'console',
  winclassic: 'classic PC', macclassic: 'classic Mac'
};

/* the simulator groups sidebar rows with a short key; expand it for prose */
const GROUP_LABEL = {
  conn: 'Connectivity', sys: 'System', apps: 'Apps', personal: 'Personalisation',
  privacy: 'Privacy and security', acct: 'Accounts', media: 'Media', net: 'Network',
  dev: 'Developer', misc: 'Everything else', hw: 'Hardware', gen: 'General'
};

const slug = id => `${SITE}/blog/os/${id}.html`;

/* Where a version link should point. prerender.js only writes /os/<id>/<ver>/
   pages for a subset of the catalogue, so linking every version there would
   manufacture 404s. Prefer the prerendered page when it is actually on disk;
   otherwise send the reader to the live route the app parses, which is
   location.hash of the form #/<id>/<version> (index.html, parseHash). */
const verSlug = v => v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
function verHref(id, v) {
  const s = verSlug(v);
  return fs.existsSync(path.join(ROOT, 'os', id, s, 'index.html'))
    ? `${SITE}/os/${id}/${s}/`
    : `${SITE}/#/${encodeURIComponent(id)}/${encodeURIComponent(v)}`;
}
/* The simulator has no ?os= query handling at all — only the hash route. */
const openHref = d => `${SITE}/#/${encodeURIComponent(d.id)}/${encodeURIComponent((d.versions || [])[0] || '')}`;
const relOf = id => `/blog/os/${id}.html`;
const niceDate = B.niceDate;

/* ------------------------------------------------------------------ CSS  */
/* only the extras this template needs; the base sheet comes from build-blog */
const EXTRA = `
.osHead{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin:0 0 4px}
.osMark{width:54px;height:54px;border-radius:15px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:21px;color:#fff;flex:none;letter-spacing:-.02em}
.specs{display:grid;grid-template-columns:repeat(auto-fit,minmax(146px,1fr));gap:12px;margin:24px 0 6px;padding:0;list-style:none}
.specs li{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:13px 15px;margin:0}
.specs b{display:block;font-size:21px;font-weight:800;letter-spacing:-.02em;color:#f4f4f8;line-height:1.15}
.specs span{display:block;font-size:12px;color:var(--faint);margin-top:3px;letter-spacing:.02em}
.menuGrp{margin:0 0 18px}
.menuGrp h3{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--faint);margin:20px 0 8px;font-weight:800}
.menuList{display:flex;flex-wrap:wrap;gap:7px;margin:0;padding:0;list-style:none}
.menuList li{margin:0}
.menuList span{display:inline-block;font-size:13.5px;padding:5px 12px;border-radius:9px;background:rgba(255,255,255,.055);border:1px solid var(--line);color:#dcdce6}
.notable{margin:18px 0 0;padding:0;list-style:none}
.notable li{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 14px 14px 0;padding:14px 18px;margin:0 0 12px}
.notable code{display:block;font-size:13.5px;color:#a9c8ff;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;margin-bottom:5px;word-break:break-word}
.notable p{margin:0;font-size:14.8px;color:#c8c8d4}
.vers{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0 0;padding:0;list-style:none}
.vers a{display:inline-block;padding:8px 15px;border-radius:11px;background:rgba(255,255,255,.055);border:1px solid var(--line);font-size:14px;color:#dcdce6;font-weight:650}
.vers a:hover{border-color:rgba(139,139,255,.55);text-decoration:none}
.honest{border:1px solid rgba(255,159,10,.34);background:linear-gradient(180deg,rgba(255,159,10,.09),rgba(255,159,10,.03));border-radius:16px;padding:18px 22px;margin:30px 0 0}
.honest h2{margin-top:0;font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:#ffc46b}
.honest p{margin:0 0 10px;font-size:15px;color:#d8d2c6}
.honest p:last-child{margin-bottom:0}
.famhead{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--faint);margin:34px 0 2px;font-weight:800}
.osCard .cmeta b{color:#c9c9d6;font-weight:700}
`.trim();

/* ------------------------------------------------------------- helpers  */
function initials(name) {
  const t = name.replace(/[^A-Za-z0-9 ]/g, ' ').trim().split(/\s+/);
  return (t.length > 1 ? t[0][0] + t[1][0] : name.slice(0, 2)).toLowerCase();
}
function groupedMenu(d) {
  const order = [], map = {};
  d.top.forEach(t => {
    const k = t.group || '_';
    if (!map[k]) { map[k] = []; order.push(k); }
    map[k].push(t);
  });
  return order.map(k => ({ key: k, label: GROUP_LABEL[k] || (k === '_' ? 'Main list' : k.replace(/^\w/, c => c.toUpperCase())), items: map[k] }));
}
function wordCount(html) { return B.strip(html).split(/\s+/).filter(Boolean).length; }
/* The scaffolding around the editorial (glance, menu intro, versions, honesty
   note, closing call to action) would otherwise be word-for-word identical on
   43 pages, which reads as boilerplate to a reader and as thin duplication to a
   crawler. Pick a phrasing per system from a stable hash of its id instead. */
function pick(id, salt, arr) {
  let h = 5381;
  const k = id + '|' + salt;
  for (let i = 0; i < k.length; i++) h = ((h * 33) ^ k.charCodeAt(i)) >>> 0;
  return arr[h % arr.length];
}

/* --------------------------------------------------------- article page  */
function osPage(c, idx) {
  const d = BY_ID[c.id];
  const fam = family(d);
  const frameWord = FRAME_LABEL[d.frame] || 'device';
  const groups = groupedMenu(d);
  const canonical = slug(c.id);
  const menuNames = d.top.map(t => t.title);
  const verList = d.versions || [];

  /* neighbours: same family first, then the next system overall */
  const sameFam = DATA.filter(x => family(x) === fam && x.id !== c.id);
  const related = sameFam.slice(0, 4).concat(DATA.filter(x => family(x) !== fam).slice(0, 3)).slice(0, 5);
  const prev = COPY[idx - 1], next = COPY[idx + 1];

  const SECTIONS = [
    ['At a glance', 'glance'],
    [`How ${d.name} organises Settings`, 'organises'],
    ['The full top-level menu', 'menu'],
    ['Three settings worth finding', 'notable'],
    [`Versions of ${d.name} you can open`, 'versions'],
    ['How this menu got here', 'history'],
    ['Who this is useful for', 'audience'],
    ['What is real and what is sample data', 'honest'],
    ['Try it yourself', 'try']
  ];

  const bodyHtml = `
<main class="wrap narrow">
<nav class="crumb" aria-label="Breadcrumb"><a href="${SITE}/">Home</a> &rsaquo; <a href="${SITE}/blog/">Blog</a> &rsaquo; <a href="${SITE}/blog/os/">Systems</a> &rsaquo; <span>${esc(d.name)}</span></nav>

<article>
<header>
  <div class="osHead">
    <span class="osMark" style="background:${attr(d.accent)}22;border:1px solid ${attr(d.accent)}66;color:${attr(d.accent)}" aria-hidden="true">${esc(initials(d.name))}</span>
    <h1>${esc(c.h1)}</h1>
  </div>
  <p class="lede">${esc(c.lede)}</p>
  <div class="meta">
    <span class="chip"><i style="background:${attr(d.accent)}"></i>${esc(fam)}</span>
    <span>${esc(d.tagline)}</span>
    <span>${verList.length} version${verList.length === 1 ? '' : 's'}</span>
    <span>${d.totalRows.toLocaleString('en-GB')} settings rows</span>
    <time datetime="${DATE}">${esc(niceDate(DATE))}</time>
  </div>
</header>

<nav class="toc" aria-label="On this page">
  <h2>On this page</h2>
  <ol>${SECTIONS.map(([t, a]) => `<li><a href="#${a}">${esc(t)}</a></li>`).join('')}</ol>
</nav>

<section id="glance">
<h2>At a glance</h2>
<p>${pick(d.id,'glance',[
  `In the simulator, ${esc(d.name)} opens inside a ${esc(frameWord)} frame and behaves the way the real Settings app does: rows sit in the same order, sub-screens open in the same place, and back takes you where you expect.`,
  `Pick ${esc(d.name)} and a ${esc(frameWord)} appears with its Settings already open. Nothing is a screenshot &mdash; every row is a live element you can tap into, and the tree underneath it is the real one.`,
  `${esc(d.name)} runs here as a working ${esc(frameWord)}. You navigate it the way you would the physical thing: tap a row, land on its screen, go back, take a different branch.`,
  `Loading ${esc(d.name)} gives you a ${esc(frameWord)} with the Settings app in front of you. The ordering, the grouping and the nesting are the system's own, not a simplified summary of it.`
])} ${pick(d.id,'counted',[
  `The figures below are counted from the menu tree the site ships, not estimated.`,
  `Every number below was counted directly from that tree.`,
  `The counts below come from the tree itself, so they move only when the tree does.`
])}</p>
<ul class="specs">
  <li><b>${d.topCount}</b><span>top-level entries</span></li>
  <li><b>${d.totalRows.toLocaleString('en-GB')}</b><span>rows in total</span></li>
  <li><b>${d.depth}</b><span>levels deep</span></li>
  <li><b>${verList.length}</b><span>version${verList.length === 1 ? '' : 's'}</span></li>
</ul>
<table>
  <caption class="visually-hidden">${esc(d.name)} in the osimulator settings simulator</caption>
  <tbody>
    <tr><th scope="row">Device family</th><td>${esc(fam)}</td></tr>
    <tr><th scope="row">Frame shown</th><td>${esc(frameWord.charAt(0).toUpperCase() + frameWord.slice(1))}</td></tr>
    <tr><th scope="row">Versions</th><td>${esc(verList.join(', ') || 'One build')}</td></tr>
    <tr><th scope="row">Deepest path</th><td>${d.depth} levels below the main list</td></tr>
    <tr><th scope="row">Interface languages</th><td>12, switchable while you browse</td></tr>
    <tr><th scope="row">Account needed</th><td>No — it runs entirely in your browser</td></tr>
  </tbody>
</table>
</section>

<section id="organises">
<h2>How ${esc(d.name)} organises Settings</h2>
${c.character.map(p => `<p>${esc(p)}</p>`).join('\n')}
</section>

<section id="menu">
<h2>The full top-level menu</h2>
<p>${pick(d.id,'menu',[
  `These are the ${d.topCount} entries on the first screen, in the order the simulator presents them`,
  `The first screen holds ${d.topCount} entries. Here they are in their real order`,
  `Open Settings and you land on ${d.topCount} entries. This is that list, unreordered`
])}${groups.length > 1 ? `, grouped the way ${esc(d.name)} groups them` : ''}. ${pick(d.id,'menu2',[
  `Every name below comes from the menu tree itself, so it matches what you see on the ${esc(frameWord)}.`,
  `None of these labels were retyped by hand; they are read straight out of the tree.`,
  `The wording is the system's own, down to the ampersands and the capitalisation.`
])}</p>
${groups.map(g => `<div class="menuGrp">${groups.length > 1 ? `<h3>${esc(g.label)}</h3>` : ''}
<ul class="menuList">${g.items.map(t => `<li><span>${esc(t.title)}</span></li>`).join('')}</ul></div>`).join('\n')}
</section>

<section id="notable">
<h2>Three settings worth finding</h2>
<ul class="notable">
${c.notable.map(n => `<li><code>${esc(n.path)}</code><p>${esc(n.why)}</p></li>`).join('\n')}
</ul>
</section>

<section id="versions">
<h2>Versions of ${esc(d.name)} you can open</h2>
<p>${verList.length > 1
    ? pick(d.id,'vers',[
        `The simulator carries ${verList.length} builds of ${esc(d.name)}. Switching between them is the quickest way to see what actually moved: a row that changed name, a section split in two, a screen that quietly disappeared.`,
        `${verList.length} builds of ${esc(d.name)} are here. Open two of them and the differences stop being release-note bullet points and become screens you can point at.`,
        `You can load ${verList.length} builds of ${esc(d.name)}. That matters when you are writing instructions for someone whose device is a release or two behind yours.`,
        `There are ${verList.length} builds of ${esc(d.name)} to choose from, which is enough to watch the menu drift over time rather than guess at it.`
      ])
    : pick(d.id,'vers1',[
        `One build of ${esc(d.name)} is available, and it is enough to walk the whole tree and see how the system is laid out.`,
        `A single build of ${esc(d.name)} is included. The tree is complete, so nothing is out of reach.`
      ])}</p>
<ul class="vers">${verList.map(v => `<li><a href="${attr(verHref(d.id, v))}">${esc(d.name)} ${esc(v)}</a></li>`).join('')}</ul>
</section>

<section id="history">
<h2>How this menu got here</h2>
<p>${esc(c.history)}</p>
</section>

<section id="audience">
<h2>Who this is useful for</h2>
<p>${esc(c.audience)}</p>
</section>

<section id="honest" class="honest">
<h2>What is real and what is sample data</h2>
<p>The <strong>structure</strong> is the real thing: menu names, their order, how they are grouped and what sits inside each one. That is why this article can quote a path such as ${esc(c.notable[0].path)} and expect it to match your ${esc(frameWord)}.</p>
<p>The <strong>state</strong> cannot be. A device name, an address, a build number, a network name, a storage figure, whether a particular switch is on or off &mdash; those belong to a physical ${esc(frameWord)}, not to a menu tree. ${pick(d.id,'honest',[
  `Everywhere the simulator shows a value like that it is clearly-marked sample data: a placeholder that tells you where the number appears, not what any real device would say.`,
  `Those values appear here as clearly-marked samples. They are there so the row has the right shape, and they should never be read as a fact about a real ${esc(frameWord)}.`,
  `The simulator fills those in with obvious sample values. Use them to learn where a figure lives; look at your own ${esc(frameWord)} to learn what it says.`
])}</p>
</section>

<section id="try">
<h2>Try it yourself</h2>
<p>${pick(d.id,'try',[
  `Open ${esc(d.name)} and walk the tree. If you are writing instructions for someone else, turn the step recorder on first: it captures the exact click-path you take, so you can replay or hand over the path instead of typing out tap this, then tap that.`,
  `The useful thing is to go looking for something specific. Pick a setting you would normally hunt for on a real ${esc(frameWord)}, find it here, and record the path while you do it so you never have to find it twice.`,
  `Start at the top of ${esc(d.name)} and open every row once. It takes a few minutes and it is the fastest way to stop guessing which section a given option lives under.`,
  `Give yourself a task &mdash; change a language, find a privacy switch, locate a build number &mdash; and do it in ${esc(d.name)} here first. The step recorder will keep the route for you.`
])} ${pick(d.id,'try2',[
  `If you are weighing one system against another, put ${esc(d.name)} beside a second one and compare the same screen on both.`,
  `Comparison mode will hold ${esc(d.name)} next to another system if you want to see the two layouts against each other.`,
  `When the question is really ${esc(d.name)} versus something else, open them side by side rather than reading two separate menus from memory.`
])} ${pick(d.id,'try3',[
  `And if you know the setting but not the section, search for it by name across all 43 systems at once.`,
  `If you already know what the setting is called, the site-wide search will tell you which section hides it here.`,
  `The search will also work backwards: give it a setting name and it reports where every system files it.`
])}</p>
<a class="cta" href="${attr(openHref(d))}"><b>Open ${esc(d.name)} in the simulator</b><span>Free, no account, works offline &mdash; ${d.totalRows.toLocaleString('en-GB')} settings rows across ${verList.length} version${verList.length === 1 ? '' : 's'}.</span></a>
</section>

<div class="key">
<h2>Key points</h2>
<ul>
<li>${esc(d.name)} shows <strong>${d.topCount} top-level entries</strong> and ${d.totalRows.toLocaleString('en-GB')} rows in total, nested up to ${d.depth} levels.</li>
<li>${pick(d.id,'key2',[
  `Menu names and their order come from the settings tree itself, so the paths quoted here match the real ${esc(frameWord)}.`,
  `Nothing in the menu listing above was retyped by hand, which is why a path from this page can be followed on a real ${esc(frameWord)}.`,
  `The labels and their ordering are the system's own, not a tidied-up approximation.`
])}</li>
<li>${pick(d.id,'key3',[
  `Values such as device names, addresses and switch positions are sample data and are marked as such.`,
  `Anything that belongs to a specific device &mdash; names, addresses, build numbers, switch positions &mdash; is a marked sample.`,
  `Device-specific figures on screen are placeholders; the structure around them is not.`
])}</li>
</ul>
</div>

<section class="faq" id="faq">
<h2>Questions about ${esc(d.name)} settings</h2>
${c.faq.map(f => `<details><summary>${esc(f.q)}</summary><p>${esc(f.a)}</p></details>`).join('\n')}
</section>

<div class="tagrow">${(c.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>

<nav class="pn" aria-label="More systems">
${prev ? `<a href="${slug(prev.id)}">&larr; ${esc(BY_ID[prev.id].name)}</a>` : '<span></span>'}
${next ? `<a href="${slug(next.id)}">${esc(BY_ID[next.id].name)} &rarr;</a>` : '<span></span>'}
</nav>

<section class="related">
<h2>Related systems</h2>
<div class="grid">
${related.map(r => {
    const rc = COPY.find(x => x.id === r.id);
    return `<a class="card osCard" href="${slug(r.id)}"><h3>${esc(r.name)}</h3><p>${esc((rc ? rc.desc : '').slice(0, 108))}&hellip;</p><div class="cmeta"><b>${r.topCount}</b> entries <span>&middot;</span> <b>${r.versions.length}</b> version${r.versions.length === 1 ? '' : 's'}</div></a>`;
  }).join('\n')}
</div>
<p style="margin-top:20px"><a href="${SITE}/blog/os/">All 43 systems</a> &middot; <a href="${SITE}/blog/">Blog home</a> &middot; <a href="${SITE}/find/">Find a setting across every system</a> &middot; <a href="${SITE}/compare/">Compare two systems</a></p>
</section>

</article>
</main>`;

  const wc = wordCount(bodyHtml);
  const graph = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'TechArticle',
        '@id': canonical + '#article',
        headline: c.h1,
        name: c.title,
        description: c.desc,
        inLanguage: 'en',
        datePublished: DATE, dateModified: DATE,
        wordCount: wc,
        articleSection: fam,
        keywords: [c.keyword].concat(c.tags || []).join(', '),
        about: { '@type': 'SoftwareApplication', name: d.name, applicationCategory: 'OperatingSystem', softwareVersion: verList.join(', ') },
        mainEntityOfPage: { '@type': 'WebPage', '@id': canonical },
        isPartOf: { '@id': SITE + '/blog/#blog' },
        author: { '@type': 'Organization', name: 'osimulator', url: SITE },
        publisher: { '@type': 'Organization', name: 'osimulator', url: SITE },
        image: SITE + '/og.png'
      },
      {
        '@type': 'BreadcrumbList',
        '@id': canonical + '#crumb',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: SITE + '/' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: SITE + '/blog/' },
          { '@type': 'ListItem', position: 3, name: 'Systems', item: SITE + '/blog/os/' },
          { '@type': 'ListItem', position: 4, name: d.name, item: canonical }
        ]
      },
      {
        '@type': 'ItemList',
        '@id': canonical + '#menu',
        name: `${d.name} Settings — top-level menu`,
        numberOfItems: menuNames.length,
        itemListOrder: 'https://schema.org/ItemListOrderAscending',
        itemListElement: menuNames.map((n, i) => ({ '@type': 'ListItem', position: i + 1, name: n }))
      },
      {
        '@type': 'FAQPage',
        '@id': canonical + '#faq',
        mainEntity: c.faq.map(f => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } }))
      }
    ]
  };

  return { html: shell({ title: c.title + ' — osimulator', desc: c.desc, canonical, jsonld: JSON.stringify(graph), body: bodyHtml, cls: 'post', navOn: 'os' }).replace('</style>', EXTRA + '\n.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}\n</style>'), words: wc };
}

/* -------------------------------------------------------------- the hub  */
function hub() {
  const canonical = SITE + '/blog/os/';
  const fams = {};
  COPY.forEach(c => { const d = BY_ID[c.id]; (fams[family(d)] = fams[family(d)] || []).push(c); });
  const order = FAMILY_ORDER.filter(f => fams[f]).concat(Object.keys(fams).filter(f => !FAMILY_ORDER.includes(f)));
  const totalRows = DATA.reduce((a, x) => a + x.totalRows, 0);
  const totalVers = DATA.reduce((a, x) => a + Math.max(1, x.versions.length), 0);

  const card = c => {
    const d = BY_ID[c.id];
    return `<a class="card osCard" href="${slug(c.id)}" data-fam="${attr(family(d))}" data-s="${attr((d.name + ' ' + c.keyword + ' ' + (c.tags || []).join(' ') + ' ' + d.tagline).toLowerCase())}">
<h3>${esc(d.name)}</h3><p>${esc(c.desc.slice(0, 116))}&hellip;</p>
<div class="cmeta"><b>${d.topCount}</b> entries <span>&middot;</span> <b>${d.totalRows.toLocaleString('en-GB')}</b> rows <span>&middot;</span> <b>${d.versions.length || 1}</b> ver</div></a>`;
  };

  const body = `
<main class="wrap">
<nav class="crumb" aria-label="Breadcrumb"><a href="${SITE}/">Home</a> &rsaquo; <a href="${SITE}/blog/">Blog</a> &rsaquo; <span>Systems</span></nav>
<header class="narrow">
<h1>Every operating system in the simulator, explained</h1>
<p class="lede">One article per system: how its Settings menu is organised, what the top level actually contains, which versions you can open, and what to look for once you are inside. ${DATA.length} systems, ${totalVers} versions, ${totalRows.toLocaleString('en-GB')} settings rows in total.</p>
</header>
<label class="visually-hidden" for="oq">Search systems</label>
<input id="oq" class="bsearch" type="search" placeholder="Search a system — iOS, Ubuntu, webOS, Symbian&hellip;" autocomplete="off">
<div class="filters" role="group" aria-label="Filter by device family">
<button class="fbtn" data-f="all" aria-pressed="true">All ${DATA.length}</button>
${order.map(f => `<button class="fbtn" data-f="${attr(f)}" aria-pressed="false">${esc(f)} (${fams[f].length})</button>`).join('')}
</div>
<div id="ogrid">
${order.map(f => `<h2 class="famhead" data-fam="${attr(f)}">${esc(f)}</h2>
<div class="grid" data-fam="${attr(f)}">${fams[f].map(card).join('\n')}</div>`).join('\n')}
</div>
<p class="empty" id="oempty">No system matches that. Try a shorter word.</p>
<section class="related">
<h2>Elsewhere on the blog</h2>
<p><a href="${SITE}/blog/">All blog articles</a> &middot; <a href="${SITE}/find/">Find a setting across every system</a> &middot; <a href="${SITE}/compare/">Compare two systems side by side</a> &middot; <a href="${SITE}/guides/">Step-by-step guides</a> &middot; <a href="${SITE}/">Open the simulator</a></p>
</section>
</main>
<script>
(function(){
 var q=document.getElementById('oq'),grid=document.getElementById('ogrid'),
     empty=document.getElementById('oempty'),btns=[].slice.call(document.querySelectorAll('.fbtn')),fam='all';
 function apply(){
  var t=(q.value||'').trim().toLowerCase(),shown=0;
  [].forEach.call(grid.querySelectorAll('.osCard'),function(c){
   var okF=fam==='all'||c.getAttribute('data-fam')===fam,
       okQ=!t||c.getAttribute('data-s').indexOf(t)>-1||c.textContent.toLowerCase().indexOf(t)>-1;
   var on=okF&&okQ;c.style.display=on?'':'none';if(on)shown++;
  });
  [].forEach.call(grid.querySelectorAll('.grid'),function(g){
   var any=[].some.call(g.querySelectorAll('.osCard'),function(c){return c.style.display!=='none'});
   g.style.display=any?'':'none';
   var h=g.previousElementSibling;if(h&&h.classList.contains('famhead'))h.style.display=any?'':'none';
  });
  empty.style.display=shown?'none':'block';
 }
 q.addEventListener('input',apply);
 btns.forEach(function(b){b.addEventListener('click',function(){
  fam=b.getAttribute('data-f');btns.forEach(function(x){x.setAttribute('aria-pressed',String(x===b))});apply();});});
})();
</script>`;

  const graph = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'CollectionPage',
        '@id': canonical + '#page',
        name: 'Every operating system in the simulator, explained',
        description: `One in-depth article for each of the ${DATA.length} operating systems in the osimulator settings simulator.`,
        inLanguage: 'en',
        isPartOf: { '@id': SITE + '/blog/#blog' },
        url: canonical
      },
      {
        '@type': 'BreadcrumbList',
        '@id': canonical + '#crumb',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: SITE + '/' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: SITE + '/blog/' },
          { '@type': 'ListItem', position: 3, name: 'Systems', item: canonical }
        ]
      },
      {
        '@type': 'ItemList',
        '@id': canonical + '#list',
        numberOfItems: COPY.length,
        itemListElement: COPY.map((c, i) => ({ '@type': 'ListItem', position: i + 1, url: slug(c.id), name: BY_ID[c.id].name }))
      }
    ]
  };

  return shell({
    title: `All 43 operating systems, explained one by one — osimulator`,
    desc: `An article for each of the 43 operating systems in the simulator: how Settings is organised, what the top-level menu holds, and which versions you can open.`,
    canonical, jsonld: JSON.stringify(graph), body, navOn: 'os'
  }).replace('</style>', EXTRA + '\n.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}\n</style>');
}

/* --------------------------------------------------------------- build  */
function w(rel, html) {
  const p = path.join(ROOT, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, html);
}

function build() {
  const urls = [SITE + '/blog/os/'];
  let total = 0;
  w('blog/os/index.html', hub());
  COPY.forEach((c, i) => {
    if (!BY_ID[c.id]) throw new Error('no structural data for ' + c.id);
    const { html, words } = osPage(c, i);
    w(`blog/os/${c.id}.html`, html);
    urls.push(slug(c.id));
    total += words;
  });
  return { urls, total, count: COPY.length };
}

module.exports = { build, COPY, DATA, slug, relOf, family, BY_ID };

if (require.main === module) {
  const r = build();
  console.log('os articles:', r.count, 'pages + hub,', r.total.toLocaleString('en-GB'), 'words,', Math.round(r.total / r.count), 'avg');
}
