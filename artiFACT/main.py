"""FastAPI application entry point."""

from fastapi import FastAPI

from artiFACT.kernel.auth.csrf import CSRFMiddleware
from artiFACT.modules.auth_admin.router import router as auth_router

app = FastAPI(title="artiFACT", version="0.1.0")

app.add_middleware(CSRFMiddleware)

app.include_router(auth_router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
