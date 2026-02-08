---
name: luckyapi-slides
description: Generate AI-powered presentation slide decks, comics, and visual content as PDF using LuckyAPI (luckyapi.chat) with the (按次)gemini-3-pro-image-preview model. Features a settings system (设定集) for visual consistency across pages. Use when creating slide presentations, comics, manga, or any multi-page visual content. Requires ANTHROPIC_AUTH_TOKEN env var.
---

# LuckyAPI Slides

Generate visually consistent multi-page content (slides, comics, manga) by first defining a settings bible (设定集), then generating pages with reference images for consistency.

## Prerequisites

- `ANTHROPIC_AUTH_TOKEN` environment variable set with LuckyAPI key
- Python packages: `requests`, `Pillow` (`pip install requests Pillow`)

## Workflow Overview

The workflow has two phases:

1. **Phase 1 — Settings (设定集)**: Guide the user through defining visual settings (art style, characters, world, props). Generate reference images. User confirms before proceeding.
2. **Phase 2 — Generation**: Generate all pages using confirmed settings for consistency, then combine into PDF.

**Important**: Do NOT start Phase 2 until the user explicitly confirms their settings are complete.

---

## Phase 1: Settings Creation (设定集)

### Step 1: Initialize settings

```bash
python scripts/settings_init.py --base-dir .
```

This creates:
```
settings/
  settings.json
  art_style/
  characters/
  world/
  props/
```

### Step 2: Show the settings dashboard

```bash
python scripts/settings_scan.py --base-dir . --pretty
```

Present the output to the user as a dashboard showing which categories are defined and which have unindexed files.

### Step 3: Guide the user through each category

The user chooses which category to define (any order, can skip or revisit). For each setting element:

1. **Ask** the user to describe what they want
2. **Source** the reference image via one of:
   - **Generate**: Call the API to create a reference image
   - **User-provided**: User supplies a local file path or URL
   - **Web search**: Search for reference images online
3. **Show** the result to the user (display the image file path)
4. **Confirm** or iterate ("try again", "adjust X")
5. **Save** to the settings folder and update settings.json

**Generate a reference image:**
```bash
python scripts/generate_reference.py "Description of the reference" \
    -o settings/<category>/<name>.png
```

With existing references for consistency:
```bash
python scripts/generate_reference.py "Same character, angry expression" \
    -o settings/characters/hero/angry.png \
    --reference-images settings/characters/hero/front.png
```

**Register in settings.json:**
```bash
python scripts/settings_add.py <category> [name] \
    --description "Text description" \
    --image settings/<category>/<name>.png
```

Examples:
```bash
# Art style
python scripts/settings_add.py art_style \
    -d "Dark navy background, cyan accents, minimal 16:9 layout" \
    -i settings/art_style/palette_ref.png

# Character
python scripts/settings_add.py characters hero \
    -d "Young woman, short black hair, lab coat" \
    -i settings/characters/hero/front.png

# World
python scripts/settings_add.py world city_night \
    -d "Neon-lit cyberpunk cityscape"

# Prop
python scripts/settings_add.py props logo \
    -d "Company logo, blue gradient circle"
```

### Step 4: Handle manual file placement

The user may drop files directly into settings subfolders. Run `settings_scan.py` to detect unindexed files and prompt the user to add descriptions for them.

### Step 5: Final confirmation

Show a summary of all settings. User must confirm before proceeding to generation.

---

## Phase 2: Content Generation

### Step 1: Define the content plan

Work with the user to define each page. Write a `slide_plan.json`:

```json
{
  "style_prefix": "Create a 16:9 presentation slide. Dark navy background, cyan accents.",
  "slides": [
    {
      "filename": "01_title.png",
      "prompt": "Title slide: 'Machine Learning 101'. Subtitle: 'A Practical Guide'.",
      "settings": ["art_style", "characters.hero"]
    },
    {
      "filename": "02_intro.png",
      "prompt": "Slide: 'Introduction'. Points: 1) What is ML 2) Why it matters.",
      "settings": ["art_style"]
    }
  ]
}
```

The `settings` array specifies which setting elements are relevant for each page. Use dot notation for specific entries: `characters.hero`, `world.city_night`, `props.logo`. Use just the category name to include all entries: `characters`, `world`.

### Step 2: Generate the deck

```bash
python scripts/generate_deck.py slide_plan.json --workers 3
```

This will:
- Load settings.json for reference images and descriptions
- Generate all slides in parallel (3 workers by default)
- Attach relevant reference images as base64 multi-modal input
- Prepend style prefix and setting descriptions to each prompt
- Combine all slides into `output/presentation.pdf`

Options:
- `--output PATH` — Custom PDF output path
- `--slides-dir DIR` — Custom slides directory
- `--workers N` — Parallel workers (default: 3)
- `--base-dir DIR` — Base directory for settings and output

### Step 3: Review and edit

After the PDF is generated:
- Show the user the output PDF path
- The user can request regeneration of specific slides
- To regenerate a single slide with settings:

```bash
python scripts/generate_slide.py "New prompt for this slide" \
    -o slides/03_methods.png \
    --reference-images settings/art_style/ref.png settings/characters/hero/front.png
```

Then recombine:
```bash
python scripts/slides_to_pdf.py slides/*.png -o output/presentation.pdf -v
```

---

## Prompt Writing Guide

**Keep prompts short** (~50 words). Long prompts cause timeouts.

**Effective structure:**
```
<style prefix> [setting descriptions] <slide type>: '<Title>'. <content>.
```

**What to avoid:**
- Prompts over ~80 words (causes timeouts)
- Embedding full design guidelines in the prompt (use reference images instead)
- Requesting specific font names or exact pixel sizes

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/settings_init.py` | Initialize settings folder structure |
| `scripts/settings_scan.py` | Scan settings, report dashboard status as JSON |
| `scripts/settings_add.py` | Add/update entries in settings.json |
| `scripts/generate_reference.py` | Generate a reference image for settings |
| `scripts/generate_slide.py` | Generate a single slide (supports `--reference-images`) |
| `scripts/generate_deck.py` | Orchestrate full deck: parallel generation + PDF |
| `scripts/slides_to_pdf.py` | Combine slide images into PDF |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_AUTH_TOKEN` | *(required)* | LuckyAPI API key |
| `LUCKYAPI_BASE_URL` | `https://luckyapi.chat/v1` | API base URL |
| `LUCKYAPI_MODEL` | `(按次)gemini-3-pro-image-preview` | Image generation model |

## Technical Notes

- Reference images are sent as **base64-encoded** data (URL-based image input is not supported by this API)
- Reference images are auto-resized to max 512px before encoding to keep payload size reasonable
- The `generate_deck.py` script handles parallel generation with configurable worker count
- Settings support manual file placement — users can drop files into settings subfolders
