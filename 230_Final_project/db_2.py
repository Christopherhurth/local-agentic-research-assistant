"""
Low-level MariaDB access for the RAG chunk table.

Uses the pure-Python `pymysql` driver (no native MariaDB Connector/C
dependency to install) and MariaDB's native VECTOR type / functions
(available from MariaDB Community Server 11.7+):

  https://mariadb.com/docs/server/reference/sql-structure/vectors/vector-overview

Table schema this module assumes (as given):

    id        varchar(64)   -- primary key; see note below
    source    varchar(255)
    page      int(11)
    chunk     int(11)
    content   text
    embedding vector(768)

`id` is assumed to be the primary/unique key so re-ingesting the same
document is idempotent (ON DUPLICATE KEY UPDATE overwrites the row instead
of duplicating it). If `id` is not actually unique in your table, either
add `PRIMARY KEY (id)` / `UNIQUE KEY (id)`, or switch `upsert_chunk` below
to a plain INSERT.

For best query performance at scale, add a vector index whose DISTANCE
matches what you query with (an index built for one metric is silently
*not* used by a query for the other metric -> full table scan):

    ALTER TABLE rag_files ADD VECTOR INDEX (embedding) M=6 DISTANCE=cosine;

Vectors are sent to MariaDB as JSON-array text via VEC_FromText(), which
is simple and portable across drivers. If you later need maximum insert
throughput, MariaDB also accepts raw little-endian float32 bytes bound
directly to a VECTOR column, which the docs report as noticeably faster
for bulk loads -- not needed for typical document ingestion volumes.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterable, Iterator

import pymysql
import pymysql.cursors

DistanceMetric = str  # "cosine" | "euclidean"

_DISTANCE_FUNCS = {
    "cosine": "VEC_DISTANCE_COSINE",
    "euclidean": "VEC_DISTANCE_EUCLIDEAN",
}


def get_connection(cfg: dict) -> pymysql.connections.Connection:
    """Open a new connection. cfg keys: host, port, user, password, database."""
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        autocommit=True,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@contextmanager
def connection(cfg: dict) -> Iterator[pymysql.connections.Connection]:
    conn = get_connection(cfg)
    try:
        yield conn
    finally:
        conn.close()


def upsert_chunk(
    conn: pymysql.connections.Connection,
    table: str,
    chunk_id: str,
    source: str,
    page: int,
    chunk_idx: int,
    content: str,
    embedding: Iterable[float],
) -> None:
    """Insert one chunk, overwriting any existing row with the same id."""
    vec_literal = json.dumps(list(embedding))
    sql = (
        f"INSERT INTO {table} (id, source, page, chunk, content, embedding) "
        f"VALUES (%s, %s, %s, %s, %s, VEC_FromText(%s)) "
        f"ON DUPLICATE KEY UPDATE "
        f"source = VALUES(source), page = VALUES(page), chunk = VALUES(chunk), "
        f"content = VALUES(content), embedding = VALUES(embedding)"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (chunk_id, source, page, chunk_idx, content, vec_literal))


def search_similar(
    conn: pymysql.connections.Connection,
    table: str,
    query_embedding: Iterable[float],
    k: int = 5,
    distance: DistanceMetric = "cosine",
) -> list[dict]:
    """Return the k rows whose embedding is nearest to query_embedding."""
    func = _DISTANCE_FUNCS.get(distance)
    if func is None:
        raise ValueError(f"Unknown distance metric {distance!r}; use 'cosine' or 'euclidean'.")

    vec_literal = json.dumps(list(query_embedding))
    sql = (
        f"SELECT id, source, page, chunk, content, "
        f"{func}(embedding, VEC_FromText(%s)) AS distance "
        f"FROM {table} "
        f"ORDER BY distance ASC "
        f"LIMIT %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (vec_literal, int(k)))
        return list(cur.fetchall())


def delete_source(conn: pymysql.connections.Connection, table: str, source: str) -> int:
    """Delete all chunks for a given source document (useful before re-ingesting it)."""
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE source = %s", (source,))
        return cur.rowcount


def source_exists(conn: pymysql.connections.Connection, table: str, source: str) -> bool:
    """True if at least one chunk for this source document is already stored."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {table} WHERE source = %s LIMIT 1", (source,))
        return cur.fetchone() is not None
