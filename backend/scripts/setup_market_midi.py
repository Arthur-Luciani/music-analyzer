"""Setup manual, único, do dataset de MIDI de mercado usado para melhorar
a transcrição de bateria (ver app/use_cases/match_market_midi.py).

Baixa o subset "Clean MIDI" do Lakh MIDI Dataset (CC-BY 4.0,
https://colinraffel.com/projects/lmd/), extrai e popula o catálogo
relacional (market_artists/market_tracks/market_midi_files, ver
app/repositories/market_midi_repository.py) usado pelo fuzzy matching em
app/services/market_midi_matcher.py.

Uso:
    python scripts/setup_market_midi.py                 # roda tudo
    python scripts/setup_market_midi.py --download
    python scripts/setup_market_midi.py --extract
    python scripts/setup_market_midi.py --index          # popula o catálogo no banco
    python scripts/setup_market_midi.py --force          # refaz download/extração mesmo se já feito

Cada etapa é idempotente (pula se já concluída) e independente — pode ser
interrompida e retomada (o download suporta resume via Range header).
"""
import argparse
import json
import logging
import re
import shutil
import sys
import tarfile
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).parent.parent))

from app.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_market_midi")

CLEAN_MIDI_URL = "http://hog.ee.columbia.edu/craffel/lmd/clean_midi.tar.gz"
_TITLE_SUFFIX_RE = re.compile(r"^(?P<title>.+?)(\.\d+)?$")

# Caracteres proibidos em nomes de arquivo/pasta no Windows (o tarball foi
# criado em Unix, onde ex: "Vou permettez Monsieur ?.mid" é um nome válido).
_WINDOWS_ILLEGAL_CHARS_RE = re.compile(r'[<>:"|?*]')
_WINDOWS_TRAILING_RE = re.compile(r"[ .]+$")
# Alguns títulos do dataset (ex: medleys) passam de 200 caracteres; o
# Windows tem um limite de caminho total de 260 (MAX_PATH) sem long-path
# habilitado, então truncamos cada segmento para deixar margem.
_MAX_SEGMENT_LENGTH = 100


def _sanitize_path_segment(segment: str) -> str:
    cleaned = _WINDOWS_ILLEGAL_CHARS_RE.sub("_", segment)
    cleaned = cleaned[:_MAX_SEGMENT_LENGTH]
    cleaned = _WINDOWS_TRAILING_RE.sub("", cleaned)
    return cleaned or "_"


def _windows_safe_filter(member: tarfile.TarInfo, dest_path: str) -> Optional[tarfile.TarInfo]:
    member.name = "/".join(_sanitize_path_segment(part) for part in member.name.split("/"))
    return tarfile.data_filter(member, dest_path)


def download(force: bool = False) -> Path:
    market_midi_root = settings.market_midi_root
    market_midi_root.mkdir(parents=True, exist_ok=True)
    archive_path = market_midi_root / "clean_midi.tar.gz"
    complete_marker = market_midi_root / "clean_midi.tar.gz.complete"

    if force:
        complete_marker.unlink(missing_ok=True)
        if archive_path.exists():
            archive_path.unlink()

    if complete_marker.exists() and archive_path.exists():
        logger.info(f"Download já completo em {archive_path}, pulando (use --force para refazer).")
        return archive_path

    existing_size = archive_path.stat().st_size if archive_path.exists() else 0
    request = urllib.request.Request(CLEAN_MIDI_URL)
    if existing_size:
        request.add_header("Range", f"bytes={existing_size}-")
        logger.info(f"Tentando retomar download a partir de {existing_size} bytes...")

    with urllib.request.urlopen(request, timeout=60) as response:
        resumed = bool(existing_size) and response.status == 206
        if existing_size and not resumed:
            logger.warning("Servidor não suportou resume (Range); baixando do zero.")

        mode = "ab" if resumed else "wb"
        downloaded = existing_size if resumed else 0
        with open(archive_path, mode) as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

    complete_marker.write_text("ok", encoding="utf-8")
    logger.info(f"Download concluído: {downloaded} bytes em {archive_path}")
    return archive_path


def extract(force: bool = False) -> Path:
    market_midi_root = settings.market_midi_root
    archive_path = market_midi_root / "clean_midi.tar.gz"
    extract_dir = market_midi_root / "clean_midi"
    complete_marker = market_midi_root / "clean_midi.extracted"

    if not archive_path.exists():
        raise FileNotFoundError(f"{archive_path} não encontrado — rode --download primeiro.")

    if force:
        complete_marker.unlink(missing_ok=True)
        if extract_dir.exists():
            shutil.rmtree(extract_dir)

    if complete_marker.exists() and extract_dir.exists():
        logger.info(f"Já extraído em {extract_dir}, pulando (use --force para refazer).")
        return extract_dir

    logger.info(f"Extraindo {archive_path} em {market_midi_root}...")
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(path=market_midi_root, filter=_windows_safe_filter)

    complete_marker.write_text("ok", encoding="utf-8")
    logger.info(f"Extração concluída em {extract_dir}")
    return extract_dir


def build_catalog() -> None:
    """Popula market_artists/market_tracks/market_midi_files a partir dos
    arquivos extraídos. Idempotente — get_or_create_artist/track e
    add_midi_file pulam o que já está no banco, então rodar de novo (ex:
    depois de um --extract --force) só insere o que for novo."""
    from app.repositories.market_midi_repository import MarketMidiRepository
    from app.services.market_midi_matcher import normalize_artist, normalize_title

    market_midi_root = settings.market_midi_root
    extract_dir = market_midi_root / "clean_midi"
    if not extract_dir.is_dir():
        raise FileNotFoundError(f"{extract_dir} não encontrado — rode --extract primeiro.")

    repo = MarketMidiRepository()

    total_files = 0
    artist_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
    for artist_dir in artist_dirs:
        artist = artist_dir.name
        artist_id = repo.get_or_create_artist(artist, normalize_artist(artist))

        for midi_file in artist_dir.glob("*.mid"):
            match = _TITLE_SUFFIX_RE.match(midi_file.stem)
            title = match.group("title") if match else midi_file.stem
            track_id = repo.get_or_create_track(artist_id, title, normalize_title(title))

            relative_path = "/".join(("clean_midi", artist_dir.name, midi_file.name))
            if repo.add_midi_file(track_id, relative_path) is not None:
                total_files += 1

    meta = {
        "built_at": datetime.utcnow().isoformat(),
        "total_files": total_files,
        "total_artists": len(artist_dirs),
        "source": (
            "Lakh MIDI Dataset - Clean MIDI subset (clean_midi.tar.gz), "
            "CC-BY 4.0 - https://colinraffel.com/projects/lmd/"
        ),
    }
    (market_midi_root / "index_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    logger.info(f"Catálogo atualizado: {total_files} arquivos novos de {len(artist_dirs)} artistas.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Baixa clean_midi.tar.gz")
    parser.add_argument("--extract", action="store_true", help="Extrai o arquivo baixado")
    parser.add_argument("--index", action="store_true", help="Constrói o índice artista/título")
    parser.add_argument("--force", action="store_true", help="Refaz a(s) etapa(s) mesmo se já concluída(s)")
    args = parser.parse_args()

    run_all = not (args.download or args.extract or args.index)

    if args.download or run_all:
        download(force=args.force)
    if args.extract or run_all:
        extract(force=args.force)
    if args.index or run_all:
        build_catalog()


if __name__ == "__main__":
    main()
