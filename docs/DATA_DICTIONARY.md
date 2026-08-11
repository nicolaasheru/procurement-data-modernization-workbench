# Data dictionary

| Table | Purpose | Primary fields |
|---|---|---|
| `ingestion_runs` | Auditable pipeline ledger | run ID, source, timestamps, status, counts, checksum, schema hash |
| `projects` | Normalized project metadata | project ID, title, country, region, sector, amount, official URL |
| `procurement_notices` | Standardized tender notices | notice ID, project ID, title, category, dates, source URL, raw JSON, quality score |
| `contract_awards` | Standardized awards | award ID, project ID, supplier, amount, signed date, raw JSON |
| `validation_results` | Control-level outcomes | control ID, severity, record, field, original/normalized values, handling |
| `rejected_records` | Quarantine ledger | run ID, record type/ID, reason, full payload |
| `procurement_features` | Analytics/ML-ready project features | counts, supplier count, award sum, missing ratio, linkage, quality score |
| `document_chunks` | Retrieval corpus | chunk ID, record metadata, text, citation URL, embedding |
| `retrieval_runs` | Retrieval observability | run ID, query, result count, latency, abstention |

