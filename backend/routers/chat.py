"""/chat router — the single entry point the Streamlit UI calls.

Two routing modes, chosen per-request via `ChatRequest.use_agent`:
- False (default): keyword-based routing (`backend.intent.route`) fans out
  to one or more IQ sources concurrently — the original behavior.
- True: a single Microsoft Agent Framework `Agent` (backend.agent_router)
  decides which IQ source(s) to call as tools itself, then synthesizes one
  answer from whichever tool(s) it invoked.
"""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent_router import route_with_agent
from backend.intent import route
from backend.sources import fabric_iq, foundry_iq, web_iq, work_iq
from backend.sources.base import IQResult, NotConfiguredError

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    workiq_token: str | None = None
    sources: list[str] | None = None  # override auto-routing, e.g. from a UI toggle
    use_agent: bool = False  # True = let an Agent Framework agent route/call tools itself


class ChatResponse(BaseModel):
    routed_sources: list[str]
    results: list[dict]
    agent_answer: str | None = None  # set only when use_agent=True


async def _call_source(name: str, message: str, workiq_token: str | None) -> IQResult:
    try:
        if name == "work-iq":
            return await work_iq.ask(message, workiq_token or "")
        if name == "fabric-iq":
            return await fabric_iq.ask(message)
        if name == "foundry-iq":
            return await foundry_iq.ask(message)
        if name == "web-iq":
            return await web_iq.ask(message)
        return IQResult(source=name, ok=False, error=f"Unknown source: {name}")
    except NotConfiguredError as exc:
        return IQResult(source=name, ok=False, error=str(exc))
    except Exception as exc:  # keep one source's failure from breaking the whole chat turn
        return IQResult(source=name, ok=False, error=f"Unexpected error: {exc}")


def _result_dicts(results: list[IQResult]) -> list[dict]:
    return [
        {
            "source": r.source,
            "ok": r.ok,
            "text": r.text,
            "error": r.error,
            "citations": [c.__dict__ for c in r.citations],
        }
        for r in results
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if req.use_agent:
        answer, results = await route_with_agent(req.message, req.workiq_token)
        return ChatResponse(
            routed_sources=[r.source for r in results],
            results=_result_dicts(results),
            agent_answer=answer,
        )

    sources = req.sources or route(req.message)
    results = await asyncio.gather(
        *(_call_source(name, req.message, req.workiq_token) for name in sources)
    )
    return ChatResponse(routed_sources=sources, results=_result_dicts(results))
