import { verifyProof, recordHashCanonicalLine } from './crypto.js';
import { initRoles, owner, lender, roleAction, roleMessage } from './roles.js';
import { workflowOverview, chooseRole, auditJourney, replayGantt, provenanceGraph, chooseNode, grantsMap } from './flows.js';
import { initAnchor, anchored, anchorSection, anchorAction, anchorNote } from './anchor.js';
import { evidenceFlow, weakestLink, cheatMap, lenderDecision, verifyPipeline, bitemporal, provenanceLineage, anchorFlow } from './diagrams.js';
import { ownerCharts, lenderCharts, verifyCharts, anchorCharts, replayCharts, explorerCharts, provenanceCharts, researchCharts } from './viz-pages.js';
import { chainStrip } from './viz.js';
import { enhanceMotion, bindRotatingWord, countPublishedFigures, condenseExposition } from './motion.js';
const base = './data/';
const cache = new Map();
async function load(name, txt = false) { const key = name + (txt ? ':text' : ''); if (!cache.has(key))
    cache.set(key, fetch(base + name).then(r => { if (!r.ok)
        throw Error('Evidence asset unavailable: ' + name); return txt ? r.text() : r.json(); })); return cache.get(key); }
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 2) => new Intl.NumberFormat('en-US', { maximumFractionDigits: d, minimumFractionDigits: d }).format(v);
const short = (s, n = 12) => s.slice(0, n) + '…' + s.slice(-6);
const labels = { home: 'Home', owner: 'Owner', lender: 'Lender', verify: 'Verify', replay: 'Replay', explorer: 'Explorer', provenance: 'Provenance', results: 'Results' };
const sourceStatus = (x) => {
    const text = { implemented: 'Implemented', offline: 'Evaluated offline', designed: 'Designed, not built', tested: 'Built and tested, not deployed', testnet: 'Deployed on a testnet' }[x];
    return `<span class="tag ${x === 'implemented' ? 'tag-solid' : x === 'designed' ? 'tag-dashed' : 'tag-outline'}">${text}</span>`;
};
const grades = {
    A1: [5, 'Device-signed reading', 'Where the physical device is installed'],
    A2: [4, 'Signed authoritative source', 'Correctness and authorization of the source'],
    'A2-': [4, 'Notarised source', 'Trust in the notary'],
    B: [3, 'Third-party / installation binding', 'Competence and independence of the third party'],
    'B-': [3, 'Third-party with extraction', 'Third party plus extraction process'],
    'C+': [2, 'Owner-uploaded file', 'Chain of custody'],
    C: [1, 'Manual or unauthenticated training', 'All unverified source assumptions']
};
function grade(g, detail = false) { const o = grades[g] || grades.C; const cls=String(g).replace('+','plus').replace('-','minus'); return `<span class="gradebadge v5-grade v5-grade--${cls}" title="${esc(o[1])} · ${esc(o[2])}"><span class="v5-grade-token">${esc(g)}</span><span class="v5-grade-name">${esc(o[1])}</span></span>${detail ? `<div class="tiny" style="margin-top:7px">${esc(o[1])}</div>` : ''}`; }
function notice(inner) { return `<div class="notice">${inner}</div>`; }
function hashView(value, full = false) { return `<button type="button" class="hash" data-action="copy" data-value="${esc(value)}" aria-label="Copy full hash ${esc(value)}" title="Copy SHA-256">${esc(full ? value : short(value))} <span style="color:var(--violet)">⧉</span></button>`; }
function sectionTitle(n, title, description = '') { return `<div class="section-head v5-section-head"><div><div class="eyebrow">${n}</div><h2>${title}</h2>${description ? `<p>${description}</p>` : ''}</div></div>`; }
function metric(title, value, sub, status = '') { return `<div class="kpi-card"><div class="micro">${title}</div><div class="value num">${value}</div><div class="caption">${sub}</div>${status ? `<div style="margin-top:10px">${status}</div>` : ''}</div>`; }
function btn(label, action, more = '', kind = 'btn-primary') { return `<button class="btn ${kind}" data-action="${action}" ${more}>${label}</button>`; }
let summary;
let current = 'home';
let selectedBuilding = 'Fox_office_Joy';
let selectedDay = '2017-01-15';
let chartView = 'chart';
let asOfIndex = 0;
let drawerOpen = false;
let tourIndex = -1;
let verifyRunning = false;
let checkList = [];
let progress = {};
let checkMode = 'all';
let tamperResult = null;
let worker = null;
let ledgerCache=[];
const roomMap = {home:'home',owner:'owner',lender:'lender',verify:'audit',replay:'audit',explorer:'audit',provenance:'audit',results:'research'};
const roomMeta = {home:['The institute','evidence'],owner:['Building owner','building'],lender:['Bank or valuer','landmark'],audit:['Independent audit','shield-check'],research:['Research findings','flask-conical']};
const roomNext = {home:'owner',owner:'lender',lender:'verify',verify:'replay',replay:'explorer',explorer:'provenance',provenance:'results',results:'home'};
function roomTabs(page){
 const audit=['verify','replay','explorer','provenance'];
 if(audit.includes(page))return `<div class="v5-room-tabs" role="navigation" aria-label="Audit tools">${audit.map(x=>`<a href="#${x}" class="${x===page?'active':''}">${labels[x]}</a>`).join('')}</div>`;
 if(page==='results')return `<div class="v5-room-tabs v5-research-tabs" role="group" aria-label="Experiment figures">${['All','E1','E2','E3','E4'].map(x=>`<button data-action="research-filter" data-filter="${x}" aria-pressed="${x==='All'}">${x}</button>`).join('')}</div>`;
 const steps=page==='owner'?[['Choose a route','owner-step-1'],['Check signed day','owner-step-2'],['Try to cheat','owner-step-3']]:page==='lender'?[['Read claim','lender-step-1'],['Grades','lender-step-2'],['Run checks','lender-step-3'],['Corrections','lender-step-4'],['Decide','lender-step-5']]:null;
 return steps?`<div class="v5-room-tabs v5-stepper" role="group" aria-label="${labels[page]} steps">${steps.map(([lab,id],i)=>`<button data-action="scroll-to" data-target="${id}"><span>${i+1}</span>${lab}</button>`).join('')}</div>`:'';
}
function roomIntro(page){if(page==='home')return '';const r=roomMap[page];const [name]=roomMeta[r];return `<div class="v5-room-head"><div class="v5-room-orb v5-orb-${r}" aria-hidden="true"><span>${r==='owner'?'⌂':r==='lender'?'▤':r==='audit'?'◇':'◈'}</span></div><div class="v5-room-head-info"><span class="eyebrow">${page==='owner'||page==='lender'?'ROLES':r.toUpperCase()} / ${labels[page]}</span><span class="v5-room-lead">${name}</span></div>${roomTabs(page)}</div>`;}
function nextCard(page){const dest=roomNext[page],r=roomMap[dest];return `<aside class="v5-next room-${r}" aria-label="Continue exploring"><span class="v5-next-orb v5-orb-${r}" aria-hidden="true"></span><div><span class="eyebrow">CONTINUE THE EVIDENCE JOURNEY</span><h3>Next: ${labels[dest]}</h3><p>${({owner:'Choose a source route, inspect a signed day and challenge the evidence.',lender:'Read the claim, inspect provenance and run six checks.',verify:'Recompute the archival evidence in your browser.',replay:'See how signed late data changes a historical report.',explorer:'Inspect the underlying records and source grades.',provenance:'Follow the weakest dependency through the claim.',results:'Read the experimental measurements and limits.',home:'Return to the full evidence lifecycle.'})[dest]}</p></div><a href="#${dest}" class="btn btn-primary">Open ${labels[dest]} →</a></aside>`;}
const root = document.getElementById('app');
const getBuilding = (id = selectedBuilding) => load('buildings/' + id + '.json');
const selectedList = () => summary?.buildings || [];
function checkStatus(c) { return `<span class="tag ${esc(c.status)}">${c.status === 'pass' ? '✓ PASSED' : c.status === 'fail' ? '✕ FAILED' : '◌ NOT VERIFIED'}</span>`; }
function metricState(value, kind, label, description) { const tone = value === 0 && (kind === 'fail' || kind === 'pass') ? 'neutral' : kind; return `<div class="verify-stat verify-stat--${tone}" aria-label="${value} ${label}"><div class="verify-stat__head"><span class="verify-stat__dot" aria-hidden="true"></span>${label}</div><div class="verify-stat__number num">${value}</div><div class="verify-stat__detail">${description}</div></div>`; }
function insightCard(index, title, description, action, icon) { return `<a class="card insight-card hover" href="#${action}"><div class="insight-card__top"><span class="insight-card__symbol" aria-hidden="true">${icon}</span><span class="insight-card__index">${index} / EXPLORE</span></div><h3>${title}</h3><p>${description}</p><span class="insight-card__link">Open workspace <span aria-hidden="true">↗</span></span></a>`; }
function frame(page, section) {
 const menu=(group,items,room)=>`<div class="v5-nav-group room-${room}" role="group" aria-label="${group}"><span class="v5-nav-dot" aria-hidden="true"></span>${items.map(k=>`<a href="#${k}" ${section===k?'aria-current="page"':''} class="${section===k?'active':''}">${labels[k]}</a>`).join('')}</div>`;
 return `<div class="honesty v5-institution"><div class="shell"><span><strong>DIYAR</strong> · reference implementation for IBCOL 2026</span><span>Team IBCOL26IR-540820 · reference run of 6 Nov 2026 · real BDG2 · simulated keys · demo pins · not a live system</span></div></div>
<header><div class="shell v5-nav-shell"><a class="brand" href="#home" aria-label="DIYAR home"><span class="brand-mark"><span>D</span></span><span><span class="brand-logo">DIYAR</span><em>Provenance-graded building evidence</em></span></a>
<nav id="main-nav" aria-label="Main navigation"><div class="v5-mobile-heading">Explore DIYAR <button class="icon-btn" data-action="menu" aria-label="Close navigation">✕</button></div><div class="v5-nav-group room-home"><a href="#home" ${section==='home'?'aria-current="page"':''} class="${section==='home'?'active':''}">Home</a></div>${menu('Roles',['owner','lender'],'owner')}${menu('Audit tools',['verify','replay','explorer','provenance'],'audit')}${menu('Research',['results'],'research')}</nav><div class="right-head"><a class="version" href="./reference-source.zip" download="DIYAR-ref-v2.1.zip" title="Download the reference Python source">Reference source ↓</a><button class="icon-btn" data-action="theme" aria-label="Toggle light or dark theme" title="Light / dark">◐</button><button class="icon-btn menu-btn" data-action="menu" aria-label="Open navigation" aria-expanded="false">☰</button></div></div></header>
<main id="content"><div class="shell">${roomIntro(section)}${page}${nextCard(section)}</div></main>
<footer class="footer"><div class="shell footer-row"><div><strong class="v5-footer-logo">DIYAR</strong><small>Team Akedia · IBCOL26IR-540820 · DIYAR-ref v2.1 · reference run regenerated from raw BDG2 on 6 Nov 2026</small><small>Building Data Genome Project 2 · Miller et al. (2020) · Keys simulated · ${anchored() ? 'Chain head anchored on the Sepolia testnet' : 'No deployed anchor'}</small></div><div><a href="./whitepaper.pdf" target="_blank" rel="noopener">Whitepaper PDF ↗</a> &nbsp; · &nbsp; <a href="#verify">Independent checks ↗</a><small>${anchored() ? 'Checks run on your device. No analytics or cookies; the only outside request is the optional Sepolia check on the Verify page.' : 'Checks run on your device. No analytics, cookies or third-party requests.'}</small></div></div></footer>
${drawerOpen ? `<div class="drawer-overlay" data-action="close-drawer"></div><aside class="drawer" id="evidence-drawer" role="dialog" aria-modal="true" aria-label="Evidence record"><div id="drawer-body">Loading evidence…</div></aside>` : ''}${tourIndex >= 0 ? tourModal() : ''}<div id="toast" aria-live="polite"></div>`;
}
function tourModal() { const steps = [['1 / 3 · ORIGIN', 'Explore', 'Trace Joy’s published 112,692.56 kWh back to 737 hourly readings.', '#explorer'], ['2 / 3 · VERIFICATION', 'Verify', 'Run the SHA-256, P-256, post-quantum SLH-DSA and Merkle checks yourself, in a few seconds, on this device.', '#verify'], ['3 / 3 · CORRECTION', 'Replay', 'Move between 4 February and 20 February. The earlier reported number remains independently inspectable.', '#replay']]; const s = steps[tourIndex]; return `<div class="drawer-overlay" data-action="close-tour"></div><aside class="drawer" role="dialog" aria-modal="true" aria-label="Three minute tour"><button class="icon-btn drawer-close" data-action="close-tour" aria-label="Close tour">✕</button><div style="margin-top:48px" class="tour-step">${s[0]}</div><h2 style="font-size:30px;margin-top:14px">${s[1]}</h2><p class="lead">${s[2]}</p><a href="${s[3]}" class="btn btn-primary" data-action="tour-visit">Open ${s[1]} ↗</a><div class="eyeline"></div><div class="toolbar">${btn('← Previous', 'tour-prev', tourIndex === 0 ? 'disabled' : '', 'btn-quiet')}${btn(tourIndex === 2 ? 'Finish tour' : 'Next step →', 'tour-next')}</div></aside>`; }
const chapterInfo = {
  owner:['01 / PARTICIPANT','Origin of the claim','SUBMIT · ATTRIBUTE · CHALLENGE'],
  lender:['02 / PARTICIPANT','A decision desk','RECEIVE · INSPECT · DECIDE'],
  verify:['03 / CONTROL','Evidence verification','RECOMPUTE · VALIDATE · CHALLENGE'],
  replay:['04 / TIME','The history is the evidence','VALID TIME · TRANSACTION TIME'],
  explorer:['05 / OBSERVATORY','Observe the published record','MEASURE · FLAG · INSPECT'],
  provenance:['06 / TRUST MAP','Who signed what?','SOURCES · ASSUMPTIONS · CLAIMS'],
  results:['07 / RESEARCH','What did we actually measure?','EXPERIMENTS · LIMITATIONS']
};
function chapterRibbon(page){ const c=chapterInfo[page];return c ? `<div class="v4-chapter"><div><span class="v4-chapter__number">${c[0]}</span><span class="v4-chapter__title">${c[1]}</span></div><span class="v4-chapter__trail">${c[2]}</span></div>` : ''; }
function roleCard(index, title, description, action, icon) { return `<a class="card insight-card hover role-card" href="#${action}"><div class="insight-card__top"><span class="insight-card__symbol" aria-hidden="true">${icon}</span><span class="insight-card__index">Role ${index}</span></div><h3>${title}</h3><p>${description}</p><span class="insight-card__link">Start <span aria-hidden="true">→</span></span></a>`; }
async function home() {
 const joy=summary.published.Fox_office_Joy;
 const recordText=await load('records.jsonl',true);
 const raw=recordText.split('\n').find(l=>l.includes('"field":"Fox_office_Joy/elec/2017-01-20"'));
 const obj=raw?JSON.parse(raw):null;
 const sample=obj?.value?.[0];
 const signature=sample?.sig||sample?.signature||'';
 const roles=[['01','owner','BUILDING OWNER','Get your number accepted. Then try to cheat.',['Choose a route','Check a signed day','Try 3 cheats'],'⌂'],['02','lender','BANK OR VALUER','A green claim lands on your desk.',['Read the claim','Run 6 checks','Decide'],'▤'],['03','verify','INDEPENDENT AUDITOR','Follow bytes, not promises.',['11 checks','Replay history','Trace provenance'],'◇'],['04','results','RESEARCH','What did we actually measure?',['E1 custody','E2 calibration','E3–E4 detection'],'◈']];
 return `<section class="hero v5-hero"><div class="v5-hero-copy"><div class="eyebrow">REFERENCE IMPLEMENTATION · IBCOL 2026</div><h1>Every number<br/>carries its <span class="gradient-text" id="v5-rotating-word">evidence.</span></h1><p class="lead">An independent evidence trail for building claims. Check each signature, grade and correction.</p><div class="actions">${btn('Choose a role ↓','scroll-roles')}${btn('Verify everything →','navigate','data-to="verify"','btn-quiet')}</div><div class="v5-hero-foot">OPEN REFERENCE · BDG2 FOX · NOT A LIVE SYSTEM</div></div>
 <div class="v5-hero-art" aria-label="Illustration of a building and its attached digital evidence"><div class="v5-hero-orb"></div><svg class="v5-building" viewBox="0 0 280 330" role="img" aria-label="Building with signed data"><title>Evidence-backed building</title><rect x="35" y="42" width="210" height="268" rx="9" fill="#0B1530"/><rect x="58" y="14" width="165" height="52" rx="8" fill="#132346"/>${Array.from({length:7},(_,i)=>Array.from({length:4},(_,j)=>`<rect x="${60+j*46}" y="${84+i*30}" width="28" height="19" rx="3" fill="${(i+j)%5===0?'#D69AF1':(i*j)%3===0?'#A2BAFF':'#293B6E'}"/>`).join('')).join('')}<path d="M136 310V272h35v38" fill="#202E59"/><circle cx="257" cy="106" r="9" fill="#F0D2FF"/></svg><div class="v5-chip chip-a"><b>● meter 000</b><small>${obj?.value?.length??24} of 24 hours signed · 20 Jan</small></div><div class="v5-chip chip-b"><b>● Daily root, chained</b><small>cites 19 Jan · signed twice</small></div><div class="v5-chip chip-c"><b>${grade('B')}</b><small>weaker of A1 reading and B certificate</small></div><div class="v5-chip chip-d"><small>JANUARY 2017 · Fox office Joy</small><strong class="gradient-text num">${fmt(joy)} <em>kWh</em></strong><small>re-checkable in your browser</small></div></div></section>
 <section class="v5-kpi-row" aria-label="Reference run measures">${metric('Signed days','91','each chained to the last')}${metric('Hourly meter signatures',fmt(summary.run.readings,0),'from three simulated meter keys')}${metric('Real BDG2 buildings',String(summary.buildings.length),'three Fox buildings')}${metric('Reference verification time','~7 s','measured on a laptop, not a guarantee')}</section>
 <section class="section" id="roles">${sectionTitle('01 │ THREE ROLES, ONE ARCHIVE','Pick a role. <span class="gradient-text">Try to break it.</span>')}<div class="v5-role-grid">${roles.map(([i,r,label,title,steps,icon])=>`<a class="v5-role-card room-${r==='verify'?'audit':r==='results'?'research':r}" href="#${r}"><div class="v5-role-art"><span class="v5-role-index">${i}</span><span class="v5-orb-icon v5-orb-${r==='verify'?'audit':r==='results'?'research':r}">${icon}</span></div><span class="eyebrow">${label}</span><h3>${title}</h3><ol>${steps.map(x=>`<li>${x}</li>`).join('')}</ol><strong class="v5-role-cta">Open ${labels[r]} →</strong></a>`).join('')}</div><details class="v5-advanced-workflow"><summary>View the complete role-by-role evidence swimlane</summary>${workflowOverview()}</details></section>
 <section class="section v5-proof-block" aria-label="What you can check yourself"><div class="v5-section-rule">02 │ WHAT YOU CAN CHECK YOURSELF</div><h2>Proof you can <span class="gradient-text">re-run</span>, not a promise.</h2><div class="v5-bento"><div class="v5-bento-large">${evidenceFlow({readings:summary.run.readings,days:summary.run.archiveDays})}<div class="v5-record"><span class="eyebrow">ONE OF ${fmt(summary.run.readings,0)} SIGNED HOURLY READINGS</span><pre>${esc(JSON.stringify({field:obj?.field??'Fox_office_Joy/elec/2017-01-20',h:sample?.h??0,v:sample?.v,signature:signature?short(signature,14):'See exact record in Explorer'},null,2))}</pre><small>Change a signed digit and its signature, record hash and the committed root no longer agree. Device keys are simulated.</small></div></div><div class="v5-bento-small"><span class="eyebrow">VERIFY</span><strong class="v5-bento-number">11 / 11</strong><p>Recorded result of the V2 reference run. Run the independent checks yourself on Verify.</p><a href="#verify">Run local checks →</a></div><div class="v5-bento-small"><span class="eyebrow">PROVENANCE</span><div class="v5-grade-row">${['A1','A2','B','C+','C'].map(x=>grade(x)).join('')}</div><p>From signed source bytes (A1) to an evidence path graded C.</p></div><div class="v5-bento-small"><span class="eyebrow">REPLAY</span><strong class="v5-bento-number">112,692.56 → 113,461.14</strong><p>February's late data is appended. The original published report remains recoverable.</p><a href="#replay">Explore history →</a></div><div class="v5-bento-small"><span class="eyebrow">ANCHOR CONTRACT</span><strong>3 attacks, 3 reverts</strong><p>Built and tested on a local EVM, not deployed.</p><a href="#verify">Inspect the local anchor →</a></div></div></section>
 <section class="section">${notice('<strong>This is</strong> a reference run on public BDG2 meter data with simulated signer keys and demo pins, regenerated from the raw files on 6 November 2026. <strong>It is not</strong> a live building system, a utility certificate, '+(anchored()?'a mainnet anchor or a verified installation. Its chain head is anchored on the Sepolia testnet, which you can check on the Verify page.':'a deployed anchor or a verified installation.'))}</section>`;
}
function chartSvg(days, mode = 'energy') {
    const W = 790, H = 268, L = 56, R = 18, T = 21, B = 42, ih = H - T - B, iw = W - L - R;
    const max = Math.max(...days.map(d => Math.max(d.kwh, d.baseline || 0)), 1) * 1.16;
    const x = (i) => L + i / (days.length - 1) * iw, y = (v) => T + ih - (v / max) * ih;
    const line = (key) => days.map((d, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(2)} ${y(d[key] || 0).toFixed(2)}`).join(' ');
    const grid = [0, 1, 2, 3, 4].map(i => `<line class="chart-grid" x1="${L}" y1="${T + ih * i / 4}" x2="${W - R}" y2="${T + ih * i / 4}"/><text class="chart-label" x="${L - 12}" y="${T + ih * i / 4 + 4}" text-anchor="end">${Math.round(max * (1 - i / 4)).toLocaleString('en-US')}</text>`).join('');
    const month = [0, 31, 59, 89].map(i => `<text class="chart-label" x="${x(i)}" y="${H - 12}" text-anchor="middle">${days[i]?.day.slice(5) || ''}</text>`).join('');
    const circles = days.map((d, i) => `<circle class="chart-point" cx="${x(i)}" cy="${y(d.kwh)}" r="${d.flag ? 4 : 2.1}" fill="${d.flag ? '#f4c874' : '#b692ff'}" data-chartday="${d.day}" tabindex="0" aria-label="${d.day}: ${d.kwh} kWh${d.flag ? ', flagged' : ''}"/>`).join('');
    const calibrationEnd = days.findLastIndex(d => d.gate === 'calibrating');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Measured daily electricity and estimated baseline, January through March 2017"><defs><linearGradient id="energyArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ac83ff" stop-opacity=".23"/><stop offset="1" stop-color="#ac83ff" stop-opacity="0"/></linearGradient></defs>${calibrationEnd >= 0 ? `<rect x="${L}" y="${T}" width="${x(calibrationEnd) - L}" height="${ih}" fill="#9e9da2" fill-opacity=".09"/><text x="${L + 8}" y="${T + 14}" font-size="10" fill="#ad9ebf">calibrating</text>` : ''}${grid}${month}<path d="${line('kwh')} L${x(days.length - 1)} ${T + ih} L${L} ${T + ih} Z" fill="url(#energyArea)"/><path d="${line('baseline')}" fill="none" stroke="#ada4b5" stroke-width="2" stroke-dasharray="6 6"/><path d="${line('kwh')}" fill="none" stroke="#ab85fa" stroke-width="2.4"/>${circles}</svg>`;
}
function statusForDay(d) { return d.gate === 'calibrating' ? `<span class="tag unsupported">Calibrating</span>` : d.flag ? `<span class="tag flag">⚠ ${esc(d.gate)} flag</span>` : `<span class="tag neutral">No flag</span>`; }
function dayTable(days) { return `<div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Hours</th><th style="text-align:right">Consumption, kWh</th><th style="text-align:right">Baseline, kWh</th><th>Gate</th><th>Versions</th><th>Inspect</th></tr></thead><tbody>${days.map(d => `<tr><td class="mono">${d.day}</td><td>${d.hours}/24</td><td class="numeric">${fmt(d.kwh)}</td><td class="numeric">${d.baseline === null ? '—' : fmt(d.baseline)}</td><td>${statusForDay(d)}</td><td>${d.versions}</td><td>${btn('Inspect →', 'inspect-day', `data-day="${d.day}"`, 'btn-sm')}</td></tr>`).join('')}</tbody></table></div>`; }
async function explorer() {
    const b = await getBuilding();
    const reports = await load('reports.json');
    const published = reports.published[b.id];
    const data = b.days;
    const totalFlags = data.filter(d => d.flag).length;
    const reportFields = Object.entries(published).filter(([k, v]) => typeof v === 'object' && v !== null && 'value' in v);
    return `<div class="page-heading"><div class="breadcrumb">DIYAR / Evidence / Building explorer</div><div class="eyebrow">Auditor · Where a number comes from</div><h1>Building Explorer</h1><p>Inspect readings, flags and their evidence. Later corrections appear in Replay.</p></div>
 <div class="toolbar"><div class="toolbar-left"><label class="micro" for="building-select">Reference building</label><select class="select" id="building-select">${selectedList().map((x) => `<option value="${x.id}" ${x.id === b.id ? 'selected' : ''}>${esc(x.id.replaceAll('_',' '))}</option>`).join('')}</select></div><div class="small">${b.meter} · ${fmt(b.area, 1)} m² · ${b.occupants === null ? 'Occupancy not recorded' : b.occupants + ' occupants'}</div></div>
 <div class="grid4 stat-row explorer-stat-row">${metric('January energy', fmt(published.actual_kwh.value) + ' <small style="font-size:11px">kWh</small>', 'Published report · as known on 4 Feb')}${metric('Hourly baseline CV(RMSE)', fmt(b.cvRmse * 100) + '%', 'Trained on 2016 data never committed as signed records → grade C')}${metric('90-day flags', `<span class="${totalFlags ? 'flag-number' : ''}">${totalFlags}</span>`, 'Flagged observations · not adjudicated')}${metric('Meter identity', b.meter, 'Signed simulated meter identity')}</div>
 <section class="section"><div class="card chart-card visual-panel"><div class="section-head" style="margin:0"><div><h2>Energy and evidence timeline</h2><p>Real BDG2 hourly observations aggregated by day; estimated baseline from the frozen 2016 model.</p></div></div>
${`<div class="legend" style="margin-top:17px"><span><i class="linekey"></i>Measured electricity</span><span><i class="linekey dashed"></i>Historical baseline</span><span><i class="linekey flag"></i>Flagged day</span></div><div class="chart-frame">${chartSvg(data)}</div><div class="chart-tip hidden" id="chart-tip"></div><div class="small" style="margin-top:5px">Hover over a point for its exact readings, baseline, flag, and number of versions. Click it to inspect the signed record.</div>`}</div></section>
<div class="v4-explorer-bridge" aria-label="Evidence inspection path"><span>01 <b>Meter-signed data</b></span><i aria-hidden="true">→</i><span>02 <b>Daily commitment</b></span><i aria-hidden="true">→</i><span>03 <b>As-of report</b></span><i aria-hidden="true">→</i><span>04 <b>Open the proof</b></span></div>
 ${await explorerCharts(load,b.id)}<section class="section">${sectionTitle('JANUARY / AS KNOWN 4 FEB', 'The published report, field by field', 'Each figure carries its own grade and the assumption you still have to trust.')}<div class="two-col"><div class="v52-claim-grid">${reportFields.map(([k,x])=>{const v=x;const val=v.value===null?'Not recorded':typeof v.value==='number'?k==='performance_vs_baseline'?fmt(v.value*100,2)+'%':k==='coverage'||k==='coverage_weather'?fmt(v.value*100,2)+'%':k==='gate_flags'?String(v.value):fmt(v.value,k==='kwh_per_m2'?2:3):String(v.value);return `<article class="v52-claim-card"><div class="v52-claim-head"><span>${esc(k.replaceAll('_',' '))}</span>${v.grade?grade(v.grade):''}</div><strong class="v52-claim-number">${esc(val)}</strong><details><summary>Trust assumption</summary><p>${esc((published.residual_assumptions||{})[k]||(v.grade==='derived'?'the inputs it was derived from':'Not specified'))}</p></details></article>`}).join('')}</div><div class="card"><div class="micro">Reconstruct the source</div><h3 style="font-size:20px">From hourly reading to building claim</h3><ol class="facts"><li>${data.filter(d => d.day.startsWith('2017-01')).reduce((n, d) => n + d.hours, 0)} signed hourly readings from <span class="mono">${b.meter}</span> in January, as first recorded.</li><li>Daily records are committed under one sparse Merkle root per day.</li><li>A signed installation certificate binds <span class="mono">${b.meter}</span> to this building (grade B); the building-level figure takes the weaker of the two grades.</li><li>The baseline was trained on 2016 data never committed as signed records, so it, and every figure built on it, is <b>grade C</b>.</li></ol>${btn('Inspect selected day →', 'inspect-day', `data-day="${selectedDay}"`)}<div class="mini-note">The gate flags; it never decides. The 15 January rule flag (18 of 24 hours) is shown as first recorded; the signed backfill of 20 February later completed that day. Signatures do not establish physical meter location or correct calibration.</div></div></div></section>
 <section class="section">${notice('<strong>Archive:</strong> the 2 November v1.1 run is kept unchanged in the repository (results/prototype) and still verifies with the current code. This site shows the V2 reference run that the whitepaper reports.')}</section>`;
}
function checkRows() { const expected = [['chain', 'Daily chain commitments'], ['ecdsa', 'ECDSA P-256 daily signatures'], ['slh', 'SLH-DSA-SHA2-256s daily signatures'], ['records', 'Record canonical hashes'], ['roots', 'Reconstructed signed SMT roots'], ['feeds', 'Authoritative-source signatures'], ['install', 'Installer certificates (meter ↔ building)'], ['reports', 'Published January report hashes'], ['absence', 'Renna occupants non-membership'], ['inclusion', 'Selective disclosure inclusion proof'], ['device', 'Deep check: hourly device signatures']]; return expected.map(([id, label], i) => { const found = checkList.find(c => c.id === id); const p = progress[id]; return `<div class="check-row check-row--${found ? esc(found.status) : verifyRunning ? 'running' : 'idle'}"><span class="index" aria-label="Check ${i + 1}">${String(i + 1).padStart(2, '0')}</span><div class="check-row__body"><div class="check-row__title"><span class="check-row__indicator" aria-hidden="true">${found ? found.status === 'pass' ? '✓' : found.status === 'fail' ? '✕' : '·' : verifyRunning ? '↻' : '○'}</span><strong>${esc(label)}</strong></div><div class="detail">${found ? esc(found.detail) : 'Not executed yet. Raw evidence is only checked when you press Run.'}</div>${p && !found ? `<div class="progress-track" role="progressbar" aria-label="Processed evidence" aria-valuemin="0" aria-valuemax="${p.total}" aria-valuenow="${p.done}"><div class="progress-bar" style="width:${Math.min(100, p.done / p.total * 100)}%"></div></div><div class="tiny">${p.done} / ${p.total} processed</div>` : ''}${found ? `<details class="check-detail"><summary>Inspect verification result</summary><div class="check-detail__content"><span>STATUS</span><strong>${esc(found.status.toUpperCase())}</strong><span>RESULT</span><strong>${esc(found.count || 'No count reported')}</strong><span>EXECUTION</span><strong>${found.ms} ms</strong><p>${esc(found.detail)}</p></div></details>` : ''}</div><div class="check-result">${found ? checkStatus(found) : `<span class="tag unsupported">◌ NOT RUN</span>`}<span class="time">${found ? `${found.count || ''} · ${found.ms} ms` : ''}</span></div></div>`; }).join(''); }
function verificationPanel() {
    const passes = checkList.filter(c => c.status === 'pass').length, failed = checkList.filter(c => c.status === 'fail').length, pending = Math.max(0,11-checkList.length) + checkList.filter(c => c.status === 'unsupported').length;
    return `<div class="verify-overview"><div class="verify-overview__heading"><div><div class="eyebrow">ON-DEVICE VERIFICATION</div><h2>${verifyRunning ? 'Verifying the archive…' : checkList.length === 0 ? 'Your evidence, under examination.' : 'Local verification receipt'}</h2><p>Computed from signed archival bytes, never preloaded PASS labels. Each result includes its actual execution time.</p></div><span class="verify-overview__edition">V2 REFERENCE RUN · LOCAL</span></div><div class="verify-summary">${metricState(passes, 'pass', 'Passed', 'Checks successfully executed')}${metricState(failed, 'fail', 'Failed', 'Invalid evidence detected')}${metricState(pending, 'neutral', 'Unverified', 'Not verified in this run')}</div><div class="verify-overview__action"><label class="deep-toggle"><input type="checkbox" id="deep-check" ${(document.getElementById('deep-check')?.checked ?? true) ? 'checked' : ''}/><span><strong>Deep verification</strong><small>Include 6,497 hourly signatures</small></span></label><div class="verify-action__right"><span class="micro">${verifyRunning ? 'Cryptographic operations running' : 'No fabricated progress or PASS states'}</span>${btn(verifyRunning ? 'Verifying…' : 'Run independent checks ↗', 'run-checks', verifyRunning ? 'disabled' : '')}</div></div>${verifyPipeline(checkList,progress)}${ledgerCache.length?chainStrip(ledgerCache,checkList):''}</div><div class="card verify-check-panel"><div class="checklist">${checkRows()}</div></div>`;
}
async function verify() {
    return `<div class="page-heading"><div class="breadcrumb">DIYAR / Verification laboratory</div><div class="eyebrow">Role 3 · Independent auditor</div><h1>Independent verification</h1><p>Verify published bytes, signatures and proofs on your own device.</p></div>${auditJourney()}<div id="verification-panel">${verificationPanel()}</div>${anchorSection()}${anchorFlow()}${await anchorCharts()}
<section class="section"><div class="two-col"><div class="card"><div class="micro">Scope of the checks</div><h3>What signature verification cannot prove</h3><p>It verifies that particular bytes were signed by a corresponding private key. It does not independently prove meter accuracy, physical installation, source authorization or operator independence.</p><div class="mini-note">Public keys in this archive were generated for a simulation. A relying party must independently pin real signer identities.</div></div><div class="card"><div class="micro">Offline and cross-language verification</div><h3>Inspect the source and test vectors</h3><p>Download the Python reference and run the original check suite. The TypeScript verifier hashes bytes independently and its tests include one-byte tampering and Merkle proof vectors.</p><div class="actions"><a class="btn" href="./reference-source.zip" download="DIYAR-ref-v2.1.zip">Download reference source ↓</a><a class="btn btn-quiet" href="./data/manifest.json" download>SHA-256 manifest ↓</a></div></div></div></section>
<section class="section" id="tamper-lab">${sectionTitle('TAMPER LAB', 'Break the evidence yourself', 'Each scenario operates on an in-memory copy of published data, never the source files.')}<div class="card"><div class="toolbar"><select class="select" id="tamper-select"><option value="reading">Reduce one meter reading by 10%</option><option value="grade">Change a provenance grade</option><option value="ledger">Delete a day from the ledger</option><option value="ecdsa">Flip one bit in the daily signatures</option><option value="proof">Forge a Merkle record hash</option><option value="false-meter">Validly signed but incorrect physical reading</option></select>${btn('Run tamper experiment →', 'run-tamper')}${btn('Reset experiment', 'reset-tamper', '', 'btn-quiet')}</div><div id="tamper-result">${tamperResult ? tamperResultHTML() : notice('Select an attack and run it. A passing cryptographic signature cannot detect a deliberately incorrect physical measurement.')}</div></div></section>`;
}
function tamperResultHTML() { const t = tamperResult; if (!t)
    return ''; const pass = t.status === 'detected'; const unknown = t.status === 'not-detectable'; return `<div class="receipt-label ${unknown ? 'receipt-label--warning' : pass ? 'receipt-label--pass' : 'receipt-label--fail'}"><strong>${unknown ? 'NOT DETECTABLE BY CRYPTOGRAPHY' : pass ? 'TAMPERING DETECTED' : 'TAMPERING NOT DETECTED'}</strong> · ${esc(t.detail)} ${Number.isFinite(t.ms) ? `· ${t.ms} ms` : ''}</div>`; }
async function replay() {
    const all = await load('reports.json');
    const dates = Object.keys(all.historicalReports), time = dates[asOfIndex], history = all.historicalReports[time], joy = history.buildings.Fox_office_Joy, initial = all.historicalReports[dates[0]].buildings.Fox_office_Joy;
    const compared = joy.actual_kwh.value - initial.actual_kwh.value;
    return `<div class="page-heading"><div class="breadcrumb">DIYAR / Temporal evidence / Replay</div><div class="eyebrow">Auditor · When the record changes</div><h1>Corrections do not erase history.</h1><p>See what was known then and what changed later.</p></div>
<div class="card replay-timebox"><div class="section-head"><div><h2>Known as of</h2><p>Four archived checkpoints around the six-hour Joy backfill.</p></div><span class="tag">V2 REFERENCE RUN</span></div><div class="asof">${dates.map((d, i) => `<button class="${i === asOfIndex ? 'active' : ''}" data-action="asof" data-index="${i}"><b>${esc(all.historicalReports[d].label)}</b><span>${i === 0 ? 'Published' : i === 1 ? 'Before correction' : i === 2 ? 'Backfill recorded' : 'Final state'}</span></button>`).join('')}</div><input aria-label="Known as of checkpoint" type="range" id="asof-range" min="0" max="3" step="1" value="${asOfIndex}" style="width:100%;margin:23px 0 0"/><div class="small">The January report was published on 5 February from the state as known on 4 February.</div></div>${await replayCharts(load)}${replayGantt(initial.actual_kwh.value,all.historicalReports[dates.at(-1)].buildings.Fox_office_Joy.actual_kwh.value)}<details class="v52-secondary-detail"><summary>Understand record time</summary>${bitemporal()}</details>
<section class="section"><div class="replay-compare"><div class="card replay-snapshot replay-snapshot--current"><div class="replay-snapshot__glow" aria-hidden="true"></div><div class="micro">January 2017 / Joy / archived as-of</div><div class="snapshot-mode">${compared === 0 ? 'ORIGINAL STATE' : 'CORRECTED STATE · FEB 20'}</div><div class="replay-value">${fmt(joy.actual_kwh.value)} <small style="font-size:13px">kWh</small></div><div class="small">Coverage: ${fmt(joy.coverage.value * 100, 2)}% · Recorded historical report ${asOfIndex < 2 ? 'unchanged' : 'recomputed after backfill'}</div><div class="eyeline"></div><div class="micro">Report output hash</div><div style="margin-top:10px">${hashView(joy.output_hash)}</div></div><div class="card replay-snapshot replay-snapshot--delta"><div class="micro">Difference from the published view</div><div class="snapshot-mode">${compared === 0 ? 'NO VERSION CHANGE' : 'NEW VERSION APPENDED'}</div><div class="replay-value" style="color:${compared === 0 ? 'var(--soft)' : 'var(--violet)'}">${compared > 0 ? '+' : ''}${fmt(compared)} <small style="font-size:13px">kWh</small></div><div class="small">${compared === 0 ? 'No correction recorded yet. Earlier January totals remain available.' : 'Six missing hours from 15 January were registered on 20 February.'}</div><div class="eyeline"></div><div class="micro">Performance vs committed baseline</div><div class="replay-value" style="font-size:22px">${fmt(joy.performance_vs_baseline.value * 100, 2)}%</div></div></div></section>
<section class="section"><div class="replay-event-note"><span class="replay-event-note__glyph">↗</span><div><strong>Correction is not a verdict.</strong><p>Later signed hours changed the total, not the original record. A correction is not a sustainability rating.</p></div><span class="tag">APPEND-ONLY HISTORY</span></div></section><section class="section">${sectionTitle('Records remain committed', 'As-of comparison across three buildings')}<div class="v52-replay-cards">${Object.keys(history.buildings).map(b=>{const original=initialReport(all,b),current=history.buildings[b],delta=current.actual_kwh.value-original.actual_kwh.value;return `<article class="v52-replay-building"><span>${esc(b.replaceAll('_',' '))}</span><strong>${fmt(current.actual_kwh.value)} <small>kWh</small></strong><div><span>Original: ${fmt(original.actual_kwh.value)}</span><b class="${delta!==0?'is-corrected':''}">${delta===0?'Unchanged':`${delta>0?'+':''}${fmt(delta)} kWh added`}</b></div></article>`}).join('')}</div><p class="small">Browser totals reflect the selected moment. Verify checks report hashes independently.</p><div id="asof-recomputed" class="notice">Recomputing the historical hourly totals…</div></section>`;
}
function initialReport(all, b) { return all.historicalReports[Object.keys(all.historicalReports)[0]].buildings[b]; }
async function recomputeAsOf() { const i = asOfIndex; const dates = ['2017-02-04T23:59', '2017-02-19T23:59', '2017-02-20T23:59', '2017-03-31T23:59']; const recs = await load('records.jsonl', true); const selected = new Map(); for (const l of recs.trim().split('\n')) {
    const r = JSON.parse(l);
    if (r.tx_time <= dates[i] && r.field.startsWith('Fox_office_Joy/elec/2017-01')) {
        const old = selected.get(r.field);
        if (!old || old.tx_time < r.tx_time)
            selected.set(r.field, r);
    }
} const hours = Array.from(selected.values()).flatMap(r => r.value); const total = Math.round(hours.reduce((a, x) => a + x.v, 0) * 1000) / 1000; const coverage = hours.length / 744; const all = await load('reports.json'); const reported = all.historicalReports[dates[i]].buildings.Fox_office_Joy; const good = Math.abs(total - reported.actual_kwh.value) < .0005 && Math.abs(coverage - reported.coverage.value) < .00002; const el = document.getElementById('asof-recomputed'); if (el)
    el.innerHTML = `<span class="recompute-state ${good ? 'recompute-state--pass' : 'recompute-state--fail'}"><strong>${good ? '✓ Browser recomputation matches the archived output' : '✕ Recomputed values differ'}</strong></span><br/>${hours.length} hourly readings · ${fmt(total, 2)} kWh · ${fmt(coverage * 100, 2)}% coverage · selected transaction cutoff ${dates[i]}. This is a recalculated total and coverage, not an independent evaluation of the full baseline regression.`; }
async function provenance() {
    const countRows = [['A1', 'Device signature', '271 meter-day records, 6,497 signed readings', 'Device identity / physical location'], ['A2', 'Authority signature over field, value, unit and validity', '93 signed claims: 90 days of weather, 3 floor areas', 'Authorized authority and signed scope'], ['A2-', 'Notarised source', 'No sample', 'Notary'], ['B', 'Signed installation certificate', '3 certificates, one per meter', 'Installer competence / real binding'], ['B-', 'Third-party extraction', 'No sample', 'Extraction quality'], ['C+', 'Owner-uploaded document', '1 uploaded occupancy schedule', 'Custody chain'], ['C', 'Manual entry / unverified training data', '3 baselines, 2 manual occupant counts, 271 gate decisions', 'Most source assumptions']];
    return `<div class="page-heading"><div class="breadcrumb">DIYAR / Trust model</div><div class="eyebrow">WHERE EVIDENCE COMES FROM MATTERS</div><h1>Provenance & trust boundaries</h1><p>Follow each claim to its weakest required source. A signature is not physical proof.</p></div>${provenanceGraph()}${await provenanceCharts(load)}<details class="v52-secondary-detail"><summary>How grades are inherited</summary>${provenanceLineage()}<section class="section"><div class="trust-explainer"><div class="trust-explainer__shape" aria-hidden="true"><span>MEASUREMENT</span><i>↓</i><span>ATTESTATION</span><i>↓</i><span>DERIVATION</span><i>↓</i><span>CLAIM</span></div><div><div class="eyebrow">TRUST IS NOT A COLOR SCALE</div><h2>Inspect the dependency, not just the grade.</h2><p>A digitally signed reading proves who signed the bytes. Building attribution, training provenance and physical reality introduce separate assumptions. DIYAR exposes where each enters the claim.</p><div class="trust-explainer__chips"><span>7 provenance categories</span><span>Explicit residual assumptions</span><span>Grades follow committed inputs</span></div></div></div></section></details><section class="section">${sectionTitle('Seven levels', 'Understand the residual assumptions')}<div class="v52-grade-grid">${countRows.map(([g,a,b,c])=>`<article class="v52-grade-card"><div>${grade(g)}</div><h3>${esc(a)}</h3><p>${esc(b)}</p><details><summary>What you still trust</summary><p>${esc(c)}</p></details></article>`).join('')}</div></section><details class="v52-secondary-detail"><summary>Inspect the source lineage</summary><section class="section">${sectionTitle('Source lineage', 'A building value inherits its weakest needed input')}<div class="grid3 lineage-grid"><div class="card lineage-card lineage-card--device"><div class="lineage-overline"><span>01</span><i aria-hidden="true">⌁</i></div><div class="micro">01 / DEVICE</div><div class="huge">A1</div><h3>Signed hourly reading</h3><p>Checks the reading bytes against a simulated meter public key. Does not establish physical placement.</p></div><div class="card lineage-card lineage-card--binding"><div class="lineage-overline"><span>02</span><i aria-hidden="true">◇</i></div><div class="micro">02 / BINDING</div><div class="huge">B</div><h3>Installer-associated building identity</h3><p>A signed certificate binds each meter key to one building, channel and unit; a missing, revoked or relabelled certificate fails closed.</p></div><div class="card lineage-card lineage-card--baseline"><div class="lineage-overline"><span>03</span><i aria-hidden="true">⇢</i></div><div class="micro">03 / DERIVATION</div><div class="huge">C</div><h3>Unauthenticated baseline training</h3><p>Baselines trained on 2016 data never committed as signed records are graded C, and so is every figure built on them.</p></div></div></section></details>
<section class="section">${sectionTitle('Current implementation boundary', 'Built, measured, or only proposed?')}<div class="v52-capability-grid">${[
        ['Signed hourly meter records', 'implemented', 'Simulated device keys; 6,497 signed readings'], ['256-level SMT commitments', 'implemented', '91 historical roots, test vectors'], ['ECDSA + daily SLH-DSA archive', 'implemented', '91/91 signed days; both verified in this browser'], ['Bitemporal replay', 'implemented', 'One late correction (Joy, 15 January), replayed at 4 moments'], ['Signed claims with unit and validity', 'implemented', 'In the reference run; demo issuer pins'], ['Installer certificates + revocation', 'implemented', 'In the reference run; demo installer pin; no real registry'], ['Grades follow committed inputs', 'implemented', 'Baselines and performance figures graded C'], ['Record chronology, also under python -O', 'implemented', '108 targeted tests pass twice'], ['Conformal seasonal evaluation', 'offline', 'E2 offline on BDG2'], ['Quarterly drift manipulation tests', 'offline', 'E3 controlled injections'], ['60-year custody & cost model', 'offline', 'E1/E4 scenario analysis'], ['Public blockchain anchor', anchored() ? 'testnet' : 'tested', anchorNote()], ['Physical inspection / certified installer', 'designed', 'Not independently demonstrated'], ['Multi-custodian RS retrieval', 'designed', 'No tested external custodian recovery']
    ].map(([a,s,e])=>`<article class="v52-capability"><div><strong>${esc(a)}</strong>${sourceStatus(s)}</div><details><summary>Evidence and limits</summary><p>${esc(e)}</p></details></article>`).join('')}</div></section>${grantsMap()}`;
}
async function results() {
    const e2 = await load('e2_summary.json'), e3 = await load('e3a_quarterly.json'), e1 = await load('e1_summary.json'), x3 = await load('e3a_extra.json');
    const power = e3.power_single_building.filter((x) => x.manipulation === 'shave').filter((x) => [.1, .2, .3, .4].includes(x.size));
    const fo = e2.focus;
    return `<div class="page-heading"><div class="breadcrumb">DIYAR / Offline experimental evidence</div><div class="eyebrow">REPRODUCIBLE RESULTS / NOT LIVE PILOT METRICS</div><h1>Experimental findings</h1><p>Four offline studies. Reproducible figures and explicit limits.</p></div><div class="v4-experiment-index" aria-label="Experimental evidence areas"><span><b>01</b> Custody design</span><span><b>02</b> Statistical calibration</span><span><b>03</b> Detection boundary</span><span><b>04</b> Review economics</span></div><div class="results-grid editorial-results">
 <div class="result-block result-block--storage"><div class="result-orbit" aria-hidden="true"><span></span><span></span><span></span></div><div class="topline"><span class="eyebrow">E1 · LONG-HORIZON CUSTODY</span>${sourceStatus('offline')}</div><div class="huge">29,792 bytes</div><h3>One SLH-DSA-256s signature per daily global root</h3><p>Storage scenarios assume 10,000 buildings, five channels and 15-minute readings over 60 years. This is not an observed footprint for a real facility.</p><div class="mini-note">Raw meter-only custody model excludes full BIM/media, registry operations and independent proof storage.</div></div>
 <div class="result-block result-block--calibration"><div class="topline"><span class="eyebrow">E2 · SEASONAL CALIBRATION</span>${sourceStatus('offline')}</div><div class="huge">17.42% → 5.05%</div><h3>Observed ACI flag rate versus split calibration</h3><p>Across 801 evaluated buildings, the adaptive conformal alert rate was near nominal α=5%. These are unlabeled flags, not verified false positives.</p><div class="calibration-bars">${[['Split', e2.all_sites.split.overall_flag_rate], ['Mondrian', e2.all_sites.mondrian.overall_flag_rate], ['Rolling 28', e2.all_sites.rolling28.overall_flag_rate], ['ACI', e2.all_sites.aci.overall_flag_rate]].map(([a, b]) => `<div class="calibration-bar"><div class="calibration-bar__head"><span>${a}</span><strong class="num">${fmt(Number(b) * 100, 2)}%</strong></div><div class="calibration-bar__rail"><span style="width:${Math.min(100, Number(b) / .2 * 100)}%"></span></div></div>`).join('')}</div></div>
 <div class="result-block result-block--detection"><div class="topline"><span class="eyebrow">E3 · DETECTION LIMIT</span>${sourceStatus('offline')}</div><h3>One-sided quarterly power, under-reporting</h3><div class="power-bars" aria-label="Offline quarterly detection power by injected severity">${power.map((r) => `<div class="power-bar"><div class="power-bar__head"><span>${fmt(r.size * 100, 0)}% altered</span><strong class="num">${fmt(r.power_one_sided * 100, 1)}% detected</strong></div><div class="power-bar__rail"><span style="width:${Math.min(100, r.power_one_sided * 100)}%"></span></div></div>`).join('')}</div><p>A separate 1,000-run study measures the 25% point directly: ${fmt(x3.rows.find(r => r.size === .25).power_one_sided * 100, 1)}% detected, ${fmt(x3.rows.find(r => r.size === .25).false_flag_one_sided * 100, 1)}% of unmanipulated buildings flagged.</p></div>
 <div class="result-block result-block--economics"><div class="topline"><span class="eyebrow">E4 · REVIEW ECONOMICS</span>${sourceStatus('offline')}</div><div class="huge">0.189</div><h3>Review cases opened per building-year</h3><p>At α=5% and 106 peers, the rank gate selects five cases per quarterly test by design. Measured value: 0.1887.</p><div class="eyeline"></div><div class="huge">≈ $179</div><p>Per building-year under the workbook scenario; this is not deployed operating cost and excludes newly added trust-governance overhead.</p></div>
 </div><div id="v5-research-figures">${await researchCharts(load)}</div><section class="section">${notice('<strong>Statistical boundary:</strong> A 5% alert rate in unlabelled observations does not establish a 5% false-positive rate. Manipulation power in E3 is conditional on the Fox cohort and injection design. All plotted values here come from the bundled experiment output files.')}</section>`;
}
function trustInfo(g) { if (g === 'none')
    return 'Field missing from published report. That does not by itself constitute an attached non-membership proof.'; const o = grades[g] || grades.C; return `${g}: ${o[1]}. Residual assumption: ${o[2]}. Historical report grade may differ from later V2 policy.`; }
async function drawerBody() {
    const pane = document.getElementById('drawer-body');
    if (!pane)
        return;
    const recordsText = await load('records.jsonl', true);
    const currentLines = recordsText.trim().split('\n').filter(line => line.includes(`"field":"${selectedBuilding}/elec/${selectedDay}"`));
    const proofs = await load('proofs.json');
    const proof = proofs.meterByDay[selectedDay]?.[`${selectedBuilding}/elec/${selectedDay}`];
    const rec = currentLines.map(l => JSON.parse(l));
    const current = rec[0];
    if (!current) {
        pane.innerHTML = 'No records found';
        return;
    }
    pane.innerHTML = `<button class="icon-btn drawer-close" data-action="close-drawer" aria-label="Close evidence drawer">✕</button><div style="padding-top:44px" class="eyebrow">EVIDENCE / EXACT PUBLISHED BYTES</div><h2>${esc(selectedDay)}</h2><div class="drawer-sub">${selectedBuilding} · Meter record · ${rec.length} version${rec.length > 1 ? 's' : ''}</div><div class="eyeline"></div><div class="grid3" style="grid-template-columns:repeat(3,1fr);gap:8px">${metric('Readings', String(current.value.length), 'Hourly rows')}${metric('Grade', String(current.grade), 'Historical record')}${metric('Versions', String(rec.length), 'Append-only')}</div><h3>Record timeline</h3>${rec.map((r, i) => `<div class="mini-note"><span class="micro">Version ${i + 1}</span><div style="margin:8px 0">Valid: ${r.valid_from} · Recorded: ${r.tx_time}</div><div>${r.value.length} readings · ${fmt(r.value.reduce((s, x) => s + x.v, 0), 3)} kWh · ${grade(r.grade)}</div></div>`).join('')}<div class="eyeline"></div><div class="micro">Version 1 record hash · SHA256(0x10 + canonical JSON)</div><div style="margin:11px 0">${hashView(recordHashCanonicalLine(currentLines[0]), true)}</div><div class="micro">Merkle proof for signed day root</div><div class="small" style="margin:9px 0">${proof ? `${proof.siblings.length} non-default siblings · ${32 + 32 * proof.siblings.length} bytes including 256-bit mask · ${verifyProof(proof) ? 'proof recomputed locally' : 'proof differs'}` : 'No proof exported for this day'}</div>${btn('Verify this day →', 'verify-day', `data-day="${selectedDay}"`)}<h3 style="margin-top:28px">Exact canonical JSONL record</h3><div class="small" style="margin:8px 0">These are the actual bytes hashed by the reference encoder; not a JavaScript-reserialized approximation.</div><pre class="codeblock" id="canonical-json">${esc(currentLines[0])}</pre><button class="btn btn-sm" data-action="copy" data-value="${esc(currentLines[0])}">Copy exact record bytes</button><div id="day-checks" style="margin-top:22px"></div>`;
}
function toast(msg) { const t = document.getElementById('toast'); if (!t)
    return; t.innerHTML = `<div class="toast">${esc(msg)}</div>`; setTimeout(() => { if (t)
    t.innerHTML = ''; }, 2600); }
function getRoute() { const key = location.hash.slice(1).split('?')[0]; return key in labels ? key : 'home'; }
async function render() {
    current = getRoute();
    let body = '';
    root.innerHTML = '<div class="boot"><span class="symbol">D</span>Loading evidence…</div>';
    try {
        if (current === 'home')
            body = await home();
        else if (current === 'explorer')
            body = await explorer();
        else if (current === 'verify') { ledgerCache=await load('ledger.json');body = await verify(); }
        else if (current === 'replay')
            body = await replay();
        else if (current === 'provenance')
            body = await provenance();
        else if (current === 'results')
            body = await results();
        else if (current === 'owner')
            body = await owner();
        else if (current === 'lender')
            body = await lender();
        document.body.dataset.diyarPage = current;
        document.body.dataset.room = roomMap[current];
        if(current==='owner'){
            let i=0;body=body.replace(/<section class="section">/g,m=>{i++;return i===1?'<section class="section" id="owner-step-1">':i===2?'<section class="section" id="owner-step-3">':m;});
        }
        if(current==='lender'){let i=0;body=body.replace(/<section class="section">/g,m=>{i++;let ids=['lender-step-1','lender-step-2','lender-step-3','lender-step-4'];return ids[i-1]?`<section class="section" id="${ids[i-1]}">`:m;});body=body.replace('<div class="card verdict-card">','<div class="card verdict-card" id="lender-step-5">');}
        const headlineParts={owner:['Then try to cheat.'],lender:['your desk.'],verify:['verification'],replay:['history.'],explorer:['Explorer'],provenance:['trust boundaries'],results:['findings']};
        for(const word of headlineParts[current]||[]){body=body.replace(new RegExp('(<h1>[^<]*?)('+word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')(</h1>)','i'),(_m,a,b,c)=>a+'<span class=\"gradient-text\">'+b+'</span>'+c)}
        root.innerHTML = frame(body, current);
        condenseExposition(root);
        enhanceMotion(root);
        countPublishedFigures(root);
        if (current === 'home') bindRotatingWord();
        updateStickyOffset();
        if (drawerOpen){ await drawerBody();document.querySelector('.drawer-close')?.focus();}
        if (current === 'replay')
            await recomputeAsOf();
        if (current === 'verify')
            renderChecks();
    }
    catch (e) {
        root.innerHTML = frame(`<div class="page-heading"><h1>Evidence could not be loaded</h1><p>${esc(e instanceof Error ? e.message : String(e))}</p><a class="btn" href="#home">Back home</a></div>`, current);
    }
}
function renderChecks() { const el = document.getElementById('verification-panel'); if (el)
    el.innerHTML = verificationPanel(); }
function updateStickyOffset() { const honesty = document.querySelector('.honesty'); if (honesty)
    document.documentElement.style.setProperty('--honesty-height', honesty.getBoundingClientRect().height + 'px'); }
function showResults(msg) {
    if (roleMessage(msg))
        return;
    if (msg.type === 'check') {
        checkList = checkList.filter(x => x.id !== msg.result.id).concat(msg.result);
        renderChecks();
        if (checkMode === 'day') {
            const el = document.getElementById('day-checks');
            if (el)
                el.innerHTML = checkList.map(c => `<div class="check-row"><div>·</div><div><strong>${esc(c.label)}</strong><div class="detail">${esc(c.detail)}</div></div><div class="check-result">${checkStatus(c)}</div></div>`).join('');
        }
    }
    if (msg.type === 'progress') {
        progress[msg.id] = { done: msg.done, total: msg.total };
        if (checkMode === 'all')
            renderChecks();
    }
    if (msg.type === 'complete') {
        verifyRunning = false;
        if (checkMode === 'all')
            renderChecks();
        toast('On-device verification finished. Inspect each check status.');
    }
    if (msg.type === 'tamper-result') {
        tamperResult = msg;
        const e = document.getElementById('tamper-result');
        if (e)
            e.innerHTML = tamperResultHTML();
    }
    if (msg.type === 'error') {
        verifyRunning = false;
        renderChecks();
        toast('Verifier error: ' + msg.message);
    }
}
function getWorker() { if (!worker) {
    worker = new Worker(new URL('./verify-worker.js', import.meta.url), { type: 'module' });
    worker.onmessage = e => showResults(e.data);
    worker.onerror = e => { verifyRunning = false; renderChecks(); toast('Worker could not execute: ' + e.message); };
} return worker; }
function startAll() { if (verifyRunning)
    return; const deep = !!document.getElementById('deep-check')?.checked; verifyRunning = true; checkMode = 'all'; checkList = []; progress = {}; renderChecks(); getWorker().postMessage({ type: 'run-all', deep }); }
async function inspect(day) { selectedDay = day; drawerOpen = true; await render(); }
async function clickAction(el) {
    const action = el.dataset.action;
    switch (action) {
        case 'flow-role':
            chooseRole(el.dataset.role);
            break;
        case 'flow-node':
            chooseNode(el.dataset.node);
            break;
        case 'navigate':
            location.hash = '#' + el.dataset.to;
            break;
        case 'theme': {
            const t = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
            document.documentElement.dataset.theme = t;
            try { localStorage.setItem('diyar-theme', t); } catch { /* private mode: theme still switches */ }
            break;
        }
        case 'menu': {const nav=document.getElementById('main-nav');const opened=nav?.classList.toggle('open');document.querySelector('.menu-btn')?.setAttribute('aria-expanded',String(!!opened));if(opened)nav.querySelector('a')?.focus();break;}
        case 'tour':
            tourIndex = 0;
            await render();
            break;
        case 'tour-next':
            if (tourIndex >= 2) {
                tourIndex = -1;
                await render();
            }
            else {
                tourIndex++;
                await render();
            }
            break;
        case 'tour-prev':
            tourIndex = Math.max(0, tourIndex - 1);
            await render();
            break;
        case 'tour-visit':
            tourIndex = -1;
            break;
        case 'close-tour':
            tourIndex = -1;
            await render();
            break;
        case 'copy': {
            try {
                await navigator.clipboard.writeText(el.dataset.value || '');
                toast('Copied to clipboard');
            }
            catch {
                toast('Clipboard unavailable. Select the text to copy.');
            }
            break;
        }
        case 'chart-view-local':
            break;
        case 'research-filter': {
            const f=el.dataset.filter;
            document.querySelectorAll('.v5-paper-card').forEach(card=>card.hidden=(f!=='All'&&card.dataset.experiment!==f));
            document.querySelectorAll('[data-action="research-filter"]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn===el)));
            document.getElementById('v5-research-figures')?.scrollIntoView({block:'start',behavior:'smooth'});
            break;
        }
        case 'scroll-to':
            document.getElementById(el.dataset.target)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
            break;
        case 'chart-view':
            break;
        case 'inspect-day':
            await inspect(el.dataset.day || selectedDay);
            break;
        case 'close-drawer':
            drawerOpen = false;
            await render();
            break;
        case 'show-trust':
            toast(trustInfo(el.dataset.grade || 'none'));
            break;
        case 'run-checks':
            startAll();
            break;
        case 'verify-day':
            checkMode = 'day';
            checkList = [];
            progress = {};
            document.getElementById('day-checks').innerHTML = notice('Checking Merkle inclusion, signatures and chain locally…');
            getWorker().postMessage({ type: 'verify-day', building: selectedBuilding, day: el.dataset.day || selectedDay });
            break;
        case 'run-tamper': {
            const select = document.getElementById('tamper-select');
            tamperResult = null;
            document.getElementById('tamper-result').innerHTML = notice('Running tamper experiment on a copy…');
            getWorker().postMessage({ type: 'tamper', case: select.value });
            break;
        }
        case 'reset-tamper':
            tamperResult = null;
            document.getElementById('tamper-result').innerHTML = notice('Experiment reset. The published archive has never been modified.');
            break;
        case 'asof':
            asOfIndex = Number(el.dataset.index);
            await render();
            break;
        case 'architecture':
            toast((el.dataset.title || '') + ': ' + (el.dataset.description || ''));
            break;
        case 'scroll-roles':
            document.getElementById('roles')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            break;
        default:
            if (!(await anchorAction(action, el)))
                await roleAction(action, el);
    }
}
document.addEventListener('click', e => { const target = e.target; const act = target.closest('[data-action]'); if (act) {
    if (act.tagName === 'A')
        return;
    e.preventDefault();
    void clickAction(act);
} const pt = target.closest('[data-chartday]'); if (pt) {
    void inspect(pt.dataset.chartday || selectedDay);
} });
document.addEventListener('change', e => { const t = e.target; if (t.id === 'building-select') {
    selectedBuilding = t.value;
    selectedDay = '2017-01-15';
    void render();
} if (t.id === 'asof-range') {
    asOfIndex = +t.value;
    void render();
} });
document.addEventListener('pointerover', e => { const pt = e.target.closest('[data-chartday]'); if (!pt)
    return; void getBuilding().then(b => { const d = b.days.find(x => x.day === pt.dataset.chartday); const t = document.getElementById('chart-tip'); if (!d || !t)
    return; t.classList.remove('hidden'); t.innerHTML = `<strong>${d.day}</strong><br/>${fmt(d.kwh)} kWh · ${d.hours} hours<br/>Baseline ${d.baseline !== null ? fmt(d.baseline) : 'n/a'} kWh<br/>${esc(d.gate)} · ${d.versions} version(s)`; const box = pt.getBoundingClientRect(), parent = t.parentElement.getBoundingClientRect(); t.style.left = Math.max(0, Math.min(parent.width - 230, box.left - parent.left - 80)) + 'px'; t.style.top = (box.top - parent.top - 90) + 'px'; }); });
document.addEventListener('keydown', e => { if(e.key==='Escape'){const nav=document.getElementById('main-nav');if(nav?.classList.contains('open')){nav.classList.remove('open');document.querySelector('.menu-btn')?.focus();}else if(drawerOpen){drawerOpen=false;void render();}else if(tourIndex>=0){tourIndex=-1;void render();}} if(e.key==='Tab'){const modal=document.querySelector('.drawer[aria-modal="true"]')||document.querySelector('#main-nav.open');if(modal){const f=[...modal.querySelectorAll('a,button,input,select,[tabindex]:not([tabindex="-1"])')].filter(x=>!x.disabled);if(f.length){let i=f.indexOf(document.activeElement);if(e.shiftKey&&i===0){e.preventDefault();f.at(-1).focus();}else if(!e.shiftKey&&i===f.length-1){e.preventDefault();f[0].focus();}}}} const key = e.key; const t = e.target; const point = t.closest?.('[data-chartday]'); if (point && (key === 'Enter' || key === ' ')) {
    e.preventDefault();
    void inspect(point.dataset.chartday || selectedDay);
} });
document.addEventListener('pointerout', e => { const pt = e.target.closest?.('[data-chartday]'); if (pt)
    document.getElementById('chart-tip')?.classList.add('hidden'); });
window.addEventListener('hashchange', () => { drawerOpen = false; window.scrollTo(0, 0); void render(); });
(async () => { try {
    let stored = null;
    try { stored = localStorage.getItem('diyar-theme'); } catch { /* storage blocked: use system theme */ }
    if (stored === 'light')
        document.documentElement.dataset.theme = 'light';
    else if (stored === 'dark')
        document.documentElement.dataset.theme = 'dark';
    else
        document.documentElement.dataset.theme = matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    summary = await load('summary.json');
    summary.publishedGrade = (await load('reports.json')).published.Fox_office_Joy.actual_kwh.grade;
    await initAnchor({ esc, fmt, load, btn, notice, hashView, sectionTitle });
    initRoles({ esc, fmt, load, grade, btn, notice, metric, hashView, sectionTitle, post: (m) => getWorker().postMessage(m), rerender: () => render() });
    await render();
}
catch (e) {
    root.textContent = e instanceof Error ? e.message : String(e);
} })();
window.addEventListener('resize', updateStickyOffset);
