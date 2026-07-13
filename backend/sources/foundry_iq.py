"""Foundry IQ client — Azure AI Search Knowledge Base, exposed as an MCP
endpoint (`/knowledgebases/{kb}/mcp?api-version=...`).

Auth: DefaultAzureCredential against the `search.azure.com` audience — the
signed-in identity needs the "Search Index Data Reader" and "Search Service
Contributor" RBAC roles on the Azure AI Search resource (data-plane RBAC,
not just an admin API key) or the MCP endpoint returns 401 regardless of a
valid AAD token. The project connection that fronts this MCP endpoint must
be registered via the REST API or `azd ai connection create` CLI — the
Foundry Portal UI strips the `?api-version` query param and breaks the
connection (RESEARCH.md §5).

The `knowledge_base_retrieve` tool's real argument is `queries`, a JSON array
of natural-language questions (not `query`/a bare string) — confirmed via its
MCP `tools/list` inputSchema.
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
    if not config.FOUNDRY_MCP_URL:
        raise NotConfiguredError(
            "Foundry IQ is not configured — set FOUNDRY_KNOWLEDGE_BASE_NAME (and confirm "
            "AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_INDEX_NAME) in .env. Run "
            "scripts/setup_foundry_index.py to create the index + knowledge base first."
        )
    try:
        ok, text, _ = await call_mcp_tool(
            endpoint=config.FOUNDRY_MCP_URL,
            credential=_credential(),
            scopes=config.FOUNDRY_SCOPES,
            tool_name="knowledge_base_retrieve",
            arguments={"queries": [question]},
        )
    except Exception as exc:
        return IQResult(source="foundry-iq", ok=False, error=describe_exception(exc))
    return IQResult(source="foundry-iq", ok=ok, text=text or "No response text from Foundry IQ.",
                     error="" if ok else text)
