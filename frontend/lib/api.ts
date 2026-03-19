export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type Metrics = {
  total_docs: number;
  total_chunks: number;
  avg_retrieval_latency_ms: number;
  avg_generation_latency_ms: number;
  embedding_model: string;
  llm_model: string;
};

export type AskResponse = {
  query: string;
  answer: string;
  citations: { title: string; section?: string | null }[];
  chunks: { title: string; section?: string | null; text: string }[];
  metrics: { retrieval_ms: number; generation_ms: number };
};

export type StreamDonePayload = {
  citations: { title: string; section?: string | null }[];
  chunks: { title: string; section?: string | null; text: string }[];
  metrics: { retrieval_ms: number; generation_ms: number };
};

export async function apiMetrics(): Promise<Metrics> {
  const r = await fetch(`${API_BASE}/api/metrics`, { method: "GET" });
  if (!r.ok) throw new Error("Metrics failed");
  return r.json();
}

export async function apiIngest(): Promise<{ indexed_docs: number; indexed_chunks: number }> {
  const r = await fetch(`${API_BASE}/api/ingest`, { method: "POST" });
  if (!r.ok) throw new Error("Ingest failed");
  return r.json();
}

export async function apiAsk(query: string, k: number = 4): Promise<AskResponse> {
  const r = await fetch(`${API_BASE}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, k }),
  });
  if (!r.ok) throw new Error("Ask failed");
  return r.json();
}

export async function apiAskStream(
  query: string,
  k: number,
  onChunk: (token: string) => void,
  onDone: (payload: StreamDonePayload) => void,
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, k }),
  });
  if (!r.ok || !r.body) throw new Error("Ask stream failed");

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent: string | null = null;

  const processBlock = (block: string) => {
    const lines = block.split("\n");
    let dataLine: string | null = null;

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLine = line.slice("data:".length).trim();
      }
    }
    if (!currentEvent || !dataLine) return;

    const payload = JSON.parse(dataLine);
    if (currentEvent === "chunk") {
      onChunk(String(payload.token ?? ""));
    } else if (currentEvent === "done") {
      onDone(payload as StreamDonePayload);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      if (block.trim()) processBlock(block);
      sep = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) processBlock(buffer);
}

