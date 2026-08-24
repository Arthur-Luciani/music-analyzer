"""Normalização e fuzzy-matching de artista/título contra o catálogo de
MIDI de mercado (Lakh Clean MIDI subset), indexado em `market_artists`/
`market_tracks` (ver app/repositories/market_midi_repository.py).

Sem I/O em `match_against_index`/`normalize_*` para manter essas funções
facilmente testáveis; `load_index`/`find_best_match` são as únicas que
tocam o banco.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

from app.repositories.market_midi_repository import CatalogEntry, MarketMidiRepository
from app.settings import settings

logger = logging.getLogger(__name__)

ARTIST_PREFILTER_THRESHOLD = 55.0

_BRACKET_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")
_TRAILING_DASH_TOPIC_RE = re.compile(r"-\s*topic\s*$", re.IGNORECASE)
_FEAT_RE = re.compile(r"\b(feat\.?|featuring|ft\.?)\b.*$", re.IGNORECASE)
_NOISE_PHRASES_RE = re.compile(
    r"\b(official\s+(music\s+)?video|official\s+audio|lyric(s)?\s+video|"
    r"remaster(ed)?(\s*\d{2,4})?|hd|4k)\b",
    re.IGNORECASE,
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
# Sufixos de nome de canal do YouTube (ex: "Queen Official", "RihannaVEVO") —
# só faz sentido remover do lado do artista, não do título de uma música.
_ARTIST_CHANNEL_SUFFIX_RE = re.compile(r"\b(official|vevo)\b", re.IGNORECASE)
# "Artista - Música" é a convenção mais comum de título de vídeo no YouTube;
# se o título já começa repetindo o artista, isso teria que ser removido
# antes de comparar contra o índice (senão a palavra extra derruba o score).
_LEADING_SEPARATOR_RE = re.compile(r"^\s*(?P<prefix>.+?)\s*[-–—:|]\s*(?=\S)")


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _base_normalize(text: str) -> str:
    text = (text or "").lower()
    text = _strip_diacritics(text)
    text = _TRAILING_DASH_TOPIC_RE.sub(" ", text)
    text = _BRACKET_RE.sub(" ", text)
    text = _FEAT_RE.sub("", text)
    text = _NOISE_PHRASES_RE.sub(" ", text)
    text = _NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def normalize_title(title: Optional[str]) -> str:
    return _base_normalize(title or "")


def normalize_artist(artist: Optional[str]) -> str:
    text = _ARTIST_CHANNEL_SUFFIX_RE.sub(" ", artist or "")
    return _base_normalize(text)


def strip_leading_artist_prefix(title: Optional[str], artist: Optional[str]) -> str:
    """Remove um prefixo 'Artista - ' do título quando o vídeo já repete o
    artista lá (ex: título "Oasis - Wonderwall (Official Video)" com artista
    "Oasis" vira "Wonderwall (Official Video)"). Sem isso, a palavra extra do
    artista no título derruba o score de fuzzy match do título sozinho."""
    if not title or not artist:
        return title or ""

    match = _LEADING_SEPARATOR_RE.match(title)
    if not match:
        return title

    leading_norm = _base_normalize(match.group("prefix"))
    artist_norm = _base_normalize(_ARTIST_CHANNEL_SUFFIX_RE.sub(" ", artist))
    if not leading_norm or not artist_norm:
        return title

    # token_set_ratio (not ratio) because the artist string is often a
    # YouTube channel name with extra words tacked on ("Survivor Band",
    # "Coldplay Music") that aren't covered by _ARTIST_CHANNEL_SUFFIX_RE —
    # ratio penalizes the length mismatch and misses the prefix.
    if fuzz.token_set_ratio(leading_norm, artist_norm) >= 80:
        return title[match.end():]
    return title


# Reexportado por conveniência — quem importa este módulo não precisa saber
# que o índice mora no repositório de catálogo.
MarketMidiIndexEntry = CatalogEntry


@dataclass(frozen=True)
class MarketMidiMatch:
    artist_id: int
    artist: str
    track_id: int
    title: str
    score: float


def load_index(repository: Optional[MarketMidiRepository] = None) -> list[CatalogEntry]:
    """Carrega o catálogo do banco. Nunca lança; retorna [] se o dataset
    ainda não foi importado (ver backend/scripts/setup_market_midi.py)."""
    repo = repository or MarketMidiRepository()
    try:
        return repo.list_catalog_entries()
    except Exception as e:
        logger.error(f"Failed to load market MIDI catalog: {e}")
        return []


def match_against_index(
    index: list[CatalogEntry],
    artist: Optional[str],
    title: Optional[str],
    *,
    threshold: Optional[float] = None,
) -> Optional[MarketMidiMatch]:
    """Função pura (sem I/O) — recebe o catálogo (nível de track) já carregado."""
    if not index or not title:
        return None

    artist_norm = normalize_artist(artist)
    title_norm = normalize_title(strip_leading_artist_prefix(title, artist))
    if not title_norm:
        return None

    match_threshold = settings.market_midi_match_threshold if threshold is None else threshold

    unique_artist_norms = {entry.artist_norm for entry in index}
    if artist_norm:
        artist_scores = {a: fuzz.token_sort_ratio(artist_norm, a) for a in unique_artist_norms}
        candidate_artist_norms = {
            a for a, score in artist_scores.items() if score >= ARTIST_PREFILTER_THRESHOLD
        }
        if not candidate_artist_norms:
            return None
    else:
        artist_scores = {}
        candidate_artist_norms = unique_artist_norms

    best: Optional[MarketMidiMatch] = None
    best_score = -1.0
    for entry in index:
        if entry.artist_norm not in candidate_artist_norms:
            continue
        title_score = fuzz.token_sort_ratio(title_norm, entry.title_norm)
        combined = (
            title_score * 0.7 + artist_scores[entry.artist_norm] * 0.3
            if artist_norm
            else float(title_score)
        )
        if combined > best_score:
            best_score = combined
            best = MarketMidiMatch(
                artist_id=entry.artist_id,
                artist=entry.artist,
                track_id=entry.track_id,
                title=entry.title,
                score=combined,
            )

    if best is None or best_score < match_threshold:
        return None
    return best


def find_best_match(artist: Optional[str], title: Optional[str]) -> Optional[MarketMidiMatch]:
    return match_against_index(load_index(), artist, title)
