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

## Configuration

All optional except `ANTHROPIC_API_KEY`.

| Env var | Default | What it does |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | **Required.** Every import runs a Claude call server-side. Validated once at boot; if it's missing or rejected, `/health` reports `llm: auth_failed` and logs CRITICAL. |
| `EXTRACT_MAX_CONCURRENCY` | `6` | Extractions allowed to touch TikTok/Instagram/Anthropic at once. |
| `EXTRACT_MAX_QUEUE` | `24` | Requests allowed to wait for a slot. Past this we return `503` + `Retry-After`. |
| `EXTRACT_DEADLINE_S` | `40` | Per-request ceiling. Kept under the app's 45s client timeout. |
| `EXTRACT_CACHE_TTL_S` | `3600` | How long an extracted result is reused for the same URL. |
| `EXTRACT_API_KEY` | unset | Opt-in shared-key gate. When set, requests must send a matching `X-Extract-Key`. Pairs with `EXPO_PUBLIC_EXTRACT_KEY` in the app. Unset = endpoints are open. |
| `EXTRACT_PROXY_URL` | unset | Proxy for **all** upstream calls (yt-dlp *and* the raw urllib page/comment/subtitle fetches). |
| `EXTRACT_COOKIES_FILE` | unset | Netscape-format cookie jar. Instagram needs one for most posts. |

### Tuning the concurrency limits

The binding constraint is not CPU — it's that TikTok and Instagram block a
datacenter IP that hits them too hard. So the goal is a low, *deliberate*
ceiling, not a high one. FastAPI runs sync `def` endpoints on a 40-thread pool
by default, which would mean up to 40 simultaneous anonymous requests from one
IP; the endpoints are `async def` and gated by an explicit limiter instead.

`MAX_QUEUE` is sized against `DEADLINE_S`: with 6 concurrent and ~5s per
extraction, the 24th queued request waits ~20s and still answers inside the 40s
deadline. If you raise `MAX_QUEUE`, the tail starts timing out instead of being
told to retry — which is worse, because a thread inside yt-dlp cannot be
cancelled, so the server keeps paying for work the app has already given up on.

**To serve more load, add upstream capacity (proxies), not queue depth.**

### Load test

Exercises the guards against stubbed upstreams — no network, no TikTok:

```bash
uv run python loadtest.py
```

Asserts that a same-URL burst coalesces to one extraction, that concurrency
never exceeds the cap, that overflow sheds with `503` rather than hanging, and
that a rotated Anthropic key surfaces as `503 llm_auth_failed` rather than an
opaque `500`.

## What's next

- Cookies + rotating/residential proxy for TikTok and Instagram (issue #3) —
  the service is currently IP-blocked by TikTok and cannot read most Instagram
  posts. Plumbing is in place (`EXTRACT_PROXY_URL`, `EXTRACT_COOKIES_FILE`);
  it needs credentials.
- Shared result cache (Redis) if this ever runs on more than one instance — the
  current cache is per-process.
