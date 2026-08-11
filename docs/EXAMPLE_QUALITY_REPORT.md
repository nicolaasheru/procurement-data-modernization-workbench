# Example quality report

The final bounded run accepted all 600 source records. Across the current database, the curation pass recorded:

| Control | Severity | Affected |
|---|---|---:|
| DQ-007 Incomplete project linkage | Warning | 113 |
| DQ-008 Potential duplicate content | Warning | 47 |

No source record was accused of fraud or misconduct. DQ-007 reflects notice-only project IDs outside the project rows materialized from the award sample. DQ-008 uses a content hash and is a review signal, not proof that a record should be deleted.

