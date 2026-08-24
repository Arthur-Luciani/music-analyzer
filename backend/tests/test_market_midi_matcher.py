from __future__ import annotations

from app.services.market_midi_matcher import (
    MarketMidiIndexEntry,
    match_against_index,
    normalize_artist,
    normalize_title,
    strip_leading_artist_prefix,
)


def test_normalize_title_strips_official_video_noise():
    assert normalize_title("Bohemian Rhapsody (Official Video)") == "bohemian rhapsody"


def test_normalize_title_strips_remaster_year():
    assert normalize_title("Goodbye Stranger (Remastered 2010)") == "goodbye stranger"


def test_normalize_artist_strips_topic_suffix():
    assert normalize_artist("Supertramp - Topic") == "supertramp"


def test_normalize_title_strips_feat():
    assert normalize_title("Song Title feat. Someone Else") == "song title"


def test_normalize_title_folds_diacritics_and_case():
    assert normalize_title("Über Café") == "uber cafe"


def test_normalize_artist_strips_official_channel_suffix():
    assert normalize_artist("Queen Official") == "queen"


def test_normalize_artist_strips_vevo_suffix():
    assert normalize_artist("RihannaVEVO".replace("VEVO", " VEVO")) == "rihanna"


def test_strip_leading_artist_prefix_removes_duplicated_artist():
    assert strip_leading_artist_prefix("Oasis - Wonderwall (Official Video)", "Oasis") == "Wonderwall (Official Video)"


def test_strip_leading_artist_prefix_keeps_title_when_no_prefix_matches():
    # Title doesn't start with the artist name -- nothing to strip.
    assert strip_leading_artist_prefix("Wonderwall (Official Video)", "Oasis") == "Wonderwall (Official Video)"


def test_strip_leading_artist_prefix_keeps_title_when_dash_is_mid_title():
    # A dash that isn't an artist-title separator shouldn't be touched.
    title = "Come As You Are - Nirvana Tribute"
    assert strip_leading_artist_prefix(title, "Nirvana") == title


def test_strip_leading_artist_prefix_handles_channel_name_with_extra_word():
    # Regression: artist is a YouTube channel name ("Survivor Band") rather
    # than the bare artist ("Survivor"). fuzz.ratio penalizes the length
    # mismatch and misses the prefix; token_set_ratio doesn't.
    title = "Survivor - Eye Of The Tiger (Official HD Video)"
    assert strip_leading_artist_prefix(title, "Survivor Band") == "Eye Of The Tiger (Official HD Video)"


def _index() -> list[MarketMidiIndexEntry]:
    def entry(artist: str, title: str, path: str) -> MarketMidiIndexEntry:
        return MarketMidiIndexEntry(
            artist=artist,
            title=title,
            artist_norm=normalize_artist(artist),
            title_norm=normalize_title(title),
            relative_path=path,
        )

    return [
        entry("Supertramp", "Goodbye Stranger", "Supertramp/Goodbye Stranger.mid"),
        entry("Supertramp", "The Logical Song", "Supertramp/The Logical Song.mid"),
        entry("Coldplay", "Yellow", "Coldplay/Yellow.mid"),
        entry("Queen", "Bohemian Rhapsody", "Queen/Bohemian Rhapsody.mid"),
    ]


def test_match_against_index_exact_match():
    match = match_against_index(_index(), "Supertramp", "Goodbye Stranger")
    assert match is not None
    assert match.relative_path == "Supertramp/Goodbye Stranger.mid"


def test_match_against_index_near_fuzzy_match():
    match = match_against_index(_index(), "Supertramp - Topic", "Goodbye Stranger (Remastered 2010)")
    assert match is not None
    assert match.relative_path == "Supertramp/Goodbye Stranger.mid"


def test_match_against_index_rejects_below_threshold():
    match = match_against_index(_index(), "Some Unrelated Band", "Totally Different Song Name")
    assert match is None


def test_match_against_index_artist_prefilter_avoids_cross_artist_title_collision():
    # "Yellow" (Coldplay) should not match under a clearly different artist,
    # even though the title itself is a short, generic word.
    match = match_against_index(_index(), "Supertramp", "Yellow")
    assert match is None


def test_match_against_index_empty_index_returns_none():
    assert match_against_index([], "Supertramp", "Goodbye Stranger") is None


def test_match_against_index_no_title_returns_none():
    assert match_against_index(_index(), "Supertramp", "") is None


def test_match_against_index_handles_official_channel_artist_suffix():
    # Regression: "Queen Official" scored just under the artist prefilter
    # threshold against "Queen" before normalize_artist stripped "Official".
    match = match_against_index(_index(), "Queen Official", "Bohemian Rhapsody")
    assert match is not None
    assert match.relative_path == "Queen/Bohemian Rhapsody.mid"


def test_match_against_index_handles_title_repeating_artist():
    # Regression: a YouTube-style "Artist - Song" title (the artist word
    # duplicated in the title) dragged the title score below threshold.
    match = match_against_index(_index(), "Supertramp", "Supertramp - Goodbye Stranger (Official Video)")
    assert match is not None
    assert match.relative_path == "Supertramp/Goodbye Stranger.mid"


def test_match_against_index_handles_title_repeating_channel_name():
    # Regression: same as above, but the uploader's channel name tacks an
    # extra word onto the artist ("Supertramp Band"), which used to prevent
    # the duplicated-artist prefix from being stripped from the title.
    match = match_against_index(_index(), "Supertramp Band", "Supertramp - Goodbye Stranger (Official Video)")
    assert match is not None
    assert match.relative_path == "Supertramp/Goodbye Stranger.mid"
