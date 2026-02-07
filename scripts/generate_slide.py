#!/usr/bin/env python3
"""Generate a single presentation slide image via LuckyAPI.

Uses (按次)gemini-3-pro-image-preview model to generate slide images.
Supports retry on failure and skips existing files.

Usage:
    python generate_slide.py "Slide description" -o slides/01_title.png
    python generate_slide.py "Slide description" -o slide.png --retries 5
    python generate_slide.py "Slide description" -o slide.png --style "dark blue bg, white text"

Environment:
    ANTHROPIC_AUTH_TOKEN   API key for LuckyAPI (required)
    LUCKYAPI_BASE_URL      Base URL (default: https://luckyapi.chat/v1)
    LUCKYAPI_MODEL         Model name (default: (按次)gemini-3-pro-image-preview)
"""
import argparse
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    print("Error: requests not found. Install: pip install requests")
    sys.exit(1)


def generate_slide(prompt, output, retries=3, api_key=None, base_url=None, model=None):
    """Generate a slide image and save to output path.

    Returns True on success, False on failure.
    """
    if os.path.exists(output) and os.path.getsize(output) > 1000:
        print(f"  [SKIP] {output} already exists")
        return True

    api_key = api_key or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("Error: No API key. Set ANTHROPIC_AUTH_TOKEN.")
        return False

    base_url = base_url or os.getenv("LUCKYAPI_BASE_URL", "https://luckyapi.chat/v1")
    model = model or os.getenv("LUCKYAPI_MODEL", "(按次)gemini-3-pro-image-preview")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            print(f"  Attempt {attempt}/{retries}...")
            r = requests.post(url, headers=headers, json=payload, timeout=300)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}, retrying...")
                time.sleep(5)
                continue

            resp = r.json()
            msg = resp.get("choices", [{}])[0].get("message", {})
            content = msg.get("content", "")

            # Extract image URL from markdown ![...](url) or bare URL
            url_match = re.search(r'!\[.*?\]\((https?://[^\s\)]+)\)', content)
            if not url_match:
                url_match = re.search(
                    r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif))',
                    content, re.IGNORECASE,
                )
            if not url_match:
                print(f"  No image URL in response, retrying...")
                time.sleep(3)
                continue

            img_url = url_match.group(1)
            img_resp = requests.get(img_url, timeout=60)
            if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                with open(output, "wb") as f:
                    f.write(img_resp.content)
                print(f"  OK ({len(img_resp.content):,} bytes) -> {output}")
                return True
            else:
                print(f"  Download failed: HTTP {img_resp.status_code}")
                time.sleep(3)
        except requests.exceptions.Timeout:
            print(f"  Timeout, retrying...")
            time.sleep(5)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(3)

    print(f"  FAILED after {retries} attempts")
    return False


def main():
    parser = argparse.ArgumentParser(description="Generate a slide image via LuckyAPI")
    parser.add_argument("prompt", help="Slide description")
    parser.add_argument("-o", "--output", required=True, help="Output image path")
    parser.add_argument("--retries", type=int, default=3, help="Max retries (default: 3)")
    parser.add_argument("--style", default="", help="Style prefix to prepend to prompt")
    args = parser.parse_args()

    prompt = args.prompt
    if args.style:
        prompt = f"{args.style} {prompt}"

    ok = generate_slide(prompt, args.output, retries=args.retries)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
