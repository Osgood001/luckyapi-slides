#!/usr/bin/env python3
"""Generate a reference image for the settings (设定集).

Calls the LuckyAPI to generate a reference image, resizes it to a
reasonable size for use as multi-modal input, and saves it to the
appropriate settings subfolder.

Usage:
    # Generate art style reference
    python generate_reference.py "Dark navy background, cyan accents, minimal" \
        -o settings/art_style/palette_ref.png

    # Generate character reference
    python generate_reference.py "Young woman, short black hair, lab coat" \
        -o settings/characters/hero/front.png

    # With existing reference images for consistency
    python generate_reference.py "Same character but angry expression" \
        -o settings/characters/hero/angry.png \
        --reference-images settings/characters/hero/front.png

Options:
    --max-size N    Max dimension for saved image (default: 512)
    --retries N     Max retry attempts (default: 3)
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
    print("Error: Pillow not found. Install: pip install Pillow")
    sys.exit(1)


def resize_image(img, max_size=512):
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


def image_to_base64(path, max_size=512):
    """Read image, resize, return base64 data URI."""
    img = Image.open(path)
    img = resize_image(img, max_size)
    if img.mode == "RGBA":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def generate_reference(prompt, output, reference_images=None,
                       max_size=512, retries=3):
    """Generate a reference image and save to output path."""
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("Error: No API key. Set ANTHROPIC_AUTH_TOKEN.")
        return False

    base_url = os.getenv("LUCKYAPI_BASE_URL", "https://luckyapi.chat/v1")
    model = os.getenv("LUCKYAPI_MODEL",
                       "(按次)gemini-3-pro-image-preview")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Build content: text + optional reference images
    content_parts = []
    if reference_images:
        for ref_path in reference_images:
            if not os.path.exists(ref_path):
                print(f"  Warning: reference image not found: {ref_path}")
                continue
            data_uri = image_to_base64(ref_path, max_size)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri}
            })
    content_parts.append({"type": "text", "text": prompt})

    # Use multi-part if we have images, plain string otherwise
    if len(content_parts) == 1:
        msg_content = prompt
    else:
        msg_content = content_parts

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": msg_content}],
        "modalities": ["image", "text"],
    }

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            print(f"  Attempt {attempt}/{retries}...")
            r = requests.post(url, headers=headers, json=payload,
                              timeout=300)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}, retrying...")
                time.sleep(5)
                continue

            resp = r.json()
            msg = resp.get("choices", [{}])[0].get("message", {})
            text = msg.get("content", "")

            # Extract image URL
            url_match = re.search(
                r'!\[.*?\]\((https?://[^\s\)]+)\)', text
            )
            if not url_match:
                url_match = re.search(
                    r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif))',
                    text, re.IGNORECASE,
                )
            if not url_match:
                print(f"  No image URL in response, retrying...")
                time.sleep(3)
                continue

            img_url = url_match.group(1)
            img_resp = requests.get(img_url, timeout=60)
            if img_resp.status_code != 200 or len(img_resp.content) < 1000:
                print(f"  Download failed: HTTP {img_resp.status_code}")
                time.sleep(3)
                continue

            # Resize and save
            img = Image.open(io.BytesIO(img_resp.content))
            img = resize_image(img, max_size)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(output, format="PNG")
            print(f"  OK -> {output} ({img.size[0]}x{img.size[1]})")
            return True

        except requests.exceptions.Timeout:
            print(f"  Timeout, retrying...")
            time.sleep(5)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(3)

    print(f"  FAILED after {retries} attempts")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate a reference image for settings"
    )
    parser.add_argument("prompt", help="Description of the reference image")
    parser.add_argument("-o", "--output", required=True,
                        help="Output image path")
    parser.add_argument("--reference-images", nargs="*", default=None,
                        help="Existing reference images for consistency")
    parser.add_argument("--max-size", type=int, default=512,
                        help="Max dimension for saved image (default: 512)")
    parser.add_argument("--retries", type=int, default=3,
                        help="Max retries (default: 3)")
    args = parser.parse_args()

    ok = generate_reference(
        args.prompt, args.output,
        reference_images=args.reference_images,
        max_size=args.max_size,
        retries=args.retries,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
