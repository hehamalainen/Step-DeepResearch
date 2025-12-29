"""ReAct Agent implementation for Deep Research Showcase."""

import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

from agent.model_provider import ChatMessage, ModelProvider, ModelResponse
from agent.tools import ToolSet, ToolResult

logger = logging.getLogger(__name__)


# System prompts for different phases
DEEP_RESEARCH_SYSTEM_PROMPT = """You are an expert deep research agent. Your task is to conduct thorough, methodical research to answer complex questions and produce professional research reports.

## Core Capabilities
You have access to powerful research tools:
- **batch_web_surfer**: Efficiently search and browse multiple sources
- **web_search**: Search for specific information
- **web_browse**: Read full content from URLs
- **todo**: Track research tasks and progress
- **file_write**: Save drafts and evidence
- **file_read**: Read saved content
- **file_edit**: Make targeted edits (more efficient than full rewrites)
- **reflect**: Structured reflection on gathered evidence
- **cross_validate**: Verify claims across multiple sources

## Research Process
Follow this systematic approach:

1. **Planning**: Break down the research question into sub-questions. Use the todo tool to create a research plan.

2. **Information Gathering**: Use batch_web_surfer for broad research, web_search for specific queries. Prioritize authoritative sources (academic, official, established industry sources).

3. **Reflection & Verification**: After gathering evidence, use reflect to identify gaps and conflicts. Use cross_validate for important factual claims.

4. **Report Generation**: Write a structured report with:
   - Executive Summary
   - Key Findings
   - Methodology
   - Detailed Analysis with citations
   - Conflicts/Uncertainties
   - Recommendations

## Citation Format
Always cite sources using this format: [Title](URL)
Each factual claim should be linked to its source.

## Quality Standards
- Prefer authoritative sources (government, academic, established industry)
- Verify key claims across multiple sources
- Acknowledge uncertainty when evidence is conflicting
- Be thorough but focused on the research question

When you have completed your research and written the final report, output it within <report> tags.
"""

BASELINE_SYSTEM_PROMPT = """You are a helpful research assistant. Answer the user's question based on web search results. Provide sources for your claims and structure your response clearly."""


class AgentState:
    """State management for the ReAct agent."""
    
    def __init__(self, run_id: str):
        """Initialize agent state."""
        self.run_id = run_id
        self.messages: list[ChatMessage] = []
        self.current_phase: str = "planning"
        self.step_count: int = 0
        self.token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.tool_calls: list[dict] = []
        self.evidence: list[dict] = []
        self.claims: list[dict] = []
        self.report_drafts: list[str] = []
        self.is_complete: bool = False
        self.error: Optional[str] = None
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the history."""
        self.messages.append(message)
    
    def update_usage(self, usage: dict[str, int]) -> None:
        """Update token usage."""
        for key, value in usage.items():
            if key in self.token_usage:
                self.token_usage[key] += value


class ReActAgent:
    """ReAct (Reasoning + Acting) agent for deep research."""
    
    def __init__(
        self,
        provider: ModelProvider,
        toolset: ToolSet,
        max_steps: int = 50,
        system_prompt: Optional[str] = None,
        is_baseline: bool = False,
    ):
        """Initialize the ReAct agent."""
        self.provider = provider
        self.toolset = toolset
        self.max_steps = max_steps
        self.is_baseline = is_baseline
        
        if system_prompt:
            self.system_prompt = system_prompt
        elif is_baseline:
            self.system_prompt = BASELINE_SYSTEM_PROMPT
        else:
            self.system_prompt = DEEP_RESEARCH_SYSTEM_PROMPT
    
    async def run(
        self,
        query: str,
        state: AgentState,
        on_step: Optional[callable] = None,
    ) -> AgentState:
        """Run the agent on a research query."""
        
        # Initialize with system prompt and user query
        state.add_message(ChatMessage(role="system", content=self.system_prompt))
        state.add_message(ChatMessage(role="user", content=query))
        
        while state.step_count < self.max_steps and not state.is_complete:
            try:
                state.step_count += 1
                logger.info(f"Step {state.step_count}/{self.max_steps}")
                
                # Determine current phase based on step and todo state
                state.current_phase = self._determine_phase(state)
                
                # Get model response
                response = await self.provider.chat_completion(
                    messages=state.messages,
                    tools=self.toolset.get_all_schemas(),
                    temperature=0.7,
                    max_tokens=4000,
                )
                
                # Update token usage
                state.update_usage(response.usage)
                
                # Add assistant message to history
                state.add_message(response.message)
                
                # Check for tool calls
                if response.has_tool_calls:
                    # Execute tool calls
                    for tool_call in response.message.tool_calls:
                        tool_result = await self._execute_tool_call(
                            tool_call, state
                        )
                        
                        # Add tool result to messages
                        state.add_message(ChatMessage(
                            role="tool",
                            tool_call_id=tool_call["id"],
                            content=json.dumps(tool_result.output) if tool_result.output else tool_result.error,
                        ))
                        
                        # Track tool call
                        state.tool_calls.append({
                            "tool": tool_call["function"]["name"],
                            "args": tool_call["function"]["arguments"],
                            "success": tool_result.success,
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        
                        # Extract evidence from web results
                        if tool_result.success:
                            self._extract_evidence(tool_call, tool_result, state)
                else:
                    # No tool calls - check if report is complete
                    if response.message.content:
                        content = response.message.content
                        
                        # Check for report markers
                        if "<report>" in content and "</report>" in content:
                            state.is_complete = True
                            # Extract report content
                            start = content.index("<report>") + len("<report>")
                            end = content.index("</report>")
                            report = content[start:end].strip()
                            state.report_drafts.append(report)
                        elif response.finish_reason == "stop" and state.step_count > 5:
                            # Consider complete if model stops naturally after some work
                            if len(content) > 1000:  # Substantial response
                                state.is_complete = True
                                state.report_drafts.append(content)
                
                # Callback for progress updates
                if on_step:
                    await on_step(state)
                
            except Exception as e:
                logger.error(f"Agent step failed: {e}", exc_info=True)
                state.error = str(e)
                break
        
        # Ensure we have a final report
        if not state.report_drafts and state.messages:
            # Use last assistant message as report
            for msg in reversed(state.messages):
                if msg.role == "assistant" and msg.content:
                    state.report_drafts.append(msg.content)
                    break
        
        return state
    
    async def _execute_tool_call(
        self,
        tool_call: dict,
        state: AgentState,
    ) -> ToolResult:
        """Execute a single tool call."""
        func = tool_call["function"]
        tool_name = func["name"]
        
        try:
            args = json.loads(func["arguments"])
        except json.JSONDecodeError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Invalid JSON in tool arguments: {func['arguments']}"
            )
        
        logger.info(f"Executing tool: {tool_name}")
        
        return await self.toolset.execute(tool_name, **args)
    
    def _determine_phase(self, state: AgentState) -> str:
        """Determine the current research phase."""
        if state.step_count <= 2:
            return "planning"
        
        # Check recent tool calls
        recent_tools = [tc["tool"] for tc in state.tool_calls[-5:]]
        
        if "reflect" in recent_tools or "cross_validate" in recent_tools:
            return "reflection"
        
        if "file_write" in recent_tools or "file_edit" in recent_tools:
            if any("report" in str(tc.get("args", "")).lower() for tc in state.tool_calls[-3:]):
                return "report_generation"
        
        if any(t in recent_tools for t in ["web_search", "web_browse", "batch_web_surfer"]):
            return "information_seeking"
        
        if state.step_count > self.max_steps * 0.7:
            return "report_generation"
        
        return "information_seeking"
    
    def _extract_evidence(
        self,
        tool_call: dict,
        result: ToolResult,
        state: AgentState,
    ) -> None:
        """Extract evidence from tool results."""
        tool_name = tool_call["function"]["name"]
        
        if tool_name in ["web_search", "batch_web_surfer"]:
            output = result.output
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict):
                        # From batch_web_surfer
                        if "browsed_content" in item:
                            for content in item.get("browsed_content", []):
                                state.evidence.append({
                                    "source_url": content.get("url", ""),
                                    "source_title": content.get("title", ""),
                                    "snippet": content.get("content", "")[:500],
                                    "retrieved_at": datetime.utcnow().isoformat(),
                                })
                        # From web_search
                        elif "url" in item:
                            state.evidence.append({
                                "source_url": item.get("url", ""),
                                "source_title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "retrieved_at": datetime.utcnow().isoformat(),
                            })
        
        elif tool_name == "web_browse":
            output = result.output
            if isinstance(output, dict):
                state.evidence.append({
                    "source_url": output.get("url", ""),
                    "source_title": output.get("title", ""),
                    "snippet": output.get("content", "")[:500],
                    "retrieved_at": datetime.utcnow().isoformat(),
                })
        
        elif tool_name == "cross_validate":
            output = result.output
            if isinstance(output, dict):
                state.claims.append({
                    "text": output.get("claim", ""),
                    "status": output.get("status", "uncertain"),
                    "supporting_sources": output.get("supporting_sources", 0),
                })
