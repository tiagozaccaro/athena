"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  ArrowUpIcon,
  MessageCircleDashedIcon,
  MessagesSquareIcon,
  PlusIcon,
  SparklesIcon,
  SquareIcon,
  Trash2Icon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Alert, AlertDescription } from "@workspace/ui/components/alert"
import { Bubble, BubbleContent } from "@workspace/ui/components/bubble"
import { Button } from "@workspace/ui/components/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@workspace/ui/components/input-group"
import { Message, MessageContent } from "@workspace/ui/components/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@workspace/ui/components/message-scroller"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@workspace/ui/components/sheet"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { toast } from "@workspace/ui/components/toast"
import { cn } from "@workspace/ui/lib/utils"

import { Markdown } from "@/components/assistant/markdown"
import { ModelPicker } from "@/components/assistant/model-picker"
import { Steps } from "@/components/assistant/steps"
import {
  useChatStream,
  type ChatMessage,
  type ChatPart,
} from "@/components/assistant/use-chat-stream"
import { useModels, type ModelRef } from "@/components/assistant/use-models"

type Conversation = Schemas["ConversationOut"]

const SUGGESTIONS = [
  "What can this server do?",
  "How much disk space is left?",
  "Which apps are running?",
]

/** Groups a reply's parts: runs of reasoning/tool steps, and text blocks. */
function blocks(parts: ChatPart[]): (ChatPart[] | string)[] {
  const out: (ChatPart[] | string)[] = []
  for (const part of parts) {
    if (part.type === "text") {
      if (part.text) out.push(part.text)
    } else {
      const last = out.at(-1)
      if (Array.isArray(last)) last.push(part)
      else out.push([part])
    }
  }
  return out
}

function Reply({
  message,
  streaming,
}: {
  message: ChatMessage
  streaming: boolean
}) {
  const groups = blocks(message.parts)
  if (groups.length === 0 && streaming) {
    return <p className="shimmer text-sm text-muted-foreground">Thinking…</p>
  }
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {groups.map((g, i) =>
        typeof g === "string" ? (
          <Markdown key={i}>{g}</Markdown>
        ) : (
          <Steps
            key={i}
            parts={g}
            streaming={streaming && i === groups.length - 1}
          />
        )
      )}
    </div>
  )
}

function ChatList({
  conversations,
  current,
  onPick,
  onNew,
  onDelete,
}: {
  conversations: Conversation[] | null
  current: string | null
  onPick: (id: string) => void
  onNew: () => void
  onDelete: (c: Conversation) => void
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <Button variant="outline" className="justify-start" onClick={onNew}>
        <PlusIcon />
        New chat
      </Button>
      <nav
        aria-label="Chats"
        className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto"
      >
        {conversations === null ? (
          <Skeleton className="h-8 w-full" />
        ) : conversations.length === 0 ? (
          <p className="px-2 py-1 text-sm text-muted-foreground">
            No chats yet.
          </p>
        ) : (
          conversations.map((c) => (
            <div
              key={c.id}
              className={cn(
                "group/chat flex items-center rounded-md hover:bg-muted",
                c.id === current && "bg-muted"
              )}
            >
              <button
                type="button"
                onClick={() => onPick(c.id)}
                aria-current={c.id === current ? "page" : undefined}
                className="min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {c.title}
              </button>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Delete ${c.title}`}
                className="opacity-0 group-hover/chat:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100"
                onClick={() => onDelete(c)}
              >
                <Trash2Icon />
              </Button>
            </div>
          ))
        )}
      </nav>
    </div>
  )
}

function NoProviders() {
  return (
    <Empty className="h-full border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SparklesIcon />
        </EmptyMedia>
        <EmptyTitle>Set up a model first</EmptyTitle>
        <EmptyDescription>
          The assistant needs an AI provider: a cloud one with an API key, or
          Ollama running on your own hardware.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button render={<Link href="/settings/ai/" />}>
          Open Settings → AI
        </Button>
      </EmptyContent>
    </Empty>
  )
}

function Chat() {
  const router = useRouter()
  const pathname = usePathname()
  const current = useSearchParams().get("c")
  const { providers } = useModels()
  const [conversations, setConversations] = React.useState<
    Conversation[] | null
  >(null)
  const [defaultModel, setDefaultModel] = React.useState<ModelRef | null>(null)
  const [model, setModel] = React.useState<ModelRef | null>(null)
  const [draft, setDraft] = React.useState("")
  const [listOpen, setListOpen] = React.useState(false)
  const formRef = React.useRef<HTMLFormElement>(null)

  const loadList = React.useCallback(async () => {
    const { data } = await api.GET("/api/assistant/conversations")
    setConversations(data ?? [])
  }, [])

  React.useEffect(() => {
    void loadList()
    void api
      .GET("/api/settings/ai")
      .then(({ data }) => setDefaultModel(data?.default_model ?? null))
  }, [loadList])

  const chat = useChatStream(current, {
    onTitle: (title) =>
      setConversations(
        (list) =>
          list?.map((c) => (c.id === current ? { ...c, title } : c)) ?? list
      ),
    onDone: () => void loadList(),
  })
  const busy = chat.status === "streaming"

  // The picker follows the chat's own model, or the default for a new chat.
  const currentConv = conversations?.find((c) => c.id === current)
  React.useEffect(() => {
    setModel(currentConv?.model ?? defaultModel)
  }, [currentConv?.id, currentConv?.model, defaultModel]) // eslint-disable-line react-hooks/exhaustive-deps

  function open(id: string | null) {
    setListOpen(false)
    router.replace(id ? `${pathname}?c=${id}` : pathname)
  }

  async function pickModel(ref: ModelRef) {
    setModel(ref)
    if (!current) return
    const { error } = await api.PATCH(
      "/api/assistant/conversations/{conversation_id}",
      {
        params: { path: { conversation_id: current } },
        body: { model: ref },
      }
    )
    if (error)
      toast.add({
        type: "error",
        title: "Couldn't change the model",
        description: errorMessage(error),
      })
    else void loadList()
  }

  async function submit(text: string) {
    text = text.trim()
    if (!text || busy) return
    if (!model) {
      toast.add({ type: "error", title: "Pick a model first" })
      return
    }
    let id = current
    if (!id) {
      const { data, error } = await api.POST("/api/assistant/conversations", {
        body: { model },
      })
      if (!data) {
        toast.add({
          type: "error",
          title: "Couldn't start a chat",
          description: errorMessage(error),
        })
        return
      }
      id = data.id
    }
    setDraft("")
    const sending = chat.send(text, model, id)
    if (id !== current) {
      open(id)
      void loadList()
    }
    const ok = await sending
    if (!ok) setDraft((d) => d || text) // give the text back so it can be resent
  }

  async function remove(c: Conversation) {
    const { error } = await api.DELETE(
      "/api/assistant/conversations/{conversation_id}",
      {
        params: { path: { conversation_id: c.id } },
      }
    )
    if (error) {
      toast.add({
        type: "error",
        title: "Couldn't delete the chat",
        description: errorMessage(error),
      })
      return
    }
    if (c.id === current) open(null)
    void loadList()
  }

  if (providers !== null && providers.length === 0) return <NoProviders />

  const list = (
    <ChatList
      conversations={conversations}
      current={current}
      onPick={open}
      onNew={() => open(null)}
      onDelete={remove}
    />
  )
  const lastId = chat.messages.at(-1)?.id

  return (
    <div className="flex h-[calc(100svh-var(--header-height)-2rem)] min-h-96 gap-4 md:h-[calc(100svh-var(--header-height)-4rem)]">
      <aside className="hidden w-60 shrink-0 flex-col md:flex">{list}</aside>
      <section className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex items-center gap-2 md:hidden">
          <Sheet open={listOpen} onOpenChange={setListOpen}>
            <SheetTrigger render={<Button variant="outline" size="sm" />}>
              <MessagesSquareIcon />
              Chats
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-4">
              <SheetHeader className="p-0">
                <SheetTitle>Chats</SheetTitle>
              </SheetHeader>
              {list}
            </SheetContent>
          </Sheet>
          <span className="min-w-0 truncate text-sm font-medium">
            {currentConv?.title ?? "New chat"}
          </span>
        </div>
        <div className="min-h-0 flex-1">
          {chat.status === "loading" ? (
            <Skeleton className="h-24 w-full" />
          ) : chat.messages.length === 0 ? (
            <Empty className="h-full">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <MessageCircleDashedIcon />
                </EmptyMedia>
                <EmptyTitle>Ask about this server</EmptyTitle>
                <EmptyDescription>
                  The assistant can look up apps, logs, files and system stats.
                  It can't change anything yet.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent className="flex-row flex-wrap justify-center">
                {SUGGESTIONS.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    onClick={() => void submit(s)}
                  >
                    {s}
                  </Button>
                ))}
              </EmptyContent>
            </Empty>
          ) : (
            <MessageScrollerProvider autoScroll>
              <MessageScroller>
                <MessageScrollerViewport>
                  <MessageScrollerContent
                    aria-busy={busy}
                    className="gap-6 py-2 md:px-4"
                  >
                    {chat.messages.map((m) =>
                      m.role === "user" ? (
                        <MessageScrollerItem
                          key={m.id}
                          messageId={m.id}
                          scrollAnchor
                        >
                          <Message align="end">
                            <MessageContent>
                              <Bubble align="end" variant="muted">
                                <BubbleContent className="whitespace-pre-wrap">
                                  {m.parts.map((p) => p.text).join("\n")}
                                </BubbleContent>
                              </Bubble>
                            </MessageContent>
                          </Message>
                        </MessageScrollerItem>
                      ) : (
                        <MessageScrollerItem key={m.id} messageId={m.id}>
                          <Message>
                            <MessageContent className="gap-3">
                              <Reply
                                message={m}
                                streaming={busy && m.id === lastId}
                              />
                            </MessageContent>
                          </Message>
                        </MessageScrollerItem>
                      )
                    )}
                  </MessageScrollerContent>
                </MessageScrollerViewport>
                <MessageScrollerButton />
              </MessageScroller>
            </MessageScrollerProvider>
          )}
        </div>
        {chat.error ? (
          <Alert variant="destructive">
            <AlertDescription>{chat.error}</AlertDescription>
          </Alert>
        ) : null}
        <form
          ref={formRef}
          onSubmit={(e) => {
            e.preventDefault()
            void submit(draft)
          }}
        >
          <InputGroup>
            <InputGroupTextarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about this server…"
              aria-label="Message"
              className="max-h-48 min-h-14"
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault()
                  formRef.current?.requestSubmit()
                }
              }}
            />
            <InputGroupAddon align="block-end" className="pt-1">
              <ModelPicker
                providers={providers}
                value={model}
                onChange={pickModel}
              />
              {busy ? (
                <InputGroupButton
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  className="ml-auto rounded-full"
                  aria-label="Stop"
                  onClick={() => void chat.stop()}
                >
                  <SquareIcon />
                </InputGroupButton>
              ) : (
                <InputGroupButton
                  type="submit"
                  variant="default"
                  size="icon-sm"
                  className="ml-auto rounded-full aria-disabled:opacity-50"
                  // Not `disabled`: InputGroup fades entirely when it holds a disabled control.
                  aria-disabled={!draft.trim() || !model}
                  aria-label="Send"
                >
                  <ArrowUpIcon />
                </InputGroupButton>
              )}
            </InputGroupAddon>
          </InputGroup>
        </form>
      </section>
    </div>
  )
}

/** /assistant: chats with the AI assistant (docs/mvp-design.md §4.5). */
export function AssistantView() {
  return (
    <React.Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <Chat />
    </React.Suspense>
  )
}
