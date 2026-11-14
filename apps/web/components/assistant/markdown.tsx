"use client"

import * as React from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@workspace/ui/lib/utils"

// Model output is untrusted: react-markdown never renders raw HTML, and links may only
// be http(s) (the default urlTransform drops javascript: and data: URLs).
const components: Components = {
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="font-medium text-primary underline underline-offset-3"
    >
      {children}
    </a>
  ),
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  ul: ({ children }) => (
    <ul className="ml-5 list-disc space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="ml-5 list-decimal space-y-1">{children}</ol>
  ),
  h1: ({ children }) => (
    <h3 className="font-heading text-base font-semibold">{children}</h3>
  ),
  h2: ({ children }) => (
    <h3 className="font-heading text-base font-semibold">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="font-heading font-semibold">{children}</h4>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 pl-3 text-muted-foreground">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const block =
      /language-/.test(className ?? "") || String(children).includes("\n")
    return block ? (
      <code className="font-mono text-xs">{children}</code>
    ) : (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
        {children}
      </code>
    )
  },
  pre: ({ children }) => (
    <pre className="overflow-x-auto rounded-lg border bg-muted/50 p-3">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b px-2 py-1 text-left font-medium">{children}</th>
  ),
  td: ({ children }) => <td className="border-b px-2 py-1">{children}</td>,
  hr: () => <hr className="border-border" />,
}

/** The assistant's Markdown, styled with theme tokens. */
export function Markdown({
  children,
  className,
}: {
  children: string
  className?: string
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-3 text-sm", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
