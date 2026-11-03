import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.routers import api_router, voice_router, supervisor_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(f"[INFO] {settings.APP_NAME} v{settings.VERSION} starting up...")
    print(f"[GATEWAY] Real-time Voice WebSocket: ws://{settings.HOST}:{settings.PORT}/ws/voice/{{session_id}}")
    print(f"[SUPERVISOR] Supervisor Portal WebSocket: ws://{settings.HOST}:{settings.PORT}/ws/supervisor")
    print(f"[UI] Web UI & Dashboard: http://{settings.HOST}:{settings.PORT}/")
    print(f"[DOCS] API Documentation: http://{settings.HOST}:{settings.PORT}/docs")
    print("=" * 60)
    yield
    print(f"[SHUTDOWN] {settings.APP_NAME} shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS setup for web client and external callers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(api_router)
app.include_router(voice_router)
app.include_router(supervisor_router)

# Static files mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "message": "AeroVoice AI API is active. Static UI not found.",
        "docs": "/docs",
    }
