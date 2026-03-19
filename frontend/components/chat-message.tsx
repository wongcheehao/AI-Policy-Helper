"use client"

import { useState } from "react"
import { Bot, User, FileText, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

export interface Citation {
  id: string
  title: string
  source: string
  snippet: string
  text?: string
}

export interface ChatMessageProps {
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
  isStreaming?: boolean
}

const markdownComponents = {
  h1: ({ children, ...props }: any) => (
    <h1 className="text-base font-semibold mt-3 mb-2" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: any) => (
    <h2 className="text-sm font-semibold mt-3 mb-2" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: any) => (
    <h3 className="text-sm font-semibold mt-3 mb-2" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }: any) => (
    <p className="text-sm leading-relaxed mb-2" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }: any) => (
    <ul className="list-disc pl-5 mb-2" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: any) => (
    <ol className="list-decimal pl-5 mb-2" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: any) => (
    <li className="mb-1" {...props}>
      {children}
    </li>
  ),
  code: ({ children, ...props }: any) => (
    <code
      className="px-1 py-0.5 rounded bg-muted/50 font-mono text-[12px]"
      {...props}
    >
      {children}
    </code>
  ),
  pre: ({ children, ...props }: any) => (
    <pre
      className="p-3 rounded-md bg-muted/50 overflow-x-auto text-[12px] leading-relaxed"
      {...props}
    >
      {children}
    </pre>
  ),
}

export function ChatMessage({ role, content, citations, isStreaming }: ChatMessageProps) {
  const hasCitations = (citations?.length || 0) > 0

  return (
    <div
      className={cn(
        "flex gap-4 p-4 rounded-lg",
        role === "user" ? "bg-secondary/50" : "bg-card"
      )}
    >
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          role === "user" ? "bg-muted" : "bg-primary/20"
        )}
      >
        {role === "user" ? (
          <User className="w-4 h-4 text-muted-foreground" />
        ) : (
          <Bot className="w-4 h-4 text-primary" />
        )}
      </div>
      <div className="flex-1 space-y-3">
        <div className="text-foreground">
          {role === "assistant" ? (
            <ReactMarkdown skipHtml components={markdownComponents as any}>
              {content}
            </ReactMarkdown>
          ) : (
            <p className="text-sm leading-relaxed">{content}</p>
          )}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse align-middle" />
          )}
        </div>

        {hasCitations && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Sources
            </p>
            <div className="space-y-2">
              {citations.map((citation) => (
                <CitationRow key={citation.id} citation={citation} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function CitationRow({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className={cn(
            "w-full text-left",
            "flex items-center justify-between gap-3",
            "px-3 py-2 rounded-md",
            "bg-secondary/30 hover:bg-secondary/50",
            "border border-border/50 transition-colors",
          )}
          aria-expanded={open}
        >
          <span className="flex items-center gap-2 min-w-0">
            <FileText className="w-4 h-4 text-primary flex-shrink-0" />
            <span className="text-xs text-foreground truncate">{citation.title}</span>
          </span>
          <span className="flex items-center gap-2 flex-shrink-0">
            <span className="text-[11px] text-muted-foreground">
              {open ? "Hide" : "Show"}
            </span>
            {open ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </span>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="mt-2 ml-6 p-3 rounded-md border border-border/50 bg-background/50">
          <div className="text-[11px] font-medium text-muted-foreground mb-1">
            {citation.source}
          </div>
          <div className="text-foreground">
            <ReactMarkdown skipHtml components={markdownComponents as any}>
              {citation.text || citation.snippet}
            </ReactMarkdown>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
