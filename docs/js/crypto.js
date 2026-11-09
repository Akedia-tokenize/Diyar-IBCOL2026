/* Independent browser-side SHA-256 / sparse Merkle / ECDSA verification.
   No value is approved based on an exported `verified:true` flag. */
export const enc = new TextEncoder();
export const bytes = (s) => enc.encode(s);
export const hex = (a) => Array.from(a, v => v.toString(16).padStart(2, '0')).join('');
export const unhex = (s) => {
    if (!/^(?:[a-f0-9]{2})*$/i.test(s))
        throw new Error('Malformed hex');
    return Uint8Array.from(s.match(/../g)?.map(x => parseInt(x, 16)) || []);
};
export function concat(...parts) {
    const length = parts.reduce((n, a) => n + a.length, 0);
    const result = new Uint8Array(length);
    let offset = 0;
    for (const p of parts) {
        result.set(p, offset);
        offset += p.length;
    }
    return result;
}
const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]);
const rr = (x, n) => ((x >>> n) | (x << (32 - n))) >>> 0;
export function sha256(data) {
    const l = data.length, extra = (56 - ((l + 1) % 64) + 64) % 64, total = l + 1 + extra + 8;
    const padded = new Uint8Array(total);
    padded.set(data);
    padded[l] = 0x80;
    const view = new DataView(padded.buffer);
    const bits = BigInt(l) * 8n;
    view.setUint32(total - 8, Number((bits >> 32n) & 0xffffffffn));
    view.setUint32(total - 4, Number(bits & 0xffffffffn));
    const h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    const w = new Uint32Array(64);
    for (let off = 0; off < total; off += 64) {
        for (let i = 0; i < 16; i++)
            w[i] = view.getUint32(off + i * 4);
        for (let i = 16; i < 64; i++) {
            const x = w[i - 15], y = w[i - 2];
            const s0 = rr(x, 7) ^ rr(x, 18) ^ (x >>> 3), s1 = rr(y, 17) ^ rr(y, 19) ^ (y >>> 10);
            w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
        }
        let [a, b, c, d, e, f, g, hh] = Array.from(h);
        for (let i = 0; i < 64; i++) {
            const S1 = rr(e, 6) ^ rr(e, 11) ^ rr(e, 25), ch = (e & f) ^ (~e & g), t1 = (hh + S1 + ch + K[i] + w[i]) >>> 0;
            const S0 = rr(a, 2) ^ rr(a, 13) ^ rr(a, 22), maj = (a & b) ^ (a & c) ^ (b & c), t2 = (S0 + maj) >>> 0;
            hh = g;
            g = f;
            f = e;
            e = (d + t1) >>> 0;
            d = c;
            c = b;
            b = a;
            a = (t1 + t2) >>> 0;
        }
        for (let i = 0; i < 8; i++)
            h[i] = (h[i] + [a, b, c, d, e, f, g, hh][i]) >>> 0;
    }
    const out = new Uint8Array(32), ov = new DataView(out.buffer);
    for (let i = 0; i < 8; i++)
        ov.setUint32(i * 4, h[i]);
    return out;
}
export const H = (...a) => sha256(concat(...a));
const ONE = (n) => new Uint8Array([n]);
const EMPTY = [H(ONE(0x02))];
for (let i = 0; i < 256; i++)
    EMPTY.push(H(ONE(0x01), EMPTY[i], EMPTY[i]));
const U64 = (v) => { const a = new Uint8Array(32); for (let i = 31; i >= 0; i--) {
    a[i] = Number(v & 255n);
    v >>= 8n;
} return a; };
const big = (arr) => BigInt('0x' + hex(arr));
export function verifyProof(proof, overrideHash) {
    try {
        const valueHash = overrideHash === undefined ? proof.recordHash : overrideHash;
        let k = big(sha256(bytes(proof.field)));
        let cur = valueHash === null ? EMPTY[0] : H(ONE(0x00), U64(k), unhex(valueHash));
        let mask = BigInt('0x' + proof.mask), index = 0;
        for (let level = 0; level < 256; level++) {
            let sibling = EMPTY[level];
            if (((mask >> BigInt(level)) & 1n) === 1n) {
                if (index >= proof.siblings.length)
                    return false;
                sibling = unhex(proof.siblings[index++]);
                if (sibling.length !== 32)
                    return false;
            }
            cur = (k & 1n) === 0n ? H(ONE(0x01), cur, sibling) : H(ONE(0x01), sibling, cur);
            k >>= 1n;
        }
        return index === proof.siblings.length && hex(cur) === proof.root;
    }
    catch {
        return false;
    }
}
export function recordHashCanonicalLine(line) { return hex(H(ONE(0x10), bytes(line))); }
export function outputHashCanonicalLine(line) { return hex(H(ONE(0x30), bytes(line))); }
const P = BigInt('0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff');
const B = BigInt('0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b');
const mod = (x) => (x % P + P) % P;
function modpow(a, n) { let y = 1n; while (n > 0n) {
    if (n & 1n)
        y = mod(y * a);
    a = mod(a * a);
    n >>= 1n;
} return y; }
export function decompressP256(pkhex) {
    const k = unhex(pkhex);
    if (k.length === 65 && k[0] === 4)
        return k;
    if (k.length !== 33 || (k[0] !== 2 && k[0] !== 3))
        throw new Error('Invalid P-256 public key');
    const x = big(k.slice(1)), root = modpow(mod(x * x * x - 3n * x + B), (P + 1n) >> 2n);
    if (mod(root * root) !== mod(x * x * x - 3n * x + B))
        throw new Error('Invalid P-256 point');
    const y = (root & 1n) === BigInt(k[0] & 1) ? root : mod(-root);
    return concat(ONE(4), U64(x), U64(y));
}
const keyCache = new Map();
export async function verifyEcdsa(pk, msg, sig) {
    try {
        if (!keyCache.has(pk))
            keyCache.set(pk, crypto.subtle.importKey('raw', decompressP256(pk), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']));
        const k = await keyCache.get(pk);
        const s = unhex(sig);
        if (s.length !== 64)
            return false;
        return await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, k, s, msg);
    }
    catch {
        return false;
    }
}
export function entryDigest(e, prev) { return hex(H(ONE(0x20), bytes(e.day), unhex(e.smt_root), unhex(prev))); }
export class SparseTree {
    nodes = new Map();
    find(h, p) { return this.nodes.get(h + ':' + p.toString(16)) || EMPTY[h]; }
    set(h, p, v) { const key = h + ':' + p.toString(16); if (hex(v) === hex(EMPTY[h]))
        this.nodes.delete(key);
    else
        this.nodes.set(key, v); }
    update(field, recordHash) {
        const key = big(sha256(bytes(field)));
        let cur = H(ONE(0), U64(key), unhex(recordHash));
        this.set(0, key, cur);
        let p = key;
        for (let i = 0; i < 256; i++) {
            const s = this.find(i, p ^ 1n);
            cur = (p & 1n) === 0n ? H(ONE(1), cur, s) : H(ONE(1), s, cur);
            p >>= 1n;
            this.set(i + 1, p, cur);
        }
    }
    get root() { return hex(this.find(256, 0n)); }
}
