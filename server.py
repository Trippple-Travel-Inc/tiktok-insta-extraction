"""FastAPI wrapper around extract.py / places.py for the trippple-react import flow."""

import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from yt_dlp.utils import DownloadError

from extract import extract, fetch_comments
from extract_instagram import extract_instagram
from places import extract_places

app = FastAPI(title="trippple tiktok extraction")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ExtractRequest(BaseModel):
    url: str
    city_hint: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/tiktok/extract")
def tiktok_extract(req: ExtractRequest) -> dict:
    started = time.perf_counter()
    try:
        info = extract(req.url)
    except DownloadError as e:
        raise HTTPException(status_code=502, detail=f"extraction_failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"unexpected: {e}")

    # Always pull top comments and merge into the LLM input. Captions often
    # under-specify (creator names 2 spots in the caption but rattles off 10
    # in the video / comments thread). Comments are unauthenticated and free
    # to fetch, so the cost is one HTTP call + a slightly fatter LLM prompt.
    comments = fetch_comments(
        aweme_id=info.get("id") or "",
        referer=info.get("canonical_url") or req.url,
        count=50,
    )
    used_comments = len(comments)
    existing_transcript = info.get("transcript") or ""
    if comments:
        comment_text = "\n".join(
            f"({c['digg_count']} likes) {c['text']}" for c in comments[:50]
        )
        merged_transcript = (
            f"{existing_transcript}\n\n--- top comments ---\n{comment_text}"
            if existing_transcript
            else f"--- top comments ---\n{comment_text}"
        )
    else:
        merged_transcript = existing_transcript or None

    places_started = time.perf_counter()
    places = extract_places(
        caption=info["caption"],
        transcript=merged_transcript,
        hashtags=info.get("hashtags") or [],
        stickers=info.get("stickers") or [],
        suggested_words=info.get("suggested_words") or [],
        location_created=info.get("location_created"),
    )
    places_source = "caption_plus_comments" if comments else "caption_only"
    places_ms = int((time.perf_counter() - places_started) * 1000)

    suggested_city = None
    for p in places:
        if p.get("city"):
            suggested_city = p["city"]
            break
    if not suggested_city and info.get("location_created"):
        suggested_city = info["location_created"]

    return {
        "source": "tiktok",
        "places": places,
        "places_source": places_source,
        "suggested_city": suggested_city,
        "thumbnail": info.get("thumbnail"),
        "transcript": info.get("transcript"),
        "caption": info.get("caption"),
        "author": info.get("author"),
        "canonical_url": info.get("canonical_url"),
        "_places_ms": places_ms,
        "_comments_used": used_comments,
        "_elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


@app.post("/instagram/extract")
def instagram_extract(req: ExtractRequest) -> dict:
    started = time.perf_counter()
    try:
        info = extract_instagram(req.url)
    except DownloadError as e:
        raise HTTPException(status_code=502, detail=f"extraction_failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"unexpected: {e}")

    places_started = time.perf_counter()
    places = extract_places(
        caption=info["caption"],
        transcript=None,
        hashtags=info.get("hashtags") or [],
        stickers=[],
        suggested_words=[],
        location_created=None,
    )
    places_ms = int((time.perf_counter() - places_started) * 1000)

    suggested_city = None
    for p in places:
        if p.get("city"):
            suggested_city = p["city"]
            break

    return {
        "source": "instagram",
        "places": places,
        "places_source": "primary",
        "suggested_city": suggested_city,
        "thumbnail": info.get("thumbnail"),
        "transcript": None,
        "caption": info.get("caption"),
        "author": info.get("author"),
        "canonical_url": info.get("canonical_url"),
        "_places_ms": places_ms,
        "_elapsed_ms": int((time.perf_counter() - started) * 1000),
    }
