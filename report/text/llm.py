"""Local / private LLM backends. Deterministic settings (temperature 0, fixed seed).

* ollama   - Ollama native API (http://localhost:11434)
* lmstudio - LM Studio, OpenAI-compatible API (http://localhost:1234/v1)
* openai   - any other OpenAI-compatible API (e.g. BionicGPT, vLLM, Jan, LocalAI...):
             base URL + optional API key; the model can be typed if the list is not available.
"""
from __future__ import annotations

import httpx

from .prompts import system_prompt

DEFAULT_URLS = {"ollama": "http://localhost:11434", "lmstudio": "http://localhost:1234", "openai": ""}
SEED = 42


class LLMUnavailable(Exception):
    pass


def _url(backend: str, url: str | None) -> str:
    base = (url or DEFAULT_URLS.get(backend) or "").strip().rstrip("/")
    if not base:
        raise LLMUnavailable("Falta la URL del servicio (por ejemplo https://servidor/v1)")
    return base


def _v1(base: str) -> str:
    """OpenAI-style base: accept both '.../v1' and the bare host."""
    return base if base.endswith("/v1") else base + "/v1"


def _headers(api_key: str | None) -> dict:
    return {"Authorization": f"Bearer {api_key.strip()}"} if api_key and api_key.strip() else {}


def list_models(backend: str, url: str | None = None, api_key: str | None = None) -> list:
    base = _url(backend, url)
    try:
        if backend == "ollama":
            r = httpx.get(f"{base}/api/tags", timeout=5)
            r.raise_for_status()
            return sorted(m["name"] for m in r.json().get("models", []))
        r = httpx.get(f"{_v1(base)}/models", timeout=8, headers=_headers(api_key))
        r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailable(f"{backend} not reachable at {base}: {e}") from e


def generate(backend: str, model: str, prompt: str, url: str | None = None, timeout: float = 600,
             language: str = "en", api_key: str | None = None) -> str:
    base = _url(backend, url)
    if not model:
        raise LLMUnavailable("Falta el nombre del modelo")
    msgs = [{"role": "system", "content": system_prompt(language)}, {"role": "user", "content": prompt}]
    try:
        if backend == "ollama":
            r = httpx.post(f"{base}/api/chat", timeout=timeout, json={
                "model": model, "messages": msgs, "stream": False,
                "options": {"temperature": 0, "seed": SEED, "top_k": 1, "num_ctx": 8192},
            })
            r.raise_for_status()
            raw = r.json()["message"]["content"]
        else:  # lmstudio / any OpenAI-compatible API
            r = httpx.post(f"{_v1(base)}/chat/completions", timeout=timeout, headers=_headers(api_key), json={
                "model": model, "messages": msgs, "temperature": 0, "seed": SEED, "stream": False,
            })
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        raise LLMUnavailable(f"{backend} generation failed: {e}") from e
    return raw.strip()
