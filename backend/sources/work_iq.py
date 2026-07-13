"""Work IQ client.

Reuses the delegated OAuth pattern already wired in ../../workiq-demo/utils.py:
the Streamlit UI signs the user in via MSAL device-code flow and hands the
resulting access token to the orchestrator on each request — no separate
credential is managed server-side for this source.

The MCP endpoint requires the full session handshake before `tools/call`
will work — `initialize` → `notifications/initialized` → subsequent calls
carrying the `Mcp-Session-Id` header the server returned from `initialize`
(this matches `../../workiq-demo/pages/7_MCP_Explorer.py`'s `ensure_mcp_session()`).
Skipping it produces a generic "An error occurred invoking 'ask'." failure.
The actual chat/reasoning tool is `ask` with a `{"question": ...}` argument
(confirmed via tools/list inputSchema) — not `{"query": ...}` (which the
server silently accepts but then fails on, returning a generic "An error
occurred invoking 'ask'." isError response) and not a `chatOverStream` tool
(that name only exists as a REST endpoint path in the older workiq-demo app,
not as an MCP tool).
"""

import json
import uuid

import httpx

from backend import config
from backend.sources.base import IQResult, NotConfiguredError


def _parse_sse_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    return json.loads(payload)
                except Exception:
                    pass
    return {}


async def _mcp_rpc(
    client: httpx.AsyncClient, token: str, method: str, params: dict | None, session_id: str | None
) -> tuple[dict, str | None]:
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    body: dict = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method}
    if params:
        body["params"] = params

    r = await client.post(config.WORKIQ_MCP, headers=headers, json=body)
    sid = r.headers.get("Mcp-Session-Id") or session_id
    if not r.content:
        return {}, sid
    content_type = r.headers.get("content-type", "")
    if "text/event-stream" in content_type or r.text.lstrip().startswith(("event:", "data:")):
        data = _parse_sse_json(r.text)
    else:
        data = r.json()
    return data, sid


async def ask(question: str, token: str) -> IQResult:
    if not token:
        raise NotConfiguredError(
            "Work IQ requires a user access token — sign in on the Streamlit Home page first."
        )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            init_resp, sid = await _mcp_rpc(
                client, token, "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "all-iq-orchestrator", "version": "0.1.0"},
                },
                session_id=None,
            )
            if "result" not in init_resp:
                err = init_resp.get("error", init_resp)
                if isinstance(err, dict):
                    err = err.get("message", json.dumps(err)[:300])
                return IQResult(source="work-iq", ok=False, error=f"MCP init failed: {err}")

            await _mcp_rpc(client, token, "notifications/initialized", None, session_id=sid)

            data, _ = await _mcp_rpc(
                client, token, "tools/call",
                {"name": "ask", "arguments": {"question": question}},
                session_id=sid,
            )
    except Exception as exc:  # network/timeout
        return IQResult(source="work-iq", ok=False, error=str(exc))

    if "error" in data:
        msg = data["error"]
        if isinstance(msg, dict):
            msg = msg.get("message", json.dumps(msg)[:300])
        return IQResult(source="work-iq", ok=False, error=str(msg))

    result = data.get("result", {})
    text = ""
    if isinstance(result, dict):
        content = result.get("content", [])
        text = "\n".join(
            c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
        )
        if result.get("isError"):
            return IQResult(source="work-iq", ok=False, error=text or "Work IQ tool call failed.")
    return IQResult(source="work-iq", ok=bool(text), text=text or "No response text from Work IQ.")
