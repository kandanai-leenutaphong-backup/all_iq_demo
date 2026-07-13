"""Web IQ client — AI-native web grounding API.

Auth: API key only (`WEBIQ_API_KEY`), per user preference — no interactive
sign-in fallback.

Uses the official `webiq` PyPI SDK rather than hand-rolled REST calls — an
earlier version of this file guessed the REST shape from RESEARCH.md and got
two details wrong that the SDK source revealed:
  - the search path is `/search/web`, not `/search`
  - API-key auth goes in an `x-apikey` header, not `Authorization: Bearer`
(`ApiKeyAuth.get_headers()` in `webiq/auth.py`). The SDK handles both
correctly, so we let it own the wire format instead of re-guessing it.
"""

import re

from webiq import WebIQAsyncClient

from backend import config
from backend.sources.base import Citation, IQResult, NotConfiguredError

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_snippet(content: str, limit: int = 500) -> str:
    """Web IQ returns raw HTML-tagged content; strip tags for a readable snippet."""
    return " ".join(_TAG_RE.sub(" ", content).split())[:limit]


def _to_result(response) -> IQResult:
    citations = [
        Citation(
            title=item.title or "",
            url=item.url or "",
            snippet=_clean_snippet(item.content or ""),
        )
        for item in (response.webResults or [])
    ]
    text = "\n\n".join(f"{c.title}\n{c.snippet}" for c in citations) or "No web results found."
    return IQResult(source="web-iq", ok=bool(citations), text=text, citations=citations)


async def ask(question: str, max_results: int = 5) -> IQResult:
    if not config.WEBIQ_API_KEY:
        raise NotConfiguredError(
            "Web IQ is not configured — set WEBIQ_API_KEY in .env (request access at "
            "https://aka.ms/webiq-waitlist if you don't have one yet)."
        )

    try:
        async with WebIQAsyncClient(
            api_key=config.WEBIQ_API_KEY, base_url=config.WEBIQ_BASE_URL
        ) as client:
            response = await client.web.search(question, max_results=max_results)
    except Exception as exc:
        return IQResult(source="web-iq", ok=False, error=str(exc))

    return _to_result(response)
