# Plan: Unified All-IQ Chat Demo (Work IQ + Foundry IQ + Fabric IQ + Web IQ)

## Problem & Approach
Build a single chat demo that grounds an agent in all four Microsoft "IQ" sources, based on findings in `RESEARCH.md`. Confirmed decisions:
- **Orchestration:** Option C — custom FastAPI orchestrator extending the existing `workiq-demo` codebase (reuses MSAL/`azure-identity` patterns already in `utils.py`), rather than the less-mature Foundry Toolbox SDK.
- **Web IQ:** User has real waitlist access — build for real (API key auth), not a mock.
- **Fabric IQ auth:** Interactive user auth (`DefaultAzureCredential`/`InteractiveBrowserCredential`), not a service principal.
- **Foundry IQ:** User confirms the Azure AI Search index/config is already set up (semantic + vector config assumed ready).
- **UI:** New unified Streamlit chat page/app (separate from but reusing patterns/auth from `workiq-demo`), not just backend-only.

## Outstanding inputs needed from user during execution
- Exact Web IQ endpoint URL + `WEBIQ_API_KEY` (RESEARCH.md only has an inferred URL).
- Foundry IQ specifics: `AZURE_SEARCH_INDEX_NAME`, `PROJECT_ENDPOINT`, `PROJECT_RESOURCE_ID`, `AZURE_OPENAI_ENDPOINT`, embedding/chat model deployment names, and the knowledge base MCP endpoint (register via REST API/CLI, not Portal, due to the known `?api-version` stripping bug).
- Confirm Fabric data agent is published; workspace ID / data agent ID already known from RESEARCH.md.

## Architecture (Option C)
```
Streamlit Chat UI  →  FastAPI Orchestrator  →  routes per-source MCP calls:
                          ├─ Work IQ MCP    (workiq.svc.cloud.microsoft/mcp)         — WorkIQAgent.Ask scope
                          ├─ Fabric IQ MCP  (api.fabric.microsoft.com/v1/mcp/...)    — fabric .default scope, interactive auth
                          ├─ Foundry IQ MCP (aiworkshop-search-.../knowledgebases/.../mcp) — search.azure.com scope
                          └─ Web IQ         (webiq.microsoft.ai, real endpoint)      — API key auth
```
Each source keeps its own credential/session (per RESEARCH.md §8 Option C code pattern: `SCOPES` dict + `call_mcp()` helper), with a lightweight intent router deciding which source(s) to call per user message, then merging results with citations before returning to the chat UI.

## Todos
See SQL `todos` table for tracking. Summary:
1. Scaffold new project structure for the orchestrator + chat UI (new folder alongside `workiq-demo`, reusing its auth utils where possible).
2. Wire Work IQ MCP client (adapt existing `workiq-demo` MCP/auth code — no new work needed here, mostly reuse).
3. Wire Fabric IQ MCP client with interactive auth (based on RESEARCH.md §6 code sample).
4. Wire Foundry IQ (Azure AI Search Knowledge Base MCP) — collect config values from user, register project connection via REST/CLI (avoiding Portal bug), wire `MCPTool`/direct MCP client call.
5. Wire Web IQ client — collect real endpoint + API key from user, integrate `webiq` SDK or REST calls.
6. Build FastAPI orchestrator router: per-source `SCOPES`/`call_mcp()` pattern, plus a simple intent-routing layer (keyword or LLM-based) to decide which IQ source(s) to query per user message.
7. Build unified Streamlit chat page: single chat input, streams/aggregates responses from the orchestrator, shows which IQ source(s) answered + citations.
8. Add `.env`/config handling for all four sources' credentials (extend `.env.example`).
9. Manual end-to-end test: ask one question per IQ source, verify correct routing + grounded answers with citations; check error handling (e.g., Work IQ `NoPolicy`, missing config).
10. Write minimal README covering setup, required env vars, and how to run (`streamlit run` + FastAPI backend).

## Notes / Risks
- Fabric `aiassistant/openai` endpoint deprecates Aug 26, 2026 — build against the new MCP endpoint per RESEARCH.md §6.
- Foundry Portal UI bug strips `?api-version` from Foundry IQ MCP connection URL — must register via REST API/CLI.
- Work IQ MCP calls require an active billing/AI-credits policy in M365 admin center.
- Confirm Web IQ's real endpoint/API key format once user supplies them; RESEARCH.md's SDK usage snippet is a fallback reference if REST/MCP details differ.
