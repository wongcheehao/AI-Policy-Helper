export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export type StreamDonePayload = {
  citations: { title: string; section?: string | null }[];
  chunks: { title: string; section?: string | null; text: string }[];
  metrics: { retrieval_ms: number; generation_ms: number };
};

export async function apiAsk(query: string, k: number = 4) {
  const r = await fetch(`${API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k })
  });
  if (!r.ok) throw new Error('Ask failed');
  return r.json();
}

export async function apiAskStream(
  query: string,
  k: number = 4,
  onChunk: (token: string) => void,
  onDone: (payload: StreamDonePayload) => void,
): Promise<void> {
  const r = await fetch(`${API_BASE}/api/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k }),
  });
  if (!r.ok || !r.body) throw new Error('Ask stream failed');

  const reader = r.body.getReader();
  const decoder = new TextDecoder();

  let buffer = '';
  let currentEvent: string | null = null;

  const processBlock = (block: string) => {
    const lines = block.split('\n');
    let dataLine: string | null = null;

    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice('event:'.length).trim();
      } else if (line.startsWith('data:')) {
        dataLine = line.slice('data:'.length).trim();
      }
    }

    if (!currentEvent || !dataLine) return;
    const payload = JSON.parse(dataLine);

    if (currentEvent === 'chunk') {
      onChunk(String(payload.token ?? ''));
    } else if (currentEvent === 'done') {
      onDone(payload as StreamDonePayload);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE blocks are separated by a blank line.
    let sepIndex = buffer.indexOf('\n\n');
    while (sepIndex !== -1) {
      const block = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      if (block.trim()) processBlock(block);
      sepIndex = buffer.indexOf('\n\n');
    }
  }

  if (buffer.trim()) processBlock(buffer);
}

export async function apiIngest() {
  const r = await fetch(`${API_BASE}/api/ingest`, { method: 'POST' });
  if (!r.ok) throw new Error('Ingest failed');
  return r.json();
}

export async function apiMetrics() {
  const r = await fetch(`${API_BASE}/api/metrics`);
  if (!r.ok) throw new Error('Metrics failed');
  return r.json();
}
