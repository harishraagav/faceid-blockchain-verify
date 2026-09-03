"""
pipeline.py
End-to-end orchestrator for HH Goa 2026 Task 3:

    face scan  -->  genuine reverse-image search  -->  blockchain upload

Basic run (single, largest face):
    python src/pipeline.py --image path/to/face.jpg

Group photo (anchor a record for every detected face):
    python src/pipeline.py --image path/to/group.jpg --multi-face

Optional: also prove the embedding is a real identity representation by
comparing it against a second photo of (supposedly) the same person:
    python src/pipeline.py --image path/to/face.jpg --compare path/to/other.jpg

This is deliberately a CLI script, not a web app/UI — the task explicitly
says no website/hosting is needed and the pipeline itself is what's judged.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from face_id import detect_and_encode, detect_and_encode_all
from reverse_search import reverse_image_search
from blockchain import upload_hash_to_chain
from utils import build_match_record, record_hash
from similarity import compare_faces

load_dotenv()


def _anchor_one_face(image_path: str, face_result: dict, out_dir: str, tag: str = "") -> dict:
    """
    Run stages 2+3 (search + blockchain upload) for a single already-
    detected face, and save its record/result files. `tag` disambiguates
    output filenames when anchoring multiple faces from one image.
    """
    suffix = f"_{tag}" if tag else ""

    print(f"\n[2/3] Live reverse-image search (SerpApi / Google Lens){' — ' + tag if tag else ''}...")
    matches = reverse_image_search(image_path=image_path)
    top = matches[0]
    social_count = sum(1 for m in matches if m["is_social"])
    print(f"      -> {len(matches)} visual matches found "
          f"({social_count} on known social platforms)")
    print(f"      -> top match: {top['title']!r} -> {top['link']}")
    print(f"      -> thumbnail: {top.get('thumbnail', 'n/a')}")

    timestamp = datetime.now(timezone.utc).isoformat()
    record = build_match_record(image_path, face_result, top, timestamp)
    r_hash = record_hash(record)
    print(f"      Record hash (SHA-256): {r_hash}")

    print(f"\n[3/3] Writing record hash to Polygon Amoy testnet{' — ' + tag if tag else ''}...")
    chain_result = upload_hash_to_chain(r_hash)
    print(f"      -> tx: {chain_result['tx_hash']}")
    print(f"      -> explorer: {chain_result['explorer_url']}")
    print(f"      -> block: {chain_result['block_number']} (status={chain_result['status']})")

    result = {
        "image_path": image_path,
        "face_result_summary": {
            "detector": face_result["detector"],
            "model": face_result["model"],
            "face_confidence": face_result["face_confidence"],
            "facial_area": face_result.get("facial_area"),
        },
        "matches_found": len(matches),
        "top_match": top,
        "record": record,
        "record_hash": r_hash,
        "chain": chain_result,
    }

    record_path = os.path.join(out_dir, f"record{suffix}.json")
    result_path = os.path.join(out_dir, f"pipeline_result{suffix}.json")
    all_matches_path = os.path.join(out_dir, f"all_matches{suffix}.json")
    with open(record_path, "w") as f:
        json.dump(record, f, indent=2)
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    with open(all_matches_path, "w") as f:
        json.dump(matches, f, indent=2)

    print(f"\n      Saved record -> {record_path}")
    print(f"      Saved full result -> {result_path}")
    print(f"      Saved ALL {len(matches)} matches -> {all_matches_path}")
    print(f"      Re-verify: python src/verify.py {record_path} {chain_result['tx_hash']}")
    return result


def run_pipeline(image_path: str, out_dir: str = "output", multi_face: bool = False,
                  compare_path: str = None) -> dict:
    os.makedirs(out_dir, exist_ok=True)

    if multi_face:
        print(f"[1/3] Face detection + encoding (ALL faces) on: {image_path}")
        faces = detect_and_encode_all(image_path)
        print(f"      -> {len(faces)} face(s) detected")
        results = []
        for i, face_result in enumerate(faces):
            print(f"\n--- Face {i+1}/{len(faces)} "
                  f"(confidence={face_result['face_confidence']}, "
                  f"embedding_len={len(face_result['embedding'])}) ---")
            results.append(_anchor_one_face(image_path, face_result, out_dir, tag=f"face{i+1}"))
        return {"faces": results}

    print(f"[1/3] Face detection + encoding on: {image_path}")
    face_result = detect_and_encode(image_path)
    print(f"      -> face detected (confidence={face_result['face_confidence']}, "
          f"embedding_len={len(face_result['embedding'])})")

    sim_result = None
    if compare_path:
        print(f"\n[bonus] Comparing this face's embedding against: {compare_path}")
        other_face = detect_and_encode(compare_path)
        sim_result = compare_faces(face_result["embedding"], other_face["embedding"])
        verdict = "SAME PERSON" if sim_result["same_person"] else "DIFFERENT PEOPLE"
        print(f"        -> {verdict} (cosine similarity: {sim_result['similarity']:.4f}, "
              f"threshold: {sim_result['threshold']})")

    result = _anchor_one_face(image_path, face_result, out_dir)
    if sim_result:
        result["similarity_check"] = {"compared_with": compare_path, **sim_result}
    return result


def main():
    parser = argparse.ArgumentParser(description="Face ID + Blockchain Verification pipeline")
    parser.add_argument("--image", required=True, help="Path to the input face image")
    parser.add_argument("--out", default="output", help="Output directory (default: output/)")
    parser.add_argument("--multi-face", action="store_true",
                         help="Detect and anchor EVERY face in the image, not just the largest")
    parser.add_argument("--compare", default=None,
                         help="Optional second image to compare the primary face's embedding against")
    args = parser.parse_args()

    try:
        run_pipeline(args.image, out_dir=args.out, multi_face=args.multi_face,
                     compare_path=args.compare)
    except Exception as e:
        print(f"\nPipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
