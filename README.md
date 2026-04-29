# tiktok-insta-extraction

Phase 1 experiment: paste a TikTok URL, get caption + metadata as JSON.

## Setup

```bash
uv sync
```

## Usage

```bash
uv run python extract.py "https://www.tiktok.com/@user/video/1234567890"
```

Or with a short link:

```bash
uv run python extract.py "https://vm.tiktok.com/abc123/"
```

## Sample output

```json
{
  "input_url": "https://vm.tiktok.com/abc123/",
  "canonical_url": "https://www.tiktok.com/@user/video/1234567890",
  "id": "1234567890",
  "caption": "best pasta in nyc 🍝 Lilia in Williamsburg is insane #foodtok",
  "hashtags": ["foodtok"],
  "author": "user",
  "timestamp": 1700000000,
  "duration_sec": 22,
  "view_count": 1234567,
  "like_count": 89000,
  "thumbnail": "https://...",
  "video_url": "https://...",
  "_elapsed_ms": 850
}
```

## What's next

- Instagram extraction (with burner-account login fallback)
- LLM place-name extraction from captions
- Geocoding via Mapbox
- Frame sampling + vision model for on-screen text
