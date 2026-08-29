create extension if not exists vector;

create table if not exists retrieval_documents (
  chunk_id text primary key,
  record_type text not null,
  record_id text not null,
  project_id text,
  content text not null,
  official_url text,
  country text,
  metadata jsonb not null default '{}'::jsonb,
  embedding_model text not null,
  embedding vector(384) not null,
  updated_at timestamptz not null default now()
);

create index if not exists retrieval_documents_embedding_hnsw
  on retrieval_documents using hnsw (embedding vector_cosine_ops);
create index if not exists retrieval_documents_country_idx on retrieval_documents(lower(country));
create index if not exists retrieval_documents_project_idx on retrieval_documents(project_id);

create table if not exists retrieval_query_runs (
  run_id uuid primary key,
  query text not null,
  country_filter text,
  project_filter text,
  embedding_model text not null,
  result_count integer not null,
  latency_ms double precision not null,
  abstained boolean not null,
  created_at timestamptz not null default now()
);
