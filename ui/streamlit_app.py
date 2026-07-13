"""Unified All-IQ Chat — single chat page grounded in Work IQ, Fabric IQ,
Foundry IQ, and Web IQ via the FastAPI orchestrator (backend/main.py).

Run:
    uvicorn backend.main:app --reload --port 8010   # in one terminal
    streamlit run ui/streamlit_app.py                # in another
"""

import os
import sys

# Allow `import backend` / `import ui.auth` regardless of the cwd Streamlit
# was launched from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import streamlit as st

from backend import config
from ui.auth import is_workiq_authenticated, workiq_sign_in_widget

st.set_page_config(page_title="All-IQ Chat", page_icon="🧭", layout="wide")

ORCHESTRATOR_URL = f"http://{config.ORCHESTRATOR_HOST}:{config.ORCHESTRATOR_PORT}"

SOURCE_LABELS = {
    "work-iq": "🧠 Work IQ",
    "fabric-iq": "📊 Fabric IQ",
    "foundry-iq": "📚 Foundry IQ",
    "web-iq": "🌐 Web IQ",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧭 All-IQ Chat")
    st.caption("Work IQ · Fabric IQ · Foundry IQ · Web IQ — one chat, four sources")
    st.divider()

    st.subheader("Work IQ sign-in")
    st.caption("Required for M365/personal-productivity questions.")
    if is_workiq_authenticated():
        st.success("✅ Signed in")
        if st.button("Sign out", use_container_width=True, key="wiq_signout"):
            for k in ["workiq_token"]:
                st.session_state.pop(k, None)
            st.rerun()
    else:
        workiq_sign_in_widget()

    st.divider()
    st.subheader("Routing mode")
    use_agent = st.toggle(
        "🤖 Let the AI route to tools itself",
        value=False,
        help="On: a single Microsoft Agent Framework agent decides which IQ source(s) "
             "to call as tools and writes the final answer. Off: keyword-based routing "
             "fans out to source(s) and shows each source's raw grounded answer.",
    )

    st.divider()
    st.subheader("Source overrides")
    if use_agent:
        st.caption("Disabled while AI routing is on — the agent picks its own tool(s).")
        manual_sources = []
    else:
        st.caption("Leave all unchecked to auto-route by keyword.")
        manual_sources = st.multiselect(
            "Force specific source(s)",
            options=list(SOURCE_LABELS),
            format_func=lambda s: SOURCE_LABELS[s],
        )

    st.divider()
    with st.expander("Backend status"):
        try:
            r = httpx.get(f"{ORCHESTRATOR_URL}/health", timeout=5)
            st.json(r.json())
        except Exception as exc:
            st.error(f"Orchestrator unreachable at {ORCHESTRATOR_URL}: {exc}")
            st.caption("Start it with: uvicorn backend.main:app --reload --port 8010")

# ── Sample questions (one per IQ source, aligned to the demo's sample data) ──

SAMPLE_QUESTIONS = {
    "work-iq": [
        "What's on my calendar today?",
        "Summarize my unread emails from this week.",
    ],
    "fabric-iq": [
        "What were total sales last quarter?",
        "Show me the current inventory forecast.",
    ],
    "foundry-iq": [
        "What's our remote work policy?",
        "How much PTO do full-time employees get, and how much carries over?",
        "What's the incident response procedure for a security breach?",
    ],
    "web-iq": [
        "What's the latest news on AI regulation?",
        "What's the current stock price of Microsoft?",
    ],
}

# ── Main chat ─────────────────────────────────────────────────────────────────

st.title("🧭 All-IQ Chat")
st.caption(
    "Ask anything — the orchestrator routes your question to the right IQ source(s) "
    "(M365 data, enterprise structured data, knowledge base docs, or the live web) "
    "and merges grounded answers with citations."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.expander("💡 Sample questions — one click to test each IQ source", expanded=not st.session_state.messages):
    for source, questions in SAMPLE_QUESTIONS.items():
        st.caption(SOURCE_LABELS[source])
        cols = st.columns(len(questions))
        for col, q in zip(cols, questions):
            if col.button(q, key=f"sample_{source}_{q}", use_container_width=True):
                st.session_state["queued_prompt"] = q

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for source_block in msg.get("source_blocks", []):
            label = SOURCE_LABELS.get(source_block["source"], source_block["source"])
            icon = "✅" if source_block["ok"] else "⚠️"
            with st.expander(f"{icon} {label}"):
                if source_block["ok"]:
                    st.markdown(source_block["text"])
                else:
                    st.error(source_block["error"])
                for c in source_block.get("citations", []):
                    if c.get("url"):
                        st.markdown(f"- [{c.get('title') or c['url']}]({c['url']})")

prompt = st.chat_input("Ask about your email, sales data, company policies, or the news…")
prompt = prompt or st.session_state.pop("queued_prompt", None)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        spinner_msg = (
            "Letting the agent choose and call tools…" if use_agent
            else "Routing your question across IQ sources…"
        )
        with st.spinner(spinner_msg):
            try:
                resp = httpx.post(
                    f"{ORCHESTRATOR_URL}/chat",
                    json={
                        "message": prompt,
                        "workiq_token": st.session_state.get("workiq_token"),
                        "sources": manual_sources or None,
                        "use_agent": use_agent,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                st.error(f"Could not reach orchestrator: {exc}")
                data = None

        if data:
            routed = ", ".join(SOURCE_LABELS.get(s, s) for s in data["routed_sources"]) or "no tools called"
            mode_caption = "🤖 AI-routed" if data.get("agent_answer") is not None else "Keyword-routed"
            st.caption(f"{mode_caption} — used: {routed}")

            if data.get("agent_answer") is not None:
                combined = data["agent_answer"] or "_The agent didn't return an answer._"
                st.markdown(combined)
            else:
                ok_results = [r for r in data["results"] if r["ok"]]
                if ok_results:
                    combined = "\n\n---\n\n".join(
                        f"**{SOURCE_LABELS.get(r['source'], r['source'])}**\n\n{r['text']}"
                        for r in ok_results
                    )
                    st.markdown(combined)
                else:
                    combined = "_No grounded answer available._"
                    st.info("No source returned a grounded answer — see details below.")

            for r in data["results"]:
                label = SOURCE_LABELS.get(r["source"], r["source"])
                icon = "✅" if r["ok"] else "⚠️"
                with st.expander(f"{icon} {label}"):
                    if r["ok"]:
                        st.markdown(r["text"])
                    else:
                        st.error(r["error"])
                    for c in r.get("citations", []):
                        if c.get("url"):
                            st.markdown(f"- [{c.get('title') or c['url']}]({c['url']})")

            st.session_state.messages.append({
                "role": "assistant",
                "content": combined,
                "source_blocks": data["results"],
            })
