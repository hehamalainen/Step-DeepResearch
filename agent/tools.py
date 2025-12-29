"""Tool definitions for the Deep Research agent."""

import abc
import json
import logging
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ToolSchema:
    """Schema definition for a tool."""
    name: str
    description: str
    parameters: dict[str, Any]
    
    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(abc.ABC):
    """Base class for all agent tools."""
    
    name: str
    description: str
    
    @abc.abstractmethod
    def get_schema(self) -> ToolSchema:
        """Get the tool schema for model function calling."""
        pass
    
    @abc.abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass


class WebSearchTool(BaseTool):
    """Tool for web search using DuckDuckGo."""
    
    name = "web_search"
    description = "Search the web for information on a topic. Returns a list of relevant search results with titles, URLs, and snippets."
    
    def __init__(self):
        """Initialize the web search tool."""
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
        except ImportError:
            self.ddgs = None
            logger.warning("duckduckgo_search not installed, web search will be limited")
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range for results: 'd' (day), 'w' (week), 'm' (month), 'y' (year)",
                        "enum": ["d", "w", "m", "y"]
                    }
                },
                "required": ["query"]
            }
        )
    
    async def execute(
        self,
        query: str,
        max_results: int = 10,
        time_range: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Execute a web search."""
        try:
            if self.ddgs is None:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Web search not available (duckduckgo_search not installed)"
                )
            
            results = list(self.ddgs.text(
                query,
                max_results=max_results,
                timelimit=time_range
            ))
            
            formatted_results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]
            
            return ToolResult(
                success=True,
                output=formatted_results,
                metadata={"query": query, "result_count": len(formatted_results)}
            )
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class WebBrowseTool(BaseTool):
    """Tool for browsing and extracting content from web pages."""
    
    name = "web_browse"
    description = "Browse a web page and extract its text content. Useful for reading full articles, documentation, or any web page content."
    
    def __init__(self):
        """Initialize the web browse tool."""
        import httpx
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"
            }
        )
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to browse"
                    },
                    "extract_links": {
                        "type": "boolean",
                        "description": "Whether to extract links from the page (default: false)",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        )
    
    async def execute(
        self,
        url: str,
        extract_links: bool = False,
        **kwargs
    ) -> ToolResult:
        """Browse a web page and extract content."""
        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get main content
            main_content = soup.find("main") or soup.find("article") or soup.body
            
            if main_content:
                # Convert to markdown for cleaner output
                text = markdownify(str(main_content), heading_style="ATX")
            else:
                text = soup.get_text(separator="\n", strip=True)
            
            # Truncate if too long
            max_chars = 15000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Content truncated...]"
            
            result = {
                "url": url,
                "title": soup.title.string if soup.title else "",
                "content": text,
            }
            
            if extract_links:
                links = []
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http"):
                        links.append({
                            "text": a.get_text(strip=True),
                            "url": href
                        })
                result["links"] = links[:50]  # Limit links
            
            return ToolResult(
                success=True,
                output=result,
                metadata={"url": url, "content_length": len(text)}
            )
            
        except Exception as e:
            logger.error(f"Web browse failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class BatchWebSurferTool(BaseTool):
    """Tool for batch web searching and browsing - combines search + browse for efficiency."""
    
    name = "batch_web_surfer"
    description = """Perform batch web research: search for a query and optionally browse top results.
    This is more efficient than separate search and browse calls.
    Use this for comprehensive information gathering on a topic."""
    
    def __init__(self):
        """Initialize the batch web surfer tool."""
        self.search_tool = WebSearchTool()
        self.browse_tool = WebBrowseTool()
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of search queries to execute"
                    },
                    "browse_top_n": {
                        "type": "integer",
                        "description": "Number of top results to browse per query (default: 3)",
                        "default": 3
                    },
                    "max_results_per_query": {
                        "type": "integer",
                        "description": "Maximum search results per query (default: 5)",
                        "default": 5
                    }
                },
                "required": ["queries"]
            }
        )
    
    async def execute(
        self,
        queries: list[str],
        browse_top_n: int = 3,
        max_results_per_query: int = 5,
        **kwargs
    ) -> ToolResult:
        """Execute batch web research."""
        import asyncio
        
        all_results = []
        
        for query in queries[:5]:  # Limit to 5 queries
            # Search
            search_result = await self.search_tool.execute(
                query=query,
                max_results=max_results_per_query
            )
            
            if not search_result.success:
                continue
            
            query_result = {
                "query": query,
                "search_results": search_result.output,
                "browsed_content": []
            }
            
            # Browse top N results
            urls_to_browse = [
                r["url"] for r in search_result.output[:browse_top_n]
            ]
            
            for url in urls_to_browse:
                browse_result = await self.browse_tool.execute(url=url)
                if browse_result.success:
                    query_result["browsed_content"].append({
                        "url": url,
                        "title": browse_result.output.get("title", ""),
                        "content": browse_result.output.get("content", "")[:5000]
                    })
            
            all_results.append(query_result)
        
        return ToolResult(
            success=True,
            output=all_results,
            metadata={
                "queries_processed": len(queries),
                "total_pages_browsed": sum(
                    len(r["browsed_content"]) for r in all_results
                )
            }
        )


class TodoTool(BaseTool):
    """Tool for managing task decomposition and tracking."""
    
    name = "todo"
    description = """Manage a todo list for research task decomposition.
    Use this to break down complex research questions into smaller tasks,
    track progress, and ensure nothing is missed."""
    
    def __init__(self, context_id: str):
        """Initialize the todo tool."""
        self.context_id = context_id
        self.items: dict[str, dict] = {}
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["add", "complete", "update", "list", "clear"]
                    },
                    "item_id": {
                        "type": "string",
                        "description": "ID of the todo item (for complete/update actions)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the todo item (for add action)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the todo item"
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Parent todo ID for sub-tasks"
                    }
                },
                "required": ["action"]
            }
        )
    
    async def execute(
        self,
        action: str,
        item_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Execute a todo action."""
        try:
            if action == "add":
                if not title:
                    return ToolResult(
                        success=False,
                        output=None,
                        error="Title required for add action"
                    )
                
                import uuid
                new_id = str(uuid.uuid4())[:8]
                self.items[new_id] = {
                    "id": new_id,
                    "title": title,
                    "description": description,
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "parent_id": parent_id,
                }
                
                return ToolResult(
                    success=True,
                    output={"added": self.items[new_id]},
                    metadata={"item_id": new_id}
                )
            
            elif action == "complete":
                if not item_id or item_id not in self.items:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Item not found: {item_id}"
                    )
                
                self.items[item_id]["status"] = "completed"
                self.items[item_id]["completed_at"] = datetime.utcnow().isoformat()
                
                return ToolResult(
                    success=True,
                    output={"completed": self.items[item_id]}
                )
            
            elif action == "update":
                if not item_id or item_id not in self.items:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Item not found: {item_id}"
                    )
                
                if title:
                    self.items[item_id]["title"] = title
                if description:
                    self.items[item_id]["description"] = description
                
                return ToolResult(
                    success=True,
                    output={"updated": self.items[item_id]}
                )
            
            elif action == "list":
                items_list = list(self.items.values())
                pending = [i for i in items_list if i["status"] == "pending"]
                completed = [i for i in items_list if i["status"] == "completed"]
                
                return ToolResult(
                    success=True,
                    output={
                        "items": items_list,
                        "pending_count": len(pending),
                        "completed_count": len(completed),
                    }
                )
            
            elif action == "clear":
                count = len(self.items)
                self.items.clear()
                return ToolResult(
                    success=True,
                    output={"cleared": count}
                )
            
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            logger.error(f"Todo action failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )
    
    def get_state(self) -> dict:
        """Get current todo state for external access."""
        items_list = list(self.items.values())
        return {
            "items": items_list,
            "pending_count": len([i for i in items_list if i["status"] == "pending"]),
            "completed_count": len([i for i in items_list if i["status"] == "completed"]),
        }


class FileWriteTool(BaseTool):
    """Tool for writing content to files."""
    
    name = "file_write"
    description = "Write content to a file. Used for creating report drafts, saving evidence, etc."
    
    def __init__(self, workdir: str):
        """Initialize the file write tool."""
        import os
        self.workdir = workdir
        os.makedirs(workdir, exist_ok=True)
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "mode": {
                        "type": "string",
                        "description": "Write mode: 'write' (overwrite) or 'append'",
                        "enum": ["write", "append"],
                        "default": "write"
                    }
                },
                "required": ["filename", "content"]
            }
        )
    
    async def execute(
        self,
        filename: str,
        content: str,
        mode: str = "write",
        **kwargs
    ) -> ToolResult:
        """Write content to a file."""
        try:
            import os
            import aiofiles
            
            # Sanitize filename
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(self.workdir, safe_filename)
            
            file_mode = "w" if mode == "write" else "a"
            
            async with aiofiles.open(filepath, file_mode) as f:
                await f.write(content)
            
            return ToolResult(
                success=True,
                output={
                    "filepath": filepath,
                    "bytes_written": len(content),
                    "mode": mode
                },
                metadata={"filepath": filepath}
            )
            
        except Exception as e:
            logger.error(f"File write failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class FileReadTool(BaseTool):
    """Tool for reading content from files."""
    
    name = "file_read"
    description = "Read content from a file. Used for reading previously saved content, evidence, etc."
    
    def __init__(self, workdir: str):
        """Initialize the file read tool."""
        self.workdir = workdir
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to read"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed)"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-indexed)"
                    }
                },
                "required": ["filename"]
            }
        )
    
    async def execute(
        self,
        filename: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        **kwargs
    ) -> ToolResult:
        """Read content from a file."""
        try:
            import os
            import aiofiles
            
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(self.workdir, safe_filename)
            
            if not os.path.exists(filepath):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File not found: {filename}"
                )
            
            async with aiofiles.open(filepath, "r") as f:
                content = await f.read()
            
            lines = content.split("\n")
            
            if start_line or end_line:
                start = (start_line or 1) - 1
                end = end_line or len(lines)
                lines = lines[start:end]
                content = "\n".join(lines)
            
            return ToolResult(
                success=True,
                output={
                    "filepath": filepath,
                    "content": content,
                    "line_count": len(lines)
                }
            )
            
        except Exception as e:
            logger.error(f"File read failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class FileEditTool(BaseTool):
    """Tool for patch-based file editing."""
    
    name = "file_edit"
    description = """Edit a file using patch-based modifications.
    More efficient than full rewrites for incremental changes.
    Specify the old text to replace and the new text."""
    
    def __init__(self, workdir: str):
        """Initialize the file edit tool."""
        self.workdir = workdir
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to edit"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Text to find and replace"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text"
                    }
                },
                "required": ["filename", "old_text", "new_text"]
            }
        )
    
    async def execute(
        self,
        filename: str,
        old_text: str,
        new_text: str,
        **kwargs
    ) -> ToolResult:
        """Apply a patch-based edit to a file."""
        try:
            import os
            import aiofiles
            
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(self.workdir, safe_filename)
            
            if not os.path.exists(filepath):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File not found: {filename}"
                )
            
            async with aiofiles.open(filepath, "r") as f:
                content = await f.read()
            
            if old_text not in content:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Old text not found in file"
                )
            
            # Calculate token savings (approximate)
            old_tokens = len(content.split())
            new_content = content.replace(old_text, new_text, 1)
            edit_tokens = len(old_text.split()) + len(new_text.split())
            savings_percent = (1 - edit_tokens / old_tokens) * 100 if old_tokens > 0 else 0
            
            async with aiofiles.open(filepath, "w") as f:
                await f.write(new_content)
            
            return ToolResult(
                success=True,
                output={
                    "filepath": filepath,
                    "old_length": len(old_text),
                    "new_length": len(new_text),
                    "token_savings_percent": round(savings_percent, 1)
                },
                metadata={"token_savings_percent": savings_percent}
            )
            
        except Exception as e:
            logger.error(f"File edit failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class ReflectTool(BaseTool):
    """Tool for structured reflection on gathered evidence."""
    
    name = "reflect"
    description = """Perform structured reflection on gathered information.
    Use this to verify claims, identify gaps, check for conflicts,
    and plan next steps in the research process."""
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "Summary of current research context"
                    },
                    "question": {
                        "type": "string",
                        "description": "The reflection question to consider"
                    },
                    "evidence_summary": {
                        "type": "string",
                        "description": "Summary of relevant evidence gathered"
                    }
                },
                "required": ["context", "question"]
            }
        )
    
    async def execute(
        self,
        context: str,
        question: str,
        evidence_summary: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Perform a reflection step."""
        # This is a structured marker for reflection - the actual reflection
        # happens in the model's reasoning. This tool provides structure.
        return ToolResult(
            success=True,
            output={
                "reflection_type": "structured",
                "context": context,
                "question": question,
                "evidence_summary": evidence_summary,
                "instruction": "Consider the question in context of the evidence. Identify gaps, conflicts, or areas needing verification."
            },
            metadata={"reflection": True}
        )


class CrossValidateTool(BaseTool):
    """Tool for cross-validating claims across sources."""
    
    name = "cross_validate"
    description = """Cross-validate a claim by checking multiple sources.
    Use this to verify important factual claims before including
    them in the final report."""
    
    def __init__(self):
        """Initialize the cross-validate tool."""
        self.search_tool = WebSearchTool()
    
    def get_schema(self) -> ToolSchema:
        """Get the tool schema."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The claim to validate"
                    },
                    "original_source": {
                        "type": "string",
                        "description": "URL or description of the original source"
                    },
                    "search_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional search queries to find corroborating sources"
                    }
                },
                "required": ["claim"]
            }
        )
    
    async def execute(
        self,
        claim: str,
        original_source: Optional[str] = None,
        search_queries: Optional[list[str]] = None,
        **kwargs
    ) -> ToolResult:
        """Cross-validate a claim."""
        try:
            # Generate validation queries if not provided
            if not search_queries:
                search_queries = [
                    claim[:100],  # Use claim itself as query
                    f'verify "{claim[:50]}"',
                    f'fact check {claim[:50]}'
                ]
            
            validation_results = []
            
            for query in search_queries[:3]:
                result = await self.search_tool.execute(query=query, max_results=3)
                if result.success:
                    validation_results.extend(result.output)
            
            # Basic analysis of results
            supporting = 0
            contradicting = 0
            
            claim_lower = claim.lower()
            for result in validation_results:
                snippet_lower = result.get("snippet", "").lower()
                # Very basic heuristic - in production this would use NLP
                if any(word in snippet_lower for word in claim_lower.split()[:5]):
                    supporting += 1
            
            if supporting >= 2:
                status = "supported"
            elif supporting == 1:
                status = "partially_supported"
            else:
                status = "uncertain"
            
            return ToolResult(
                success=True,
                output={
                    "claim": claim,
                    "original_source": original_source,
                    "validation_sources": validation_results[:5],
                    "supporting_sources": supporting,
                    "status": status,
                },
                metadata={
                    "cross_validated": True,
                    "supporting_count": supporting
                }
            )
            
        except Exception as e:
            logger.error(f"Cross-validation failed: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class ToolSet:
    """Collection of tools available to the agent."""
    
    def __init__(self, context_id: str, workdir: str, ablations: Optional[dict] = None):
        """Initialize the toolset."""
        self.context_id = context_id
        self.workdir = workdir
        self.ablations = ablations or {}
        
        # Core tools (always available)
        self.tools: dict[str, BaseTool] = {
            "web_search": WebSearchTool(),
            "web_browse": WebBrowseTool(),
            "batch_web_surfer": BatchWebSurferTool(),
            "file_write": FileWriteTool(workdir),
            "file_read": FileReadTool(workdir),
        }
        
        # Ablation-controlled tools
        if self.ablations.get("enable_todo_state", True):
            self.tools["todo"] = TodoTool(context_id)
        
        if self.ablations.get("enable_patch_editing", True):
            self.tools["file_edit"] = FileEditTool(workdir)
        
        if self.ablations.get("enable_reflection", True):
            self.tools["reflect"] = ReflectTool()
            self.tools["cross_validate"] = CrossValidateTool()
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_schemas(self) -> list[dict]:
        """Get all tool schemas in OpenAI format."""
        return [tool.get_schema().to_openai_format() for tool in self.tools.values()]
    
    def list_tools(self) -> list[str]:
        """List available tool names."""
        return list(self.tools.keys())
    
    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get_tool(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                output=None,
                error=f"Unknown tool: {tool_name}"
            )
        return await tool.execute(**kwargs)
    
    def get_todo_state(self) -> Optional[dict]:
        """Get current todo state if available."""
        todo_tool = self.tools.get("todo")
        if isinstance(todo_tool, TodoTool):
            return todo_tool.get_state()
        return None
