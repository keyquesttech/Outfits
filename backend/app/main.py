from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, jobs
from .routers import insights, items, outfits, settings, suggest, wear


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    db.get_conn()  # applies the schema on first run
    jobs.start()
    yield
    jobs.stop()


app = FastAPI(
    title="Outfits",
    description="Self-hosted wardrobe manager",
    version="1.0.0",
    lifespan=lifespan,
)

# Only relevant when the Vite dev server is running on another port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (items.router, outfits.router, wear.router,
               suggest.router, insights.router, settings.router):
    app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


config.ensure_dirs()
app.mount("/photos", StaticFiles(directory=config.PHOTO_DIR), name="photos")

# index.html must never be cached: it names the hashed asset files, so a stale
# copy pins the browser to a previous build forever. The assets themselves carry
# a content hash in the filename, so they can be cached hard.
NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}

if config.STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        """Serve built files, falling back to index.html so client routes work.

        An unknown API path must say 404 rather than serve the app shell — a
        caller of a removed endpoint should hear "gone", not receive HTML.
        """
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (config.STATIC_DIR / path).resolve()
        if path and candidate.is_file() and config.STATIC_DIR.resolve() in candidate.parents:
            headers = IMMUTABLE if path.startswith("assets/") else NO_CACHE
            return FileResponse(candidate, headers=headers)
        return FileResponse(config.STATIC_DIR / "index.html", headers=NO_CACHE)
else:
    @app.get("/", include_in_schema=False)
    async def no_build():
        return JSONResponse({
            "status": "backend running",
            "note": "Frontend is not built yet. Run: cd frontend && npm install && npm run build",
            "api_docs": "/docs",
        })
