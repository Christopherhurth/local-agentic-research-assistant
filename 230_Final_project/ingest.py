"""
Ingest documents into the MariaDB RAG table.

Usage:
    python ingest.py ./docs                  # ingest every .pdf/.txt/.md under ./docs
    python ingest.py ./docs/manual.pdf        # ingest a single file
    python ingest.py ./docs --reingest        # delete existing rows for a source first

For each file:
  - PDFs are loaded page by page (langchain's PyPDFLoader), so `page`
    matches the real PDF page number.
  - .txt / .md files are treated as a single page (page = 0).
  - Each page's text is split into overlapping chunks with
    RecursiveCharacterTextSplitter; `chunk` is the chunk's index within
    that page.
  - Each chunk is embedded with Ollama (EMBED_MODEL, default
    nomic-embed-text -> 768 dims, matching `embedding VECTOR(768)`).
  - `id` is a deterministic sha256 of (source, page, chunk), so re-running
    ingest on an unchanged document is a no-op (upsert), and re-running
    it after an edit just overwrites those rows.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

import db_2 as db

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "3306"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "rag_db"),
}
TABLE = os.getenv("DB_TABLE", "rag_files")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EXPECTED_DIM = int(os.getenv("EMBED_DIM", "768"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}


def load_pages(path: Path) -> list[tuple[int, str]]:
    """Return a list of (page_number, page_text) for a single file."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        docs = PyPDFLoader(str(path)).load()
        # PyPDFLoader sets metadata["page"] to a 0-indexed page number.
        return [(doc.metadata.get("page", i), doc.page_content) for i, doc in enumerate(docs)]
    elif suffix in (".txt", ".md"):
        text = TextLoader(str(path), encoding="utf-8").load()[0].page_content
        return [(0, text)]
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def make_id(source: str, page: int, chunk_idx: int) -> str:
    return hashlib.sha256(f"{source}:{page}:{chunk_idx}".encode("utf-8")).hexdigest()


def discover_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )


def ingest_path(path_str: str, reingest: bool = False) -> None:
    root = Path(path_str)
    files = discover_files(root)
    if not files:
        print(f"No {sorted(SUPPORTED_SUFFIXES)} files found under {path_str}")
        return

    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    with db.connection(DB_CONFIG) as conn:
        for f in files:
            source = f.name
            if reingest:
                deleted = db.delete_source(conn, TABLE, source)
                if deleted:
                    print(f"Removed {deleted} existing rows for {source}")

            pages = load_pages(f)
            n_chunks = 0
            for page_num, page_text in tqdm(pages, desc=f"{f.name}", unit="page"):
                chunks = splitter.split_text(page_text)
                if not chunks:
                    continue

                vectors = embeddings.embed_documents(chunks)
                for chunk_idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                    if len(vector) != EXPECTED_DIM:
                        raise ValueError(
                            f"'{EMBED_MODEL}' produced a {len(vector)}-dim embedding, "
                            f"but the table column is VECTOR({EXPECTED_DIM}). "
                            f"Set EMBED_MODEL/EMBED_DIM to a matching embedding model."
                        )
                    chunk_id = make_id(source, page_num, chunk_idx)
                    db.upsert_chunk(
                        conn, TABLE, chunk_id, source, page_num, chunk_idx, chunk_text, vector
                    )
                    n_chunks += 1

            print(f"Ingested {source}: {len(pages)} page(s), {n_chunks} chunk(s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into the MariaDB RAG table")
    parser.add_argument("path", help="File or directory to ingest (.pdf, .txt, .md)")
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Delete existing rows for each source file before inserting new ones",
    )
    args = parser.parse_args()
    ingest_path(args.path, reingest=args.reingest)
