import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.models import (
    ExportJob,
    ExportRequest,
    JobState,
    MixState,
    MixStateUpdate,
    ProcessRequest,
    ProcessResponse,
    SearchResponse,
    SessionDetail,
    SessionEvent,
    SessionListResponse,
    DrumAnalysis,
    DrumCorrections,
    MarketMidiMatchResult,
)
from app.use_cases.generate_drum_midi import GenerateDrumMidiUseCase
from app.settings import settings
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
    query: str = Query(..., min_length=3, description="Search term or video URL"),
    limit: int = Query(5, ge=1, le=10),
) -> SearchResponse:
    return await asyncio.to_thread(job_service.search_candidates, query, limit=limit)


@app.post("/api/process", response_model=ProcessResponse)
async def process_track(payload: ProcessRequest, background_tasks: BackgroundTasks) -> ProcessResponse:
    search = await asyncio.to_thread(job_service.search_candidates, payload.query, limit=10)
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
        selected_track = search.candidates[0]

    job = await job_service.create_job(
        payload.query,
        selected_track=selected_track,
        target_stems=payload.target_stems,
    )
    background_tasks.add_task(job_service.run_pipeline, job.job_id)
    return ProcessResponse(
        job_id=job.job_id,
        session_id=job.session_id,
        session_code=job.session_code,
    )


@app.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(
    query: str | None = Query(default=None, min_length=1),
    status: JobState | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SessionListResponse:
    items, total = await job_service.list_sessions(
        query=query,
        status=status,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return SessionListResponse(items=items, page=page, page_size=page_size, total=total)


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    job = await job_service.get_job(session_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetail(
        session_id=job.session_id,
        job_id=job.job_id,
        session_code=job.session_code,
        track_title=job.selected_track.title if job.selected_track else None,
        artist=job.selected_track.artist if job.selected_track else None,
        status=job.state,
        created_at=job.created_at,
        updated_at=job.updated_at,
        query=job.query,
        selected_track=job.selected_track,
        target_stems=job.target_stems,
        progress=job.progress,
        message=job.message,
        stems=job.stems,
        error=job.error,
        estimated_remaining_seconds=job.estimated_remaining_seconds,
        separation_device=job.separation_device,
        master_metrics=job.master_metrics,
    )


@app.get("/api/sessions/{session_id}/events", response_model=list[SessionEvent])
async def get_session_events(session_id: str) -> list[SessionEvent]:
    events = await job_service.list_session_events(session_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return events


@app.post("/api/sessions/{session_id}/duplicate", response_model=ProcessResponse)
async def duplicate_session(session_id: str, background_tasks: BackgroundTasks) -> ProcessResponse:
    try:
        job = await job_service.duplicate_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if job is None:
        raise HTTPException(status_code=404, detail="Session not found")

    background_tasks.add_task(job_service.run_pipeline, job.job_id)
    return ProcessResponse(
        job_id=job.job_id,
        session_id=job.session_id,
        session_code=job.session_code,
    )


@app.post("/api/sessions/{session_id}/reprocess", response_model=ProcessResponse)
async def reprocess_session(session_id: str, background_tasks: BackgroundTasks) -> ProcessResponse:
    try:
        job = await job_service.reprocess_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if job is None:
        raise HTTPException(status_code=404, detail="Session not found")

    background_tasks.add_task(job_service.run_pipeline, job.job_id)
    return ProcessResponse(
        job_id=job.job_id,
        session_id=job.session_id,
        session_code=job.session_code,
    )


@app.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    deleted = await job_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/api/sessions/{session_id}/mix-state", response_model=MixState)
async def get_session_mix_state(session_id: str) -> MixState:
    mix_state = await job_service.get_mix_state(session_id)
    if mix_state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return mix_state


@app.put("/api/sessions/{session_id}/mix-state", response_model=MixState)
async def put_session_mix_state(session_id: str, payload: MixStateUpdate) -> MixState:
    mix_state = await job_service.save_mix_state(session_id, payload)
    if mix_state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return mix_state


@app.post("/api/sessions/{session_id}/exports", response_model=ExportJob)
async def create_session_export(
    session_id: str,
    payload: ExportRequest,
    background_tasks: BackgroundTasks,
) -> ExportJob:
    export_job = await job_service.create_export_job(session_id, payload.preset, payload.format)
    if export_job is None:
        raise HTTPException(status_code=404, detail="Session not found")

    background_tasks.add_task(
        job_service.run_export_pipeline,
        session_id,
        export_job.export_id,
        payload.options,
    )
    return export_job


@app.get("/api/sessions/{session_id}/exports", response_model=list[ExportJob])
async def list_session_exports(session_id: str) -> list[ExportJob]:
    export_jobs = await job_service.list_export_jobs(session_id)
    if export_jobs is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return export_jobs


@app.get("/api/sessions/{session_id}/exports/{export_id}", response_model=ExportJob)
async def get_session_export(session_id: str, export_id: str) -> ExportJob:
    export_job = await job_service.get_export_job(session_id, export_id)
    if export_job is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return export_job


@app.get("/api/sessions/{session_id}/exports/{export_id}/files/{file_name}")
async def download_export_file(session_id: str, export_id: str, file_name: str) -> FileResponse:
    export_file = await job_service.get_export_file_path(session_id, export_id, file_name)
    if export_file is None:
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(path=export_file, filename=file_name)


@app.post("/api/sessions/{session_id}/drum-analysis")
async def trigger_drum_analysis(session_id: str, background_tasks: BackgroundTasks):
    """Dispara análise do stem de bateria em background."""
    background_tasks.add_task(job_service.analyze_drum_stem, session_id)
    return {"status": "started"}


@app.get("/api/sessions/{session_id}/drum-analysis/samples")
async def get_drum_samples(session_id: str):
    """Extrai e retorna URLs para os samples de áudio da bateria."""
    analysis = await job_service.get_drum_analysis(session_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    from app.use_cases.extract_drum_samples import ExtractDrumSamplesUseCase
    use_case = ExtractDrumSamplesUseCase(settings.stems_root)
    samples = await use_case.execute(session_id, analysis)
    
    return samples


@app.get("/api/sessions/{session_id}/drum-analysis", response_model=DrumAnalysis)
async def get_drum_analysis(session_id: str):
    """Retorna análise salva ou 404 se ainda não foi executada."""
    analysis = await job_service.get_drum_analysis(session_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Drum analysis not found")
    return analysis


@app.get("/api/sessions/{session_id}/drum-analysis/market-midi", response_model=MarketMidiMatchResult)
async def get_market_midi_status(session_id: str):
    """Retorna o resultado do casamento/alinhamento de MIDI de mercado, se já
    tiver rodado. 'not_indexed' (sem aplicar nada ainda) é um estado normal,
    não um erro — não retorna 404."""
    result = await job_service.get_market_midi_status(session_id)
    if result is None:
        return MarketMidiMatchResult(status="not_indexed", applied=False, checked_at=datetime.utcnow())
    return result


@app.post("/api/sessions/{session_id}/drum-analysis/corrections", response_model=DrumAnalysis)
async def post_drum_corrections(session_id: str, payload: DrumCorrections):
    """Salva correções manuais do usuário para a análise de bateria."""
    analysis = await job_service.save_drum_corrections(session_id, payload)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Session or analysis not found")
    return analysis


@app.get("/api/sessions/{session_id}/drum-analysis/drums.mid")
async def download_drum_midi(session_id: str):
    """Download do arquivo MIDI da transcrição de bateria."""
    try:
        use_case = GenerateDrumMidiUseCase(job_service)
        path = await use_case.execute(session_id, format="midi")
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="MIDI not available. Run drum analysis first.")
        return FileResponse(
            path=str(path),
            media_type="audio/midi",
            filename="bateria.mid",
            content_disposition_type="attachment",
        )
    except Exception as e:
        logger.error(f"Error generating MIDI for {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/drum-analysis/drums.musicxml")
async def download_drum_musicxml(session_id: str):
    """Download do MusicXML para editar em MuseScore."""
    try:
        use_case = GenerateDrumMidiUseCase(job_service)
        path = await use_case.execute(session_id, format="musicxml")
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="MusicXML not available. Run drum analysis first.")
        return FileResponse(
            path=str(path),
            media_type="application/vnd.recordare.musicxml+xml",
            filename="bateria.musicxml",
            content_disposition_type="attachment",
        )
    except Exception as e:
        logger.error(f"Error generating MusicXML for {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = await job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@app.post("/api/admin/cleanup", status_code=200)
async def trigger_cleanup(days_old: int = Query(15, ge=1, le=365)) -> dict:
    older_than = datetime.utcnow() - timedelta(days=days_old)
    deleted_count = await job_service.cleanup_stale_sessions(older_than)
    return {"status": "success", "deleted_sessions": deleted_count, "days_old_threshold": days_old}


@app.get("/api/jobs/{job_id}/stems/{stem_name}.mp3")
async def get_job_stem_audio(job_id: str, stem_name: str) -> FileResponse:
    if stem_name not in {"vocals", "drums", "bass", "other"}:
        raise HTTPException(status_code=404, detail="Stem not found")

    job = await job_service.get_job(job_id)
    if job is None or not job.stems or stem_name not in job.stems:
        raise HTTPException(status_code=404, detail="Stem not found")

    raw_path = job.stems[stem_name]
    # Preferimos a localização canônica atual (settings.stems_root) — o
    # caminho absoluto salvo em job.stems pode estar obsoleto se STORAGE_ROOT
    # mudou de lugar desde que a sessão foi processada.
    canonical_file = settings.stems_root / job_id / f"{stem_name}.mp3"
    if canonical_file.is_file():
        requested_file = canonical_file.resolve()
    # Se o caminho veio de um ambiente Docker (/app/storage/...),
    # convertemos para o storage_root local.
    elif raw_path.startswith("/app/storage/"):
        relative_part = raw_path.replace("/app/storage/", "", 1)
        requested_file = (settings.storage_root / relative_part).resolve()
    else:
        requested_file = Path(raw_path).resolve()

    storage_root = settings.storage_root.resolve()

    try:
        requested_file.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid stem path") from exc

    if not requested_file.is_file():
        raise HTTPException(status_code=404, detail="Stem file is unavailable")

    return FileResponse(path=requested_file, media_type="audio/mpeg", filename=f"{stem_name}.mp3")


@app.get("/api/sessions/{session_id}/samples/{file_name}")
async def get_session_sample(session_id: str, file_name: str) -> FileResponse:
    """Serve um arquivo de sample de bateria."""
    sample_path = (settings.stems_root / session_id / "samples" / file_name).resolve()
    if not sample_path.is_file():
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Validação de segurança básica
    if not str(sample_path).startswith(str(settings.stems_root.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(path=sample_path, media_type="audio/wav")


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
