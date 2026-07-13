"""Central config for the All-IQ orchestrator.

All values are read from environment variables (see ../.env.example). Nothing
here should ever hold a real secret — only names/URLs/defaults.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── Work IQ (reuses workiq-demo app registration) ────────────────────────────
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"

WORKIQ_MCP = os.getenv("WORKIQ_MCP", "https://workiq.svc.cloud.microsoft/mcp")
WORKIQ_SCOPES = ["api://workiq.svc.cloud.microsoft/WorkIQAgent.Ask"]

# ── Fabric IQ (Fabric Data Agent, MCP endpoint) ──────────────────────────────
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID", "")
FABRIC_DATA_AGENT_ID = os.getenv("FABRIC_DATA_AGENT_ID", "")
FABRIC_MCP_URL = (
    f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{FABRIC_WORKSPACE_ID}"
    f"/dataagents/{FABRIC_DATA_AGENT_ID}/agent"
    if FABRIC_WORKSPACE_ID and FABRIC_DATA_AGENT_ID
    else ""
)
FABRIC_SCOPES = ["https://api.fabric.microsoft.com/.default"]

# ── Foundry IQ (Azure AI Search Knowledge Base, MCP endpoint) ────────────────
AZURE_SEARCH_ENDPOINT = os.getenv(
    "AZURE_SEARCH_ENDPOINT", "https://aiworkshop-search-rmsgmwk472oxi.search.windows.net"
)
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY", "")
FOUNDRY_KNOWLEDGE_BASE_NAME = os.getenv("FOUNDRY_KNOWLEDGE_BASE_NAME", "")
PROJECT_ENDPOINT = os.getenv(
    "PROJECT_ENDPOINT",
    "https://aiworkshop-foundry-rmsgmwk472oxi.services.ai.azure.com/api/projects/proj-default",
)
PROJECT_RESOURCE_ID = os.getenv("PROJECT_RESOURCE_ID", "")
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT", "https://aiworkshop-foundry-rmsgmwk472oxi.openai.azure.com/"
)
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
FOUNDRY_MCP_URL = (
    f"{AZURE_SEARCH_ENDPOINT}/knowledgebases/{FOUNDRY_KNOWLEDGE_BASE_NAME}/mcp"
    f"?api-version=2026-05-01-preview"
    if FOUNDRY_KNOWLEDGE_BASE_NAME
    else ""
)
FOUNDRY_SCOPES = ["https://search.azure.com/.default"]

# ── Web IQ ────────────────────────────────────────────────────────────────────
WEBIQ_API_KEY = os.getenv("WEBIQ_API_KEY", "")
WEBIQ_BASE_URL = os.getenv("WEBIQ_BASE_URL", "https://api.microsoft.ai/v3")
WEBIQ_MCP_URL = os.getenv("WEBIQ_MCP_URL", "https://api.microsoft.ai/v3/mcp")
WEBIQ_SCOPES = ["https://api.microsoft.ai/.default"]

ORCHESTRATOR_HOST = os.getenv("ORCHESTRATOR_HOST", "127.0.0.1")
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8010"))
