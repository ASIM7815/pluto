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
    from app.llm.gpt_oss import gpt_oss_client
    from app.voice.elevenlabs import elevenlabs_client
    from app.tools.browser import browser_manager
    from app.agent.context_manager import context_manager

    logger.info(
        "pluto_starting",
        version="1.0.0",
        env=settings.pluto_env,
        llm_mock=settings.pluto_llm_mock_mode,
        tts_mock=settings.pluto_tts_mock_mode,
        active_contexts=context_manager.get_stats()["active_sessions"],
    )
    yield
    # Shutdown: release resources gracefully.
    logger.info("pluto_shutdown")
    await gpt_oss_client.close()
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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": "PLUTO",
        "backend": "FastAPI",
        "environment": settings.pluto_env,
        "llm_mock": settings.pluto_llm_mock_mode,
        "tts_mock": settings.pluto_tts_mock_mode,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.pluto_backend_host,
        port=settings.pluto_backend_port,
        reload=settings.pluto_env == "development",
        log_level=settings.pluto_log_level.lower(),
    )
