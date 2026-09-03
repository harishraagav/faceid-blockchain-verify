"""
face_id.py
Stage 1 of the pipeline: detect a face in an input image and compute its
encoding (a numerical embedding representing facial identity).

Uses DeepFace (https://github.com/serengil/deepface), which wraps several
detector backends (RetinaFace, MTCNN, OpenCV, etc.) and embedding models
(Facenet512, ArcFace, VGG-Face, etc.) behind one API. Chosen over
`face_recognition`/dlib because it installs cleanly via pip on Windows
without needing a C++ build toolchain for dlib.
"""

import os
from deepface import DeepFace


def detect_and_encode(image_path: str, detector_backend: str = "retinaface",
                       model_name: str = "Facenet512") -> dict:
    """
    Detect the primary (largest) face in `image_path` and return its
    encoding. For multi-face photos, use detect_and_encode_all() instead.

    Args:
        image_path: path to a local image file containing at least one face.
        detector_backend: DeepFace detector to use (retinaface, mtcnn,
            opencv, ssd, dlib, mediapipe, yolov8, ...).
        model_name: DeepFace embedding model (Facenet512, ArcFace, VGG-Face,
            Facenet, OpenFace, DeepFace, DeepID, SFace, ...).

    Returns:
        {
            "embedding": [float, ...],   # the face encoding vector
            "facial_area": {...},        # bounding box + landmarks (if any)
            "face_confidence": float,    # detector confidence
            "model": model_name,
            "detector": detector_backend,
        }

    Raises:
        FileNotFoundError: if image_path does not exist.
        ValueError: if no face is detected in the image.
    """
    faces = detect_and_encode_all(image_path, detector_backend, model_name)
    return max(faces, key=lambda r: _face_area(r.get("facial_area", {})))


def detect_and_encode_all(image_path: str, detector_backend: str = "retinaface",
                           model_name: str = "Facenet512") -> list:
    """
    Detect and encode EVERY face in `image_path` (group-photo support),
    not just the largest one. Returns a list of face dicts, each shaped
    like the single-face return value of detect_and_encode(), ordered
    largest-bounding-box-first.

    Raises:
        FileNotFoundError: if image_path does not exist.
        ValueError: if no face is detected in the image.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        results = DeepFace.represent(
            img_path=image_path,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=True,
        )
    except ValueError as e:
        raise ValueError(f"No face detected in {image_path}: {e}") from e

    if not results:
        raise ValueError(f"No face detected in {image_path}")

    faces = [
        {
            "embedding": face["embedding"],
            "facial_area": face.get("facial_area"),
            "face_confidence": face.get("face_confidence"),
            "model": model_name,
            "detector": detector_backend,
        }
        for face in results
    ]
    faces.sort(key=lambda r: _face_area(r.get("facial_area", {})), reverse=True)
    return faces


def _face_area(box: dict) -> int:
    return box.get("w", 0) * box.get("h", 0)


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python face_id.py <image_path> [--all]")
        sys.exit(1)

    if "--all" in sys.argv:
        faces = detect_and_encode_all(sys.argv[1])
        print(f"Detected {len(faces)} face(s).")
        for i, f in enumerate(faces):
            print(f"  Face {i+1}: confidence={f['face_confidence']}, "
                  f"embedding_len={len(f['embedding'])}, box={json.dumps(f['facial_area'])}")
    else:
        result = detect_and_encode(sys.argv[1])
        print(f"Detected face — confidence: {result['face_confidence']}")
        print(f"Embedding length: {len(result['embedding'])}")
        print(f"Bounding box: {json.dumps(result['facial_area'])}")
