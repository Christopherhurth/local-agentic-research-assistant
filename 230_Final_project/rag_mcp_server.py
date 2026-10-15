#!/usr/bin/env python3
"""rag_mcp_server.py for Agentic AI course 230 final project"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import db_2 as db

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("rag-mcp")

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
DISTANCE_METRIC = os.getenv("DISTANCE_METRIC", "cosine")

DEFAULT_K = 4
MAX_K = 8  # hard cap so a model can't flood its own context window

# Optional: drop chunks whose distance is above this value. Unset = keep all
# and let the model judge relevance. Use --selftest to find a sensible number.
_max_dist = os.getenv("MAX_DISTANCE", "").strip()
MAX_DISTANCE = float(_max_dist) if _max_dist else None

mcp = MCPServer("rag-search")
_embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)


def _search(query: str, k: int) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")
    k = max(1, min(int(k), MAX_K))

    vector = _embeddings.embed_query(query)
    if len(vector) != EXPECTED_DIM:
        raise ValueError(
            f"Embedding model '{EMBED_MODEL}' returned {len(vector)} dims but the "
            f"table column is VECTOR({EXPECTED_DIM}). Use the same model as ingestion."
        )

    logger.info("semantic_search query=%r k=%d", query, k)
    with db.connection(DB_CONFIG) as conn:
        rows = db.search_similar(conn, TABLE, vector, k=k, distance=DISTANCE_METRIC)

    results = []
    for row in rows:
        dist = float(row["distance"])
        if MAX_DISTANCE is not None and dist > MAX_DISTANCE:
            continue
        results.append(
            {
                "source": row["source"],
                "page": int(row["page"]) + 1,
                "chunk": int(row["chunk"]),
                "distance": round(dist, 4),
                "content": row["content"],
            }
        )

    if not results:
        # An empty list would produce zero content blocks for the client,
        # return an explicit message the model can read.
        return [{"message": "No chunks found that are close enough to this query."}]
    return results


@mcp.tool()
def semantic_search(query: str, k: int = DEFAULT_K) -> list[dict[str, Any]]:
    """
    Search the private document collection by meaning (vector similarity).

    Use this for ANY question about the documents. Returns the k most similar
    text chunks, each with its source file, page number, and a distance score
    (lower = more similar; large distances usually mean unrelated text).

    Args:
        query: A natural-language search query. Rephrase with specific key
            terms if a first attempt returns nothing useful.
        k: How many chunks to return (default 4, maximum 8).
    """
    try:
        return _search(query, k)
    except Exception as exc:  # noqa: BLE001
        logger.exception("semantic_search failed")
        # ToolError makes the real message reach the client/model.
        raise ToolError(f"semantic_search failed: {exc}") from exc


def _selftest(query: str) -> None:
    for i, r in enumerate(_search(query, DEFAULT_K), 1):
        if "message" in r:
            print(r["message"])
            continue
        print(f"{i}. {r['source']} p.{r['page']} chunk {r['chunk']}  distance={r['distance']}")
        print(f"   {r['content'][:150].replace(chr(10), ' ')}...\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest(" ".join(sys.argv[2:]) or "test query")
    else:
        mcp.run(transport="stdio")

###### 1 #####

# python .\rag_mcp_server.py --selftest "how long do you have to be an apprentice in order to advance to a general pemit in falconry"
# INFO:httpx:HTTP Request: POST http://localhost:11434/api/embed "HTTP/1.1 200 OK"
# INFO:rag-mcp:semantic_search query='how long do you have to be an apprentice in order to advance to a general pemit in falconry' k=4
# 1. falconry_study utah.pdf p.3 chunk 0  distance=0.2106
#    After passing the written exam, you must meet the following requirements before obtaining your  apprentice falconry license:  1. You must have a curre...

# 2. falconry-packet MN.pdf p.17 chunk 0  distance=0.2164
#    16    The Apprentice:    1. The MFA recommends all Apprentices read:  • North American Falconry and Hunting Hawks by Frank Beebe and Harold  Webster i...

# 3. falconry-packet MN.pdf p.15 chunk 0  distance=0.2202
#    14    APPRENTICE / SPONSOR GUIDELINES  Federal and State Regulations for Sponsors and Apprentices:  1. A Sponsor must hold a valid Master Falconry per...

# 4. falconry-packet MN.pdf p.7 chunk 0  distance=0.2226
#    6    A. A 12 year old JA and their parent who is an Apprentice have a passage red-tailed hawk.   The hawk is listed under the adult’s permit.    B. In...


##### 2 #####

# (.venv) PS C:\Users\chris\OneDrive\Desktop\semester 3 aicc\AgenticAI_230_AAI\module_7_8_AAI\230_final> python .\rag_mcp_server.py --selftest "how old are trees"                                                                            
# INFO:httpx:HTTP Request: POST http://localhost:11434/api/embed "HTTP/1.1 200 OK"
# INFO:rag-mcp:semantic_search query='how old are trees' k=4
# 1. CFR-2010-title50-vol6-sec21-29.pdf p.21 chunk 1  distance=0.462
#    the number and species of raptors to be  held under the permit.  (2) Whether propagation is authorized  by the State in which the propagation  will oc...

# 2. E8-23226.pdf p.6 chunk 2  distance=0.4797
#    to use Harris Hawks.’’  • ‘‘Those who argue that few 12–year-  olds are mature enough to succeed at  falconry are correct; however, they miss  the poi...

# 3. falconry-packet MN.pdf p.7 chunk 0  distance=0.4916
#    6    A. A 12 year old JA and their parent who is an Apprentice have a passage red-tailed hawk.   The hawk is listed under the adult’s permit.    B. In...

# 4. E8-23226.pdf p.7 chunk 0  distance=0.4934
#    59454 Federal Register / Vol. 73, No. 196 / Wednesday, October 8, 2008 / Rules and Regulations  • ‘‘We do not support lowering the age  of apprentice ...