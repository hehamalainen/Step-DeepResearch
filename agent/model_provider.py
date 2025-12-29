"""Model provider abstraction for Deep Research Showcase."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A message in the chat history."""
    role: str  # system, user, assistant, tool
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        d = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class ModelResponse:
    """Response from the model."""
    message: ChatMessage
    finish_reason: str
    usage: dict[str, int] = field(default_factory=dict)
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.message.tool_calls)


class ModelProvider(ABC):
    """Abstract base class for model providers."""
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        **kwargs
    ) -> ModelResponse:
        """Perform a chat completion."""
        pass
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        **kwargs
    ) -> AsyncGenerator[ModelResponse, None]:
        """Perform a streaming chat completion."""
        pass


class OpenAIProvider(ModelProvider):
    """OpenAI-compatible model provider."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
        **kwargs
    ):
        """Initialize the OpenAI provider."""
        settings = get_settings()
        
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self.model = model
        self.default_kwargs = kwargs
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
    
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        **kwargs
    ) -> ModelResponse:
        """Perform a chat completion."""
        try:
            merged_kwargs = {**self.default_kwargs, **kwargs}
            
            api_messages = [m.to_dict() for m in messages]
            
            call_kwargs = {
                "model": self.model,
                "messages": api_messages,
                **merged_kwargs,
            }
            
            if tools:
                call_kwargs["tools"] = tools
                call_kwargs["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**call_kwargs)
            
            choice = response.choices[0]
            message = choice.message
            
            # Extract tool calls if present
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            return ModelResponse(
                message=ChatMessage(
                    role="assistant",
                    content=message.content,
                    tool_calls=tool_calls,
                ),
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            )
            
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise
    
    async def chat_completion_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        **kwargs
    ) -> AsyncGenerator[ModelResponse, None]:
        """Perform a streaming chat completion."""
        try:
            merged_kwargs = {**self.default_kwargs, **kwargs}
            
            api_messages = [m.to_dict() for m in messages]
            
            call_kwargs = {
                "model": self.model,
                "messages": api_messages,
                "stream": True,
                **merged_kwargs,
            }
            
            if tools:
                call_kwargs["tools"] = tools
                call_kwargs["tool_choice"] = "auto"
            
            stream = await self.client.chat.completions.create(**call_kwargs)
            
            accumulated_content = ""
            accumulated_tool_calls: dict[int, dict] = {}
            
            async for chunk in stream:
                if not chunk.choices:
                    continue
                
                choice = chunk.choices[0]
                delta = choice.delta
                
                # Accumulate content
                if delta.content:
                    accumulated_content += delta.content
                
                # Accumulate tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {
                                    "name": tc.function.name if tc.function else "",
                                    "arguments": "",
                                }
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                
                # Yield intermediate response
                tool_calls_list = list(accumulated_tool_calls.values()) if accumulated_tool_calls else None
                
                yield ModelResponse(
                    message=ChatMessage(
                        role="assistant",
                        content=accumulated_content if accumulated_content else None,
                        tool_calls=tool_calls_list,
                    ),
                    finish_reason=choice.finish_reason or "null",
                )
            
        except Exception as e:
            logger.error(f"Streaming chat completion failed: {e}")
            raise


def get_provider(
    engine_type: str = "deep_research",
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ModelProvider:
    """Get a model provider based on configuration."""
    settings = get_settings()
    
    if engine_type == "baseline":
        # Use alternative provider if configured
        if base_url:
            return OpenAIProvider(
                api_key=api_key or settings.alt_model_api_key,
                base_url=base_url,
                model=model_name or settings.default_model,
            )
    
    # Default to OpenAI provider
    return OpenAIProvider(
        api_key=api_key or settings.openai_api_key,
        base_url=base_url or settings.openai_base_url,
        model=model_name or settings.default_model,
    )
