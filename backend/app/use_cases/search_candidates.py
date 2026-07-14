import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from yt_dlp import YoutubeDL

from app.models import SearchCandidate, SearchResponse


@dataclass
class SearchCandidatesUseCase:
    _job_service: object
    _recent_searches: Dict[str, List[SearchCandidate]] = field(default_factory=dict)

    def execute(self, query: str, limit: int = 5) -> SearchResponse:
        query_key = self._cache_query_key(query)
        if not query_key:
            return SearchResponse(query=query, candidates=[], recommended_source_id=None)

        entries = self._search_youtube(query, limit=max(1, min(limit, 10)))
        candidates = [
            candidate
            for index, entry in enumerate(entries, start=1)
            if (candidate := SearchCandidate.from_ydl_entry(entry, index, query)) is not None
        ]

        self._recent_searches[query_key] = candidates
        recommended_source_id = candidates[0].source_id if candidates else None
        return SearchResponse(
            query=query,
            candidates=candidates,
            recommended_source_id=recommended_source_id,
        )

    def find_candidate(self, query: str, source_id: str) -> Optional[SearchCandidate]:
        query_key = self._cache_query_key(query)
        cached = self._recent_searches.get(query_key, [])
        for candidate in cached:
            if candidate.source_id == source_id:
                return candidate

        response = self.execute(query, limit=10)
        for candidate in response.candidates:
            if candidate.source_id == source_id:
                return candidate
        return None

    def _search_youtube(self, query: str, *, limit: int) -> list[dict[str, object]]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": True,
            "default_search": "ytsearch",
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                if self._looks_like_url(query):
                    result = ydl.extract_info(query, download=False)
                else:
                    result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        except Exception:
            return []

        if not isinstance(result, dict):
            return []

        if isinstance(result.get("entries"), list):
            entries = [entry for entry in result["entries"] if isinstance(entry, dict)]
        else:
            entries = [result]

        return entries

    @staticmethod
    def _cache_query_key(query: str) -> str:
        return query.strip().lower()

    @staticmethod
    def _looks_like_url(query: str) -> bool:
        return query.startswith("http://") or query.startswith("https://")


