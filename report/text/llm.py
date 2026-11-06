"""Local LLM backends: Ollama and LM Studio (OpenAI-compatible). Deterministic settings."""
from __future__ import annotations

import httpx

from .prompts import system_prompt

DEFAULT_URLS = {"ollama": "http://localhost:11434", "lmstudio": "http://localhost:1234"}
SEED = 42


class LLMUnavailable(Exception):
    pass


def _url(backend: str, url: str | None) -> str:
    return (url or DEFAULT_URLS[backend]).rstrip("/")


def list_models(backend: str, url: str | None = None) -> list:
    base = _url(backend, url)
    try:
        if backend == "ollama":
            r = httpx.get(f"{base}/api/tags", timeout=3)
            r.raise_for_status()
            return sorted(m["name"] for m in r.json().get("models", []))
        r = httpx.get(f"{base}/v1/models", timeout=3)
        r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailable(f"{backend} not reachable at {base}: {e}") from e


def generate(backend: str, model: str, prompt: str, url: str | None = None, timeout: float = 600,
             language: str = "en") -> str:
    base = _url(backend, url)
    msgs = [{"role": "system", "content": system_prompt(language)}, {"role": "user", "content": prompt}]
    try:
        if backend == "ollama":
            r = httpx.post(f"{base}/api/chat", timeout=timeout, json={
                "model": model, "messages": msgs, "stream": False,
                "options": {"temperature": 0, "seed": SEED, "top_k": 1, "num_ctx": 8192},
            })
            r.raise_for_status()
            raw = r.json()["message"]["content"]
        else:
            r = httpx.post(f"{base}/v1/chat/completions", timeout=timeout, json={
                "model": model, "messages": msgs, "temperature": 0, "seed": SEED, "stream": False,
            })
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailable(f"{backend} generation failed: {e}") from e
    return raw.strip()
