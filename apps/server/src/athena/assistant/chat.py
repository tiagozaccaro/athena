"""Chat turns: run the agent for one user message, stream typed events, save the history
(docs/mvp-design.md §4.5).

A turn runs in its own task and keeps going if the browser goes away, so the answer is
saved either way. Stopping uses pydantic-ai's CancellationToken, which keeps what the
model had already said.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    CancellationToken,
    Conversation,
    ConversationTypeAdapter,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    RunCancelled,
    UsageLimits,
)
from pydantic_ai.capabilities import Caching
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage

from athena.assistant.tools import Deps, toolset_for
from athena.db.models import AiConversation
from athena.platform.capabilities import CapabilityManifest

log = logging.getLogger(__name__)

TITLE_LENGTH = 60
RESULT_CHARS = 4000
"""Tool results shown in the UI are cut to this; the model still gets all of it."""

INSTRUCTIONS = """\
You are Athena's assistant. Athena is a self-hosted home server control panel: apps \
(Docker Compose projects), an app store, host packages, a terminal, files, shares and \
cloud storage. You help the server's admin understand and run this server.

- Use your tools to look things up instead of guessing. Only the tools you have exist on \
this host; if something isn't available, say so and point to the page in Athena that \
would handle it.
- You can only read for now: you can't install, start, stop, change or delete anything. \
When the admin asks for a change, explain how to do it in Athena's UI.
- Be brief and concrete. Use Markdown for lists, tables and code.
"""


def _host_instructions(manifest: CapabilityManifest) -> str:
    return f"This server runs {manifest.os_version} ({manifest.os}, {manifest.arch})."


agent: Agent[Deps, str] = Agent(
    deps_type=Deps,
    instructions=[INSTRUCTIONS],
    capabilities=[Caching()],
    name="athena",
)


# ---------------------------------------------------------------- UI messages


class ChatPart(BaseModel):
    type: Literal["text", "reasoning", "tool"]
    text: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    args: Any = None
    result: str | None = None
    """The tool's result as JSON or text, cut to RESULT_CHARS."""
    error: str | None = None
    state: Literal["running", "done", "error"] | None = None


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    parts: list[ChatPart]


def _result_text(content: Any) -> str:
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    return text if len(text) <= RESULT_CHARS else text[:RESULT_CHARS] + "…"


def _user_text(part: UserPromptPart) -> str:
    if isinstance(part.content, str):
        return part.content
    return "\n".join(c for c in part.content if isinstance(c, str))


def ui_messages(messages: list[ModelMessage]) -> list[ChatMessage]:
    """The stored history as chat bubbles: user prompts, and one assistant message per
    reply with its text, reasoning and tool calls (with their results)."""
    out: list[ChatMessage] = []
    tools: dict[str, ChatPart] = {}
    current: ChatMessage | None = None
    for i, msg in enumerate(messages):
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    current = None
                    out.append(
                        ChatMessage(
                            id=f"m{i}",
                            role="user",
                            parts=[ChatPart(type="text", text=_user_text(part))],
                        )
                    )
                elif isinstance(part, ToolReturnPart) and part.tool_call_id in tools:
                    tool = tools[part.tool_call_id]
                    tool.result = _result_text(part.content)
                    tool.state = "error" if part.outcome == "failed" else "done"
                elif isinstance(part, RetryPromptPart) and part.tool_call_id in tools:
                    tool = tools[part.tool_call_id]
                    tool.error = _result_text(part.content)
                    tool.state = "error"
        elif isinstance(msg, ModelResponse):
            if current is None:
                current = ChatMessage(id=f"m{i}", role="assistant", parts=[])
                out.append(current)
            for part in msg.parts:
                if isinstance(part, TextPart) and part.content:
                    current.parts.append(ChatPart(type="text", text=part.content))
                elif isinstance(part, ThinkingPart) and part.content:
                    current.parts.append(ChatPart(type="reasoning", text=part.content))
                elif isinstance(part, ToolCallPart):
                    tool = ChatPart(
                        type="tool",
                        tool_call_id=part.tool_call_id,
                        tool_name=part.tool_name,
                        args=_args(part),
                        state="running",
                    )
                    tools[part.tool_call_id] = tool
                    current.parts.append(tool)
    return out


def _args(part: ToolCallPart) -> Any:
    try:
        return part.args_as_dict()
    except (ValueError, TypeError):
        return part.args


# ---------------------------------------------------------------- history


def load_history(row: AiConversation) -> Conversation | None:
    if not row.history:
        return None
    try:
        return ConversationTypeAdapter.validate_json(row.history)
    except ValueError:
        log.warning("conversation %s has unreadable history; starting over", row.id)
        return None


def history_messages(row: AiConversation) -> list[ModelMessage]:
    conv = load_history(row)
    return list(conv.messages) if conv else []


# ---------------------------------------------------------------- running a turn


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@dataclass
class Turn:
    """One running reply. Events go to whoever is listening; the task saves the result."""

    conversation_id: str
    token: CancellationToken = field(default_factory=CancellationToken)
    queue: asyncio.Queue[str | None] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None

    def emit(self, event: str, data: Any) -> None:
        self.queue.put_nowait(sse(event, data))

    async def stream(self) -> AsyncIterator[str]:
        while (item := await self.queue.get()) is not None:
            yield item


def _usage_out(usage: Any) -> dict[str, Any]:
    cost = getattr(usage, "cost", None)
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost": float(cost) if cost is not None else None,
    }


async def _run(
    turn: Turn,
    *,
    app: FastAPI,
    model: Model,
    text: str,
    spend_limit: float | None,
    username: str,
) -> None:
    db_factory = app.state.db
    manifest = await app.state.capabilities.get()
    for db in db_factory.session():
        row = db.get(AiConversation, turn.conversation_id)
        assert row is not None
        previous = load_history(row)
        deps = Deps(app=app, db=db, username=username, manifest=manifest)
        limits = UsageLimits(
            request_limit=25,
            tool_calls_limit=50,
            cost_limit=Decimal(str(spend_limit)) if spend_limit else None,
        )
        saved: Conversation | None = None
        try:
            async with agent.run_stream_events(
                text,
                conversation=previous,
                model=model,
                deps=deps,
                toolsets=[toolset_for(manifest)],
                instructions=_host_instructions(manifest),
                usage_limits=limits,
                cancellation_token=turn.token,
            ) as events:
                async for event in events:
                    _forward(turn, event)
                    if isinstance(event, AgentRunResultEvent):
                        saved = event.result.conversation
        except RunCancelled as exc:
            saved = Conversation(messages=list(exc.all_messages()), usage=exc.usage or RunUsage())
            if exc.conversation_id:
                saved.conversation_id = exc.conversation_id
            turn.emit("stopped", {})
        except UsageLimitExceeded as exc:
            turn.emit("error", {"message": f"Stopped: {exc}"})
        except Exception as exc:  # the model's errors are for the person to read
            log.warning("assistant turn failed: %s", exc)
            turn.emit("error", {"message": _readable(exc)})
        if saved is not None:
            row.history = ConversationTypeAdapter.dump_json(saved).decode()
            if row.title == "New chat":
                row.title = _title(text)
                turn.emit("title", {"title": row.title})
            row.updated_at = datetime.now(UTC)
            db.add(row)
            db.commit()
            turn.emit("usage", _usage_out(saved.usage))
        turn.emit("done", {})


def _forward(turn: Turn, event: Any) -> None:
    if isinstance(event, PartStartEvent):
        part = event.part
        if isinstance(part, TextPart):
            turn.emit("text", {"delta": part.content, "new": True})
        elif isinstance(part, ThinkingPart):
            turn.emit("reasoning", {"delta": part.content, "new": True})
    elif isinstance(event, PartDeltaEvent):
        delta = event.delta
        if isinstance(delta, TextPartDelta) and delta.content_delta:
            turn.emit("text", {"delta": delta.content_delta})
        elif isinstance(delta, ThinkingPartDelta) and delta.content_delta:
            turn.emit("reasoning", {"delta": delta.content_delta})
    elif isinstance(event, FunctionToolCallEvent):
        part = event.part
        turn.emit(
            "tool-call", {"id": part.tool_call_id, "name": part.tool_name, "args": _args(part)}
        )
    elif isinstance(event, FunctionToolResultEvent):
        part = event.part
        if isinstance(part, ToolReturnPart):
            failed = part.outcome == "failed"
            turn.emit(
                "tool-result",
                {
                    "id": part.tool_call_id,
                    "result": _result_text(part.content),
                    "error": _result_text(part.content) if failed else None,
                },
            )
        elif isinstance(part, RetryPromptPart):
            turn.emit(
                "tool-result",
                {"id": part.tool_call_id, "result": None, "error": _result_text(part.content)},
            )


def _readable(exc: Exception) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text if len(text) <= 500 else text[:500] + "…"


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_LENGTH else line[: TITLE_LENGTH - 1].rstrip() + "…"


class Turns:
    """Running turns by conversation id: one at a time per chat."""

    def __init__(self) -> None:
        self._turns: dict[str, Turn] = {}

    def get(self, conversation_id: str) -> Turn | None:
        turn = self._turns.get(conversation_id)
        if turn and turn.task and turn.task.done():
            self._turns.pop(conversation_id, None)
            return None
        return turn

    def start(
        self,
        conversation_id: str,
        *,
        app: FastAPI,
        model: Model,
        text: str,
        spend_limit: float | None,
        username: str,
    ) -> Turn:
        turn = Turn(conversation_id)

        async def body() -> None:
            try:
                await _run(
                    turn,
                    app=app,
                    model=model,
                    text=text,
                    spend_limit=spend_limit,
                    username=username,
                )
            except Exception:
                log.exception("assistant turn crashed")
                turn.emit("error", {"message": "The assistant failed. See the server log."})
                turn.emit("done", {})
            finally:
                turn.queue.put_nowait(None)
                self._turns.pop(conversation_id, None)

        self._turns[conversation_id] = turn
        turn.task = asyncio.create_task(body())
        return turn

    async def stop_all(self) -> None:
        for turn in list(self._turns.values()):
            turn.token.cancel()
            if turn.task:
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await asyncio.wait_for(turn.task, 5)
