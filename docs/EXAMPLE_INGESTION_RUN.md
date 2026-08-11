# Example ingestion-run report

| Field | Verified value |
|---|---|
| Run ID | `79f796ab-c3dd-4922-9d8a-3337803c106f` |
| Started | 2026-08-05T17:09:34.527860Z |
| Completed | 2026-08-05T17:09:47.192589Z |
| Status | completed |
| Read / accepted / quarantined | 600 / 600 / 0 |
| Notices / awards | 300 / 300 |
| Materialized projects | 159 |
| Curated project feature rows | 272 |
| Indexed chunks | 759 |
| Raw payload checksum | `35c03e79e29fc00bfe654a9c54a3cf26d68fe834979219bba12d05897ef29203` |
| Notice schema hash | `267cc6aef6b7329340f8341a0aa9df2d2c3d9824048bf85de49d1ed4e40fc9d3` |

The 159 materialized project rows come from the project metadata included in the Contract Awards payload. Notice-only project IDs without a materialized project record remain in the feature table with incomplete-linkage status.

