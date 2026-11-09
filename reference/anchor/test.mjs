// Tests for DiyarAnchor on an in-process EVM (Cancun), against the real V2 reference-run ledger.
// usage: node test.mjs LEDGER_JSON
import fs from 'fs';
import { VM } from '@ethereumjs/vm';
import { Common, Chain, Hardfork } from '@ethereumjs/common';
import { LegacyTransaction } from '@ethereumjs/tx';
import { Address, Account, hexToBytes, bytesToHex, privateToAddress, randomBytes } from '@ethereumjs/util';
import { keccak256 } from 'ethereum-cryptography/keccak.js';
import { createHash } from 'crypto';

const art = JSON.parse(fs.readFileSync(new URL('./DiyarAnchor.json', import.meta.url)));
const ledger = JSON.parse(fs.readFileSync(process.argv[2]));
const common = new Common({ chain: Chain.Mainnet, hardfork: Hardfork.Cancun });
const vm = await VM.create({ common });
const keys = [randomBytes(32), randomBytes(32)];                       // throwaway keys, in-memory EVM only
const addrs = keys.map(k => new Address(privateToAddress(k)));
for (const a of addrs) await vm.stateManager.putAccount(a, new Account(0n, 10n ** 21n));
const nonces = [0n, 0n];
const reader = new Address(privateToAddress(randomBytes(32)));      // view calls only

const hex = (b) => bytesToHex(b).slice(2);
const word = (h) => h.padEnd(64, '0');                                   // left-aligned bytesN
const day10 = (d) => word(Buffer.from(d, 'ascii').toString('hex'));
const sel = (sig) => hex(keccak256(Buffer.from(sig))).slice(0, 8);
const errSel = (sig) => sel(sig);
const encAnchor = (d, root, prev) => sel('anchor(bytes10,bytes32,bytes32)') + day10(d) + root + prev;
function encBatch(days, roots) {
    const n = days.length, u = (v) => v.toString(16).padStart(64, '0');
    const off1 = 64, off2 = 64 + 32 * (1 + n);
    return sel('anchorBatch(bytes10[],bytes32[])') + u(off1) + u(off2) + u(n) + days.map(day10).join('') + u(n) + roots.join('');
}
async function send(who, data, to) {
    const tx = LegacyTransaction.fromTxData({ nonce: nonces[who]++, gasPrice: 10n ** 9n, gasLimit: 6_000_000n, to, data: '0x' + data }, { common }).sign(keys[who]);
    const r = await vm.runTx({ tx, skipBlockGasLimitValidation: true });
    return { gas: Number(r.totalGasSpent ?? r.totalGasUsed), err: r.execResult.exceptionError, ret: hex(r.execResult.returnValue), created: r.createdAddress, logs: r.receipt.logs };
}
async function call(to, data) {
    const r = await vm.evm.runCall({ to, caller: reader, data: hexToBytes('0x' + data), gasLimit: 1_000_000n });
    return hex(r.execResult.returnValue);
}
let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => { cond ? pass++ : fail++; console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  · ' + extra : ''}`); };

// deploy
const dep = await send(0, art.bytecode.slice(2));
const C = dep.created;
ok('deploys', !dep.err && !!C, `${dep.gas} gas`);
ok('operator is the deployer', (await call(C, sel('operator()'))).endsWith(hex(addrs[0].bytes)));
ok('head starts at 32 zero bytes (the ledger genesis prev)', (await call(C, sel('head()'))) === '0'.repeat(64));
const code = Buffer.from(await vm.stateManager.getContractCode(C));
const opWord = art.immutableReferences.map(r => code.subarray(r.start, r.start + r.length).toString('hex'));
for (const r of art.immutableReferences) code.fill(0, r.start, r.start + r.length);
ok('deployed code, operator masked, equals the compiled fingerprint', createHash('sha256').update(code).digest('hex') === art.runtimeSha256Masked && opWord.every(w => w === hex(addrs[0].bytes).padStart(64, '0')), `${code.length} bytes, ${art.immutableReferences.length} immutable slot(s)`);

// entryHash = the DIYAR ledger rule, for every published day
let same = 0;
for (const e of ledger) if ((await call(C, sel('entryHash(bytes10,bytes32,bytes32)') + day10(e.day) + e.smt_root + e.prev)) === e.entry) same++;
ok('entryHash() reproduces every ledger entry', same === ledger.length, `${same}/${ledger.length}`);

// single anchors and the rules
const a0 = await send(0, encAnchor(ledger[0].day, ledger[0].smt_root, ledger[0].prev), C);
ok('first anchor (genesis prev)', !a0.err, `${a0.gas} gas (first write to empty slots)`);
const a1 = await send(0, encAnchor(ledger[1].day, ledger[1].smt_root, ledger[1].prev), C);
ok('second anchor cites the first', !a1.err && (await call(C, sel('head()'))) === ledger[1].entry, `${a1.gas} gas (a typical day)`);
const fork = await send(0, encAnchor(ledger[2].day, ledger[2].smt_root, ledger[0].entry), C);
ok('a fork (stale prev) reverts with WrongPrevious', !!fork.err && fork.ret.startsWith(errSel('WrongPrevious(bytes32,bytes32)')));
const back = await send(0, encAnchor(ledger[0].day, ledger[2].smt_root, ledger[1].entry), C);
ok('a non-increasing day reverts with DayNotIncreasing', !!back.err && back.ret.startsWith(errSel('DayNotIncreasing(bytes10,bytes10)')));
const intruder = await send(1, encAnchor(ledger[2].day, ledger[2].smt_root, ledger[1].entry), C);
ok('another account cannot write (NotOperator)', !!intruder.err && intruder.ret.startsWith(errSel('NotOperator()')));
ok('head unchanged after the three rejected writes', (await call(C, sel('head()'))) === ledger[1].entry);
const ev = a1.logs[0];
const topic = hex(keccak256(Buffer.from('Anchored(uint64,bytes10,bytes32,bytes32,bytes32)')));
ok('Anchored event carries index, day, root, prev, entry', !!ev && hex(ev[1][0]) === topic && hex(ev[1][1]) === '1'.padStart(64, '0') && hex(ev[2]) === day10(ledger[1].day) + ledger[1].smt_root + ledger[1].prev + ledger[1].entry);
ok('rootOf(day) is in state after a single anchor', (await call(C, sel('rootOf(bytes10)') + day10(ledger[1].day))) === ledger[1].smt_root);

// a fresh contract, all 91 days in one transaction
const dep2 = await send(0, art.bytecode.slice(2));
const C2 = dep2.created;
const batch = await send(0, encBatch(ledger.map(e => e.day), ledger.map(e => e.smt_root)), C2);
const head2 = await call(C2, sel('head()')), count2 = parseInt(await call(C2, sel('count()')), 16);
ok('anchorBatch(91 days) ends on the last ledger entry', !batch.err && head2 === ledger[ledger.length - 1].entry && count2 === ledger.length, `${batch.gas} gas for ${ledger.length} days`);
const bad = await send(0, encBatch([ledger[5].day], [ledger[5].smt_root]), C2);
ok('replaying an old day after the batch reverts', !!bad.err);
let roots = 0;
for (const e of ledger) if ((await call(C2, sel('rootOf(bytes10)') + day10(e.day))) === e.smt_root) roots++;
ok('rootOf(day) returns every anchored root from state', roots === ledger.length, `${roots}/${ledger.length}`);
ok('rootOf(a day never anchored) is zero', (await call(C2, sel('rootOf(bytes10)') + day10('2017-04-01'))) === '0'.repeat(64));

const out = { compiler: art.compiler, source_sha256: art.sourceSha256, runtime_sha256_masked: art.runtimeSha256Masked, anchored_topic: topic, deploy_gas: dep.gas, first_anchor_gas: a0.gas, typical_anchor_gas: a1.gas, batch_91_gas: batch.gas,
    batch_per_day_gas: Math.round(batch.gas / ledger.length), last_entry: ledger[ledger.length - 1].entry, tests: { pass, fail } };
fs.writeFileSync(new URL('./gas.json', import.meta.url), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out));
process.exit(fail ? 1 : 0);
