import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.scheduler import create_scheduler, run_all_fetchers
from backend.storage import get_items, init_db

logging.basicConfig(level=logging.INFO)

_scheduler = create_scheduler()
_ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    _scheduler.start()
    yield
    _scheduler.shutdown()


app = FastAPI(title="Kotitaulu", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/items")
async def api_items():
    items = await get_items()
    grouped: dict[str, list] = {}
    for item in items:
        src = item["source"]
        grouped.setdefault(src, []).append(item)
    return JSONResponse({"sources": grouped, "total": len(items)})


@app.post("/api/refresh")
async def api_refresh():
    counts = await run_all_fetchers()
    return {"refreshed": counts}


frontend_dir = _ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
