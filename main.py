from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend dashboard (added in Stage 7)
# app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Returns the health status of the API along with version information.",
)
async def health_check():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "title": settings.app_title,
    }
