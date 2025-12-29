"""FastAPI application and routes for Deep Research Showcase."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database import close_database, get_database
from backend.models import (
    AgentPhase,
    ClaimDiff,
    CreateRunRequest,
    CreateTaskSetRequest,
    EngineType,
    EvaluationSummary,
    EvaluationTask,
    OutputFormat,
    PairwiseJudgmentRequest,
    PairwiseResult,
    Report,
    Run,
    RunComparison,
    RunConfig,
    RunMetrics,
    RunStatus,
    RunSummary,
    TaskSet,
)
from backend.websocket import manager, RunEventEmitter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    settings.ensure_data_dirs()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize database
    db = await get_database()
    logger.info("Deep Research Showcase API started")
    
    yield
    
    # Shutdown
    await close_database()
    logger.info("Deep Research Showcase API stopped")


app = FastAPI(
    title="Deep Research Showcase API",
    description="API for the Copilot Deep Research Showcase application",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# Health Check
# ========================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ========================================
# Run Endpoints
# ========================================

@app.post("/api/runs", response_model=Run)
async def create_run(request: CreateRunRequest):
    """Create a new research run."""
    db = await get_database()
    
    run = Run(
        run_id=str(uuid.uuid4()),
        query=request.query,
        config=request.config,
        status=RunStatus.PENDING,
        current_phase=AgentPhase.PLANNING,
        created_at=datetime.utcnow(),
        metrics=RunMetrics(),
    )
    
    await db.create_run(run)
    
    # Start the agent in the background
    asyncio.create_task(execute_research_run(run.run_id))
    
    return run


@app.get("/api/runs", response_model=list[RunSummary])
async def list_runs(
    status: Optional[RunStatus] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List all research runs."""
    db = await get_database()
    return await db.list_runs(status=status, limit=limit, offset=offset)


@app.get("/api/runs/{run_id}", response_model=Run)
async def get_run(run_id: str):
    """Get a specific run by ID."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/runs/{run_id}/report")
async def get_run_report(run_id: str):
    """Get the report for a run."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    report = await db.get_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


@app.get("/api/runs/{run_id}/evidence")
async def get_run_evidence(run_id: str):
    """Get all evidence for a run."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return await db.get_evidence(run_id)


@app.get("/api/runs/{run_id}/claims")
async def get_run_claims(run_id: str):
    """Get all claims for a run."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return await db.get_claims(run_id)


@app.get("/api/runs/{run_id}/tool-events")
async def get_run_tool_events(run_id: str):
    """Get all tool events for a run."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return await db.get_tool_events(run_id)


@app.get("/api/runs/{run_id}/export")
async def export_run(run_id: str, format: str = "markdown"):
    """Export a run's report and artifacts."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    report = await db.get_report(run_id)
    evidence = await db.get_evidence(run_id)
    claims = await db.get_claims(run_id)
    
    if format == "markdown":
        markdown = report.markdown if report else ""
        return JSONResponse(content={
            "format": "markdown",
            "content": markdown,
            "evidence_count": len(evidence),
            "claim_count": len(claims),
        })
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    """Cancel/delete a run."""
    db = await get_database()
    run = await db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status == RunStatus.RUNNING:
        run.status = RunStatus.CANCELLED
        run.completed_at = datetime.utcnow()
        await db.update_run(run)
    
    return {"status": "cancelled", "run_id": run_id}


# ========================================
# Comparison Endpoints
# ========================================

@app.get("/api/runs/{run_a_id}/compare/{run_b_id}", response_model=RunComparison)
async def compare_runs(run_a_id: str, run_b_id: str):
    """Compare two research runs."""
    db = await get_database()
    
    run_a = await db.get_run(run_a_id)
    run_b = await db.get_run(run_b_id)
    
    if run_a is None:
        raise HTTPException(status_code=404, detail=f"Run A not found: {run_a_id}")
    if run_b is None:
        raise HTTPException(status_code=404, detail=f"Run B not found: {run_b_id}")
    
    # Get claims for comparison
    claims_a = await db.get_claims(run_a_id)
    claims_b = await db.get_claims(run_b_id)
    
    # Create claim diff
    claims_a_texts = {c.text: c for c in claims_a}
    claims_b_texts = {c.text: c for c in claims_b}
    
    claim_diffs = []
    all_claim_texts = set(claims_a_texts.keys()) | set(claims_b_texts.keys())
    
    for text in all_claim_texts:
        claim_a = claims_a_texts.get(text)
        claim_b = claims_b_texts.get(text)
        claim_diffs.append(ClaimDiff(
            claim_text=text,
            status_a=claim_a.status if claim_a else None,
            status_b=claim_b.status if claim_b else None,
            evidence_count_a=len(claim_a.evidence_ids) if claim_a else 0,
            evidence_count_b=len(claim_b.evidence_ids) if claim_b else 0,
            in_both=claim_a is not None and claim_b is not None,
        ))
    
    # Calculate metric deltas
    metric_deltas = {
        "tool_calls": run_a.metrics.total_tool_calls - run_b.metrics.total_tool_calls,
        "tokens": run_a.metrics.total_tokens - run_b.metrics.total_tokens,
        "cost_usd": run_a.metrics.cost_estimate_usd - run_b.metrics.cost_estimate_usd,
        "latency_ms": run_a.metrics.latency_ms - run_b.metrics.latency_ms,
        "citations": run_a.metrics.citation_count - run_b.metrics.citation_count,
        "unsupported_claims": run_a.metrics.unsupported_claims - run_b.metrics.unsupported_claims,
        "reflection_steps": run_a.metrics.reflection_steps - run_b.metrics.reflection_steps,
    }
    
    # Citation comparison
    citation_comparison = {
        "run_a": run_a.metrics.citation_authority_mix,
        "run_b": run_b.metrics.citation_authority_mix,
    }
    
    return RunComparison(
        run_a=RunSummary(
            run_id=run_a.run_id,
            query=run_a.query,
            status=run_a.status,
            engine=run_a.config.engine,
            current_phase=run_a.current_phase,
            created_at=run_a.created_at,
            completed_at=run_a.completed_at,
            citation_count=run_a.metrics.citation_count,
            tool_calls=run_a.metrics.total_tool_calls,
        ),
        run_b=RunSummary(
            run_id=run_b.run_id,
            query=run_b.query,
            status=run_b.status,
            engine=run_b.config.engine,
            current_phase=run_b.current_phase,
            created_at=run_b.created_at,
            completed_at=run_b.completed_at,
            citation_count=run_b.metrics.citation_count,
            tool_calls=run_b.metrics.total_tool_calls,
        ),
        report_diff_summary="Report comparison available in claim diffs",
        claim_diffs=claim_diffs,
        metric_deltas=metric_deltas,
        citation_comparison=citation_comparison,
    )


# ========================================
# Evaluation Endpoints
# ========================================

@app.post("/api/eval/tasks", response_model=TaskSet)
async def create_task_set(request: CreateTaskSetRequest):
    """Create a new evaluation task set."""
    db = await get_database()
    
    tasks = [
        EvaluationTask(
            task_id=str(uuid.uuid4()),
            query=task.get("query", ""),
            output_format=OutputFormat(task.get("format", "report")),
            expected_criteria=task.get("criteria"),
        )
        for task in request.tasks
    ]
    
    task_set = TaskSet(
        task_set_id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        tasks=tasks,
        created_at=datetime.utcnow(),
    )
    
    await db.create_task_set(task_set)
    return task_set


@app.get("/api/eval/tasks", response_model=list[TaskSet])
async def list_task_sets():
    """List all evaluation task sets."""
    db = await get_database()
    return await db.get_task_sets()


@app.post("/api/eval/runs")
async def run_evaluation_batch(
    task_set_id: str,
    engines: list[EngineType] = [EngineType.DEEP_RESEARCH],
):
    """Run a batch evaluation across engines."""
    db = await get_database()
    
    # Get task set
    task_sets = await db.get_task_sets()
    task_set = next((ts for ts in task_sets if ts.task_set_id == task_set_id), None)
    
    if task_set is None:
        raise HTTPException(status_code=404, detail="Task set not found")
    
    # Create runs for each task x engine combination
    runs = []
    for task in task_set.tasks:
        for engine in engines:
            run = Run(
                run_id=str(uuid.uuid4()),
                query=task.query,
                config=RunConfig(
                    engine=engine,
                    output_format=task.output_format,
                ),
                status=RunStatus.PENDING,
                current_phase=AgentPhase.PLANNING,
                created_at=datetime.utcnow(),
                metrics=RunMetrics(),
            )
            await db.create_run(run)
            runs.append(run)
            
            # Start execution in background
            asyncio.create_task(execute_research_run(run.run_id))
    
    return {
        "task_set_id": task_set_id,
        "runs_created": len(runs),
        "run_ids": [r.run_id for r in runs],
    }


@app.post("/api/eval/pairwise", response_model=PairwiseResult)
async def submit_pairwise_judgment(request: PairwiseJudgmentRequest):
    """Submit a pairwise comparison judgment."""
    db = await get_database()
    
    result = PairwiseResult(
        result_id=str(uuid.uuid4()),
        run_a_id=request.run_a_id,
        run_b_id=request.run_b_id,
        winner=request.winner,
        scores={
            "a": {
                "completeness": request.completeness_a,
                "depth": request.depth_a,
                "readability": request.readability_a,
                "requirement_fit": request.requirement_fit_a,
            },
            "b": {
                "completeness": request.completeness_b,
                "depth": request.depth_b,
                "readability": request.readability_b,
                "requirement_fit": request.requirement_fit_b,
            },
        },
        notes=request.notes,
        evaluated_at=datetime.utcnow(),
    )
    
    await db.create_pairwise_result(result)
    return result


@app.get("/api/eval/results", response_model=list[PairwiseResult])
async def get_evaluation_results(run_id: Optional[str] = None):
    """Get pairwise evaluation results."""
    db = await get_database()
    return await db.get_pairwise_results(run_id)


@app.get("/api/eval/summary", response_model=EvaluationSummary)
async def get_evaluation_summary():
    """Get summary of all evaluations."""
    db = await get_database()
    results = await db.get_pairwise_results()
    
    # Calculate wins by engine
    wins = {"deep_research": 0, "baseline": 0, "tie": 0}
    scores = {"deep_research": [], "baseline": []}
    
    for result in results:
        if result.winner == "a":
            # Get engine from run
            run_a = await db.get_run(result.run_a_id)
            if run_a:
                engine = run_a.config.engine.value
                wins[engine] = wins.get(engine, 0) + 1
        elif result.winner == "b":
            run_b = await db.get_run(result.run_b_id)
            if run_b:
                engine = run_b.config.engine.value
                wins[engine] = wins.get(engine, 0) + 1
        else:
            wins["tie"] = wins.get("tie", 0) + 1
    
    return EvaluationSummary(
        total_comparisons=len(results),
        wins_by_engine=wins,
        average_scores={},  # Would need more complex calculation
        elo_ratings=None,
    )


# ========================================
# Settings Endpoints
# ========================================

@app.get("/api/settings/providers")
async def get_model_providers():
    """Get available model providers."""
    settings = get_settings()
    
    providers = []
    
    if settings.openai_api_key:
        providers.append({
            "id": "openai",
            "name": "OpenAI",
            "base_url": settings.openai_base_url,
            "default_model": settings.default_model,
            "configured": True,
        })
    
    if settings.alt_model_base_url:
        providers.append({
            "id": "alternative",
            "name": "Alternative Provider",
            "base_url": settings.alt_model_base_url,
            "default_model": None,
            "configured": bool(settings.alt_model_api_key),
        })
    
    return providers


@app.get("/api/settings/ablations")
async def get_ablation_options():
    """Get available ablation toggles."""
    return {
        "toggles": [
            {
                "id": "enable_reflection",
                "name": "Reflection & Cross-Validation",
                "description": "Enable reflection steps and cross-source validation",
                "default": True,
            },
            {
                "id": "enable_authority_ranking",
                "name": "Authority-Aware Ranking",
                "description": "Prefer authoritative sources in search results",
                "default": True,
            },
            {
                "id": "enable_todo_state",
                "name": "Todo State Tracking",
                "description": "Track task decomposition and completion",
                "default": True,
            },
            {
                "id": "enable_patch_editing",
                "name": "Patch-Based Editing",
                "description": "Use incremental edits instead of full rewrites",
                "default": True,
            },
        ]
    }


# ========================================
# Demo Scenarios Endpoint
# ========================================

@app.get("/api/scenarios")
async def get_demo_scenarios():
    """Get predefined demo scenarios."""
    return {
        "scenarios": [
            {
                "id": "adr-comparison",
                "name": "Architecture Decision Record",
                "category": "planning",
                "query": "Create an ADR comparing 3 approaches to implement real-time collaboration features in a document editing application, include risks and rollout plan.",
                "description": "Tests planning and multi-option analysis capabilities",
            },
            {
                "id": "regulation-updates",
                "name": "Regulatory Analysis",
                "category": "information_seeking",
                "query": "Find the latest AI regulation updates in the EU and US from 2024, summarize key requirements for technology companies.",
                "description": "Tests deep information seeking and synthesis",
            },
            {
                "id": "conflicting-sources",
                "name": "Claim Verification",
                "category": "verification",
                "query": "Analyze claims about the effectiveness of large language models for code generation, with evidence from peer-reviewed sources and industry benchmarks.",
                "description": "Tests cross-validation and evidence handling",
            },
            {
                "id": "client-brief",
                "name": "Professional Brief",
                "category": "reporting",
                "query": "Write a professional consulting brief on the current state of quantum computing hardware, including major players, recent milestones, and 5-year outlook.",
                "description": "Tests professional report generation",
            },
            {
                "id": "noisy-web-1",
                "name": "Health Claims Analysis",
                "category": "authority",
                "query": "Evaluate claims about the health benefits of intermittent fasting based on scientific evidence, distinguishing between peer-reviewed research and popular media.",
                "description": "Tests authority-aware ranking with noisy sources",
            },
            {
                "id": "noisy-web-2",
                "name": "Tech Product Comparison",
                "category": "authority",
                "query": "Compare the latest flagship smartphones from Apple, Samsung, and Google based on objective technical specifications and independent reviews.",
                "description": "Tests filtering SEO-heavy promotional content",
            },
            {
                "id": "security-assessment",
                "name": "Security Assessment",
                "category": "planning",
                "query": "Perform a security assessment of common authentication patterns for web applications, including OAuth 2.0, SAML, and WebAuthn.",
                "description": "Tests structured analysis with technical depth",
            },
            {
                "id": "market-analysis",
                "name": "Market Analysis",
                "category": "information_seeking",
                "query": "Analyze the current market landscape for developer productivity tools, including key players, recent funding, and emerging trends.",
                "description": "Tests market research capabilities",
            },
            {
                "id": "policy-memo",
                "name": "Policy Memo",
                "category": "reporting",
                "query": "Draft a policy memo on the implications of generative AI for software development teams, including recommendations for governance and adoption strategies.",
                "description": "Tests policy-oriented writing",
            },
            {
                "id": "literature-review",
                "name": "Literature Review",
                "category": "verification",
                "query": "Conduct a literature review on retrieval-augmented generation (RAG) techniques for large language models, focusing on 2023-2024 publications.",
                "description": "Tests academic-style synthesis",
            },
        ]
    }


# ========================================
# WebSocket Endpoint
# ========================================

@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for streaming run events."""
    await manager.connect(websocket, run_id)
    try:
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # Handle ping/pong or other client messages if needed
    except WebSocketDisconnect:
        await manager.disconnect(websocket, run_id)


@app.websocket("/ws")
async def websocket_global_endpoint(websocket: WebSocket):
    """Global WebSocket endpoint for all run events."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


# ========================================
# Agent Execution (Background Task)
# ========================================

async def execute_research_run(run_id: str) -> None:
    """Execute a research run in the background."""
    # Import here to avoid circular imports
    from agent.runner import AgentRunner
    
    db = await get_database()
    run = await db.get_run(run_id)
    
    if run is None:
        logger.error(f"Run not found: {run_id}")
        return
    
    emitter = RunEventEmitter(run_id)
    
    try:
        # Update status to running
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        await db.update_run(run)
        await emitter.run_started()
        
        # Create and run the agent
        runner = AgentRunner(run, db, emitter)
        await runner.execute()
        
        # Update status to completed
        run = await db.get_run(run_id)  # Refresh from DB
        if run and run.status == RunStatus.RUNNING:
            run.status = RunStatus.SUCCEEDED
            run.completed_at = datetime.utcnow()
            await db.update_run(run)
            await emitter.run_completed(run.report_artifact_path)
        
    except Exception as e:
        logger.error(f"Research run failed: {e}", exc_info=True)
        run = await db.get_run(run_id)
        if run:
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            await db.update_run(run)
            await emitter.run_failed(str(e))


def main():
    """Run the application."""
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.server:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
