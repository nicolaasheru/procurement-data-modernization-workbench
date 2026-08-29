# Procurement Data Modernization Workbench

An independent, testable prototype that migrates public World Bank procurement notices, contract awards, and project metadata into auditable raw, standardized, curated, feature, and retrieval layers.

> **Independent prototype using public World Bank data. Not affiliated with or endorsed by the World Bank Group.** Source records and official pages remain authoritative.

## Executive summary

The workbench demonstrates the core data-engineering responsibilities described for an AI Data Engineer in fiduciary procurement operations: heterogeneous API ingestion, pagination-ready and idempotent processing, source preservation, schema checks, normalization, quarantine, explicit quality controls, analyst decisions with append-only audit events, project-level integration, feature engineering, model-backed semantic retrieval, citation construction, abstention, APIs, tests, and technical documentation.

The verified prototype run uses a bounded sample of **300 procurement notices and 300 contract awards**, then retrieves project metadata for observed project IDs. The source API reported **412,871 procurement notices on 5 August 2026**. The code supports bounded runs up to the official API's documented 1,000-record page size; a production scheduler would iterate pages and checkpoints rather than fit all source records into a free-tier demo.

## Why procurement data infrastructure matters

Procurement records help stakeholders understand how project needs move from notices to awards and supporting evidence. Fragmented formats, missing fields, duplicates, and incomplete linkages make that trail harder to inspect. This prototype preserves uncertainty and lineage while producing datasets that can support analytics and evidence retrieval without treating quality signals as misconduct.

## Official sources and access validation

| Source | Tested access | Key fields used | Important limitation |
|---|---|---|---|
| [Procurement Notices](https://financesone.worldbank.org/procurement-notice/DS00979) | JSON API, `top`/`skip`, max 1,000/page | `id`, `project_id`, title, country, category, method, publication/deadline, sector, URL | Public source reports daily updates; bounded prototype is not the full dataset |
| [Contract Awards](https://datacatalog.worldbank.org/search/dataset/0037797/world-bank-contract-awards) | JSON API, `rows`/`os` | contract ID, project ID, description, supplier, amount, signed date | Officially does not represent every contract; supplier country is registration location |
| [Projects & Operations](https://datacatalog.worldbank.org/search/dataset/0037800/world-bank-projects-operations) | JSON API with project lookup | project ID, name, country, region, sector, total amount | Metadata availability varies by project |
| [Documents & Reports](https://documents.worldbank.org/en/publication/documents-reports/api) | API documentation and sample calls validated | project ID, title, abstract, type, document date, official URLs | Adapter is documented as the next bounded-ingest module; not counted in this verified run |

`project_id` / `projectid` is the valid common key across the operational datasets. The pipeline normalizes it to `P` plus six digits and quarantines invalid values.

## Architecture

```mermaid
flowchart TD
  A[Official public APIs] --> B[Raw snapshots]
  B --> C[Standardize and validate]
  C -->|valid| D[Curated SQL tables]
  C -->|ambiguous| E[Quarantine and review]
  D --> F[Project features]
  D --> G[Sentence Transformer embeddings]
  G --> H[PostgreSQL and pgvector retrieval]
  H --> I[Citations or abstention]
```

- **Raw:** complete retrieved payload, source URLs, retrieval time, run ID, SHA-256 checksum, and detected schema hash.
- **Standardized:** normalized project IDs and ISO dates, preserved raw JSON, validation results, and rejected/quarantined payloads.
- **Curated:** projects, notices, awards, project features, document chunks, embeddings, and retrieval runs.
- **Serving:** typed FastAPI routes and a responsive institutional workbench.

## Data model

```mermaid
erDiagram
  INGESTION_RUNS ||--o{ VALIDATION_RESULTS : records
  PROJECTS ||--o{ PROCUREMENT_NOTICES : links
  PROJECTS ||--o{ CONTRACT_AWARDS : links
  PROJECTS ||--|| PROCUREMENT_FEATURES : summarizes
  PROJECTS ||--o{ DOCUMENT_CHUNKS : indexes
  RETRIEVAL_RUNS ||--o{ DOCUMENT_CHUNKS : ranks
```

See [data dictionary](docs/DATA_DICTIONARY.md) and [control catalog](docs/CONTROL_CATALOG.md).

## Pipeline behavior

- HTTP timeouts and exponential retry for transient failures
- bounded `top`/`skip` or `rows`/`os` ingestion
- immutable raw snapshots and payload checksum
- source-schema fingerprint
- primary-key upserts for idempotence
- normalization with original raw JSON retained
- quality issue and quarantine ledgers
- review cases, accountable dispositions, retest state, and append-only audit events
- curated rebuild and feature generation
- versioned Sentence Transformers embedding generation
- PostgreSQL/pgvector storage with HNSW cosine indexing
- retrieval-run logging and abstention

### Feature dataset

One row per project: notice count, award count, supplier count, total award amount, missing-field ratio, project-linkage status, and average quality score. It is suitable for analytics or downstream ML experimentation; this project does not add an arbitrary predictive model.

## Data-quality framework

Every issue stores the control ID, severity, result name, record type and ID, source field, original value, normalized value, run ID, and recommended handling. Controls include missing/invalid project IDs, missing titles, invalid dates, deadline ordering, missing category, incomplete project linkage, and potential duplicate content.

Quality controls are **review signals, not fraud labels**. Ambiguous values are not silently repaired.

## Retrieval methodology and safeguards

Text from notices, awards, and projects is embedded with the pinned `sentence-transformers/all-MiniLM-L6-v2` model into 384-dimensional normalized vectors. PostgreSQL stores the evidence and pgvector performs cosine-distance ranking through an HNSW index. Country and project filters execute in SQL, low-similarity queries abstain, and each query records its model version, filters, result count, latency, and abstention state. The browser calls the FastAPI service directly; no vectors or substitute retrieval algorithm are shipped to the client.

Safeguards:

- every result contains record type, ID, project ID, excerpt, score, and official URL;
- retrieval score is explicitly a ranking signal, not factual confidence;
- results below the minimum evidence threshold abstain;
- no supplier, country, or project misconduct inference;
- no generated record or citation;
- optional future synthesis must remain visibly separate from retrieved facts.

## API

Run the backend and open `/docs` for OpenAPI.

Review workflow routes:

- `GET /reviews` lists exception cases, with optional status filtering.
- `POST /reviews` opens one case from a stored validation result and optionally assigns it.
- `GET /reviews/{case_id}` returns the issue evidence, current decision state, and full event history.
- `PATCH /reviews/{case_id}` records assignment, lifecycle changes, resolution rationale, and retest state.

A final disposition requires a named actor and rationale. Each transition appends a separate event instead of rewriting history. The browser case study provides the same lifecycle as a recruiter-testable local demonstration; enterprise authentication and authorization remain outside prototype scope.

- `GET /health`
- `GET /ingestion/runs`
- `POST /ingestion/sample`
- `GET /quality/summary`
- `GET /quality/issues`
- `GET /projects`
- `GET /projects/{project_id}`
- `GET /procurement/notices`
- `POST /procurement/search`

## Local setup (macOS and Linux)

Requires Python 3.11+, Node 22.13+, and Docker.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
set -a && source .env && set +a
docker compose up -d postgres
python -m backend.app.cli ingest-sample --notices 300 --awards 300
python -m backend.app.cli retrieval-migrate
python -m backend.app.cli retrieval-index
uvicorn backend.app.main:app --reload
```

In another terminal:

```bash
npm ci
npm run dev
```

Tests and production build:

```bash
pytest -q
npm test
```

Run the opt-in real PostgreSQL/model round-trip after the model has downloaded:

```bash
RUN_PGVECTOR_INTEGRATION=1 pytest -q backend/tests/test_retrieval_integration.py
```

Verify the service:

```bash
curl http://localhost:8000/retrieval/health
curl -X POST http://localhost:8000/procurement/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"digital government infrastructure","country":"Madagascar","limit":5}'
```

`npm run build` refreshes only aggregate country counts for the map. Retrieval documents and embeddings remain server-side in PostgreSQL.

No Linux-only locking utility is used.

## Environment variables

Retrieval requires:

```text
DATABASE_URL=postgresql://procurement:procurement_local@localhost:5432/procurement
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
RETRIEVAL_MINIMUM_SCORE=0.25
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

No secrets belong in source control.

## Demo

The interface is organized around one operational outcome: determine whether a migration run is ready for controlled release.

1. Open **Runs** to inspect reconciliation, quality signals, lineage, and the next required action for the 5 August rehearsal.
2. Open **Review queue**, assign a selected DQ-008 case, compare its source evidence, and record a disposition with a mandatory rationale.
3. Open **Release readiness** to see which acceptance criteria passed and which analyst decisions still prevent completion.
4. Use **Search evidence** contextually when a review requires supporting records. The explorer returns cited records or no evidence; it does not fabricate an answer.

The three selected review cases are a transparent prototype adjudication scope drawn from the verified DQ-008 results. The full run contains 47 duplicate-content signals and 113 non-blocking project-linkage warnings.

## Testing and evaluation

Unit tests cover project/date normalization, idempotent upserts, curated feature generation, vector retrieval, metadata filtering, abstention, reviewer assignment, resolution, and audit-event ordering. The frontend test performs a production build and checks rendered product/disclaimer content. Exact executed results are recorded in [TEST_REPORT.md](docs/TEST_REPORT.md); no pass claim should be made without that report.

The transparent retrieval evaluation is intentionally small and prototype-scoped. Queries, manual relevance labels, metrics, and limitations are in [RETRIEVAL_EVALUATION.md](docs/RETRIEVAL_EVALUATION.md).

## Responsible AI and known limitations

- Bounded sample only; not full-source coverage.
- Contract Awards is not a complete list of all awards.
- Documents API is validated but is not part of the counted run.
- The current English-oriented embedding model is not a substitute for a multilingual retrieval evaluation.
- Operational workflow state remains in SQLite; retrieval is isolated in PostgreSQL/pgvector. Production still needs managed migrations, orchestration, object storage, and monitoring.
- Manual evaluation labels are small and authored for this prototype.
- Official records may themselves contain missing or inconsistent metadata.

## Deployment

No external deployment or GitHub push has been performed. The included cloud configuration targets Railway for the FastAPI/model container and any PostgreSQL provider that permits `CREATE EXTENSION vector`. The frontend reaches retrieval over HTTPS, while PostgreSQL remains private to the API service.

### Railway backend

`Dockerfile` builds a non-root Python 3.12 container and caches the pinned Sentence Transformer model in the image. `.railway/railway.ts` uses Railway's current project-level Infrastructure-as-Code format to define the API, shared database and CORS variable linkage, replica count, and `/health/ready` gate. At startup, `scripts/start-backend.sh`:

1. requires `DATABASE_URL`;
2. applies the idempotent pgvector schema;
3. embeds and upserts the curated evidence unless `SKIP_RETRIEVAL_INDEX=1`; and
4. starts FastAPI with proxy-aware production settings.

Install Railway's CLI, authenticate, and apply the checked-in project definition:

```bash
npm install
railway login
railway config plan
railway config apply
```

Before planning, create two Railway shared variables: `DATABASE_URL`, pointing to a private PostgreSQL database built with pgvector (for example Railway's pgvector template, Neon, or Supabase), and `CORS_ORIGINS`, containing the deployed frontend origin. Railway's default PostgreSQL image does not bundle pgvector, so the configuration deliberately does not pretend that an ordinary Railway PostgreSQL helper is sufficient. The database role must permit `CREATE EXTENSION vector`. Deployment fails closed if the extension cannot be installed or the evidence index remains empty.

The backend environment is:

```text
DATABASE_URL=<private PostgreSQL connection string>
CORS_ORIGINS=https://<your-frontend-domain>
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
RETRIEVAL_MINIMUM_SCORE=0.25
WEB_CONCURRENCY=1
SKIP_RETRIEVAL_INDEX=0
```

After the first successful deployment, set the frontend build variable `NEXT_PUBLIC_API_BASE_URL` to the Railway public HTTPS URL. Keep `SKIP_RETRIEVAL_INDEX=0` when source records changed; it can be set to `1` for later code-only restarts after verifying that the correct model index already exists.

### Continuous integration

`.github/workflows/ci.yml` runs on pushes and pull requests with four gates:

- backend unit and workflow tests;
- frontend production build and rendered-interface test;
- a real Sentence Transformer round trip against a pgvector PostgreSQL service; and
- construction of the deployable backend container.

The model cache is reused between CI runs. A failed pgvector round trip prevents the container gate from passing.

## Production roadmap

1. Complete historical page iteration with checkpoint resume and scheduled incrementals.
2. Add Documents & Reports ingestion and text extraction.
3. Add managed migration orchestration and embedding backfill checkpoints.
4. Add an embedding-model registry and multilingual retrieval.
5. Expand adjudicated retrieval labels and automated drift monitoring.
6. Add enterprise identity, role-based approvals, and durable browser-to-API integration for reviewer actions.

## License and attribution

Code: MIT License. World Bank source data is used under the licensing stated on each official catalog page, including CC BY 4.0 where specified. See [ATTRIBUTION.md](docs/ATTRIBUTION.md). World Bank names and source links identify the public data origin only.
