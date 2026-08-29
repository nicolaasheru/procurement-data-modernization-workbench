import json
import pytest

from backend.app.pipeline import connect
from backend.app.retrieval import PgVectorRetrieval, RetrievalConfig, RetrievalConfigurationError, pgvector_readiness


class FakeEmbedder:
    model_name="test/model-v1"
    dimensions=3
    def __init__(self,vector=None): self.vector=vector or [1.0,0.0,0.0]; self.calls=[]
    def encode(self,texts): self.calls.append(texts); return [self.vector[:] for _ in texts]


class Result:
    def __init__(self,rows): self.rows=rows
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0]


class FakeConnection:
    def __init__(self,search_rows=None): self.search_rows=search_rows or []; self.executed=[]; self.batches=[]
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,sql,params=None):
        self.executed.append((sql,params))
        if "from retrieval_documents d" in sql: return Result(self.search_rows)
        if "pg_extension" in sql: return Result([{"extversion":"0.8.1"}])
        if "count(*) count" in sql: return Result([{"count":7}])
        return Result([])
    def executemany(self,sql,rows): self.batches.append((sql,rows))


def service(connection,embedder=None,minimum_score=.25):
    config=RetrievalConfig("postgresql://test",model_name="test/model-v1",dimensions=3,minimum_score=minimum_score)
    return PgVectorRetrieval(config,embedder or FakeEmbedder(),lambda:connection)


def test_pgvector_search_returns_cited_semantic_results_and_logs_query():
    connection=FakeConnection([{"chunk_id":"c1","record_type":"notice","record_id":"1","project_id":"P123456","text":"Digital infrastructure","official_url":"https://example.org","country":"Indonesia","retrieval_score":0.81}])
    result=service(connection).search("technology modernization","Indonesia","P123456",6)
    assert result["abstained"] is False
    assert result["results"][0]["retrieval_score"]==.81
    assert result["embedding_model"]=="test/model-v1"
    search_params=next(params for sql,params in connection.executed if "from retrieval_documents d" in sql)
    assert search_params[2:6]==("Indonesia","Indonesia","P123456","P123456")
    assert any("retrieval_query_runs" in sql for sql,_ in connection.executed)


def test_pgvector_search_abstains_below_threshold():
    connection=FakeConnection([{"chunk_id":"c1","record_type":"notice","record_id":"1","project_id":"P123456","text":"Weak match","official_url":"https://example.org","country":"Indonesia","retrieval_score":0.19}])
    result=service(connection,minimum_score=.25).search("unrelated request")
    assert result["abstained"] is True and result["results"]==[]


def test_pgvector_index_reads_staging_documents_and_upserts_idempotently(tmp_path):
    sqlite_path=tmp_path/"source.db"; db=connect(sqlite_path)
    db.execute("insert into document_chunks values(?,?,?,?,?,?,?,?)",("c1","notice","1","P123456","Digital infrastructure","https://example.org",json.dumps({"country":"Indonesia"}),"[]")); db.commit()
    connection=FakeConnection(); embedder=FakeEmbedder()
    indexed=service(connection,embedder).index_sqlite(sqlite_path)
    assert indexed==1 and embedder.calls==[["Digital infrastructure"]]
    sql,rows=connection.batches[0]
    assert "on conflict(chunk_id) do update" in sql
    assert rows[0][0]=="c1" and rows[0][6]=="Indonesia" and rows[0][8]=="test/model-v1"


def test_pgvector_migration_installs_extension_schema_and_dimension():
    connection=FakeConnection(); service(connection).migrate()
    sql="\n".join(statement for statement,_ in connection.executed)
    assert "create extension if not exists vector" in sql
    assert "embedding vector(3) not null" in sql
    assert "using hnsw" in sql


def test_pgvector_health_reports_extension_model_and_index_count():
    result=service(FakeConnection()).health()
    assert result=={"status":"ok","backend":"postgresql+pgvector","pgvector_version":"0.8.1","embedding_model":"test/model-v1","dimensions":3,"indexed_documents":7}


def test_lightweight_cloud_readiness_checks_extension_and_index_without_loading_model():
    config=RetrievalConfig("postgresql://test",model_name="test/model-v1",dimensions=3)
    result=pgvector_readiness(config,lambda:FakeConnection())
    assert result["status"]=="ready" and result["indexed_documents"]==7


def test_cloud_readiness_rejects_empty_index():
    class EmptyConnection(FakeConnection):
        def execute(self,sql,params=None):
            if "count(*) count" in sql: return Result([{"count":0}])
            return super().execute(sql,params)
    config=RetrievalConfig("postgresql://test",model_name="test/model-v1",dimensions=3)
    with pytest.raises(RetrievalConfigurationError,match="empty"):
        pgvector_readiness(config,lambda:EmptyConnection())


def test_retrieval_requires_database_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL",raising=False)
    with pytest.raises(RetrievalConfigurationError,match="DATABASE_URL"):
        RetrievalConfig.from_env()


def test_embedding_dimension_mismatch_fails_before_database_query():
    connection=FakeConnection(); embedder=FakeEmbedder([1.0,0.0])
    with pytest.raises(RetrievalConfigurationError,match="dimension"):
        service(connection,embedder).search("query")
    assert connection.executed==[]
