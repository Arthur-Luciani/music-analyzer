import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_STEMS = ("vocals", "drums", "bass", "other")


@dataclass(frozen=True)
class Settings:
    storage_root: Path
    stems_root: Path
    exports_root: Path
    sessions_db_path: Path
    separation_model: str
    separation_device: str
    separation_segment: float
    separation_overlap: float
    separation_shifts: int
    separation_target_stems: tuple[str, ...]
    torch_home: Path


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
    storage_root = Path(os.getenv("STORAGE_ROOT", "storage"))
    torch_home_default = storage_root / "cache" / "torch"
    sessions_db_default = storage_root / "sessions.db"
    exports_root_default = storage_root / "exports"

    return Settings(
        storage_root=storage_root,
        stems_root=storage_root / "stems",
        exports_root=Path(os.getenv("EXPORTS_ROOT", str(exports_root_default))),
        sessions_db_path=Path(os.getenv("SESSIONS_DB_PATH", str(sessions_db_default))),
        separation_model=(os.getenv("SEPARATION_MODEL", "htdemucs") or "htdemucs").strip(),
        separation_device=_read_device_env(),
        separation_segment=_read_float_env("SEPARATION_SEGMENT", 7.0),
        separation_overlap=_read_float_env("SEPARATION_OVERLAP", 0.25),
        separation_shifts=_read_int_env("SEPARATION_SHIFTS", 1),
        separation_target_stems=_read_target_stems_env(),
        torch_home=Path(os.getenv("TORCH_HOME", str(torch_home_default))),
    )


settings = load_settings()
