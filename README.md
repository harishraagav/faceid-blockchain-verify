# Face ID + Blockchain Verification

**HH Goa 2026 — Shortlisting Task 3**

A pipeline that (1) detects and encodes a face from a photo, (2) runs a
genuine, live reverse-image search to find a real matching social media
post, and (3) writes a tamper-evident, publicly verifiable record of that
match to a public blockchain.

```
 face image
     │
     ▼
┌─────────────────────┐
│ 1. Face ID           │  DeepFace (RetinaFace detector + Facenet512
│    detect + encode   │  embedding model) → 512-d face embedding
└─────────┬────────────┘
          ▼
┌─────────────────────┐
│ 2. Reverse image      │  SerpApi → Google Lens engine (live API call,
│    search             │  no hardcoded results) → real visual matches,
└─────────┬────────────┘  ranked with social-media links first
          ▼
┌─────────────────────┐
│ 3. Blockchain upload  │  SHA-256 hash of the match record → written
│    + verification     │  on-chain (Polygon Amoy testnet) → publicly
└─────────┬────────────┘  re-verifiable via PolygonScan or any RPC node
          ▼
   record.json + tx hash + explorer link
```

## Why it's genuine, not staged

- **Face encoding is a real embedding**, not just a bounding box — 512
  floating point numbers from Facenet512, produced by DeepFace at
  detection time.
- **The reverse-image search is a live API call** to Google Lens (via
  SerpApi) made *with the input image itself* as the query. Nothing about
  the resulting match is chosen or hardcoded in advance — whatever Google
  Lens returns for that specific image at request time is what gets used.
  Matches are ranked with known social-media domains
  (Instagram/X/Facebook/LinkedIn/Pinterest/Reddit/TikTok/etc.) first, but
  all real visual matches are returned, not filtered to only "nice"
  results.
- **The blockchain write is a real on-chain transaction** on Polygon
  Amoy, a public Ethereum-compatible testnet. It is not a local
  SQLite file relabeled as a "chain." Anyone can independently look up
  the transaction on
  [PolygonScan](https://amoy.polygonscan.com/) and see the exact same
  hash this pipeline computed.

## What actually goes on-chain

We do **not** put the raw image or the full scraped post on-chain —
blockchains are a slow, expensive place to store blobs, and it isn't
necessary for tamper-evidence. Instead:

1. We build a small JSON **record**: a SHA-256 hash of the input image
   file, the face detector/model used, the matched post's title/link/
   source, and a UTC timestamp.
2. We canonically serialize that record (sorted keys, no whitespace) and
   take its **SHA-256 hash** — a single 32-byte fingerprint.
3. That 32-byte hash is written into the `data` field of a zero-value
   self-transaction on Polygon Amoy.
4. **Re-verification** (`src/verify.py`) recomputes the hash from the
   saved `record.json` and compares it against the hash pulled back off
   the transaction on-chain. If even one character of `record.json`
   changes — the claimed link, the timestamp, anything — the recomputed
   hash no longer matches the on-chain value, and verification fails
   loudly. That mismatch *is* the tamper-evidence guarantee.

## Which blockchain, and why

**Polygon Amoy** (chain ID `80002`), a free public Ethereum-compatible
testnet.

- Free — test MATIC from a public faucet, no real funds ever touch this.
- Public and independently verifiable — anyone can check the transaction
  on PolygonScan without trusting this codebase at all.
- We deliberately avoided writing/deploying a custom Solidity smart
  contract: a plain transaction with data is a fully legitimate,
  minimal-failure-surface way to get an immutable on-chain record, given
  the one-week build window. (See "Possible upgrades" below for the
  smart-contract version.)

## Setup

### 1. Clone and install

```bash
git clone <this-repo-url>
cd faceid-blockchain-verify
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get three free accounts/keys

| Service | What for | Link |
|---|---|---|
| SerpApi | reverse image search | https://serpapi.com/manage-api-key (100 free searches/month) |
| Alchemy (or Infura) | Polygon Amoy RPC endpoint | https://www.alchemy.com/ → create app → "Polygon Amoy" |
| MetaMask | throwaway testnet wallet | https://metamask.io/ → create a **new, empty** wallet, export its private key |

Then fund the wallet with free test MATIC:
https://faucet.polygon.technology/ (select **Amoy**, paste your address).

### 3. Configure

```bash
cp .env.example .env
# fill in SERPAPI_KEY, AMOY_RPC_URL, WALLET_PRIVATE_KEY
```

### 4. Run

```bash
python src/pipeline.py --image path/to/face.jpg
```

This runs all three stages end-to-end and prints/saves:
- `output/record.json` — the match record
- `output/pipeline_result.json` — full run output including the tx hash
  and PolygonScan link

### 5. Independently re-verify

```bash
python src/verify.py output/record.json <tx_hash printed above>
```

Prints `✅ VERIFIED` if the local record hash matches the on-chain hash,
or `❌ TAMPERED / MISMATCH` (and exits non-zero) if not. Try editing
`record.json` by hand afterward and re-running this to see the mismatch
detection fire.

### Running stages individually (for debugging/demoing)

```bash
python src/face_id.py path/to/face.jpg
python src/reverse_search.py path/to/face.jpg
python src/blockchain.py <some_sha256_hex>
```

## Known limitations

- **SerpApi free tier**: 100 searches/month, and its image-upload
  endpoint caps files at **500 KB** — downscale/compress larger photos
  before running the pipeline, or host the image yourself and pass
  `image_url` instead of `image_path` to `reverse_search.py`.
- **Match quality depends on the photo already being findable online.**
  Google Lens can only return a real match if that face genuinely
  appears in an indexed public post somewhere; a private or never-posted
  photo will correctly produce no match rather than a fabricated one.
- **Testnet, not mainnet.** Polygon Amoy is a test network — the record
  is real and publicly verifiable, but test MATIC has no monetary value.
  Swapping to Polygon mainnet only requires changing the RPC URL, chain
  ID, and funding the wallet with real MATIC — no code logic changes.
- **Single dominant face per image.** If a photo contains multiple
  people, the pipeline encodes the largest/most prominent detected face
  and ignores the rest.
- **No identity claim beyond "this embedding was computed."** The
  pipeline does not claim to know *who* the person is — it encodes a
  face and finds where visually matching imagery already exists online;
  it makes no independent identity/age/name inference.
- **Gas/network variability.** Testnet transaction confirmation time
  depends on Amoy network conditions; the pipeline waits up to 180s for
  a receipt before failing.

## Possible upgrades (not implemented, out of scope for the deadline)

- A minimal Solidity registry contract instead of a raw self-transaction:

  ```solidity
  // SPDX-License-Identifier: MIT
  pragma solidity ^0.8.20;

  contract FaceMatchRegistry {
      event RecordRegistered(bytes32 indexed recordHash, address indexed submitter, uint256 timestamp);

      function registerRecord(bytes32 recordHash) external {
          emit RecordRegistered(recordHash, msg.sender, block.timestamp);
      }
  }
  ```

  This would let anyone query all records ever submitted by filtering
  `RecordRegistered` events, rather than needing a specific tx hash.
- Multi-face batch mode (encode + search + anchor every face in a group
  photo in one run).
- A fallback reverse-search provider (e.g. Google Cloud Vision Web
  Detection) if SerpApi's free quota is exhausted mid-demo.

## Repo layout

```
faceid-blockchain-verify/
├── src/
│   ├── face_id.py         # Stage 1: face detect + encode (DeepFace)
│   ├── reverse_search.py  # Stage 2: live reverse-image search (SerpApi/Google Lens)
│   ├── blockchain.py      # Stage 3: write + re-fetch on-chain record (Polygon Amoy)
│   ├── verify.py          # Independent re-verification CLI
│   ├── utils.py           # Hashing + canonical record building
│   └── pipeline.py        # Orchestrates all three stages end-to-end
├── examples/               # Sample/test images
├── requirements.txt
├── .env.example
└── README.md
```
