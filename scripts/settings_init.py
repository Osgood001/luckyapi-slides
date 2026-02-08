#!/usr/bin/env python3
"""Initialize the settings (设定集) folder structure.

Creates:
    settings/
    settings/art_style/
    settings/characters/
    settings/world/
    settings/props/
    settings/settings.json

Usage:
    python settings_init.py [--base-dir DIR]
"""
import argparse
import json
import os
import sys

CATEGORIES = ["art_style", "characters", "world", "props"]

DEFAULT_SETTINGS = {
    "art_style": {
        "description": "",
        "images": []
    },
    "characters": {},
    "world": {},
    "props": {}
}


def init_settings(base_dir="."):
    settings_dir = os.path.join(base_dir, "settings")
    settings_file = os.path.join(settings_dir, "settings.json")

    if os.path.exists(settings_file):
        print(f"Settings already exist at {settings_file}")
        return True

    for cat in CATEGORIES:
        cat_dir = os.path.join(settings_dir, cat)
        os.makedirs(cat_dir, exist_ok=True)
        print(f"  Created {cat_dir}/")

    with open(settings_file, "w") as f:
        json.dump(DEFAULT_SETTINGS, f, indent=2)
    print(f"  Created {settings_file}")

    print("Settings initialized.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Initialize settings folder structure"
    )
    parser.add_argument(
        "--base-dir", default=".",
        help="Base directory (default: current dir)"
    )
    args = parser.parse_args()
    ok = init_settings(args.base_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
