/* Worker for the in-page anchor demo: loads the ledger and the compiled contract from this site, runs anchor-local.js
   on a local EVM and posts each step. Loaded only when the visitor presses the button. */
import { runLocal } from './anchor-local.js';

self.onmessage = async (e) => {
    if (!e.data || e.data.type !== 'local-run') return;
    try {
        const get = async (path) => { const r = await fetch(path); if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); };
        const [ledger, artifact] = await Promise.all([get('../data/ledger.json'), get('../anchor/DiyarAnchor.json')]);
        await runLocal({ ledger, artifact, expect: e.data.expect, onStep: (step) => self.postMessage({ type: 'local-step', step }) });
        self.postMessage({ type: 'local-done' });
    } catch (err) {
        self.postMessage({ type: 'local-error', message: err && err.message ? err.message : String(err) });
    }
};
