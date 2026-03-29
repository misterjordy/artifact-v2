"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from artiFACT.kernel.auth.csrf import CSRFMiddleware
from artiFACT.modules.audit.recorder import register_subscribers as register_audit_subscribers
from artiFACT.modules.audit.router import router as audit_router
from artiFACT.modules.auth_admin.router import router as auth_router
from artiFACT.modules.facts.router import router as facts_router
from artiFACT.modules.queue.badge_counter import register_badge_subscribers
from artiFACT.modules.queue.router import router as queue_router
from artiFACT.modules.search.acronym_miner import register_subscribers as register_search_subscribers
from artiFACT.modules.search.router import partials_router as search_partials_router
from artiFACT.modules.search.router import router as search_router
from artiFACT.modules.ai_chat.router import router as ai_chat_router
from artiFACT.modules.import_pipeline.router import router as import_router
from artiFACT.modules.admin.router import router as admin_router
from artiFACT.modules.export.router import router as export_router
from artiFACT.modules.export.router import sync_router
from artiFACT.modules.signing.router import router as signing_router
from artiFACT.modules.taxonomy.router import partials_router as taxonomy_partials_router
from artiFACT.modules.taxonomy.router import router as taxonomy_router
from artiFACT.pages import router as pages_router

app = FastAPI(title="artiFACT", version="0.1.0")

app.add_middleware(CSRFMiddleware)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(taxonomy_router)
app.include_router(taxonomy_partials_router)
app.include_router(facts_router)
app.include_router(audit_router)
app.include_router(queue_router)
app.include_router(search_router)
app.include_router(search_partials_router)
app.include_router(signing_router)
app.include_router(ai_chat_router)
app.include_router(import_router)
app.include_router(export_router)
app.include_router(sync_router)
app.include_router(admin_router)
app.include_router(pages_router)

register_audit_subscribers()
register_badge_subscribers()
register_search_subscribers()


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
