"""
blockchain_contract.py
Alternative to blockchain.py: writes record hashes to the deployed
FaceMatchRegistry smart contract (contracts/FaceMatchRegistry.sol)
instead of embedding them in a raw transaction's data field.

Requires the contract to already be deployed (see README "Deploying the
smart contract" section — done once, via Remix). Set CONTRACT_ADDRESS
in .env after deploying.

Advantage over blockchain.py's approach: every record ever submitted is
independently discoverable by anyone via the RecordRegistered event log
on a block explorer — not just someone who already has a specific tx
hash.
"""

import os
import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CHAIN_ID = 80002  # Polygon Amoy testnet
DEFAULT_EXPLORER_TX_URL = "https://amoy.polygonscan.com/tx/{tx_hash}"
DEFAULT_EXPLORER_ADDRESS_URL = "https://amoy.polygonscan.com/address/{address}"

# Minimal ABI — only the functions/events this client actually uses.
# Matches contracts/FaceMatchRegistry.sol.
CONTRACT_ABI = json.loads("""
[
  {
    "inputs": [{"internalType": "bytes32", "name": "recordHash", "type": "bytes32"}],
    "name": "registerRecord",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{"internalType": "bytes32", "name": "recordHash", "type": "bytes32"}],
    "name": "checkRecord",
    "outputs": [
      {"internalType": "bool", "name": "registered", "type": "bool"},
      {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "anonymous": false,
    "inputs": [
      {"indexed": true, "internalType": "bytes32", "name": "recordHash", "type": "bytes32"},
      {"indexed": true, "internalType": "address", "name": "submitter", "type": "address"},
      {"indexed": false, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
    ],
    "name": "RecordRegistered",
    "type": "event"
  }
]
""")


def _get_web3(rpc_url: str = None) -> Web3:
    rpc_url = rpc_url or os.environ.get("AMOY_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("AMOY_RPC_URL not set (env var or rpc_url param).")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"Could not connect to RPC endpoint: {rpc_url}")
    return w3


def register_hash_on_contract(hash_hex: str, contract_address: str = None,
                               private_key: str = None, rpc_url: str = None,
                               chain_id: int = DEFAULT_CHAIN_ID) -> dict:
    """
    Call FaceMatchRegistry.registerRecord(hash_hex) on-chain.

    Returns:
        {"tx_hash": "0x...", "explorer_url": "...", "contract_address": "...",
         "block_number": int, "status": int}
    """
    contract_address = contract_address or os.environ.get("CONTRACT_ADDRESS")
    if not contract_address:
        raise EnvironmentError(
            "CONTRACT_ADDRESS not set. Deploy contracts/FaceMatchRegistry.sol "
            "first (see README), then set CONTRACT_ADDRESS in .env."
        )
    private_key = private_key or os.environ.get("WALLET_PRIVATE_KEY")
    if not private_key:
        raise EnvironmentError("WALLET_PRIVATE_KEY not set (env var or private_key param).")

    w3 = _get_web3(rpc_url)
    account = Account.from_key(private_key)
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=CONTRACT_ABI)

    hash_bytes = bytes.fromhex(hash_hex[2:] if hash_hex.startswith("0x") else hash_hex)
    if len(hash_bytes) != 32:
        raise ValueError(f"hash_hex must be exactly 32 bytes (64 hex chars), got {len(hash_bytes)} bytes.")

    tx = contract.functions.registerRecord(hash_bytes).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": chain_id,
    })

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
        "contract_address": contract_address,
        "contract_explorer_url": DEFAULT_EXPLORER_ADDRESS_URL.format(address=contract_address),
        "block_number": receipt["blockNumber"],
        "status": receipt["status"],
    }


def check_hash_on_contract(hash_hex: str, contract_address: str = None, rpc_url: str = None) -> dict:
    """
    Read-only re-verification: ask the contract itself whether a given
    hash has ever been registered, and when. Costs no gas (view call).
    """
    contract_address = contract_address or os.environ.get("CONTRACT_ADDRESS")
    if not contract_address:
        raise EnvironmentError("CONTRACT_ADDRESS not set.")

    w3 = _get_web3(rpc_url)
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=CONTRACT_ABI)

    hash_bytes = bytes.fromhex(hash_hex[2:] if hash_hex.startswith("0x") else hash_hex)
    registered, timestamp = contract.functions.checkRecord(hash_bytes).call()

    return {"registered": registered, "registered_at_unix": timestamp}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python blockchain_contract.py <hash_hex> [--check]")
        sys.exit(1)

    if "--check" in sys.argv:
        result = check_hash_on_contract(sys.argv[1])
        print(json.dumps(result, indent=2))
    else:
        result = register_hash_on_contract(sys.argv[1])
        print(f"Tx hash: {result['tx_hash']}")
        print(f"Explorer: {result['explorer_url']}")
        print(f"Contract: {result['contract_explorer_url']}")
        print(f"Block: {result['block_number']} | status: {result['status']}")
