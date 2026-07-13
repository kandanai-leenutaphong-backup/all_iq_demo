"""Generic MCP (Model Context Protocol) call helper shared by Fabric IQ,
Foundry IQ, and Web IQ clients — all three are plain streamable-HTTP MCP
servers authenticated via an Entra bearer token. (Confirmed for Web IQ by
live probing of `https://api.microsoft.ai/v3/mcp`, which returns
`auth_token_parse_failed` for a raw API key and `auth_missing_token` when no
Authorization header is sent — i.e. it requires a real JWT, not a static
key.)
"""

from typing import Any

from azure.core.credentials import TokenCredential


async def call_mcp_tool_with_token(
    endpoint: str,
    token: str,
    tool_name: str | None,
    arguments: dict[str, Any],
) -> tuple[bool, str, list[dict]]:
    """Call an MCP tool over streamable HTTP using an already-acquired bearer token.

    If `tool_name` is None, calls the first (only) tool the server advertises
    — matches the "exactly one tool per published data agent" pattern used by
    Fabric IQ (RESEARCH.md §6).

    Returns (ok, text, raw_content_blocks).
    """
    # Imported lazily so the rest of the app works even if the `mcp` package
    # isn't installed yet (e.g. before credentials/config are wired up).
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": "Bearer " + token}

    async with streamablehttp_client(endpoint, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            name = tool_name
            args = dict(arguments)
            if name is None:
                tools = await session.list_tools()
                if not tools.tools:
                    return False, "MCP server advertised no tools.", []
                tool = tools.tools[0]
                name = tool.name
                # Map the free-text arg(s) onto whatever the tool actually calls it.
                props = (tool.inputSchema or {}).get("properties", {})
                if props:
                    matching = {k: v for k, v in arguments.items() if k in props}
                    args = matching or {next(iter(props)): next(iter(arguments.values()))}

            result = await session.call_tool(name, args)
            blocks = [
                {"type": b.type, "text": getattr(b, "text", "")} for b in result.content
            ]
            text = "\n".join(b["text"] for b in blocks if b["type"] == "text")
            return not result.isError, text, blocks


async def call_mcp_tool(
    endpoint: str,
    credential: TokenCredential,
    scopes: list[str],
    tool_name: str | None,
    arguments: dict[str, Any],
) -> tuple[bool, str, list[dict]]:
    """Same as `call_mcp_tool_with_token`, but resolves the token from an
    azure-identity `TokenCredential` first — used by Fabric IQ and Foundry IQ.

    `credential.get_token()` is a *blocking* synchronous call — for
    `InteractiveBrowserCredential` in particular it pops a browser window and
    waits on it. Running it directly inside this `async def` would block the
    whole FastAPI event loop (freezing every other in-flight request, not
    just this one) until sign-in completes or times out, so it's offloaded
    to a worker thread via `asyncio.to_thread`.
    """
    import asyncio

    token = await asyncio.to_thread(credential.get_token, *scopes)
    return await call_mcp_tool_with_token(endpoint, token.token, tool_name, arguments)
