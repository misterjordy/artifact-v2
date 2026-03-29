"""FastAPI application entry point."""

from fastapi import FastAPI

from artiFACT.kernel.auth.csrf import CSRFMiddleware
from artiFACT.modules.auth_admin.router import router as auth_router
from artiFACT.modules.taxonomy.router import partials_router as taxonomy_partials_router
from artiFACT.modules.taxonomy.router import router as taxonomy_router

app = FastAPI(title="artiFACT", version="0.1.0")

app.add_middleware(CSRFMiddleware)

app.include_router(auth_router)
app.include_router(taxonomy_router)
app.include_router(taxonomy_partials_router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
