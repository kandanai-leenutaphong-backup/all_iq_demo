# All-IQ Unified Chat Demo

A single Streamlit chat that grounds answers in all four Microsoft "IQ" sources:

- **Work IQ** — M365 personal productivity (mail, calendar, Teams, files) via delegated MSAL sign-in.
- **Fabric IQ** — enterprise structured data (sales, forecasts) via a published Fabric Data Agent's MCP endpoint.
- **Foundry IQ** — an Azure AI Search Knowledge Base (this demo ships with a sample "company policies" index) via MCP.
- **Web IQ** — live web grounding (news, current events) via API-key auth.

Architecture: **Option C** from `RESEARCH.md` — a custom FastAPI orchestrator (`backend/`) that keeps one
credential/session per source and does simple keyword-based intent routing, fronted by a Streamlit chat UI (`ui/`).
See `PLAN.md` for the full design rationale and `RESEARCH.md` for background on each source.

## Project layout

```
backend/
  config.py          # all env-var driven config, no secrets
  intent.py           # keyword router deciding which source(s) to call
  main.py              # FastAPI app (/health, /chat)
  routers/chat.py      # POST /chat — fans out to sources, merges results
  sources/
    work_iq.py         # delegated MSAL token passed in from the UI
    fabric_iq.py        # InteractiveBrowserCredential -> Fabric Data Agent MCP
    foundry_iq.py        # DefaultAzureCredential -> AI Search Knowledge Base MCP
    web_iq.py             # API-key REST/SDK client
ui/
  auth.py             # Work IQ device-code sign-in widget (reused pattern from ../workiq-demo)
  streamlit_app.py     # the unified chat page
scripts/
  setup_foundry_index.py   # creates the sample Foundry IQ index + uploads sample_data/policies.json
  sample_data/policies.json
```

## Setup

1. `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
2. Copy `.env.example` → `.env` (already done) and fill in the values you have. Anything left blank
   makes that source respond with a clear "not configured" error instead of crashing the app.
   - **Work IQ**: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` (same app registration as `../workiq-demo`).
   - **Fabric IQ**: `FABRIC_WORKSPACE_ID` / `FABRIC_DATA_AGENT_ID` (defaults pre-filled from `RESEARCH.md`);
     confirm the data agent is **published**. Uses interactive browser sign-in on first call.
   - **Foundry IQ**: run `python scripts/setup_foundry_index.py` once to create the index + upload sample
     policy documents, then follow the printed next steps to create the Knowledge Base and register the
     Foundry project connection **via REST API / `azd ai connection create`** — the Foundry Portal UI has a
     known bug that strips `?api-version` from the MCP connection URL (see `RESEARCH.md` §5).
   - **Web IQ**: set `WEBIQ_API_KEY` once you have waitlist access (`https://aka.ms/webiq-waitlist`).
3. Run the orchestrator: `uvicorn backend.main:app --reload --port 8010`
4. Run the UI (separate terminal): `streamlit run ui/streamlit_app.py`
5. Sign in to Work IQ from the sidebar, then ask a question. Use the "Force specific source(s)" multiselect
   to bypass auto-routing while testing a single source.

## Manual end-to-end test checklist

- [ ] Work IQ question (e.g. "What's on my calendar today?") — requires sidebar sign-in first.
- [ ] Fabric IQ question (e.g. "What were total sales last quarter?").
- [ ] Foundry IQ question (e.g. "What's our remote work policy?") — answered from the sample index.
- [ ] Web IQ question (e.g. "What's the latest news on...?").
- [ ] Check `/health` (via sidebar "Backend status") shows which sources are configured.
- [ ] Confirm a source with missing config returns a readable error instead of a stack trace
      (e.g. temporarily unset `WEBIQ_API_KEY`).
- [ ] Confirm Work IQ `NoPolicy` errors (missing billing/AI-credits policy) surface as a readable message,
      not a crash.

## Known gaps (see `RESEARCH.md` §9 for details)

- Web IQ requires waitlist access; until `WEBIQ_API_KEY` is set, that source stays "not configured".
- Foundry IQ's Knowledge Base + project connection must be finished manually per the script's printed
  next steps (Foundry Toolbox/Knowledge Base creation isn't fully scriptable via public SDKs yet).
- Fabric's `aiassistant/openai` endpoint is deprecated Aug 26, 2026 — this demo already targets the
  newer MCP endpoint instead.
