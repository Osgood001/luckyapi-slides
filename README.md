# luckyapi-slides

AI-powered slide deck generator using LuckyAPI with `(按次)gemini-3-pro-image-preview`. Generates each slide as an image, then combines into a PDF presentation.

## Install into Claude Code

```bash
claude plugin add --from github:Osgood001/luckyapi-slides
```

Then set your API key:

```bash
export ANTHROPIC_AUTH_TOKEN="your-luckyapi-key"
```

## Usage

Once installed, ask Claude Code to create slides:

```
Create a 10-slide presentation about machine learning for beginners
```

Claude will use the skill automatically to generate each slide image and combine them into a PDF.

## Manual usage

Generate a single slide:

```bash
python scripts/generate_slide.py "Create a 16:9 slide. Dark navy background, white text. Title slide: 'My Presentation'." -o slides/01_title.png
```

Combine slides into PDF:

```bash
python scripts/slides_to_pdf.py slides/*.png -o presentation.pdf
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_AUTH_TOKEN` | *(required)* | LuckyAPI API key |
| `LUCKYAPI_BASE_URL` | `https://luckyapi.chat/v1` | API base URL |
| `LUCKYAPI_MODEL` | `(按次)gemini-3-pro-image-preview` | Image generation model |

## Requirements

- Python 3.8+
- `requests`, `Pillow` (`pip install requests Pillow`)
