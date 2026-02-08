#!/usr/bin/env python3
"""Scan settings folders and report dashboard status as JSON.

Detects indexed entries (in settings.json) and unindexed files
(present in folders but not referenced in settings.json).

Usage:
    python settings_scan.py [--base-dir DIR]

Output: JSON with category status, indexed entries, and unindexed files.
"""
import argparse
import glob
import json
import os
import sys

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def scan_settings(base_dir="."):
    settings_dir = os.path.join(base_dir, "settings")
    settings_file = os.path.join(settings_dir, "settings.json")

    if not os.path.exists(settings_file):
        return {"initialized": False, "categories": {}}

    with open(settings_file) as f:
        settings = json.load(f)

    # Collect all image paths referenced in settings.json
    indexed_paths = set()
    for cat in ["art_style", "characters", "world", "props"]:
        cat_data = settings.get(cat, {})
        if cat == "art_style":
            for p in cat_data.get("images", []):
                indexed_paths.add(os.path.normpath(p))
        else:
            for name, entry in cat_data.items():
                if isinstance(entry, dict):
                    for p in entry.get("images", []):
                        indexed_paths.add(os.path.normpath(p))

    result = {"initialized": True, "categories": {}}

    for cat in ["art_style", "characters", "world", "props"]:
        cat_dir = os.path.join(settings_dir, cat)
        cat_data = settings.get(cat, {})

        # Find all image files in this category's folder
        all_files = []
        if os.path.isdir(cat_dir):
            for root, _, files in os.walk(cat_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in IMAGE_EXTS:
                        all_files.append(
                            os.path.normpath(
                                os.path.join(root, fname)
                            )
                        )

        unindexed = [f for f in all_files
                     if f not in indexed_paths]

        if cat == "art_style":
            indexed_count = (1 if cat_data.get("description")
                            or cat_data.get("images") else 0)
            entries = {}
        else:
            entries = {}
            for name, entry in cat_data.items():
                if isinstance(entry, dict):
                    entries[name] = {
                        "description": entry.get("description", ""),
                        "image_count": len(entry.get("images", [])),
                    }
            indexed_count = len(entries)

        result["categories"][cat] = {
            "indexed_count": indexed_count,
            "entries": entries,
            "unindexed_files": unindexed,
            "has_description": bool(
                cat_data.get("description", "")
            ) if cat == "art_style" else None,
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Scan settings and report status"
    )
    parser.add_argument(
        "--base-dir", default=".",
        help="Base directory (default: current dir)"
    )
    parser.add_argument(
        "--pretty", action="store_true",
        help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    result = scan_settings(args.base_dir)
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent))


if __name__ == "__main__":
    main()
