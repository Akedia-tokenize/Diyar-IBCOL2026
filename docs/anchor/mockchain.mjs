// In-memory stand-in for Sepolia, used only by e2e.mjs: a real EVM (@ethereumjs/vm, Cancun) behind the
// JSON-RPC methods that the operator tool calls on its wallet and the Verify page calls on a public node.
// The signing key is random and lives only in this process.
import { randomBytes } from 'crypto';
import { VM } from '@ethereumjs/vm';
import { Common, Chain, Hardfork } from '@ethereumjs/common';
import { LegacyTransaction } from '@ethereumjs/tx';
import { Address, Account, hexToBytes, bytesToHex, privateToAddress } from '@ethereumjs/util';

const rpcError = (code, message) => Object.assign(new Error(message), { code });

export async function createChain({ chainId = '0xaa36a7', startBlock = 7_000_000, startTime = Date.UTC(2026, 10, 9, 10, 0, 0) / 1000 } = {}) {
    const common = new Common({ chain: Chain.Sepolia, hardfork: Hardfork.Cancun });
    const vm = await VM.create({ common });
    const key = randomBytes(32);
    const me = new Address(privateToAddress(key));
    const reader = new Address(privateToAddress(randomBytes(32)));
    await vm.stateManager.putAccount(me, new Account(0n, 10n ** 20n));
    const st = { chainId, height: startBlock, confirmations: 12, nonce: 0n };
    const receipts = new Map(), blocks = new Map(), unmined = new Set();
    const hx = (n) => '0x' + n.toString(16);

    async function send({ from, to, data }) {
        if (String(from).toLowerCase() !== me.toString()) throw rpcError(4100, 'unknown account');
        const tx = LegacyTransaction.fromTxData({ nonce: st.nonce++, gasPrice: 10n ** 9n, gasLimit: 10_000_000n, to: to || undefined, data }, { common }).sign(key);
        const r = await vm.runTx({ tx, skipBlockGasLimitValidation: true });
        st.height += 1;
        const hash = bytesToHex(tx.hash()), blockNumber = hx(st.height);
        blocks.set(blockNumber, { number: blockNumber, timestamp: hx(startTime + 12 * (st.height - startBlock)), transactions: [hash] });
        receipts.set(hash, {
            transactionHash: hash, blockNumber, from: me.toString(), to: to ? String(to).toLowerCase() : null,
            contractAddress: r.createdAddress ? r.createdAddress.toString() : null,
            status: r.execResult.exceptionError ? '0x0' : '0x1', gasUsed: hx(r.totalGasSpent ?? r.totalGasUsed),
            logs: r.receipt.logs.map(([addr, topics, d], i) => ({ address: bytesToHex(addr), topics: topics.map(t => bytesToHex(t)), data: bytesToHex(d), logIndex: hx(i), blockNumber, transactionHash: hash }))
        });
        unmined.add(hash);                    // the first receipt query returns null, as before a block is mined
        return hash;
    }
    async function request(method, params = []) {
        switch (method) {
            case 'eth_requestAccounts': case 'eth_accounts': return [me.toString()];
            case 'eth_chainId': return st.chainId;
            case 'wallet_switchEthereumChain': st.chainId = params[0].chainId; return null;
            case 'eth_getBalance': return hx((await vm.stateManager.getAccount(me)).balance);
            case 'eth_sendTransaction': return send(params[0]);
            case 'eth_getTransactionReceipt': {
                const k = String(params[0]).toLowerCase();
                if (unmined.delete(k)) return null;
                return receipts.get(k) ?? null;
            }
            case 'eth_getBlockByNumber': return blocks.get(params[0]) ?? null;
            case 'eth_blockNumber': return hx(st.height + st.confirmations);
            case 'eth_getCode': return bytesToHex(await vm.stateManager.getContractCode(Address.fromString(String(params[0]).toLowerCase())));
            case 'eth_call': {
                const r = await vm.evm.runCall({ to: Address.fromString(String(params[0].to).toLowerCase()), caller: reader, data: hexToBytes(params[0].data), gasLimit: 10_000_000n });
                if (r.execResult.exceptionError) throw rpcError(3, 'execution reverted');
                return bytesToHex(r.execResult.returnValue);
            }
            default: throw rpcError(-32601, 'method not supported by the test chain: ' + method);
        }
    }
    return { request, st, receipts, account: me.toString() };
}
