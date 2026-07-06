"""Extract specific real-world places from caption + transcript using Claude."""

from typing import Literal, Optional

from anthropic import Anthropic
from pydantic import BaseModel, Field


class Place(BaseModel):
    name: str = Field(description="Cleaned, canonical name of the place")
    type: Literal[
        "restaurant",
        "bar",
        "cafe",
        "park",
        "museum",
        "neighborhood",
        "transit",
        "shop",
        "hotel",
        "landmark",
        "other",
    ]
    city: Optional[str] = None
    country: Optional[str] = None
    context: str = Field(
        description="Short snippet (≤25 words) describing what was said about this place"
    )


class PlacesResponse(BaseModel):
    places: list[Place]


SYSTEM = """You extract real-world places from social-media video content. You receive several signals: caption, hashtags, on-screen-text stickers (creator-typed — usually the cleanest place names), audio transcript (often noisy auto-transcription), and TikTok-suggested keywords.

Rules:
- Trust stickers as ground truth for spelling when they conflict with the transcript.
- Only extract specific, named places: restaurants, bars, cafes, parks, museums, neighborhoods, transit lines, shops, hotels, landmarks. Skip generic descriptors ("a cafe", "the park").
- Fix transcription errors using stickers/hashtags/context. Examples: "Boydeven Sen" → "Bois de Vincennes"; "Pomonette" → "Promenade Plantée".
- Use the most canonical, searchable form of the name.
- Infer city/country from context (hashtags, suggested keywords, location_created).
- Skip the city/country itself unless it's the only thing mentioned. We want specific spots, not the destination.
- Keep `context` short — what was said about it, not a full quote."""


def extract_places(
    caption: str,
    transcript: Optional[str],
    hashtags: list[str],
    stickers: Optional[list[str]] = None,
    suggested_words: Optional[list[str]] = None,
    location_created: Optional[str] = None,
) -> list[dict]:
    client = Anthropic()

    parts = [
        f"Caption: {caption}",
        f"Hashtags: {', '.join(hashtags) if hashtags else '(none)'}",
        f"On-screen stickers (ground truth): {' | '.join(stickers) if stickers else '(none)'}",
        f"Suggested keywords: {', '.join(suggested_words) if suggested_words else '(none)'}",
        f"Location created: {location_created or '(unknown)'}",
        "",
        f"Transcript:\n{transcript or '(no transcript)'}",
    ]
    user = "\n".join(parts)

    response = client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=PlacesResponse,
    )

    parsed = response.parsed_output
    if parsed is None:
        return []
    return [p.model_dump() for p in parsed.places]


TEXT_SYSTEM = """You extract real-world places from a user's pasted travel itinerary or notes. The input is messy freeform text: bullet lists, day-by-day plans, copied articles, chat messages, or a rough brain-dump.

Rules:
- Extract EVERY specific, named place: restaurants, bars, cafes, parks, museums, neighborhoods, transit lines, shops, hotels, landmarks, markets, attractions. Be thorough — if something looks like it could be a place name, include it.
- Skip generic descriptors ("a cafe", "our hotel", "the beach", "downtown") — only actual named places.
- Fix obvious misspellings and use the most canonical, searchable form of each name (e.g. "Boqueria Market" -> "Mercat de la Boqueria", "Uffizi Gallery" -> "Galleria degli Uffizi", "vinaeo" -> "vinaio").
- Prefer the local/official name when you know it.
- Infer city/country from context. If a city hint is provided, assume places are in or near it unless the text clearly says otherwise.
- Skip the destination city/country itself unless it's the only thing mentioned — we want specific spots, not the destination.
- Keep `context` short — what the text says about the place, not a full quote."""


def extract_places_from_text(
    text: str,
    city_hint: Optional[str] = None,
) -> list[dict]:
    """Extract places from freeform pasted text (the 'paste your own itinerary'
    import mode). Same structured-output contract as extract_places, but with a
    prompt tuned for messy documents rather than social-video signals."""
    client = Anthropic()

    user = "\n".join(
        [
            f"City hint: {city_hint or '(none)'}",
            "",
            f"Itinerary / notes:\n{text}",
        ]
    )

    response = client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=TEXT_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=PlacesResponse,
    )

    parsed = response.parsed_output
    if parsed is None:
        return []
    return [p.model_dump() for p in parsed.places]
