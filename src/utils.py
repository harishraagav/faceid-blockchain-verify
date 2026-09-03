"""
utils.py
Small shared helpers: hashing and canonical record serialization.

The core idea behind the "blockchain verification" stage is that we never
put raw images or scraped post content on-chain (blockchains are a bad,
expensive place to store blobs). Instead we build a small JSON "record"
describing the match, serialize it deterministically, and hash it. Only
that hash goes on-chain. Anyone who has the original record can recompute
the same hash and compare it to the on-chain value.
"""

import hashlib
import json


def sha256_file(path: str) -> str:
    """Return the hex SHA-256 digest of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(record: dict) -> str:
    """
    Serialize a dict deterministically so the same logical record always
    hashes to the same value, regardless of key insertion order.
    """
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def record_hash(record: dict) -> str:
    """
    Compute the canonical SHA-256 hash (hex string, no 0x prefix) of a
    record dict. This is the value that gets written on-chain.
    """
    return sha256_text(canonical_json(record))


def build_match_record(image_path: str, face_result: dict, match: dict, timestamp: str) -> dict:
    """
    Build the canonical record that represents "this face image matches
    this social media post, discovered at this time". This is the object
    whose hash gets written to the blockchain.

    Deliberately excludes the raw face embedding (large, and not needed
    for tamper-evidence of the *match claim*) and instead includes a hash
    of the input image plus the essential facts of the discovered match.
    """
    return {
        "image_sha256": sha256_file(image_path),
        "face_detector": face_result.get("detector"),
        "face_model": face_result.get("model"),
        "face_confidence": face_result.get("face_confidence"),
        "match_title": match.get("title"),
        "match_link": match.get("link"),
        "match_source": match.get("source"),
        "match_is_social": match.get("is_social"),
        "discovered_at": timestamp,
    }
