// End-to-end test of the Sepolia anchor, offline.
// 1. anchor/deploy.html deploys DiyarAnchor and anchors the 91 days through a mocked wallet backed by a real EVM.
// 2. The Verify page checks that deployment through mocked Sepolia RPC endpoints backed by the same EVM,
//    then again with each answer tampered, a node down, both nodes down, and a pending or broken record.
// usage: node e2e.mjs BASE_URL OUT_DIR
import fs from 'fs';
import { createRequire } from 'module';
import { createChain } from './mockchain.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const BASE = process.argv[2].replace(/\/$/, ''), OUT = process.argv[3];
fs.mkdirSync(OUT, { recursive: true });
const IN = JSON.parse(fs.readFileSync(new URL('./deploy-inputs.json', import.meta.url)));
const RPC = ['https://ethereum-sepolia-rpc.publicnode.com', 'https://sepolia.drpc.org'];
const errors = [], report = {};
// the WCAG contrast routine of contrast.py, reused as is
const CJS = (() => { for (const f of ['../tools/contrast.py', '../_dev/contrast.py', './contrast.py']) { try { return fs.readFileSync(new URL(f, import.meta.url), 'utf8').split('JS = r"""')[1].split('"""')[0]; } catch { /* try the next place */ } } return null; })();
const lowContrast = async (page) => CJS ? page.evaluate(`(${CJS})()`) : [];
const STATIC_HEADER = 'header, .honesty { position: static !important; }';
let pass = 0, fail = 0;
const tests = [];
const ok = (name, cond, extra = '') => { cond ? pass++ : fail++; tests.push(`${cond ? 'PASS' : 'FAIL'} ${name}`); console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  · ' + String(extra).slice(0, 240) : ''}`); };
const watch = (page, tag) => {
    page.on('pageerror', e => errors.push(`${tag} pageerror: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') errors.push(`${tag} console: ${m.text()}`); });
};

const chain = await createChain();
const browser = await chromium.launch();

/* ---------------------------------------------------------------- 1. operator tool ---------- */
const wctx = await browser.newContext({ viewport: { width: 1100, height: 1000 }, deviceScaleFactor: 2, colorScheme: 'light' });
const w = await wctx.newPage();
watch(w, 'deploy');
await w.exposeFunction('__wallet', async (method, params) => {
    try { return { result: await chain.request(method, params) }; } catch (e) { return { error: { code: e.code ?? -32000, message: e.message } }; }
});
await w.addInitScript(() => {
    window.ethereum = {
        isMetaMask: true, on() { }, removeListener() { },
        async request({ method, params }) {
            const r = await window.__wallet(method, params ?? []);
            if (r.error) throw Object.assign(new Error(r.error.message), { code: r.error.code });
            return r.result;
        }
    };
});
chain.st.chainId = '0x1';                                            // the wallet starts on mainnet
await w.goto(`${BASE}/anchor/deploy.html`);
await w.click('#connect');
await w.waitForSelector('#s1 .ok');
ok('operator tool switches the wallet to Sepolia first', chain.st.chainId === '0xaa36a7');
chain.st.chainId = '0x1';                                            // the user moves the wallet back to mainnet
let sent = chain.receipts.size;
await w.click('#deploy');
await w.waitForSelector('#s2 .bad');
ok('refuses to send on any chain but Sepolia', chain.receipts.size === sent, await w.textContent('#s2'));
chain.st.chainId = '0xaa36a7';
await w.click('#deploy');
await w.waitForSelector('#s2 .ok', { timeout: 30000 });
await w.click('#anchor');
await w.waitForSelector('#s3 .ok', { timeout: 60000 });
const record = JSON.parse(await w.inputValue('#out'));
ok('deployment record is complete', record.status === 'anchored' && record.days === 91 && record.head === IN.expectedHead && /^0x[0-9a-f]{40}$/.test(record.contract)
    && record.operator === chain.account && /^0x[0-9a-f]{64}$/.test(record.anchorTx) && /^0x[0-9a-f]{64}$/.test(record.deployTx) && record.firstDay === '2016-12-31' && record.lastDay === '2017-03-31',
    JSON.stringify(record));
ok('gas through the tool equals the local measurement', record.gasDeploy === 427275 && record.gasAnchorBatch === 2586922, `${record.gasDeploy} / ${record.gasAnchorBatch}`);
ok('operator tool: no text below WCAG contrast (light)', (await lowContrast(w)).length === 0, JSON.stringify(await lowContrast(w)));
await w.screenshot({ path: `${OUT}/deploy-tool-light.png`, fullPage: true });
await w.emulateMedia({ colorScheme: 'dark' });
ok('operator tool: no text below WCAG contrast (dark)', (await lowContrast(w)).length === 0, JSON.stringify(await lowContrast(w)));
await w.screenshot({ path: `${OUT}/deploy-tool-dark.png`, fullPage: true });
await w.emulateMedia({ colorScheme: 'light' });
sent = chain.receipts.size;
await w.reload();
await w.click('#connect');
await w.waitForSelector('#s3 .ok', { timeout: 30000 });
ok('a reload resumes from the stored contract and sends nothing', chain.receipts.size === sent && JSON.parse(await w.inputValue('#out')).anchorTx === record.anchorTx);
await w.click('#anchor').catch(() => { });
ok('cannot anchor twice into the same contract', chain.receipts.size === sent && (await w.isDisabled('#anchor') || /already holds/.test(await w.textContent('#s3'))));
await wctx.close();
fs.writeFileSync(`${OUT}/anchor.json`, JSON.stringify(record, null, 1) + '\n');

/* ---------------------------------------------------------------- 2. Verify page ------------ */
const anchorTx = record.anchorTx.toLowerCase();
async function site({ rec = record, theme = 'dark', phone = false, down = [], override = null, ledgerDay = null } = {}) {
    const ctx = await browser.newContext(phone ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: theme }
        : { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: theme });
    const page = await ctx.newPage();
    watch(page, 'site');
    const calls = [];
    await page.route('**/data/anchor.json', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(rec) }));
    if (ledgerDay) await ctx.route('**/data/ledger.json', async (r) => {
        const res = await r.fetch(); const l = await res.json(); const e = l.find(x => x.day === ledgerDay);
        e.smt_root = e.smt_root.slice(0, -1) + (e.smt_root.endsWith('0') ? '1' : '0');
        return r.fulfill({ response: res, body: JSON.stringify(l) });
    });
    for (const origin of RPC) {
        const name = new URL(origin).host;
        await page.route(u => u.origin === origin, async (route) => {
            const req = route.request();
            const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST, OPTIONS' };
            if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
            const body = JSON.parse(req.postData() || '{}');
            calls.push(`${name} ${body.method}`);
            if (down.includes(name)) return down.includes('refuse') ? route.abort('connectionrefused') : route.fulfill({ status: 503, headers: cors, body: 'unavailable' });
            let answer;
            try {
                const o = override ? await override(body.method, body.params) : undefined;
                answer = o !== undefined ? { result: o } : { result: await chain.request(body.method, body.params) };
            } catch (e) { answer = { error: { code: -32000, message: e.message } }; }
            return route.fulfill({ status: 200, headers: { ...cors, 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: body.id, ...answer }) });
        });
    }
    await page.goto(`${BASE}/index.html#verify`);
    await page.waitForFunction(() => !document.querySelector('.boot'));
    return { ctx, page, calls };
}
async function check(page) {
    await page.click('[data-action="anchor-check"]');
    await page.waitForFunction(() => document.querySelector('#anchor-checks .receipt-label'), null, { timeout: 90000 });
    return page.evaluate(() => ({
        verdict: document.querySelector('#anchor-checks .receipt-label').innerText.trim(),
        rows: [...document.querySelectorAll('#anchor-checks .check-row')].map(r => ({ st: r.className.split('--')[1], label: r.querySelector('strong').textContent, detail: r.querySelector('.detail').textContent }))
    }));
}
const allPass = (r) => r.rows.length === 6 && r.rows.every(x => x.st === 'pass') && /ANCHOR CONFIRMED/.test(r.verdict);

// the honest path, both themes and a phone
for (const theme of ['dark', 'light']) {
    const { ctx, page, calls } = await site({ theme });
    ok(`${theme}: no request to any node before the button is pressed`, calls.length === 0);
    const t0 = Date.now(), r = await check(page);
    report[`honest_${theme}`] = { ...r, requests: calls.length, seconds: (Date.now() - t0) / 1000 };
    ok(`${theme}: all 6 checks pass against the deployment`, allPass(r), r.verdict);
    ok(`${theme}: 12 read-only requests, all to the primary node`, calls.length === 12 && calls.every(c => c.startsWith('ethereum-sepolia-rpc.publicnode.com ')), calls.join(', '));
    const lc = await lowContrast(page);
    ok(`${theme}: no text below WCAG contrast on the Verify page after the check`, lc.length === 0, JSON.stringify(lc.slice(0, 3)));
    await page.addStyleTag({ content: STATIC_HEADER });
    await page.locator('#anchor').screenshot({ path: `${OUT}/anchor-verify-${theme}.png` });
    if (theme === 'dark') {
        ok('footer names the anchor and the one outside request', /Sepolia testnet/.test(await page.textContent('.footer')) && /only outside request/.test(await page.textContent('.footer')));
        const go = async (name, ready) => { await page.evaluate((n) => { location.hash = n; }, name); await page.waitForFunction(ready, null, { timeout: 15000 }); };
        await go('provenance', () => [...document.querySelectorAll('.table tr')].some(t => /Public blockchain anchor/.test(t.innerText)));
        ok('provenance row says testnet, not mainnet', await page.evaluate(() => [...document.querySelectorAll('.table tr')].some(t => /Public blockchain anchor/.test(t.innerText) && /Deployed on a testnet/.test(t.innerText) && /Not on mainnet/.test(t.innerText))));
        await go('home', () => !!document.querySelector('.hero-notes'));
        ok('home notice and hero mention the testnet anchor', /anchored on the Sepolia testnet, which you can check/.test(await page.textContent('body')) && /checkable on Sepolia/.test(await page.textContent('.hero-notes')));
        await go('lender', () => !!document.querySelector('[data-action="goto-anchor"]'));
        await page.click('[data-action="goto-anchor"]');
        await page.waitForFunction(() => location.hash === '#verify' && document.getElementById('anchor') && Math.abs(document.getElementById('anchor').getBoundingClientRect().top) < 160, null, { timeout: 8000 }).catch(() => { });
        ok('lender page link lands on the anchor section', await page.evaluate(() => location.hash === '#verify' && Math.abs(document.getElementById('anchor').getBoundingClientRect().top) < 160));
    }
    await ctx.close();
}
{
    const { ctx, page } = await site({ phone: true });
    const r = await check(page);
    ok('phone: all pass and no horizontal scroll', allPass(r) && await page.evaluate(() => document.documentElement.scrollWidth <= 390), String(await page.evaluate(() => document.documentElement.scrollWidth)));
    await page.addStyleTag({ content: STATIC_HEADER });
    await page.locator('#anchor').screenshot({ path: `${OUT}/anchor-verify-phone.png` });
    await ctx.close();
}
// resilience and tampering
async function scenario(name, opts, expect) {
    const { ctx, page, calls } = await site(opts);
    const r = await check(page);
    report[name] = { ...r, requests: calls };
    const good = expect(r, calls);
    ok(name, good, r.verdict + ' | ' + (r.rows[r.rows.length - 1]?.detail || ''));
    await ctx.close();
}
const word = (h) => h.padEnd(64, '0');
const flip = (hexs, at) => hexs.slice(0, at) + (hexs[at] === '0' ? '1' : '0') + hexs.slice(at + 1);
await scenario('primary node down: falls back to the second node', { down: ['ethereum-sepolia-rpc.publicnode.com'] },
    (r, c) => allPass(r) && c.some(x => x.startsWith('sepolia.drpc.org ')) && /sepolia\.drpc\.org/.test(r.verdict));
await scenario('both nodes down: not verified, nothing marked passed', { down: ['ethereum-sepolia-rpc.publicnode.com', 'sepolia.drpc.org', 'refuse'] },
    (r) => /NOT VERIFIED/.test(r.verdict) && r.rows.length === 1 && r.rows[0].st === 'unsupported');
await scenario('a node on another chain fails at check 1', { override: (m) => m === 'eth_chainId' ? '0x1' : undefined },
    (r) => /DOES NOT MATCH/.test(r.verdict) && r.rows.length === 1 && r.rows[0].st === 'fail');
await scenario('one changed byte of contract code fails check 2', {
    override: async (m, p) => m === 'eth_getCode' ? flip(await chain.request(m, p), 2 + 2 * 100) : undefined
}, (r) => r.rows.length === 2 && r.rows[1].st === 'fail' && /differs from DiyarAnchor\.sol/.test(r.rows[1].detail));
await scenario('a record naming another operator fails check 2', { rec: { ...record, operator: '0x' + '1'.repeat(40) } },
    (r) => r.rows.length === 2 && r.rows[1].st === 'fail' && /names operator/.test(r.rows[1].detail));
await scenario('a failed anchor transaction fails check 3', {
    override: async (m, p) => m === 'eth_getTransactionReceipt' && String(p[0]).toLowerCase() === anchorTx ? { ...(await chain.request(m, p)), status: '0x0' } : undefined
}, (r) => r.rows.length === 3 && r.rows[2].st === 'fail');
await scenario('one altered root in the events fails check 4 and names the day', {
    override: async (m, p) => {
        if (m !== 'eth_getTransactionReceipt' || String(p[0]).toLowerCase() !== anchorTx) return undefined;
        const rc = structuredClone(await chain.request(m, p));
        rc.logs[20].data = flip(rc.logs[20].data, 2 + 64 + 10);
        return rc;
    }
}, (r) => r.rows.length === 4 && r.rows[3].st === 'fail' && /2017-01-20: the anchored root [0-9a-f]{64} differs/.test(r.rows[3].detail));
await scenario('a different head in contract state fails check 5', {
    override: (m, p) => m === 'eth_call' && p[0].data === IN.selectors.head ? '0x' + 'ab'.repeat(32) : undefined
}, (r) => r.rows.length === 5 && r.rows[4].st === 'fail');
const rootOf0205 = IN.selectors.rootOf + word(Buffer.from('2017-02-05').toString('hex'));
await scenario('a different stored root for 5 Feb fails check 6', {
    override: (m, p) => m === 'eth_call' && p[0].data === rootOf0205 ? '0x' + 'cd'.repeat(32) : undefined
}, (r) => r.rows.length === 6 && r.rows[5].st === 'fail' && /2017-02-05/.test(r.rows[5].detail));

// pending and malformed records show the not-deployed state and never contact a node
for (const [name, rec] of [['pending record', { status: 'pending', network: 'sepolia', chainId: 11155111 }], ['malformed record', { ...record, contract: 'not-an-address' }]]) {
    const { ctx, page, calls } = await site({ rec });
    const txt = await page.textContent('#anchor');
    ok(`${name}: shows not deployed, offers the local run, no Sepolia check`, /not deployed/.test(txt) && !!(await page.$('[data-action="anchor-local"]')) && !(await page.$('[data-action="anchor-check"]')) && calls.length === 0
        && /No deployed anchor/.test(await page.textContent('.footer')) && /no analytics, cookies or third-party requests/i.test(await page.textContent('.footer')));
    if (name === 'pending record') { await page.addStyleTag({ content: STATIC_HEADER }); await page.locator('#anchor').screenshot({ path: `${OUT}/anchor-verify-pending.png` }); }
    await ctx.close();
}
/* ---------------------------------------------------------------- 3. local EVM in the page --- */
async function local(page) {
    await page.click('[data-action="anchor-local"]');
    await page.waitForFunction(() => document.querySelector('#anchor-local .receipt-label'), null, { timeout: 90000 });
    return page.evaluate(() => ({
        verdict: document.querySelector('#anchor-local .receipt-label').innerText.trim(),
        rows: [...document.querySelectorAll('#anchor-local .check-row')].map(r => ({ st: r.className.split('--')[1], label: r.querySelector('strong').textContent, detail: r.querySelector('.detail').textContent, time: r.querySelector('.time')?.textContent || '' }))
    }));
}
const pending = { status: 'pending', network: 'sepolia', chainId: 11155111 };
for (const theme of ['dark', 'light']) {
    const { ctx, page, calls } = await site({ rec: pending, theme });
    const t0 = Date.now(), r = await local(page);
    report[`local_${theme}`] = { ...r, seconds: (Date.now() - t0) / 1000 };
    const txt = r.rows.map(x => x.detail + ' ' + x.time).join(' ');
    ok(`${theme}: local EVM run, 8 of 8 steps pass`, r.rows.length === 8 && r.rows.every(x => x.st === 'pass') && /CONTRACT RULES HOLD/.test(r.verdict), r.verdict);
    ok(`${theme}: local gas equals the contract test log (427,275 and 2,586,922)`, /427,275 gas/.test(txt) && /2,586,922 gas/.test(txt));
    ok(`${theme}: the three forbidden writes revert with their own errors`, /WrongPrevious\(/.test(txt) && /DayNotIncreasing\(last "2017-03-31", given "2017-01-20"\)/.test(txt) && /NotOperator\(\)/.test(txt));
    ok(`${theme}: the local run sends nothing to any node`, calls.length === 0);
    const lc = await lowContrast(page);
    ok(`${theme}: no text below WCAG contrast after the local run`, lc.length === 0, JSON.stringify(lc.slice(0, 3)));
    await page.click('[data-action="anchor-local"]');
    await page.waitForFunction(() => document.querySelector('#anchor-local .receipt-label') && !document.querySelector('[data-action="anchor-local"]').disabled, null, { timeout: 90000 });
    ok(`${theme}: the run can be repeated`, (await page.$$eval('#anchor-local .check-row--pass', x => x.length)) === 8);
    await page.addStyleTag({ content: STATIC_HEADER });
    await page.locator('#anchor').screenshot({ path: `${OUT}/anchor-local-${theme}.png` });
    await ctx.close();
}
{
    const { ctx, page } = await site({ rec: pending, ledgerDay: '2017-01-20' });
    const r = await local(page);
    ok('local run on a ledger with one altered root stops at the state check', r.rows.length === 3 && r.rows[2].st === 'fail' && /CONTRACT CHECK FAILED/.test(r.verdict), r.verdict + ' | ' + (r.rows[2]?.detail || ''));
    await ctx.close();
}
{
    const { ctx, page } = await site({ rec: pending, phone: true });
    const r = await local(page);
    ok('phone: local run passes, no horizontal scroll', r.rows.length === 8 && r.rows.every(x => x.st === 'pass') && await page.evaluate(() => document.documentElement.scrollWidth <= 390));
    await page.addStyleTag({ content: STATIC_HEADER });
    await page.locator('#anchor').screenshot({ path: `${OUT}/anchor-local-phone.png` });
    await ctx.close();
}
{
    const { ctx, page } = await site({});
    const r = await local(page);
    ok('anchored record: the local run is offered too and passes', r.rows.length === 8 && r.rows.every(x => x.st === 'pass'));
    await ctx.close();
}
await browser.close();
const unexpected = errors.filter(e => !/status of 503|ERR_CONNECTION_REFUSED|Failed to load resource/.test(e));
ok('no page errors or console errors (other than the simulated outages)', unexpected.length === 0, unexpected.join(' | '));
fs.writeFileSync(`${OUT}/e2e.json`, JSON.stringify({ pass, fail, tests, record, report, errors }, null, 1));
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
