"""Static file server for frontend"""
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

def setup_static_files(app):
    """Mount static file handlers"""
    frontend_dir = Path(__file__).parent.parent / "frontend"
    
    # Serve static files
    app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")
    
    # Serve HTML pages
    @app.get("/")
    async def read_root():
        return FileResponse(str(frontend_dir / "login.html"))
    
    @app.get("/{page}.html")
    async def read_page(page: str):
        file_path = frontend_dir / f"{page}.html"
        if file_path.exists():
            return FileResponse(str(file_path))
        return {"error": "Page not found"}
