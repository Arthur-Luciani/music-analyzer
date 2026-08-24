from __future__ import annotations

import pytest

from app.services.market_midi_alignment import (
    FEATURE_CHANNELS,
    AlignmentResult,
    build_onset_density_features,
    compute_dtw_alignment,
    is_alignment_confident,
    is_duration_compatible,
    warp_midi,
)


def test_build_onset_density_features_bins_by_channel_and_time():
    hits = [(0.0, "kick"), (0.05, "snare"), (0.6, "hihat"), (1.05, "tom")]
    features = build_onset_density_features(hits, duration=1.2, hop_seconds=0.5, smooth_radius=0)

    assert features.shape == (len(FEATURE_CHANNELS), 3)
    assert features.sum() == len(hits)
    assert features[FEATURE_CHANNELS.index("kick"), 0] == 1.0
    assert features[FEATURE_CHANNELS.index("snare"), 0] == 1.0
    assert features[FEATURE_CHANNELS.index("hihat"), 1] == 1.0
    # tom is folded into the "other" channel
    assert features[FEATURE_CHANNELS.index("other"), 2] == 1.0


def test_build_onset_density_features_ignores_hits_outside_duration():
    hits = [(-1.0, "kick"), (5.0, "kick")]
    features = build_onset_density_features(hits, duration=1.0, hop_seconds=0.5, smooth_radius=0)
    assert features.sum() == 0.0


def test_build_onset_density_features_preserves_frame_count_when_shorter_than_kernel():
    # Regression: numpy's convolve(mode="same") returns max(len(row), len(kernel))
    # frames, not len(row), when the kernel is longer than the row.
    hits = [(0.0, "kick")]
    features = build_onset_density_features(hits, duration=1.2, hop_seconds=0.5, smooth_radius=2)
    assert features.shape == (len(FEATURE_CHANNELS), 3)


@pytest.mark.parametrize(
    "ref_duration,cand_duration,expected",
    [
        (100.0, 100.0, True),
        (100.0, 65.0, True),
        (100.0, 155.0, True),
        (100.0, 50.0, False),
        (100.0, 170.0, False),
        (100.0, 0.0, False),
    ],
)
def test_is_duration_compatible_boundaries(ref_duration, cand_duration, expected):
    assert is_duration_compatible(ref_duration, cand_duration) is expected


def _click_track(n_beats: int, period: float, offset: float = 0.0, scale: float = 1.0):
    return [(offset + scale * i * period, "kick") for i in range(n_beats)]


def test_dtw_alignment_recovers_linear_stretch_and_shift():
    ref_hits = _click_track(20, period=0.5)  # 0.0, 0.5, ..., 9.5
    ref_duration = 10.0

    # Candidate is the same rhythm, but slower (x1.2) and shifted by +0.3s —
    # simulates a market MIDI with its own arbitrary tempo/offset.
    cand_hits = _click_track(20, period=0.5 * 1.2, offset=0.3)
    cand_duration = 0.3 + 1.2 * 9.5 + 0.5

    hop = 0.1
    ref_features = build_onset_density_features(ref_hits, ref_duration, hop_seconds=hop)
    cand_features = build_onset_density_features(cand_hits, cand_duration, hop_seconds=hop)

    result = compute_dtw_alignment(ref_features, cand_features, hop_seconds=hop)

    assert result.coverage_ratio > 0.8

    # mapping_fn(cand_time) should approximately invert cand = 0.3 + 1.2*ref
    for ref_time in (1.0, 5.0, 9.0):
        cand_time = 0.3 + 1.2 * ref_time
        recovered = result.mapping_fn(cand_time)
        assert recovered == pytest.approx(ref_time, abs=0.3)


def test_dtw_alignment_cost_higher_for_unrelated_candidate():
    ref_hits = _click_track(20, period=0.5)  # steady, spread across 10s
    ref_duration = 10.0
    hop = 0.1
    ref_features = build_onset_density_features(ref_hits, ref_duration, hop_seconds=hop)

    good_cand_hits = _click_track(20, period=0.5 * 1.2, offset=0.3)
    good_cand_duration = 0.3 + 1.2 * 9.5 + 0.5
    good_features = build_onset_density_features(good_cand_hits, good_cand_duration, hop_seconds=hop)
    good_result = compute_dtw_alignment(ref_features, good_features, hop_seconds=hop)

    # Unrelated: same onset count, but all crammed into the first 2s —
    # a genuinely different rhythmic profile from the reference's steady
    # spread across the full 10s (simulates matching the wrong song).
    unrelated_cand_hits = [(0.1 * i, "kick") for i in range(20)]
    unrelated_features = build_onset_density_features(unrelated_cand_hits, ref_duration, hop_seconds=hop)
    unrelated_result = compute_dtw_alignment(ref_features, unrelated_features, hop_seconds=hop)

    # DTW cost must at least discriminate *directionally* between a real
    # match and a clearly wrong one. The specific pass/fail threshold is a
    # separate, tunable policy decision — see test_is_alignment_confident_*
    # below, which tests that gating logic in isolation.
    assert unrelated_result.normalized_cost > good_result.normalized_cost
    assert is_alignment_confident(good_result, max_cost=0.35, min_coverage=0.8)


def test_is_alignment_confident_gates_on_cost_and_coverage():
    good = AlignmentResult(mapping_fn=lambda t: t, normalized_cost=0.1, coverage_ratio=0.95)
    high_cost = AlignmentResult(mapping_fn=lambda t: t, normalized_cost=0.9, coverage_ratio=0.95)
    low_coverage = AlignmentResult(mapping_fn=lambda t: t, normalized_cost=0.1, coverage_ratio=0.2)

    assert is_alignment_confident(good, max_cost=0.35, min_coverage=0.8)
    assert not is_alignment_confident(high_cost, max_cost=0.35, min_coverage=0.8)
    assert not is_alignment_confident(low_coverage, max_cost=0.35, min_coverage=0.8)


def test_warp_midi_remaps_notes_and_drops_out_of_range():
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    drums.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=1.0, end=1.05))
    drums.notes.append(pretty_midi.Note(velocity=90, pitch=38, start=10.0, end=10.05))
    pm.instruments.append(drums)

    non_drum = pretty_midi.Instrument(program=0, is_drum=False, name="Bass")
    non_drum.notes.append(pretty_midi.Note(velocity=80, pitch=40, start=1.0, end=1.5))
    pm.instruments.append(non_drum)

    def mapping_fn(t: float) -> float:
        return t * 2.0

    warped = warp_midi(pm, mapping_fn, ref_duration=5.0, bpm=120.0)

    assert len(warped.instruments) == 1
    warped_notes = warped.instruments[0].notes
    # The pitch=38 note maps to start=20.0, past ref_duration=5.0 -> dropped.
    assert len(warped_notes) == 1
    assert warped_notes[0].pitch == 36
    assert warped_notes[0].start == pytest.approx(2.0)
    assert warped_notes[0].end == pytest.approx(2.1)
