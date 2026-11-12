"""LLM provider abstraction for the Underwriting Copilot.

Resolution order (first that works wins):

1. **Ollama** at ``OLLAMA_HOST`` (default ``http://localhost:11434``) with model
   ``OLLAMA_MODEL`` (default ``llama3.2:3b``) — probed with a short timeout.
2. **Gemini** REST API when ``GEMINI_API_KEY`` is set (model ``GEMINI_MODEL``,
   default ``gemini-2.0-flash``).
3. **None** — the copilot answers from grounded templates only.

The whole system works with no LLM at all. ``COPILOT_LLM`` can force a choice:
``auto`` (default) | ``ollama`` | ``gemini`` | ``none``.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

_PROBE_TTL_S = 60.0
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, LLMProvider | None]] = {}


@dataclass(frozen=True)
class LLMProvider:
    """A reachable chat-completion backend."""

    kind: str   # "ollama" | "gemini"
    model: str
    host: str = ""

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.model}"

    def complete(self, system: str, user: str, timeout: float = 30.0) -> str:
        """Return the model's text reply (raises on transport / API error)."""
        if self.kind == "ollama":
            return _ollama_chat(self.host, self.model, system, user, timeout)
        if self.kind == "gemini":
            return _gemini_generate(self.model, system, user, timeout)
        raise ValueError(f"unknown provider {self.kind}")


def _ollama_host() -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip()
    if not host.startswith("http"):
        host = "http://" + host
    return host.rstrip("/")


def _probe_ollama(timeout: float = 0.6) -> LLMProvider | None:
    host = _ollama_host()
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    try:
        r = httpx.get(f"{host}/api/tags", timeout=timeout)
        if r.status_code != 200:
            return None
        names = {m.get("name", "") for m in r.json().get("models", [])}
        if names and model not in names and f"{model}:latest" not in names:
            log.info("ollama reachable but model %s not pulled (have %s)", model, sorted(names))
            return None
        return LLMProvider("ollama", model, host)
    except (httpx.HTTPError, ValueError):
        return None


def _probe_gemini() -> LLMProvider | None:
    if not os.getenv("GEMINI_API_KEY"):
        return None
    return LLMProvider("gemini", os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))


def get_provider(refresh: bool = False) -> LLMProvider | None:
    """Return the active provider or ``None`` (cached for 60 s)."""
    mode = os.getenv("COPILOT_LLM", "auto").strip().lower()
    if mode in ("none", "off", "0", "false", ""):
        return None
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(mode)
        if hit and not refresh and now - hit[0] < _PROBE_TTL_S:
            return hit[1]
    provider: LLMProvider | None = None
    if mode in ("auto", "ollama"):
        provider = _probe_ollama()
    if provider is None and mode in ("auto", "gemini"):
        provider = _probe_gemini()
    with _cache_lock:
        _cache[mode] = (now, provider)
    return provider


def provider_status() -> dict[str, str | None]:
    p = get_provider()
    return {"provider": p.kind if p else None, "model": p.model if p else None,
            "label": p.label if p else "grounded-template"}


# --------------------------------------------------------------------------- transports
def _ollama_chat(host: str, model: str, system: str, user: str, timeout: float) -> str:
    r = httpx.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "stream": False,
            "options": {"temperature": 0.1, "seed": 42},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return str(r.json().get("message", {}).get("content", "")).strip()


def _gemini_generate(model: str, system: str, user: str, timeout: float) -> str:
    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = httpx.post(
        url,
        headers={"x-goog-api-key": key},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(str(p.get("text", "")) for p in parts).strip()
