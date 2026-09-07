"""Configuration management for PLUTO backend."""
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    pluto_max_iterations: int = 10      # max observe->reason loop passes per task
    pluto_stream_text: bool = False
    pluto_session_idle_minutes: int = 120  # context/session expiry

    # ---- Browser automation ----
    # "auto" => headless only when no graphical display is available.
    pluto_browser_headless: str = "auto"
    # Path to the browser PLUTO should drive. Empty = auto-detect the user's
    # REAL installed browser (google-chrome > chromium > brave > edge) so
    # PLUTO never silently falls back to Playwright's bundled copy while a
    # real Chrome is installed on the machine.
    pluto_browser_executable: str = ""
    # Optional playwright channel hint (e.g. "chrome", "msedge"). Empty = none.
    pluto_browser_channel: str = ""
    # Persistent profile: PLUTO keeps its own Chrome profile (cookies, logins,
    # history) between runs, so "open YouTube" opens in a window that stays
    # logged in. Set false for an ephemeral browser each time.
    pluto_browser_persistent_profile: bool = True
    pluto_browser_profile_dir: str = "~/.pluto/browser-profile"

    # ---- Voice / STT ----
    pluto_stt_language: str = "en-US"

    # ---- Response style: concise | friendly | detailed ----
    # friendly (default): PLUTO is communicative - a couple of warm sentences
    # that say what it did, whether it verified the result, and what's next.
    pluto_response_style: str = "friendly"

    # ---- Messaging integration (see app/tools/messaging.py) ----
    # Executable invoked with (recipient, message) args; exit 0 = delivered.
    pluto_messaging_command: str = ""

    # ---- Filesystem Sandbox ----
    # Comma separated list of directories the file tools may touch. When empty,
    # the sandbox defaults to the PLUTO user's home directory plus the standard
    # XDG folders (Desktop/Documents/Downloads/Pictures/...), which is what a
    # desktop assistant needs while still blocking /etc, /usr, other users'
    # homes, etc. Set explicitly in .env to tighten or extend it.
    pluto_allowed_paths: str = ""

    # ---- Permissions ----
    pluto_auto_approve_safe: bool = True
    pluto_require_confirmation_dangerous: bool = True

    # ---- Memory / persistence ----
    # Persist context & actions to the local SQLite store (~/.pluto) so PLUTO
    # survives restarts and can learn from corrections. Set false for a
    # strictly stateless session.
    pluto_persist_context: bool = True

    def model_post_init(self, __context) -> None:  # noqa: D105
        # Derive mock mode from absence of real credentials.
        self.pluto_llm_mock_mode = not bool(self.gpt_oss_api_key)
        self.pluto_tts_mock_mode = not bool(self.elevenlabs_api_key)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.pluto_cors_origins.split(",") if origin.strip()]

    @property
    def allowed_paths_list(self) -> List[str]:
        """Expand the configured sandbox; empty config => dynamic home default."""
        raw = (self.pluto_allowed_paths or "").strip()
        if raw:
            configured = [p.strip() for p in raw.split(",") if p.strip()]
            return [os.path.expanduser(p) for p in configured]

        home = os.path.expanduser("~")
        folders = ["", "Desktop", "Documents", "Downloads", "Pictures",
                   "Music", "Videos", "Projects", "Templates", "Public"]
        return [os.path.join(home, f) if f else home for f in folders]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
