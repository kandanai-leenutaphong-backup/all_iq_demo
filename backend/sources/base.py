"""Shared types for per-source IQ clients."""

from dataclasses import dataclass, field


@dataclass
class Citation:
    title: str = ""
    url: str = ""
    snippet: str = ""


@dataclass
class IQResult:
    source: str                       # "work-iq" | "fabric-iq" | "foundry-iq" | "web-iq"
    ok: bool
    text: str = ""
    citations: list[Citation] = field(default_factory=list)
    error: str = ""


class NotConfiguredError(Exception):
    """Raised by a source client when required env vars/config are missing."""


def describe_exception(exc: BaseException) -> str:
    """Human-readable message for an exception, unwrapping asyncio TaskGroup /
    anyio `ExceptionGroup`s (as raised by MCP's streamable-HTTP client) down
    to their first real underlying cause instead of the opaque
    "unhandled errors in a TaskGroup (N sub-exceptions)" wrapper text.
    """
    seen = exc
    while isinstance(seen, BaseExceptionGroup) and seen.exceptions:
        seen = seen.exceptions[0]
    return str(seen) or repr(seen)
