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


def _concatenate_reference_images(paths, cell_size=256, max_cols=3,
                                   labels=None):
    """Concatenate multiple images into a single labeled reference sheet.

    Arranges images in a grid so the model sees all references at once
    instead of processing them as separate inputs (which can overwhelm it).
    Each cell can have a label drawn at the top for identification.

    Args:
        paths: List of image file paths.
        cell_size: Size of each grid cell in pixels.
        max_cols: Maximum columns in the grid.
        labels: Optional list of label strings, one per path.
    """
    if Image is None:
        raise RuntimeError("Pillow required for --reference-images. "
                           "Install: pip install Pillow")
    from PIL import ImageDraw, ImageFont

    imgs = []
    valid_labels = []
    for i, p in enumerate(paths):
        if not os.path.exists(p):
            continue
        img = Image.open(p)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        imgs.append(img)
        if labels and i < len(labels):
            valid_labels.append(labels[i])
        else:
            valid_labels.append(None)

    if not imgs:
        return None

    if len(imgs) == 1:
        # Single image — add label if present, then return
        img = _resize_image(imgs[0], cell_size)
        if valid_labels[0]:
            draw = ImageDraw.Draw(img)
            font, cjk_ok = _get_label_font(16)
            _draw_label(draw, valid_labels[0], img.size[0], font,
                        cjk_supported=cjk_ok)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    # Reserve space for label text at top of each cell
    label_h = 24
    img_area = cell_size - label_h

    # Calculate grid layout
    n = len(imgs)
    cols = min(n, max_cols)
    rows = (n + cols - 1) // cols

    # Create canvas with white background
    canvas_w = cols * cell_size
    canvas_h = rows * cell_size
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font, cjk_ok = _get_label_font(14)

    # Paste each image centered in its cell, with label
    for i, img in enumerate(imgs):
        row = i // cols
        col = i % cols
        cell_x = col * cell_size
        cell_y = row * cell_size

        # Draw label at top of cell
        if valid_labels[i]:
            _draw_label(draw, valid_labels[i], cell_size,
                        font, cjk_supported=cjk_ok,
                        offset_x=cell_x, offset_y=cell_y)

        # Resize image to fit below label
        img = _resize_image(img, img_area)
        x = cell_x + (cell_size - img.size[0]) // 2
        y = cell_y + label_h + (img_area - img.size[1]) // 2
        canvas.paste(img, (x, y))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _get_label_font(size=14):
    """Try to load a font that supports CJK characters."""
    from PIL import ImageFont
    # Common CJK font paths on Linux/Mac/Windows
    cjk_fonts = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    # Also check user-local fonts
    import os.path
    home = os.path.expanduser("~")
    cjk_fonts.append(os.path.join(home, ".local/share/fonts/NotoSansSC.ttf"))

    for path in cjk_fonts:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size), True
            except Exception:
                continue
    # Fallback: use DejaVu or default (no CJK support)
    fallback_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    ]
    for path in fallback_fonts:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size), False
            except Exception:
                continue
    return ImageFont.load_default(), False


def _sanitize_label(text, cjk_supported):
    """If CJK font not available, strip non-ASCII characters."""
    if cjk_supported:
        return text
    # Keep ASCII and common punctuation, replace CJK with nothing
    clean = ""
    for ch in text:
        if ord(ch) < 128:
            clean += ch
    return clean.strip() or text  # fallback to original if all stripped


def _draw_label(draw, text, cell_width, font, cjk_supported=True,
                offset_x=0, offset_y=0):
    """Draw a centered label with dark background strip."""
    text = _sanitize_label(text, cjk_supported)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    # Dark semi-transparent strip
    strip_h = th + 6
    draw.rectangle(
        [offset_x, offset_y, offset_x + cell_width, offset_y + strip_h],
        fill=(40, 40, 40),
    )
    # Centered white text
    tx = offset_x + (cell_width - tw) // 2
    ty = offset_y + 3
    draw.text((tx, ty), text, fill=(255, 255, 255), font=font)


def _quality_check(image_path, prompt, api_key, base_url, model):
    """Send generated image to the model for quality evaluation.

    Returns (passed: bool, reason: str).
    """
    data_uri = _image_to_base64(image_path, max_size=512)
    check_prompt = (
        "You are a quality checker for AI-generated manga/slide images. "
        "Evaluate this image against the intended content below. "
        "Check for: 1) Strange/deformed characters or body parts, "
        "2) Incoherent text or garbled characters, "
        "3) Major layout problems, 4) Content not matching the description. "
        "Respond with EXACTLY one line: 'PASS' if acceptable, or "
        "'FAIL: <brief reason>' if there are serious flaws. "
        "Minor imperfections are OK — only flag serious issues.\n\n"
        f"Intended content: {prompt}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": check_prompt},
            ]
        }],
    }

    url = f"{base_url}/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code != 200:
            print(f"  QC: HTTP {r.status_code}, skipping check")
            return True, "check unavailable"

        resp = r.json()
        text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = text.strip()
        print(f"  QC: {text[:100]}")

        if text.upper().startswith("PASS"):
            return True, text
        elif text.upper().startswith("FAIL"):
            reason = text[5:].strip(": ")
            return False, reason
        else:
            return True, text
    except Exception as e:
        print(f"  QC error: {e}, skipping")
        return True, str(e)


def _refine_image(image_path, prompt, reason, output,
                  reference_data_uri, api_key, base_url, model):
    """Regenerate an image using the flawed version as context."""
    flawed_uri = _image_to_base64(image_path, max_size=512)
    refine_prompt = (
        f"The previous attempt had issues: {reason}. "
        f"Please regenerate and fix these problems. "
        f"Original request: {prompt}"
    )

    content_parts = []
    if reference_data_uri:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": reference_data_uri}
        })
    content_parts.append({
        "type": "image_url",
        "image_url": {"url": flawed_uri}
    })
    content_parts.append({"type": "text", "text": refine_prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content_parts}],
        "modalities": ["image", "text"],
    }

    url = f"{base_url}/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=300)
        if r.status_code != 200:
            print(f"  Refine: HTTP {r.status_code}")
            return False

        resp = r.json()
        text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")

        url_match = re.search(r'!\[.*?\]\((https?://[^\s\)]+)\)', text)
        if not url_match:
            url_match = re.search(
                r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif))',
                text, re.IGNORECASE,
            )
        if not url_match:
            print(f"  Refine: no image in response")
            return False

        img_url = url_match.group(1)
        img_resp = requests.get(img_url, timeout=60)
        if img_resp.status_code == 200 and len(img_resp.content) > 1000:
            with open(output, "wb") as f:
                f.write(img_resp.content)
            print(f"  Refine: OK ({len(img_resp.content):,} bytes)")
            return True
        return False
    except Exception as e:
        print(f"  Refine error: {e}")
        return False


def generate_slide(prompt, output, retries=3, api_key=None,
                   base_url=None, model=None, reference_images=None,
                   reference_labels=None, quality_check=False,
                   max_refine=2):
    """Generate a slide image and save to output path.

    If quality_check=True, evaluates the generated image and refines
    up to max_refine times if serious flaws are detected.

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

    # Build content: concatenated reference sheet + text prompt
    if reference_images:
        ref_data_uri = _concatenate_reference_images(
            reference_images, labels=reference_labels
        )
        if ref_data_uri:
            msg_content = [
                {"type": "image_url", "image_url": {"url": ref_data_uri}},
                {"type": "text", "text": prompt},
            ]
        else:
            msg_content = prompt
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

                # Quality check + refine loop
                if quality_check:
                    ref_data_uri = None
                    if reference_images:
                        ref_data_uri = _concatenate_reference_images(
                            reference_images, labels=reference_labels
                        )
                    for qc_round in range(max_refine):
                        passed, reason = _quality_check(
                            output, prompt, api_key, base_url, model
                        )
                        if passed:
                            print(f"  QC passed")
                            break
                        print(f"  QC failed ({qc_round+1}/{max_refine}): "
                              f"{reason}")
                        refined = _refine_image(
                            output, prompt, reason, output,
                            ref_data_uri, api_key, base_url, model,
                        )
                        if not refined:
                            print(f"  Refine failed, keeping current")
                            break
                    else:
                        print(f"  Max refine attempts reached, keeping best")

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
