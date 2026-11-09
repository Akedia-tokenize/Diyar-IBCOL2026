import {weakestLink,cheatMap,lenderDecision} from './diagrams.js';
import {ownerCharts,lenderCharts} from './viz-pages.js';
/* DIYAR role pages: the building owner and the lender. The auditor uses Verify, Replay and Explorer.
   Everything shown comes from the published reference-run files or from checks run in this browser;
   the arrival-path choice and the cheating slider are labelled simulations built on those files. */

import { anchorHint } from './anchor.js';
import { miniJourney } from './flows.js';

let C = null;                       // helpers shared by app.js: esc, fmt, load, grade, btn, notice, metric, hashView, post
export function initRoles(ctx) { C = ctx; }

const BUILDING = 'Fox_office_Joy';
let path = 'meter';
let shave = 20;
let job = null;                     // the worker job this page is waiting for

const PATHS = {
    meter: { title: 'Signed by the meter', sub: 'Every hourly reading carries the meter’s own signature', reading: 'A1', figure: 'B',
        trust: 'the installer who bound meter-000 to this building',
        why: 'The readings are A1. Their link to this building is a signed installation certificate, grade B, and a building figure takes the weaker of the two.' },
    utility: { title: 'The utility’s signed statement', sub: 'The utility signs the monthly figure for this building', reading: 'A2', figure: 'A2',
        trust: 'the utility as an authoritative source',
        why: 'The utility vouches for the value and for the building, so the figure is A2.' },
    upload: { title: 'Upload your own bill', sub: 'A PDF from your files', reading: 'C+', figure: 'C+',
        trust: 'how the file was kept before you sent it',
        why: 'Nobody independent signed it. DIYAR keeps the file exactly as received, and no more.' },
    typed: { title: 'Type the number in', sub: 'Entered by hand in a form', reading: 'C', figure: 'C',
        trust: 'everything',
        why: 'Nothing about the number can be checked.' },
};

const pct = (x, d = 0) => (x * 100).toFixed(d) + '%';

/* ------------------------------------------------------------------ owner ---------------- */
let curve = null;
async function detectionCurve() {
    if (curve) return curve;
    const q = await C.load('e3a_quarterly.json'), x = await C.load('e3a_extra.json');
    const pts = new Map();
    for (const r of q.power_single_building.filter(r => r.manipulation === 'shave')) pts.set(r.size, { p: r.power_one_sided, src: 'E3 quarterly data' });
    for (const r of x.rows) if (!pts.has(r.size)) pts.set(r.size, { p: r.power_one_sided, src: 'E3 additional data' });
    const ff = q.power_single_building.filter(r => r.manipulation === 'shave').map(r => r.false_flag_one_sided);
    pts.set(0, { p: ff.reduce((a, b) => a + b, 0) / ff.length, src: 'false flags, unmanipulated' });
    curve = [...pts.entries()].map(([s, v]) => ({ s, ...v })).sort((a, b) => a.s - b.s);
    return curve;
}
function detectAt(c, s) {
    const exact = c.find(r => Math.abs(r.s - s) < 1e-9);
    if (exact) return { p: exact.p, measured: true };
    const hi = c.findIndex(r => r.s > s);
    if (hi <= 0) return { p: c[c.length - 1].p, measured: false };
    const a = c[hi - 1], b = c[hi];
    return { p: a.p + (b.p - a.p) * (s - a.s) / (b.s - a.s), measured: false };
}
function curveSvg(c, s) {
    const W = 420, H = 210, L = 44, R = 12, T = 12, B = 30, iw = W - L - R, ih = H - T - B, max = 0.4;
    const x = v => L + v / max * iw, y = p => T + ih - p * ih;
    const line = c.filter(r => r.s <= max).map((r, i) => `${i ? 'L' : 'M'}${x(r.s).toFixed(1)} ${y(r.p).toFixed(1)}`).join(' ');
    const d = detectAt(c, s / 100);
    const grid = [0, .25, .5, .75, 1].map(p => `<line class="chart-grid" x1="${L}" x2="${W - R}" y1="${y(p)}" y2="${y(p)}"/><text class="chart-label" x="${L - 8}" y="${y(p) + 4}" text-anchor="end">${p * 100}%</text>`).join('');
    const ticks = [0, .1, .2, .3, .4].map(v => `<text class="chart-label" x="${x(v)}" y="${H - 10}" text-anchor="middle">${v * 100}%</text>`).join('');
    const dots = c.filter(r => r.s <= max && r.s > 0).map(r => `<circle cx="${x(r.s)}" cy="${y(r.p)}" r="3.5" class="curve-dot"><title>${pct(r.s, 1)} under-report: ${pct(r.p, 1)} caught (${r.src})</title></circle>`).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Share of quarters in which the gate catches an under-report, by its size">${grid}${ticks}
<path d="${line}" class="curve-line" fill="none"/>${dots}
<line x1="${x(s / 100)}" x2="${x(s / 100)}" y1="${T}" y2="${T + ih}" class="curve-now"/><circle cx="${x(s / 100)}" cy="${y(d.p)}" r="6" class="curve-now-dot"/></svg>`;
}
function shaveVerdict(s, p) {
    if (s === 0) return 'An honest building is still flagged in about 4 of 100 quarters. That is the price of any test, and why a flag opens a review rather than a verdict.';
    if (p < 0.5) return 'This mostly passes the gate. A quarterly test among honest peers cannot see a small, steady shave: a statistical limit, not a bug.';
    if (p < 0.8) return 'Caught in most quarters, but not reliably.';
    return 'Caught in at least 4 of 5 quarters.';
}

export async function owner() {
    const pth = PATHS[path];
    const c = await detectionCurve();
    const d = detectAt(c, shave / 100);
    const rep = (await C.load('reports.json')).published[BUILDING];
    return `<div class="page-heading"><div class="eyebrow">Role 1 · Building owner</div><h1>Get your number accepted. Then try to cheat.</h1>
<p>January 2017, ${BUILDING.replaceAll('_',' ')}: <b class="num">${C.fmt(rep.actual_kwh.value)} kWh</b>. DIYAR does not ask whether the number is true. It records how the number reached it, and grades it by that path.</p></div>
${miniJourney('owner')}
<section class="section">${C.sectionTitle('Step 1', 'How does your number arrive?', 'Same number, four routes. Pick one.')}
<div class="path-grid" role="radiogroup" aria-label="Arrival path">${Object.entries(PATHS).map(([k, v]) => `<button type="button" role="radio" aria-checked="${k === path}" class="path-option ${k === path ? 'active' : ''}" data-action="owner-path" data-path="${k}"><strong>${v.title}</strong><span>${v.sub}</span><span class="path-grade">${C.grade(v.reading)}</span></button>`).join('')}</div>
<div id="owner-step-2"></div><div class="card path-result"><div class="path-flow"><div><div class="micro">Reading</div>${C.grade(pth.reading, true)}</div><div class="path-arrow" aria-hidden="true">→</div><div><div class="micro">January figure for the building</div>${C.grade(pth.figure, true)}</div><div class="path-value"><div class="micro">Value</div><div class="num">${C.fmt(rep.actual_kwh.value)} kWh</div></div></div>
<p>${pth.why}</p><p class="small"><b>What a lender still has to trust:</b> ${pth.trust}.</p>
${path === 'meter' ? `<div class="toolbar">${C.btn('Check one real signed day →', 'owner-verify-day')}<span class="small">Runs on the published 20 January record, in this browser.</span></div><div id="owner-day"></div>` : `<p class="tiny">Simulated: in the reference run, Joy’s readings arrive signed by the meter. The other routes show how the grade would differ.</p>`}
</div>${weakestLink(pth.reading,pth.figure,C.fmt(rep.actual_kwh.value))}${await ownerCharts(C.load)}</section>

<section class="section">${C.sectionTitle('Step 2', 'Now try to cheat', 'Three ways. Each is answered by a different part of DIYAR, or by nothing.')}
<div class="cheat-grid">
<div class="card"><div class="micro">Cheat A · change the bytes</div><h3>Edit one signed reading by 10%</h3><p>Runs on the real 20 January record.</p>${C.btn('Try it →', 'owner-cheat-edit')}<div id="owner-cheat-edit"></div></div>
<div class="card cheat-wide"><div class="micro">Cheat B · shave the whole quarter</div><h3>Under-report every day by <span class="num" id="shave-label">${shave}%</span></h3>
<input type="range" id="shave" min="0" max="40" step="2.5" value="${shave}" aria-label="Under-report size in percent"/>
<div class="shave-out"><div><div class="huge num" id="shave-p">${Math.round(d.p * 100)}%</div><div class="small">of quarters caught by the slow gate${d.measured ? '' : ' (between measured points)'}</div></div><div class="shave-chart" id="shave-chart">${curveSvg(c, shave)}</div></div>
<p id="shave-text">${shaveVerdict(shave, d.p)}</p>
<p class="tiny">From experiment E3 (offline, 106 Fox buildings, one under-reporting building among honest peers, 1,000 runs per point). Dots are measured; the line between them is straight interpolation.</p></div>
<div class="card"><div class="micro">Cheat C · make the meter lie</div><h3>A wrong reading, correctly signed</h3><p>No signature can catch this: the meter signs what it measures. Physical binding and inspection are the only answer, and they are outside cryptography.</p><span class="tag flag">Not detectable by cryptography</span></div>
</div>${cheatMap()}</section>

<section class="section">${C.notice('<strong>What this shows:</strong> changed bytes, removed days and forged proofs are caught every time. Small, steady under-reporting and a lying meter are not. That is why every figure keeps its grade: whatever passes the gate still carries the weight of the route it came by.')}</section>`;
}

/* ------------------------------------------------------------------ lender --------------- */
const RELY = {
    A1: ['yes', 'Rely'], A2: ['yes', 'Rely'], 'A2-': ['yes', 'Rely'],
    B: ['cond', 'Rely, with one named assumption'], 'B-': ['cond', 'Rely, with one named assumption'],
    'C+': ['no', 'Not on its own'], C: ['no', 'Not on its own'], derived: ['ctx', 'Context only'],
};
const LABEL = { actual_kwh: 'Metered energy', coverage: 'Hours covered', coverage_weather: 'Weather days covered', kwh_per_m2: 'Energy per m²',
    kwh_per_occupant: 'Energy per occupant', baseline_kwh: 'Expected energy (baseline)', performance_vs_baseline: 'Performance vs baseline', gate_flags: 'Gate flags in January' };
function value(k, v) {
    if (v.value === null || v.value === undefined) return 'Not recorded';
    if (k === 'coverage' || k === 'coverage_weather') return pct(v.value, 2);
    if (k === 'performance_vs_baseline') return (v.value >= 0 ? '+' : '') + pct(v.value, 2);
    if (k === 'gate_flags') return String(v.value);
    return C.fmt(v.value, k === 'kwh_per_m2' ? 2 : k === 'actual_kwh' ? 2 : 0) + (k === 'kwh_per_m2' ? ' kWh/m²' : ' kWh');
}

export async function lender() {
    const reps = await C.load('reports.json');
    const r = reps.published[BUILDING];
    const times = Object.keys(reps.historicalReports);
    const later = reps.historicalReports[times[times.length - 1]].buildings[BUILDING];
    const order = ['actual_kwh', 'coverage', 'kwh_per_m2', 'coverage_weather', 'baseline_kwh', 'performance_vs_baseline', 'kwh_per_occupant', 'gate_flags'];
    const rows = order.filter(k => r[k]).map(k => {
        const g=r[k].grade||'derived',[cls,txt]=RELY[g]||RELY.C;
        const trust=(r.residual_assumptions||{})[k]||(g==='derived'?'the inputs it was computed from':'Not stated');
        return `<article class="v52-lender-card"><div class="v52-claim-head"><h3>${LABEL[k]||k}</h3>${g==='derived'?'<span class="v52-derived">Derived</span>':C.grade(g)}</div><div class="v52-lender-value">${value(k,r[k])}</div><div class="v52-rely v52-rely--${cls}">${cls==='yes'?'◉':cls==='cond'?'◐':'○'} ${txt}</div><details><summary>Trust assumption</summary><p>${C.esc(trust)}</p></details></article>`;
    }).join('');
    const delta = later.actual_kwh.value - r.actual_kwh.value;
    return `<div class="page-heading"><div class="eyebrow">Role 2 · Bank or valuer</div><h1>A green claim lands on your desk.</h1>
<p>Which figures can a lender rely on, and why?</p></div>
${miniJourney('lender')}
<section class="section"><div class="card claim-card"><div class="micro">The claim, as published on 5 February 2017</div>
<div class="claim-line"><div><div class="huge num">${C.fmt(r.actual_kwh.value)} <small>kWh</small></div><div class="small">electricity used in January</div></div>
<div><div class="huge num">${value('kwh_per_m2', r.kwh_per_m2).replace(' kWh/m²', '')} <small>kWh/m²</small></div><div class="small">per square metre of floor</div></div>
<div><div class="huge num">${value('performance_vs_baseline', r.performance_vs_baseline)}</div><div class="small">against the building’s own baseline</div></div></div>
<div class="demo-foot"><span class="micro">Report hash</span>${C.hashView(r.output_hash)}</div></div></section>

<section class="section">${C.sectionTitle('What each number rests on', 'Grade, assumption, and what you can do with it')}
<div class="v52-lender-grid">${rows}</div>
<div class="card verdict-card"><div class="micro">Verdict</div><h3>Use the metered energy. Do not lend against the performance claim alone.</h3>
<p>Energy, coverage and energy per m² are grade B: the readings are meter-signed, and the only assumption left is the installer who bound the meter to this building. The baseline, and so the comparison with it, is grade C: it was trained on 2016 data that was never committed as signed records.</p></div>${lenderDecision()}${await lenderCharts(C.load)}</section>

<section class="section">${C.sectionTitle('Check it yourself', 'Six checks on this claim, run in this browser')}
<div class="toolbar">${C.btn('Check this claim →', 'lender-check')}<span class="small">Uses only the published files: report, records, ledger, certificate, demo pins.</span></div><div id="claim-checks"></div>${anchorHint()}</section>

<section class="section">${C.sectionTitle('Was it changed later?', 'Corrections are appended, never written over')}
<div class="replay-compare"><div class="card"><div class="micro">As published (known on 4 Feb)</div><div class="replay-value num">${C.fmt(r.actual_kwh.value)} <small style="font-size:13px">kWh</small></div><div class="small">Coverage ${pct(r.coverage.value, 2)}</div></div>
<div class="card"><div class="micro">As known now (after 20 Feb)</div><div class="replay-value num">${C.fmt(later.actual_kwh.value)} <small style="font-size:13px">kWh</small></div><div class="small">Coverage ${pct(later.coverage.value, 2)} · ${delta >= 0 ? '+' : ''}${C.fmt(delta)} kWh from 6 meter-signed hours that arrived late</div></div></div>
<p class="small">The figure you received still verifies against its own root; a newer version exists beside it. Ask the owner to refresh the claim. <a class="hint-link" href="#replay">See the full replay →</a></p></section>`;
}

/* ------------------------------------------------------------------ actions -------------- */
function checkRow(c, i) {
    const st = c.status;
    return `<div class="check-row check-row--${st}"><span class="index">${String(i + 1).padStart(2, '0')}</span><div class="check-row__body"><div class="check-row__title"><span class="check-row__indicator" aria-hidden="true">${st === 'pass' ? '✓' : st === 'fail' ? '✕' : '·'}</span><strong>${C.esc(c.label)}</strong></div><div class="detail">${C.esc(c.detail)}</div></div><div class="check-result"><span class="tag ${st}">${st === 'pass' ? '✓ PASSED' : st === 'fail' ? '✕ FAILED' : '◌ NOT VERIFIED'}</span><span class="time">${C.esc(c.count || '')} · ${c.ms} ms</span></div></div>`;
}
let results = [];
function startJob(target, message, waiting) {
    job = target; results = [];
    const el = document.getElementById(target);
    if (el) el.innerHTML = C.notice(waiting);
    C.post(message);
}
export function roleMessage(msg) {
    if (!job) return false;
    const el = document.getElementById(job);
    if (msg.type === 'check') {
        results.push(msg.result);
        if (el) el.innerHTML = `<div class="card checklist">${results.map(checkRow).join('')}</div>`;
    } else if (msg.type === 'tamper-result') {
        const ok = msg.status === 'detected';
        if (el) el.innerHTML = `<div class="receipt-label ${ok ? 'receipt-label--pass' : 'receipt-label--warning'}"><strong>${ok ? 'CAUGHT' : 'NOT CAUGHT'}</strong> · ${C.esc(msg.detail)}${Number.isFinite(msg.ms) ? ` · ${msg.ms} ms` : ''}</div>`;
        job = null;
    } else if (msg.type === 'complete') {
        job = null;
    } else if (msg.type === 'error') {
        if (el) el.innerHTML = C.notice('Verifier error: ' + C.esc(msg.message));
        job = null;
    }
    return true;
}
export async function roleAction(action, el) {
    switch (action) {
        case 'owner-path': path = el.dataset.path; await C.rerender(); return true;
        case 'owner-verify-day': startJob('owner-day', { type: 'verify-day', building: BUILDING, day: '2017-01-20' }, 'Checking the 20 January record: Merkle path, 24 meter signatures, chain, ECDSA, SLH-DSA, certificate…'); return true;
        case 'owner-cheat-edit': startJob('owner-cheat-edit', { type: 'tamper', case: 'reading' }, 'Editing a copy of the record in memory and re-checking it…'); return true;
        case 'lender-check': startJob('claim-checks', { type: 'verify-claim', building: BUILDING }, 'Checking the claim…'); return true;
    }
    return false;
}
document.addEventListener('input', async (e) => {
    if (e.target.id !== 'shave') return;
    shave = +e.target.value;
    const c = await detectionCurve(), d = detectAt(c, shave / 100);
    const set = (id, html) => { const n = document.getElementById(id); if (n) n.innerHTML = html; };
    set('shave-label', shave + '%');
    set('shave-p', Math.round(d.p * 100) + '%');
    set('shave-chart', curveSvg(c, shave));
    set('shave-text', shaveVerdict(shave, d.p));
    const small = document.getElementById('shave-p')?.nextElementSibling;
    if (small) small.textContent = 'of quarters caught by the slow gate' + (d.measured ? '' : ' (between measured points)');
});
