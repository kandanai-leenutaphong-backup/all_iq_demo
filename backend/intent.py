"""Lightweight keyword-based intent router.

Decides which IQ source(s) to call for a given user message. This is
intentionally simple (per PLAN.md step 6: "keyword or LLM-based") — it can be
swapped for an LLM classifier later without changing the orchestrator API.
"""

import re

_KEYWORDS: dict[str, list[str]] = {
    "work-iq": [
        "email", "mail", "calendar", "meeting", "teams", "chat", "file", "onedrive",
        "sharepoint", "colleague", "people", "inbox", "schedule", "my day",
    ],
    "fabric-iq": [
        "sales", "revenue", "forecast", "inventory", "kpi", "report", "quarter",
        "dashboard", "data agent", "dax", "sql", "warehouse", "supply chain",
    ],
    "foundry-iq": [
        "policy", "policies", "contract", "handbook", "procedure", "compliance",
        "guideline", "document", "knowledge base", "hr policy", "benefits",
    ],
    "web-iq": [
        "news", "latest", "today", "current", "stock price", "weather",
        "who is", "what is happening", "search the web", "recent",
    ],
}


def route(message: str) -> list[str]:
    """Return the list of source names to query for `message`.

    Falls back to querying all four sources when no keyword matches, so the
    demo always attempts to ground the answer rather than silently no-op'ing.
    """
    lower = message.lower()
    matched = [
        source
        for source, keywords in _KEYWORDS.items()
        if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in keywords)
    ]
    return matched or list(_KEYWORDS.keys())
