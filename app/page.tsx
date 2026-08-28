"use client";

import { useEffect, useState } from "react";

type View = "Overview" | "Pipeline" | "Data quality" | "Analyst review" | "Evidence search" | "Methodology";
type CorpusRecord = {chunk_id:string;record_type:string;record_id:string;project_id:string;text:string;official_url:string;metadata:{country?:string|null};embedding:number[]};
type SearchResult = CorpusRecord & {retrieval_score:number};
type SearchState = {status:"idle"|"loading"|"done"|"error";results:SearchResult[];abstained:boolean;latency:number;source:string};
type ReviewStatus="Open"|"Assigned"|"In review"|"Resolved"|"Rejected";
type ReviewEvent={event:string;actor:string;at:string;note:string};
type ReviewCase={id:string;recordId:string;controlId:string;severity:"Warning"|"Error";title:string;sourceField:string;originalValue:string;recommended:string;status:ReviewStatus;priority:"High"|"Medium";assignee:string;resolution?:string;rationale?:string;retest?:string;events:ReviewEvent[]};

const sqlChecks = [
  {purpose:"Reconcile source and curated counts",sql:"SELECT records_read, accepted, quarantined\nFROM ingestion_runs WHERE run_id = :run_id;"},
  {purpose:"Protect award totals from unsafe joins",sql:"SELECT project_id, SUM(amount) AS award_amount\nFROM contract_awards GROUP BY project_id;"},
  {purpose:"Find unresolved project relationships",sql:"SELECT n.project_id, COUNT(*) AS notices\nFROM procurement_notices n\nLEFT JOIN projects p USING (project_id)\nWHERE p.project_id IS NULL GROUP BY n.project_id;"},
];

const migrationStages = [
  ["Discover","Inventory sources, owners, formats, volume and dependencies"],
  ["Profile","Measure keys, nulls, duplicates, code sets and temporal coverage"],
  ["Map","Assign every source field a target rule and exception policy"],
  ["Rehearse","Run bounded migrations, reconcile results and resolve defects"],
  ["Cut over","Freeze changes, apply the final delta and retain rollback evidence"],
  ["Stabilize","Monitor defects, performance and residual remediation"],
];

const productionTranslations = [
  {today:"Python + SQLite pipeline",target:"Databricks jobs + Delta Lake",reason:"Distributed transformations, ACID tables and versioned bronze/silver/gold layers"},
  {today:"Bounded API ingestion",target:"Orchestrated incremental loads",reason:"Checkpointed pagination, retry policy, schema-drift alerts and resumable runs"},
  {today:"SQLite curated model",target:"Snowflake or managed PostgreSQL",reason:"Separated compute, governed schemas, workload isolation and institutional access"},
  {today:"Deterministic 256-d vectors",target:"Model registry + managed vector store",reason:"Versioned multilingual embeddings, access filtering, evaluation and monitoring"},
];

const tokenize=(text:string)=>text.toLowerCase().match(/[a-z0-9]{2,}/g)||[];
const stopWords=new Set(["and","are","award","bank","contract","data","for","from","in","notice","of","on","project","procurement","record","records","the","to","world"]);
const distinctiveTokens=(text:string)=>new Set(tokenize(text).filter(token=>!stopWords.has(token)));
function vector(text:string,vocabulary:Record<string,number>,dims=256){
  const counts=new Map<string,number>();
  tokenize(text).forEach(token=>counts.set(token,(counts.get(token)||0)+1));
  const output=Array(dims).fill(0) as number[];
  for(const [token,count] of counts){
    const bucket=vocabulary[token];
    if(bucket!==undefined)output[bucket]+=1+Math.log(count);
  }
  const norm=Math.sqrt(output.reduce((sum,value)=>sum+value*value,0))||1;
  return output.map(value=>value/norm);
}

const controls = [
  {id:"DQ-001",name:"Missing project identifier",severity:"Error",rule:"Project ID is empty",handling:"Quarantine until a valid ID is available",count:0},
  {id:"DQ-002",name:"Invalid project identifier",severity:"Error",rule:"Does not match P plus six digits",handling:"Preserve the source value and quarantine",count:0},
  {id:"DQ-003",name:"Missing notice title",severity:"Error",rule:"Description is empty",handling:"Quarantine; never infer a title",count:0},
  {id:"DQ-004",name:"Invalid date format",severity:"Error",rule:"Date cannot be normalized to ISO",handling:"Preserve the original value and quarantine",count:0},
  {id:"DQ-005",name:"Deadline before publication",severity:"Warning",rule:"Deadline is earlier than publication",handling:"Retain and request human review",count:0},
  {id:"DQ-006",name:"Missing procurement category",severity:"Info",rule:"Category is empty",handling:"Retain as incomplete metadata",count:0},
  {id:"DQ-007",name:"Project metadata unavailable",severity:"Warning",rule:"Valid project ID has no project row in this bounded sample",handling:"Retain the record and retrieve metadata later",count:113},
  {id:"DQ-008",name:"Potential duplicate content",severity:"Warning",rule:"Same project, description and dates",handling:"Retain both records and compare the official sources",count:47},
];

const layers = [
  {n:"01",name:"Raw evidence",fact:"600 records",copy:"Complete API responses are stored with retrieval time, source URLs and a SHA-256 checksum."},
  {n:"02",name:"Standardized",fact:"8 controls",copy:"Project identifiers and dates are normalized while original JSON remains intact for audit."},
  {n:"03",name:"Curated SQL",fact:"9 tables",copy:"Notices, awards, projects, validation results and run history become queryable relational data."},
  {n:"04",name:"Project features",fact:"272 rows",copy:"Counts, supplier totals, missingness, linkage and quality scores are calculated by project."},
  {n:"05",name:"Evidence index",fact:"759 chunks",copy:"Record text is indexed with metadata, citations and deterministic 256-dimensional vectors."},
];

const initialReviewCases:ReviewCase[]=[
  {id:"REV-00001",recordId:"459873",controlId:"DQ-008",severity:"Warning",title:"Potential duplicate content",sourceField:"bid_description",originalValue:"Software",recommended:"Compare the official source records before choosing a canonical record.",status:"Open",priority:"High",assignee:"",events:[{event:"Case created",actor:"Validation pipeline",at:"5 Aug 2026 · 14:32 UTC",note:"Opened from validation result 1 in verified run 79f796ab…"}]},
  {id:"REV-00002",recordId:"459874",controlId:"DQ-008",severity:"Warning",title:"Potential duplicate content",sourceField:"bid_description",originalValue:"Software",recommended:"Compare the official source records before choosing a canonical record.",status:"Open",priority:"High",assignee:"",events:[{event:"Case created",actor:"Validation pipeline",at:"5 Aug 2026 · 14:32 UTC",note:"Opened from validation result 2 in verified run 79f796ab…"}]},
  {id:"REV-00003",recordId:"459884",controlId:"DQ-008",severity:"Warning",title:"Potential duplicate content",sourceField:"bid_description",originalValue:"ACQUISITION DE FOURNITURES DE BUREAU ET DE CONSOMMABLES INFORMATIQUES",recommended:"Retain both records until an analyst compares the official sources.",status:"Open",priority:"Medium",assignee:"",events:[{event:"Case created",actor:"Validation pipeline",at:"5 Aug 2026 · 14:32 UTC",note:"Opened from validation result 3 in verified run 79f796ab…"}]},
];

export default function Workbench(){
  const [view,setView]=useState<View>("Overview");
  const [query,setQuery]=useState("");
  const [selectedControl,setSelectedControl]=useState(controls[7]);
  const [selectedSql,setSelectedSql]=useState(0);
  const [searchState,setSearchState]=useState<SearchState>({status:"idle",results:[],abstained:false,latency:0,source:""});
  const [guidedMode,setGuidedMode]=useState(false);
  const [reviewCases,setReviewCases]=useState<ReviewCase[]>(initialReviewCases);
  const [selectedCaseId,setSelectedCaseId]=useState(initialReviewCases[0].id);
  const [reviewer,setReviewer]=useState("");
  const [resolution,setResolution]=useState("accept_exception");
  const [rationale,setRationale]=useState("");
  const [reviewNotice,setReviewNotice]=useState("");
  useEffect(()=>{const saved=window.localStorage.getItem("procurement-review-cases-v1");if(saved)try{setReviewCases(JSON.parse(saved))}catch{}},[]);
  useEffect(()=>{window.localStorage.setItem("procurement-review-cases-v1",JSON.stringify(reviewCases))},[reviewCases]);
  const go=(next:View)=>{setView(next);window.scrollTo({top:0,behavior:"smooth"})};
  const guideViews:View[]=["Pipeline","Data quality","Analyst review","Evidence search","Methodology"];
  const guideIndex=guideViews.indexOf(view);
  const startGuide=()=>{setGuidedMode(true);go("Pipeline")};
  const nextGuide=()=>{if(guideIndex<guideViews.length-1)go(guideViews[guideIndex+1]);else{setGuidedMode(false);go("Overview")}};
  async function runSearch(nextQuery=query){
    const clean=nextQuery.trim(); if(clean.length<3)return;
    setQuery(clean); setSearchState(state=>({...state,status:"loading"}));
    const started=performance.now();
    try{
      const response=await fetch("/data/retrieval-corpus.json");
      if(!response.ok)throw new Error("Evidence index unavailable");
      const corpus=await response.json() as {source:string;vocabulary:Record<string,number>;records:CorpusRecord[]};
      const queryVector=vector(clean,corpus.vocabulary);
      const queryTerms=distinctiveTokens(clean);
      const ranked=corpus.records
        .filter(record=>[...distinctiveTokens(record.text)].some(token=>queryTerms.has(token)))
        .map(record=>({...record,retrieval_score:queryVector.reduce((score,value,index)=>score+value*(record.embedding[index]||0),0)}))
        .filter(record=>record.retrieval_score>0)
        .sort((a,b)=>b.retrieval_score-a.retrieval_score).slice(0,8);
      const abstained=!ranked.length||ranked[0].retrieval_score<.12;
      setSearchState({status:"done",results:abstained?[]:ranked,abstained,latency:performance.now()-started,source:corpus.source});
    }catch{
      setSearchState({status:"error",results:[],abstained:true,latency:performance.now()-started,source:""});
    }
  }
  const selectedCase=reviewCases.find(item=>item.id===selectedCaseId)||reviewCases[0];
  const stamp=()=>new Date().toLocaleString("en-GB",{day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"UTC",timeZoneName:"short"});
  const updateCase=(change:Partial<ReviewCase>,event?:ReviewEvent)=>setReviewCases(cases=>cases.map(item=>item.id===selectedCaseId?{...item,...change,events:event?[...item.events,event]:item.events}:item));
  const assignCase=()=>{const actor=reviewer.trim();if(!actor){setReviewNotice("Enter a reviewer name before assigning the case.");return}updateCase({assignee:actor,status:"Assigned"},{event:"Case assigned",actor,at:stamp(),note:`Ownership assigned to ${actor}.`});setReviewNotice("Assignment recorded in the audit trail.")};
  const beginReview=()=>{const actor=selectedCase.assignee||reviewer.trim();if(!actor){setReviewNotice("Assign the case before beginning review.");return}updateCase({assignee:actor,status:"In review"},{event:"Review started",actor,at:stamp(),note:"Case moved from assigned to in review."});setReviewNotice("Review started.")};
  const decideCase=()=>{const actor=selectedCase.assignee||reviewer.trim();if(!actor||rationale.trim().length<20){setReviewNotice("A reviewer and a rationale of at least 20 characters are required.");return}const labels:Record<string,string>={accept_exception:"Accept documented exception",remediate:"Send for remediation",reject_record:"Reject from trusted layer"};const status:ReviewStatus=resolution==="reject_record"?"Rejected":"Resolved";const retest=resolution==="remediate"?"Pending":"Not required";updateCase({status,resolution:labels[resolution],rationale:rationale.trim(),retest},{event:"Decision recorded",actor,at:stamp(),note:`${labels[resolution]}. Rationale: ${rationale.trim()} Retest: ${retest}.`});setReviewNotice("Decision locked into the case history.");setRationale("")};

  return <main className="case-site">
    <header className="case-brand"><button onClick={()=>go("Overview")}><b>Procurement<br/>Evidence</b></button><div><strong>AI Data Engineering Case Study</strong><span>Independent prototype · Nicolaas Dreandachrista</span></div></header>
    <nav className="case-nav" aria-label="Case study navigation"><div>{(["Overview","Pipeline","Data quality","Analyst review","Evidence search","Methodology"] as View[]).map(item=><button key={item} className={view===item?"active":""} onClick={()=>go(item)}>{item}</button>)}</div><span>Verified bounded run · 5 Aug 2026</span></nav>

    {guidedMode&&guideIndex>=0&&<aside className="guide-dock" aria-live="polite"><div className="guide-progress"><span style={{width:`${((guideIndex+1)/guideViews.length)*100}%`}}/></div><button className="guide-close" aria-label="Exit guided walkthrough" onClick={()=>setGuidedMode(false)}>×</button><p>Guided walkthrough · {guideIndex+1} of {guideViews.length}</p><h2>{["Follow one record from source to evidence.","See how uncertainty is detected.","Make and audit a human decision.","Test retrieval, then watch it refuse to guess.","Finish with the production path."][guideIndex]}</h2><button className="guide-next" onClick={nextGuide}>{guideIndex===guideViews.length-1?"Finish walkthrough":"Continue"}<span>→</span></button></aside>}

    {view==="Overview"&&<>
      <section className="case-hero"><div className="case-hero-copy"><p>Procurement data modernization</p><span className="start-here">Start here · 3 minutes · no setup needed</span><h1>From fragmented records to traceable evidence.</h1><p className="hero-lead">I built this workbench to test the central challenge in the World Bank’s AI Data Engineer internship: migrating heterogeneous procurement data into validated, documented and AI-retrievable layers.</p><div className="hero-actions"><button className="case-primary" onClick={startGuide}>Guide me through it <span>→</span></button><button className="case-secondary" onClick={()=>go("Evidence search")}>Try the evidence search</button></div></div><div className="hero-proof"><span>Verified prototype scope</span><b>600</b><h2>source records processed</h2><p>300 notices + 300 contract awards</p><div><strong>159</strong><span>projects materialized</span></div></div></section>
      <section className="challenge-statement"><p>The engineering question</p><h2>How can public procurement records become consistent enough for analytics without hiding uncertainty or breaking their source trail?</h2></section>
      <section className="proof-ribbon"><button onClick={()=>go("Pipeline")}><b>272</b><span>project feature rows</span></button><button onClick={()=>go("Data quality")}><b>8</b><span>documented controls</span></button><button onClick={()=>go("Evidence search")}><b>759</b><span>indexed evidence chunks</span></button><button onClick={()=>go("Methodology")}><b>3</b><span>tested source structures</span></button></section>
      <section className="walkthrough"><div><p>Choose what you want to verify</p><h2>Every claim opens into evidence.</h2><button className="walkthrough-start" onClick={startGuide}>Start the recommended path →</button></div><ol><li><button onClick={()=>go("Pipeline")}><span>01</span><b>Can he engineer the migration?</b><small>Follow raw records into validated SQL and an evidence index.</small></button></li><li><button onClick={()=>go("Data quality")}><span>02</span><b>Does he understand data integrity?</b><small>Inspect a control decision without silent edits or inflated claims.</small></button></li><li><button onClick={()=>go("Evidence search")}><span>03</span><b>Is the AI behavior real?</b><small>Search 759 indexed records, then trigger an explicit abstention.</small></button></li></ol></section>
    </>}

    {view==="Pipeline"&&<CasePage eyebrow="Pipeline" title="One run, five inspectable layers." intro="This is not a decorative flowchart. Each layer corresponds to implemented Python, SQL, stored evidence and documented outputs.">
      <section className="run-heading"><div><p>Verified run</p><h2>5 August 2026</h2><span>Completed in 13 seconds · bounded local execution</span></div><div className="reconciliation"><span><b>600</b>read</span><i>→</i><span><b>600</b>accepted</span><i>→</i><span><b>0</b>quarantined</span></div></section>
      <section className="layer-story">{layers.map(layer=><article key={layer.n}><span>{layer.n}</span><div><p>{layer.name}</p><h3>{layer.fact}</h3></div><p>{layer.copy}</p></article>)}</section>
      <section className="mapping"><div className="section-side"><p>Transformation evidence</p><h2>Source-to-target mapping</h2><span>The source value is always retained in raw JSON.</span></div><div className="mapping-list"><Mapping source="projectid" target="project_id" rule="Trim whitespace, uppercase, require P + six digits"/><Mapping source="contr_sgn_date" target="signed_date" rule="Parse supported source date and emit ISO-8601"/><Mapping source="contr_desc" target="description" rule="Preserve the published source text without rewriting"/><Mapping source="total_contr_amnt" target="amount" rule="Parse numeric value; retain original payload for audit"/></div></section>
      <section className="record-inspection"><div className="section-side"><p>One record, fully traced</p><h2>See the transformation, not just its outcome.</h2><span>A representative award shows the source value, normalization decision and curated field side by side.</span></div><div className="record-trace"><article><span>Raw source</span><pre>{`{
  "projectid": " p166309 ",
  "contr_sgn_date": "29-Jul-2026",
  "total_contr_amnt": "1285000"
}`}</pre></article><i>validated by DQ-002 / DQ-004 →</i><article><span>Curated record</span><pre>{`{
  "project_id": "P166309",
  "signed_date": "2026-07-29",
  "amount": 1285000.00
}`}</pre></article></div></section>
      <section className="model-evidence"><div className="section-side"><p>Relational model</p><h2>Grain, keys and joins are explicit.</h2><span>Financial totals are aggregated before joining so one-to-many relationships cannot multiply values.</span></div><div className="entity-flow"><div><b>projects</b><span>PK project_id</span></div><i>1 → many</i><div><b>procurement_notices</b><span>PK notice_id · FK project_id</span></div><div><b>contract_awards</b><span>PK award_id · FK project_id</span></div><i>many → 1</i><div><b>procurement_features</b><span>PK/FK project_id · one row per project</span></div></div></section>
      <section className="sql-evidence"><div><p>Executable SQL evidence</p><h2>Three checks that protect migration meaning.</h2><nav>{sqlChecks.map((check,index)=><button key={check.purpose} className={selectedSql===index?"selected":""} onClick={()=>setSelectedSql(index)}><span>0{index+1}</span>{check.purpose}</button>)}</nav></div><article><span>SQLite · parameterized</span><pre>{sqlChecks[selectedSql].sql}</pre><p>Stored with the run ledger and designed to remain valid when translated to a governed warehouse.</p></article></section>
      <section className="run-evidence"><div><p>Run ledger</p><h2>What makes it reproducible?</h2></div><ul><li><b>Run ID</b><span>79f796ab-c3dd-4922-9d8a-3337803c106f</span></li><li><b>Raw checksum</b><span>SHA-256 stored with the ingestion record</span></li><li><b>Schema fingerprint</b><span>267cc6ae…e40fc9d3</span></li><li><b>Idempotence</b><span>Primary-key upserts prevent repeated rows</span></li><li><b>Failure handling</b><span>Timeout, bounded retries and quarantine ledger</span></li></ul></section>
    </CasePage>}

    {view==="Data quality"&&<CasePage eyebrow="Data quality" title="Uncertainty becomes a review signal, never a silent edit." intro="Eight controls record what happened, where it happened and what a human should do next.">
      <section className="quality-layout"><aside><p>Control catalog</p>{controls.map(control=><button key={control.id} className={selectedControl.id===control.id?"selected":""} onClick={()=>setSelectedControl(control)}><span>{control.id}</span><b>{control.name}</b><small>{control.count} affected</small></button>)}</aside><article className="control-detail"><div className="control-top"><span className={`severity ${selectedControl.severity.toLowerCase()}`}>{selectedControl.severity}</span><b>{selectedControl.count}</b><small>records affected</small></div><p>{selectedControl.id}</p><h2>{selectedControl.name}</h2><dl><div><dt>Rule evaluated</dt><dd>{selectedControl.rule}</dd></div><div><dt>Recommended handling</dt><dd>{selectedControl.handling}</dd></div><div><dt>Automatic mutation?</dt><dd>No. The original source value remains available for review.</dd></div></dl><div className="quality-principle"><b>Why this matters</b><p>A quality signal is not evidence of misconduct. The pipeline records uncertainty without converting it into an accusation or deleting an ambiguous record.</p></div></article></section>
      <section className="example-pair"><div><p>Example transformation</p><h2>The audit trail keeps both values.</h2></div><div><span>Original source value</span><code>“ p166309 ”</code><i>→</i><span>Normalized value</span><code>P166309</code><small>Control decision and run ID are stored beside the transformation.</small></div></section>
      <section className="review-handoff"><div><p>Human control point</p><h2>A signal only matters if someone can decide what happens next.</h2></div><button onClick={()=>go("Analyst review")}>Open the review queue <span>→</span></button></section>
    </CasePage>}

    {view==="Analyst review"&&<CasePage eyebrow="Analyst review" title="Every exception ends in an accountable decision." intro="Assign a real validation case, record a disposition and inspect the append-only history that explains who decided what and why.">
      <section className="review-summary"><div><b>{reviewCases.filter(item=>item.status==="Open").length}</b><span>open</span></div><div><b>{reviewCases.filter(item=>item.status==="In review"||item.status==="Assigned").length}</b><span>active</span></div><div><b>{reviewCases.filter(item=>item.status==="Resolved"||item.status==="Rejected").length}</b><span>decided</span></div><p>Prototype decisions persist in this browser. The FastAPI implementation stores the same lifecycle in relational case and event tables.</p></section>
      <section className="review-workbench">
        <aside className="review-queue"><header><p>Exception queue</p><span>{reviewCases.length} cases</span></header>{reviewCases.map(item=><button key={item.id} className={selectedCaseId===item.id?"selected":""} onClick={()=>{setSelectedCaseId(item.id);setReviewNotice("")}}><div><b>{item.id}</b><span className={`case-status ${item.status.toLowerCase().replace(" ","-")}`}>{item.status}</span></div><h3>{item.controlId} · {item.title}</h3><p>Notice {item.recordId} · {item.priority} priority</p><small>{item.assignee||"Unassigned"}</small></button>)}</aside>
        <article className="review-case"><header><div><p>{selectedCase.id} · Notice {selectedCase.recordId}</p><h2>{selectedCase.title}</h2></div><span className={`case-status ${selectedCase.status.toLowerCase().replace(" ","-")}`}>{selectedCase.status}</span></header>
          <div className="case-evidence"><div><span>Control</span><b>{selectedCase.controlId} · {selectedCase.severity}</b></div><div><span>Source field</span><code>{selectedCase.sourceField}</code></div><div className="wide"><span>Original source value</span><p>{selectedCase.originalValue}</p></div><div className="wide"><span>Recommended handling</span><p>{selectedCase.recommended}</p></div></div>
          <section className="decision-panel"><h3>Record the accountable action</h3><div className="assignment"><label>Reviewer<input value={reviewer} onChange={event=>setReviewer(event.target.value)} placeholder={selectedCase.assignee||"Enter reviewer name"}/></label><button onClick={assignCase}>Assign case</button><button onClick={beginReview} disabled={selectedCase.status==="Resolved"||selectedCase.status==="Rejected"}>Begin review</button></div><fieldset disabled={selectedCase.status==="Resolved"||selectedCase.status==="Rejected"}><legend>Disposition</legend><label><input type="radio" name="resolution" value="accept_exception" checked={resolution==="accept_exception"} onChange={event=>setResolution(event.target.value)}/>Accept documented exception</label><label><input type="radio" name="resolution" value="remediate" checked={resolution==="remediate"} onChange={event=>setResolution(event.target.value)}/>Send for remediation</label><label><input type="radio" name="resolution" value="reject_record" checked={resolution==="reject_record"} onChange={event=>setResolution(event.target.value)}/>Reject from trusted layer</label></fieldset><label className="rationale">Decision rationale<textarea value={rationale} onChange={event=>setRationale(event.target.value)} placeholder="Explain the evidence considered and why this disposition is appropriate." disabled={selectedCase.status==="Resolved"||selectedCase.status==="Rejected"}/></label><button className="record-decision" onClick={decideCase} disabled={selectedCase.status==="Resolved"||selectedCase.status==="Rejected"}>Record decision</button>{reviewNotice&&<p className="review-notice" role="status">{reviewNotice}</p>}
          {selectedCase.resolution&&<div className="decision-outcome"><span>Recorded outcome</span><b>{selectedCase.resolution}</b><p>{selectedCase.rationale}</p><small>Retest: {selectedCase.retest}</small></div>}</section>
        </article>
      </section>
      <section className="audit-history"><div><p>Append-only history</p><h2>The decision can be reconstructed.</h2><span>Events are added rather than overwritten, preserving actor, time, transition and rationale.</span></div><ol>{selectedCase.events.map((event,index)=><li key={`${event.at}-${index}`}><span>{String(index+1).padStart(2,"0")}</span><div><b>{event.event}</b><p>{event.note}</p></div><aside><b>{event.actor}</b><span>{event.at}</span></aside></li>)}</ol></section>
    </CasePage>}

    {view==="Evidence search"&&<CasePage eyebrow="Evidence search" title="Ask the indexed evidence, not an improvising chatbot." intro="This recruiter demo searches representative records from the verified corpus and exposes why each result matched.">
      <section className="evidence-search"><label htmlFor="evidence-query">What evidence are you looking for?</label><div><input id="evidence-query" value={query} onChange={event=>setQuery(event.target.value)} onKeyDown={event=>event.key==="Enter"&&runSearch()} placeholder="Try: healthcare furniture in Pakistan"/><button onClick={()=>runSearch()} disabled={searchState.status==="loading"}>{searchState.status==="loading"?"Searching 759 vectors…":"Search evidence"}</button></div><p>This runs cosine similarity against the vectors exported from the verified SQLite evidence index, not a hard-coded result list.</p></section>
      {searchState.status==="idle"&&<section className="query-prompts"><p>Try a demonstration</p><button onClick={()=>runSearch("healthcare furniture in Pakistan")}>Find supporting evidence <span>→</span></button><button onClick={()=>runSearch("nuclear procurement on Mars")}>Trigger an abstention <span>→</span></button></section>}
      {searchState.status==="done"&&searchState.results.length>0&&<section className="search-results"><header><div><b>{searchState.results.length}</b><span>supporting {searchState.results.length===1?"record":"records"}</span></div><p>759-record index · {searchState.latency.toFixed(1)} ms</p></header>{searchState.results.map((result,index)=><article key={result.chunk_id}><span>{String(index+1).padStart(2,"0")}</span><div><p>{result.record_type} · indexed evidence</p><h2>{result.text}</h2><div className="evidence-meta"><b>{result.project_id}</b><span>{result.metadata.country||"Country not published"}</span><span>{result.record_type} ID {result.record_id}</span></div><p className="match-reason">Ranked from the stored 256-dimensional vector; the score is relevance, not factual confidence.</p></div><aside><div className="score"><b>{result.retrieval_score.toFixed(3)}</b><span>cosine similarity</span></div><a href={result.official_url} target="_blank" rel="noreferrer">Open official source ↗</a><a href={`https://projects.worldbank.org/en/projects-operations/project-detail/${result.project_id}`} target="_blank" rel="noreferrer">View project ↗</a></aside></article>)}</section>}
      {(searchState.abstained||searchState.status==="error")&&<section className="abstention"><span>Insufficient evidence</span><h2>The indexed prototype cannot support this query.</h2><p>{searchState.status==="error"?"The verified evidence export could not be loaded. No fallback result was fabricated.":"No indexed vector exceeded the evidence threshold. The system returns nothing rather than composing an unsupported answer."}</p><button onClick={()=>runSearch("healthcare furniture in Pakistan")}>Try a supported query</button></section>}
      <section className="retrieval-method"><div><p>What happens under the hood</p><h2>Transparent retrieval in four steps.</h2></div><ol><li><span>01</span><b>Tokenize</b><p>Normalize query and record text.</p></li><li><span>02</span><b>Vectorize</b><p>Create a reproducible 256-dimensional vector.</p></li><li><span>03</span><b>Filter and rank</b><p>Apply metadata filters and cosine similarity.</p></li><li><span>04</span><b>Cite or abstain</b><p>Return source evidence or explicitly stop.</p></li></ol></section>
    </CasePage>}

    {view==="Methodology"&&<CasePage eyebrow="Methodology" title="Implemented evidence, production boundaries and no inflated claims." intro="The architecture is deliberately modest about what runs today and explicit about what institutional scale would require.">
      <section className="architecture"><div className="section-side"><p>Architecture</p><h2>Raw → standardized → curated → retrievable</h2></div><div className="arch-flow">{["Official APIs","Raw snapshots","Validated SQL","Project features","Evidence index"].map((label,index)=><div key={label}><span>{index+1}</span><b>{label}</b>{index<4&&<i>↓</i>}</div>)}</div></section>
      <section className="implementation-boundary"><div><p>Implemented now</p><ul><li>Python ingestion and validation</li><li>SQLite relational model</li><li>Immutable raw JSON snapshots</li><li>Eight control rules and quarantine</li><li>Analyst decisions and append-only audit events</li><li>Deterministic local vectors</li><li>Metadata-filtered retrieval</li><li>FastAPI service routes</li><li>Unit and rendered-build tests</li></ul></div><div><p>Production extension</p><ul><li>Orchestrated incremental ingestion</li><li>PostgreSQL and Alembic migrations</li><li>Cloud object storage</li><li>Sentence Transformers registry</li><li>pgvector or managed vector store</li><li>Monitoring and schema-drift alerts</li><li>Enterprise identity and role-based approval</li><li>CI/CD and load testing</li></ul></div></section>
      <section className="production-translation"><div className="section-side"><p>Production translation</p><h2>Prototype choices map to enterprise services.</h2><span>The architecture distinguishes what runs now from what scale, governance and reliability would require.</span></div><div>{productionTranslations.map(item=><article key={item.today}><div><span>Implemented</span><b>{item.today}</b></div><i>→</i><div><span>Institutional target</span><b>{item.target}</b><p>{item.reason}</p></div></article>)}</div></section>
      <section className="migration-lifecycle"><div><p>Migration operating model</p><h2>Technology alone does not make a safe cutover.</h2></div><ol>{migrationStages.map(([stage,detail],index)=><li key={stage}><span>{String(index+1).padStart(2,"0")}</span><b>{stage}</b><p>{detail}</p></li>)}</ol></section>
      <section className="uat-evidence"><div><p>UAT and release evidence</p><h2>A decision package, not a ceremonial test.</h2></div><div className="uat-list"><article><b>Representative scenarios</b><p>Create, amend, approve and close procurement records across realistic roles.</p></article><article><b>Reconciliation acceptance</b><p>Counts, keys, totals, relationships and business states meet signed thresholds.</p></article><article><b>Defect governance</b><p>Severity, owner, remediation, retest result and go-live disposition are recorded.</p></article><article><b>Rollback readiness</b><p>Snapshot, final delta, recovery steps and accountable approval remain auditable.</p></article></div></section>
      <section className="test-evidence"><div><p>Verification</p><h2>What the tests actually cover.</h2></div><ul><li><b>Normalization</b><span>Project IDs and supported date formats</span></li><li><b>Idempotence</b><span>Repeated source record does not create a duplicate row</span></li><li><b>Feature generation</b><span>Curated project aggregates are reproducible</span></li><li><b>Retrieval</b><span>Matching, metadata filter and unsupported-query abstention</span></li><li><b>Frontend artifact</b><span>Production compilation and rendered worker response</span></li></ul></section>
      <Boundary/>
    </CasePage>}

    <footer className="case-footer"><div><b>Procurement<br/>Evidence</b><p>Independent AI data-engineering case study using official public World Bank data.</p></div><div><span>Built by Nicolaas Dreandachrista</span><span>Not affiliated with or endorsed by the World Bank Group</span></div></footer>
  </main>
}

function CasePage({eyebrow,title,intro,children}:{eyebrow:string,title:string,intro:string,children:React.ReactNode}){return <><header className="case-page-head"><span className="page-orbit" aria-hidden="true">{eyebrow.slice(0,1)}</span><p>{eyebrow}</p><h1>{title}</h1><div><span>Verified prototype</span><p>{intro}</p></div></header><div className="case-page-body">{children}</div></>}
function Mapping({source,target,rule}:{source:string,target:string,rule:string}){return <div><code>{source}</code><span>→</span><code>{target}</code><p>{rule}</p></div>}
function Boundary(){return <aside className="scope-note"><span>Prototype scope</span><p>Implemented locally with public records. The methodology page maps each working component to its production-scale counterpart.</p></aside>}
