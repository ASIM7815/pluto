"""Configuration management for PLUTO backend"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """PLUTO Backend Settings"""
    
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
    
    # GPT-OSS Configuration
    gpt_oss_api_key: str
    gpt_oss_base_url: str = "https://api.groq.com/openai/v1"
    gpt_oss_model: str = "llama-3.3-70b-versatile"
    
    # ElevenLabs Configuration
    elevenlabs_api_key: str
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # Indian girl voice
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    
    # Filesystem Sandbox
    pluto_allowed_paths: str = "/home/user/Desktop,/home/user/Documents,/home/user/Downloads,/home/user/Projects"
    
    # Permissions
    pluto_auto_approve_safe: bool = True
    pluto_require_confirmation_dangerous: bool = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.pluto_cors_origins.split(",")]
    
    @property
    def allowed_paths_list(self) -> List[str]:
        # Expand ~ to user home
        paths = [p.strip() for p in self.pluto_allowed_paths.split(",")]
        return [os.path.expanduser(p) for p in paths]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
