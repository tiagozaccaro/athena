"""The AI provider kinds Athena knows (docs/mvp-design.md §4.5).

Each kind is a small form description: the UI renders the fields, the server checks
them, and `providers.py` turns a saved provider into a pydantic-ai model.
"""

from typing import Literal

from pydantic import BaseModel

KindId = Literal[
    "anthropic",
    "openai",
    "google",
    "openrouter",
    "groq",
    "mistral",
    "deepseek",
    "xai",
    "azure",
    "bedrock",
    "ollama",
    "openai-compatible",
]


class KindField(BaseModel):
    key: str
    label: str
    secret: bool = False
    """Stored encrypted and never sent back to the browser."""
    required: bool = False
    default: str | None = None
    placeholder: str | None = None
    help: str | None = None


class ProviderKind(BaseModel):
    id: KindId
    label: str
    group: Literal["cloud", "local"]
    fields: list[KindField]
    lists_models: bool = True
    """False when model ids can only be typed (Azure deployments)."""


def _key(required: bool = True, help: str | None = None) -> KindField:
    return KindField(key="api_key", label="API key", secret=True, required=required, help=help)


def _url(default: str | None, *, required: bool = False, help: str | None = None) -> KindField:
    return KindField(
        key="base_url",
        label="Base URL",
        required=required,
        default=default,
        placeholder=default,
        help=help,
    )


KINDS: list[ProviderKind] = [
    ProviderKind(
        id="anthropic",
        label="Anthropic",
        group="cloud",
        fields=[_key(), _url("https://api.anthropic.com")],
    ),
    ProviderKind(
        id="openai",
        label="OpenAI",
        group="cloud",
        fields=[_key(), _url("https://api.openai.com/v1")],
    ),
    ProviderKind(id="google", label="Google Gemini", group="cloud", fields=[_key()]),
    ProviderKind(id="openrouter", label="OpenRouter", group="cloud", fields=[_key()]),
    ProviderKind(id="groq", label="Groq", group="cloud", fields=[_key()]),
    ProviderKind(id="mistral", label="Mistral", group="cloud", fields=[_key()]),
    ProviderKind(id="deepseek", label="DeepSeek", group="cloud", fields=[_key()]),
    ProviderKind(id="xai", label="xAI", group="cloud", fields=[_key()]),
    ProviderKind(
        id="azure",
        label="Azure OpenAI",
        group="cloud",
        lists_models=False,
        fields=[
            _key(),
            KindField(
                key="base_url",
                label="Endpoint",
                required=True,
                placeholder="https://<resource>.openai.azure.com",
            ),
            KindField(key="api_version", label="API version", default="2024-10-21"),
        ],
    ),
    ProviderKind(
        id="bedrock",
        label="Amazon Bedrock",
        group="cloud",
        fields=[
            KindField(key="access_key_id", label="Access key ID", required=True),
            KindField(
                key="secret_access_key", label="Secret access key", secret=True, required=True
            ),
            KindField(key="region", label="Region", required=True, default="us-east-1"),
        ],
    ),
    ProviderKind(
        id="ollama",
        label="Ollama",
        group="local",
        fields=[
            _url("http://127.0.0.1:11434", required=True),
            _key(required=False, help="Only for Ollama Cloud or a proxy that asks for one."),
        ],
    ),
    ProviderKind(
        id="openai-compatible",
        label="OpenAI-compatible",
        group="local",
        fields=[
            _url(
                None,
                required=True,
                help="LM Studio, vLLM, llama.cpp or any server with an OpenAI-style /v1 API, "
                "e.g. http://127.0.0.1:1234/v1",
            ),
            _key(required=False),
        ],
    ),
]

BY_ID: dict[str, ProviderKind] = {k.id: k for k in KINDS}


def secret_keys(kind: ProviderKind) -> set[str]:
    return {f.key for f in kind.fields if f.secret}
