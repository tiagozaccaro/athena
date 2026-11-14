"""Saved AI providers: their settings, the pydantic-ai model for a model id, and the live
model list (docs/mvp-design.md §4.5)."""

import asyncio
import contextlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx2
from pydantic import BaseModel
from pydantic_ai.models import Model

from athena.assistant.kinds import BY_ID, ProviderKind, secret_keys
from athena.crypto import SecretBox
from athena.db.models import AiProvider

LIST_TIMEOUT = 15.0
CACHE_SECONDS = 600


class ProviderError(Exception):
    """A provider can't be reached or refused the request. The message is for people."""


class ModelInfo(BaseModel):
    id: str
    name: str | None = None
    tools: bool | None = None
    """Whether the model can call tools, when the provider says; None when unknown."""


@dataclass
class ProviderConfig:
    """A saved provider with its secrets decrypted, ready to build models from."""

    id: str
    kind: ProviderKind
    name: str
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        value = self.values.get(key)
        if value:
            return value
        spec = next((f for f in self.kind.fields if f.key == key), None)
        return spec.default if spec else None


def config_of(row: AiProvider, box: SecretBox) -> ProviderConfig:
    kind = BY_ID[row.kind]
    values: dict[str, str] = dict(json.loads(row.config or "{}"))
    if row.secrets:
        values.update(json.loads(box.decrypt(row.secrets)))
    return ProviderConfig(id=row.id, kind=kind, name=row.name, values=values)


def split_values(
    kind: ProviderKind, values: dict[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    """(plain config, secrets) for the kind's known fields; other keys are dropped."""
    secret = secret_keys(kind)
    known = {f.key for f in kind.fields}
    plain = {k: v for k, v in values.items() if k in known and k not in secret and v}
    secrets = {k: v for k, v in values.items() if k in secret and v}
    return plain, secrets


def check_values(kind: ProviderKind, values: dict[str, str]) -> None:
    for f in kind.fields:
        value = values.get(f.key) or f.default
        if f.required and not value:
            raise ValueError(f"{f.label} is required")
        if f.key == "base_url" and value:
            parts = urlsplit(value)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                raise ValueError(f"{f.label} must be an http:// or https:// address")


# ---------------------------------------------------------------- models


def _strip(url: str) -> str:
    return url.rstrip("/")


def build_model(cfg: ProviderConfig, model_id: str) -> Model:
    """The pydantic-ai model for `model_id` on this provider."""
    kind = cfg.kind.id
    key = cfg.get("api_key")
    if kind == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            model_id, provider=AnthropicProvider(api_key=key, base_url=cfg.get("base_url"))
        )
    if kind == "openai":
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIResponsesModel(
            model_id, provider=OpenAIProvider(base_url=cfg.get("base_url"), api_key=key)
        )
    if kind == "google":
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(model_id, provider=GoogleProvider(api_key=key))
    if kind == "openrouter":
        from pydantic_ai.models.openrouter import OpenRouterModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        return OpenRouterModel(
            model_id, provider=OpenRouterProvider(api_key=key, app_title="Athena")
        )
    if kind == "groq":
        from pydantic_ai.models.groq import GroqModel
        from pydantic_ai.providers.groq import GroqProvider

        return GroqModel(model_id, provider=GroqProvider(api_key=key))
    if kind == "mistral":
        from pydantic_ai.models.mistral import MistralModel
        from pydantic_ai.providers.mistral import MistralProvider

        return MistralModel(model_id, provider=MistralProvider(api_key=key))
    if kind == "deepseek":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.deepseek import DeepSeekProvider

        return OpenAIChatModel(model_id, provider=DeepSeekProvider(api_key=key))
    if kind == "xai":
        # xAI's own provider needs its gRPC SDK; its OpenAI-style API works the same here.
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIChatModel(
            model_id, provider=OpenAIProvider(base_url="https://api.x.ai/v1", api_key=key)
        )
    if kind == "azure":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.azure import AzureProvider

        return OpenAIChatModel(
            model_id,
            provider=AzureProvider(
                azure_endpoint=cfg.get("base_url"),
                api_version=cfg.get("api_version"),
                api_key=key,
            ),
        )
    if kind == "bedrock":
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        return BedrockConverseModel(
            model_id,
            provider=BedrockProvider(
                aws_access_key_id=cfg.get("access_key_id"),
                aws_secret_access_key=cfg.get("secret_access_key"),
                region_name=cfg.get("region"),
            ),
        )
    if kind == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider

        base = _strip(cfg.get("base_url") or "")
        return OllamaModel(
            model_id, provider=OllamaProvider(base_url=f"{base}/v1", api_key=key or "ollama")
        )
    if kind == "openai-compatible":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        # The client insists on a key; local servers ignore it.
        return OpenAIChatModel(
            model_id,
            provider=OpenAIProvider(base_url=cfg.get("base_url"), api_key=key or "not-needed"),
        )
    raise ProviderError(f"Unknown provider kind {kind!r}")


# ---------------------------------------------------------------- model lists


def _describe(exc: Exception, cfg: ProviderConfig) -> str:
    if isinstance(exc, httpx2.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return f"{cfg.name} refused the API key (HTTP {code})"
        detail = ""
        with contextlib.suppress(ValueError):
            body = exc.response.json()
            err = body.get("error") if isinstance(body, dict) else None
            detail = (err.get("message") if isinstance(err, dict) else err) or ""
        return f"{cfg.name} answered HTTP {code}" + (f": {detail}" if detail else "")
    if isinstance(exc, httpx2.TimeoutException):
        return f"{cfg.name} didn't answer in time"
    if isinstance(exc, httpx2.RequestError):
        return f"Can't reach {cfg.name}: {exc}"
    return f"{cfg.name}: {exc}"


async def _json(client: httpx2.AsyncClient, method: str, url: str, **kw: Any) -> Any:
    res = await client.request(method, url, **kw)
    res.raise_for_status()
    return res.json()


def _bearer(key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"} if key else {}


async def _openai_style(client: httpx2.AsyncClient, base: str, key: str | None) -> list[ModelInfo]:
    data = await _json(client, "GET", f"{_strip(base)}/models", headers=_bearer(key))
    return [ModelInfo(id=m["id"]) for m in data.get("data", []) if m.get("id")]


async def _ollama(client: httpx2.AsyncClient, base: str, key: str | None) -> list[ModelInfo]:
    base = _strip(base)
    tags = await _json(client, "GET", f"{base}/api/tags", headers=_bearer(key))
    listed = [m for m in tags.get("models", []) if m.get("name")]

    def info_of(name: str, caps: object) -> ModelInfo:
        if not isinstance(caps, list):
            return ModelInfo(id=name)
        # Embedding-only models can't chat at all; they're left out below.
        if "completion" not in caps and "embedding" in caps:
            return ModelInfo(id=name, tools=False, name="embedding")
        return ModelInfo(id=name, tools="tools" in caps)

    async def show(model: dict[str, Any]) -> ModelInfo:
        name = model["name"]
        if "capabilities" in model:  # newer Ollama lists them in /api/tags
            return info_of(name, model["capabilities"])
        try:
            info = await _json(
                client, "POST", f"{base}/api/show", json={"model": name}, headers=_bearer(key)
            )
        except (httpx2.HTTPError, ValueError):
            return ModelInfo(id=name)
        return info_of(name, info.get("capabilities"))

    infos = await asyncio.gather(*(show(m) for m in listed))
    return [i for i in infos if i.name != "embedding"]


async def _anthropic(client: httpx2.AsyncClient, cfg: ProviderConfig) -> list[ModelInfo]:
    data = await _json(
        client,
        "GET",
        f"{_strip(cfg.get('base_url') or '')}/v1/models",
        params={"limit": 1000},
        headers={"x-api-key": cfg.get("api_key") or "", "anthropic-version": "2023-06-01"},
    )
    return [
        ModelInfo(id=m["id"], name=m.get("display_name"), tools=True)
        for m in data.get("data", [])
        if m.get("id")
    ]


async def _google(client: httpx2.AsyncClient, cfg: ProviderConfig) -> list[ModelInfo]:
    data = await _json(
        client,
        "GET",
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"pageSize": 1000},
        headers={"x-goog-api-key": cfg.get("api_key") or ""},
    )
    out = []
    for m in data.get("models", []):
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        out.append(ModelInfo(id=m["name"].removeprefix("models/"), name=m.get("displayName")))
    return out


async def _openrouter(client: httpx2.AsyncClient, cfg: ProviderConfig) -> list[ModelInfo]:
    data = await _json(
        client,
        "GET",
        "https://openrouter.ai/api/v1/models",
        headers=_bearer(cfg.get("api_key")),
    )
    return [
        ModelInfo(
            id=m["id"],
            name=m.get("name"),
            tools="tools" in (m.get("supported_parameters") or []),
        )
        for m in data.get("data", [])
        if m.get("id")
    ]


async def _mistral(client: httpx2.AsyncClient, cfg: ProviderConfig) -> list[ModelInfo]:
    data = await _json(
        client, "GET", "https://api.mistral.ai/v1/models", headers=_bearer(cfg.get("api_key"))
    )
    out = []
    for m in data.get("data", []):
        caps = m.get("capabilities") or {}
        if caps.get("completion_chat") is False:
            continue
        tools = caps.get("function_calling")
        out.append(ModelInfo(id=m["id"], tools=tools if isinstance(tools, bool) else None))
    return out


async def _azure(client: httpx2.AsyncClient, cfg: ProviderConfig) -> list[ModelInfo]:
    """Azure can't list deployments with a key, so this only proves the key works."""
    await _json(
        client,
        "GET",
        f"{_strip(cfg.get('base_url') or '')}/openai/models",
        params={"api-version": cfg.get("api_version")},
        headers={"api-key": cfg.get("api_key") or ""},
    )
    return []


def _bedrock(cfg: ProviderConfig) -> list[ModelInfo]:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        client = boto3.client(
            "bedrock",
            aws_access_key_id=cfg.get("access_key_id"),
            aws_secret_access_key=cfg.get("secret_access_key"),
            region_name=cfg.get("region"),
        )
        data = client.list_foundation_models(byOutputModality="TEXT")
    except (BotoCoreError, ClientError) as exc:
        raise ProviderError(f"{cfg.name}: {exc}") from exc
    return [
        ModelInfo(id=m["modelId"], name=m.get("modelName"))
        for m in data.get("modelSummaries", [])
        if "ON_DEMAND" in (m.get("inferenceTypesSupported") or ["ON_DEMAND"])
    ]


OPENAI_STYLE_BASES = {
    "openai": None,  # from the form
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "xai": "https://api.x.ai/v1",
    "openai-compatible": None,
}


async def fetch_models(
    cfg: ProviderConfig, transport: httpx2.AsyncBaseTransport | None = None
) -> list[ModelInfo]:
    """The provider's own model list. Raises ProviderError with a readable message."""
    kind = cfg.kind.id
    if kind == "bedrock":
        return await asyncio.to_thread(_bedrock, cfg)
    try:
        async with httpx2.AsyncClient(timeout=LIST_TIMEOUT, transport=transport) as client:
            if kind == "anthropic":
                models = await _anthropic(client, cfg)
            elif kind == "google":
                models = await _google(client, cfg)
            elif kind == "openrouter":
                models = await _openrouter(client, cfg)
            elif kind == "mistral":
                models = await _mistral(client, cfg)
            elif kind == "azure":
                models = await _azure(client, cfg)
            elif kind == "ollama":
                models = await _ollama(client, cfg.get("base_url") or "", cfg.get("api_key"))
            else:
                base = OPENAI_STYLE_BASES.get(kind) or cfg.get("base_url") or ""
                models = await _openai_style(client, base, cfg.get("api_key"))
    except (httpx2.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProviderError(_describe(exc, cfg)) from exc
    return sorted(models, key=lambda m: m.id)


class ModelCache:
    """Model lists per provider, kept for CACHE_SECONDS."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[float, list[ModelInfo]]] = {}

    def get(self, provider_id: str) -> list[ModelInfo] | None:
        entry = self._entries.get(provider_id)
        if entry and self._clock() - entry[0] < CACHE_SECONDS:
            return entry[1]
        return None

    def put(self, provider_id: str, models: list[ModelInfo]) -> None:
        self._entries[provider_id] = (self._clock(), models)

    def drop(self, provider_id: str) -> None:
        self._entries.pop(provider_id, None)
