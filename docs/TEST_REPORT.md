# Test report | 11 August 2026

| Suite | Command | Result |
|---|---|---|
| Python unit/integration | `python3 -m pytest -q` | 4 passed in 0.13s |
| Frontend production + artifact | `npm test` | Build passed; 1 rendered-worker test passed |
| Browser interaction | supported query + unsupported query | 8 ranked records; unsupported query abstained; zero horizontal overflow |
| Retrieval evaluation | `python3 scripts/evaluate.py` | Completed; six-query report recorded |

Covered behaviors: project/date normalization, idempotent upserts, feature generation, all eight quality controls, quarantine and rejection accounting, source and mapping failures, pgvector migration shape, model-versioned indexing, semantic score abstention, country/project SQL filters, embedding-dimension enforcement, retrieval health and cloud readiness, reviewer assignment, lifecycle transition, mandatory rationale, final disposition, audit-event ordering, production frontend compilation, deployable container construction, Sites artifact shape, and rendered HTML response. CI additionally runs the opt-in real Sentence Transformer and pgvector round trip.

The current suite is intentionally prototype-sized. It does not yet simulate every network retry, a full 412,871-row run, or a hosted PostgreSQL migration.
