---
name: luckyapi-slides
description: Generate AI-powered presentation slide decks as PDF using LuckyAPI (luckyapi.chat) with the (按次)gemini-3-pro-image-preview model. Use when creating slide presentations, conference talks, lecture decks, or any multi-slide visual content. Generates each slide as an image, then combines into PDF. Requires ANTHROPIC_AUTH_TOKEN env var.
---

# LuckyAPI Slides

Generate presentation slide decks by creating each slide as an AI-generated image, then combining into a PDF.

## Prerequisites

- `ANTHROPIC_AUTH_TOKEN` environment variable set with LuckyAPI key
- Python packages: `requests`, `Pillow` (`pip install requests Pillow`)

## Workflow

### 1. Plan the deck

Define slide count, titles, and key content for each slide. Choose a consistent style prefix.

**Style prefix example:**
```
Create a 16:9 presentation slide. Deep navy background, white and cyan text, modern sans-serif font, minimal clean design.
```

### 2. Generate each slide

```bash
python scripts/generate_slide.py "<STYLE> <CONTENT>" -o slides/01_title.png
```

**Key lessons from production use:**

- **Keep prompts short** (~50 words). Long prompts with embedded guidelines cause 524 timeouts.
- **Prepend a consistent style string** to every prompt for visual coherence across the deck.
- **Name files with numeric prefix** (`01_`, `02_`) for correct PDF ordering.
- The API returns images as markdown URLs (`![Image](https://...)`), not base64. The script handles this.
- Each call takes ~30-90 seconds. Budget accordingly for large decks.
- Use `--retries 3` (default) to handle intermittent 524 errors.

**Script options:**
- `-o, --output` — Output image path (required)
- `--retries N` — Max retry attempts (default: 3)
- `--style "..."` — Style prefix prepended to prompt

**Environment overrides:**
- `LUCKYAPI_BASE_URL` — API base URL (default: `https://luckyapi.chat/v1`)
- `LUCKYAPI_MODEL` — Model name (default: `(按次)gemini-3-pro-image-preview`)

### 3. Combine into PDF

```bash
python scripts/slides_to_pdf.py slides/*.png -o presentation.pdf
```

Accepts PNG/JPG files or a directory. Sorts by filename. Options: `--dpi N` (default 150), `-v` for verbose.

## Prompt Writing Guide

**Effective prompt structure:**
```
<style prefix> <slide type>: '<Title>'. <content points>.
```

**Example prompts that work well:**
```
Create a 16:9 presentation slide. Deep navy background, white and cyan text, minimal design. Title slide: 'Machine Learning 101'. Subtitle: 'A Practical Guide'. Presenter: K-Dense.
```
```
Create a 16:9 presentation slide. Deep navy background, white and cyan text, minimal design. Slide: 'Key Findings'. Points: 1) 95% accuracy 2) 3x faster than baseline 3) Works across all datasets.
```

**What to avoid:**
- Prompts over ~80 words (causes timeouts)
- Embedding full slide design guidelines in the prompt
- Requesting specific font names or exact pixel sizes

## Scripts

### `scripts/generate_slide.py`
Generate a single slide image. Calls LuckyAPI, extracts the image URL from the response, downloads and saves it. Retries on failure.

### `scripts/slides_to_pdf.py`
Combine multiple slide images into a single PDF. Handles PNG/JPG/WEBP. Converts RGBA to RGB automatically. Requires Pillow.
