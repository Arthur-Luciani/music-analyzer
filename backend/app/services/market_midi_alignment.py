"""Alinhamento temporal (DTW) entre o MIDI gerado pelo ADTOF (referência,
já sincronizado ao stem real) e o MIDI de mercado candidato (timeline
própria, arbitrária), e o "warp" do candidato para a timeline da sessão.

Sem I/O; recebe eventos/features já extraídos. `extract_drum_note_events`
e `warp_midi` tocam objetos `pretty_midi.PrettyMIDI` em memória, mas não
leem/escrevem arquivos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import numpy as np

from app.services.drum_pitch_map import GM_PITCH_TO_HIT_TYPE
from app.settings import settings

FEATURE_CHANNELS = ("kick", "snare", "hihat", "other")
DEFAULT_HOP_SECONDS = 0.05
DEFAULT_MIN_COVERAGE = 0.8
DEFAULT_DURATION_RATIO_BAND = (0.6, 1.6)

# hit_type (kick/snare/hihat/tom/cymbal) -> canal de feature (tom/cymbal caem em "other")
_HIT_TYPE_TO_CHANNEL = {
    "kick": "kick",
    "snare": "snare",
    "hihat": "hihat",
    "tom": "other",
    "cymbal": "other",
}


@dataclass(frozen=True)
class NoteEvent:
    start: float
    end: float
    velocity: int
    pitch: int
    hit_type: str


@dataclass(frozen=True)
class AlignmentResult:
    mapping_fn: Callable[[float], float]  # candidate_time -> reference_time
    normalized_cost: float
    coverage_ratio: float


def extract_drum_note_events(pm) -> list[NoteEvent]:
    """Extrai eventos de nota de todas as faixas `is_drum` de um PrettyMIDI."""
    events: list[NoteEvent] = []
    for instrument in pm.instruments:
        if not instrument.is_drum:
            continue
        for note in instrument.notes:
            hit_type = GM_PITCH_TO_HIT_TYPE.get(note.pitch, "other")
            events.append(NoteEvent(
                start=float(note.start),
                end=float(note.end),
                velocity=int(note.velocity),
                pitch=int(note.pitch),
                hit_type=hit_type,
            ))
    events.sort(key=lambda e: e.start)
    return events


def _smooth_channels(features: np.ndarray, kernel_radius: int) -> np.ndarray:
    """Espalha cada onset para frames vizinhos com um kernel triangular.

    Sem isso, DTW consegue casar o k-ésimo onset da referência com o
    k-ésimo onset do candidato "de graça" (custo 0) mesmo quando os dois
    estão muito distantes no tempo real — onsets são raros e o resto é
    silêncio (também custo 0), então o caminho de custo mínimo não é
    forçado a respeitar proximidade temporal. Suavizar os onsets faz com
    que um desalinhamento real vire custo real.
    """
    if kernel_radius <= 0:
        return features
    offsets = np.arange(-kernel_radius, kernel_radius + 1)
    kernel = 1.0 - np.abs(offsets) / (kernel_radius + 1)
    kernel = kernel / kernel.sum()
    # Explicit padding + 'valid' convolution (not 'same') because numpy's
    # 'same' mode returns length max(len(row), len(kernel)) — it does NOT
    # preserve len(row) when the kernel is longer than a short row.
    padded = np.pad(features, ((0, 0), (kernel_radius, kernel_radius)), mode="constant")
    return np.stack([np.convolve(row, kernel, mode="valid") for row in padded])


def build_onset_density_features(
    hits: Sequence[tuple[float, str]],
    duration: float,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
    smooth_radius: int = 2,
) -> np.ndarray:
    """Constroi uma matriz de features (canais x frames) com contagem de
    onsets por canal (kick/snare/hihat/other) em janelas de `hop_seconds`,
    suavizada no eixo do tempo (ver `_smooth_channels`).

    `hits` é uma sequência de (time_seconds, hit_type) — deliberadamente
    genérico para aceitar tanto `DrumHit` (referência ADTOF) quanto
    `NoteEvent` (candidato de mercado) sem acoplar os dois formatos.
    """
    n_frames = max(1, int(math.ceil(duration / hop_seconds))) if duration > 0 else 1
    features = np.zeros((len(FEATURE_CHANNELS), n_frames), dtype=np.float64)
    channel_index = {c: i for i, c in enumerate(FEATURE_CHANNELS)}

    for time, hit_type in hits:
        if time < 0 or time > duration:
            continue
        frame = min(n_frames - 1, int(time / hop_seconds))
        channel = _HIT_TYPE_TO_CHANNEL.get(hit_type, "other")
        features[channel_index[channel], frame] += 1.0

    return _smooth_channels(features, smooth_radius)


def is_duration_compatible(
    ref_duration: float,
    cand_duration: float,
    *,
    band: tuple[float, float] = DEFAULT_DURATION_RATIO_BAND,
) -> bool:
    """Checagem rápida (sem DTW) para descartar candidatos com duração
    muito diferente da sessão antes de gastar tempo com alinhamento."""
    if ref_duration <= 0 or cand_duration <= 0:
        return False
    ratio = cand_duration / ref_duration
    low, high = band
    return low <= ratio <= high


def compute_dtw_alignment(
    ref_features: np.ndarray,
    cand_features: np.ndarray,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
) -> AlignmentResult:
    import librosa.sequence

    # euclidean (not cosine) because most frames are all-zero (silence) —
    # cosine distance against a zero vector is undefined (NaN).
    cost_matrix, warp_path = librosa.sequence.dtw(X=ref_features, Y=cand_features, metric="euclidean")

    # librosa retorna o warp path do fim para o início; precisamos ascendente.
    warp_path = np.asarray(warp_path)[::-1]
    ref_frames = warp_path[:, 0]
    cand_frames = warp_path[:, 1]

    normalized_cost = float(cost_matrix[warp_path[-1, 0], warp_path[-1, 1]] / len(warp_path))

    ref_span = int(ref_frames.max() - ref_frames.min() + 1)
    cand_span = int(cand_frames.max() - cand_frames.min() + 1)
    coverage_ratio = float(min(
        ref_span / ref_features.shape[1],
        cand_span / cand_features.shape[1],
    ))

    cand_times = cand_frames.astype(np.float64) * hop_seconds
    ref_times = ref_frames.astype(np.float64) * hop_seconds

    def mapping_fn(candidate_time: float) -> float:
        return float(np.interp(candidate_time, cand_times, ref_times))

    return AlignmentResult(
        mapping_fn=mapping_fn,
        normalized_cost=normalized_cost,
        coverage_ratio=coverage_ratio,
    )


def is_alignment_confident(
    result: AlignmentResult,
    *,
    max_cost: Optional[float] = None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> bool:
    cost_threshold = settings.market_midi_alignment_max_cost if max_cost is None else max_cost
    return result.normalized_cost <= cost_threshold and result.coverage_ratio >= min_coverage


def warp_midi(candidate_pm, mapping_fn: Callable[[float], float], ref_duration: float, bpm: float):
    """Remapeia as notas de bateria do MIDI candidato pela timeline da
    referência, preservando pitch/velocity originais (o groove humano é
    o que estamos importando; só a linha do tempo é ajustada)."""
    import pretty_midi

    warped = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for instrument in candidate_pm.instruments:
        if not instrument.is_drum:
            continue
        for note in instrument.notes:
            start = mapping_fn(float(note.start))
            if start < 0 or start > ref_duration:
                continue
            end = mapping_fn(float(note.end))
            if end <= start:
                end = start + 0.03
            end = min(end, ref_duration)
            drums.notes.append(pretty_midi.Note(
                velocity=int(note.velocity),
                pitch=int(note.pitch),
                start=start,
                end=end,
            ))

    warped.instruments.append(drums)
    return warped
