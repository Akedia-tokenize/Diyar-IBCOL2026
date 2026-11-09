/* The anchor contract on a local EVM, in this browser (run by anchor-evm-worker.js; also importable in Node for tests).
   It deploys the published init code (anchor/DiyarAnchor.json), anchors the 91 days of data/ledger.json in one call,
   reads the state back, then tries three forbidden writes that must revert. Nothing leaves the page: there is no
   network, no wallet and no key; the two accounts are plain local addresses. Gas is the transaction gas a node would
   charge under the Cancun rules: intrinsic cost (21,000, calldata, contract creation, init-code words) plus execution. */
import { EVM, DefaultStateManager, Common, Chain, Hardfork, Address, Account, hexToBytes, bytesToHex, keccak256 } from './vendor/ethereumjs-evm.js';
import { sha256, hex, unhex, concat, bytes } from './crypto.js';

const NO_BN254 = new Proxy({}, { get() { return () => { throw new Error('BN254 precompiles are not available in this page'); }; } });
const BLOCKS = { async getBlock() { return { hash: () => new Uint8Array(32) }; }, shallowCopy() { return this; } };
const OPERATOR = new Address(hexToBytes('0x' + 'd1a0'.repeat(10)));      // local demo accounts, not real addresses
const OUTSIDER = new Address(hexToBytes('0x' + '0b5e'.repeat(10)));
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const strip = (h) => String(h).toLowerCase().replace(/^0x/, '');
const short = (h) => { const s = strip(h); return s.length > 20 ? s.slice(0, 8) + '…' + s.slice(-6) : s; };
const int = (n) => Number(n).toLocaleString('en-US');
const word = (h) => strip(h).padEnd(64, '0');
const day10 = (d) => word(hex(bytes(d)));
const u256 = (n) => n.toString(16).padStart(64, '0');
const sel = (sig) => hex(keccak256(bytes(sig))).slice(0, 8);
const ascii10 = (b) => new TextDecoder().decode(b.slice(0, 10));
const dayLabel = (d) => { const [y, m, dd] = d.split('-'); return `${+dd} ${MONTHS[+m - 1]} ${y}`; };
const flipLast = (h) => h.slice(0, -1) + (h.endsWith('0') ? '1' : '0');

/** Transaction gas = intrinsic (EIP-2028 calldata, EIP-2 creation, EIP-3860 init-code words) + execution, no refunds here. */
function txGas(data, create, executionGasUsed) {
    let g = 21000n;
    for (const b of data) g += b === 0 ? 4n : 16n;
    if (create) g += 32000n + 2n * BigInt(Math.ceil(data.length / 32));
    return g + executionGasUsed;
}

export async function runLocal({ ledger, artifact, expect, onStep }) {
    const common = new Common({ chain: Chain.Mainnet, hardfork: Hardfork.Cancun });
    const evm = new EVM({ common, stateManager: new DefaultStateManager(), blockchain: BLOCKS }, NO_BN254);
    for (const a of [OPERATOR, OUTSIDER]) await evm.stateManager.putAccount(a, new Account(0n, 10n ** 21n));
    const m = artifact.methods, n = ledger.length, last = ledger[n - 1];
    const ERR = { [sel('WrongPrevious(bytes32,bytes32)')]: 'WrongPrevious', [sel('DayNotIncreasing(bytes10,bytes10)')]: 'DayNotIncreasing', [sel('NotOperator()')]: 'NotOperator', [sel('LengthMismatch()')]: 'LengthMismatch' };
    let C = null;

    // One transaction, as a node runs it: a clean journal, then the sender, the recipient and the precompiles warm (EIP-2929).
    async function send(caller, dataHex, to) {
        const data = hexToBytes('0x' + dataHex);
        await evm.journal.cleanup();
        for (const [a] of evm.precompiles.entries()) evm.journal.addAlwaysWarmAddress(a);
        evm.journal.addAlwaysWarmAddress(caller.toString());
        if (to) evm.journal.addAlwaysWarmAddress(to.toString());
        const r = await evm.runCall({ caller, to, data, gasLimit: 16_000_000n, value: 0n });
        await evm.journal.cleanup();
        const ret = r.execResult.returnValue;
        const err = r.execResult.exceptionError;
        return { ok: !err, gas: txGas(data, !to, r.execResult.executionGasUsed), created: r.createdAddress, logs: r.execResult.logs || [],
            error: err ? (ERR[hex(ret.slice(0, 4))] || err.error || 'reverted') : null, ret };
    }
    async function view(dataHex) {
        await evm.journal.cleanup();
        const r = await evm.runCall({ caller: OUTSIDER, to: C, data: hexToBytes('0x' + dataHex), gasLimit: 1_000_000n });
        await evm.journal.cleanup();
        if (r.execResult.exceptionError) throw new Error('view call reverted');
        return hex(r.execResult.returnValue);
    }
    const head = async () => view(m['head()']);
    const count = async () => parseInt(await view(m['count()']), 16);
    const rootOf = async (d) => view(m['rootOf(bytes10)'] + day10(d));
    const anchorOne = (d, root, prev) => m['anchor(bytes10,bytes32,bytes32)'] + day10(d) + strip(root) + strip(prev);
    const steps = [];
    async function step(id, label, fn) {
        const t = (globalThis.performance || Date).now();
        let r;
        try { r = await fn(); } catch (e) { r = { status: 'fail', detail: e && e.message ? e.message : String(e) }; }
        const s = { id, label, ms: Math.round((globalThis.performance || Date).now() - t), count: '', ...r };
        steps.push(s);
        onStep?.(s);
        return s.status === 'pass';
    }
    const pass = (detail, count = '') => ({ status: 'pass', detail, count });
    const fail = (detail, count = '') => ({ status: 'fail', detail, count });

    const ok = await step('deploy', 'Deploy the published contract', async () => {
        const init = strip(artifact.bytecode);
        const r = await send(OPERATOR, init);
        if (!r.ok || !r.created) return fail(`Deployment reverted (${r.error}).`);
        C = r.created;
        const code = await evm.stateManager.getContractCode(C);
        const words = artifact.immutableReferences.map(({ start, length }) => hex(code.slice(start, start + length)));
        const masked = code.slice();
        for (const { start, length } of artifact.immutableReferences) masked.fill(0, start, start + length);
        const sum = hex(sha256(masked));
        if (code.length !== expect.runtimeBytes || sum !== expect.runtimeSha256Masked) return fail(`The deployed code (${int(code.length)} bytes, SHA-256 ${short(sum)} with the operator masked) is not the fingerprint the Sepolia check expects (${short(expect.runtimeSha256Masked)}).`);
        if (!words.every(w => w === hex(OPERATOR.bytes).padStart(64, '0'))) return fail('The operator address inside the deployed code is not the deploying account.');
        return pass(`The init code from anchor/DiyarAnchor.json (${int(init.length / 2)} bytes) leaves ${int(code.length)} bytes of runtime code. With the operator masked, its SHA-256 is ${short(sum)}: the same fingerprint the Sepolia check expects.`, `${int(r.gas)} gas`);
    });
    if (!ok) return steps;

    let batchLogs = [];
    if (!await step('batch', `Anchor all ${n} days in one transaction`, async () => {
        const data = m['anchorBatch(bytes10[],bytes32[])'] + u256(64n) + u256(BigInt(64 + 32 * (1 + n))) + u256(BigInt(n)) + ledger.map(e => day10(e.day)).join('') + u256(BigInt(n)) + ledger.map(e => strip(e.smt_root)).join('');
        const r = await send(OPERATOR, data, C);
        if (!r.ok) return fail(`The batch reverted (${r.error}).`);
        batchLogs = r.logs;
        return pass(`Days ${dayLabel(ledger[0].day)} to ${dayLabel(last.day)} and their signed roots, taken from data/ledger.json. The contract recomputed every entry as SHA-256(0x20 || day || root || prev) and stored every root: about ${int(Math.round(Number(r.gas) / n))} gas per day.`, `${int(r.gas)} gas`);
    })) return steps;

    if (!await step('state', 'Contract state equals the ledger', async () => {
        const h = await head(), c = await count();
        if (h !== last.entry || c !== n) return fail(`head() = ${short(h)}, count() = ${c}; the ledger ends on ${short(last.entry)} after ${n} days.`);
        if (batchLogs.length !== n) return fail(`${batchLogs.length} Anchored events; the ledger has ${n} days.`);
        for (let i = 0; i < n; i++) {
            const d = batchLogs[i][2], e = ledger[i];
            if (ascii10(d) !== e.day || hex(d.slice(32, 64)) !== e.smt_root || hex(d.slice(64, 96)) !== e.prev || hex(d.slice(96, 128)) !== e.entry) return fail(`${e.day}: the Anchored event differs from the ledger.`);
        }
        return pass(`head() = ${short(h)}, the ledger’s last entry (${dayLabel(last.day)}); count() = ${c}; all ${n} Anchored events equal the ledger day by day.`, `${n}/${n} days`);
    })) return steps;

    if (!await step('lookup', 'Roots read back from contract state', async () => {
        const feb5 = ledger.find(e => e.day === '2017-02-05');
        const got = await rootOf('2017-02-05'), none = await rootOf('2017-04-01');
        if (!feb5 || got !== feb5.smt_root) return fail(`rootOf("2017-02-05") = ${short(got)}, but the ledger root for that day is ${feb5 ? short(feb5.smt_root) : 'missing'}.`);
        if (!/^0+$/.test(none)) return fail('rootOf("2017-04-01") is not empty, although that day was never anchored.');
        return pass(`rootOf("2017-02-05") = ${short(got)}, the root the lender page proofs end on. rootOf("2017-04-01") is empty: that day was never anchored.`, '2 days');
    })) return steps;

    const before = { h: await head(), c: await count() };
    const fake = flipLast(ledger.find(e => e.day === '2017-01-20').smt_root);
    if (!await step('fork', 'A fork is rejected', async () => {
        const stale = ledger[n - 2];
        const r = await send(OPERATOR, anchorOne('2017-04-01', fake, stale.entry), C);
        if (r.ok) return fail('A new day citing an old entry was accepted: the chain could be forked.');
        if (r.error !== 'WrongPrevious') return fail(`Reverted for another reason (${r.error}).`);
        return pass(`The operator tried to add 1 April citing the ${dayLabel(stale.day)} entry instead of the head. Reverted with WrongPrevious(expected ${short(hex(r.ret.slice(4, 36)))}, given ${short(hex(r.ret.slice(36, 68)))}).`);
    })) return steps;

    if (!await step('rewrite', 'Rewriting an anchored day is rejected', async () => {
        const r = await send(OPERATOR, anchorOne('2017-01-20', fake, before.h), C);
        if (r.ok) return fail('A second root for 20 January was accepted: an anchored day could be rewritten.');
        if (r.error !== 'DayNotIncreasing') return fail(`Reverted for another reason (${r.error}).`);
        return pass(`The operator tried to give 20 January a different root, citing the current head. Reverted with DayNotIncreasing(last "${ascii10(r.ret.slice(4, 36))}", given "${ascii10(r.ret.slice(36, 68))}").`);
    })) return steps;

    if (!await step('outsider', 'Another account cannot write', async () => {
        const r = await send(OUTSIDER, anchorOne('2017-04-01', fake, before.h), C);
        if (r.ok) return fail('An account other than the operator could write.');
        if (r.error !== 'NotOperator') return fail(`Reverted for another reason (${r.error}).`);
        return pass('A second account tried to add 1 April with the correct head. Reverted with NotOperator().');
    })) return steps;

    await step('unchanged', 'Nothing changed after the three attempts', async () => {
        const h = await head(), c = await count(), r20 = await rootOf('2017-01-20');
        const jan20 = ledger.find(e => e.day === '2017-01-20');
        if (h !== before.h || c !== before.c || r20 !== jan20.smt_root) return fail('The contract state changed after a rejected write.');
        return pass(`head() is still ${short(h)}, count() is still ${c}, and rootOf("2017-01-20") is still the signed root ${short(r20)}.`);
    });
    return steps;
}
