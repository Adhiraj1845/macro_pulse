from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.database import Base, engine
from app.models import MacroIndicator, IndicatorSnapshot, MarketAsset, AssetSnapshot  # noqa: F401
from app.routers import indicators, assets, snapshots, analytics

# ---------------------------------------------------------------------------
# Rate limiter — keyed by client IP, 60 requests/minute default
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Expose limiter on app state so routers can import and use it
app.state.limiter = limiter

# Register the 429 handler so slowapi returns clean JSON instead of a 500
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate limiting middleware (must be added before other middleware)
app.add_middleware(SlowAPIMiddleware)

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(indicators.router)
app.include_router(assets.router)
app.include_router(snapshots.router)
app.include_router(analytics.router)


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

