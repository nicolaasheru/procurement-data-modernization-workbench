"""Opt-in integration test against the Docker pgvector service and real model."""
import os
import uuid
import pytest

from backend.app.retrieval import PgVectorRetrieval, RetrievalConfig, SentenceTransformerEmbedder

pytestmark=pytest.mark.skipif(os.getenv("RUN_PGVECTOR_INTEGRATION")!="1",reason="set RUN_PGVECTOR_INTEGRATION=1 with PostgreSQL running")

def test_real_model_pgvector_round_trip():
    config=RetrievalConfig.from_env(); embedder=SentenceTransformerEmbedder(config.model_name,config.dimensions)
    service=PgVectorRetrieval(config,embedder); service.migrate()
    marker=uuid.uuid4().hex
    service.index_documents([
        {"chunk_id":f"integration-digital-{marker}","record_type":"notice","record_id":marker,"project_id":"P999991","text":"Procurement of cloud infrastructure and digital public services","official_url":"https://example.org/digital","country":"Indonesia"},
        {"chunk_id":f"integration-water-{marker}","record_type":"notice","record_id":marker+"b","project_id":"P999992","text":"Construction of rural water supply and sanitation facilities","official_url":"https://example.org/water","country":"Kenya"},
    ])
    result=service.search("technology systems for online government services",country="Indonesia",project_id="P999991",limit=2)
    assert result["abstained"] is False
    assert result["results"][0]["project_id"]=="P999991"
