"use client";

import { useEffect, useMemo, useState } from "react";

type View = "Runs" | "Review queue" | "Release readiness";
type Status = "Open" | "Assigned" | "In review" | "Resolved" | "Rejected";
type DecisionErrors = Partial<
  Record<"reviewer" | "status" | "resolution" | "rationale", string>
>;
type Event = { action: string; actor: string; at: string; note: string };
type ReviewCase = {
  id: string;
  recordId: string;
  projectId: string;
  country: string;
  control: string;
  title: string;
  sourceValue: string;
  comparison: string;
  status: Status;
  assignee: string;
  priority: "High" | "Medium";
  resolution?: string;
  rationale?: string;
  events: Event[];
};
type CorpusRecord = {
  chunk_id: string;
  record_type: string;
  record_id: string;
  project_id: string;
  text: string;
  official_url: string;
  metadata: { country?: string | null };
  embedding: number[];
};
type SearchResult = CorpusRecord & { score: number };

const casesSeed: ReviewCase[] = [
  {
    id: "REV-00001",
    recordId: "459873",
    projectId: "P506439",
    country: "Eastern and Southern Africa",
    control: "DQ-008",
    title: "Potential duplicate content",
    sourceValue: "Software",
    comparison:
      "Notice 459874 contains the same project, description and date signature.",
    status: "Open",
    assignee: "",
    priority: "High",
    events: [
      {
        action: "Signal created",
        actor: "Validation pipeline",
        at: "5 Aug 2026 · 14:32 UTC",
        note: "DQ-008 matched a repeated content signature. Both source records were retained.",
      },
    ],
  },
  {
    id: "REV-00002",
    recordId: "459874",
    projectId: "P506439",
    country: "Eastern and Southern Africa",
    control: "DQ-008",
    title: "Potential duplicate content",
    sourceValue: "Software",
    comparison:
      "Notice 459873 contains the same project, description and date signature.",
    status: "Open",
    assignee: "",
    priority: "High",
    events: [
      {
        action: "Signal created",
        actor: "Validation pipeline",
        at: "5 Aug 2026 · 14:32 UTC",
        note: "DQ-008 matched a repeated content signature. Both source records were retained.",
      },
    ],
  },
  {
    id: "REV-00003",
    recordId: "459884",
    projectId: "P166309",
    country: "Madagascar",
    control: "DQ-008",
    title: "Potential duplicate content",
    sourceValue:
      "Acquisition de fournitures de bureau et de consommables informatiques",
    comparison:
      "A second published notice shares the same normalized procurement description.",
    status: "Open",
    assignee: "",
    priority: "Medium",
    events: [
      {
        action: "Signal created",
        actor: "Validation pipeline",
        at: "5 Aug 2026 · 14:32 UTC",
        note: "The record remains in the warning layer until source evidence is compared.",
      },
    ],
  },
];

const tokenize = (text: string) =>
  text.toLowerCase().match(/[a-z0-9]{2,}/g) || [];
function vector(text: string, vocabulary: Record<string, number>) {
  const counts = new Map<string, number>();
  tokenize(text).forEach((t) => counts.set(t, (counts.get(t) || 0) + 1));
  const out = Array(256).fill(0);
  for (const [token, count] of counts) {
    const bucket = vocabulary[token];
    if (bucket !== undefined) out[bucket] += 1 + Math.log(count);
  }
  const norm = Math.sqrt(out.reduce((s, v) => s + v * v, 0)) || 1;
  return out.map((v) => v / norm);
}

export default function Workbench() {
  const [view, setView] = useState<View>("Runs");
  const [cases, setCases] = useState<ReviewCase[]>(casesSeed);
  const [selectedId, setSelectedId] = useState(casesSeed[0].id);
  const [reviewer, setReviewer] = useState("");
  const [resolution, setResolution] = useState("");
  const [rationale, setRationale] = useState("");
  const [decisionErrors, setDecisionErrors] = useState<DecisionErrors>({});
  const [notice, setNotice] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchStatus, setSearchStatus] = useState<
    "idle" | "loading" | "empty" | "done" | "error"
  >("idle");
  useEffect(() => {
    const saved = localStorage.getItem("pdmw-review-v2");
    if (saved)
      try {
        setCases(JSON.parse(saved));
      } catch {}
  }, []);
  useEffect(() => {
    localStorage.setItem("pdmw-review-v2", JSON.stringify(cases));
  }, [cases]);
  useEffect(() => {
    setReviewer("");
    setResolution("");
    setRationale("");
    setDecisionErrors({});
    setNotice("");
  }, [selectedId]);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileToolsOpen(false);
        setSearchOpen(false);
        setAboutOpen(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);
  const selected = cases.find((c) => c.id === selectedId) || cases[0];
  const completed = cases.filter(
    (c) => c.status === "Resolved" || c.status === "Rejected",
  ).length;
  const releaseReady = completed === cases.length;
  const canSubmitDecision =
    selected.status === "In review" &&
    Boolean(selected.assignee) &&
    Boolean(resolution) &&
    rationale.trim().length >= 20;
  const stamp = () =>
    new Date().toLocaleString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
      timeZoneName: "short",
    });
  const update = (change: Partial<ReviewCase>, event?: Event) =>
    setCases((all) =>
      all.map((c) =>
        c.id === selectedId
          ? { ...c, ...change, events: event ? [...c.events, event] : c.events }
          : c,
      ),
    );
  const assign = () => {
    const actor = reviewer.trim();
    if (actor.length < 2) {
      setDecisionErrors((errors) => ({
        ...errors,
        reviewer: "Enter the reviewer's full name.",
      }));
      setNotice("Enter a reviewer name first.");
      return;
    }
    update(
      { assignee: actor, status: "Assigned" },
      {
        action: "Case assigned",
        actor,
        at: stamp(),
        note: "Accountability transferred from the unassigned queue.",
      },
    );
    setDecisionErrors((errors) => ({ ...errors, reviewer: undefined }));
    setNotice("Assignment recorded.");
  };
  const start = () => {
    const actor = selected.assignee || reviewer.trim();
    if (!actor) {
      setDecisionErrors((errors) => ({
        ...errors,
        status: "Assign a reviewer before beginning review.",
      }));
      setNotice("Assign the case before starting review.");
      return;
    }
    update(
      { assignee: actor, status: "In review" },
      {
        action: "Review started",
        actor,
        at: stamp(),
        note: "The analyst opened the evidence package and began adjudication.",
      },
    );
    setDecisionErrors((errors) => ({ ...errors, status: undefined }));
    setNotice("Case is now in review.");
  };
  const decide = () => {
    const errors: DecisionErrors = {};
    if (!selected.assignee)
      errors.reviewer = "Assign an accountable reviewer first.";
    if (selected.status !== "In review")
      errors.status = "Begin review before recording a decision.";
    if (!resolution)
      errors.resolution = "Select one disposition based on the evidence.";
    if (rationale.trim().length < 20)
      errors.rationale =
        "Explain the evidence and reasoning in 20 characters or more.";
    setDecisionErrors(errors);
    if (Object.keys(errors).length) {
      setNotice("Complete the highlighted decision requirements.");
      return;
    }
    const actor = selected.assignee as string;
    const status: Status =
      resolution === "Reject from trusted layer" ? "Rejected" : "Resolved";
    update(
      { status, resolution, rationale: rationale.trim() },
      {
        action: "Decision recorded",
        actor,
        at: stamp(),
        note: `${resolution}. ${rationale.trim()}`,
      },
    );
    setResolution("");
    setRationale("");
    setDecisionErrors({});
    setNotice(
      `Decision recorded. ${completed + 1} of ${cases.length} selected reviews complete.`,
    );
  };
  async function search() {
    if (query.trim().length < 3) return;
    setSearchStatus("loading");
    try {
      const response = await fetch("/data/retrieval-corpus.json");
      const corpus = (await response.json()) as {
        vocabulary: Record<string, number>;
        records: CorpusRecord[];
      };
      const qv = vector(query, corpus.vocabulary);
      const terms = new Set(tokenize(query));
      const ranked = corpus.records
        .filter((r) => tokenize(r.text).some((t) => terms.has(t)))
        .map((r) => ({
          ...r,
          score: qv.reduce((s, v, i) => s + v * (r.embedding[i] || 0), 0),
        }))
        .filter((r) => r.score >= 0.12)
        .sort((a, b) => b.score - a.score)
        .slice(0, 6);
      setResults(ranked);
      setSearchStatus(ranked.length ? "done" : "empty");
    } catch {
      setSearchStatus("error");
    }
  }
  const queue = useMemo(
    () =>
      cases
        .slice()
        .sort(
          (a, b) =>
            Number(a.status === "Resolved" || a.status === "Rejected") -
            Number(b.status === "Resolved" || b.status === "Rejected"),
        ),
    [cases],
  );

  return (
    <div className="app-shell">
      <header className="institutional-header">
        <div className="brand-bar">
          <button className="brand" onClick={() => setView("Runs")}>
            <span className="brand-mark" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>
              <b>Procurement Modernization Workbench</b>
              <small>Migration validation and analyst review</small>
            </span>
          </button>
          <div className="source-links">
            <span>Official public sources</span>
            <a
              href="https://financesone.worldbank.org/procurement-notice/DS00979"
              target="_blank"
            >
              Procurement notices
            </a>
            <a
              href="https://datacatalog.worldbank.org/search/dataset/0037797/world-bank-contract-awards"
              target="_blank"
            >
              Contract awards
            </a>
            <a
              href="https://datacatalog.worldbank.org/search/dataset/0037800/world-bank-projects-operations"
              target="_blank"
            >
              Projects
            </a>
          </div>
        </div>
        <nav className="primary-navigation">
          <div>
            {(["Runs", "Review queue", "Release readiness"] as View[]).map(
              (item) => (
                <button
                  key={item}
                  className={view === item ? "active" : ""}
                  onClick={() => setView(item)}
                >
                  {item}
                  {item === "Review queue" && (
                    <em>{cases.length - completed}</em>
                  )}
                </button>
              ),
            )}
          </div>
          <div className="utility-navigation">
            <button
              className="evidence-button"
              onClick={() => setSearchOpen(true)}
            >
              Search evidence
            </button>
            <button className="about-button" onClick={() => setAboutOpen(true)}>
              About
            </button>
            <button
              className="mobile-tools-button"
              aria-expanded={mobileToolsOpen}
              aria-controls="mobile-tools"
              onClick={() => setMobileToolsOpen((open) => !open)}
            >
              Sources &amp; search
            </button>
          </div>
        </nav>
        {mobileToolsOpen && (
          <div
            className="mobile-tools-backdrop"
            onClick={() => setMobileToolsOpen(false)}
          >
            <section
              id="mobile-tools"
              className="mobile-tools-panel"
              role="dialog"
              aria-modal="true"
              aria-label="Sources and evidence search"
              onClick={(event) => event.stopPropagation()}
            >
              <header>
                <h2>Sources and search</h2>
                <button
                  onClick={() => setMobileToolsOpen(false)}
                  aria-label="Close sources and search"
                >
                  ×
                </button>
              </header>
              <button
                className="mobile-search-action"
                onClick={() => {
                  setMobileToolsOpen(false);
                  setSearchOpen(true);
                }}
              >
                Search migration evidence
              </button>
              <button
                className="mobile-about-action"
                onClick={() => {
                  setMobileToolsOpen(false);
                  setAboutOpen(true);
                }}
              >
                About this workbench
              </button>
              <nav aria-label="Official public record sources">
                <a
                  href="https://financesone.worldbank.org/procurement-notice/DS00979"
                  target="_blank"
                >
                  <b>Procurement notices</b>
                  <span>World Bank public dataset DS00979</span>
                </a>
                <a
                  href="https://datacatalog.worldbank.org/search/dataset/0037797/world-bank-contract-awards"
                  target="_blank"
                >
                  <b>Contract awards</b>
                  <span>World Bank Data Catalog dataset 0037797</span>
                </a>
                <a
                  href="https://datacatalog.worldbank.org/search/dataset/0037800/world-bank-projects-operations"
                  target="_blank"
                >
                  <b>Projects and Operations</b>
                  <span>World Bank Data Catalog dataset 0037800</span>
                </a>
              </nav>
            </section>
          </div>
        )}
      </header>
      <main>
        {view === "Runs" && (
          <RunView
            onReview={() => setView("Review queue")}
            onReadiness={() => setView("Release readiness")}
            completed={completed}
          />
        )}
        {view === "Review queue" && (
          <ReviewView
            queue={queue}
            selected={selected}
            selectedId={selectedId}
            setSelectedId={setSelectedId}
            reviewer={reviewer}
            setReviewer={setReviewer}
            resolution={resolution}
            setResolution={setResolution}
            rationale={rationale}
            setRationale={setRationale}
            notice={notice}
            errors={decisionErrors}
            completed={completed}
            total={cases.length}
            canSubmit={canSubmitDecision}
            assign={assign}
            start={start}
            decide={decide}
          />
        )}
        {view === "Release readiness" && (
          <ReleaseView
            completed={completed}
            total={cases.length}
            ready={releaseReady}
            onReview={() => setView("Review queue")}
          />
        )}
      </main>
      <footer>
        <span>
          Independent prototype using official public World Bank procurement
          records
        </span>
        <span>
          <a
            href="https://financesone.worldbank.org/procurement-notice/DS00979"
            target="_blank"
          >
            Procurement notices
          </a>
          <a
            href="https://datacatalog.worldbank.org/search/dataset/0037797/world-bank-contract-awards"
            target="_blank"
          >
            Contract awards
          </a>
          <a
            href="https://datacatalog.worldbank.org/search/dataset/0037800/world-bank-projects-operations"
            target="_blank"
          >
            Projects and Operations
          </a>
        </span>
      </footer>
      {searchOpen && (
        <div
          className="drawer-backdrop"
          onMouseDown={() => setSearchOpen(false)}
        >
          <aside
            className="search-drawer"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>Search trusted records</h2>
              </div>
              <button onClick={() => setSearchOpen(false)} aria-label="Close">
                ×
              </button>
            </header>
            <div className="search-box">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
                placeholder="Project, country, supplier or description"
                autoFocus
              />
              <button onClick={search}>Search</button>
            </div>
            <p className="search-help">
              Results come from 759 indexed public records. Unsupported queries
              return no evidence.
            </p>
            {searchStatus === "idle" && (
              <div className="drawer-empty">
                <b>Search the migration evidence package</b>
                <p>
                  Use evidence to investigate a review case without leaving the
                  operational flow.
                </p>
              </div>
            )}
            {searchStatus === "loading" && (
              <div className="drawer-empty">Searching evidence…</div>
            )}
            {(searchStatus === "empty" || searchStatus === "error") && (
              <div className="drawer-empty">
                <b>No supporting evidence</b>
                <p>The indexed scope cannot support this query.</p>
              </div>
            )}
            {searchStatus === "done" && (
              <div className="drawer-results">
                {results.map((r) => (
                  <a key={r.chunk_id} href={r.official_url} target="_blank">
                    <span>
                      {r.record_type} · {r.project_id}
                    </span>
                    <b>{r.text}</b>
                    <small>
                      {r.metadata.country || "Country unavailable"} · score{" "}
                      {r.score.toFixed(3)}
                    </small>
                  </a>
                ))}
              </div>
            )}
          </aside>
        </div>
      )}
      {aboutOpen && (
        <div className="about-backdrop" onMouseDown={() => setAboutOpen(false)}>
          <aside
            className="about-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header>
              <h2 id="about-title">About this workbench</h2>
              <button
                onClick={() => setAboutOpen(false)}
                aria-label="Close about this workbench"
              >
                ×
              </button>
            </header>
            <p className="about-purpose">
              A migration-control prototype for procurement data and QA analysts
              deciding whether transformed records are safe to enter a trusted
              target system.
            </p>
            <div className="about-flow">
              <div>
                <b>Inspect</b>
                <span>
                  Reconcile a migration run and understand its quality signals.
                </span>
              </div>
              <div>
                <b>Decide</b>
                <span>
                  Review source evidence and record an accountable disposition.
                </span>
              </div>
              <div>
                <b>Release</b>
                <span>
                  Confirm whether the bounded migration meets its acceptance
                  criteria.
                </span>
              </div>
            </div>
            <div className="about-scope">
              <b>Prototype scope</b>
              <p>
                Built independently with 600 official public World Bank
                procurement records and three selected analyst-review cases. It
                does not access STEP, private data, or internal World Bank
                systems.
              </p>
            </div>
            <footer>
              <span>
                Designed and engineered by Nicolaas Heru Dreandachrista.
              </span>
              <span>
                Not affiliated with or endorsed by the World Bank Group.
              </span>
            </footer>
          </aside>
        </div>
      )}
    </div>
  );
}

function RunView({
  onReview,
  onReadiness,
  completed,
}: {
  onReview: () => void;
  onReadiness: () => void;
  completed: number;
}) {
  return (
    <>
      <section className="run-hero">
        <div>
          <h1>Public procurement migration</h1>
          <p>
            600 official public records moving through validation, review and
            controlled release.
          </p>
          <div className="hero-actions">
            <button onClick={onReview}>Review unresolved cases</button>
            <button onClick={onReadiness}>View release readiness</button>
          </div>
        </div>
        <div className="run-status">
          <i />
          <span>
            <b>Validation complete</b>
            <small>Analyst review required</small>
          </span>
        </div>
      </section>
      <div className="page runs-page">
        <section className="decision-banner">
          <div>
            <h2>
              {3 - completed} selected exception{" "}
              {3 - completed === 1 ? "case remains" : "cases remain"} before
              release assessment.
            </h2>
            <p>
              Reconciliation passed. Quality warnings remain traceable and
              require documented analyst disposition.
            </p>
          </div>
          <button onClick={onReview}>Open review queue</button>
        </section>
        <section className="metrics">
          <Metric
            value="600"
            label="Records read"
            detail="300 notices · 300 awards"
          />
          <Metric
            value="600"
            label="Loaded"
            detail="No rejected source records"
          />
          <Metric
            value="160"
            label="Quality signals"
            detail="47 duplicates · 113 linkage"
            tone="warning"
          />
          <Metric
            value={`${completed}/3`}
            label="Selected reviews complete"
            detail="Prototype adjudication scope"
          />
        </section>
        <div className="run-grid">
          <section className="panel reconciliation-panel">
            <PanelHead
              label=""
              title="Source and target counts agree"
              action="Passed"
            />
            <div className="count-flow">
              <div>
                <span>Source snapshot</span>
                <b>600</b>
                <small>records</small>
              </div>
              <div>
                <span>Standardized</span>
                <b>600</b>
                <small>records</small>
              </div>
              <div>
                <span>Curated</span>
                <b>600</b>
                <small>records</small>
              </div>
            </div>
            <ul className="checks">
              <li>
                <span>✓</span>Primary keys remain unique
              </li>
              <li>
                <span>✓</span>Required identifiers normalized
              </li>
              <li>
                <span>✓</span>Source payloads and checksums retained
              </li>
            </ul>
          </section>
          <section className="panel controls-panel">
            <PanelHead label="" title="Quality controls requiring attention" />
            <button onClick={onReview}>
              <span className="dot amber" />
              <div>
                <b>DQ-008 · Potential duplicate content</b>
                <p>47 records · analyst comparison required</p>
              </div>
              <strong>Review</strong>
            </button>
            <button>
              <span className="dot blue" />
              <div>
                <b>DQ-007 · Project metadata unavailable</b>
                <p>113 records · non-blocking enrichment warning</p>
              </div>
              <strong>Inspect</strong>
            </button>
          </section>
        </div>
        <section className="run-details">
          <PanelHead label="" title="Reproducibility and lineage" />
          <dl>
            <div>
              <dt>Run ID</dt>
              <dd>79f796ab-c3dd-4922-9d8a-3337803c106f</dd>
            </div>
            <div>
              <dt>Raw checksum</dt>
              <dd>SHA-256 verified</dd>
            </div>
            <div>
              <dt>Schema fingerprint</dt>
              <dd>267cc6ae…e40fc9d3</dd>
            </div>
            <div>
              <dt>Pipeline version</dt>
              <dd>0.1.0</dd>
            </div>
            <div>
              <dt>Execution</dt>
              <dd>13 seconds · completed</dd>
            </div>
          </dl>
          <div className="record-sources">
            <span>Records retrieved from</span>
            <a
              href="https://financesone.worldbank.org/procurement-notice/DS00979"
              target="_blank"
            >
              World Bank Procurement Notices
            </a>
            <a
              href="https://datacatalog.worldbank.org/search/dataset/0037797/world-bank-contract-awards"
              target="_blank"
            >
              World Bank Contract Awards
            </a>
            <a
              href="https://datacatalog.worldbank.org/search/dataset/0037800/world-bank-projects-operations"
              target="_blank"
            >
              World Bank Projects and Operations
            </a>
          </div>
        </section>
      </div>
    </>
  );
}

function ReviewView(p: {
  queue: ReviewCase[];
  selected: ReviewCase;
  selectedId: string;
  setSelectedId: (v: string) => void;
  reviewer: string;
  setReviewer: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  rationale: string;
  setRationale: (v: string) => void;
  notice: string;
  errors: DecisionErrors;
  completed: number;
  total: number;
  canSubmit: boolean;
  assign: () => void;
  start: () => void;
  decide: () => void;
}) {
  const s = p.selected;
  const locked = s.status === "Resolved" || s.status === "Rejected";
  return (
    <div className="review-page">
      <aside className="queue-column">
        <header>
          <h1>Exception review</h1>
          <p className="review-progress" aria-live="polite">
            {p.completed} of {p.total} selected reviews complete
          </p>
          <div className="queue-filters">
            <button className="active">All 3</button>
            <button>
              Open{" "}
              {
                p.queue.filter(
                  (c) =>
                    !(["Resolved", "Rejected"] as Status[]).includes(c.status),
                ).length
              }
            </button>
          </div>
        </header>
        <div className="case-list">
          {p.queue.map((c) => (
            <button
              key={c.id}
              className={p.selectedId === c.id ? "selected" : ""}
              onClick={() => p.setSelectedId(c.id)}
            >
              <div>
                <span className={`priority ${c.priority.toLowerCase()}`}>
                  {c.priority}
                </span>
                <small>{c.status}</small>
              </div>
              <b>
                {c.control} · {c.title}
              </b>
              <p>
                Notice {c.recordId} · {c.country}
              </p>
              <footer>
                <span>{c.assignee || "Unassigned"}</span>
              </footer>
            </button>
          ))}
        </div>
      </aside>
      <section className="case-workspace">
        <header className="case-header">
          <div>
            <span>
              {s.id} · Notice {s.recordId}
            </span>
            <h2>{s.title}</h2>
            <p>
              {s.control} detected repeated normalized content within the same
              procurement context.
            </p>
          </div>
          <span className={`status-pill ${locked ? "complete" : "active"}`}>
            {s.status}
          </span>
        </header>
        <div className="evidence-layout">
          <article className="evidence-document">
            <div className="document-head">
              <h3>Source evidence</h3>
              <a
                href={`https://projects.worldbank.org/en/projects-operations/project-detail/${s.projectId}`}
                target="_blank"
              >
                Open official project
              </a>
            </div>
            <dl>
              <div>
                <dt>Record</dt>
                <dd>Procurement notice {s.recordId}</dd>
              </div>
              <div>
                <dt>Project ID</dt>
                <dd>{s.projectId}</dd>
              </div>
              <div>
                <dt>Country</dt>
                <dd>{s.country}</dd>
              </div>
              <div className="wide">
                <dt>Published description</dt>
                <dd>{s.sourceValue}</dd>
              </div>
            </dl>
            <div className="comparison">
              <span>Matched evidence</span>
              <b>{s.comparison}</b>
              <p>
                The pipeline preserved both records. Similarity is a review
                signal, not proof that either record is invalid.
              </p>
            </div>
            <div className="lineage">
              <span>Source payload retained</span>
              <span>Checksum verified</span>
              <span>No automatic mutation</span>
            </div>
          </article>
          <aside className="decision-card">
            <h3>Analyst decision</h3>
            <p className="decision-intro">
              Determine how this record should be handled in the trusted layer.
            </p>
            {!locked ? (
              <>
                <label>
                  Assigned reviewer
                  <div className="input-action">
                    <input
                      value={p.reviewer}
                      onChange={(e) => p.setReviewer(e.target.value)}
                      placeholder={s.assignee || "Full name"}
                      aria-invalid={Boolean(p.errors.reviewer)}
                      aria-describedby="reviewer-error"
                    />
                    <button
                      onClick={p.assign}
                      disabled={p.reviewer.trim().length < 2}
                    >
                      Assign
                    </button>
                  </div>
                </label>
                {p.errors.reviewer && (
                  <p className="field-error" id="reviewer-error">
                    {p.errors.reviewer}
                  </p>
                )}
                <button
                  className="start-review"
                  onClick={p.start}
                  disabled={!s.assignee || s.status === "In review"}
                >
                  Begin review
                </button>
                {p.errors.status && (
                  <p className="field-error">{p.errors.status}</p>
                )}
                <ul
                  className="decision-requirements"
                  aria-label="Decision requirements"
                >
                  <li className={s.assignee ? "met" : ""}>Reviewer assigned</li>
                  <li className={s.status === "In review" ? "met" : ""}>
                    Review in progress
                  </li>
                  <li className={p.resolution ? "met" : ""}>
                    Disposition selected
                  </li>
                  <li className={p.rationale.trim().length >= 20 ? "met" : ""}>
                    Rationale meets minimum
                  </li>
                </ul>
                <fieldset className={p.errors.resolution ? "has-error" : ""}>
                  <legend>Disposition</legend>
                  {[
                    "Accept documented exception",
                    "Send for remediation",
                    "Reject from trusted layer",
                  ].map((item) => (
                    <label key={item}>
                      <input
                        type="radio"
                        name="decision"
                        checked={p.resolution === item}
                        onChange={() => p.setResolution(item)}
                      />
                      <span>
                        <b>{item}</b>
                        <small>
                          {item === "Accept documented exception"
                            ? "Retain the record with rationale"
                            : item === "Send for remediation"
                              ? "Return it for correction and retest"
                              : "Exclude it from the trusted layer"}
                        </small>
                      </span>
                    </label>
                  ))}
                </fieldset>
                {p.errors.resolution && (
                  <p className="field-error" id="resolution-error">
                    {p.errors.resolution}
                  </p>
                )}
                <label>
                  <span className="rationale-label">
                    Required rationale
                    <small
                      className={p.rationale.trim().length >= 20 ? "valid" : ""}
                    >
                      {p.rationale.trim().length}/20 minimum
                    </small>
                  </span>
                  <textarea
                    value={p.rationale}
                    onChange={(e) => p.setRationale(e.target.value)}
                    placeholder="Reference the evidence considered and explain the decision."
                    aria-invalid={Boolean(p.errors.rationale)}
                    aria-describedby="rationale-error"
                  />
                </label>
                {p.errors.rationale && (
                  <p className="field-error" id="rationale-error">
                    {p.errors.rationale}
                  </p>
                )}
                <button
                  className="primary decision-submit"
                  onClick={p.decide}
                  disabled={!p.canSubmit}
                >
                  Record accountable decision
                </button>
                {p.notice && (
                  <p className="form-notice" aria-live="polite">
                    {p.notice}
                  </p>
                )}
              </>
            ) : (
              <div className="recorded-decision">
                <span>Recorded disposition</span>
                <b>{s.resolution}</b>
                <p>{s.rationale}</p>
                <small>Decision stored in the append-only case history.</small>
              </div>
            )}
          </aside>
        </div>
        <section className="audit-log">
          <div>
            <span>Audit history</span>
            <h3>Every state change remains reconstructable</h3>
          </div>
          <ol>
            {s.events.map((e, i) => (
              <li key={i}>
                <span>{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <b>{e.action}</b>
                  <p>{e.note}</p>
                </div>
                <aside>
                  <b>{e.actor}</b>
                  <span>{e.at}</span>
                </aside>
              </li>
            ))}
          </ol>
        </section>
      </section>
    </div>
  );
}

function ReleaseView({
  completed,
  total,
  ready,
  onReview,
}: {
  completed: number;
  total: number;
  ready: boolean;
  onReview: () => void;
}) {
  return (
    <div className="page release-page">
      <section className={`release-hero ${ready ? "ready" : "blocked"}`}>
        <div>
          <h1>
            {ready
              ? "Ready for controlled release"
              : `${total - completed} review decisions remain open.`}
          </h1>
          <p>
            {ready
              ? "The evidence package is complete for this bounded rehearsal scope."
              : "Reconciliation has passed, but the selected exception scope must be adjudicated before readiness can be confirmed."}
          </p>
        </div>
        <b>{ready ? "Ready" : "Pending"}</b>
      </section>
      <section className="criteria">
        <header>
          <div>
            <h2>Release decision package</h2>
          </div>
          <p>
            {completed} of {total} selected reviews completed
          </p>
        </header>
        <Criterion
          title="Source-to-target reconciliation"
          detail="600 source records match 600 curated records."
          state="Passed"
        />
        <Criterion
          title="Schema and identifier validation"
          detail="Required formats and keys passed implemented controls."
          state="Passed"
        />
        <Criterion
          title="Blocking exception disposition"
          detail={`${total - completed} selected cases still require accountable decisions.`}
          state={ready ? "Passed" : "Action required"}
        />
        <Criterion
          title="Audit evidence completeness"
          detail="Decision actors, rationales and timestamps must be recorded."
          state={ready ? "Passed" : "Pending"}
        />
        <Criterion
          title="Rollback evidence"
          detail="Raw source snapshot and checksum are retained."
          state="Passed"
        />
      </section>
      {!ready && (
        <section className="release-action">
          <div>
            <h2>Complete the outstanding exception reviews.</h2>
          </div>
          <button className="primary" onClick={onReview}>
            Continue review
          </button>
        </section>
      )}
      <section className="scope-boundary">
        <b>Prototype boundary</b>
        <p>
          This readiness assessment covers the verified 600-record rehearsal and
          three selected analyst cases. Institutional release would additionally
          require authenticated approvals, complete UAT evidence, environment
          controls and stakeholder sign-off.
        </p>
      </section>
    </div>
  );
}

function Metric({
  value,
  label,
  detail,
  tone,
}: {
  value: string;
  label: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className={tone || ""}>
      <span>{label}</span>
      <b>{value}</b>
      <p>{detail}</p>
    </article>
  );
}
function PanelHead({
  label,
  title,
  action,
}: {
  label: string;
  title: string;
  action?: string;
}) {
  return (
    <header className="panel-head">
      <div>
        <span>{label}</span>
        <h3>{title}</h3>
      </div>
      {action && <b>{action}</b>}
    </header>
  );
}
function Criterion({
  title,
  detail,
  state,
}: {
  title: string;
  detail: string;
  state: string;
}) {
  return (
    <article>
      <span className={state === "Passed" ? "check-icon" : "pending-icon"}>
        {state === "Passed" ? "✓" : "!"}
      </span>
      <div>
        <b>{title}</b>
        <p>{detail}</p>
      </div>
      <strong className={state.toLowerCase().replace(" ", "-")}>{state}</strong>
    </article>
  );
}
