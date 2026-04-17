import asyncio

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.models import ProcessRequest, ProcessResponse, SearchResponse
from app.services.jobs import job_service

app = FastAPI(title="Music Analyzer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/search", response_model=SearchResponse)
async def search_tracks(
    query: str = Query(..., min_length=3, description="Artist + song title"),
    limit: int = Query(5, ge=1, le=10),
) -> SearchResponse:
    return job_service.search_candidates(query, limit=limit)


@app.post("/api/process", response_model=ProcessResponse)
async def process_track(payload: ProcessRequest, background_tasks: BackgroundTasks) -> ProcessResponse:
    search = job_service.search_candidates(payload.query, limit=5)
    if not search.candidates:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NO_MATCHES",
                "message": "Nenhum resultado encontrado para a busca informada",
            },
        )

    selected_track = None
    if payload.selected_source_id:
        selected_track = job_service.find_candidate(payload.query, payload.selected_source_id)
        if selected_track is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_SOURCE_ID",
                    "message": "A faixa selecionada nao pertence aos resultados desta busca",
                },
            )
    else:
        if search.requires_selection:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "AMBIGUOUS_QUERY",
                    "message": "Multiplos resultados com confianca parecida. Selecione uma faixa.",
                    "recommended_source_id": search.recommended_source_id,
                    "candidates": [candidate.model_dump(mode="json") for candidate in search.candidates],
                },
            )

        selected_track = next(
            (
                candidate
                for candidate in search.candidates
                if candidate.source_id == search.recommended_source_id
            ),
            search.candidates[0],
        )

    job = await job_service.create_job(payload.query, selected_track=selected_track)
    background_tasks.add_task(job_service.run_pipeline, job.job_id)
    return ProcessResponse(job_id=job.job_id)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = await job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@app.websocket("/ws/{job_id}")
async def ws_job_updates(websocket: WebSocket, job_id: str) -> None:
    job = await job_service.get_job(job_id)
    if job is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    queue = await job_service.subscribe(job_id)
    await websocket.send_json(job.model_dump(mode="json"))

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                snapshot = await job_service.get_job(job_id)
                if snapshot is None:
                    await websocket.close(code=1011)
                    return
                await websocket.send_json(snapshot.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        await job_service.unsubscribe(job_id, queue)
