// Compile DiyarAnchor.sol with the pinned solc (npm solc 0.8.26) and write DiyarAnchor.json.
const solc = require('solc'); const fs = require('fs'); const crypto = require('crypto');
const src = fs.readFileSync('DiyarAnchor.sol', 'utf8');
const input = { language: 'Solidity', sources: { 'DiyarAnchor.sol': { content: src } },
  settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: 'cancun',
    outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object', 'evm.deployedBytecode.object', 'evm.deployedBytecode.immutableReferences', 'evm.methodIdentifiers'] } } } };
const out = JSON.parse(solc.compile(JSON.stringify(input)));
let bad = 0;
for (const e of out.errors || []) { console.log(e.severity, e.formattedMessage); if (e.severity === 'error') bad++; }
if (bad) process.exit(1);
const c = out.contracts['DiyarAnchor.sol'].DiyarAnchor;
// Runtime code with every immutable (the operator address) zeroed: what any deployment of this source must equal.
const immutables = Object.values(c.evm.deployedBytecode.immutableReferences || {}).flat();
const runtime = Buffer.from(c.evm.deployedBytecode.object, 'hex');
for (const { start, length } of immutables) runtime.fill(0, start, start + length);
const sha = (b) => crypto.createHash('sha256').update(b).digest('hex');
const art = { compiler: solc.version(), optimizer: input.settings.optimizer, evmVersion: input.settings.evmVersion,
  sourceSha256: sha(Buffer.from(src, 'utf8')), abi: c.abi, bytecode: '0x' + c.evm.bytecode.object,
  deployedBytecode: '0x' + c.evm.deployedBytecode.object, immutableReferences: immutables,
  runtimeSha256Masked: sha(runtime), methods: c.evm.methodIdentifiers };
fs.writeFileSync('DiyarAnchor.json', JSON.stringify(art, null, 1));
console.log('compiled', art.compiler, '· init code', c.evm.bytecode.object.length / 2, 'bytes · runtime', runtime.length, 'bytes · immutables', JSON.stringify(immutables));
console.log('source sha256', art.sourceSha256, '· masked runtime sha256', art.runtimeSha256Masked);
console.log('methods', JSON.stringify(art.methods));
