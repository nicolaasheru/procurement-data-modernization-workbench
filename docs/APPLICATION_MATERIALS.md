# Application materials

## One-line CV bullet

Engineered a procurement data-modernization workbench integrating 600 verified public World Bank notice and award records with 159 linked project records through Python/SQL ETL; implemented schema validation, duplicate signals, quarantine, lineage, project features, and citation-grounded vector retrieval across 759 indexed chunks.

## Three-paragraph cover-letter draft

Procurement data infrastructure matters because development outcomes depend not only on financing, but on whether project teams and oversight stakeholders can trace needs, opportunities, awards, and supporting evidence consistently. Fragmented formats, incomplete identifiers, duplicate records, and weak lineage can make that trail harder to inspect. I am drawn to ITS Fiduciary Operations because it sits at the practical intersection of public purpose, reliable data systems, and responsible modernization.

To understand that work more concretely, I independently built a Procurement Data Modernization Workbench using official public World Bank sources. The prototype ingests a verified bounded sample of 300 procurement notices and 300 contract awards, materializes 159 project records, preserves raw payloads and checksums, normalizes project identifiers and dates, records quality-control outcomes, creates 272 project-level feature rows, and indexes 759 evidence chunks. Its retrieval instrument uses a versioned Sentence Transformer model with PostgreSQL/pgvector, metadata filters, official citations, and an explicit insufficient-evidence state; it does not infer fraud or present generated text as a Bank conclusion.

This project gave me a disciplined way to practice the migration, validation, feature-engineering, testing, and documentation responsibilities described for the AI Data Engineer internship. I would be honored to bring my foundation in Python, SQL, APIs, systems design, and applied machine learning to the Procurement team, while learning how the Bank engineers reliable platforms at institutional scale and collaborates across product, data, software, and compliance stakeholders.

## Portfolio case-study description

I built a procurement data-modernization workbench to test how heterogeneous public records can become consistent, auditable, and AI-retrievable evidence. Using official World Bank notices and awards, the system preserves immutable raw payloads, validates and quarantines records, links activity through project IDs, generates documented project features, and supports citation-grounded retrieval with transparent abstention. The verified prototype processes 600 procurement records, materializes 159 projects, and indexes 759 chunks while remaining explicit about source coverage, incomplete linkage, and the limits of retrieval scores.
