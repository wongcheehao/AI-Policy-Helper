# AI Policy & Product Helper

Local-first RAG assistant for policy/product Q&A with citations.

- Backend: FastAPI
- Frontend: Next.js
- Vector store: Qdrant (default) or in-memory fallback
- Run mode: stub-first for deterministic local development

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`
- Qdrant UI: `http://localhost:6333`

Ingest sample docs:

```bash
curl -X POST http://localhost:8000/api/ingest
```

Ask:

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the shipping SLA to East Malaysia for bulky items?","k":4}'
```

## Local Run (No Docker)

Backend:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Tests:

```bash
make test
```

## Configuration

Primary knobs live in `.env` (copy from `.env.example`):

- `LLM_PROVIDER=stub|openrouter|ollama` (default is `stub`)
- `OPENROUTER_API_KEY` (required only for `openrouter`)
- `VECTOR_STORE=qdrant|memory`
- `HYBRID_SEARCH_ENABLED=true|false`
- `CHUNK_SIZE`, `CHUNK_OVERLAP`
- `RERANKING_BACKEND=stub|cross-encoder`
- `ANSWER_CACHE_ENABLED`, `ANSWER_CACHE_TTL_S`, `ANSWER_CACHE_MAX_ENTRIES`

## Architecture (Current)

```mermaid
flowchart LR
userQuery[UserQuery] --> apiAsk[/api/ask]
apiAsk --> answerCache[AnswerCacheLookup]
answerCache -->|miss| retrieve[RetrieveTopK]
retrieve --> rerank[Rerank]
rerank --> generate[GenerateAnswer]
generate --> citationFilter[FilterByCitationMarkers]
citationFilter --> response[Answer+Citations+Metrics]
answerCache -->|hit| response
```

Request path in practice:

1. Ingest reads markdown/text from `data/`, chunks by size/overlap, embeds, and indexes.
2. Ask normalizes request, checks in-memory TTL answer cache.
3. On cache miss, retrieve context (dense or hybrid with Qdrant), then rerank.
4. Generate answer (stub or OpenRouter), then keep only cited chunks.
5. Return `answer`, `citations`, `chunks`, and timing `metrics`.

## API Surface

- `POST /api/ingest` -> index documents from `DATA_DIR`
- `POST /api/ask` -> sync answer with citations/chunks/metrics
- `POST /api/ask/stream` -> SSE streaming answer + final metadata event
- `GET /api/metrics` -> aggregate service metrics
- `GET /api/health` -> liveness

## Trade-offs (Current Design)

- Stub-first defaults keep local/dev deterministic and offline-friendly.
- In-memory answer cache gives fast wins but resets on restart and is per-process.
- Qdrant hybrid retrieval improves recall, but increases retrieval complexity.
- Citation extraction relies on answer citation markers; if markers are missing, sources are intentionally withheld.
- Fallback behavior prefers availability (degraded mode) over hard failure in some dependency issues.

## What To Ship Next

### 1) Split Caching: Retrieval Cache + Answer Cache

- Why: answer cache helps repeats; retrieval cache cuts repeated retrieval latency and Qdrant load.
- Scope: add retrieval TTL cache keyed by normalized query + `k` + corpus namespace.
- Metric: `p50 retrieval_ms` down by >=30% on replay queries; retrieval-cache hit rate >40%.

### 2) Pre-Retrieval Query Routing

- Why: route low-signal or non-policy queries to clarify/direct paths before expensive retrieval.
- Scope: lightweight deterministic router (`retrieve | clarify | direct`) before retrieval.
- Metric: route precision >85% on labeled query set; fewer irrelevant citations on non-policy queries.

### 3) Query Rewriting (Canonicalization)

- Why: improve recall for typos/paraphrases/domain variants.
- Scope: normalization + synonym mapping (keep original query for response UX/logging).
- Metric: top-4 source relevance improves by 10-15% on paraphrase/typo regression set.

### 4) Controlled Query Expansion

- Why: recover recall for short/ambiguous questions.
- Scope: max 2 variants, retrieve per variant with smaller k, merge with de-dup + rank fusion.
- Metric: Recall@4 improves >=10% with `p95 retrieval_ms` increase <25%.

### 5) Feedback Logging + Traceability

- Why: prioritize quality issues using real user signals.
- Scope: add `/api/feedback` with `request_id`, rating, optional reason, selected citations; wire thumbs up/down in UI.
- Metric: feedback coverage >20% and all negative feedback rows link to a retrievable request trace.

### 6) Better Observability for RAG Tuning

- Why: quickly explain bad answers and validate improvements.
- Scope: log route/rewrite/expansion/cache hit type/context summaries per request; expose counters in `/api/metrics`.
- Metric: able to debug one bad answer by `request_id` in <5 minutes.

