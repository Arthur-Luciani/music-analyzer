import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_STEMS = ("vocals", "drums", "bass", "other")


@dataclass(frozen=True)
class Settings:
    storage_root: Path
    stems_root: Path
    exports_root: Path
    sessions_db_path: Path
    yt_dlp_cookie_file: Optional[Path]
    separation_model: str
    separation_device: str
    separation_segment: float
    separation_overlap: float
    separation_shifts: int
    separation_target_stems: tuple[str, ...]
    torch_home: Path
    market_midi_root: Path
    market_midi_match_threshold: float
    market_midi_alignment_max_cost: float


def _read_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _read_path_env(name: str) -> Optional[Path]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    return Path(raw)


def _read_device_env() -> str:
    value = (os.getenv("SEPARATION_DEVICE", "auto") or "auto").strip().lower()
    if value not in {"auto", "cuda", "cpu"}:
        return "auto"
    return value


def _read_target_stems_env() -> tuple[str, ...]:
    raw = (os.getenv("SEPARATION_TARGET_STEMS") or "").strip().lower()
    if not raw:
        return DEFAULT_STEMS

    requested = [chunk.strip() for chunk in raw.split(",") if chunk.strip()]
    if not requested:
        return DEFAULT_STEMS

    seen: set[str] = set()
    filtered: list[str] = []
    for stem_name in requested:
        if stem_name in DEFAULT_STEMS and stem_name not in seen:
            filtered.append(stem_name)
            seen.add(stem_name)

    if not filtered:
        return DEFAULT_STEMS

    return tuple(filtered)


def load_settings() -> Settings:
    # Resolve project root (root of the git repo)
    # settings.py is in backend/app/settings.py, so we go up 3 levels
    project_root = Path(__file__).resolve().parent.parent.parent
    
    raw_storage_root = os.getenv("STORAGE_ROOT", "storage")
    storage_root = Path(raw_storage_root)
    
    # If storage_root is relative, resolve it against the project root
    # instead of the current working directory.
    if not storage_root.is_absolute():
        storage_root = (project_root / storage_root).resolve()

    torch_home_default = storage_root / "cache" / "torch"
    sessions_db_default = storage_root / "sessions.db"
    exports_root_default = storage_root / "exports"
    market_midi_root_default = storage_root / "market_midi"


    return Settings(
        storage_root=storage_root,
        stems_root=storage_root / "stems",
        exports_root=Path(os.getenv("EXPORTS_ROOT", str(exports_root_default))),
        sessions_db_path=Path(os.getenv("SESSIONS_DB_PATH", str(sessions_db_default))),
        yt_dlp_cookie_file=_read_path_env("YTDLP_COOKIE_FILE"),
        separation_model=(os.getenv("SEPARATION_MODEL", "htdemucs") or "htdemucs").strip(),
        separation_device=_read_device_env(),
        separation_segment=_read_float_env("SEPARATION_SEGMENT", 7.0),
        separation_overlap=_read_float_env("SEPARATION_OVERLAP", 0.25),
        separation_shifts=_read_int_env("SEPARATION_SHIFTS", 1),
        separation_target_stems=_read_target_stems_env(),
        torch_home=Path(os.getenv("TORCH_HOME", str(torch_home_default))),
        market_midi_root=Path(os.getenv("MARKET_MIDI_ROOT", str(market_midi_root_default))),
        market_midi_match_threshold=_read_float_env("MARKET_MIDI_MATCH_THRESHOLD", 87.0),
        market_midi_alignment_max_cost=_read_float_env("MARKET_MIDI_ALIGNMENT_MAX_COST", 0.35),
    )


settings = load_settings()
