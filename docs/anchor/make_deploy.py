"""Fill the operator tool template with the compiled contract and the ledger's batch calldata.
usage: python3 -I make_deploy.py ANCHOR_DIR OUT_HTML"""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
inp = json.loads((d / 'deploy-inputs.json').read_text())
gas = json.loads((d / 'gas.json').read_text())
tpl = (d / 'deploy-anchor.template.html').read_text()
keep = {k: inp[k] for k in ('bytecode', 'batchData', 'expectedHead', 'days', 'firstDay', 'lastDay', 'selectors', 'compiler', 'sourceSha256')}
keep['expectedHead'] = keep['expectedHead'].lower()
fill = {
    '__INPUTS__': json.dumps(keep, separators=(',', ':')),
    '__DAYS__': str(inp['days']),
    '__FIRST__': inp['firstDay'],
    '__LAST__': inp['lastDay'],
    '__HEADSHORT__': inp['expectedHead'][:12] + '…' + inp['expectedHead'][-6:],
    '__SRCSHORT__': inp['sourceSha256'][:12] + '…',
    '__COMPILER__': inp['compiler'].split('+')[0],
    '__INITBYTES__': f"{(len(inp['bytecode']) - 2) // 2:,}",
    '__GAS_DEPLOY__': f"{gas['deploy_gas']:,}",
    '__GAS_BATCH__': f"{gas['batch_91_gas']:,}",
}
for k, v in fill.items():
    assert k in tpl, k
    tpl = tpl.replace(k, v)
assert '__' not in tpl.replace('__proto__', ''), 'unfilled placeholder'
Path(sys.argv[2]).write_text(tpl)
print('wrote', sys.argv[2], len(tpl), 'bytes')
