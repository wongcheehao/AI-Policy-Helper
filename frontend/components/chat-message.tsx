"use client"

import { Bot, User, FileText, ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"

export interface Citation {
  id: string
  title: string
  source: string
  snippet: string
}

export interface ChatMessageProps {
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
  isStreaming?: boolean
}

export function ChatMessage({ role, content, citations, isStreaming }: ChatMessageProps) {
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
        <p className="text-sm leading-relaxed text-foreground">
          {content}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
          )}
        </p>
        {citations && citations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Sources
            </p>
            <div className="flex flex-wrap gap-2">
              {citations.map((citation) => (
                <button
                  key={citation.id}
                  className="group flex items-center gap-2 px-3 py-1.5 bg-secondary/50 hover:bg-secondary rounded-md border border-border/50 transition-colors"
                >
                  <FileText className="w-3 h-3 text-primary" />
                  <span className="text-xs text-foreground">{citation.title}</span>
                  <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
