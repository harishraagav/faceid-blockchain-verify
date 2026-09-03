"""
verify.py
Independent re-verification step, run separately from the upload.

Given a saved record.json (produced by pipeline.py) and the tx_hash it
was anchored under, this:
  1. Recomputes the record hash locally from the saved record.
  2. Fetches the transaction from the blockchain and extracts the hash
     that was actually stored on-chain.
  3. Compares the two.

If someone tampers with record.json after the fact (e.g. edits the
matched link or the claimed image), step 1's hash will no longer match
step 2's on-chain hash — that mismatch is the tamper-evidence guarantee
this whole pipeline is built around.
"""

import json
import sys
from dotenv import load_dotenv

load_dotenv()

from utils import record_hash
from blockchain import fetch_hash_from_chain


def verify_record(record_path: str, tx_hash: str, rpc_url: str = None) -> dict:
    with open(record_path, "r") as f:
        record = json.load(f)

    local_hash = record_hash(record)
    onchain_hash = fetch_hash_from_chain(tx_hash, rpc_url=rpc_url)

    match = local_hash == onchain_hash
    return {
        "verified": match,
        "local_hash": local_hash,
        "onchain_hash": onchain_hash,
        "tx_hash": tx_hash,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python verify.py <record.json> <tx_hash>")
        sys.exit(1)

    result = verify_record(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2))
    if result["verified"]:
        print("\n✅ VERIFIED — local record hash matches the on-chain record.")
    else:
        print("\n❌ TAMPERED / MISMATCH — local record hash does NOT match on-chain record.")
        sys.exit(1)
