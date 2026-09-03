"""
blockchain.py
Stage 3 of the pipeline: write a tamper-evident record to a public
blockchain (Polygon Amoy testnet by default).

Design choice: rather than deploying a custom Solidity smart contract, we
send a zero-value self-transaction whose `data` field carries the SHA-256
hash (32 bytes) of the match record. This is a fully legitimate on-chain
write — the hash is permanently and publicly recorded in that
transaction, viewable and independently re-derivable by anyone via a
public block explorer (Amoy PolygonScan) or any Ethereum-compatible RPC
node. It avoids the extra failure surface of contract deployment while
still satisfying "verifiable, tamper-evident record on a blockchain".

A `contract.sol` alternative (an on-chain registry contract with a
`registerRecord(bytes32 hash)` function + event log) is sketched in
README.md as an optional upgrade path.
"""

import os
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CHAIN_ID = 80002  # Polygon Amoy testnet
DEFAULT_EXPLORER_TX_URL = "https://amoy.polygonscan.com/tx/{tx_hash}"


def _get_web3(rpc_url: str = None) -> Web3:
    rpc_url = rpc_url or os.environ.get("AMOY_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("AMOY_RPC_URL not set (env var or rpc_url param).")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    # Polygon (like many chains) is Proof-of-Authority-style and uses a
    # longer extraData field in its block headers than plain Ethereum.
    # Without this middleware, web3.py's default validator rejects every
    # block it reads with ExtraDataLengthError.
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"Could not connect to RPC endpoint: {rpc_url}")
    return w3


def upload_hash_to_chain(hash_hex: str, private_key: str = None, rpc_url: str = None,
                          chain_id: int = DEFAULT_CHAIN_ID) -> dict:
    """
    Send a zero-value transaction to yourself with `hash_hex` embedded in
    the transaction's data field, on the given EVM-compatible chain
    (Polygon Amoy by default).

    Args:
        hash_hex: hex string (with or without 0x prefix) of the record hash
            to write on-chain — typically the output of utils.record_hash().
        private_key: funded testnet wallet private key. Falls back to the
            WALLET_PRIVATE_KEY env var. NEVER commit this to git.
        rpc_url: EVM JSON-RPC endpoint (e.g. an Alchemy/Infura Amoy URL).
            Falls back to the AMOY_RPC_URL env var.
        chain_id: EVM chain id (80002 = Polygon Amoy).

    Returns:
        {"tx_hash": "0x...", "explorer_url": "...", "block_number": int}
    """
    private_key = private_key or os.environ.get("WALLET_PRIVATE_KEY")
    if not private_key:
        raise EnvironmentError("WALLET_PRIVATE_KEY not set (env var or private_key param).")

    w3 = _get_web3(rpc_url)
    account = Account.from_key(private_key)

    data = hash_hex if hash_hex.startswith("0x") else "0x" + hash_hex

    tx = {
        "from": account.address,
        "to": account.address,       # self-transaction; only the data matters
        "value": 0,
        "data": data,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": chain_id,
    }
    tx["gas"] = w3.eth.estimate_gas(tx)

    # EIP-1559 fee fields (Amoy supports EIP-1559)
    latest = w3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas", w3.to_wei(30, "gwei"))
    priority_fee = w3.to_wei(30, "gwei")
    tx["maxPriorityFeePerGas"] = priority_fee
    tx["maxFeePerGas"] = base_fee * 2 + priority_fee

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    tx_hash_hex = tx_hash.hex()
    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = "0x" + tx_hash_hex

    return {
        "tx_hash": tx_hash_hex,
        "explorer_url": DEFAULT_EXPLORER_TX_URL.format(tx_hash=tx_hash_hex),
        "block_number": receipt["blockNumber"],
        "status": receipt["status"],  # 1 = success
    }


def fetch_hash_from_chain(tx_hash: str, rpc_url: str = None) -> str:
    """
    Re-fetch a transaction by hash and return the hex hash stored in its
    data field (no 0x prefix), for comparison against a locally
    recomputed record hash. This is the "re-verification" step.
    """
    w3 = _get_web3(rpc_url)
    tx = w3.eth.get_transaction(tx_hash)
    input_data = tx["input"]
    # web3.py returns HexBytes for input
    hex_str = input_data.hex() if hasattr(input_data, "hex") else input_data
    return hex_str[2:] if hex_str.startswith("0x") else hex_str


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python blockchain.py <hash_hex>")
        sys.exit(1)

    result = upload_hash_to_chain(sys.argv[1])
    print(f"Tx hash: {result['tx_hash']}")
    print(f"Explorer: {result['explorer_url']}")
    print(f"Block: {result['block_number']} | status: {result['status']}")
