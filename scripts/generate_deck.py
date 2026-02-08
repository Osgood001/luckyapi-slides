#!/usr/bin/env python3
"""Orchestrate full deck generation from a slide plan.

Reads slide_plan.json and settings/settings.json, generates all slides
with reference images for visual consistency, and combines into PDF.

Supports parallel generation via ThreadPoolExecutor.

Usage:
    python generate_deck.py slide_plan.json
    python generate_deck.py slide_plan.json --workers 4
    python generate_deck.py slide_plan.json --output presentation.pdf

slide_plan.json format:
{
  "style_prefix": "16:9 slide, dark navy bg, cyan accents",
  "slides": [
    {
      "filename": "01_title.png",
      "prompt": "Title slide: 'ML 101'",
      "settings": ["art_style", "characters.hero"]
    }
  ]
}
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_slide import generate_slide
from slides_to_pdf import combine_images_to_pdf


def resolve_settings_images(settings_keys, settings, base_dir="."):
    """Resolve setting keys like 'art_style', 'characters.hero' to image paths and labels."""
    images = []
    labels = []
    for key in settings_keys:
        parts = key.split(".", 1)
        category = parts[0]

        if category == "art_style":
            desc = settings.get("art_style", {}).get("description", "")
            label = f"Art Style: {desc[:30]}" if desc else "Art Style"
            for p in settings.get("art_style", {}).get("images", []):
                full = os.path.join(base_dir, p)
                if os.path.exists(full):
                    images.append(full)
                    labels.append(label)
        elif len(parts) == 2:
            name = parts[1]
            entry = settings.get(category, {}).get(name, {})
            desc = entry.get("description", "")
            label = f"{name}: {desc[:30]}" if desc else name
            for p in entry.get("images", []):
                full = os.path.join(base_dir, p)
                if os.path.exists(full):
                    images.append(full)
                    labels.append(label)
        else:
            # Category-level: include all images from all entries
            cat_data = settings.get(category, {})
            for name, entry in cat_data.items():
                if isinstance(entry, dict):
                    desc = entry.get("description", "")
                    label = f"{name}: {desc[:30]}" if desc else name
                    for p in entry.get("images", []):
                        full = os.path.join(base_dir, p)
                        if os.path.exists(full):
                            images.append(full)
                            labels.append(label)
    return images, labels


def resolve_settings_descriptions(settings_keys, settings):
    """Resolve setting keys to text descriptions."""
    descs = []
    for key in settings_keys:
        parts = key.split(".", 1)
        category = parts[0]

        if category == "art_style":
            d = settings.get("art_style", {}).get("description", "")
            if d:
                descs.append(f"[Style: {d}]")
        elif len(parts) == 2:
            name = parts[1]
            entry = settings.get(category, {}).get(name, {})
            d = entry.get("description", "")
            if d:
                descs.append(f"[{category}/{name}: {d}]")
    return " ".join(descs)


def generate_one_slide(slide_info, style_prefix, settings,
                       slides_dir, base_dir, quality_check=False):
    """Generate a single slide with settings context."""
    filename = slide_info["filename"]
    prompt = slide_info["prompt"]
    settings_keys = slide_info.get("settings", ["art_style"])
    output = os.path.join(slides_dir, filename)

    # Build full prompt with style prefix and settings descriptions
    desc_text = resolve_settings_descriptions(settings_keys, settings)
    full_prompt = ""
    if style_prefix:
        full_prompt += style_prefix + " "
    if desc_text:
        full_prompt += desc_text + " "
    full_prompt += prompt

    # Resolve reference images and labels
    ref_images, ref_labels = resolve_settings_images(
        settings_keys, settings, base_dir
    )

    print(f"\n[{filename}] Generating...")
    if ref_images:
        print(f"  Reference images: {len(ref_images)} (concatenated)")

    ok = generate_slide(
        full_prompt, output, retries=3,
        reference_images=ref_images if ref_images else None,
        reference_labels=ref_labels if ref_labels else None,
        quality_check=quality_check,
    )
    return filename, ok


def run_deck(plan_path, output_pdf=None, slides_dir=None,
             workers=3, base_dir=None, quality_check=False):
    """Run the full deck generation pipeline."""
    with open(plan_path) as f:
        plan = json.load(f)

    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(plan_path))
        # If plan is in project root, use that
        if not base_dir:
            base_dir = "."

    settings_file = os.path.join(base_dir, "settings", "settings.json")
    if os.path.exists(settings_file):
        with open(settings_file) as f:
            settings = json.load(f)
        print(f"Loaded settings from {settings_file}")
    else:
        settings = {}
        print("No settings.json found, proceeding without settings")

    style_prefix = plan.get("style_prefix", "")
    slides = plan.get("slides", [])

    if not slides:
        print("Error: No slides in plan")
        return False

    if slides_dir is None:
        slides_dir = os.path.join(base_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)

    if output_pdf is None:
        output_pdf = os.path.join(base_dir, "output", "presentation.pdf")
    os.makedirs(os.path.dirname(output_pdf) or ".", exist_ok=True)

    print(f"Generating {len(slides)} slides (workers={workers})...")

    # Generate slides in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for slide_info in slides:
            future = executor.submit(
                generate_one_slide, slide_info, style_prefix,
                settings, slides_dir, base_dir, quality_check,
            )
            futures[future] = slide_info["filename"]

        for future in as_completed(futures):
            filename = futures[future]
            try:
                fname, ok = future.result()
                results[fname] = ok
                status = "OK" if ok else "FAILED"
                print(f"  [{fname}] {status}")
            except Exception as e:
                results[filename] = False
                print(f"  [{filename}] ERROR: {e}")

    # Report
    succeeded = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    print(f"\nGeneration complete: {succeeded} OK, {failed} failed")

    if failed > 0:
        print("Warning: Some slides failed. PDF will be created with "
              "available slides only.")

    # Collect generated slide files in order
    slide_files = []
    for slide_info in slides:
        path = Path(os.path.join(slides_dir, slide_info["filename"]))
        if path.exists() and path.stat().st_size > 1000:
            slide_files.append(path)

    if not slide_files:
        print("Error: No slide images available for PDF")
        return False

    # Combine into PDF
    print(f"\nCombining {len(slide_files)} slides into PDF...")
    ok = combine_images_to_pdf(
        slide_files, Path(output_pdf), dpi=150, verbose=True
    )
    if ok:
        print(f"\nDeck complete: {output_pdf}")
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Generate a full slide deck from a plan"
    )
    parser.add_argument("plan", help="Path to slide_plan.json")
    parser.add_argument("--output", "-o", default=None,
                        help="Output PDF path (default: output/presentation.pdf)")
    parser.add_argument("--slides-dir", default=None,
                        help="Directory for slide images (default: slides/)")
    parser.add_argument("--workers", "-w", type=int, default=3,
                        help="Parallel workers (default: 3)")
    parser.add_argument("--base-dir", default=None,
                        help="Base directory (default: plan file's directory)")
    parser.add_argument("--quality-check", "-q", action="store_true",
                        help="Enable quality check and auto-refinement")
    args = parser.parse_args()

    ok = run_deck(
        args.plan, output_pdf=args.output,
        slides_dir=args.slides_dir,
        workers=args.workers, base_dir=args.base_dir,
        quality_check=args.quality_check,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
