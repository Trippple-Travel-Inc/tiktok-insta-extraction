"""In-process load test for the concurrency guards.

Stubs the network and Claude, then drives the ASGI app directly, so we can
assert on behaviour under a burst instead of guessing at it — and without
sending a single request to TikTok.

    uv run python loadtest.py
"""

import asyncio
import os
import threading
import time

# Must be set before `server` is imported — config is read at module load.
os.environ.setdefault("EXTRACT_MAX_CONCURRENCY", "6")
os.environ.setdefault("EXTRACT_MAX_QUEUE", "24")
os.environ.setdefault("EXTRACT_DEADLINE_S", "30")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake-for-loadtest")

import httpx  # noqa: E402
from anthropic import AuthenticationError  # noqa: E402
from yt_dlp.utils import DownloadError  # noqa: E402

import server  # noqa: E402

WORK_S = 0.25  # stand-in for yt-dlp + page scrape + comments + Claude

live = 0
peak = 0
upstream_calls = 0
_lock = threading.Lock()


def reset() -> None:
    global live, peak, upstream_calls
    live = peak = upstream_calls = 0
    server._cache._entries.clear()
    server._cache._inflight.clear()


def _fake_extract(url: str) -> dict:
    global live, peak, upstream_calls
    with _lock:
        live += 1
        peak = max(peak, live)
        upstream_calls += 1
    try:
        time.sleep(WORK_S)
    finally:
        with _lock:
            live -= 1
    return {
        "id": "1",
        "caption": "cool spots",
        "hashtags": [],
        "transcript": None,
        "stickers": [],
        "suggested_words": [],
        "location_created": "Paris",
        "canonical_url": url,
        "thumbnail": None,
        "author": "someone",
    }


def _fake_places(**_kw) -> list[dict]:
    return [{"name": "Lilia", "type": "restaurant", "city": "Paris",
             "country": "France", "context": "pasta"}]


def install_stubs() -> None:
    server.extract = _fake_extract
    server.fetch_comments = lambda **_kw: []
    server.extract_places = _fake_places
    # _tiktok_work closes over the module globals, so rebinding above is enough.


async def burst(client: httpx.AsyncClient, urls: list[str]) -> list[httpx.Response]:
    return await asyncio.gather(
        *(client.post("/tiktok/extract", json={"url": u}) for u in urls)
    )


def summarise(responses: list[httpx.Response]) -> dict:
    out: dict[int, int] = {}
    for r in responses:
        out[r.status_code] = out.get(r.status_code, 0) + 1
    return out


async def main() -> int:
    install_stubs()
    transport = httpx.ASGITransport(app=server.app)
    failures = []

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=60
    ) as client:

        # 1. Viral post: 100 people import the SAME url at once.
        reset()
        t0 = time.perf_counter()
        responses = await burst(client, ["https://tiktok.com/@a/video/1"] * 100)
        elapsed = time.perf_counter() - t0
        codes = summarise(responses)
        print(f"\n[1] 100 concurrent, SAME url  -> {codes} in {elapsed:.1f}s")
        print(f"    upstream extractions: {upstream_calls}  (peak concurrent: {peak})")
        if upstream_calls != 1:
            failures.append(f"same-url burst did {upstream_calls} extractions, want 1")
        if codes.get(200) != 100:
            failures.append(f"same-url burst: {codes.get(200)}/100 succeeded")

        # 2. 100 DISTINCT urls at once — the genuine worst case.
        reset()
        t0 = time.perf_counter()
        responses = await burst(
            client, [f"https://tiktok.com/@a/video/{i}" for i in range(100)]
        )
        elapsed = time.perf_counter() - t0
        codes = summarise(responses)
        print(f"\n[2] 100 concurrent, DISTINCT  -> {codes} in {elapsed:.1f}s")
        print(f"    peak concurrent upstream: {peak}  (cap {server.MAX_CONCURRENCY})")
        if peak > server.MAX_CONCURRENCY:
            failures.append(f"peak {peak} exceeded cap {server.MAX_CONCURRENCY}")
        if codes.get(500):
            failures.append(f"{codes[500]} bare 500s under load")
        served = codes.get(200, 0) + codes.get(503, 0)
        if served != 100:
            failures.append(f"only {served}/100 got a definite answer")

        # 3. Rotated/dead Anthropic key must be a typed 503, not a bare 500.
        reset()
        def _auth_fail(**_kw):
            request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            raise AuthenticationError(
                "invalid x-api-key",
                response=httpx.Response(401, request=request),
                body=None,
            )
        server.extract_places = _auth_fail
        r = await client.post("/tiktok/extract", json={"url": "https://tiktok.com/@a/video/x"})
        print(f"\n[3] dead Anthropic key       -> {r.status_code} {r.json().get('detail')}")
        if r.status_code != 503:
            failures.append(f"dead key gave {r.status_code}, want 503")

        # 4. Platform blocking our IP must be distinguishable from a dead post.
        reset()
        server.extract_places = _fake_places
        def _blocked(url: str):
            raise DownloadError(
                "ERROR: [TikTok] 123: Your IP address is blocked from accessing this post"
            )
        server.extract = _blocked
        r = await client.post("/tiktok/extract", json={"url": "https://tiktok.com/@a/video/y"})
        detail = r.json().get("detail", "")
        print(f"\n[4] upstream IP block        -> {r.status_code} {detail[:60]}")
        if r.status_code != 502 or not detail.startswith("upstream_blocked"):
            failures.append(f"IP block gave {r.status_code} {detail[:40]!r}")

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
