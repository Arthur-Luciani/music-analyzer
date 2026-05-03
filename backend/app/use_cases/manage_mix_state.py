import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models import MixState, MixStateUpdate, StemMixState

SUPPORTED_STEMS = ("vocals", "drums", "bass", "other")


@dataclass
class GetMixStateUseCase:
    _job_service: object

    async def execute(self, session_id: str) -> Optional[MixState]:
        session = await self._job_service.get_job(session_id)
        if session is None:
            return None

        payload = await asyncio.to_thread(self._job_service._store.get_mix_state_payload, session_id)
        if payload is None:
            return self._job_service._default_mix_state()

        try:
            return MixState.model_validate(payload)
        except Exception:
            return self._job_service._default_mix_state()


@dataclass
class SaveMixStateUseCase:
    _job_service: object

    async def execute(self, session_id: str, update: MixStateUpdate) -> Optional[MixState]:
        current = await self._job_service.get_mix_state(session_id)
        if current is None:
            return None

        persisted_state = current.apply_update(update)

        payload = {
            "per_stem": {
                stem_name: stem_state.model_dump(mode="json")
                for stem_name, stem_state in persisted_state.per_stem.items()
            },
            "master_gain": persisted_state.master_gain,
        }

        await asyncio.to_thread(
            self._job_service._store.save_mix_state_payload,
            session_id,
            payload,
            persisted_state.updated_at,
        )

        return persisted_state
