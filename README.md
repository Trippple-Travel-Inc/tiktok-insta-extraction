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

## Local API server

For use from the trippple-react Import Itinerary modal:

```bash
doppler run --project trippple-recs-engine --config dev --command \
  'ANTHROPIC_API_KEY="$CLAUDE_HAIKU" uv run uvicorn server:app --host 0.0.0.0 --port 8765 --reload'
```

Smoke test:

```bash
curl -s -X POST localhost:8765/tiktok/extract \
  -H 'content-type: application/json' \
  -d '{"url":"https://www.tiktok.com/@sagevanalstine/video/7236850924650548523"}' | jq
```

The mobile app reaches this from a phone over LAN — set
`EXPO_PUBLIC_TIKTOK_API_URL=http://<mac-lan-ip>:8765` in `trippple-react/.env.local`.

## What's next

- Instagram extraction (with burner-account login fallback)
- Hosting decision (Render / fly.io / fold into trippple-core) after a week of local use
