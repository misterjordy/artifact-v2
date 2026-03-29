from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="artiFACT", version="0.1.0")

@app.get("/api/v1/health")
async def health():
    # Sprint 0: just prove the stack runs
    return {"status": "healthy"}
