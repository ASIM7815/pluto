"""PLUTO Backend - FastAPI Application"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_chat, routes_voice, routes_system, routes_tools
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: open/close shared async clients."""
    from app.voice.elevenlabs import elevenlabs_client
    from app.tools.browser import browser_manager
    from app.agent.context_manager import context_manager

    logger.info(
        "pluto_starting_local_intelligence",
        version="1.0.0",
        env=settings.pluto_env,
        mode="local-intelligence (NO external AI/API)",
        tts_mock=settings.pluto_tts_mock_mode,
        active_contexts=context_manager.get_stats()["active_sessions"],
    )
    yield
    # Shutdown: release resources gracefully.
    logger.info("pluto_shutdown")
    # No LLM client to close - we're pattern-based now!
    await elevenlabs_client.close()
    await browser_manager.close()


# Create FastAPI app
app = FastAPI(
    title="PLUTO AI Assistant Backend",
    description="Futuristic AI Desktop Assistant for Linux",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes_chat.router)
app.include_router(routes_voice.router)
app.include_router(routes_system.router)
app.include_router(routes_tools.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "PLUTO AI Assistant",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    state = brain_info()
    try:
        from app.platform import get_platform_capabilities

        platform_info = get_platform_capabilities()
    except Exception:  # noqa: BLE001
        platform_info = {"platform": "unknown"}
    return {
        "status": "healthy",
        "agent": "PLUTO",
        "mode": "local-intelligence (NO external AI/API)",
        "backend": "FastAPI",
        "environment": settings.pluto_env,
        "cost": "$0 - 100% FREE",
        "tts_mock": settings.pluto_tts_mock_mode,
        "platform": platform_info,
        "intelligence": state,
    }


def brain_info() -> dict:
    """Best-effort local-brain metadata (never raises)."""
    try:
        from app.intelligence.brain import get_brain

        brain = get_brain()
        try:
            brain.ensure_model()  # reflect the on-disk/persisted model if present
        except Exception:  # noqa: BLE001
            pass
        return {
            "engine": "local (TF-IDF + scikit-learn linear classifier)",
            "intent_model": "loaded" if brain.classifier.is_trained() else "unavailable",
            "intent_classes": len(brain.classifier.labels),
            "success_actions": brain.outcome_stats().get("success", 0),
            "failed_actions": brain.outcome_stats().get("failure", 0),
        }
    except Exception as e:  # noqa: BLE001
        return {"engine": "local", "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.pluto_backend_host,
        port=settings.pluto_backend_port,
        reload=settings.pluto_env == "development",
        log_level=settings.pluto_log_level.lower(),
    )
