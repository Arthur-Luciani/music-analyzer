import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from sqlalchemy import select
from app.db.config import SessionLocal
from app.db.models import SessionORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def compress_to_mp3(source_file: Path, target_file: Path) -> bool:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_file),
        "-b:a",
        "320k",
        str(target_file),
    ]
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error(f"Failed to compress {source_file}: {exc}")
        return False

async def migrate_existing_stems():
    db = SessionLocal()
    try:
        sessions = db.query(SessionORM).filter(SessionORM.stems_json.isnot(None)).all()
        logger.info(f"Found {len(sessions)} sessions with stems.")

        total_saved_bytes = 0

        for session in sessions:
            stems = json.loads(session.stems_json)
            updated_stems = {}
            modified = False

            for stem_name, stem_path in stems.items():
                local_path = stem_path.replace("/app/storage", "c:/git/music-analyzer/storage")
                source_path = Path(local_path)
                
                if source_path.suffix.lower() == ".wav" and source_path.exists():
                    target_path = source_path.with_suffix(".mp3")
                    
                    logger.info(f"Compressing {source_path.name} for session {session.id}...")
                    
                    original_size = source_path.stat().st_size
                    
                    if compress_to_mp3(source_path, target_path):
                        new_size = target_path.stat().st_size
                        saved = original_size - new_size
                        total_saved_bytes += saved
                        
                        # Keep the /app format if it was there, just change extension
                        updated_stems[stem_name] = stem_path.replace(".wav", ".mp3")
                        modified = True
                        
                        # Delete original WAV
                        try:
                            source_path.unlink()
                        except Exception as e:
                            logger.error(f"Failed to delete {source_path}: {e}")
                else:
                    # Maybe it's already mp3, or it's missing on disk but exists in DB.
                    # Let's just fix the extension in the DB anyway if it was .wav so the UI doesn't break
                    updated_stems[stem_name] = stem_path.replace(".wav", ".mp3")
                    if stem_path.endswith(".wav"):
                        modified = True

            if modified:
                session.stems_json = json.dumps(updated_stems)
                db.commit()
                logger.info(f"Updated session {session.id} in database.")

        saved_mb = total_saved_bytes / (1024 * 1024)
        logger.info(f"Migration completed! Saved {saved_mb:.2f} MB of disk space.")
    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(migrate_existing_stems())
