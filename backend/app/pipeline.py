from __future__ import annotations

import hashlib, json, math, re, sqlite3, time, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .mappings import apply_mapping, load_mapping

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "workbench.db"
RAW = ROOT / "data" / "raw"
NOTICE_API = "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"
PROJECT_API = "https://search.worldbank.org/api/v3/projects"
AWARD_API = "https://search.worldbank.org/api/contractdata"

SCHEMA = """
create table if not exists ingestion_runs(run_id text primary key, source text, started_at text, completed_at text, status text, records_read integer, accepted integer, rejected integer, quarantined integer, checksum text, schema_hash text);
create table if not exists projects(project_id text primary key, title text, country text, region text, sector text, total_amount real, official_url text, raw_json text);
create table if not exists procurement_notices(notice_id text primary key, project_id text, title text, country text, country_code text, category text, method text, publication_date text, deadline_date text, sector text, official_url text, raw_json text, quality_score real);
create table if not exists contract_awards(award_id text primary key, project_id text, description text, country text, category text, supplier text, amount real, signed_date text, official_url text, raw_json text);
create table if not exists validation_results(id integer primary key autoincrement, run_id text, control_id text, severity text, result text, record_type text, record_id text, source_field text, original_value text, normalized_value text, recommended_handling text);
create table if not exists rejected_records(id integer primary key autoincrement, run_id text, record_type text, record_id text, reason text, payload text);
create table if not exists procurement_features(project_id text primary key, notice_count integer, award_count integer, supplier_count integer, award_amount real, missing_field_ratio real, linkage_status text, quality_score real);
create table if not exists document_chunks(chunk_id text primary key, record_type text, record_id text, project_id text, text text, official_url text, metadata text, embedding text);
create table if not exists retrieval_runs(run_id text primary key, query text, created_at text, result_count integer, latency_ms real, abstained integer);
create table if not exists review_cases(case_id text primary key, validation_result_id integer not null, status text not null, priority text not null, assigned_to text, created_at text not null, updated_at text not null, resolution text, resolution_rationale text, decided_by text, decided_at text, retest_status text, foreign key(validation_result_id) references validation_results(id));
create table if not exists review_events(event_id text primary key, case_id text not null, event_type text not null, actor text not null, occurred_at text not null, from_status text, to_status text, note text, metadata text, foreign key(case_id) references review_cases(case_id));
create table if not exists mapping_executions(run_id text not null, mapping_id text not null, mapping_version text not null, mapping_hash text not null, executed_at text not null, record_count integer not null, primary key(run_id,mapping_id));
create index if not exists idx_review_cases_status on review_cases(status);
create index if not exists idx_review_events_case on review_events(case_id,occurred_at);
"""

CONTROLS = {
 "DQ-001": ("Missing project identifier", "error", "Quarantine until a valid project ID is available"),
 "DQ-002": ("Invalid project identifier format", "error", "Preserve source value and quarantine"),
 "DQ-003": ("Missing notice title", "error", "Quarantine; do not infer a title"),
 "DQ-004": ("Invalid date format", "error", "Preserve original value and quarantine"),
 "DQ-005": ("Deadline earlier than publication", "warning", "Requires human review"),
 "DQ-006": ("Missing procurement category", "info", "Retain as incomplete metadata"),
 "DQ-007": ("Incomplete project linkage", "warning", "Retain and flag for review"),
 "DQ-008": ("Potential duplicate content", "warning", "Retain canonical record and review duplicates"),
}

def connect(path: Path = DB):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db

def fetch_json(url: str, params: dict, retries: int = 3, timeout: int = 30):
    req = Request(url + "?" + urlencode(params), headers={"User-Agent":"ProcurementModernizationWorkbench/0.1"})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as res: return json.load(res)
        except Exception:
            if attempt == retries - 1: raise
            time.sleep(0.5 * (2 ** attempt))

def norm_project(value):
    v = re.sub(r"\s+", "", str(value or "")).upper()
    return v if re.fullmatch(r"P\d{6}", v) else None

def norm_date(value):
    if not value: return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try: return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError: pass
    return None

def schema_hash(rows):
    keys = sorted({k for r in rows for k in r})
    return hashlib.sha256(json.dumps(keys).encode()).hexdigest()

def record_issue(db, run, control, rtype, rid, field, original, normalized=None):
    name, severity, handling = CONTROLS[control]
    db.execute("insert into validation_results(run_id,control_id,severity,result,record_type,record_id,source_field,original_value,normalized_value,recommended_handling) values(?,?,?,?,?,?,?,?,?,?)",
               (run,control,severity,name,rtype,str(rid),field,str(original),str(normalized or ""),handling))

def ingest_sample(notice_rows=300, award_rows=300, db_path: Path = DB):
    db=connect(db_path); run=str(uuid.uuid4()); started=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    db.execute("insert into ingestion_runs values(?,?,?,?,?,?,?,?,?,?,?)",(run,"official-world-bank-sample",started,None,"running",0,0,0,0,None,None)); db.commit()
    meta=fetch_json(NOTICE_API,{"datasetId":"DS00979","resourceId":"RS00909","top":1,"type":"json"})
    total=int(meta["count"]); skip=max(0,total-notice_rows)
    npayload=fetch_json(NOTICE_API,{"datasetId":"DS00979","resourceId":"RS00909","top":notice_rows,"skip":skip,"type":"json"})
    apayload=fetch_json(AWARD_API,{"format":"json","rows":award_rows,"os":0})
    raw={"retrieved_at":started,"sources":[NOTICE_API,AWARD_API],"notices":npayload,"awards":apayload}
    raw_bytes=json.dumps(raw,ensure_ascii=False,sort_keys=True).encode(); checksum=hashlib.sha256(raw_bytes).hexdigest()
    RAW.mkdir(parents=True,exist_ok=True); (RAW/f"{run}.json").write_bytes(raw_bytes)
    accepted=quarantined=0; project_ids=set(); seen_content=set()
    for r in npayload.get("data",[]):
        rid=str(r.get("id")); pid=norm_project(r.get("project_id")); pub=norm_date(r.get("publication_date")); deadline=norm_date(r.get("deadline_date")); invalid=[]
        if not r.get("project_id"): invalid.append(("DQ-001","project_id"))
        elif not pid: invalid.append(("DQ-002","project_id"))
        if not r.get("bid_description"): invalid.append(("DQ-003","bid_description"))
        if r.get("publication_date") and not pub: invalid.append(("DQ-004","publication_date"))
        if r.get("deadline_date") and not deadline: invalid.append(("DQ-004","deadline_date"))
        if invalid:
            quarantined+=1; db.execute("insert into rejected_records(run_id,record_type,record_id,reason,payload) values(?,?,?,?,?)",(run,"notice",rid,";".join(x[0] for x in invalid),json.dumps(r)))
            for c,f in invalid: record_issue(db,run,c,"notice",rid,f,r.get(f)); continue
        if pub and deadline and deadline < pub: record_issue(db,run,"DQ-005","notice",rid,"deadline_date",r.get("deadline_date"),deadline)
        if not r.get("procurement_category"): record_issue(db,run,"DQ-006","notice",rid,"procurement_category",None)
        content=hashlib.sha256(f"{pid}|{r.get('bid_description')}|{pub}|{deadline}".encode()).hexdigest()
        if content in seen_content: record_issue(db,run,"DQ-008","notice",rid,"bid_description",r.get("bid_description"))
        seen_content.add(content); project_ids.add(pid); missing=sum(not r.get(k) for k in ("project_id","bid_description","country_name","procurement_category","publication_date","deadline_date")); q=round(1-missing/6,3)
        mapped=apply_mapping("procurement_notice",r,context={"computed":{"quality_score":q}}); m=mapped["record"]
        db.execute("insert or replace into procurement_notices values(?,?,?,?,?,?,?,?,?,?,?,?,?)",(m["notice_id"],m["project_id"],m["title"],m["country"],m["country_code"],m["category"],m["method"],m["publication_date"],m["deadline_date"],m["sector"],m["official_url"],m["raw_json"],m["quality_score"])); accepted+=1
    for r in apayload.get("contract",[]):
        pid=norm_project(r.get("projectid")); rid=str(r.get("contr_id"));
        if not pid: quarantined+=1; record_issue(db,run,"DQ-002","award",rid,"projectid",r.get("projectid")); continue
        project_ids.add(pid)
        # The awards feed exposes an award ID but no public award-detail page.
        # Link to the official dataset rather than inventing a notice-style URL.
        url="https://financesone.worldbank.org/contract-awards-in-investment-project-financing-since-fy-2020/DS00005"
        mapped=apply_mapping("contract_award",r,context={"constants":{"official_awards_url":url}}); m=mapped["record"]
        db.execute("insert or replace into contract_awards values(?,?,?,?,?,?,?,?,?,?)",(m["award_id"],m["project_id"],m["description"],m["country"],m["category"],m["supplier"],m["amount"],m["signed_date"],m["official_url"],m["raw_json"])); accepted+=1
        # Awards include official project-level metadata. Materializing it here
        # keeps the bounded run fast; the separately validated Projects API is
        # the production enrichment adapter.
        db.execute("insert or ignore into projects values(?,?,?,?,?,?,?,?)",(pid,r.get("project_name"),r.get("countryshortname"),r.get("regionname"),",".join(r.get("mjsecname") or []),0,f"https://projects.worldbank.org/en/projects-operations/project-detail/{pid}",json.dumps({"source":"contract-awards","project_name":r.get("project_name")})))
    for mapping_id,count in (("procurement_notice",notice_rows),("contract_award",award_rows)):
        mapping=load_mapping(mapping_id)
        db.execute("insert or replace into mapping_executions values(?,?,?,?,?,?)",(run,mapping_id,mapping["version"],mapping["sha256"],utc_now(),count))
    db.commit(); build_curated(db)
    rows=notice_rows+award_rows; completed=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    db.execute("update ingestion_runs set completed_at=?,status='completed',records_read=?,accepted=?,rejected=0,quarantined=?,checksum=?,schema_hash=? where run_id=?",(completed,rows,accepted,quarantined,checksum,schema_hash(npayload.get("data",[])),run)); db.commit(); return run

STOP_WORDS={"and","are","award","bank","contract","data","for","from","in","notice","of","on","project","procurement","record","records","the","to","world"}
def tokenize(text): return re.findall(r"[a-z0-9]{2,}", (text or "").lower())
def distinctive_tokens(text): return {token for token in tokenize(text) if token not in STOP_WORDS}
def vector(text, dims=256):
    v=[0.0]*dims
    for token,count in Counter(tokenize(text)).items():
        # SHA-256 keeps the deterministic local embedding portable. The
        # browser demo uses the identical first-four-byte bucket rule against
        # the exported vectors from this verified SQLite index.
        bucket=int.from_bytes(hashlib.sha256(token.encode()).digest()[:4],"big")%dims
        v[bucket]+=1+math.log(count)
    n=math.sqrt(sum(x*x for x in v)) or 1; return [x/n for x in v]

def build_curated(db):
    db.execute("delete from procurement_features"); db.execute("delete from document_chunks")
    pids={r[0] for r in db.execute("select project_id from projects")}
    allids={r[0] for r in db.execute("select distinct project_id from procurement_notices union select distinct project_id from contract_awards")}
    for pid in allids:
        notices=db.execute("select * from procurement_notices where project_id=?",(pid,)).fetchall(); awards=db.execute("select * from contract_awards where project_id=?",(pid,)).fetchall()
        suppliers={r["supplier"] for r in awards if r["supplier"]}; missing=sum(1-r["quality_score"] for r in notices)/(len(notices) or 1)
        db.execute("insert into procurement_features values(?,?,?,?,?,?,?,?)",(pid,len(notices),len(awards),len(suppliers),sum(r["amount"] for r in awards),round(missing,3),"linked" if pid in pids else "project metadata unavailable",round(sum(r["quality_score"] for r in notices)/(len(notices) or 1),3)))
        if pid not in pids:
            for r in notices[:1]: record_issue(db,"curation","DQ-007","project",pid,"project_id",pid)
    for table,rtype,idcol,textcol in (("procurement_notices","notice","notice_id","title"),("contract_awards","award","award_id","description"),("projects","project","project_id","title")):
        for r in db.execute(f"select * from {table}"):
            text=f"{r[textcol]} {r['country'] if 'country' in r.keys() else ''} {r['sector'] if 'sector' in r.keys() else ''}"
            cid=hashlib.sha256(f"{rtype}:{r[idcol]}".encode()).hexdigest()[:20]
            db.execute("insert or replace into document_chunks values(?,?,?,?,?,?,?,?)",(cid,rtype,str(r[idcol]),r["project_id"],text,r["official_url"],json.dumps({"country":r["country"] if "country" in r.keys() else None}),json.dumps(vector(text))))
    db.commit()

def search(query, country=None, project_id=None, limit=8, db_path: Path=DB):
    started=time.perf_counter(); db=connect(db_path); qv=vector(query); rows=db.execute("select * from document_chunks").fetchall(); out=[]
    for r in rows:
        md=json.loads(r["metadata"])
        if country and country.lower() not in (md.get("country") or "").lower(): continue
        if project_id and r["project_id"] != norm_project(project_id): continue
        if not (distinctive_tokens(query) & distinctive_tokens(r["text"])): continue
        ev=json.loads(r["embedding"]); score=sum(a*b for a,b in zip(qv,ev))
        if score>0: out.append({"record_type":r["record_type"],"record_id":r["record_id"],"project_id":r["project_id"],"excerpt":r["text"][:360],"official_url":r["official_url"],"retrieval_score":round(score,4)})
    out=sorted(out,key=lambda x:x["retrieval_score"],reverse=True)[:limit]; latency=(time.perf_counter()-started)*1000; rid=str(uuid.uuid4()); abstained=not out or out[0]["retrieval_score"]<0.12
    db.execute("insert into retrieval_runs values(?,?,?,?,?,?)",(rid,query,datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),len(out),latency,int(abstained))); db.commit()
    return {"run_id":rid,"query":query,"results":[] if abstained else out,"abstained":abstained,"message":"Insufficient evidence in the indexed prototype scope." if abstained else "Retrieved facts only; relevance score is ranking, not factual confidence.","latency_ms":round(latency,2)}

REVIEW_STATUSES={"open","assigned","in_review","resolved","rejected"}
REVIEW_RESOLUTIONS={"accept_exception","remediate","reject_record"}

def utc_now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def create_review_case(validation_result_id, actor="system", assigned_to=None, priority="medium", db_path: Path=DB):
    db=connect(db_path)
    issue=db.execute("select * from validation_results where id=?",(validation_result_id,)).fetchone()
    if not issue: raise ValueError("Validation result not found")
    existing=db.execute("select case_id from review_cases where validation_result_id=?",(validation_result_id,)).fetchone()
    if existing: return existing[0]
    now=utc_now(); case_id=f"REV-{validation_result_id:05d}"; status="assigned" if assigned_to else "open"
    db.execute("insert into review_cases(case_id,validation_result_id,status,priority,assigned_to,created_at,updated_at) values(?,?,?,?,?,?,?)",(case_id,validation_result_id,status,priority,assigned_to,now,now))
    db.execute("insert into review_events values(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),case_id,"case_created",actor,now,None,status,"Created from validation result",json.dumps({"control_id":issue["control_id"]})))
    if assigned_to:
        db.execute("insert into review_events values(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),case_id,"assigned",actor,now,"open","assigned",f"Assigned to {assigned_to}","{}"))
    db.commit(); return case_id

def update_review_case(case_id, actor, status=None, assigned_to=None, resolution=None, rationale=None, retest_status=None, db_path: Path=DB):
    db=connect(db_path); case=db.execute("select * from review_cases where case_id=?",(case_id,)).fetchone()
    if not case: raise ValueError("Review case not found")
    if status and status not in REVIEW_STATUSES: raise ValueError("Invalid review status")
    if resolution and resolution not in REVIEW_RESOLUTIONS: raise ValueError("Invalid resolution")
    if resolution and case["status"] != "in_review": raise ValueError("Case must be in review before a decision")
    if resolution and not case["assigned_to"]: raise ValueError("An assigned reviewer is required")
    if resolution and len((rationale or "").strip()) < 20: raise ValueError("Resolution rationale must be at least 20 characters")
    next_status=status or case["status"]
    if resolution: next_status="rejected" if resolution=="reject_record" else "resolved"
    now=utc_now(); next_assignee=assigned_to if assigned_to is not None else case["assigned_to"]
    db.execute("update review_cases set status=?,assigned_to=?,updated_at=?,resolution=coalesce(?,resolution),resolution_rationale=coalesce(?,resolution_rationale),decided_by=case when ? is not null then ? else decided_by end,decided_at=case when ? is not null then ? else decided_at end,retest_status=coalesce(?,retest_status) where case_id=?",(next_status,next_assignee,now,resolution,rationale,resolution,actor,resolution,now,retest_status,case_id))
    event_type="decision_recorded" if resolution else "case_updated"
    note=rationale or (f"Assigned to {next_assignee}" if assigned_to is not None else f"Status changed to {next_status}")
    db.execute("insert into review_events values(?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),case_id,event_type,actor,now,case["status"],next_status,note,json.dumps({"resolution":resolution,"retest_status":retest_status})))
    db.commit()

def get_review_case(case_id, db_path: Path=DB):
    db=connect(db_path)
    case=db.execute("select c.*,v.control_id,v.severity,v.result,v.record_type,v.record_id,v.source_field,v.original_value,v.normalized_value,v.recommended_handling,v.run_id from review_cases c join validation_results v on v.id=c.validation_result_id where c.case_id=?",(case_id,)).fetchone()
    if not case: return None
    events=db.execute("select * from review_events where case_id=? order by occurred_at,rowid",(case_id,)).fetchall()
    return {"case":dict(case),"events":[dict(e) for e in events]}
