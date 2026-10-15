# Local Agentic Research Assistant

Final project for AICC-230 (AI and Cloud Computing), College of Western Idaho.

A fully local research assistant that answers questions from a collection of 29 PDFs (state falconry regulations and guides). It searches the documents, judges whether the results are relevant, and answers with citations (file name and page). If the documents don't cover the question, it says so instead of guessing. Nothing leaves the computer: the models, the database and the search all run locally.

## How it works

1. **`ingest.py`** splits each PDF into chunks, creates embeddings with Ollama (`nomic-embed-text`, 768 dimensions) and stores them in MariaDB.
2. **`rag_mcp_server.py`** exposes a `semantic_search(query, k)` tool over MCP (Model Context Protocol), using MariaDB's built-in vector search with cosine distance.
3. **`agent_demo_style.py`** runs a tool-calling agent loop on Ollama (`qwen2.5`). The model searches, reads the results, may search again, then answers with citations or declines.

Supporting files: `db_2.py` (database helpers), `check_db.py` (lists each ingested file and its chunk count).

## Tech stack

Python, Ollama, MariaDB 11.7+ (vector search), MCP, LangChain (text splitting), pypdf, PyMySQL

## Results

- Relevant matches scored about **0.21–0.25** cosine distance; unrelated questions scored about **0.46–0.49**. That gap is what lets the agent tell a grounded answer from a question it should decline.
- Sample runs are in the transcript files: a normal answer (`run_1_nrml.md`), a correct decline (`run_2_correct_decline.md`), and a multi-source answer (`run_3_1_multiSource_correct.md`).
- A misspelled question ("pemit" for "permit") still found the right passage.

## Problems I hit and fixed

- **Vector index error 1071:** the `id` column was a long text type. Fixed by changing it to `CHAR(64)` with an ASCII collation.
- **The model declined without searching:** declining looked safe but wasn't based on evidence. Added a guard that makes the agent search before it can decline.
- **Citations printed literally as "(source, p.17)":** the prompt example was being copied word for word. Rewrote the example so the model fills in real file names and pages.

## Setup

Requirements: Python, MariaDB 11.7 or newer, and Ollama.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

ollama pull nomic-embed-text
ollama pull qwen2.5
```

Copy `.env.example` to `.env` and fill in your database settings. **Never commit your real `.env` file.**

Create the table (in DBeaver or the MariaDB client). It needs a short ASCII `id` key, a `VECTOR(768)` column and a vector index:

```sql
ALTER TABLE AAI_230_final_docs
  MODIFY id CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL;

ALTER TABLE AAI_230_final_docs
  ADD VECTOR INDEX (embedding) M=6 DISTANCE=cosine;
```

## Running it

```bash
python ingest.py ./pdfs          # load the PDFs into the database
python check_db.py               # confirm every file was ingested
python rag_mcp_server.py --selftest "your question"   # test search on its own
python agent_demo_style.py       # start the agent; a blank line quits
```

The PDFs themselves aren't included in this repo. Put your own text-based PDFs (10–30 works well) in a folder and point `ingest.py` at it.

## Known limitations and next steps

- Chunks are large (about 4,000 characters), so one result can mix topics. Next step: smaller chunks.
- No memory between questions.
- Some source documents overlap.
- Ideas: a distance cutoff, conversation memory and a simple web UI.

## Note on AI assistance

I used Claude to help write and debug the code. I ran every step myself and checked the answers against the source PDF pages.
