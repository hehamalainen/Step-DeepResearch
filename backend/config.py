"""Configuration settings for Deep Research Showcase."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Model Provider Configuration
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API Base URL"
    )
    alt_model_base_url: str = Field(default="", description="Alternative model base URL")
    alt_model_api_key: str = Field(default="", description="Alternative model API key")
    default_model: str = Field(default="gpt-4o-mini", description="Default model to use")
    
    # Server Configuration
    backend_host: str = Field(default="0.0.0.0", description="Backend server host")
    backend_port: int = Field(default=8001, description="Backend server port")
    frontend_port: int = Field(default=3000, description="Frontend dev server port")
    
    # Storage Configuration
    data_dir: Path = Field(default=Path("./data"), description="Data directory path")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/deep_research.db",
        description="Database URL"
    )
    
    # Agent Configuration
    max_agent_steps: int = Field(default=50, description="Maximum agent steps")
    max_context_tokens: int = Field(default=128000, description="Maximum context tokens")
    enable_disk_context: bool = Field(default=True, description="Enable disk-backed context")
    
    # Security Configuration
    shell_sandbox_mode: bool = Field(default=True, description="Enable shell sandbox")
    shell_allowed_commands: str = Field(
        default="python,node,grep,cat,head,tail,wc,curl",
        description="Allowed shell commands"
    )
    
    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log format"
    )
    
    # Feature Flags (Ablation Controls)
    enable_reflection: bool = Field(default=True, description="Enable reflection")
    enable_authority_ranking: bool = Field(default=True, description="Enable authority ranking")
    enable_todo_state: bool = Field(default=True, description="Enable todo state tracking")
    enable_patch_editing: bool = Field(default=True, description="Enable patch-based editing")
    
    @property
    def allowed_commands_list(self) -> list[str]:
        """Get list of allowed shell commands."""
        return [cmd.strip() for cmd in self.shell_allowed_commands.split(",")]
    
    def ensure_data_dirs(self) -> None:
        """Ensure required data directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "runs").mkdir(exist_ok=True)
        (self.data_dir / "traces").mkdir(exist_ok=True)
        (self.data_dir / "artifacts").mkdir(exist_ok=True)
        (self.data_dir / "evidence").mkdir(exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    settings = Settings()
    settings.ensure_data_dirs()
    return settings
