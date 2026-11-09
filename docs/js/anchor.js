/* Public anchor on the Sepolia testnet (Verify page).
   data/anchor.json only says where to look: the contract and its two transactions. Nothing in it is trusted.
   "Check against Sepolia" asks a public node for the contract's code, the transactions, the Anchored events and
   the current contract state, and compares every value with the published ledger and the compiled contract.
   Read-only JSON-RPC: no wallet, no key, and no request at all until the button is pressed. */
import { sha256, hex, unhex, concat, bytes } from './crypto.js';

const CHAIN_ID = '0xaa36a7';                                   // Sepolia, 11155111
const EXPLORER = 'https://sepolia.etherscan.io';
const RPCS = ['https://ethereum-sepolia-rpc.publicnode.com', 'https://sepolia.drpc.org'];  // = connect-src in index.html
// Fingerprint of anchor/DiyarAnchor.sol compiled with solc 0.8.26 (anchor/DiyarAnchor.json; rebuild with anchor/compile.cjs).
const CONTRACT = {
    compiler: 'solc 0.8.26 (optimizer, 200 runs)',
    sourceSha256: 'f2827fe9df9d47ff33d226166ae938dc632eaf48a0e34420f5850a8bbe059c9c',
    runtimeBytes: 1733,
    runtimeSha256Masked: '9d49ba161b05c11db1b8de51cc0375317163d5bc0bf15ae9e1b7094ca99190d3',
    immutables: [[237, 32], [417, 32], [649, 32]],             // where the compiler inlines the operator address
    topic: '0x0e56cecc6f7e15cf634b1e758cd88db688d2577468035096bafac33043458f72', // Anchored(uint64,bytes10,bytes32,bytes32,bytes32)
    sel: { head: '0x8f7dcfa3', count: '0x06661abd', operator: '0x570ca735', rootOf: '0x29a27768' }
};
const LOOKUPS = [['2017-01-20', 'the day the owner page checks'], ['2017-02-05', 'the root the lender page proofs end on'], ['2017-03-31', 'the last day']];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

let C = null, A = null, checks = [], running = false, verdict = null, node = 0, used = new Set();
const L = { steps: [], running: false, verdict: null, worker: null, t0: 0 };   // the in-page EVM run

const isHex = (v, n) => typeof v === 'string' && new RegExp('^0x[0-9a-f]{' + n + '}$').test(v.toLowerCase());
const lc = (v) => String(v ?? '').toLowerCase();
const strip = (v) => lc(v).replace(/^0x/, '');
const short = (h) => { const s = strip(h); return s.length > 20 ? s.slice(0, 8) + '…' + s.slice(-6) : s; };
/** Short forms of two values that differ; full forms when the short forms would look the same. */
const two = (a, b) => short(a) === short(b) ? [strip(a), strip(b)] : [short(a), short(b)];
const shortAddr = (a) => isHex(a, 40) ? lc(a).slice(0, 8) + '…' + lc(a).slice(-4) : '—';
const int = (n) => Number(n).toLocaleString('en-US');
const host = (u) => u.replace(/^https:\/\//, '').split('/')[0];
function dayLabel(d) { const [y, m, dd] = d.split('-'); return `${+dd} ${MONTHS[+m - 1]} ${y}`; }
function utc(iso) {
    const t = new Date(iso);
    if (isNaN(t)) return '—';
    const p = (n) => String(n).padStart(2, '0');
    return `${t.getUTCDate()} ${MONTHS[t.getUTCMonth()]} ${t.getUTCFullYear()}, ${p(t.getUTCHours())}:${p(t.getUTCMinutes())} UTC`;
}

export async function initAnchor(ctx) {
    C = ctx;
    try { A = await C.load('anchor.json'); } catch { A = null; }
}
/** True only for a well-formed deployment record; a pending or broken file shows the not-deployed state. */
export function anchored() {
    return !!A && A.status === 'anchored' && isHex(A.contract, 40) && isHex(A.anchorTx, 64) &&
        (A.deployTx == null || isHex(A.deployTx, 64)) && (A.operator == null || isHex(A.operator, 40)) && Number.isInteger(A.days);
}
export function anchorNote() {
    return anchored() ? `Sepolia testnet only: ${A.days} days in contract ${shortAddr(A.contract)}, ${utc(A.anchoredAt).split(',')[0]}; checkable on the Verify page. Not on mainnet.`
        : 'DiyarAnchor.sol: 17 tests pass; runs on a local EVM on the Verify page; not deployed to a public network';
}
export function anchorHint() {
    if (!anchored()) return '';
    return `<p class="small anchor-hint">These proofs end on the signed root of 5 February 2017. A public contract on the Sepolia testnet holds that root too. <button type="button" class="hint-link linklike" data-action="goto-anchor">Check the anchor →</button></p>`;
}

/* ------------------------------------------------------------------ page section ---------- */
export function anchorSection() {
    if (!anchored()) {
        return `<section class="section" id="anchor">${C.sectionTitle('ANCHOR CONTRACT · RUN IT HERE', 'Run the anchor contract in your browser', 'The design keeps the head of this daily chain, and every day’s root, in a public Ethereum contract that refuses any entry not citing the head before it. This prototype has not deployed it to a public network; the compiled contract runs below on a local EVM inside this page.')}
<div class="anchor-grid"><div class="card anchor-card"><div class="topline"><span class="micro">Status</span><span class="tag tag-outline">Built and tested, not deployed</span></div>
<dl class="anchor-dl"><dt>Contract</dt><dd>DiyarAnchor.sol, solc 0.8.26, ${int(CONTRACT.runtimeBytes)} bytes of runtime code</dd>
<dt>Rules</dt><dd>Recomputes each entry as SHA-256(0x20 || day || root || prev), keeps every root in state, and rejects a fork, an earlier or repeated day, and any writer but the operator</dd>
<dt>Tests</dt><dd>17 of 17 pass against this ledger</dd></dl>
<div class="actions">${C.btn(L.running ? 'Running…' : L.steps.length ? 'Run again ↻' : 'Deploy and anchor 91 days here →', 'anchor-local', L.running ? 'disabled' : '')}<a class="btn btn-quiet" href="./anchor/DiyarAnchor.sol" target="_blank" rel="noopener">Contract source ↗</a><a class="btn btn-quiet" href="./anchor/test-log.txt" target="_blank" rel="noopener">Test log ↗</a></div>
<p class="small">Runs entirely in this browser with ethereumjs (EVM, Cancun rules), on the published contract and data/ledger.json. Nothing is sent anywhere. About 0.4 MB of code loads when you press the button.</p></div>
<div class="card anchor-card"><div class="micro">What this shows, and what it does not</div><ul class="anchor-list">
<li><span class="anchor-mark anchor-mark--yes" aria-hidden="true">✓</span><span><strong>The contract’s own rules, on the real bytecode.</strong> Every entry is recomputed and every root kept in state; a fork, a rewritten day and an outside writer are rejected.</span></li>
<li><span class="anchor-mark" aria-hidden="true">○</span><span><strong>Not a public blockchain.</strong> This run exists only in your browser, so it witnesses nothing for anyone else. Deployed on a public chain, the same contract would.</span></li>
<li><span class="anchor-mark" aria-hidden="true">○</span><span><strong>No timestamp.</strong> Only a public chain can show that a root existed by a given time.</span></li></ul></div></div>
<div id="anchor-local">${localHTML()}</div></section>`;
    }
    const range = A.firstDay && A.lastDay ? `${dayLabel(A.firstDay)} – ${dayLabel(A.lastDay)}` : '';
    const label = running ? 'Checking Sepolia…' : checks.length ? 'Check again ↗' : 'Check against Sepolia ↗';
    return `<section class="section" id="anchor">${C.sectionTitle('PUBLIC ANCHOR · SEPOLIA TESTNET', 'Check the archive against a public blockchain', 'Every signed day above ends in one 32-byte head. A contract on the Sepolia testnet holds that head and each day’s root, and refuses any entry that does not cite the head before it.')}
<div class="anchor-grid"><div class="card anchor-card"><div class="topline"><span class="micro">Deployment record · data/anchor.json</span><span class="tag tag-outline">Deployed on a testnet</span></div>
<dl class="anchor-dl"><dt>Contract</dt><dd><a class="hint-link" href="${EXPLORER}/address/${lc(A.contract)}" target="_blank" rel="noopener noreferrer">${shortAddr(A.contract)} ↗</a></dd>
<dt>Anchored</dt><dd>${int(A.days)} days${range ? ', ' + range : ''}, in 1 transaction</dd>
<dt>When</dt><dd>${C.esc(utc(A.anchoredAt))}${Number.isInteger(A.anchorBlock) ? ' · block ' + int(A.anchorBlock) : ''}</dd>
<dt>Head</dt><dd>${isHex(A.head, 64) ? C.hashView(strip(A.head)) : '—'}</dd>
<dt>Writer</dt><dd>${shortAddr(A.operator)}, the single operator of phases 0 and 1</dd></dl>
<div class="actions">${C.btn(label, 'anchor-check', running ? 'disabled' : '')}<a class="btn btn-quiet" href="./anchor/DiyarAnchor.sol" target="_blank" rel="noopener">Contract source ↗</a></div>
<p class="small">The record above is only a pointer. The check asks a public Sepolia node (${host(RPCS[0])}, with ${host(RPCS[1])} as fallback) for 12 read-only values, only when you press it. Nothing else on this site contacts a third party.</p></div>
<div class="card anchor-card"><div class="micro">What the anchor shows, and what it does not</div><ul class="anchor-list">
<li><span class="anchor-mark anchor-mark--yes" aria-hidden="true">✓</span><span><strong>No rewrite after the anchor.</strong> Nobody, the operator included, can publish a different history for these days: the contract rejects an entry that does not cite its head, and the head is public.</span></li>
<li><span class="anchor-mark" aria-hidden="true">○</span><span><strong>Not proof the roots existed in 2017.</strong> An anchor proves “no later than” its block time. These 2017 roots were anchored on ${C.esc(utc(A.anchoredAt).split(',')[0])} to demonstrate the mechanism.</span></li>
<li><span class="anchor-mark" aria-hidden="true">○</span><span><strong>No economic security.</strong> Sepolia ether has no value. The design anchors once a day on Ethereum mainnet (Annex D).</span></li></ul></div></div>
<div id="anchor-checks">${checksHTML()}</div>
<div class="card anchor-card anchor-local-card"><div class="topline"><span class="micro">Or run the same contract here</span><span class="tag tag-outline">Local EVM, this browser only</span></div><p class="small">Deploys the published bytecode on a local EVM in this page, anchors the 91 days and tries a fork, a rewrite and an outside writer. Nothing is sent anywhere.</p><div class="actions">${C.btn(L.running ? 'Running…' : L.steps.length ? 'Run again ↻' : 'Run it locally →', 'anchor-local', L.running ? 'disabled' : '', 'btn-quiet')}</div></div>
<div id="anchor-local">${localHTML()}</div></section>`;
}
function checkRow(c, i) {
    const st = c.status;
    return `<div class="check-row check-row--${st}"><span class="index">${String(i + 1).padStart(2, '0')}</span><div class="check-row__body"><div class="check-row__title"><span class="check-row__indicator" aria-hidden="true">${st === 'pass' ? '✓' : st === 'fail' ? '✕' : '·'}</span><strong>${C.esc(c.label)}</strong></div><div class="detail">${C.esc(c.detail)}</div></div><div class="check-result"><span class="tag ${st}">${st === 'pass' ? '✓ PASSED' : st === 'fail' ? '✕ FAILED' : '◌ NOT VERIFIED'}</span><span class="time">${C.esc(c.count ? c.count + ' · ' : '')}${c.ms} ms</span></div></div>`;
}
function checksHTML() {
    if (!checks.length && !running) return '';
    const v = verdict ? `<div class="receipt-label ${verdict.cls}"><strong>${verdict.title}</strong> · ${C.esc(verdict.detail)}</div>` : '';
    const wait = running ? C.notice('Asking a public Sepolia node for the contract code, the two transactions, the Anchored events and the contract state…') : '';
    return `${checks.length ? `<div class="card checklist">${checks.map(checkRow).join('')}</div>` : ''}${wait}${v}`;
}
function paint() {
    const el = document.getElementById('anchor-checks');
    if (el) el.innerHTML = checksHTML();
    const b = document.querySelector('[data-action="anchor-check"]');
    if (b) { b.disabled = running; b.textContent = running ? 'Checking Sepolia…' : checks.length ? 'Check again ↗' : 'Check against Sepolia ↗'; }
}

/* ------------------------------------------------------------------ local EVM run ----------- */
const LOCAL_STEPS = 8;
function localHTML() {
    if (!L.steps.length && !L.running && !L.verdict) return '';
    const v = L.verdict ? `<div class="receipt-label ${L.verdict.cls}"><strong>${L.verdict.title}</strong> · ${C.esc(L.verdict.detail)}</div>` : '';
    const wait = L.running ? C.notice('Deploying the contract on a local EVM in this page and anchoring the 91 days…') : '';
    return `${L.steps.length ? `<div class="card checklist">${L.steps.map(checkRow).join('')}</div>` : ''}${wait}${v}`;
}
function paintLocal() {
    const el = document.getElementById('anchor-local');
    if (el) el.innerHTML = localHTML();
    const b = document.querySelector('[data-action="anchor-local"]');
    if (b) { b.disabled = L.running; b.textContent = L.running ? 'Running…' : L.steps.length ? 'Run again ↻' : (anchored() ? 'Run it locally →' : 'Deploy and anchor 91 days here →'); }
}
function finishLocal(error) {
    const s = ((performance.now() - L.t0) / 1000).toFixed(1), passed = L.steps.filter(x => x.status === 'pass').length;
    L.verdict = error ? { cls: 'receipt-label--warning', title: 'NOT RUN', detail: `the local EVM could not start (${error}). Nothing here is marked as passed.` }
        : passed === LOCAL_STEPS ? { cls: 'receipt-label--pass', title: 'CONTRACT RULES HOLD', detail: `${passed} of ${LOCAL_STEPS} in ${s} s · local EVM in this browser, not a public blockchain` }
            : { cls: 'receipt-label--fail', title: 'CONTRACT CHECK FAILED', detail: `stopped at step ${L.steps.length} of ${LOCAL_STEPS}: ${L.steps[L.steps.length - 1].label.toLowerCase()}` };
    L.running = false;
    paintLocal();
}
function runLocalDemo() {
    if (L.running) return;
    L.running = true; L.steps = []; L.verdict = null; L.t0 = performance.now();
    paintLocal();
    try {
        if (!L.worker) {
            L.worker = new Worker(new URL('./anchor-evm-worker.js', import.meta.url), { type: 'module' });
            L.worker.onmessage = (e) => {
                const m = e.data || {};
                if (m.type === 'local-step') { L.steps.push(m.step); paintLocal(); }
                else if (m.type === 'local-done') finishLocal();
                else if (m.type === 'local-error') finishLocal(m.message);
            };
            L.worker.onerror = (e) => { e.preventDefault?.(); finishLocal(e.message || 'worker error'); L.worker = null; };
        }
        L.worker.postMessage({ type: 'local-run', expect: { runtimeBytes: CONTRACT.runtimeBytes, runtimeSha256Masked: CONTRACT.runtimeSha256Masked } });
    } catch (e) { finishLocal(e && e.message ? e.message : String(e)); }
}

/* ------------------------------------------------------------------ JSON-RPC ---------------- */
class Offline extends Error { }
async function rpcAt(url, method, params) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 15000);
    let r;
    try {
        r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }), signal: ctl.signal, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer' });
    } catch (e) { throw new Offline(e && e.name === 'AbortError' ? 'timed out' : 'unreachable'); }
    finally { clearTimeout(timer); }
    if (!r.ok) throw new Offline('HTTP ' + r.status);
    let j;
    try { j = await r.json(); } catch { throw new Offline('not a JSON-RPC answer'); }
    if (j.error) throw new Error(`${method}: ${j.error.message || 'JSON-RPC error'}`);
    return j.result;
}
async function rpc(method, params = []) {
    let last = null;
    for (let k = 0; k < RPCS.length; k++) {
        const i = (node + k) % RPCS.length;
        try { const v = await rpcAt(RPCS[i], method, params); node = i; used.add(host(RPCS[i])); return v; }
        catch (e) { if (!(e instanceof Offline)) throw e; last = e; }
    }
    throw new Offline(`no public Sepolia node answered (${last ? last.message : 'unreachable'})`);
}
const ethCall = (data) => rpc('eth_call', [{ to: lc(A.contract), data }, 'latest']);
const pass = (detail, count = '') => ({ status: 'pass', detail, count });
const fail = (detail, count = '') => ({ status: 'fail', detail, count });

/* ------------------------------------------------------------------ the six checks ---------- */
async function network() {
    const id = lc(await rpc('eth_chainId'));
    return id === CHAIN_ID ? pass(`Chain id 11155111, answered by ${[...used].join(' and ')}.`) : fail(`The node reports chain id ${parseInt(id, 16)}, not Sepolia (11155111).`);
}
async function code(x) {
    const b = unhex(strip(await rpc('eth_getCode', [lc(A.contract), 'latest'])));
    if (!b.length) return fail('There is no contract code at this address on Sepolia.');
    if (b.length !== CONTRACT.runtimeBytes) return fail(`The code is ${int(b.length)} bytes; DiyarAnchor.sol compiles to ${int(CONTRACT.runtimeBytes)} bytes.`, `${int(b.length)} bytes`);
    const words = CONTRACT.immutables.map(([s, l]) => hex(b.slice(s, s + l)));
    const masked = b.slice();
    for (const [s, l] of CONTRACT.immutables) masked.fill(0, s, s + l);
    const sum = hex(sha256(masked));
    if (sum !== CONTRACT.runtimeSha256Masked) { const [g, w] = two(sum, CONTRACT.runtimeSha256Masked); return fail(`The deployed code differs from DiyarAnchor.sol: SHA-256 ${g} with the operator masked, instead of ${w}.`, `${int(b.length)} bytes`); }
    const op = '0x' + words[0].slice(24), viaCall = '0x' + strip(await ethCall(CONTRACT.sel.operator)).slice(-40);
    if (!words.every(w => w === words[0]) || !/^0{24}/.test(words[0]) || viaCall !== op) return fail('The operator address inside the code is inconsistent.');
    if (A.operator && lc(A.operator) !== op) return fail(`anchor.json names operator ${shortAddr(A.operator)}, but the contract’s operator is ${shortAddr(op)}.`);
    x.operator = op;
    return pass(`${int(b.length)} bytes. With the operator address masked, SHA-256 = ${short(sum)}: the fingerprint of DiyarAnchor.sol (source SHA-256 ${short(CONTRACT.sourceSha256)}) compiled with ${CONTRACT.compiler}. Single writer: ${shortAddr(op)}.`, `${int(b.length)} bytes`);
}
async function transactions(x) {
    const ra = await rpc('eth_getTransactionReceipt', [lc(A.anchorTx)]);
    if (!ra) return fail('The anchor transaction is not on Sepolia.');
    if (ra.status !== '0x1' || lc(ra.to) !== lc(A.contract) || lc(ra.from) !== x.operator) return fail('The anchor transaction failed, or was not sent by the operator to this contract.');
    let deployed = '';
    if (A.deployTx) {
        const rd = await rpc('eth_getTransactionReceipt', [lc(A.deployTx)]);
        if (!rd || rd.status !== '0x1' || lc(rd.contractAddress) !== lc(A.contract)) return fail('The deployment transaction did not create this contract.');
        deployed = `Deployed in block ${int(parseInt(rd.blockNumber, 16))}; `;
    }
    const n = parseInt(ra.blockNumber, 16), blk = await rpc('eth_getBlockByNumber', [ra.blockNumber, false]);
    if (!blk) return fail('The node does not return the anchor block.');
    const depth = parseInt(await rpc('eth_blockNumber'), 16) - n + 1;
    x.receipt = ra;
    return pass(`${deployed}anchored in block ${int(n)} at ${utc(parseInt(blk.timestamp, 16) * 1000)}, now ${int(depth)} blocks deep; sent by the operator to this contract; ${int(parseInt(ra.gasUsed, 16))} gas.`, `${int(depth)} blocks deep`);
}
async function events(x) {
    const ledger = await C.load('ledger.json');
    const logs = (x.receipt?.logs || []).filter(l => lc(l.address) === lc(A.contract) && lc(l.topics?.[0]) === CONTRACT.topic);
    if (logs.length !== ledger.length) return fail(`${logs.length} Anchored events in the transaction; the ledger has ${ledger.length} days.`, `${logs.length}/${ledger.length}`);
    let prevEntry = '0'.repeat(64);
    for (let i = 0; i < logs.length; i++) {
        const d = unhex(strip(logs[i].data)), e = ledger[i];
        if (d.length !== 128 || BigInt(logs[i].topics[1]) !== BigInt(i) || d.slice(10, 32).some(v => v)) return fail(`Event ${i + 1} is malformed.`);
        const day = new TextDecoder().decode(d.slice(0, 10)), root = hex(d.slice(32, 64)), prev = hex(d.slice(64, 96)), entry = hex(d.slice(96, 128));
        const bad = day !== e.day ? ['day', day, e.day] : root !== e.smt_root ? ['root', root, e.smt_root] : prev !== e.prev ? ['previous entry', prev, e.prev] : entry !== e.entry ? ['entry', entry, e.entry] : null;
        if (bad) { const [g, w] = bad[0] === 'day' ? [bad[1], bad[2]] : two(bad[1], bad[2]); return fail(`${e.day}: the anchored ${bad[0]} ${g} differs from the published ledger (${w}).`, `${i}/${ledger.length}`); }
        if (prev !== prevEntry) return fail(`${day}: the anchored chain is broken (previous entry ${short(prev)}, expected ${short(prevEntry)}).`, `${i}/${ledger.length}`);
        if (hex(sha256(concat(Uint8Array.of(0x20), bytes(day), unhex(root), unhex(prev)))) !== entry) return fail(`${day}: the anchored entry does not recompute from its day, root and previous entry.`, `${i}/${ledger.length}`);
        prevEntry = entry;
    }
    return pass(`${logs.length} of ${ledger.length} events equal the ledger day by day (day, root, previous entry, entry), form one unbroken chain from the zero genesis, and every entry recomputes in this browser as SHA-256(0x20 || day || root || prev).`, `${logs.length}/${ledger.length} days`);
}
async function state() {
    const ledger = await C.load('ledger.json'), last = ledger[ledger.length - 1];
    const head = strip(await ethCall(CONTRACT.sel.head)), count = parseInt(strip(await ethCall(CONTRACT.sel.count)) || '0', 16);
    if (head === last.entry && count === ledger.length) return pass(`head() = ${short(head)}, the ledger’s last entry (${dayLabel(last.day)}); count() = ${count}. Nothing has been appended or replaced since.`, `count ${count}`);
    if (count > ledger.length) return fail(`The contract has moved on: count() = ${count}, head ${short(head)}. This archive covers only the first ${ledger.length} entries.`, `count ${count}`);
    const [g, w] = two(head, last.entry);
    return fail(`head() = ${g} and count() = ${count}, but the ledger ends on ${w} after ${ledger.length} days.`, `count ${count}`);
}
async function lookups() {
    const ledger = await C.load('ledger.json'), seen = [];
    for (const [day, why] of LOOKUPS) {
        const e = ledger.find(r => r.day === day);
        const got = strip(await ethCall(CONTRACT.sel.rootOf + hex(bytes(day)).padEnd(64, '0')));
        if (!e || got !== e.smt_root) { const [g, w] = e ? two(got, e.smt_root) : [short(got), 'missing']; return fail(`rootOf("${day}") = ${g}, but the ledger root for that day is ${w}.`); }
        seen.push(`rootOf("${day}") = ${short(got)}, ${why}`);
    }
    return pass(`${seen.join('; ')}. Each equals the ledger, read from contract state rather than from event logs.`, `${LOOKUPS.length} days`);
}
const STEPS = [['network', 'Network is the Sepolia testnet', network], ['code', 'Contract code is DiyarAnchor.sol', code], ['txs', 'Deployment and anchor transactions', transactions],
    ['events', 'Every anchored day equals the published ledger', events], ['state', 'Contract state: head and count', state], ['lookup', 'Roots read back from contract state', lookups]];

async function runChecks() {
    if (running || !anchored()) return;
    running = true; checks = []; verdict = null; used = new Set();
    paint();
    const t0 = performance.now(), x = {};
    let offline = null;
    for (const [id, label, fn] of STEPS) {
        const t = performance.now();
        let r;
        try { r = await fn(x); }
        catch (e) {
            if (e instanceof Offline) { offline = e.message; r = { status: 'unsupported', detail: `Not checked: ${e.message}. Nothing here is marked as passed.` }; }
            else r = fail(e && e.message ? e.message : String(e));
        }
        checks.push({ id, label, ms: Math.round(performance.now() - t), ...r });
        paint();
        if (r.status !== 'pass') break;                       // later checks build on earlier ones
    }
    const s = ((performance.now() - t0) / 1000).toFixed(1), passed = checks.filter(c => c.status === 'pass').length;
    verdict = offline ? { cls: 'receipt-label--warning', title: 'NOT VERIFIED', detail: `${offline}. Try again later; the anchor itself is unaffected.` }
        : passed === STEPS.length ? { cls: 'receipt-label--pass', title: 'ANCHOR CONFIRMED ON SEPOLIA', detail: `${passed} of ${STEPS.length} checks in ${s} s, against ${[...used].join(' and ')}` }
            : { cls: 'receipt-label--fail', title: 'ANCHOR DOES NOT MATCH', detail: `stopped at check ${checks.length} of ${STEPS.length}: ${checks[checks.length - 1].label.toLowerCase()}` };
    running = false;
    paint();
}
function scrollWhenReady(tries = 0) {
    const el = document.getElementById('anchor');
    if (el && location.hash === '#verify' && tries > 1) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
    if (tries < 60) setTimeout(() => scrollWhenReady(tries + 1), 50);
}
export async function anchorAction(action) {
    if (action === 'anchor-check') { await runChecks(); return true; }
    if (action === 'anchor-local') { runLocalDemo(); return true; }
    if (action === 'goto-anchor') { if (location.hash !== '#verify') location.hash = 'verify'; scrollWhenReady(); return true; }
    return false;
}
