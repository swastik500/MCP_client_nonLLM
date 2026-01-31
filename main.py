"""
MCP Client - Main Application Entry Point.

Production-grade Model Context Protocol client with:
- Schema-driven execution
- No LLMs in execution path
- Deterministic pipeline
- Full audit logging
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from config.settings import settings
from database.connection import init_database, close_database
from api.routes import (
    auth_router, execute_router, tools_router,
    servers_router, audit_router, health_router,
)
from discovery.service import get_discovery_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.logging.LOG_LEVEL),
    format=settings.logging.LOG_FORMAT,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Continue anyway - database might already exist
    
    # Run MCP server discovery
    try:
        discovery_service = get_discovery_service()
        discovery_service.load_config()
        
        # Run discovery in background
        results = await discovery_service.discover_all()
        
        successful = sum(1 for r in results if r.success)
        total_tools = sum(r.tools_discovered for r in results)
        logger.info(f"Discovery complete: {successful}/{len(results)} servers, {total_tools} tools")
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Disconnect from MCP servers
    from mcp.client import get_mcp_client
    await get_mcp_client().disconnect_all()
    
    # Close database connections
    await close_database()
    
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Production-grade Model Context Protocol (MCP) Client.
    
    A deterministic, schema-driven execution engine that:
    - Discovers MCP servers dynamically
    - Stores tools and schemas in a database
    - Executes tools using only schemas and extracted entities
    - Requires zero code changes to add new tools
    """,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(execute_router, prefix=settings.API_PREFIX)
app.include_router(tools_router, prefix=settings.API_PREFIX)
app.include_router(servers_router, prefix=settings.API_PREFIX)
app.include_router(audit_router, prefix=settings.API_PREFIX)

# Setup static file serving
frontend_dir = Path(__file__).parent / "frontend"
app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")


@app.get("/")
async def root():
    """Serve login page."""
    login_html = frontend_dir / "login.html"
    if login_html.exists():
        return FileResponse(str(login_html))
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api": settings.API_PREFIX,
    }


@app.get("/{page}.html")
async def serve_page(page: str):
    """Serve HTML pages."""
    page_path = frontend_dir / f"{page}.html"
    if page_path.exists():
        return FileResponse(str(page_path))
    return {"error": "Page not found"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.logging.LOG_LEVEL.lower(),
    )
