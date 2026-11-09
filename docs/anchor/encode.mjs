// Precompute the exact calldata for anchorBatch(91 days) — same encoder as test.mjs.
import fs from 'fs';
import { keccak256 } from 'ethereum-cryptography/keccak.js';
const ledger = JSON.parse(fs.readFileSync(process.argv[2]));
const hex = (b) => Buffer.from(b).toString('hex');
const sel = (sig) => hex(keccak256(Buffer.from(sig))).slice(0, 8);
const word = (h) => h.padEnd(64, '0'), day10 = (d) => word(Buffer.from(d, 'ascii').toString('hex'));
const u = (v) => v.toString(16).padStart(64, '0');
const n = ledger.length;
const data = '0x' + sel('anchorBatch(bytes10[],bytes32[])') + u(64) + u(64 + 32 * (1 + n)) + u(n) + ledger.map(e => day10(e.day)).join('') + u(n) + ledger.map(e => e.smt_root).join('');
const art = JSON.parse(fs.readFileSync('DiyarAnchor.json'));
const out = { bytecode: art.bytecode, batchData: data, expectedHead: '0x' + ledger[n - 1].entry, days: n, firstDay: ledger[0].day, lastDay: ledger[n - 1].day,
  selectors: { head: '0x' + sel('head()'), count: '0x' + sel('count()'), operator: '0x' + sel('operator()'), rootOf: '0x' + sel('rootOf(bytes10)') },
  topic: '0x' + hex(keccak256(Buffer.from('Anchored(uint64,bytes10,bytes32,bytes32,bytes32)'))),
  compiler: art.compiler, sourceSha256: art.sourceSha256, runtimeSha256Masked: art.runtimeSha256Masked, immutableReferences: art.immutableReferences,
  runtimeBytes: (art.deployedBytecode.length - 2) / 2,
  remix: { dayList: ledger.map(e => '0x' + Buffer.from(e.day, 'ascii').toString('hex')), roots: ledger.map(e => '0x' + e.smt_root) } };
fs.writeFileSync('deploy-inputs.json', JSON.stringify(out));
fs.writeFileSync('remix-arguments.txt', `anchorBatch arguments for Remix (paste each line into its field)\n\ndayList:\n${JSON.stringify(out.remix.dayList)}\n\nroots:\n${JSON.stringify(out.remix.roots)}\n\nExpected head() after the call: ${out.expectedHead}\nExpected count(): ${n}\n`);
console.log('batch calldata bytes', (data.length - 2) / 2, 'expected head', out.expectedHead, out.selectors);
