"use client"

import * as React from "react"
import { yaml } from "@codemirror/lang-yaml"
import { EditorView } from "@codemirror/view"
import CodeMirror from "@uiw/react-codemirror"

import { cn } from "@workspace/ui/lib/utils"

/**
 * CodeMirror 6 editor themed from the app's CSS variables, so it follows the active
 * base color, theme, radius and light/dark mode (docs/mvp-design.md §5.3).
 */
const tokens = EditorView.theme({
  "&": {
    backgroundColor: "transparent",
    color: "var(--foreground)",
    fontSize: "0.8125rem",
  },
  "&.cm-focused": { outline: "none" },
  ".cm-content": {
    fontFamily: "var(--font-mono)",
    caretColor: "var(--foreground)",
    padding: "0.5rem 0",
  },
  ".cm-gutters": {
    backgroundColor: "transparent",
    color: "var(--muted-foreground)",
    border: "none",
  },
  ".cm-activeLine, .cm-activeLineGutter": {
    backgroundColor: "color-mix(in oklab, var(--muted) 60%, transparent)",
  },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--foreground)" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection":
    {
      backgroundColor:
        "color-mix(in oklab, var(--primary) 25%, transparent) !important",
    },
  ".cm-placeholder": { color: "var(--muted-foreground)" },
})

export type CodeEditorProps = {
  value: string
  onChange?: (value: string) => void
  language?: "yaml"
  readOnly?: boolean
  placeholder?: string
  minHeight?: string
  maxHeight?: string
  className?: string
  "aria-label"?: string
  "aria-invalid"?: boolean
}

function CodeEditor({
  value,
  onChange,
  language = "yaml",
  readOnly,
  placeholder,
  minHeight = "12rem",
  maxHeight = "32rem",
  className,
  "aria-invalid": invalid,
  ...props
}: CodeEditorProps) {
  const extensions = React.useMemo(
    () => [
      tokens,
      EditorView.lineWrapping,
      ...(language === "yaml" ? [yaml()] : []),
    ],
    [language]
  )
  return (
    <div
      data-slot="code-editor"
      aria-invalid={invalid}
      className={cn(
        "overflow-hidden rounded-lg border border-input bg-transparent shadow-xs transition-[color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:bg-input/30",
        className
      )}
    >
      <CodeMirror
        value={value}
        onChange={onChange}
        readOnly={readOnly}
        placeholder={placeholder}
        extensions={extensions}
        theme="none"
        minHeight={minHeight}
        maxHeight={maxHeight}
        basicSetup={{ foldGutter: false, highlightActiveLineGutter: true }}
        aria-label={props["aria-label"]}
      />
    </div>
  )
}

export { CodeEditor }
