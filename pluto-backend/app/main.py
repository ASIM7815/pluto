"""PLUTO Backend - FastAPI Application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api import routes_chat, routes_voice, routes_system

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("pluto_starting", version="1.0.0", env=settings.pluto_env)
    yield
    # Shutdown
    logger.info("pluto_shutdown")


# Create FastAPI app
app = FastAPI(
    title="PLUTO AI Assistant Backend",
    description="Futuristic AI Desktop Assistant for Linux",
    version="1.0.0",
    lifespan=lifespan
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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "PLUTO AI Assistant",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": "PLUTO",
        "backend": "FastAPI",
        "environment": settings.pluto_env
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.pluto_backend_host,
        port=settings.pluto_backend_port,
        reload=settings.pluto_env == "development",
        log_level=settings.pluto_log_level.lower()
    )
