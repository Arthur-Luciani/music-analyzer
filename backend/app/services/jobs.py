import asyncio
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Optional
from uuid import uuid4

from app.models import JobState, JobStatus, ScoreBreakdown, SearchCandidate, SearchResponse


class JobService:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobStatus] = {}
        self._subscribers: Dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._catalog = self._build_catalog()

    @staticmethod
    def _build_catalog() -> list[dict[str, object]]:
        return [
            {
                "source_id": "yt_001",
                "source": "youtube",
                "title": "Daft Punk - Get Lucky (Official Audio)",
                "artist": "Daft Punk",
                "duration_seconds": 369,
                "url": "https://www.youtube.com/watch?v=5NV6Rdv1a3I",
                "channel": "Daft Punk - Topic",
            },
            {
                "source_id": "yt_002",
                "source": "youtube",
                "title": "Daft Punk - Get Lucky (Live at Grammy Awards)",
                "artist": "Daft Punk",
                "duration_seconds": 392,
                "url": "https://www.youtube.com/watch?v=3g_qO8m0M8s",
                "channel": "Recording Academy",
            },
            {
                "source_id": "yt_003",
                "source": "youtube",
                "title": "Get Lucky - Studio Cover",
                "artist": "Session Band",
                "duration_seconds": 356,
                "url": "https://www.youtube.com/watch?v=JGwWNGJdvx8",
                "channel": "Studio Session",
            },
            {
                "source_id": "yt_004",
                "source": "youtube",
                "title": "Billie Jean (Remastered)",
                "artist": "Michael Jackson",
                "duration_seconds": 295,
                "url": "https://www.youtube.com/watch?v=Zi_XLOBDo_Y",
                "channel": "michaeljacksonVEVO",
            },
            {
                "source_id": "yt_005",
                "source": "youtube",
                "title": "Michael Jackson - Billie Jean (Live in Bucharest)",
                "artist": "Michael Jackson",
                "duration_seconds": 382,
                "url": "https://www.youtube.com/watch?v=Y6fM6K5l-zQ",
                "channel": "michaeljacksonVEVO",
            },
            {
                "source_id": "yt_006",
                "source": "youtube",
                "title": "The Weeknd - Blinding Lights (Official Audio)",
                "artist": "The Weeknd",
                "duration_seconds": 201,
                "url": "https://www.youtube.com/watch?v=fHI8X4OXluQ",
                "channel": "The Weeknd",
            },
            {
                "source_id": "yt_007",
                "source": "youtube",
                "title": "Daft Punk - Harder Better Faster Stronger",
                "artist": "Daft Punk",
                "duration_seconds": 224,
                "url": "https://www.youtube.com/watch?v=gAjR4_CbPpQ",
                "channel": "Daft Punk - Topic",
            },
            {
                "source_id": "yt_008",
                "source": "youtube",
                "title": "Get Lucky - Karaoke Version",
                "artist": "Karaoke Star",
                "duration_seconds": 372,
                "url": "https://www.youtube.com/watch?v=8UVNT4wvIGY",
                "channel": "Karaoke Star",
            },
            {
                "source_id": "yt_009",
                "source": "youtube",
                "title": "Ed Sheeran - Shape of You (Official Video)",
                "artist": "Ed Sheeran",
                "duration_seconds": 234,
                "url": "https://www.youtube.com/watch?v=JGwWNGJdvx8",
                "channel": "Ed Sheeran",
            },
            {
                "source_id": "yt_010",
                "source": "youtube",
                "title": "Shape of You - Acoustic Cover",
                "artist": "Acoustic Studio",
                "duration_seconds": 246,
                "url": "https://www.youtube.com/watch?v=lp-EO5I60KA",
                "channel": "Acoustic Studio",
            },
        ]

    def search_candidates(self, query: str, *, limit: int = 5) -> SearchResponse:
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return SearchResponse(query=query, candidates=[], recommended_source_id=None, requires_selection=False)

        scored: list[SearchCandidate] = []
        for item in self._catalog:
            candidate = self._score_candidate(query, item)
            if candidate.score >= 20:
                scored.append(candidate)

        scored.sort(key=lambda candidate: candidate.score, reverse=True)
        top = scored[:limit]
        recommended_source_id, requires_selection = self._resolve_recommendation(top)
        return SearchResponse(
            query=query,
            candidates=top,
            recommended_source_id=recommended_source_id,
            requires_selection=requires_selection,
        )

    def find_candidate(self, query: str, source_id: str) -> Optional[SearchCandidate]:
        response = self.search_candidates(query, limit=10)
        for candidate in response.candidates:
            if candidate.source_id == source_id:
                return candidate
        return None

    @staticmethod
    def _resolve_recommendation(candidates: list[SearchCandidate]) -> tuple[Optional[str], bool]:
        if not candidates:
            return None, False

        top = candidates[0]
        if len(candidates) == 1:
            return top.source_id, False

        second = candidates[1]
        gap = top.score - second.score
        auto_select = top.score >= 85 and gap >= 10
        return top.source_id, not auto_select

    def _score_candidate(self, query: str, item: dict[str, object]) -> SearchCandidate:
        title = str(item["title"])
        artist = str(item["artist"])
        channel = str(item.get("channel", ""))
        duration_seconds = int(item["duration_seconds"])

        normalized_query = self._normalize_text(query)
        normalized_title = self._normalize_text(title)
        normalized_artist = self._normalize_text(artist)
        guessed_artist = self._normalize_text(self._guess_artist(query))

        title_score = self._fuzzy_score(normalized_query, normalized_title)
        artist_score = max(
            self._fuzzy_score(normalized_query, normalized_artist),
            self._fuzzy_score(guessed_artist, normalized_artist),
        )
        duration_score = self._duration_score(duration_seconds)
        quality_score = self._quality_score(normalized_title, self._normalize_text(channel))
        penalties = self._penalty_score(normalized_title)

        base_velocity = 70
        raw_score = (
            (0.40 * title_score)
            + (0.30 * artist_score)
            + (0.15 * duration_score)
            + (0.10 * quality_score)
            + (0.05 * base_velocity)
            - penalties
        )
        final_score = int(max(0, min(100, round(raw_score))))

        return SearchCandidate(
            source_id=str(item["source_id"]),
            source=str(item["source"]),
            title=title,
            artist=artist,
            duration_seconds=duration_seconds,
            url=str(item["url"]),
            score=final_score,
            score_breakdown=ScoreBreakdown(
                title=title_score,
                artist=artist_score,
                duration=duration_score,
                quality=quality_score,
                penalties=penalties,
            ),
        )

    @staticmethod
    def _guess_artist(query: str) -> str:
        if "-" in query:
            return query.split("-", 1)[0].strip()
        tokens = query.strip().split()
        if len(tokens) >= 2:
            return " ".join(tokens[:2])
        return query.strip()

    @staticmethod
    def _normalize_text(value: str) -> str:
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = value.lower()
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        tokens = value.split()
        noise_tokens = {
            "official",
            "video",
            "audio",
            "lyrics",
            "lyric",
            "hd",
            "4k",
            "mv",
        }
        filtered = [token for token in tokens if token not in noise_tokens]
        return " ".join(filtered)

    @staticmethod
    def _fuzzy_score(left: str, right: str) -> int:
        if not left or not right:
            return 0

        ratio = SequenceMatcher(None, left, right).ratio()
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        if not left_tokens or not right_tokens:
            overlap = 0.0
        else:
            overlap = len(left_tokens & right_tokens) / len(left_tokens)

        score = ((ratio * 0.7) + (overlap * 0.3)) * 100
        return int(max(0, min(100, round(score))))

    @staticmethod
    def _duration_score(duration_seconds: int) -> int:
        if 150 <= duration_seconds <= 420:
            return 90
        if 120 <= duration_seconds <= 540:
            return 78
        if 90 <= duration_seconds <= 600:
            return 65
        return 45

    @staticmethod
    def _quality_score(title: str, channel: str) -> int:
        score = 55
        if "official" in title:
            score += 20
        if "audio" in title:
            score += 12
        if "topic" in channel:
            score += 8
        if "remaster" in title:
            score += 4
        if "live" in title:
            score -= 8
        return int(max(0, min(100, score)))

    @staticmethod
    def _penalty_score(title: str) -> int:
        weights = {
            "live": 14,
            "cover": 22,
            "remix": 16,
            "karaoke": 30,
            "nightcore": 20,
            "slowed": 18,
            "sped": 18,
        }
        penalty = 0
        for term, weight in weights.items():
            if term in title:
                penalty += weight
        return int(max(0, min(100, penalty)))

    async def create_job(self, query: str, selected_track: Optional[SearchCandidate] = None) -> JobStatus:
        now = datetime.utcnow()
        job = JobStatus(
            job_id=str(uuid4()),
            query=query,
            selected_track=selected_track,
            state=JobState.queued,
            progress=0,
            message="Job queued",
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._jobs[job.job_id] = job
            self._subscribers[job.job_id] = set()
        return job

    async def get_job(self, job_id: str) -> Optional[JobStatus]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(job_id)
            if subscribers is not None and queue in subscribers:
                subscribers.remove(queue)

    async def _broadcast(self, job_id: str, payload: dict) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(job_id, set()))
        for queue in subscribers:
            await queue.put(payload)

    async def update_job(
        self,
        job_id: str,
        *,
        state: JobState,
        progress: int,
        message: str,
        stems: Optional[Dict[str, str]] = None,
        error: Optional[str] = None,
    ) -> Optional[JobStatus]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            updated = job.model_copy(
                update={
                    "state": state,
                    "progress": progress,
                    "message": message,
                    "updated_at": datetime.utcnow(),
                    "stems": stems,
                    "error": error,
                }
            )
            self._jobs[job_id] = updated

        await self._broadcast(job_id, updated.model_dump(mode="json"))
        return updated

    async def run_pipeline(self, job_id: str) -> None:
        try:
            snapshot = await self.get_job(job_id)
            selected_title = snapshot.selected_track.title if snapshot and snapshot.selected_track else "selected source"

            await self.update_job(
                job_id,
                state=JobState.downloading,
                progress=15,
                message=f"Downloading audio source: {selected_title}",
            )
            await asyncio.sleep(1.2)

            await self.update_job(
                job_id,
                state=JobState.downloading,
                progress=45,
                message="Audio normalized and converted to WAV",
            )
            await asyncio.sleep(1.0)

            await self.update_job(
                job_id,
                state=JobState.separating,
                progress=70,
                message="Running stem separation on GPU",
            )
            await asyncio.sleep(1.6)

            stems = {
                "vocals": "storage/stems/{}/vocals.wav".format(job_id),
                "drums": "storage/stems/{}/drums.wav".format(job_id),
                "bass": "storage/stems/{}/bass.wav".format(job_id),
                "other": "storage/stems/{}/other.wav".format(job_id),
            }
            await self.update_job(
                job_id,
                state=JobState.ready,
                progress=100,
                message="Stems ready",
                stems=stems,
            )
        except Exception as exc:  # pragma: no cover
            await self.update_job(
                job_id,
                state=JobState.failed,
                progress=100,
                message="Processing failed",
                error=str(exc),
            )


job_service = JobService()
