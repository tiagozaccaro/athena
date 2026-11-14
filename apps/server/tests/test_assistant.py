"""The AI assistant: secrets, Ollama detection, providers, model lists and chats."""

import json
import os
import sys
from collections.abc import AsyncIterator

import httpx2
import pytest
from conftest import make_app, signed_in
from fake_probe import FakeProbe
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.models.test import TestModel
from sqlmodel import select

from athena.api import assistant as assistant_api
from athena.assistant.kinds import KINDS
from athena.assistant.providers import ProviderConfig, build_model
from athena.crypto import SecretBox, SecretError
from athena.db.models import AiProvider, AuditEntry
from athena.platform.detect import detect_ollama

KEY = "sk-test-not-a-real-key"


# ---------------------------------------------------------------- secrets


def test_secret_box_round_trip(tmp_path):
    box = SecretBox(tmp_path)
    token = box.encrypt(KEY)
    assert KEY not in token
    assert SecretBox(tmp_path).decrypt(token) == KEY  # the key file is reused
    if sys.platform != "win32":
        assert (tmp_path / "secret.key").stat().st_mode & 0o777 == 0o600


def test_secret_box_with_another_key_fails(tmp_path):
    token = SecretBox(tmp_path / "a").encrypt(KEY)
    with pytest.raises(SecretError):
        SecretBox(tmp_path / "b").decrypt(token)


# ---------------------------------------------------------------- Ollama detection


def test_ollama_ready():
    probe = FakeProbe(http={"http://127.0.0.1:11434/api/version": {"version": "0.12.3"}})
    cap = detect_ollama(probe)
    assert cap.status == "ready"
    assert cap.endpoint == "http://127.0.0.1:11434"
    assert cap.detail == "Ollama 0.12.3"


def test_ollama_host_env():
    probe = FakeProbe(
        env={"OLLAMA_HOST": "0.0.0.0"},
        http={"http://127.0.0.1:11434/api/version": {"version": "1"}},
    )
    assert detect_ollama(probe).status == "ready"
    probe = FakeProbe(
        env={"OLLAMA_HOST": "https://gpu.lan:8443/"},
        http={"https://gpu.lan:8443/api/version": {"version": "1"}},
    )
    assert detect_ollama(probe).endpoint == "https://gpu.lan:8443"


def test_ollama_installed_but_stopped_or_missing():
    assert detect_ollama(FakeProbe(binaries={"ollama": "/usr/bin/ollama"})).status == "stopped"
    assert detect_ollama(FakeProbe()).status == "missing"


# ---------------------------------------------------------------- models per kind


@pytest.mark.parametrize("kind", [k.id for k in KINDS])
def test_every_kind_builds_a_model(kind, monkeypatch):
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    spec = next(k for k in KINDS if k.id == kind)
    values = {f.key: f.default or "x" for f in spec.fields}
    if "base_url" in values:
        values["base_url"] = "http://127.0.0.1:9999"
    model_id = "openai/m1" if kind == "openrouter" else "m1"
    model = build_model(ProviderConfig(id="p", kind=spec, name=spec.label, values=values), model_id)
    assert model.model_name == model_id


# ---------------------------------------------------------------- API helpers


def mock_transport(routes: dict[str, object]) -> httpx2.MockTransport:
    """URL path (without query) -> JSON body, or an int status code."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        answer = routes.get(request.url.path)
        if answer is None:
            return httpx2.Response(404, json={"error": "not found"})
        if isinstance(answer, int):
            return httpx2.Response(answer, json={"error": {"message": "bad key"}})
        if callable(answer):
            return httpx2.Response(200, json=answer(request))
        return httpx2.Response(200, json=answer)

    return httpx2.MockTransport(handler)


OLLAMA = {
    "/api/tags": {"models": [{"name": "llama3.2:3b"}, {"name": "gemma:2b"}, {"name": "nomic"}]},
    "/api/show": lambda req: {
        "llama3.2:3b": {"capabilities": ["completion", "tools"]},
        "gemma:2b": {"capabilities": ["completion"]},
        "nomic": {"capabilities": ["embedding"]},
    }[json.loads(req.content)["model"]],
}


def add_provider(client, kind="anthropic", name="Claude", values=None):
    res = client.post(
        "/api/assistant/providers",
        json={"kind": kind, "name": name, "values": values or {"api_key": KEY}},
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- providers


def test_provider_keys_are_never_returned_or_stored_in_clear(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        signed_in(client)
        created = add_provider(client)
        assert created["secrets_set"] == ["api_key"]
        assert KEY not in json.dumps(created)
        assert KEY not in client.get("/api/assistant/providers").text
        for db in app.state.db.session():
            row = db.get(AiProvider, created["id"])
            assert row is not None and row.secrets and KEY not in row.secrets
            actions = [e.action for e in db.exec(select(AuditEntry)).all()]
            assert "ai.provider.create" in actions


def test_editing_keeps_an_empty_secret(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        signed_in(client)
        pid = add_provider(client)["id"]
        res = client.put(
            f"/api/assistant/providers/{pid}",
            json={"name": "Work", "values": {"api_key": "", "base_url": "https://proxy.lan"}},
        )
        assert res.status_code == 200, res.text
        assert res.json()["secrets_set"] == ["api_key"]
        assert res.json()["values"] == {"base_url": "https://proxy.lan"}


def test_provider_validation(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        res = client.post(
            "/api/assistant/providers",
            json={"kind": "anthropic", "name": "No key", "values": {}},
        )
        assert res.status_code == 422
        assert "API key is required" in res.text
        res = client.post(
            "/api/assistant/providers",
            json={"kind": "ollama", "name": "Bad", "values": {"base_url": "file:///etc"}},
        )
        assert res.status_code == 422
        res = client.post("/api/assistant/providers", json={"kind": "nope", "name": "x"})
        assert res.status_code == 422


def test_assistant_needs_a_session(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        assert client.get("/api/assistant/providers").status_code == 401
        assert client.get("/api/settings/ai").status_code == 401


def test_ollama_models_and_tool_support(tmp_path):
    app = make_app(tmp_path)
    app.state.ai_transport = mock_transport(OLLAMA)
    with TestClient(app) as client:
        signed_in(client)
        pid = add_provider(client, "ollama", "Ollama", {"base_url": "http://127.0.0.1:11434"})["id"]
        res = client.get(f"/api/assistant/providers/{pid}/models")
        assert res.status_code == 200
        models = {m["id"]: m["tools"] for m in res.json()["models"]}
        assert models == {"gemma:2b": False, "llama3.2:3b": True}  # embeddings left out
        test = client.post(f"/api/assistant/providers/{pid}/test").json()
        assert test == {"ok": True, "message": "Connected: 2 models, 1 can use tools."}


def test_model_list_errors_are_readable(tmp_path):
    app = make_app(tmp_path)
    app.state.ai_transport = mock_transport({"/v1/models": 401})
    with TestClient(app) as client:
        signed_in(client)
        pid = add_provider(client)["id"]
        test = client.post(f"/api/assistant/providers/{pid}/test").json()
        assert test["ok"] is False
        assert "refused the API key" in test["message"]
        everything = client.get("/api/assistant/models").json()
        assert everything[0]["error"] and everything[0]["models"] == []


def test_anthropic_and_openrouter_lists(tmp_path):
    app = make_app(tmp_path)
    app.state.ai_transport = mock_transport(
        {
            "/v1/models": {"data": [{"id": "claude-x", "display_name": "Claude X"}]},
            "/api/v1/models": {
                "data": [
                    {"id": "a/tools", "supported_parameters": ["tools"]},
                    {"id": "b/none", "supported_parameters": []},
                ]
            },
        }
    )
    with TestClient(app) as client:
        signed_in(client)
        add_provider(client)
        add_provider(client, "openrouter", "OpenRouter")
        lists = client.get("/api/assistant/models").json()
        assert lists[0]["models"] == [{"id": "claude-x", "name": "Claude X", "tools": True}]
        assert [(m["id"], m["tools"]) for m in lists[1]["models"]] == [
            ("a/tools", True),
            ("b/none", False),
        ]


def test_removing_a_provider_clears_the_default_model(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        pid = add_provider(client)["id"]
        ref = {"provider_id": pid, "model": "claude-x"}
        res = client.put("/api/settings/ai", json={"default_model": ref, "spend_limit_usd": 2})
        assert res.status_code == 200, res.text
        assert client.get("/api/settings/ai").json()["default_model"] == ref
        assert client.delete(f"/api/assistant/providers/{pid}").status_code == 204
        assert client.get("/api/settings/ai").json()["default_model"] is None
        bad = {"default_model": {"provider_id": "0" * 16, "model": "x"}}
        assert client.put("/api/settings/ai", json=bad).status_code == 422


# ---------------------------------------------------------------- chat


def read_events(res) -> list[tuple[str, dict]]:
    events, name = [], None
    for line in res.iter_lines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append((name, json.loads(line.removeprefix("data: "))))
    return events


def chat_app(tmp_path, monkeypatch, model):
    app = make_app(tmp_path)
    monkeypatch.setattr(assistant_api, "build_model", lambda cfg, model_id: model)
    return app


def test_chat_streams_a_reply_with_tools_and_saves_it(tmp_path, monkeypatch):
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator:
        names = {t.name for t in info.function_tools}
        # Containers are missing on the fake host, so their tools aren't offered.
        assert "list_apps" not in names and "get_capabilities" in names
        last = messages[-1]
        if any(getattr(p, "part_kind", "") == "user-prompt" for p in last.parts):
            yield {0: DeltaToolCall(name="get_capabilities", json_args="{}", tool_call_id="c1")}
        else:
            yield "This is "
            yield "a Mac."

    app = chat_app(tmp_path, monkeypatch, FunctionModel(stream_function=reply))
    with TestClient(app) as client:
        signed_in(client)
        pid = add_provider(client)["id"]
        conv = client.post(
            "/api/assistant/conversations", json={"model": {"provider_id": pid, "model": "m"}}
        ).json()
        url = f"/api/assistant/conversations/{conv['id']}/messages"
        with client.stream("POST", url, json={"text": "What OS is this server running?"}) as res:
            assert res.status_code == 200
            events = read_events(res)
        kinds = [e for e, _ in events]
        assert kinds[0] == "tool-call" and kinds[-1] == "done"
        assert ("tool-call", {"id": "c1", "name": "get_capabilities", "args": {}}) in events
        result = next(d for e, d in events if e == "tool-result")
        assert '"os": "darwin"' in result["result"] and result["error"] is None
        assert "".join(d["delta"] for e, d in events if e == "text") == "This is a Mac."
        assert ("title", {"title": "What OS is this server running?"}) in events

        detail = client.get(f"/api/assistant/conversations/{conv['id']}").json()
        assert detail["running"] is False
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        parts = detail["messages"][1]["parts"]
        assert parts[0]["type"] == "tool" and parts[0]["state"] == "done"
        assert parts[-1] == {**parts[-1], "type": "text", "text": "This is a Mac."}

        # The history is kept: a second turn sees the first.
        with client.stream("POST", url, json={"text": "Thanks"}) as res:
            read_events(res)
        detail = client.get(f"/api/assistant/conversations/{conv['id']}").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"] * 2
        assert client.get("/api/assistant/conversations").json()[0]["title"].startswith("What OS")


def test_chat_reports_model_errors(tmp_path, monkeypatch):
    async def broken(messages, info) -> AsyncIterator[str]:
        raise RuntimeError("model exploded")
        yield ""

    app = chat_app(tmp_path, monkeypatch, FunctionModel(stream_function=broken))
    with TestClient(app) as client:
        signed_in(client)
        pid = add_provider(client)["id"]
        conv = client.post(
            "/api/assistant/conversations", json={"model": {"provider_id": pid, "model": "m"}}
        ).json()
        url = f"/api/assistant/conversations/{conv['id']}/messages"
        with client.stream("POST", url, json={"text": "hi"}) as res:
            events = read_events(res)
        assert ("error", {"message": "model exploded"}) in events
        assert events[-1][0] == "done"
        assert client.get(f"/api/assistant/conversations/{conv['id']}").json()["messages"] == []


def test_chat_needs_a_model(tmp_path, monkeypatch):
    app = chat_app(tmp_path, monkeypatch, TestModel())
    with TestClient(app) as client:
        signed_in(client)
        conv = client.post("/api/assistant/conversations", json={}).json()
        url = f"/api/assistant/conversations/{conv['id']}/messages"
        res = client.post(url, json={"text": "hi"})
        assert res.status_code == 409 and "Pick a model" in res.text
        gone = {"provider_id": "0" * 16, "model": "x"}
        res = client.post(url, json={"text": "hi", "model": gone})
        assert res.status_code == 409 and "removed" in res.text


def test_chats_can_be_renamed_and_deleted(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        conv = client.post("/api/assistant/conversations", json={}).json()
        url = f"/api/assistant/conversations/{conv['id']}"
        assert client.patch(url, json={"title": "Disk space"}).json()["title"] == "Disk space"
        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404


@pytest.mark.skipif(os.environ.get("ATHENA_OLLAMA_TESTS") != "1", reason="needs a local Ollama")
def test_real_ollama_lists_models(tmp_path):
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        pid = add_provider(client, "ollama", "Ollama", {"base_url": "http://127.0.0.1:11434"})["id"]
        assert client.post(f"/api/assistant/providers/{pid}/test").json()["ok"] is True
