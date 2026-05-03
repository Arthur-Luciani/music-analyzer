from app.models import SessionListResponse, SessionSummary, JobState
from datetime import datetime
import json

items = [
    SessionSummary(
        session_id="d7b9932e-f9f9-401a-9cf0-5f5e32bdcf97",
        job_id="d7b9932e-f9f9-401a-9cf0-5f5e32bdcf97",
        session_code="MX-020",
        track_title="Sujeito Boa Praça - Cartolas (Assista em HQ)",
        artist="Cartolas !",
        status=JobState.ready,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    ) for _ in range(8)
]
resp = SessionListResponse(items=items, page=1, page_size=8, total=10)
json_str = resp.model_dump_json()
print(f"Size: {len(json_str)} bytes")
print(json_str[:100])
