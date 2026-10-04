# 📖 StudyBuddy — Local-First AI Study Assistant

> **Built for the "Build for a Friend" Hackathon**  
> Open-source AI at its core · Runs entirely on your laptop · No cloud, no cost, no data leaks.

---

![StudyBuddy UI - Main Interface](screenshots/firstlanding.png)

## 🧩 The Problem It Solves

My friend is preparing for their university exams and has **hundreds of pages of handwritten-scan PDFs, lecture slides, and typed notes** — all scattered across folders, never searchable, impossible to revise efficiently.

The usual options are bad:
- **Uploading notes to ChatGPT/Gemini** — their personal notes leave their device and sit on someone else's server forever.
- **Manual re-reading** — takes hours, doesn't tell you which topics you're weakest at.
- **Paid tools** — cost money per query, stop working without internet.

**StudyBuddy solves all three problems at once:**

1. 🔒 **Drop your PDFs → search and get answered** — completely locally, offline-capable.
2. 🧠 **Ask questions in plain English** — get a direct 2–3 line answer citing the exact page.
3. 📝 **Take auto-generated quizzes** — MCQ + short answer, built from *your* notes, not generic content.
4. 📊 **Know your weak spots** — an ML predictor tells you which topics to revise based on your quiz history.

---

## 🌍 Why Open-Source & Local AI Matters Here

This project is built *entirely* on open-weight and open-source tools:

| Component | Open Tool | Why It Matters |
|-----------|-----------|----------------|
| LLM (answers, quiz gen, grading) | **Gemma 2b** via Ollama | Free to run, no API key, no billing surprises |
| Embeddings | **BGE-M3** via Ollama | State-of-the-art multilingual embeddings, self-hosted |
| Vector DB | **pgvector** (PostgreSQL extension) | No separate vector DB service; auditable SQL |
| Workflow engine | **Temporal** (open-source) | Durable, retry-safe ingestion without paying for orchestration SaaS |
| LLM routing | **Python agent** (custom tool router) | Fully transparent — you can read and change every decision |
| Frontend | **React + Vite** | Zero lock-in |

### What "open" unlocks for my friend:
- ✅ **Runs on a laptop with no internet** after first model pull
- ✅ **Personal notes never leave the machine** — no uploads to OpenAI, Anthropic, or anyone
- ✅ **Zero cost per query** — no API bills even if they ask 10,000 questions before the exam
- ✅ **Swappable models** — set `LLM_MODEL=gemma3:4b` in `.env` and restart; no code change
- ✅ **Fine-tunable** — the same Ollama setup supports Modelfiles and LoRA fine-tunes if we want to specialize Gemma on exam-style Q&A

> *"I couldn't use ChatGPT because my notes have personal diagrams and draft answers. With this, it stays on my PC and actually works offline during the commute."*

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser  →  React + Vite UI  (port 5173)                                │
│  Tabs: Ask/Search  |  Practice Quiz  |  Weak Topics Dashboard            │
└─────────────────────────────────────┬────────────────────────────────────┘
                                      │ HTTP/JSON
┌─────────────────────────────────────▼────────────────────────────────────┐
│  FastAPI  (port 8000)  ·  core/main.py                                   │
│                                                                          │
│  POST /search   →  Cache → Hybrid Search → Gate → Gemma Synthesis        │
│  GET  /quiz     →  Generate / Retrieve MCQ + Short-Answer Questions      │
│  POST /attempts →  Log quiz results for ML predictor                     │
│  GET  /weak-topics → TabPFN weak-topic prediction                        │
│  GET  /stats    →  Operational metrics (LLM skip %, cache hit rate)      │
│  POST /upload   →  Save PDF to /uploads/ folder                          │
│  POST /agent/chat → Tool-routing agent with thread memory                │
└──────┬──────────────────────────────────────────────────────────────────┘
       │                          │ Ollama HTTP API
┌──────▼──────────────────┐  ┌───▼──────────────────────────────────┐
│  PostgreSQL 16           │  │  Ollama (Docker)                     │
│  + pgvector extension    │  │  bge-m3  → embeddings (1024-dim)     │
│                          │  │  gemma:2b → answers, quiz, grading   │
│  documents               │  └──────────────────────────────────────┘
│  chunks (+ vector col)   │
│  answer_cache            │  ┌──────────────────────────────────────┐
│  questions               │  │  Temporal (Docker)                   │
│  attempts                │  │  Durable ingestion workflows         │
└──────────────────────────┘  │  Retry-safe: parse → chunk → embed  │
                              └──────────────────────────────────────┘
       ▲
       │ (file events)
┌──────┴──────────────────────────────────────────────────────────────────┐
│  File Watcher  (watcher/watcher.py)                                      │
│  Watchdog monitors /uploads/ → triggers ingest on new/changed files      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 How It Works — Step by Step

### 1. Upload & Ingest a PDF

```
You drag a PDF into the UI
       │
       ▼
POST /upload  → saves file to /uploads/
       │
       ▼
watcher.py detects the new file
       │
       ▼
POST /ingest  → starts Temporal IngestWorkflow
       │
       ├── Activity: parse   (PyMuPDF extracts text page by page)
       ├── Activity: chunk   (split into ~400-token chunks with 50-token overlap)
       ├── Activity: embed   (BGE-M3 via Ollama → 1024-dim vector per chunk)
       └── Activity: upsert  (store chunks + vectors in PostgreSQL)

Document status changes: "pending" → "ready"
Searchable in ~30–60 seconds.
```

**Why token-based chunking?**
Lecture PDFs often have no sentence punctuation (bullet lists, tables, headers).
Sentence splitters fail on these — they return entire pages as one chunk.
We hard-split at 400 tokens so each chunk is a focused, retrievable unit.

![StudyBuddy Document Inspector & Extracted Passages Modal](screenshots/chunks.png)

---

### 2. Ask a Question

```
You type: "What are the 17 SDGs and when were they adopted?"
       │
POST /search {query: "...", synthesize: true}
       │
       ├── Step 1: Answer Cache Check
       │   Embed query → cosine search in answer_cache table
       │   CACHE HIT  → return cached answer instantly (no LLM!)
       │   CACHE MISS → continue ↓
       │
       ├── Step 2: Hybrid Search  (core/search.py)
       │   ┌─ Vector search: embed query → top-20 by cosine (pgvector <=>)
       │   ├─ BM25 search:   PostgreSQL tsvector → top-20 by ts_rank_cd
       │   └─ RRF merge:     score = Σ 1/(60 + rank) → combined top-5 chunks
       │
       ├── Step 3: Confidence Gate  (core/gate.py)
       │   Evaluate score margin between top results
       │   HIGH confidence  → note gate decision (could skip LLM)
       │   MEDIUM / LOW     → route to LLM synthesis
       │
       └── Step 4: LLM Answer Synthesis  (core/answer.py)
           Build citation prompt with top-3 chunks:
             "Source [Module_1.pdf, p.2]: <chunk text> ..."
           POST to Ollama gemma:2b  (max 80 tokens, temp 0)
           → "• SDGs adopted in Sept 2015 [Module_1.pdf, p.2]
              • 17 goals covering poverty, climate, health..."
           Auto-cache this Q→A pair for future requests.

Response UI:
  ┌────────────────────────────────────────────────────┐
  │ 🤖 AI Answer                          Cache: MISS  │
  │ • SDGs adopted in Sept 2015 [p.2]                  │
  │ • 17 goals: No Poverty, Zero Hunger, ...           │
  └────────────────────────────────────────────────────┘
  ▼ Source Passages (collapsed — click to expand)
    📄 Module_1.pdf  §SDGs  p.2  score 0.032
    📄 Module_1.pdf  §Timeline  p.5  score 0.028
```

> **The LLM is the last resort.** Cache hits and high-confidence retrievals skip Gemma entirely.
> In practice, repeated exam-prep questions (same question rephrased) almost always hit the cache.

![StudyBuddy Hybrid Search & Direct AI Answer Synthesis](screenshots/output.png)

---

### 3. Practice Quiz

```
GET /quiz?topic=Environmental+Studies&count=5
       │
       ├── Check questions table for cached questions on this topic
       │   (cached) → return immediately
       │   (none)   → generate with Gemma:
       │                Prompt: "Create 5 MCQ questions from this passage..."
       │                Store generated questions in DB for reuse
       │
       ▼
UI shows MCQ + Short-Answer questions

User answers → POST /attempts  (logs: topic, correct, seconds_taken)
                       │
Short-answer  → POST /quiz/grade-short
                       │
               Gemma grades against rubric from source chunk
               Returns: score (0–1) + feedback string
```

---

### 4. Weak Topics Prediction

```
GET /weak-topics
       │
       └── core/weak_topics.py
           Loads attempt history from DB
           Groups by topic: accuracy rate, avg time, recent trend
           Ranks topics by P(wrong) — lowest accuracy first
           Returns top weak topics to show in Dashboard
```

> For cold-start (few attempts), falls back to ordering by accuracy rate.
> As you take more quizzes, the ranking becomes more accurate.

---

## 🗄️ Database Schema

```sql
-- Core ingestion
documents   (id, filename, sha256, status, ingested_at)
chunks      (id, doc_id, page, heading, text,
             embedding VECTOR(1024),     ← pgvector
             tsv TSVECTOR)               ← BM25 full-text

-- Answer intelligence
answer_cache (id, question, question_emb VECTOR(1024), answer, created_at)

-- Quiz & analytics
questions   (id, topic, question_text, type, options JSONB, answer, difficulty)
attempts    (id, question_id, topic, correct BOOLEAN, seconds_taken, attempted_at)
```

Indexes:
- `HNSW` on `chunks.embedding` for fast vector search
- `GIN` on `chunks.tsv` for fast full-text search
- `ivfflat` on `answer_cache.question_emb` for fast cache lookup

---

## 🛠️ Full Stack

| Layer | Technology | Open Source? |
|-------|-----------|--------------|
| Frontend | React 18 + Vite + TypeScript | ✅ |
| Backend API | FastAPI (Python 3.11+) | ✅ |
| LLM inference | Gemma 2b via Ollama | ✅ Open-weight |
| Embeddings | BGE-M3 via Ollama | ✅ Open-weight |
| Vector DB | PostgreSQL 16 + pgvector | ✅ |
| Full-text search | PostgreSQL tsvector (BM25) | ✅ |
| Workflow engine | Temporal (durable ingestion) | ✅ |
| File watching | Watchdog (Python) | ✅ |
| PDF parsing | PyMuPDF (fitz) | ✅ |
| Tokenization | tiktoken (cl100k_base) | ✅ |
| Observability | Sentry SDK | ✅ |

---

## 🚀 Installation & Running

### Prerequisites

- **Docker Desktop** (for PostgreSQL + Ollama + Temporal)
- **Python 3.11+**
- **Node.js 18+**

### Step 1 — Clone and Configure

```powershell
git clone <your-repo-url>
cd studybuddy

# Copy environment template and edit if needed
Copy-Item .env.example .env
```

Key `.env` settings:
```env
DATABASE_URL=postgresql+psycopg://studybuddy:studybuddy@localhost:5433/studybuddy
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gemma:2b          # swap to gemma3:4b for better answers
EMBED_MODEL=bge-m3
UPLOAD_DIR=./uploads
```

### Step 2 — Start Infrastructure (Docker)

```powershell
docker compose up -d
```

This starts:
- **PostgreSQL 16 + pgvector** on port `5433`
- **Ollama** on port `11434` (CPU by default; uncomment GPU block for CUDA)
- **Temporal** workflow engine on port `7233`
- **Temporal Web UI** on port `8233`

Wait ~30 seconds for services to be healthy:
```powershell
docker compose ps   # all services should show "healthy"
```

### Step 3 — Pull AI Models (one-time, ~3 GB)

```powershell
# Pull the LLM (Gemma 2b — fits on most laptops)
docker exec studybuddy_ollama ollama pull gemma:2b

# Pull the embedding model
docker exec studybuddy_ollama ollama pull bge-m3

# Verify models are ready
curl http://localhost:11434/api/tags
```

> **GPU users:** uncomment the `deploy` block in `docker-compose.yml` to use NVIDIA GPU.
> CPU works fine — embedding is fast; Gemma answer generation takes ~10–20s on CPU.

### Step 4 — Install Python Dependencies

```powershell
cd studybuddy

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### Step 5 — Start All Services (5 Terminals)

Open 5 PowerShell terminals in `c:\Users\livan\studybuddy`:

**Terminal 1 — FastAPI Backend**
```powershell
.venv\Scripts\uvicorn core.main:app --reload --port 8000
# → API:  http://localhost:8000
# → Docs: http://localhost:8000/docs
```

**Terminal 2 — Temporal Ingestion Worker**
```powershell
.venv\Scripts\python worker/worker.py
```

**Terminal 3 — File Watcher**
```powershell
.venv\Scripts\python watcher/watcher.py
# Monitors /uploads/ and triggers ingestion automatically
```

**Terminal 4 — Frontend (React + Vite)**
```powershell
cd ui
npm install        # first time only
npm run dev
# → UI: http://localhost:5173
```

**Terminal 5 — (Optional) Docker logs**
```powershell
docker logs -f studybuddy_ollama   # watch Gemma generation requests
```

### Step 6 — Verify Everything Works

```powershell
# Backend health
curl http://localhost:8000/health
# → {"status": "ok"}

# Ollama health
curl http://localhost:11434/api/tags
# → {"models": [{"name": "gemma:2b", ...}, {"name": "bge-m3", ...}]}
```

Open **http://localhost:5173** — you should see the StudyBuddy interface.

---

## 📄 First-Time Usage

1. **Upload a PDF** — Drag your notes onto the sidebar dropzone
2. **Wait for ingestion** — Status changes from `pending` → `ready` (30–60 seconds)
3. **Ask a question** — Type in the search box, click Search
4. **See the AI Answer** — Bulleted, cited, concise
5. **Try a Quiz** — Click "Practice Quiz" tab, select a topic
6. **Check Weak Topics** — Click "Weak Topics" tab after a few quiz attempts

---

## 🧪 API Reference (Quick)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/upload` | Upload a PDF file |
| `POST` | `/ingest` | Manually trigger ingestion for a path |
| `GET` | `/documents` | List all ingested documents |
| `DELETE` | `/documents/{filename}` | Delete a document and its chunks |
| `POST` | `/search` | Hybrid search + AI answer synthesis |
| `GET` | `/quiz` | Get quiz questions for a topic |
| `POST` | `/attempts` | Log a quiz attempt |
| `POST` | `/quiz/grade-short` | Grade a free-text answer with Gemma |
| `GET` | `/weak-topics` | Get predicted weak study topics |
| `GET` | `/stats` | Operational metrics |
| `POST` | `/agent/chat` | Chat with the AI agent (tool-routing) |

Full interactive docs: **http://localhost:8000/docs**

---

## 🔑 Key Design Decisions

### "LLM as Last Resort"
Gemma is only called when:
1. The answer cache has no similar previous question, **AND**
2. We actually need synthesis (not just retrieval)

In exam-prep mode (repeated questions), most queries return cached answers with **zero LLM inference**. This keeps latency low and GPU/CPU load minimal.

### Hybrid Search (Vector + BM25)
- **Vector alone** misses exact keyword matches (dates, proper nouns, article numbers)
- **BM25 alone** misses semantic similarity ("sustainable development" vs "SDGs")
- **RRF fusion** of both gives the best result reliably

### Why Not Use the OpenAI API?
A friend's exam notes are personal. They contain draft answers, personal mnemonics, diagrams, and struggles. Sending that to a cloud API means it may be logged, trained on, or stored. A local Gemma model means **the data never leaves the machine**.

### Swappable Models
Change one line in `.env`:
```env
LLM_MODEL=gemma3:4b     # better answers, needs more RAM
LLM_MODEL=llama3.2:3b   # alternative open-weight option
EMBED_MODEL=nomic-embed-text  # lighter embedding model
```
Restart the backend — no code changes required.

---

## 📊 Observability

The `/stats` endpoint and Dashboard tab show:
- **% queries answered without LLM** (cache hits + high-confidence retrieval)
- **Cache hit rate**
- **Total documents and chunks indexed**
- **LLM call count**

Sentry tracing (optional, set `SENTRY_DSN` in `.env`) adds:
- Per-request spans: cache → retrieve → gate → llm → grade
- `llm_used: true/false` tag on every trace

---

## 📁 Project Structure

```
studybuddy/
├── core/
│   ├── main.py          # FastAPI app — all routes
│   ├── parsing.py       # PDF text extraction (PyMuPDF)
│   ├── chunking.py      # Token-based chunking (400 tok, 50 overlap)
│   ├── embedding.py     # BGE-M3 embeddings via Ollama
│   ├── ingest.py        # Orchestrates parse → chunk → embed → store
│   ├── search.py        # Hybrid search: vector + BM25 + RRF
│   ├── gate.py          # Confidence gate (when to call LLM)
│   ├── cache.py         # Semantic answer cache (pgvector)
│   ├── answer.py        # Gemma answer synthesis with citations
│   ├── quiz.py          # Question generation and attempt logging
│   ├── grader.py        # Free-text grading with Gemma rubric
│   ├── weak_topics.py   # Weak topic prediction from attempt history
│   ├── stats.py         # Operational metrics
│   ├── agent.py         # Tool-routing agent with thread memory
│   ├── db.py            # SQLAlchemy models (Document, Chunk, etc.)
│   ├── config.py        # Pydantic settings from .env
│   └── schema.sql       # PostgreSQL schema (auto-run on first start)
├── ui/
│   └── src/
│       ├── App.tsx              # Root layout, tab routing
│       ├── components/
│       │   ├── SearchBox.tsx    # Ask/Search interface
│       │   ├── DropZone.tsx     # PDF drag-drop upload
│       │   ├── UploadStatus.tsx # Document list
│       │   ├── QuizView.tsx     # Quiz interface
│       │   └── DashboardView.tsx # Weak Topics + Stats
│       └── index.css            # Design system
├── worker/
│   └── worker.py        # Temporal workflow worker
├── watcher/
│   └── watcher.py       # Watchdog file monitor
├── docker-compose.yml   # PostgreSQL + Ollama + Temporal
├── requirements.txt     # Python dependencies
└── .env.example         # Environment template
```

---

## 🤝 Why Open Innovation Mattered Here

A closed-source cloud solution (GPT-4 API, Gemini API) would have solved the surface problem but failed on what mattered most:

1. **Privacy** — Personal notes shouldn't leave the device. Full stop.
2. **Cost** — A student preparing for exams shouldn't pay per query. With open models, it's free forever.
3. **Offline** — Exam prep often happens during commutes or in areas with bad connectivity. This runs fully offline after setup.
4. **Transparency** — Every decision (which chunk was retrieved, why the LLM was called, what prompt was used) is auditable Python code. Nothing is hidden in a black-box API.
5. **Adaptability** — When Gemma 2b gives weak answers, we can swap to `gemma3:4b` or fine-tune on exam-style Q&A pairs with Ollama's Modelfile system — something impossible with a closed API.

> The open-source stack didn't just make this *possible* — it made it *right* for the person it was built for.

---

## 🔧 Troubleshooting

**Ollama not responding?**
```powershell
docker restart studybuddy_ollama
curl http://localhost:11434/api/tags
```

**Embeddings failing?**
```powershell
# Check bge-m3 is pulled
docker exec studybuddy_ollama ollama list
# If missing:
docker exec studybuddy_ollama ollama pull bge-m3
```

**Gemma answer times out (>60s on CPU)?**  
Switch to a lighter model in `.env`:
```env
LLM_MODEL=gemma:2b    # default — should be fine on most laptops
```
Or reduce `num_predict` in `core/answer.py` from 80 to 60.

**Database connection error?**
```powershell
docker compose ps     # verify postgres is "healthy"
docker compose logs postgres
```

**Port conflict?**
Edit `docker-compose.yml` to change `5433` (Postgres) or `11434` (Ollama) to free ports, then update `.env` accordingly.