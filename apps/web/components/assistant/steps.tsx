"use client"

import * as React from "react"
import { CircleCheckIcon, LoaderCircleIcon, WrenchIcon } from "lucide-react"

import {
  CodeBlock,
  CodeBlockContent,
} from "@workspace/ui/components/code-block"
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from "@workspace/ui/components/trace"

import type { ChatPart } from "@/components/assistant/use-chat-stream"

/** What each tool is called in the trace. */
const TOOL_TITLES: Record<string, [running: string, done: string]> = {
  get_capabilities: [
    "Checking what this server can do",
    "Checked what this server can do",
  ],
  get_system_stats: ["Reading system stats", "Read system stats"],
  list_apps: ["Listing apps", "Listed apps"],
  app_logs: ["Reading app logs", "Read app logs"],
  list_file_locations: ["Listing file locations", "Listed file locations"],
  list_files: ["Listing files", "Listed files"],
}

function toolTitle(part: ChatPart, running: boolean): string {
  const name = part.tool_name ?? "tool"
  const titles = TOOL_TITLES[name]
  const args = part.args as Record<string, unknown> | null
  const subject = typeof args?.name === "string" ? ` of ${args.name}` : ""
  if (!titles) return running ? `Running ${name}` : `Ran ${name}`
  return (running ? titles[0] : titles[1]) + subject
}

function pretty(text: string | null | undefined): string {
  if (!text) return ""
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

function ReasoningRow({ text, running }: { text: string; running: boolean }) {
  const [open, setOpen] = React.useState<boolean>()
  return (
    <TraceCollapsible open={open ?? running} onOpenChange={setOpen}>
      <TraceCollapsibleTrigger>
        <TraceLine status={running ? "running" : undefined}>
          <TraceIcon>
            {running ? (
              <LoaderCircleIcon className="animate-spin" />
            ) : (
              <CircleCheckIcon />
            )}
          </TraceIcon>
          <TraceTitle>{running ? "Thinking" : "Thought"}</TraceTitle>
        </TraceLine>
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent className="whitespace-pre-wrap">
        {text}
      </TraceCollapsibleContent>
    </TraceCollapsible>
  )
}

function ToolRow({ part, streaming }: { part: ChatPart; streaming: boolean }) {
  const running = part.state === "running" && streaming
  if (running || part.state === "running") {
    // Still running, or the reply stopped before the tool answered.
    return (
      <TraceLine status={running ? "running" : "pending"}>
        <TraceIcon>
          {running ? (
            <LoaderCircleIcon className="animate-spin" />
          ) : (
            <WrenchIcon />
          )}
        </TraceIcon>
        <TraceTitle>{toolTitle(part, running)}</TraceTitle>
      </TraceLine>
    )
  }
  const failed = part.state === "error"
  return (
    <TraceCollapsible>
      <TraceCollapsibleTrigger>
        <TraceLine status={failed ? "error" : undefined}>
          <TraceIcon>
            <WrenchIcon />
          </TraceIcon>
          <TraceTitle>
            {failed
              ? `Couldn't ${toolTitle(part, true).toLowerCase()}`
              : toolTitle(part, false)}
          </TraceTitle>
        </TraceLine>
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent>
        <CodeBlock size="sm" variant={failed ? "destructive" : "default"}>
          <CodeBlockContent wrap className="max-h-64">
            {pretty(failed ? (part.error ?? part.result) : part.result)}
          </CodeBlockContent>
        </CodeBlock>
      </TraceCollapsibleContent>
    </TraceCollapsible>
  )
}

/** Reasoning and tool calls of a reply, as a shadcn Trace. */
export function Steps({
  parts,
  streaming,
}: {
  parts: ChatPart[]
  streaming: boolean
}) {
  if (parts.length === 0) return null
  return (
    <Trace>
      {parts.map((part, i) =>
        part.type === "reasoning" ? (
          <ReasoningRow
            key={i}
            text={part.text ?? ""}
            running={streaming && i === parts.length - 1}
          />
        ) : (
          <ToolRow
            key={part.tool_call_id ?? i}
            part={part}
            streaming={streaming}
          />
        )
      )}
    </Trace>
  )
}
