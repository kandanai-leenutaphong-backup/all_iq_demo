"""LLM-driven tool routing via the Microsoft Agent Framework.

When the "agent mode" toggle is on (`ChatRequest.use_agent`), a single
`agent_framework.Agent` decides which IQ source(s) to call as tools itself
instead of `backend/intent.py`'s keyword-based router picking sources up
front. Each tool below is a thin wrapper around the existing
`backend/sources/*.ask()` clients, so all the hard-won auth/MCP-handshake
code (Work IQ's session handshake, Foundry IQ's RBAC-based
DefaultAzureCredential, etc.) is reused completely unchanged — only the
"which source(s) should answer this?" decision moves from a keyword router
to the LLM.

Chat client: `agent_framework.foundry.FoundryChatClient` against the same
Azure AI Foundry project (`PROJECT_ENDPOINT`) and model (`AGENT_MODEL`)
already configured for Foundry IQ, authenticated the same way
(`DefaultAzureCredential`).
"""

from functools import lru_cache

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

from backend import config
from backend.sources import fabric_iq, foundry_iq, web_iq, work_iq
from backend.sources.base import IQResult, NotConfiguredError

AGENT_INSTRUCTIONS = (
    "You are an enterprise assistant with access to four tools, each grounding "
    "answers in a different data source:\n"
    "- work_iq: the user's Microsoft 365 data (calendar, email, files, Teams).\n"
    "- fabric_iq: structured/business data hosted in Microsoft Fabric (e.g. sales, "
    "operational datasets).\n"
    "- foundry_iq: internal HR/IT/Legal policy documents.\n"
    "- web_iq: real-time public web search (news, general knowledge).\n\n"
    "Call whichever tool(s) are relevant to answer the user's question — call "
    "more than one if the question spans multiple domains. Do not guess an "
    "answer without calling a tool first if the question could be grounded in "
    "one of these sources. Synthesize a concise final answer, and mention "
    "which source(s) the information came from."
)


@lru_cache(maxsize=1)
def _credential():
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


@lru_cache(maxsize=1)
def _chat_client() -> FoundryChatClient:
    return FoundryChatClient(
        project_endpoint=config.PROJECT_ENDPOINT,
        model=config.AGENT_MODEL,
        credential=_credential(),
    )


def _build_tools(workiq_token: str | None, called: list[IQResult]):
    """Builds the four tool callables for one request, closing over the
    caller's Work IQ token (per-user, so it can't be cached across requests)
    and a shared `called` list the router uses to recover structured
    IQResult/citation data the LLM's tool-result text alone would lose.
    """

    async def work_iq_tool(query: str) -> str:
        """Ask Work IQ (Microsoft 365 Copilot) about the user's calendar, email, files, or Teams/collaboration data."""
        if not workiq_token:
            return "Work IQ unavailable: the user is not signed in — do not use this tool."
        try:
            result = await work_iq.ask(query, workiq_token)
        except NotConfiguredError as exc:
            return f"Work IQ error: {exc}"
        called.append(result)
        return result.text if result.ok else f"Work IQ error: {result.error}"

    async def fabric_iq_tool(query: str) -> str:
        """Ask Fabric IQ about structured/business data such as sales figures or operational datasets."""
        try:
            result = await fabric_iq.ask(query)
        except NotConfiguredError as exc:
            return f"Fabric IQ error: {exc}"
        called.append(result)
        return result.text if result.ok else f"Fabric IQ error: {result.error}"

    async def foundry_iq_tool(query: str) -> str:
        """Ask Foundry IQ about internal HR/IT/Legal policy documents (e.g. PTO, expense, security policy)."""
        try:
            result = await foundry_iq.ask(query)
        except NotConfiguredError as exc:
            return f"Foundry IQ error: {exc}"
        called.append(result)
        return result.text if result.ok else f"Foundry IQ error: {result.error}"

    async def web_iq_tool(query: str) -> str:
        """Search the public web for current information via Web IQ (news, general knowledge, non-internal data)."""
        try:
            result = await web_iq.ask(query)
        except NotConfiguredError as exc:
            return f"Web IQ error: {exc}"
        called.append(result)
        return result.text if result.ok else f"Web IQ error: {result.error}"

    return [work_iq_tool, fabric_iq_tool, foundry_iq_tool, web_iq_tool]


async def route_with_agent(message: str, workiq_token: str | None) -> tuple[str, list[IQResult]]:
    """Runs `message` through an Agent that can call all four IQ tools itself.

    Returns `(final_answer_text, iq_results)` where `iq_results` holds the
    IQResult (with citations) for every tool the LLM actually decided to
    call, in call order — empty if it answered without calling any tool.
    """
    called: list[IQResult] = []
    agent = Agent(
        _chat_client(),
        instructions=AGENT_INSTRUCTIONS,
        name="all-iq-router",
        tools=_build_tools(workiq_token, called),
    )
    response = await agent.run(message)
    return response.text or "", called
