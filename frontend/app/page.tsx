"use client"

import { useState, useRef, useEffect } from "react"
import {
  FileText,
  Database,
  Zap,
  Clock,
  Cpu,
  Brain,
  RefreshCw,
  Sparkles,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ChatMessage, type Citation } from "@/components/chat-message"
import { ChatInput } from "@/components/chat-input"
import { MetricsCard } from "@/components/metrics-card"
import { apiAsk, apiAskStream, apiIngest, apiMetrics } from "@/lib/api"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
}

interface Metrics {
  total_docs: number
  total_chunks: number
  avg_retrieval_latency_ms: number
  avg_generation_latency_ms: number
  embedding_model: string
  llm_model: string
}

function toCitation(
  title: string,
  section: string | null | undefined,
  snippet: string,
  id: string,
  text?: string,
): Citation {
  const sec = (section || "").trim()
  return {
    id,
    title: sec ? `${title} — ${sec}` : title,
    source: title,
    snippet,
    text,
  }
}

export default function PolicyHelper() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)
  const [isIngesting, setIsIngesting] = useState(false)
  const [metrics, setMetrics] = useState<Metrics>({
    total_docs: 0,
    total_chunks: 0,
    avg_retrieval_latency_ms: 0,
    avg_generation_latency_ms: 0,
    embedding_model: "unknown",
    llm_model: "unknown",
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    const run = async () => {
      try {
        const m = await apiMetrics()
        setMetrics(m)
      } catch {
        // Keep defaults if backend isn't reachable yet.
      }
    }
    run()
  }, [])

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    }
    const assistantId = (Date.now() + 1).toString()
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: "assistant", content: "", citations: [] },
    ])
    setIsLoading(true)

    try {
      const k = 4
      let donePayload: any | null = null

      await apiAskStream(
        content,
        k,
        (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: (m.content || "") + token } : m,
            ),
          )
        },
        (payload) => {
          donePayload = payload
        },
      )

      if (donePayload) {
        const citations: Citation[] = (donePayload.citations || []).map((c: any, i: number) => {
          const chunkText =
            donePayload.chunks && donePayload.chunks[i]
              ? String(donePayload.chunks[i].text || "")
              : ""
          const snippet = chunkText.slice(0, 140) + (chunkText.length > 140 ? "…" : "")
          return toCitation(String(c.title || "Untitled"), c.section, snippet, String(i + 1), chunkText)
        })

        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, citations } : m)),
        )

        // Refresh metrics after a full request so the dashboard reflects real latencies.
        try {
          const m = await apiMetrics()
          setMetrics(m)
        } catch {
          // ignore
        }
      }
    } catch {
      // Fallback to non-streaming ask if SSE fails
      try {
        const res = await apiAsk(content, 4)
        const citations: Citation[] = (res.citations || []).map((c, i) => {
          const chunkText = res.chunks && res.chunks[i] ? String(res.chunks[i].text || "") : ""
          const snippet = chunkText.slice(0, 140) + (chunkText.length > 140 ? "…" : "")
          return toCitation(String(c.title || "Untitled"), c.section, snippet, String(i + 1), chunkText)
        })
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: res.answer, citations } : m,
          ),
        )
        const m = await apiMetrics()
        setMetrics(m)
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: "Error: failed to fetch answer." } : m,
          ),
        )
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleIngestDocs = async () => {
    setIsIngesting(true)
    try {
      await apiIngest()
      const m = await apiMetrics()
      setMetrics(m)
    } finally {
      setIsIngesting(false)
    }
  }

  const handleRefreshMetrics = async () => {
    const m = await apiMetrics()
    setMetrics(m)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-foreground">Policy Assistant</h1>
                <p className="text-xs text-muted-foreground">AI-powered policy & product helper</p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAdmin(!showAdmin)}
              className="gap-2"
            >
              <Database className="w-4 h-4" />
              Admin
              {showAdmin ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {/* Admin Panel */}
        {showAdmin && (
          <Card className="mb-6 bg-card border-border/50">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <Database className="w-4 h-4 text-primary" />
                System Dashboard
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <MetricsCard
                  label="Documents"
                  value={metrics.total_docs}
                  icon={<FileText className="w-5 h-5" />}
                />
                <MetricsCard
                  label="Chunks"
                  value={metrics.total_chunks}
                  icon={<Database className="w-5 h-5" />}
                />
                <MetricsCard
                  label="Retrieval"
                  value={`${metrics.avg_retrieval_latency_ms}ms`}
                  icon={<Zap className="w-5 h-5" />}
                  trend={metrics.avg_retrieval_latency_ms > 50 ? "down" : "up"}
                />
                <MetricsCard
                  label="Generation"
                  value={`${metrics.avg_generation_latency_ms}ms`}
                  icon={<Clock className="w-5 h-5" />}
                  trend={metrics.avg_generation_latency_ms > 300 ? "down" : "up"}
                />
                <MetricsCard
                  label="Embedding"
                  value={metrics.embedding_model}
                  icon={<Cpu className="w-5 h-5" />}
                />
                <MetricsCard
                  label="LLM"
                  value={metrics.llm_model}
                  icon={<Brain className="w-5 h-5" />}
                />
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={handleIngestDocs}
                  disabled={isIngesting}
                  className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground"
                >
                  {isIngesting ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Database className="w-4 h-4" />
                  )}
                  {isIngesting ? "Ingesting..." : "Ingest Sample Docs"}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleRefreshMetrics}
                  className="gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh Metrics
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Chat Area */}
        <div className="flex flex-col h-[calc(100vh-200px)]">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 pb-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                  <BookOpen className="w-8 h-8 text-primary" />
                </div>
                <h2 className="text-xl font-semibold text-foreground mb-2">
                  Ask about policies & products
                </h2>
                <p className="text-sm text-muted-foreground max-w-md mb-6">
                  Get instant answers with citations from your company documents. Try asking about
                  return policies, shipping SLAs, or product specifications.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {[
                    "Can a customer return a damaged blender after 20 days?",
                    "What's the shipping SLA to East Malaysia for bulky items?",
                    "What is the warranty policy for electronics?",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => handleSend(suggestion)}
                      className="px-4 py-2 text-sm text-foreground bg-secondary/50 hover:bg-secondary border border-border/50 rounded-lg transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <ChatMessage
                    key={message.id}
                    role={message.role}
                    content={message.content}
                    citations={message.citations}
                  />
                ))}
                {isLoading && (
                  <ChatMessage
                    role="assistant"
                    content="Searching documents and generating response"
                    isStreaming
                  />
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="pt-4 border-t border-border/50">
            <ChatInput onSend={handleSend} isLoading={isLoading} />
            <p className="text-xs text-muted-foreground text-center mt-2">
              Responses are generated from your ingested documents with source citations
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
