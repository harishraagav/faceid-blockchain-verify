"""
reverse_search.py
Stage 2 of the pipeline: genuine reverse-image search using SerpApi's
Google Lens engine (https://serpapi.com/google-lens-api).

Two ways to search:
  1. image_url  — a publicly reachable URL to the image (fastest, no upload).
  2. image_path — a local file. We first POST it to SerpApi's /image
     upload endpoint to get an `image_id`, then search with that id.
     NOTE: SerpApi's upload endpoint caps files at 500 KB — downscale/
     compress large photos before uploading (see README).

Either path calls the *real* Google Lens engine live — there is no
hardcoded/pre-picked result here; whatever Google Lens returns for this
specific image at request time is what gets used downstream.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
SERPAPI_IMAGE_UPLOAD_URL = "https://serpapi.com/image"

SOCIAL_DOMAINS = [
    "instagram.com", "twitter.com", "x.com", "facebook.com",
    "linkedin.com", "pinterest.com", "reddit.com", "tiktok.com",
    "tumblr.com", "threads.net", "vk.com",
]


def _upload_image(image_path: str, api_key: str) -> str:
    """Upload a local image to SerpApi and return its image_id."""
    size = os.path.getsize(image_path)
    if size > 500_000:
        raise ValueError(
            f"{image_path} is {size/1000:.0f} KB — SerpApi's image upload "
            "endpoint caps files at 500 KB. Downscale/compress the image "
            "first (see README 'Known limitations')."
        )

    with open(image_path, "rb") as f:
        resp = requests.post(
            SERPAPI_IMAGE_UPLOAD_URL,
            params={"api_key": api_key},
            files={"image": f},
            timeout=60,
        )
    resp.raise_for_status()
    data = resp.json()
    image_id = data.get("image_id")
    if not image_id:
        raise RuntimeError(f"SerpApi image upload did not return an image_id: {data}")
    return image_id


def reverse_image_search(image_path: str = None, image_url: str = None,
                          api_key: str = None) -> list:
    """
    Perform a live reverse-image search via SerpApi's Google Lens engine.

    Provide exactly one of image_path (local file) or image_url (publicly
    reachable URL).

    Returns a list of match dicts, social-media matches sorted first:
        [{"title": ..., "link": ..., "source": ..., "thumbnail": ...,
          "is_social": bool}, ...]

    Raises RuntimeError if SerpApi returns no visual matches at all.
    """
    api_key = api_key or os.environ.get("SERPAPI_KEY")
    if not api_key:
        raise EnvironmentError("SERPAPI_KEY not set (env var or api_key param).")
    if not image_url and not image_path:
        raise ValueError("Provide image_path or image_url.")
    if image_url and image_path:
        raise ValueError("Provide only one of image_path or image_url, not both.")

    params = {"engine": "google_lens", "api_key": api_key, "type": "visual_matches"}

    if image_url:
        params["url"] = image_url
    else:
        params["image_id"] = _upload_image(image_path, api_key)

    resp = requests.get(SERPAPI_SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"SerpApi error: {data['error']}")

    visual_matches = data.get("visual_matches", [])
    if not visual_matches:
        raise RuntimeError(
            "No visual matches found for this image. Try a different/"
            "clearer photo, or one more likely to already appear online."
        )

    matches = []
    for m in visual_matches:
        link = m.get("link", "") or ""
        is_social = any(domain in link for domain in SOCIAL_DOMAINS)
        matches.append({
            "title": m.get("title"),
            "link": link,
            "source": m.get("source"),
            "thumbnail": m.get("thumbnail"),
            "is_social": is_social,
        })

    matches.sort(key=lambda x: not x["is_social"])
    return matches


def best_match(image_path: str = None, image_url: str = None, api_key: str = None) -> dict:
    """Convenience wrapper: return just the top-ranked match."""
    matches = reverse_image_search(image_path=image_path, image_url=image_url, api_key=api_key)
    return matches[0]


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python reverse_search.py <image_path>")
        sys.exit(1)

    results = reverse_image_search(image_path=sys.argv[1])
    print(json.dumps(results[:5], indent=2))
