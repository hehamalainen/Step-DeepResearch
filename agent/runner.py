"""Agent runner that orchestrates the research process."""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agent.authority import evaluate_source_authority, get_authority_summary, rank_sources
from agent.model_provider import OpenAIProvider, get_provider
from agent.react_agent import AgentState, ReActAgent
from agent.tools import ToolSet

from backend.config import get_settings
from backend.database import Database
from backend.models import (
    AgentPhase,
    AuthorityTier,
    Claim,
    ClaimStatus,
    Evidence,
    Report,
    ReportSection,
    Run,
    RunMetrics,
    RunStatus,
    ToolEvent,
    ToolType,
)
from backend.websocket import RunEventEmitter

logger = logging.getLogger(__name__)


class AgentRunner:
    """Orchestrates the deep research agent execution."""
    
    def __init__(
        self,
        run: Run,
        db: Database,
        emitter: RunEventEmitter,
    ):
        """Initialize the agent runner."""
        self.run = run
        self.db = db
        self.emitter = emitter
        self.settings = get_settings()
        
        # Set up working directory
        self.workdir = Path(self.settings.data_dir) / "runs" / run.run_id
        self.workdir.mkdir(parents=True, exist_ok=True)
        
        # Get ablation config
        self.ablations = {
            "enable_reflection": run.config.ablations.enable_reflection,
            "enable_authority_ranking": run.config.ablations.enable_authority_ranking,
            "enable_todo_state": run.config.ablations.enable_todo_state,
            "enable_patch_editing": run.config.ablations.enable_patch_editing,
        }
        
        # Initialize toolset
        self.toolset = ToolSet(
            context_id=run.run_id,
            workdir=str(self.workdir),
            ablations=self.ablations,
        )
        
        # Initialize model provider
        self.provider = get_provider(
            engine_type=run.config.engine.value,
            model_name=run.config.model_name,
            base_url=run.config.model_base_url,
        )
        
        # Initialize agent
        is_baseline = run.config.engine.value == "baseline"
        self.agent = ReActAgent(
            provider=self.provider,
            toolset=self.toolset,
            max_steps=run.config.max_steps,
            is_baseline=is_baseline,
        )
        
        # Metrics tracking
        self.start_time: Optional[datetime] = None
        self.tool_event_count = 0
        self.patch_edit_savings: list[float] = []
    
    async def execute(self) -> None:
        """Execute the research run."""
        self.start_time = datetime.utcnow()
        
        # Create agent state
        state = AgentState(run_id=self.run.run_id)
        
        try:
            # Emit phase change
            await self.emitter.phase_changed("planning", "Breaking down research question")
            
            # Run the agent
            final_state = await self.agent.run(
                query=self.run.query,
                state=state,
                on_step=self._on_step,
            )
            
            # Process results
            await self._process_results(final_state)
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            self.run.error_message = str(e)
            self.run.status = RunStatus.FAILED
            await self.db.update_run(self.run)
            raise
    
    async def _on_step(self, state: AgentState) -> None:
        """Callback for each agent step."""
        # Update phase
        if state.current_phase != self.run.current_phase.value:
            self.run.current_phase = AgentPhase(state.current_phase)
            await self.db.update_run(self.run)
            await self.emitter.phase_changed(
                state.current_phase,
                f"Step {state.step_count}/{self.agent.max_steps}"
            )
        
        # Process new tool calls
        for tool_call in state.tool_calls[self.tool_event_count:]:
            await self._record_tool_event(tool_call)
            self.tool_event_count += 1
        
        # Update todo state if available
        todo_state = self.toolset.get_todo_state()
        if todo_state:
            await self.emitter.todo_updated(
                items=todo_state["items"],
                completed_count=todo_state["completed_count"],
                pending_count=todo_state["pending_count"],
            )
        
        # Update metrics
        await self._update_metrics(state)
    
    async def _record_tool_event(self, tool_call: dict) -> None:
        """Record a tool event to the database."""
        tool_name = tool_call.get("tool", "unknown")
        
        # Map tool name to ToolType
        tool_type_map = {
            "web_search": ToolType.WEB_SEARCH,
            "web_browse": ToolType.WEB_BROWSE,
            "batch_web_surfer": ToolType.WEB_SEARCH,
            "file_read": ToolType.FILE_READ,
            "file_write": ToolType.FILE_WRITE,
            "file_edit": ToolType.FILE_EDIT,
            "todo": ToolType.TODO,
            "shell": ToolType.SHELL,
        }
        
        tool_type = tool_type_map.get(tool_name, ToolType.WEB_SEARCH)
        
        event = ToolEvent(
            event_id=str(uuid.uuid4()),
            run_id=self.run.run_id,
            tool=tool_type,
            tool_name=tool_name,
            args=json.loads(tool_call.get("args", "{}")) if isinstance(tool_call.get("args"), str) else {},
            started_at=datetime.fromisoformat(tool_call.get("timestamp", datetime.utcnow().isoformat())),
            ended_at=datetime.utcnow(),
        )
        
        await self.db.create_tool_event(event)
        
        # Emit WebSocket event
        await self.emitter.tool_call_completed(
            event_id=event.event_id,
            tool_name=tool_name,
            result_summary=f"Tool {tool_name} completed",
            duration_ms=0,
        )
    
    async def _update_metrics(self, state: AgentState) -> None:
        """Update run metrics."""
        end_time = datetime.utcnow()
        latency_ms = int((end_time - self.start_time).total_seconds() * 1000) if self.start_time else 0
        
        # Count tool calls by type
        tool_calls_by_type: dict[str, int] = {}
        for tc in state.tool_calls:
            tool = tc.get("tool", "unknown")
            tool_calls_by_type[tool] = tool_calls_by_type.get(tool, 0) + 1
        
        # Count reflections
        reflection_steps = tool_calls_by_type.get("reflect", 0)
        cross_validation_events = tool_calls_by_type.get("cross_validate", 0)
        
        # Calculate patch edit savings
        avg_savings = sum(self.patch_edit_savings) / len(self.patch_edit_savings) if self.patch_edit_savings else None
        
        # Estimate cost (simplified - would need actual token counts and pricing)
        total_tokens = state.token_usage.get("total_tokens", 0)
        cost_estimate = total_tokens * 0.00001  # Very rough estimate
        
        self.run.metrics = RunMetrics(
            total_tool_calls=len(state.tool_calls),
            tool_calls_by_type=tool_calls_by_type,
            total_tokens=total_tokens,
            prompt_tokens=state.token_usage.get("prompt_tokens", 0),
            completion_tokens=state.token_usage.get("completion_tokens", 0),
            cost_estimate_usd=cost_estimate,
            latency_ms=latency_ms,
            reflection_steps=reflection_steps,
            cross_validation_events=cross_validation_events,
            patch_edit_savings_percent=avg_savings,
        )
        
        await self.db.update_run(self.run)
        await self.emitter.metrics_updated(self.run.metrics.model_dump())
    
    async def _process_results(self, state: AgentState) -> None:
        """Process the final results from the agent."""
        # Extract and save evidence
        await self._save_evidence(state)
        
        # Extract and save claims
        await self._save_claims(state)
        
        # Generate and save report
        await self._save_report(state)
        
        # Final metrics update
        await self._update_metrics(state)
        
        # Update authority stats
        await self._update_authority_stats()
    
    async def _save_evidence(self, state: AgentState) -> None:
        """Save evidence items to database."""
        for evidence_data in state.evidence:
            url = evidence_data.get("source_url", "")
            
            # Evaluate authority if enabled
            if self.ablations.get("enable_authority_ranking", True):
                authority = evaluate_source_authority(url)
                tier = AuthorityTier(authority.tier)
            else:
                tier = AuthorityTier.OTHER
            
            evidence = Evidence(
                evidence_id=str(uuid.uuid4()),
                run_id=self.run.run_id,
                source_url=url,
                source_title=evidence_data.get("source_title", ""),
                snippet=evidence_data.get("snippet", ""),
                authority_tier=tier,
                retrieved_at=datetime.fromisoformat(evidence_data.get("retrieved_at", datetime.utcnow().isoformat())),
            )
            
            await self.db.create_evidence(evidence)
            
            await self.emitter.evidence_found(
                evidence_id=evidence.evidence_id,
                source_url=evidence.source_url,
                source_title=evidence.source_title or "",
                snippet=evidence.snippet,
                authority_tier=evidence.authority_tier.value,
            )
        
        # Update citation count
        self.run.metrics.citation_count = len(state.evidence)
        await self.db.update_run(self.run)
    
    async def _save_claims(self, state: AgentState) -> None:
        """Save extracted claims to database."""
        for claim_data in state.claims:
            status_map = {
                "supported": ClaimStatus.SUPPORTED,
                "refuted": ClaimStatus.REFUTED,
                "uncertain": ClaimStatus.UNCERTAIN,
                "partially_supported": ClaimStatus.UNCERTAIN,
            }
            
            claim = Claim(
                claim_id=str(uuid.uuid4()),
                run_id=self.run.run_id,
                text=claim_data.get("text", ""),
                status=status_map.get(claim_data.get("status", ""), ClaimStatus.UNVERIFIED),
            )
            
            await self.db.create_claim(claim)
            
            await self.emitter.claim_extracted(
                claim_id=claim.claim_id,
                text=claim.text,
            )
    
    async def _save_report(self, state: AgentState) -> None:
        """Save the generated report."""
        if not state.report_drafts:
            return
        
        # Use the last (final) report draft
        markdown = state.report_drafts[-1]
        
        # Parse sections from markdown
        sections = self._parse_report_sections(markdown)
        
        # Extract executive summary
        exec_summary = ""
        for section in sections:
            if "summary" in section["title"].lower() or "executive" in section["title"].lower():
                exec_summary = section["content"][:500]
                break
        
        # Create title from query
        title = f"Research Report: {self.run.query[:100]}"
        
        report = Report(
            run_id=self.run.run_id,
            title=title,
            executive_summary=exec_summary,
            sections=[
                ReportSection(
                    id=s["id"],
                    title=s["title"],
                    content=s["content"],
                    order=i,
                    claims=[],
                )
                for i, s in enumerate(sections)
            ],
            markdown=markdown,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        await self.db.save_report(report)
        
        # Save to file
        report_path = self.workdir / "report.md"
        with open(report_path, "w") as f:
            f.write(markdown)
        
        self.run.report_artifact_path = str(report_path)
        await self.db.update_run(self.run)
        
        await self.emitter.report_finalized(markdown)
    
    def _parse_report_sections(self, markdown: str) -> list[dict]:
        """Parse markdown into sections."""
        sections = []
        current_section = None
        current_content = []
        
        for line in markdown.split("\n"):
            # Check for headers
            if line.startswith("# "):
                if current_section:
                    sections.append({
                        "id": str(uuid.uuid4())[:8],
                        "title": current_section,
                        "content": "\n".join(current_content).strip(),
                    })
                current_section = line[2:].strip()
                current_content = []
            elif line.startswith("## "):
                if current_section:
                    sections.append({
                        "id": str(uuid.uuid4())[:8],
                        "title": current_section,
                        "content": "\n".join(current_content).strip(),
                    })
                current_section = line[3:].strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Add last section
        if current_section:
            sections.append({
                "id": str(uuid.uuid4())[:8],
                "title": current_section,
                "content": "\n".join(current_content).strip(),
            })
        
        # If no sections found, create a single section
        if not sections:
            sections.append({
                "id": str(uuid.uuid4())[:8],
                "title": "Research Findings",
                "content": markdown,
            })
        
        return sections
    
    async def _update_authority_stats(self) -> None:
        """Update citation authority statistics."""
        evidence = await self.db.get_evidence(self.run.run_id)
        
        authority_mix: dict[str, int] = {}
        for e in evidence:
            tier = e.authority_tier.value
            authority_mix[tier] = authority_mix.get(tier, 0) + 1
        
        self.run.metrics.citation_authority_mix = authority_mix
        
        # Count unsupported claims
        claims = await self.db.get_claims(self.run.run_id)
        unsupported = sum(1 for c in claims if not c.evidence_ids)
        self.run.metrics.unsupported_claims = unsupported
        
        await self.db.update_run(self.run)
