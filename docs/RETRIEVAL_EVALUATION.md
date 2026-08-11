# Retrieval evaluation

Evaluation is prototype-scoped and manually labeled. The planned set contains five representative queries, each with one or more known relevant records from the bounded corpus plus one deliberately unsupported query.

| Query type | Expected behavior |
|---|---|
| digital/information systems | rank notices containing those concepts |
| project-ID lookup | enforce exact metadata filter |
| country-filtered procurement | return only matching country metadata |
| award-related query | retrieve award chunks with official citations |
| unsupported topic | abstain |

Executed on 6 August 2026:

| Metric | Result |
|---|---:|
| Precision@5 | 0.240 |
| Mean Reciprocal Rank | 1.000 |
| Citation coverage | 1.000 |
| Metadata-filter accuracy | 1.000 |
| Mean retrieval latency | 9.13 ms |
| Zero-result rate | 0.167 |
| Unsupported-query abstention | Passed |
| Duplicate-result rate | 0.000 |

The low Precision@5 partly reflects only one or two labeled relevant records per query while always requesting five results. The small manual label set does not support an enterprise-grade accuracy claim.

