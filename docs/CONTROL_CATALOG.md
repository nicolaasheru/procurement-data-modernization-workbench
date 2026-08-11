# Data-quality control catalog

| ID | Control | Severity | Logic | Handling |
|---|---|---|---|---|
| DQ-001 | Missing project identifier | Error | source value empty | Quarantine |
| DQ-002 | Invalid project identifier | Error | not `P` + six digits | Preserve and quarantine |
| DQ-003 | Missing notice title | Error | title empty | Quarantine; do not infer |
| DQ-004 | Invalid date format | Error | supported parsers fail | Preserve and quarantine |
| DQ-005 | Deadline before publication | Warning | normalized deadline < publication | Requires review |
| DQ-006 | Missing category | Info | category empty | Retain as incomplete |
| DQ-007 | Incomplete project linkage | Warning | operational record has no curated project row | Retain and flag |
| DQ-008 | Potential duplicate content | Warning | same project/title/date content hash | Retain canonical record; review |

