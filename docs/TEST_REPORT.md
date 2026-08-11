# Test report | 11 August 2026

| Suite | Command | Result |
|---|---|---|
| Python unit/integration | `.venv/bin/python -m pytest -q` | 3 passed in 0.09s |
| Frontend production + artifact | `npm test` | Build passed; 1 rendered-worker test passed |
| Browser interaction | supported query + unsupported query | 8 ranked records; unsupported query abstained; zero horizontal overflow |
| Retrieval evaluation | `python3 scripts/evaluate.py` | Completed; six-query report recorded |

Covered behaviors: project/date normalization, idempotent upserts, feature generation, deterministic embeddings, 759-record browser and backend retrieval, country metadata filter, unsupported-query abstention, production frontend compilation, Sites artifact shape, rendered HTML response, and responsive overflow inspection.

The current suite is intentionally prototype-sized. It does not yet simulate every network retry, a full 412,871-row run, or a hosted PostgreSQL migration.
