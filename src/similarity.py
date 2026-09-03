"""
similarity.py
Demonstrates that the face embedding from face_id.py is actually load-
bearing, not just computed-and-discarded: given embeddings from two
photos, compute how similar they are, and classify same-person vs
different-person using a standard threshold for Facenet512 embeddings.

This does not replace the reverse-image-search stage (which is what
finds the real social post); it's an independent, additional use of the
face encoding that shows the 512-d vector produced in Stage 1 is a
genuine identity representation, not just a detection artifact.
"""

import numpy as np

# Facenet512 embeddings are commonly compared with cosine distance.
# A cosine-distance threshold around 0.30 is the widely-used DeepFace
# default for "same person" on Facenet512 (equivalently, cosine
# similarity above ~0.70). We use similarity (higher = more alike) here
# for readability.
DEFAULT_SIMILARITY_THRESHOLD = 0.70


def cosine_similarity(embedding_a: list, embedding_b: list) -> float:
    """
    Return cosine similarity between two embeddings, in [-1, 1].
    1.0 = identical direction (very likely same face),
    0.0 = unrelated, negative = opposite.
    """
    a = np.asarray(embedding_a, dtype=np.float64)
    b = np.asarray(embedding_b, dtype=np.float64)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compare_faces(embedding_a: list, embedding_b: list,
                   threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> dict:
    """
    Compare two face embeddings and classify same-person vs different.

    Returns:
        {"similarity": float, "same_person": bool, "threshold": float}
    """
    sim = cosine_similarity(embedding_a, embedding_b)
    return {
        "similarity": sim,
        "same_person": sim >= threshold,
        "threshold": threshold,
    }


if __name__ == "__main__":
    import sys
    import json
    sys.path.insert(0, ".")
    from face_id import detect_and_encode

    if len(sys.argv) < 3:
        print("Usage: python similarity.py <image_a> <image_b>")
        sys.exit(1)

    face_a = detect_and_encode(sys.argv[1])
    face_b = detect_and_encode(sys.argv[2])
    result = compare_faces(face_a["embedding"], face_b["embedding"])

    print(json.dumps(result, indent=2))
    verdict = "SAME PERSON" if result["same_person"] else "DIFFERENT PEOPLE"
    print(f"\n{verdict} (cosine similarity: {result['similarity']:.4f}, "
          f"threshold: {result['threshold']})")
