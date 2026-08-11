"""Export the verified SQLite evidence index for the browser demo.

The frontend consumes the same stored text, metadata, citations, and vectors as
the FastAPI endpoint. This keeps the hosted case study functional without
inventing a second, hard-coded search implementation.
"""

from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "workbench.db"
OUTPUT = ROOT / "public" / "data" / "retrieval-corpus.json"


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", text.lower()))


def bucket(token: str, dimensions: int = 256) -> int:
    return int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % dimensions


def main() -> None:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        select chunk_id, record_type, record_id, project_id, text,
               official_url, metadata, embedding
        from document_chunks
        order by record_type, record_id
        """
    ).fetchall()

    vocabulary = sorted({token for row in rows for token in tokens(row["text"])})
    payload = {
        "source": "verified SQLite document_chunks export",
        "dimensions": 256,
        "count": len(rows),
        "vocabulary": {token: bucket(token) for token in vocabulary},
        "records": [
            {
                "chunk_id": row["chunk_id"],
                "record_type": row["record_type"],
                "record_id": row["record_id"],
                "project_id": row["project_id"],
                "text": row["text"],
                "official_url": row["official_url"],
                "metadata": json.loads(row["metadata"]),
                "embedding": json.loads(row["embedding"]),
            }
            for row in rows
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"exported {len(rows)} indexed records to {OUTPUT}")


if __name__ == "__main__":
    main()
