# System card

## Intended use
Public procurement data migration, quality review, project linkage, feature preparation, and evidence retrieval.

## Out of scope
Fraud detection, supplier risk scoring, sanctions decisions, automated procurement decisions, or authoritative World Bank conclusions.

## Data and model
Official public APIs; versioned 384-dimensional Sentence Transformer embeddings; PostgreSQL/pgvector HNSW cosine ranking; metadata filters; explicit abstention.

## Human oversight
Reviewers inspect original values, normalized values, official citations, and incomplete-evidence states. Quality flags require interpretation.

## Risks
Incomplete source coverage, missing metadata, lexical retrieval limitations, duplicate records, stale samples, and overinterpretation of ranking scores.

## Mitigations
Scope disclosure, immutable raw snapshots, official URLs, quarantine, explicit limitations, retrieval trace, and no misconduct labels.
