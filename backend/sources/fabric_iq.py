"""Fabric IQ client — Fabric Data Agent via its native MCP endpoint.

Auth: DefaultAzureCredential, scoped to https://api.fabric.microsoft.com/.default.
Uses the same signed-in identity (via `az login` / AzureCliCredential, or a
managed identity/service principal in other environments) as Foundry IQ,
rather than a separate interactive-browser sign-in per source.
"""

from functools import lru_cache

from backend import config
from backend.sources.base import IQResult, NotConfiguredError, describe_exception
from backend.sources.mcp_client import call_mcp_tool


@lru_cache(maxsize=1)
def _credential():
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


async def ask(question: str) -> IQResult:
    if not config.FABRIC_MCP_URL:
        raise NotConfiguredError(
            "Fabric IQ is not configured — set FABRIC_WORKSPACE_ID and FABRIC_DATA_AGENT_ID in .env."
        )
    try:
        ok, text, _ = await call_mcp_tool(
            endpoint=config.FABRIC_MCP_URL,
            credential=_credential(),
            scopes=config.FABRIC_SCOPES,
            tool_name=None,  # published data agents expose exactly one tool
            arguments={"question": question},
        )
    except Exception as exc:
        return IQResult(source="fabric-iq", ok=False, error=describe_exception(exc))
    return IQResult(source="fabric-iq", ok=ok, text=text or "No response text from Fabric IQ.",
                     error="" if ok else text)
