"""WebSocket manager for real-time event streaming."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional
from weakref import WeakSet

from fastapi import WebSocket, WebSocketDisconnect

from backend.models import WSEvent, WSEventType

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts events."""
    
    def __init__(self):
        """Initialize the connection manager."""
        # Map of run_id -> set of connected websockets
        self._run_connections: dict[str, set[WebSocket]] = {}
        # All active connections
        self._all_connections: set[WebSocket] = set()
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, run_id: Optional[str] = None) -> None:
        """Accept a WebSocket connection."""
        await websocket.accept()
        
        async with self._lock:
            self._all_connections.add(websocket)
            if run_id:
                if run_id not in self._run_connections:
                    self._run_connections[run_id] = set()
                self._run_connections[run_id].add(websocket)
        
        logger.info(f"WebSocket connected. Run ID: {run_id}")
        
        # Send connection confirmation
        await self.send_personal(websocket, WSEvent(
            event_type=WSEventType.CONNECTED,
            run_id=run_id or "",
            data={"message": "Connected to Deep Research Showcase"}
        ))
    
    async def disconnect(self, websocket: WebSocket, run_id: Optional[str] = None) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._all_connections.discard(websocket)
            if run_id and run_id in self._run_connections:
                self._run_connections[run_id].discard(websocket)
                if not self._run_connections[run_id]:
                    del self._run_connections[run_id]
        
        logger.info(f"WebSocket disconnected. Run ID: {run_id}")
    
    async def send_personal(self, websocket: WebSocket, event: WSEvent) -> None:
        """Send an event to a specific WebSocket."""
        try:
            await websocket.send_json(event.model_dump(mode="json"))
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
    
    async def broadcast_to_run(self, run_id: str, event: WSEvent) -> None:
        """Broadcast an event to all connections watching a run."""
        async with self._lock:
            connections = self._run_connections.get(run_id, set()).copy()
        
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._all_connections.discard(ws)
                    if run_id in self._run_connections:
                        self._run_connections[run_id].discard(ws)
    
    async def broadcast_all(self, event: WSEvent) -> None:
        """Broadcast an event to all connections."""
        async with self._lock:
            connections = self._all_connections.copy()
        
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._all_connections.discard(ws)


# Global connection manager instance
manager = ConnectionManager()


class RunEventEmitter:
    """Helper class for emitting events for a specific run."""
    
    def __init__(self, run_id: str):
        """Initialize the event emitter."""
        self.run_id = run_id
        self.manager = manager
    
    async def emit(self, event_type: WSEventType, data: dict[str, Any]) -> None:
        """Emit an event for this run."""
        event = WSEvent(
            event_type=event_type,
            run_id=self.run_id,
            timestamp=datetime.utcnow(),
            data=data
        )
        await self.manager.broadcast_to_run(self.run_id, event)
    
    async def run_started(self) -> None:
        """Emit run started event."""
        await self.emit(WSEventType.RUN_STARTED, {"message": "Research run started"})
    
    async def run_completed(self, report_path: Optional[str] = None) -> None:
        """Emit run completed event."""
        await self.emit(WSEventType.RUN_COMPLETED, {
            "message": "Research run completed",
            "report_path": report_path
        })
    
    async def run_failed(self, error: str) -> None:
        """Emit run failed event."""
        await self.emit(WSEventType.RUN_FAILED, {
            "message": "Research run failed",
            "error": error
        })
    
    async def phase_changed(self, phase: str, description: str = "") -> None:
        """Emit phase change event."""
        await self.emit(WSEventType.PHASE_CHANGED, {
            "phase": phase,
            "description": description
        })
    
    async def tool_call_started(
        self,
        event_id: str,
        tool_name: str,
        args: dict[str, Any]
    ) -> None:
        """Emit tool call started event."""
        await self.emit(WSEventType.TOOL_CALL_STARTED, {
            "event_id": event_id,
            "tool_name": tool_name,
            "args": args
        })
    
    async def tool_call_completed(
        self,
        event_id: str,
        tool_name: str,
        result_summary: str,
        duration_ms: int
    ) -> None:
        """Emit tool call completed event."""
        await self.emit(WSEventType.TOOL_CALL_COMPLETED, {
            "event_id": event_id,
            "tool_name": tool_name,
            "result_summary": result_summary,
            "duration_ms": duration_ms
        })
    
    async def tool_call_failed(
        self,
        event_id: str,
        tool_name: str,
        error: str
    ) -> None:
        """Emit tool call failed event."""
        await self.emit(WSEventType.TOOL_CALL_FAILED, {
            "event_id": event_id,
            "tool_name": tool_name,
            "error": error
        })
    
    async def evidence_found(
        self,
        evidence_id: str,
        source_url: str,
        source_title: str,
        snippet: str,
        authority_tier: str
    ) -> None:
        """Emit evidence found event."""
        await self.emit(WSEventType.EVIDENCE_FOUND, {
            "evidence_id": evidence_id,
            "source_url": source_url,
            "source_title": source_title,
            "snippet": snippet[:500],  # Truncate for WS
            "authority_tier": authority_tier
        })
    
    async def claim_extracted(
        self,
        claim_id: str,
        text: str,
        section: Optional[str] = None
    ) -> None:
        """Emit claim extracted event."""
        await self.emit(WSEventType.CLAIM_EXTRACTED, {
            "claim_id": claim_id,
            "text": text,
            "section": section
        })
    
    async def claim_verified(
        self,
        claim_id: str,
        status: str,
        evidence_count: int
    ) -> None:
        """Emit claim verified event."""
        await self.emit(WSEventType.CLAIM_VERIFIED, {
            "claim_id": claim_id,
            "status": status,
            "evidence_count": evidence_count
        })
    
    async def todo_updated(
        self,
        items: list[dict],
        completed_count: int,
        pending_count: int
    ) -> None:
        """Emit todo updated event."""
        await self.emit(WSEventType.TODO_UPDATED, {
            "items": items,
            "completed_count": completed_count,
            "pending_count": pending_count
        })
    
    async def report_draft_updated(
        self,
        markdown_preview: str,
        version: int
    ) -> None:
        """Emit report draft updated event."""
        await self.emit(WSEventType.REPORT_DRAFT_UPDATED, {
            "markdown_preview": markdown_preview[:2000],  # Truncate for WS
            "version": version
        })
    
    async def report_section_added(
        self,
        section_id: str,
        title: str,
        content_preview: str
    ) -> None:
        """Emit report section added event."""
        await self.emit(WSEventType.REPORT_SECTION_ADDED, {
            "section_id": section_id,
            "title": title,
            "content_preview": content_preview[:500]
        })
    
    async def report_finalized(self, markdown: str) -> None:
        """Emit report finalized event."""
        await self.emit(WSEventType.REPORT_FINALIZED, {
            "markdown": markdown
        })
    
    async def metrics_updated(self, metrics: dict[str, Any]) -> None:
        """Emit metrics updated event."""
        await self.emit(WSEventType.METRICS_UPDATED, metrics)
    
    async def context_spill(self, file_path: str, summary: str) -> None:
        """Emit context spill to disk event."""
        await self.emit(WSEventType.CONTEXT_SPILL, {
            "file_path": file_path,
            "summary": summary
        })
    
    async def reflection_started(self, question: str) -> None:
        """Emit reflection started event."""
        await self.emit(WSEventType.REFLECTION_STARTED, {
            "question": question
        })
    
    async def cross_validation(
        self,
        claim_id: str,
        sources: list[str],
        result: str
    ) -> None:
        """Emit cross-validation event."""
        await self.emit(WSEventType.CROSS_VALIDATION, {
            "claim_id": claim_id,
            "sources": sources,
            "result": result
        })
