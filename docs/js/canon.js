/* Lossless JSON for DIYAR evidence.

   The reference encoder is Python json.dumps(sort_keys=True, separators=(",", ":"),
   ensure_ascii=False). JavaScript's JSON.parse/JSON.stringify cannot reproduce its bytes:
   a float such as 50.0 comes back as "50". This module keeps every number exactly as it was
   written, so the browser can rebuild the exact bytes a device, issuer or installer signed
   from the committed record itself, instead of trusting a precomputed message file. */

export class Num {
    constructor(raw) { this.raw = raw; }
    valueOf() { return Number(this.raw); }
}

export function parseLossless(text) {
    let i = 0;
    const ws = () => { while (i < text.length && ' \t\n\r'.includes(text[i])) i++; };
    const fail = (m) => { throw new Error(`Malformed JSON at ${i}: ${m}`); };
    function value() {
        ws();
        const c = text[i];
        if (c === '{') {
            i++; const o = {}; ws();
            if (text[i] === '}') { i++; return o; }
            for (;;) {
                ws(); if (text[i] !== '"') fail('key');
                const k = string();
                if (Object.prototype.hasOwnProperty.call(o, k)) fail('duplicate key ' + k);
                ws(); if (text[i++] !== ':') fail('colon');
                o[k] = value(); ws();
                if (text[i] === ',') { i++; continue; }
                if (text[i] === '}') { i++; return o; }
                fail('object');
            }
        }
        if (c === '[') {
            i++; const a = []; ws();
            if (text[i] === ']') { i++; return a; }
            for (;;) {
                a.push(value()); ws();
                if (text[i] === ',') { i++; continue; }
                if (text[i] === ']') { i++; return a; }
                fail('array');
            }
        }
        if (c === '"') return string();
        if (text.startsWith('true', i)) { i += 4; return true; }
        if (text.startsWith('false', i)) { i += 5; return false; }
        if (text.startsWith('null', i)) { i += 4; return null; }
        const m = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(i, i + 40));
        if (!m) fail('value');
        i += m[0].length;
        return new Num(m[0]);
    }
    function string() {
        const start = i; i++;
        while (i < text.length && text[i] !== '"') i += text[i] === '\\' ? 2 : 1;
        if (text[i] !== '"') fail('string');
        i++;
        return JSON.parse(text.slice(start, i));
    }
    const v = value(); ws();
    if (i !== text.length) fail('trailing data');
    return v;
}

/* Python repr(float): shortest round-trip digits; fixed notation when -4 <= exponent < 16,
   otherwise d.ddde±XX; integral values keep ".0". */
export function pyFloatRepr(x) {
    if (!Number.isFinite(x)) throw new Error('NaN/Infinity are not canonical');
    if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
    const [mant, e] = x.toExponential().split('e');
    const exp = parseInt(e, 10), neg = mant[0] === '-';
    const digits = mant.replace('-', '').replace('.', '');
    let s;
    if (exp >= -4 && exp < 16) {
        if (exp >= 0) {
            const intPart = digits.slice(0, exp + 1).padEnd(exp + 1, '0');
            const frac = digits.slice(exp + 1);
            s = intPart + '.' + (frac || '0');
        } else {
            s = '0.' + '0'.repeat(-exp - 1) + digits;
        }
    } else {
        s = digits[0] + (digits.length > 1 ? '.' + digits.slice(1) : '') + 'e' + (exp < 0 ? '-' : '+') + String(Math.abs(exp)).padStart(2, '0');
    }
    return (neg ? '-' : '') + s;
}

export function canonicalNumber(raw) {
    if (/^-?(?:0|[1-9]\d*)$/.test(raw)) return raw !== '-0';           // Python int
    return pyFloatRepr(Number(raw)) === raw;                               // Python float
}

export function canon(v) {
    if (v === null) return 'null';
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (v instanceof Num) return v.raw;
    if (typeof v === 'string') return JSON.stringify(v);
    if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
    if (typeof v === 'object') return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
    throw new Error('Only losslessly parsed values can be re-encoded');
}

/* True when the line is exactly the reference encoder's output for its own content. */
export function isCanonicalLine(line) {
    try {
        let ok = true;
        const walk = (v) => {
            if (v instanceof Num) { if (!canonicalNumber(v.raw)) ok = false; }
            else if (Array.isArray(v)) v.forEach(walk);
            else if (v && typeof v === 'object') Object.values(v).forEach(walk);
        };
        const tree = parseLossless(line);
        walk(tree);
        return ok && canon(tree) === line;
    } catch {
        return false;
    }
}

export const plain = (v) => v instanceof Num ? Number(v.raw) : Array.isArray(v) ? v.map(plain)
    : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)])) : v;
