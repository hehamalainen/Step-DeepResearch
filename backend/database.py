"""Database layer for Deep Research Showcase using SQLite."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from backend.config import get_settings
from backend.models import (
    AblationConfig,
    AuthorityTier,
    Claim,
    ClaimStatus,
    Evidence,
    EvaluationTask,
    PairwiseResult,
    Report,
    ReportSection,
    Run,
    RunConfig,
    RunMetrics,
    RunStatus,
    RunSummary,
    TaskSet,
    ToolEvent,
    AgentPhase,
    EngineType,
    OutputFormat,
    ToolType,
)

logger = logging.getLogger(__name__)


class Database:
    """SQLite database wrapper for async operations."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        if db_path is None:
            settings = get_settings()
            db_path = settings.data_dir / "deep_research.db"
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self) -> None:
        """Connect to the database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
    
    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    @property
    def conn(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection
    
    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        await self.conn.executescript("""
            -- Runs table
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                config TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                current_phase TEXT NOT NULL DEFAULT 'planning',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                metrics TEXT NOT NULL DEFAULT '{}',
                error_message TEXT,
                report_artifact_path TEXT,
                trace_path TEXT
            );
            
            -- Tool events table
            CREATE TABLE IF NOT EXISTS tool_events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                args TEXT NOT NULL DEFAULT '{}',
                result TEXT,
                result_file_path TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_ms INTEGER,
                error TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            -- Evidence table
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_title TEXT,
                snippet TEXT NOT NULL,
                authority_tier TEXT NOT NULL DEFAULT 'other',
                retrieved_at TEXT NOT NULL,
                tool_event_id TEXT,
                cross_validated INTEGER NOT NULL DEFAULT 0,
                validation_sources TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (tool_event_id) REFERENCES tool_events(event_id)
            );
            
            -- Claims table
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unverified',
                evidence_ids TEXT NOT NULL DEFAULT '[]',
                section TEXT,
                confidence REAL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            -- Reports table
            CREATE TABLE IF NOT EXISTS reports (
                run_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                executive_summary TEXT NOT NULL DEFAULT '',
                sections TEXT NOT NULL DEFAULT '[]',
                markdown TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
            
            -- Task sets table
            CREATE TABLE IF NOT EXISTS task_sets (
                task_set_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                tasks TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            
            -- Pairwise results table
            CREATE TABLE IF NOT EXISTS pairwise_results (
                result_id TEXT PRIMARY KEY,
                run_a_id TEXT NOT NULL,
                run_b_id TEXT NOT NULL,
                winner TEXT NOT NULL,
                scores TEXT NOT NULL,
                notes TEXT,
                evaluated_at TEXT NOT NULL,
                evaluator_id TEXT,
                FOREIGN KEY (run_a_id) REFERENCES runs(run_id),
                FOREIGN KEY (run_b_id) REFERENCES runs(run_id)
            );
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
            CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
            CREATE INDEX IF NOT EXISTS idx_tool_events_run_id ON tool_events(run_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_run_id ON evidence(run_id);
            CREATE INDEX IF NOT EXISTS idx_claims_run_id ON claims(run_id);
        """)
        await self.conn.commit()
    
    # ========================================
    # Run Operations
    # ========================================
    
    async def create_run(self, run: Run) -> Run:
        """Create a new run."""
        await self.conn.execute(
            """
            INSERT INTO runs (
                run_id, query, config, status, current_phase, created_at,
                started_at, completed_at, metrics, error_message,
                report_artifact_path, trace_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.query,
                run.config.model_dump_json(),
                run.status.value,
                run.current_phase.value,
                run.created_at.isoformat(),
                run.started_at.isoformat() if run.started_at else None,
                run.completed_at.isoformat() if run.completed_at else None,
                run.metrics.model_dump_json(),
                run.error_message,
                run.report_artifact_path,
                run.trace_path,
            )
        )
        await self.conn.commit()
        return run
    
    async def get_run(self, run_id: str) -> Optional[Run]:
        """Get a run by ID."""
        cursor = await self.conn.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run(dict(row))
    
    async def list_runs(
        self,
        status: Optional[RunStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[RunSummary]:
        """List runs with optional filtering."""
        query = "SELECT * FROM runs"
        params: list[Any] = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        
        summaries = []
        for row in rows:
            run = self._row_to_run(dict(row))
            summaries.append(RunSummary(
                run_id=run.run_id,
                query=run.query,
                status=run.status,
                engine=run.config.engine,
                current_phase=run.current_phase,
                created_at=run.created_at,
                completed_at=run.completed_at,
                citation_count=run.metrics.citation_count,
                tool_calls=run.metrics.total_tool_calls,
            ))
        
        return summaries
    
    async def update_run(self, run: Run) -> Run:
        """Update an existing run."""
        await self.conn.execute(
            """
            UPDATE runs SET
                status = ?,
                current_phase = ?,
                started_at = ?,
                completed_at = ?,
                metrics = ?,
                error_message = ?,
                report_artifact_path = ?,
                trace_path = ?
            WHERE run_id = ?
            """,
            (
                run.status.value,
                run.current_phase.value,
                run.started_at.isoformat() if run.started_at else None,
                run.completed_at.isoformat() if run.completed_at else None,
                run.metrics.model_dump_json(),
                run.error_message,
                run.report_artifact_path,
                run.trace_path,
                run.run_id,
            )
        )
        await self.conn.commit()
        return run
    
    def _row_to_run(self, row: dict) -> Run:
        """Convert a database row to a Run object."""
        config_data = json.loads(row["config"])
        metrics_data = json.loads(row["metrics"])
        
        return Run(
            run_id=row["run_id"],
            query=row["query"],
            config=RunConfig(**config_data),
            status=RunStatus(row["status"]),
            current_phase=AgentPhase(row["current_phase"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            metrics=RunMetrics(**metrics_data),
            error_message=row["error_message"],
            report_artifact_path=row["report_artifact_path"],
            trace_path=row["trace_path"],
        )
    
    # ========================================
    # Tool Event Operations
    # ========================================
    
    async def create_tool_event(self, event: ToolEvent) -> ToolEvent:
        """Create a new tool event."""
        await self.conn.execute(
            """
            INSERT INTO tool_events (
                event_id, run_id, tool, tool_name, args, result,
                result_file_path, started_at, ended_at, duration_ms, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.run_id,
                event.tool.value,
                event.tool_name,
                json.dumps(event.args),
                json.dumps(event.result) if event.result else None,
                event.result_file_path,
                event.started_at.isoformat(),
                event.ended_at.isoformat() if event.ended_at else None,
                event.duration_ms,
                event.error,
            )
        )
        await self.conn.commit()
        return event
    
    async def update_tool_event(self, event: ToolEvent) -> ToolEvent:
        """Update a tool event."""
        await self.conn.execute(
            """
            UPDATE tool_events SET
                result = ?,
                result_file_path = ?,
                ended_at = ?,
                duration_ms = ?,
                error = ?
            WHERE event_id = ?
            """,
            (
                json.dumps(event.result) if event.result else None,
                event.result_file_path,
                event.ended_at.isoformat() if event.ended_at else None,
                event.duration_ms,
                event.error,
                event.event_id,
            )
        )
        await self.conn.commit()
        return event
    
    async def get_tool_events(self, run_id: str) -> list[ToolEvent]:
        """Get all tool events for a run."""
        cursor = await self.conn.execute(
            "SELECT * FROM tool_events WHERE run_id = ? ORDER BY started_at",
            (run_id,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_tool_event(dict(row)) for row in rows]
    
    def _row_to_tool_event(self, row: dict) -> ToolEvent:
        """Convert a database row to a ToolEvent object."""
        return ToolEvent(
            event_id=row["event_id"],
            run_id=row["run_id"],
            tool=ToolType(row["tool"]),
            tool_name=row["tool_name"],
            args=json.loads(row["args"]) if row["args"] else {},
            result=json.loads(row["result"]) if row["result"] else None,
            result_file_path=row["result_file_path"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            duration_ms=row["duration_ms"],
            error=row["error"],
        )
    
    # ========================================
    # Evidence Operations
    # ========================================
    
    async def create_evidence(self, evidence: Evidence) -> Evidence:
        """Create a new evidence item."""
        await self.conn.execute(
            """
            INSERT INTO evidence (
                evidence_id, run_id, source_url, source_title, snippet,
                authority_tier, retrieved_at, tool_event_id, cross_validated,
                validation_sources
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.run_id,
                evidence.source_url,
                evidence.source_title,
                evidence.snippet,
                evidence.authority_tier.value,
                evidence.retrieved_at.isoformat(),
                evidence.tool_event_id,
                1 if evidence.cross_validated else 0,
                json.dumps(evidence.validation_sources),
            )
        )
        await self.conn.commit()
        return evidence
    
    async def get_evidence(self, run_id: str) -> list[Evidence]:
        """Get all evidence for a run."""
        cursor = await self.conn.execute(
            "SELECT * FROM evidence WHERE run_id = ? ORDER BY retrieved_at",
            (run_id,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_evidence(dict(row)) for row in rows]
    
    def _row_to_evidence(self, row: dict) -> Evidence:
        """Convert a database row to an Evidence object."""
        return Evidence(
            evidence_id=row["evidence_id"],
            run_id=row["run_id"],
            source_url=row["source_url"],
            source_title=row["source_title"],
            snippet=row["snippet"],
            authority_tier=AuthorityTier(row["authority_tier"]),
            retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
            tool_event_id=row["tool_event_id"],
            cross_validated=bool(row["cross_validated"]),
            validation_sources=json.loads(row["validation_sources"]),
        )
    
    # ========================================
    # Claim Operations
    # ========================================
    
    async def create_claim(self, claim: Claim) -> Claim:
        """Create a new claim."""
        await self.conn.execute(
            """
            INSERT INTO claims (
                claim_id, run_id, text, status, evidence_ids, section, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim.claim_id,
                claim.run_id,
                claim.text,
                claim.status.value,
                json.dumps(claim.evidence_ids),
                claim.section,
                claim.confidence,
            )
        )
        await self.conn.commit()
        return claim
    
    async def update_claim(self, claim: Claim) -> Claim:
        """Update a claim."""
        await self.conn.execute(
            """
            UPDATE claims SET
                status = ?,
                evidence_ids = ?,
                confidence = ?
            WHERE claim_id = ?
            """,
            (
                claim.status.value,
                json.dumps(claim.evidence_ids),
                claim.confidence,
                claim.claim_id,
            )
        )
        await self.conn.commit()
        return claim
    
    async def get_claims(self, run_id: str) -> list[Claim]:
        """Get all claims for a run."""
        cursor = await self.conn.execute(
            "SELECT * FROM claims WHERE run_id = ?",
            (run_id,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_claim(dict(row)) for row in rows]
    
    def _row_to_claim(self, row: dict) -> Claim:
        """Convert a database row to a Claim object."""
        return Claim(
            claim_id=row["claim_id"],
            run_id=row["run_id"],
            text=row["text"],
            status=ClaimStatus(row["status"]),
            evidence_ids=json.loads(row["evidence_ids"]),
            section=row["section"],
            confidence=row["confidence"],
        )
    
    # ========================================
    # Report Operations
    # ========================================
    
    async def save_report(self, report: Report) -> Report:
        """Save or update a report."""
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO reports (
                run_id, title, executive_summary, sections, markdown,
                created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.run_id,
                report.title,
                report.executive_summary,
                json.dumps([s.model_dump() for s in report.sections]),
                report.markdown,
                report.created_at.isoformat(),
                report.updated_at.isoformat(),
                report.version,
            )
        )
        await self.conn.commit()
        return report
    
    async def get_report(self, run_id: str) -> Optional[Report]:
        """Get a report by run ID."""
        cursor = await self.conn.execute(
            "SELECT * FROM reports WHERE run_id = ?",
            (run_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_report(dict(row))
    
    def _row_to_report(self, row: dict) -> Report:
        """Convert a database row to a Report object."""
        sections_data = json.loads(row["sections"])
        return Report(
            run_id=row["run_id"],
            title=row["title"],
            executive_summary=row["executive_summary"],
            sections=[ReportSection(**s) for s in sections_data],
            markdown=row["markdown"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            version=row["version"],
        )
    
    # ========================================
    # Task Set Operations
    # ========================================
    
    async def create_task_set(self, task_set: TaskSet) -> TaskSet:
        """Create a new task set."""
        await self.conn.execute(
            """
            INSERT INTO task_sets (
                task_set_id, name, description, tasks, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_set.task_set_id,
                task_set.name,
                task_set.description,
                json.dumps([t.model_dump() for t in task_set.tasks]),
                task_set.created_at.isoformat(),
            )
        )
        await self.conn.commit()
        return task_set
    
    async def get_task_sets(self) -> list[TaskSet]:
        """Get all task sets."""
        cursor = await self.conn.execute(
            "SELECT * FROM task_sets ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_task_set(dict(row)) for row in rows]
    
    def _row_to_task_set(self, row: dict) -> TaskSet:
        """Convert a database row to a TaskSet object."""
        tasks_data = json.loads(row["tasks"])
        return TaskSet(
            task_set_id=row["task_set_id"],
            name=row["name"],
            description=row["description"],
            tasks=[EvaluationTask(**t) for t in tasks_data],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
    
    # ========================================
    # Pairwise Evaluation Operations
    # ========================================
    
    async def create_pairwise_result(self, result: PairwiseResult) -> PairwiseResult:
        """Create a new pairwise evaluation result."""
        await self.conn.execute(
            """
            INSERT INTO pairwise_results (
                result_id, run_a_id, run_b_id, winner, scores, notes,
                evaluated_at, evaluator_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.result_id,
                result.run_a_id,
                result.run_b_id,
                result.winner,
                json.dumps(result.scores),
                result.notes,
                result.evaluated_at.isoformat(),
                result.evaluator_id,
            )
        )
        await self.conn.commit()
        return result
    
    async def get_pairwise_results(
        self,
        run_id: Optional[str] = None
    ) -> list[PairwiseResult]:
        """Get pairwise results, optionally filtered by run."""
        if run_id:
            cursor = await self.conn.execute(
                """
                SELECT * FROM pairwise_results 
                WHERE run_a_id = ? OR run_b_id = ?
                ORDER BY evaluated_at DESC
                """,
                (run_id, run_id)
            )
        else:
            cursor = await self.conn.execute(
                "SELECT * FROM pairwise_results ORDER BY evaluated_at DESC"
            )
        rows = await cursor.fetchall()
        return [self._row_to_pairwise_result(dict(row)) for row in rows]
    
    def _row_to_pairwise_result(self, row: dict) -> PairwiseResult:
        """Convert a database row to a PairwiseResult object."""
        return PairwiseResult(
            result_id=row["result_id"],
            run_a_id=row["run_a_id"],
            run_b_id=row["run_b_id"],
            winner=row["winner"],
            scores=json.loads(row["scores"]),
            notes=row["notes"],
            evaluated_at=datetime.fromisoformat(row["evaluated_at"]),
            evaluator_id=row["evaluator_id"],
        )


# Global database instance
_db: Optional[Database] = None


async def get_database() -> Database:
    """Get the database instance, initializing if necessary."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
    return _db


async def close_database() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None
