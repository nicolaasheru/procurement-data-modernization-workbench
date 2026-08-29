from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Protocol

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIMENSIONS = 384
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "001_pgvector_retrieval.sql"


class RetrievalConfigurationError(RuntimeError):
    pass


class Embedder(Protocol):
    model_name: str
    dimensions: int
    def encode(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class RetrievalConfig:
    database_url: str
    model_name: str = DEFAULT_MODEL
    dimensions: int = DEFAULT_DIMENSIONS
    minimum_score: float = 0.25

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        url=os.getenv("DATABASE_URL","").strip()
        if not url:
            raise RetrievalConfigurationError("DATABASE_URL is required for retrieval")
        return cls(url,os.getenv("EMBEDDING_MODEL",DEFAULT_MODEL),int(os.getenv("EMBEDDING_DIMENSIONS",DEFAULT_DIMENSIONS)),float(os.getenv("RETRIEVAL_MINIMUM_SCORE","0.25")))


class SentenceTransformerEmbedder:
    def __init__(self,model_name: str=DEFAULT_MODEL,dimensions: int=DEFAULT_DIMENSIONS):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RetrievalConfigurationError("Install backend retrieval dependencies before loading the embedding model") from exc
        self.model_name=model_name; self._model=SentenceTransformer(model_name)
        self.dimensions=int(self._model.get_sentence_embedding_dimension())
        if self.dimensions!=dimensions:
            raise RetrievalConfigurationError(f"Embedding dimension mismatch: model emits {self.dimensions}, schema expects {dimensions}")

    def encode(self,texts: list[str]) -> list[list[float]]:
        vectors=self._model.encode(texts,normalize_embeddings=True,show_progress_bar=False)
        return [vector.tolist() for vector in vectors]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


class PgVectorRetrieval:
    def __init__(self,config: RetrievalConfig|None=None,embedder: Embedder|None=None,connection_factory: Callable|None=None):
        self.config=config or RetrievalConfig.from_env()
        self.embedder=embedder or SentenceTransformerEmbedder(self.config.model_name,self.config.dimensions)
        self.connection_factory=connection_factory or self._default_connection

    def _default_connection(self):
        try:
            import psycopg
            from pgvector.psycopg import register_vector
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RetrievalConfigurationError("psycopg and pgvector are required for retrieval") from exc
        connection=psycopg.connect(self.config.database_url,row_factory=dict_row)
        register_vector(connection)
        return connection

    def migrate(self) -> None:
        sql=MIGRATION.read_text(encoding="utf-8").replace("vector(384)",f"vector({self.config.dimensions})")
        with self.connection_factory() as connection:
            for statement in (part.strip() for part in sql.split(";")):
                if statement: connection.execute(statement)

    def index_documents(self,documents: Iterable[dict],batch_size: int=64) -> int:
        docs=list(documents); indexed=0
        with self.connection_factory() as connection:
            for offset in range(0,len(docs),batch_size):
                batch=docs[offset:offset+batch_size]
                embeddings=self.embedder.encode([item["text"] for item in batch])
                if any(len(vector)!=self.config.dimensions for vector in embeddings):
                    raise RetrievalConfigurationError("Embedding model returned an unexpected vector dimension")
                rows=[(item["chunk_id"],item["record_type"],str(item["record_id"]),item.get("project_id"),item["text"],item.get("official_url"),item.get("country"),json.dumps(item.get("metadata") or {}),self.embedder.model_name,vector) for item,vector in zip(batch,embeddings)]
                connection.executemany("""insert into retrieval_documents(chunk_id,record_type,record_id,project_id,content,official_url,country,metadata,embedding_model,embedding)
                    values(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                    on conflict(chunk_id) do update set record_type=excluded.record_type,record_id=excluded.record_id,project_id=excluded.project_id,content=excluded.content,official_url=excluded.official_url,country=excluded.country,metadata=excluded.metadata,embedding_model=excluded.embedding_model,embedding=excluded.embedding,updated_at=now()""",rows)
                indexed+=len(rows)
        return indexed

    def index_sqlite(self,sqlite_path: Path) -> int:
        source=sqlite3.connect(sqlite_path); source.row_factory=sqlite3.Row
        documents=[]
        for row in source.execute("select chunk_id,record_type,record_id,project_id,text,official_url,metadata from document_chunks"):
            metadata=json.loads(row["metadata"] or "{}")
            documents.append({**dict(row),"country":metadata.get("country"),"metadata":metadata})
        source.close(); return self.index_documents(documents)

    def search(self,query: str,country: str|None=None,project_id: str|None=None,limit: int=8) -> dict:
        started=time.perf_counter(); query_vector=self.embedder.encode([query])[0]
        if len(query_vector)!=self.config.dimensions:
            raise RetrievalConfigurationError("Query embedding dimension does not match the retrieval schema")
        run_id=str(uuid.uuid4())
        with self.connection_factory() as connection:
            rows=connection.execute("""with query_vector as (select %s::vector embedding)
                select d.chunk_id,d.record_type,d.record_id,d.project_id,d.content text,d.official_url,d.country,
                       1-(d.embedding <=> q.embedding) retrieval_score
                from retrieval_documents d cross join query_vector q
                where d.embedding_model=%s
                  and (%s is null or lower(d.country)=lower(%s))
                  and (%s is null or d.project_id=%s)
                order by d.embedding <=> q.embedding limit %s""",
                (query_vector,self.embedder.model_name,country,country,project_id,project_id,limit)).fetchall()
            results=[dict(row) for row in rows if float(row["retrieval_score"])>=self.config.minimum_score]
            for result in results: result["retrieval_score"]=round(float(result["retrieval_score"]),4)
            latency=(time.perf_counter()-started)*1000; abstained=not results
            connection.execute("insert into retrieval_query_runs(run_id,query,country_filter,project_filter,embedding_model,result_count,latency_ms,abstained) values(%s,%s,%s,%s,%s,%s,%s,%s)",(run_id,query,country,project_id,self.embedder.model_name,len(results),latency,abstained))
        return {"run_id":run_id,"query":query,"results":results,"abstained":abstained,"message":"Insufficient semantic evidence in the indexed scope." if abstained else "Retrieved source records only; similarity is a ranking signal, not factual confidence.","latency_ms":round(latency,2),"embedding_model":self.embedder.model_name}

    def health(self) -> dict:
        with self.connection_factory() as connection:
            row=connection.execute("select extversion from pg_extension where extname='vector'").fetchone()
            count=connection.execute("select count(*) count from retrieval_documents where embedding_model=%s",(self.embedder.model_name,)).fetchone()
        return {"status":"ok","backend":"postgresql+pgvector","pgvector_version":row["extversion"],"embedding_model":self.embedder.model_name,"dimensions":self.embedder.dimensions,"indexed_documents":count["count"]}
