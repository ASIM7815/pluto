"""Configuration management for PLUTO backend."""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """PLUTO Backend Settings."""

    # Application
    app_name: str = "PLUTO AI Assistant"
    app_version: str = "1.0.0"
    pluto_env: str = "development"
    pluto_backend_host: str = "127.0.0.1"
    pluto_backend_port: int = 8765
    pluto_log_level: str = "INFO"

    # Security
    pluto_secret_key: str = "change-this-in-production"
    pluto_cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # ---- LLM (GPT-OSS 120B) ----
    # Provider can be "groq", "openai", or "custom". The API is OpenAI-compatible.
    pluto_llm_provider: str = "groq"
    gpt_oss_base_url: str = "https://api.groq.com/openai/v1"
    gpt_oss_model: str = "openai/gpt-oss-120b"
    # Empty key => mock mode (scripted planner), so the loop runs without credentials.
    gpt_oss_api_key: str = ""
    pluto_llm_temperature: float = 0.7
    pluto_llm_max_tokens: int = 4096
    # Whether we truly believe we have a live LLM. Auto-derived.
    pluto_llm_mock_mode: bool = False

    # ---- ElevenLabs TTS ----
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Indian girl voice
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    pluto_tts_mock_mode: bool = False

    # ---- Agent loop behaviour ----
    pluto_auto_speak: bool = True       # speak the final answer
    pluto_auto_listen: bool = True      # auto-return to LISTENING after speaking
    pluto_max_iterations: int = 8       # max observe->reason loop passes per task
    pluto_stream_text: bool = False

    # ---- Filesystem Sandbox ----
    pluto_allowed_paths: str = (
        "/home/user/Desktop,/home/user/Documents,/home/user/Downloads,"
        "/home/user/Projects,/home/user/pluto,/home/user/pluto/pluto-backend"
    )

    # ---- Permissions ----
    pluto_auto_approve_safe: bool = True
    pluto_require_confirmation_dangerous: bool = True

    def model_post_init(self, __context) -> None:  # noqa: D105
        # Derive mock mode from absence of real credentials.
        self.pluto_llm_mock_mode = not bool(self.gpt_oss_api_key)
        self.pluto_tts_mock_mode = not bool(self.elevenlabs_api_key)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.pluto_cors_origins.split(",") if origin.strip()]

    @property
    def allowed_paths_list(self) -> List[str]:
        paths = [p.strip() for p in self.pluto_allowed_paths.split(",") if p.strip()]
        return [os.path.expanduser(p) for p in paths]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
