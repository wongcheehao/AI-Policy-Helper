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
  Upload,
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

const sampleCitations: Citation[] = [
  { id: "1", title: "Return Policy v2.1", source: "policies/returns.md", snippet: "Returns accepted within 30 days..." },
  { id: "2", title: "Shipping Guidelines", source: "policies/shipping.md", snippet: "East Malaysia deliveries..." },
]

export default function PolicyHelper() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)
  const [isIngesting, setIsIngesting] = useState(false)
  const [metrics, setMetrics] = useState<Metrics>({
    total_docs: 6,
    total_chunks: 204,
    avg_retrieval_latency_ms: 0,
    avg_generation_latency_ms: 0,
    embedding_model: "local-384",
    llm_model: "stub",
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    // Simulate streaming response - replace with actual API call
    await new Promise((resolve) => setTimeout(resolve, 1500))

    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: `Based on our policy documents, I can help answer your question about "${content}". This is a demo response that would be replaced by actual RAG-generated content with citations from your ingested documents.`,
      citations: sampleCitations,
    }
    setMessages((prev) => [...prev, assistantMessage])
    setIsLoading(false)
  }

  const handleIngestDocs = async () => {
    setIsIngesting(true)
    // Simulate ingestion - replace with actual API call
    await new Promise((resolve) => setTimeout(resolve, 2000))
    setMetrics((prev) => ({
      ...prev,
      total_docs: prev.total_docs + 3,
      total_chunks: prev.total_chunks + 85,
    }))
    setIsIngesting(false)
  }

  const handleRefreshMetrics = async () => {
    // Simulate refresh - replace with actual API call
    setMetrics((prev) => ({
      ...prev,
      avg_retrieval_latency_ms: Math.floor(Math.random() * 100) + 20,
      avg_generation_latency_ms: Math.floor(Math.random() * 500) + 100,
    }))
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
                    <Upload className="w-4 h-4" />
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
