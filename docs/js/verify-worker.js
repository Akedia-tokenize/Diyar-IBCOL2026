/* DIYAR in-browser verifier (fixed build).

   Same message protocol and check ids as UI v2. What changed:
   - SLH-DSA-SHA2-256s daily signatures are verified (vendored @noble/post-quantum 0.5.2, MIT).
   - Every signed message is rebuilt from the committed record itself (lossless canonical JSON),
     so a signature is tied to the bytes that went into the Merkle root. The precomputed
     signature_inputs.json file is no longer needed.
   - "Record canonical hashes" now checks something: each line must re-encode to its own bytes.
   - V2 archives: installer certificates are verified against the pinned installer key, and each
     meter record must point to the certificate whose key signed its readings.
   Nothing is reported as passed unless it was computed here from the published bytes. */
import { hex, unhex, bytes, concat, verifyEcdsa, verifyProof, recordHashCanonicalLine, outputHashCanonicalLine, SparseTree, entryDigest } from './crypto.js';
import { parseLossless, canon, isCanonicalLine, plain } from './canon.js';
import { slh_dsa_sha2_256s } from './vendor/noble-slh-dsa.js';

const CACHE = new Map();
const BASE = '../data/';
async function source(name, kind = 'json', optional = false) {
    const id = kind + name;
    if (!CACHE.has(id))
        CACHE.set(id, fetch(BASE + name).then(async (r) => {
            if (!r.ok) { if (optional) return null; throw new Error('Missing evidence file ' + name); }
            return kind === 'json' ? r.json() : r.text();
        }));
    return CACHE.get(id);
}
const put = (data) => postMessage(data);
const now = () => performance.now();
const checked = (id, label, start, ok, detail, count) => ({ id, label, status: ok ? 'pass' : 'fail', detail, count, ms: Math.round(now() - start) });
const unsupported = (id, label, detail) => ({ id, label, status: 'unsupported', detail, ms: 0 });
const emit = (result) => put({ type: 'check', result });
const progress = (id, done, total) => put({ type: 'progress', id, done, total });

const FEED_V2_DOMAIN = bytes('DIYAR/AUTH-FEED/V2\u0000');
const BIND_DOMAIN = bytes('DIYAR/METER-BIND/V2\u0000');
const q = (s) => JSON.stringify(s);

/* ---- evidence model: every record kept as exact line + lossless tree ------------------- */
let MODEL = null;
async function model() {
    if (MODEL) return MODEL;
    const [ledger, keys, text] = await Promise.all([source('ledger.json'), source('public_keys.json'), source('records.jsonl', 'text')]);
    const issuerPins = await source('issuer_pins_DEMO_NOT_TRUSTED.json', 'json', true);
    const installerPins = await source('installer_pins_DEMO_NOT_TRUSTED.json', 'json', true);
    const rows = text.trimEnd().split('\n').map(line => ({ line, t: parseLossless(line) }));
    for (const r of rows) r.r = plain(r.t);
    const certs = new Map(rows.filter(x => x.r.field.startsWith('certificates/')).map(x => [x.r.value.certificate_id, x]));
    MODEL = { ledger, keys, rows, certs, issuerPins, installerPins, v2: certs.size > 0 };
    return MODEL;
}

/* The exact bytes each signer signed, rebuilt from the committed record. */
function readingMessages(row) {
    const device = row.r.evidence.device_id;
    return row.t.value.map((x, i) => ({
        hour: x.h, sig: x.sig,
        msg: bytes(`{"d":${q(device)},"f":${q(row.r.field)},"h":${q(x.h)},"v":${canon(row.t.value[i].v)}}`),
    }));
}
function feedMessage(row, v2) {
    if (!v2) return bytes(`{"f":${q(row.r.field)},"v":${canon(row.t.value)}}`);
    const r = row.r, e = r.evidence;
    const claim = `{"audience":"DIYAR/provenance","claim_schema":${q(r.schema_ver)},"field_id":${q(r.field)},` +
        `"issuer_id":${q(e.issuer)},"issuer_key_id":${q(e.issuer_key_id)},"sig_format":"AUTH-FEED-V2","unit":${canon(row.t.unit)},` +
        `"valid_from":${canon(row.t.valid_from)},"valid_to":${canon(row.t.valid_to)},"value":${canon(row.t.value)}}`;
    return concat(FEED_V2_DOMAIN, bytes(claim));
}
function feedKey(m, row) {
    const e = row.r.evidence;
    if (!m.v2) return m.keys.issuers[e.issuer];
    return m.issuerPins?.[e.issuer]?.[e.issuer_key_id];
}
/* V2: the device key that must have signed a meter record, taken from its signed certificate. */
function deviceKey(m, row) {
    if (!m.v2) return m.keys.devices[row.r.evidence.device_id];
    const cert = m.certs.get(row.r.evidence.binding_cert_id);
    if (!cert) return null;
    const v = cert.r.value;
    if (v.device_id !== row.r.evidence.device_id || !row.r.field.startsWith(v.building_id + '/')) return null;
    return v.public_key;
}
async function verifyCertificate(m, cert) {
    const v = cert.r.value, e = cert.r.evidence;
    const pk = m.installerPins?.[v.installer_id]?.[v.installer_key_id];
    if (!pk || e.installer_id !== v.installer_id || e.installer_key_id !== v.installer_key_id || cert.r.grade !== 'B') return false;
    return verifyEcdsa(pk, concat(BIND_DOMAIN, bytes(canon(cert.t.value))), e.signature);
}
const slhVerify = (pkHex, msg, sigHex) => { try { return slh_dsa_sha2_256s.verify(unhex(sigHex), msg, unhex(pkHex)); } catch { return false; } };

async function runAll(deep) {
    const m = await model();
    const { ledger, keys, rows } = m;
    let start = now(), good = 0, prev = '00'.repeat(32);
    for (const e of ledger) {
        if (e.prev !== prev || entryDigest(e, prev) !== e.entry) break;
        prev = e.entry; good++;
    }
    emit(checked('chain', 'Daily chain commitments', start, good === ledger.length, `Recomputed SHA-256 over domain 0x20, day, SMT root and previous entry. ${good} of ${ledger.length} links match.`, `${good}/${ledger.length}`));

    start = now(); good = 0;
    for (let i = 0; i < ledger.length; i++) {
        if (await verifyEcdsa(keys.operator_ecdsa, unhex(ledger[i].entry), ledger[i].ecdsa)) good++;
        if (i % 10 === 0) progress('ecdsa', i + 1, ledger.length);
    }
    emit(checked('ecdsa', 'ECDSA P-256 daily signatures', start, good === ledger.length, 'WebCrypto checks each raw r || s signature over the daily entry against the published operator key (simulated identity).', `${good}/${ledger.length}`));

    start = now(); good = 0;
    for (let i = 0; i < ledger.length; i++) {
        if (slhVerify(keys.operator_slh, unhex(ledger[i].entry), ledger[i].slh_dsa)) good++;
        if (i % 5 === 0) progress('slh', i + 1, ledger.length);
    }
    emit(checked('slh', 'SLH-DSA-SHA2-256s daily signatures', start, good === ledger.length, `Post-quantum FIPS 205 signature (29,792 bytes) over each daily entry, verified in this browser with @noble/post-quantum 0.5.2. ${good} of ${ledger.length} verify.`, `${good}/${ledger.length}`));

    start = now();
    const canonical = rows.filter(x => isCanonicalLine(x.line)).length;
    const withHash = rows.map(x => ({ ...x, h: recordHashCanonicalLine(x.line) }));
    emit(checked('records', 'Record canonical hashes', start, canonical === rows.length, `Each of the ${rows.length} record versions re-encodes to exactly its published bytes (sorted keys, no whitespace, Python number form); SHA-256(0x10 || bytes) of each line feeds the root rebuild below.`, `${canonical}/${rows.length}`));

    start = now();
    const perday = new Map();
    for (const row of withHash) {
        const day = row.r.tx_time.slice(0, 10);
        if (!perday.has(day)) perday.set(day, []);
        perday.get(day).push(row);
    }
    const tree = new SparseTree();
    let roots = 0;
    for (let i = 0; i < ledger.length; i++) {
        for (const row of (perday.get(ledger[i].day) || []).sort((a, b) => a.r.tx_time < b.r.tx_time ? -1 : 1)) tree.update(row.r.field, row.h);
        if (tree.root === ledger[i].smt_root) roots++;
        progress('roots', i + 1, ledger.length);
    }
    emit(checked('roots', 'Reconstructed signed SMT roots', start, roots === ledger.length, `Rebuilt the 256-level sparse Merkle state from every record version. ${roots} of ${ledger.length} signed daily roots match.`, `${roots}/${ledger.length}`));

    start = now(); good = 0;
    const feeds = rows.filter(x => x.r.grade === 'A2' && x.r.evidence && x.r.evidence.sig);
    for (const row of feeds) {
        const pk = feedKey(m, row);
        if (pk && await verifyEcdsa(pk, feedMessage(row, m.v2), row.r.evidence.sig)) good++;
    }
    emit(checked('feeds', m.v2 ? 'Authoritative-source signatures (V2)' : 'Historical issuer signatures', start, good === feeds.length,
        m.v2 ? `${good} of ${feeds.length} signed claims verify. Each signature covers field, value, unit, validity and issuer, rebuilt from the committed record and checked against the demo issuer pins.`
             : `${good} of ${feeds.length} signatures verify over messages rebuilt from the committed records. This archive signs field and value only; unit and validity are not covered.`, `${good}/${feeds.length}`));

    if (m.v2) {
        start = now(); good = 0;
        for (const cert of m.certs.values()) if (await verifyCertificate(m, cert)) good++;
        const meterRows = rows.filter(x => x.r.field.includes('/elec/'));
        const bound = meterRows.filter(x => deviceKey(m, x)).length;
        emit(checked('install', 'Installer certificates (meter ↔ building)', start, good === m.certs.size && bound === meterRows.length,
            `${good} of ${m.certs.size} installation certificates verify against the pinned installer key (demo pin), and ${bound} of ${meterRows.length} meter records name a certificate for their own device and building.`, `${good}/${m.certs.size}`));
    } else {
        emit(unsupported('install', 'Installer certificates (meter ↔ building)', 'This archive has unsigned installation assertions, not signed installer certificates. Load the V2 reference run to check them.'));
    }

    start = now();
    const rep = await source('reports.json');
    good = 0;
    for (const b of Object.keys(rep.published)) {
        const s = rep.publishedCanonical[b];
        if (isCanonicalLine(s) && outputHashCanonicalLine(s) === rep.published[b].output_hash &&
            withHash.some(x => x.r.field === `report/2017-01/${b}` && x.r.value.output_hash === rep.published[b].output_hash)) good++;
    }
    emit(checked('reports', 'Published January report hashes', start, good === 3, 'SHA-256(0x30 || canonical report) equals the published hash, and that hash sits in a committed report record (so under a signed root).', `${good}/3`));

    const pr = await source('proofs.json');
    start = now();
    const absent = verifyProof(pr.absence) && pr.absence.recordHash === null && pr.absence.root === ledger[ledger.length - 1].smt_root;
    emit(checked('absence', 'Renna occupants non-membership', start, absent, 'Sparse Merkle non-membership proof against the final signed root: the field was never entered, and no value is invented.', absent ? '1/1' : '0/1'));

    start = now();
    const incl = pr.meterByDay['2017-02-10']['Fox_education_Wendell/elec/2017-02-10'];
    const line = rows.find(x => x.r.field === incl.field && x.r.tx_time.startsWith(incl.day));
    const include = !!line && recordHashCanonicalLine(line.line) === incl.recordHash && verifyProof(incl) && incl.root === ledger.find(e => e.day === incl.day)?.smt_root;
    emit(checked('inclusion', 'Selective disclosure inclusion proof', start, include, `${incl.field}: the disclosed record hashes to the proof's leaf, and a ${32 + 32 * incl.siblings.length}-byte proof folds it into the signed day root.`, include ? '1/1' : '0/1'));

    if (deep) {
        start = now(); good = 0;
        const meter = rows.filter(x => x.r.field.includes('/elec/'));
        const total = meter.reduce((n, x) => n + x.r.value.length, 0);
        let done = 0;
        for (const row of meter) {
            const pk = deviceKey(m, row);
            for (const s of readingMessages(row)) {
                if (pk && await verifyEcdsa(pk, s.msg, s.sig)) good++;
                if (++done % 250 === 0) progress('device', done, total);
            }
        }
        emit(checked('device', 'Deep check: hourly device signatures', start, good === total, `${good} of ${total} hourly signatures verify over messages rebuilt from the committed readings${m.v2 ? ', each with the meter key named in its signed installation certificate' : ''}.`, `${good}/${total}`));
    } else {
        emit(unsupported('device', 'Deep check: hourly device signatures', 'Not run; tick “Deep verification” and run again to check every hourly signature.'));
    }
    put({ type: 'complete', kind: 'run-all' });
}

async function verifyDay(building, day) {
    const m = await model();
    const proofs = await source('proofs.json');
    const proof = proofs.meterByDay[day]?.[`${building}/elec/${day}`];
    if (!proof) throw new Error('No proof for this field and day');
    const row = m.rows.find(x => x.r.field === proof.field && x.r.tx_time.startsWith(day));
    let start = now();
    const ok = !!row && recordHashCanonicalLine(row.line) === proof.recordHash && verifyProof(proof) && proof.root === m.ledger.find(e => e.day === day)?.smt_root;
    emit(checked('day-proof', 'Day inclusion and root', start, ok, 'The record bytes hash to the proof leaf, and the 256-level path recomputes the signed day root.', ok ? '1/1' : '0/1'));
    start = now();
    const pk = deviceKey(m, row);
    let good = 0;
    const msgs = readingMessages(row);
    for (const s of msgs) if (pk && await verifyEcdsa(pk, s.msg, s.sig)) good++;
    emit(checked('day-signatures', 'Hourly device signatures', start, good === msgs.length, `Messages rebuilt from this record's readings; key ${m.v2 ? 'from its signed installation certificate' : 'from the published (simulated) device keys'}.`, `${good}/${msgs.length}`));
    start = now();
    let prev = '00'.repeat(32), count = 0;
    for (const e of m.ledger) {
        if (e.prev !== prev || entryDigest(e, prev) !== e.entry) break;
        prev = e.entry; count++;
        if (e.day === day) break;
    }
    const idx = m.ledger.findIndex(e => e.day === day);
    emit(checked('day-chain', 'Chain through selected day', start, count === idx + 1, `Verified ${count} daily commitments up to ${day}.`, `${count}/${idx + 1}`));
    const entry = m.ledger[idx];
    start = now();
    const ecd = await verifyEcdsa(m.keys.operator_ecdsa, unhex(entry.entry), entry.ecdsa);
    emit(checked('day-ecdsa', 'Day ECDSA signature', start, ecd, 'WebCrypto P-256 against the published (simulated) operator key.', '1/1'));
    start = now();
    const slh = slhVerify(m.keys.operator_slh, unhex(entry.entry), entry.slh_dsa);
    emit(checked('day-slh', 'Day SLH-DSA signature', start, slh, 'Post-quantum FIPS 205 signature on the same entry, verified in this browser.', slh ? '1/1' : '0/1'));
    if (m.v2) {
        start = now();
        const cert = m.certs.get(row.r.evidence.binding_cert_id);
        const cok = !!cert && await verifyCertificate(m, cert) && !!pk;
        emit(checked('day-binding', 'Installation certificate for this meter', start, cok, cert ? `${cert.r.value.certificate_id}: ${cert.r.value.device_id} → ${cert.r.value.building_id}, signed by ${cert.r.value.installer_id} (demo pin).` : 'No certificate named.', cok ? '1/1' : '0/1'));
    }
    put({ type: 'complete', kind: 'verify-day' });
}

async function tamper(which) {
    const m = await model();
    const proofs = await source('proofs.json');
    const row = m.rows.find(x => x.r.field === 'Fox_office_Joy/elec/2017-01-20');
    if (!row) throw Error('Missing source reading');
    const start = now();
    let detail = '', detected = false;
    switch (which) {
        case 'reading': {
            const tree = parseLossless(row.line);
            const orig = tree.value[12].v.raw;
            tree.value[12].v.raw = String(Math.round(Number(orig) * 0.9 * 1e4) / 1e4);
            const line2 = canon(tree);
            const msg = bytes(`{"d":${q(row.r.evidence.device_id)},"f":${q(row.r.field)},"h":${q(tree.value[12].h)},"v":${tree.value[12].v.raw}}`);
            const sigOk = await verifyEcdsa(deviceKey(m, row), msg, tree.value[12].sig);
            const p = proofs.meterByDay['2017-01-20'][row.r.field];
            const rootOk = verifyProof(p, recordHashCanonicalLine(line2));
            detected = !sigOk && !rootOk;
            detail = `Changed 1 hourly reading by 10% (${orig} → ${tree.value[12].v.raw} kWh): the meter signature over the rebuilt message fails, and the record no longer folds into the signed 20 January root.`;
            break;
        }
        case 'grade': {
            const line2 = row.line.replace('"grade":"A1"', '"grade":"C"');
            const p = proofs.meterByDay['2017-01-20'][row.r.field];
            detected = line2 !== row.line && !verifyProof(p, recordHashCanonicalLine(line2));
            detail = 'Changed the record grade from A1 to C: its hash changes, so the Merkle path no longer reaches the signed day root.';
            break;
        }
        case 'ledger': {
            const shortened = m.ledger.filter(e => e.day !== '2017-01-20');
            let prev = '00'.repeat(32), good = true;
            for (const e of shortened) { if (e.prev !== prev || entryDigest(e, prev) !== e.entry) { good = false; break; } prev = e.entry; }
            detected = !good;
            detail = 'Removed the 20 January entry: the next entry commits to a different previous hash, so the chain breaks there.';
            break;
        }
        case 'ecdsa': {
            const e = m.ledger[40];
            const s = unhex(e.ecdsa); s[0] ^= 1;
            detected = !(await verifyEcdsa(m.keys.operator_ecdsa, unhex(e.entry), hex(s)));
            const t = unhex(e.slh_dsa); t[100] ^= 1;
            detected = detected && !slhVerify(m.keys.operator_slh, unhex(e.entry), hex(t));
            detail = `Flipped one bit in the ECDSA and in the SLH-DSA signature of ${e.day}: both verifiers reject them.`;
            break;
        }
        case 'proof': {
            const p = proofs.meterByDay['2017-01-20'][row.r.field];
            detected = verifyProof(p) && !verifyProof({ ...p, recordHash: '00'.repeat(32) });
            detail = 'Substituted a false record hash in a real inclusion proof: the recomputed root no longer matches.';
            break;
        }
        case 'false-meter': {
            put({ type: 'tamper-result', status: 'not-detectable', detail: 'A meter that measures wrongly but signs correctly passes every signature check. Signatures prove who signed the bytes, not that the measurement is right; that needs physical binding and inspection (whitepaper VI).' });
            return;
        }
        default: throw Error('Unknown tamper scenario');
    }
    put({ type: 'tamper-result', status: detected ? 'detected' : 'not-detected', detail, ms: Math.round(now() - start) });
}

/* Lender view: check one published claim end to end, as it was known when it was published. */
async function verifyClaim(building) {
    const m = await model();
    const rep = await source('reports.json');
    const pr = await source('proofs.json');
    const asOf = rep.historicalReports ? Object.keys(rep.historicalReports)[0] : '2017-02-04T23:59';
    const pub = rep.published[building], s = rep.publishedCanonical[building];
    let start = now();
    const h1 = isCanonicalLine(s) && outputHashCanonicalLine(s) === pub.output_hash;
    emit(checked('claim-hash', 'The claim is the published report, byte for byte', start, h1, `SHA-256(0x30 || report bytes) = ${pub.output_hash.slice(0, 12)}…, the hash published for January.`, h1 ? '1/1' : '0/1'));
    start = now();
    const rp = pr.reports[building];
    const rrow = m.rows.find(x => x.r.field === `report/2017-01/${building}`);
    const entry = m.ledger.find(e => e.day === rp.day);
    const h2 = !!rrow && rrow.r.value.output_hash === pub.output_hash && recordHashCanonicalLine(rrow.line) === rp.recordHash && verifyProof(rp) && rp.root === entry?.smt_root;
    emit(checked('claim-committed', 'It was committed under a signed daily root', start, h2, `The report record folds into the ${rp.day} root with a ${32 + 32 * rp.siblings.length}-byte proof.`, h2 ? '1/1' : '0/1'));
    start = now();
    let prev = '00'.repeat(32), chain = true;
    for (const e of m.ledger) { if (e.prev !== prev || entryDigest(e, prev) !== e.entry) { chain = false; break; } prev = e.entry; if (e.day === rp.day) break; }
    const sig = chain && await verifyEcdsa(m.keys.operator_ecdsa, unhex(entry.entry), entry.ecdsa) && slhVerify(m.keys.operator_slh, unhex(entry.entry), entry.slh_dsa);
    emit(checked('claim-root', 'That root is chained and signed twice', start, sig, `Chain verified from ${m.ledger[0].day} to ${rp.day}; the ECDSA and the post-quantum SLH-DSA signature on that day both verify.`, sig ? '2/2' : '0/2'));
    start = now();
    const latest = new Map();
    for (const x of m.rows) {
        if (!x.r.field.startsWith(`${building}/elec/2017-01`) || x.r.tx_time > asOf) continue;
        const o = latest.get(x.r.field);
        if (!o || o.r.tx_time < x.r.tx_time) latest.set(x.r.field, x);
    }
    let good = 0, total = 0, sum = 0;
    for (const x of latest.values()) {
        const pk = deviceKey(m, x);
        for (const sm of readingMessages(x)) { total++; if (pk && await verifyEcdsa(pk, sm.msg, sm.sig)) good++; }
        for (const v of x.r.value) sum += v.v;
    }
    const meter = latest.size ? latest.values().next().value.r.evidence.device_id : '';
    emit(checked('claim-readings', 'Every January reading is signed by the meter', start, good === total && total > 0, `${good} of ${total} hourly readings verify with ${meter}'s key${m.v2 ? ', the key named in its signed installation certificate' : ''}.`, `${good}/${total}`));
    start = now();
    const kwh = Math.round(sum * 100) / 100, cov = Math.round(total / 744 * 1e5) / 1e5;
    const h5 = Math.abs(kwh - pub.actual_kwh.value) < 0.005 && Math.abs(cov - pub.coverage.value) < 1e-5;
    emit(checked('claim-recompute', 'The claimed figures recompute from those readings', start, h5, `${kwh.toLocaleString('en-US', { minimumFractionDigits: 2 })} kWh and ${(cov * 100).toFixed(2)}% coverage (${total} of 744 hours), equal to the report.`, h5 ? '2/2' : '0/2'));
    if (m.v2) {
        start = now();
        const cert = [...m.certs.values()].find(c => c.r.value.building_id === building);
        const cok = !!cert && await verifyCertificate(m, cert);
        emit(checked('claim-binding', 'The meter is bound to this building', start, cok, cert ? `${cert.r.value.certificate_id}: ${cert.r.value.device_id} → ${building}, signed by ${cert.r.value.installer_id} (demo pin). This is the assumption behind grade B.` : 'No certificate for this building.', cok ? '1/1' : '0/1'));
    }
    put({ type: 'complete', kind: 'verify-claim' });
}

onmessage = async (e) => {
    try {
        put({ type: 'start', job: e.data.type });
        if (e.data.type === 'run-all') await runAll(!!e.data.deep);
        else if (e.data.type === 'verify-day') await verifyDay(e.data.building, e.data.day);
        else if (e.data.type === 'tamper') await tamper(e.data.case);
        else if (e.data.type === 'verify-claim') await verifyClaim(e.data.building || 'Fox_office_Joy');
    } catch (err) {
        put({ type: 'error', message: err instanceof Error ? err.message : String(err) });
    }
};
