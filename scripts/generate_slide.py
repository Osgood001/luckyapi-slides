#!/usr/bin/env python3
"""Generate a single presentation slide image via LuckyAPI.

Uses (按次)gemini-3-pro-image-preview model to generate slide images.
Supports retry on failure, skips existing files, and accepts reference
images for visual consistency (设定集).

Usage:
    python generate_slide.py "Slide description" -o slides/01_title.png
    python generate_slide.py "Slide description" -o slide.png --retries 5
    python generate_slide.py "Slide description" -o slide.png --style "dark blue bg, white text"
    python generate_slide.py "Slide description" -o slide.png \
        --reference-images settings/art_style/ref.png settings/characters/hero/front.png

Environment:
    ANTHROPIC_AUTH_TOKEN   API key for LuckyAPI (required)
    LUCKYAPI_BASE_URL      Base URL (default: https://luckyapi.chat/v1)
    LUCKYAPI_MODEL         Model name (default: (按次)gemini-3-pro-image-preview)
"""
import argparse
import base64
import io
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    print("Error: requests not found. Install: pip install requests")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    Image = None  # Optional: only needed for --reference-images


def _resize_image(img, max_size=512):
    """Resize image so longest side is max_size."""
    w, h = img.size
    if max(w, h) <= max_size:
        return img
    if w >= h:
        new_w = max_size
        new_h = int(h * max_size / w)
    else:
        new_h = max_size
        new_w = int(w * max_size / h)
    return img.resize((new_w, new_h), Image.LANCZOS)


def _image_to_base64(path, max_size=512):
    """Read image, resize, return base64 data URI."""
    if Image is None:
        raise RuntimeError("Pillow required for --reference-images. "
                           "Install: pip install Pillow")
    img = Image.open(path)
    img = _resize_image(img, max_size)
    if img.mode == "RGBA":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def generate_slide(prompt, output, retries=3, api_key=None,
                   base_url=None, model=None, reference_images=None):
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

    # Build content: reference images + text prompt
    if reference_images:
        content_parts = []
        for ref_path in reference_images:
            if not os.path.exists(ref_path):
                print(f"  Warning: reference image not found: {ref_path}")
                continue
            data_uri = _image_to_base64(ref_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri}
            })
        content_parts.append({"type": "text", "text": prompt})
        msg_content = content_parts
    else:
        msg_content = prompt

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": msg_content}],
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
    parser.add_argument("--reference-images", nargs="*", default=None,
                        help="Reference image paths for visual consistency")
    args = parser.parse_args()

    prompt = args.prompt
    if args.style:
        prompt = f"{args.style} {prompt}"

    ok = generate_slide(prompt, args.output, retries=args.retries,
                        reference_images=args.reference_images)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
