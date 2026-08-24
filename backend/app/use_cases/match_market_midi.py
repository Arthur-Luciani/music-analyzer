import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models.market_midi import MarketMidiMatchResult
from app.repositories.market_midi_repository import MarketMidiRepository, MidiFileEntry
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class MatchMarketMidiUseCase:
    _job_service: object
    _repository: Optional[MarketMidiRepository] = None

    async def execute(self, session_id: str) -> MarketMidiMatchResult:
        """Tenta casar e alinhar um MIDI 'de mercado' para a sessão. Roda de
        forma sequencial (não fire-and-forget) logo após a análise técnica de
        bateria, para que `drum_transcription.mid` já esteja no estado final
        antes do evento de conclusão ser emitido — ver analyze_drum_stem.py."""
        job = await self._job_service.get_job(session_id)
        artist = job.selected_track.artist if job and job.selected_track else None
        title = job.selected_track.title if job and job.selected_track else None

        result = await asyncio.to_thread(self._run_sync, session_id, artist, title)

        try:
            await asyncio.to_thread(self._persist_result, session_id, result)
        except Exception as e:
            logger.error(f"Failed to persist market MIDI match result for {session_id}: {e}")

        return result

    def _run_sync(self, session_id: str, artist: Optional[str], title: Optional[str]) -> MarketMidiMatchResult:
        now = datetime.utcnow()
        try:
            return self._run_sync_unsafe(session_id, artist, title, now)
        except Exception as e:
            # Nunca deixa a análise de bateria falhar por causa do matching
            # de mercado — na dúvida, o MIDI gerado pelo ADTOF permanece.
            logger.error(f"Market MIDI matching failed unexpectedly for {session_id}: {e}", exc_info=True)
            return MarketMidiMatchResult(status="no_match", checked_at=now)

    def _run_sync_unsafe(
        self, session_id: str, artist: Optional[str], title: Optional[str], now: datetime
    ) -> MarketMidiMatchResult:
        from app.services.market_midi_matcher import load_index, match_against_index

        repo = self._repository or MarketMidiRepository()

        index = load_index(repo)
        if not index:
            return MarketMidiMatchResult(status="not_indexed", checked_at=now)

        from app.use_cases.analyze_drum_stem import AnalyzeDrumStemUseCase
        analysis = AnalyzeDrumStemUseCase.load_saved_analysis(session_id)
        if analysis is None or not analysis.hits:
            logger.warning(f"No reference drum analysis for session {session_id}; skipping market MIDI match")
            return MarketMidiMatchResult(status="no_match", checked_at=now)

        best_match = match_against_index(index, artist, title)
        if best_match is None:
            return MarketMidiMatchResult(status="no_match", checked_at=now)

        candidate_files = repo.list_files_for_track(best_match.track_id)
        return self._try_candidate_files(
            session_id=session_id,
            repo=repo,
            candidate_files=candidate_files,
            matched_artist=best_match.artist,
            matched_title=best_match.title,
            match_score=best_match.score,
            ref_duration=analysis.duration_seconds,
            ref_hits=[(hit.time, hit.type) for hit in analysis.hits],
            bpm=analysis.bpm if analysis.bpm > 0 else 120.0,
            now=now,
        )

    def _try_candidate_files(
        self,
        *,
        session_id: str,
        repo: MarketMidiRepository,
        candidate_files: list[MidiFileEntry],
        matched_artist: str,
        matched_title: str,
        match_score: float,
        ref_duration: float,
        ref_hits: list[tuple],
        bpm: float,
        now: datetime,
    ) -> MarketMidiMatchResult:
        """Uma track pode ter N arquivos MIDI candidatos (variações do mesmo
        dataset) — tenta o alinhamento DTW em cada um e fica com o de maior
        confiança. Arquivos já sabidamente ruins (`has_drum_track=False`,
        cacheado de uma tentativa anterior) são pulados sem reabrir o arquivo."""
        import pretty_midi
        from app.services.market_midi_alignment import (
            build_onset_density_features,
            compute_dtw_alignment,
            extract_drum_note_events,
            is_alignment_confident,
            is_duration_compatible,
            warp_midi,
        )

        base_result_kwargs = dict(
            matched_artist=matched_artist,
            matched_title=matched_title,
            match_score=match_score,
            checked_at=now,
        )

        ref_features = build_onset_density_features(ref_hits, ref_duration)

        winner = None  # (alignment, candidate_pm)
        best_attempt = None  # (alignment,) — melhor tentativa que rodou DTW mas não passou no gate
        any_readable = False

        for file_entry in candidate_files:
            if file_entry.has_drum_track is False:
                continue

            candidate_path = settings.market_midi_root / file_entry.relative_path
            try:
                candidate_pm = pretty_midi.PrettyMIDI(str(candidate_path))
                candidate_events = extract_drum_note_events(candidate_pm)
            except Exception as e:
                logger.warning(f"Could not read candidate market MIDI {candidate_path}: {e}")
                repo.update_file_probe_result(file_entry.id, has_drum_track=False, duration_seconds=None)
                continue

            if not candidate_events:
                logger.warning(f"Candidate market MIDI {candidate_path} has no drum track")
                repo.update_file_probe_result(file_entry.id, has_drum_track=False, duration_seconds=None)
                continue

            any_readable = True
            cand_duration = candidate_pm.get_end_time()
            if file_entry.has_drum_track is None:
                repo.update_file_probe_result(file_entry.id, has_drum_track=True, duration_seconds=cand_duration)

            if not is_duration_compatible(ref_duration, cand_duration):
                continue

            cand_hits = [(event.start, event.hit_type) for event in candidate_events]
            cand_features = build_onset_density_features(cand_hits, cand_duration)
            alignment = compute_dtw_alignment(ref_features, cand_features)

            if is_alignment_confident(alignment):
                if winner is None or alignment.normalized_cost < winner[0].normalized_cost:
                    winner = (alignment, candidate_pm)
            elif best_attempt is None or alignment.normalized_cost < best_attempt[0].normalized_cost:
                best_attempt = (alignment,)

        if winner is not None:
            alignment, candidate_pm = winner
            warped = warp_midi(candidate_pm, alignment.mapping_fn, ref_duration, bpm)

            output_path = settings.stems_root / session_id / "drum_transcription.mid"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            warped.write(str(output_path))
            logger.info(f"Applied market MIDI for session {session_id}: {matched_artist} - {matched_title}")

            return MarketMidiMatchResult(
                status="applied",
                alignment_cost=alignment.normalized_cost,
                alignment_coverage=alignment.coverage_ratio,
                applied=True,
                **base_result_kwargs,
            )

        if best_attempt is not None:
            alignment, = best_attempt
            return MarketMidiMatchResult(
                status="low_confidence",
                alignment_cost=alignment.normalized_cost,
                alignment_coverage=alignment.coverage_ratio,
                **base_result_kwargs,
            )

        if any_readable:
            # Pelo menos um arquivo tinha trilha de bateria, mas nenhum passou
            # nem a checagem de duração (rejeitado antes do DTW rodar).
            return MarketMidiMatchResult(status="low_confidence", **base_result_kwargs)

        return MarketMidiMatchResult(status="candidate_unreadable", **base_result_kwargs)

    @staticmethod
    def _persist_result(session_id: str, result: MarketMidiMatchResult) -> None:
        output_path = settings.stems_root / session_id / "market_midi_match.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def load_saved_result(session_id: str) -> Optional[MarketMidiMatchResult]:
        path = settings.stems_root / session_id / "market_midi_match.json"
        if not path.is_file():
            return None
        try:
            return MarketMidiMatchResult.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Error loading saved market MIDI match for {session_id}: {e}")
            return None
