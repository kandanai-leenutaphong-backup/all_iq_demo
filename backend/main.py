"""All-IQ orchestrator — FastAPI app.

Run with:  uvicorn backend.main:app --reload --port 8010
"""

from fastapi import FastAPI

from backend import config
from backend.routers.chat import router as chat_router

app = FastAPI(title="All-IQ Orchestrator", version="0.1.0")
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "sources_configured": {
            "work-iq": bool(config.AZURE_TENANT_ID and config.AZURE_CLIENT_ID),
            "fabric-iq": bool(config.FABRIC_MCP_URL),
            "foundry-iq": bool(config.FOUNDRY_MCP_URL),
            "web-iq": bool(config.WEBIQ_API_KEY),
        },
    }
