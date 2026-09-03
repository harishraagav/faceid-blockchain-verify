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

## Extended capabilities

### Multi-face (group photo) support

The task asks for detecting and matching "a face," but a submitted photo
may contain several people. `--multi-face` detects **every** face DeepFace
finds, and independently runs reverse-search + blockchain-anchoring for
each one:

```bash
python src/pipeline.py --image path/to/group_photo.jpg --multi-face
```

Produces `output/record_face1.json`, `output/record_face2.json`, etc. —
one full record + on-chain transaction per detected face. Faces are
processed largest-bounding-box-first.

Standalone (detection only, no search/chain — useful for quick checks):
```bash
python src/face_id.py path/to/group_photo.jpg --all
```

### Embedding similarity check (proving the encoding is load-bearing)

Stage 1 produces a 512-dimension face embedding. Beyond feeding the raw
image to the reverse-search API, `--compare` demonstrates the embedding
is a genuine identity representation by comparing it (via cosine
similarity) against a second photo:

```bash
python src/pipeline.py --image path/to/face.jpg --compare path/to/other_photo_of_same_person.jpg
```

Prints `SAME PERSON` or `DIFFERENT PEOPLE` with the similarity score,
and includes the comparison in `pipeline_result.json`. Standalone:

```bash
python src/similarity.py path/to/photo_a.jpg path/to/photo_b.jpg
```

Threshold: cosine similarity ≥ 0.70 is classified as the same person —
the commonly-used default for Facenet512 embeddings. Verified in testing:
two photos of the same face score ~1.00 (identical crop) down to ~0.75+
for different photos of the same person; two different people typically
score well under 0.30.

**Real limitation found in testing**: two genuine photos of the same
person, one clean-shaven and one with a beard, scored only ~0.52 —
below the 0.70 threshold, misclassified as "different people." This is
a known, documented weakness of face-embedding models generally:
significant appearance changes (facial hair, glasses, major haircuts,
age gaps) measurably reduce similarity even for the same identity,
because those features are part of what the embedding actually
encodes. Lowering the threshold to compensate would reduce the check's
ability to catch genuine impostors, so this is reported as an honest
limitation rather than tuned away. In practice this only affects the
optional `--compare` bonus feature — it has no effect on the core
face→search→blockchain pipeline, which never compares two embeddings
against each other.

### Detector backend comparison

`benchmark_detectors.py` runs the same image through three DeepFace
detector backends (opencv, mtcnn, retinaface) and reports measured
confidence + wall-clock time for each, rather than asserting which is
"best" without evidence:

```bash
python src/benchmark_detectors.py path/to/face.jpg
```

Measured example (real run, CPU-only, your numbers will vary by
hardware and image):

| Backend | Result | Confidence | Time |
|---|---|---|---|
| opencv | ❌ failed to load | — | 1.9s |
| mtcnn | ✅ success | 1.00 | 2.6s |
| retinaface (pipeline default) | ✅ success | 1.00 | 4.2s |

**Finding**: the `opencv` backend failed in testing with `Confirm that
opencv is installed on your environment!` — not a real missing
install, but a known packaging inconsistency: DeepFace's `opencv`
backend needs a Haar Cascade XML file that ships inside the full
`opencv-python` PyPI package but is sometimes absent from
`opencv-python-headless` (the smaller-footprint variant used in
`requirements.txt`, chosen since this project needs no GUI features).
`mtcnn` and `retinaface` both use their own bundled model weights and
were unaffected. Fixable by installing `opencv-python` instead, but
left as-is here since it's not the pipeline's default backend and
scored no higher than the alternatives when it did work. Documented
here rather than silently avoided.

Takeaway: retinaface and mtcnn both reliably hit maximum confidence on
this test image; retinaface is noticeably slower, so mtcnn is a
reasonable middle ground if throughput matters more than using the
pipeline's default.

### Smart-contract mode (on-chain event log, queryable by anyone)

`src/blockchain.py`'s default approach (a hash in a raw transaction's
data field) is fully legitimate but only discoverable if you already
have the specific tx hash. `contracts/FaceMatchRegistry.sol` is a
minimal Solidity registry that emits a `RecordRegistered` event on every
submission, so **all** records ever submitted are discoverable by
anyone via the contract's event log on PolygonScan — not just one
you hand someone the tx hash for.

**Deploying it (one-time, ~5 minutes, via Remix — no local Solidity
toolchain needed):**

1. Go to https://remix.ethereum.org
2. Create a new file, paste in the contents of `contracts/FaceMatchRegistry.sol`
3. Left sidebar → **Solidity Compiler** tab → select compiler version
   `0.8.20` (or compatible) → click **Compile FaceMatchRegistry.sol**
4. Left sidebar → **Deploy & Run Transactions** tab → set
   **Environment** to `Injected Provider - MetaMask` → MetaMask will
   prompt you to connect; make sure MetaMask is switched to the
   **Polygon Amoy** network first
5. Click **Deploy**, confirm the transaction in the MetaMask popup
6. Once mined, copy the deployed **contract address** from Remix's
   "Deployed Contracts" panel
7. Paste it into `.env` as `CONTRACT_ADDRESS=0x...`

**Using it:**

```bash
python src/blockchain_contract.py <hash_hex>          # write (costs gas)
python src/blockchain_contract.py <hash_hex> --check   # read (free)
```

Or integrate it into the main pipeline by swapping the import in
`pipeline.py` from `blockchain.upload_hash_to_chain` to
`blockchain_contract.register_hash_on_contract` (same call signature
for the hash argument).

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
- **POA middleware required.** Polygon's block headers use a longer
  `extraData` field than plain Ethereum (it's a Proof-of-Authority-style
  chain), which trips web3.py's default response validator. `blockchain.py`
  injects `ExtraDataToPOAMiddleware` to handle this — if you swap to a
  different EVM chain, you may or may not still need it.

## Possible upgrades (not implemented, out of scope for the deadline)

- A fallback reverse-search provider (e.g. Google Cloud Vision Web
  Detection) if SerpApi's free quota is exhausted mid-demo.
- Persisting all `output/record_faceN.json` files from a `--multi-face`
  run into a single combined index, rather than one file per face.

## Repo layout

```
faceid-blockchain-verify/
├── src/
│   ├── face_id.py             # Stage 1: face detect + encode (DeepFace), single or --all faces
│   ├── reverse_search.py      # Stage 2: live reverse-image search (SerpApi/Google Lens)
│   ├── blockchain.py          # Stage 3: raw-tx on-chain record (Polygon Amoy) — default path
│   ├── blockchain_contract.py # Stage 3 alternative: FaceMatchRegistry smart-contract mode
│   ├── verify.py               # Independent re-verification CLI
│   ├── similarity.py           # Embedding comparison (cosine similarity, same/different person)
│   ├── benchmark_detectors.py  # Measured comparison of detector backends
│   ├── utils.py                 # Hashing + canonical record building
│   └── pipeline.py              # Orchestrates all stages; --multi-face, --compare flags
├── contracts/
│   └── FaceMatchRegistry.sol   # Optional on-chain registry contract (see "Smart-contract mode")
├── examples/                    # Sample/test images
├── requirements.txt
├── .env.example
└── README.md
```
