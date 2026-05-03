import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class SearchCandidate(BaseModel):
    source_id: str
    source: str
    title: str
    artist: str
    duration_seconds: int = Field(ge=1)
    url: str
    compatibility_score: Optional[int] = Field(default=None, ge=0, le=100)
    compatibility_breakdown: Optional[Dict[str, int]] = None

    @staticmethod
    def _normalize_for_score(value: str) -> List[str]:
        lowered = (value or "").strip().lower()
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", lowered)
        return [token for token in cleaned.split() if token]

    @staticmethod
    def _token_overlap_score(query_tokens: List[str], candidate_tokens: List[str]) -> int:
        if not query_tokens or not candidate_tokens:
            return 0

        query_set = set(query_tokens)
        candidate_set = set(candidate_tokens)
        overlap = len(query_set & candidate_set)
        ratio = overlap / max(1, len(query_set))
        return max(0, min(100, int(round(ratio * 100))))

    @classmethod
    def _estimate_compatibility_score(cls, query: str, title: str, artist: str) -> tuple[int, Dict[str, int]]:
        query_tokens = cls._normalize_for_score(query)
        title_tokens = cls._normalize_for_score(title)
        artist_tokens = cls._normalize_for_score(artist)

        title_score = cls._token_overlap_score(query_tokens, title_tokens)
        artist_score = cls._token_overlap_score(query_tokens, artist_tokens)

        score = int(round((title_score * 0.7) + (artist_score * 0.3)))
        score = max(0, min(100, score))

        return score, {
            "title": title_score,
            "artist": artist_score,
        }

    @classmethod
    def from_ydl_entry(cls, entry: Dict[str, Any], position: int, query: str) -> Optional["SearchCandidate"]:
        title = str(entry.get("title") or "").strip()
        if not title:
            return None

        video_id = str(entry.get("id") or "").strip()
        artist = str(entry.get("uploader") or entry.get("channel") or "Unknown").strip()
        source = str(entry.get("extractor_key") or "youtube").lower()

        duration_raw = entry.get("duration")
        duration_seconds = int(duration_raw) if isinstance(duration_raw, (int, float)) and duration_raw > 0 else 1

        url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
        if not url and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        if not url:
            return None

        source_id = f"yt_{video_id}" if video_id else f"yt_result_{position}"
        compatibility_score, compatibility_breakdown = cls._estimate_compatibility_score(query, title, artist)

        return cls(
            source_id=source_id,
            source=source,
            title=title,
            artist=artist,
            duration_seconds=duration_seconds,
            url=url,
            compatibility_score=compatibility_score,
            compatibility_breakdown=compatibility_breakdown,
        )


class SearchResponse(BaseModel):
    query: str
    candidates: List[SearchCandidate]
    recommended_source_id: Optional[str] = None
