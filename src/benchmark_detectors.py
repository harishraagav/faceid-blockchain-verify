"""
benchmark_detectors.py
Runs the same image through several DeepFace detector backends and
reports confidence + wall-clock time for each, so the README can show a
real, measured comparison instead of an unsubstantiated claim about
which backend is "best."

Not part of the main pipeline — this is a one-off analysis tool.
"""

import sys
import time
import json

from face_id import detect_and_encode

# A representative spread: a fast classic (opencv), a widely-used deep
# detector (mtcnn), and the pipeline's default (retinaface).
BACKENDS = ["opencv", "mtcnn", "retinaface"]


def benchmark(image_path: str, backends: list = None) -> list:
    backends = backends or BACKENDS
    results = []
    for backend in backends:
        start = time.perf_counter()
        try:
            face = detect_and_encode(image_path, detector_backend=backend)
            elapsed = time.perf_counter() - start
            results.append({
                "backend": backend,
                "success": True,
                "confidence": face["face_confidence"],
                "seconds": round(elapsed, 3),
            })
        except Exception as e:
            elapsed = time.perf_counter() - start
            results.append({
                "backend": backend,
                "success": False,
                "error": str(e),
                "seconds": round(elapsed, 3),
            })
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python benchmark_detectors.py <image_path>")
        sys.exit(1)

    results = benchmark(sys.argv[1])
    print(json.dumps(results, indent=2))

    print(f"\n{'Backend':<12} {'Success':<9} {'Confidence':<12} {'Time (s)':<10}")
    print("-" * 45)
    for r in results:
        conf = f"{r['confidence']:.3f}" if r.get("success") else "—"
        print(f"{r['backend']:<12} {str(r['success']):<9} {conf:<12} {r['seconds']:<10}")
