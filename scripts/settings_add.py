#!/usr/bin/env python3
"""Add or update an entry in settings.json.

Usage:
    # Add art style
    python settings_add.py art_style --description "Dark navy, cyan accents"
    python settings_add.py art_style --image settings/art_style/ref.png

    # Add a character
    python settings_add.py characters hero \
        --description "Young woman, short black hair, lab coat" \
        --image settings/characters/hero/front.png

    # Add a world setting
    python settings_add.py world city_night \
        --description "Neon-lit cyberpunk cityscape at night"

    # Add a prop
    python settings_add.py props magic_sword \
        --description "Glowing blue longsword with runes"
"""
import argparse
import json
import os
import sys


def add_setting(base_dir, category, name, description, images):
    settings_file = os.path.join(base_dir, "settings", "settings.json")

    if not os.path.exists(settings_file):
        print(f"Error: {settings_file} not found. Run settings_init.py first.")
        return False

    with open(settings_file) as f:
        settings = json.load(f)

    if category not in settings:
        settings[category] = {}

    if category == "art_style":
        if description:
            settings["art_style"]["description"] = description
        for img in images:
            if img not in settings["art_style"].get("images", []):
                settings["art_style"].setdefault("images", []).append(img)
        print(f"  Updated art_style")
    else:
        if not name:
            print("Error: name required for characters/world/props")
            return False
        if name not in settings[category]:
            settings[category][name] = {"description": "", "images": []}
        entry = settings[category][name]
        if description:
            entry["description"] = description
        for img in images:
            if img not in entry["images"]:
                entry["images"].append(img)
        print(f"  Updated {category}/{name}")

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    print(f"  Saved {settings_file}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Add/update a settings entry"
    )
    parser.add_argument("category",
                        choices=["art_style", "characters", "world", "props"])
    parser.add_argument("name", nargs="?", default=None,
                        help="Entry name (required for characters/world/props)")
    parser.add_argument("--description", "-d", default=None)
    parser.add_argument("--image", "-i", action="append", default=[],
                        help="Image path (can specify multiple)")
    parser.add_argument("--base-dir", default=".")
    args = parser.parse_args()

    ok = add_setting(
        args.base_dir, args.category, args.name,
        args.description, args.image
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
