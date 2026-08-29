import sqlite3
import json
import pytest
from pathlib import Path
import backend.app.pipeline as pipeline
from backend.app.pipeline import connect,norm_project,norm_date,vector,build_curated,search,create_review_case,update_review_case,get_review_case,record_disposition,create_migration_evidence,get_migration_evidence,ingest_sample
from backend.app.mappings import MappingError, apply_mapping, list_mappings, load_mapping

def notice(record_id="n-1",project_id="P100001",**overrides):
    row={"id":record_id,"project_id":project_id,"bid_description":"Supply digital equipment","country_name":"Madagascar","country_code":"mg","procurement_category":"Goods","procurement_method":"RFQ","publication_date":"2026-08-10","deadline_date":"2026-08-20","sector":"Technology","url":"https://example.org/notice"}
    row.update(overrides); return row

def award(record_id="a-1",project_id="P200002",**overrides):
    row={"contr_id":record_id,"projectid":project_id,"contr_desc":"Implementation services","countryshortname":"Madagascar","procurement_group_desc":"Consulting","supp_name":["Supplier A"],"total_contr_amnt":"125000","contr_sgn_date":"2026-08-12","project_name":"Digital Government","regionname":"Africa","mjsecname":["Technology"]}
    row.update(overrides); return row

def fake_fetcher(notices,awards):
    calls={"count":0}
    def fetch(url,params):
        calls["count"]+=1
        if calls["count"]==1: return {"count":len(notices)}
        if url==pipeline.NOTICE_API: return {"data":notices}
        return {"contract":awards}
    return fetch
def test_normalization():
    assert norm_project(" p123456 ")=="P123456" and norm_project("123") is None
    assert norm_date("05-Aug-2026")=="2026-08-05" and norm_date("nope") is None
def test_idempotent_upsert_and_features(tmp_path):
    dbp=tmp_path/"t.db"; db=connect(dbp)
    row=("1","P123456","Digital system","Indonesia","ID","Consulting","QCBS","2026-08-01","2026-08-20","Technology","https://example.org",'{}',1.0)
    db.execute("insert or replace into procurement_notices values(?,?,?,?,?,?,?,?,?,?,?,?,?)",row);db.execute("insert or replace into procurement_notices values(?,?,?,?,?,?,?,?,?,?,?,?,?)",row);db.commit();build_curated(db)
    assert db.execute("select count(*) from procurement_notices").fetchone()[0]==1
    assert db.execute("select notice_count from procurement_features").fetchone()[0]==1
def test_retrieval_and_abstention(tmp_path):
    dbp=tmp_path/"t.db";db=connect(dbp);txt="digital infrastructure information systems Indonesia"
    db.execute("insert into document_chunks values(?,?,?,?,?,?,?,?)",("c","notice","1","P123456",txt,"https://example.org",'{"country":"Indonesia"}',__import__('json').dumps(vector(txt))));db.commit()
    assert search("digital infrastructure",country="Indonesia",db_path=dbp)["results"]
    assert search("xylophone nebula",db_path=dbp)["abstained"]
    assert search("nuclear procurement on Mars",db_path=dbp)["abstained"]
def test_review_decision_creates_immutable_audit_events(tmp_path):
    dbp=tmp_path/"t.db";db=connect(dbp)
    db.execute("insert into validation_results(run_id,control_id,severity,result,record_type,record_id,source_field,original_value,normalized_value,recommended_handling) values(?,?,?,?,?,?,?,?,?,?)",("run-1","DQ-008","warning","Potential duplicate content","notice","459873","bid_description","Software","","Compare official sources"));db.commit()
    issue_id=db.execute("select id from validation_results").fetchone()[0]
    case_id=create_review_case(issue_id,"pipeline","Amina Okafor","high",dbp)
    update_review_case(case_id,"Amina Okafor",status="in_review",db_path=dbp)
    update_review_case(case_id,"Amina Okafor",resolution="accept_exception",rationale="Distinct official notice IDs; retain both records.",retest_status="not_required",db_path=dbp)
    result=get_review_case(case_id,dbp)
    assert result["case"]["status"]=="resolved"
    assert result["case"]["resolution"]=="accept_exception"
    assert [event["event_type"] for event in result["events"]]==["case_created","assigned","case_updated","decision_recorded"]

def test_review_decision_enforces_state_and_rationale(tmp_path):
    dbp=tmp_path/"t.db";db=connect(dbp)
    db.execute("insert into validation_results(run_id,control_id,severity,result,record_type,record_id,source_field,original_value,normalized_value,recommended_handling) values(?,?,?,?,?,?,?,?,?,?)",("run-1","DQ-008","warning","Potential duplicate content","notice","459873","bid_description","Software","","Compare official sources"));db.commit()
    issue_id=db.execute("select id from validation_results").fetchone()[0]
    case_id=create_review_case(issue_id,"pipeline","Amina Okafor","high",dbp)
    with pytest.raises(ValueError, match="must be in review"):
        update_review_case(case_id,"Amina Okafor",resolution="accept_exception",rationale="This rationale is long enough to pass.",db_path=dbp)
    update_review_case(case_id,"Amina Okafor",status="in_review",db_path=dbp)
    with pytest.raises(ValueError, match="at least 20"):
        update_review_case(case_id,"Amina Okafor",resolution="accept_exception",rationale="Too short",db_path=dbp)
    result=get_review_case(case_id,dbp)
    assert result["case"]["status"]=="in_review"
    assert [event["event_type"] for event in result["events"]]==["case_created","assigned","case_updated"]

def test_versioned_mapping_registry_and_hashes_are_stable():
    mappings={item["mapping_id"]:item for item in list_mappings()}
    assert mappings["procurement_notice"]["active_version"]=="1.1.0"
    assert mappings["procurement_notice"]["available_versions"]==["1.0.0","1.1.0"]
    assert len(mappings["procurement_notice"]["sha256"])==64
    assert load_mapping("procurement_notice")["sha256"]==load_mapping("procurement_notice","1.1.0")["sha256"]
    assert load_mapping("procurement_notice","1.0.0")["sha256"]!=load_mapping("procurement_notice","1.1.0")["sha256"]

def test_mapping_execution_returns_target_and_field_lineage():
    source={"id":459873,"project_id":" p506439 ","bid_description":" Software ","country_name":"Madagascar","country_code":"mg","procurement_category":"Goods","procurement_method":"RFQ","publication_date":"05-Aug-2026","deadline_date":"2026-08-20","sector":"Technology","url":"https://example.org"}
    result=apply_mapping("procurement_notice",source,context={"computed":{"quality_score":1}})
    record=result["record"]
    assert record["notice_id"]=="459873"
    assert record["project_id"]=="P506439"
    assert record["country_code"]=="MG"
    assert record["publication_date"]=="2026-08-05"
    assert record["quality_score"]==1.0
    assert result["mapping_version"]=="1.1.0"
    assert {item["target"] for item in result["lineage"]}==set(record)

def test_reconciliation_accounts_for_loaded_quarantined_and_rejected_records(tmp_path):
    dbp=tmp_path/"t.db"; db=connect(dbp)
    db.execute("insert into ingestion_runs values(?,?,?,?,?,?,?,?,?,?,?)",("run-1","test","2026-01-01", "2026-01-01","completed",5,3,1,1,"checksum","schema"))
    for mapping_id in ("procurement_notice","contract_award"):
        mapping=load_mapping(mapping_id)
        db.execute("insert into mapping_executions values(?,?,?,?,?,?)",("run-1",mapping_id,mapping["version"],mapping["sha256"],"2026-01-01",1))
    record_disposition(db,"run-1","notice","n-1","quarantined","DQ-001",{"id":"n-1"})
    record_disposition(db,"run-1","award","a-1","rejected","mapping_error",{"id":"a-1"})
    db.commit()
    evidence=create_migration_evidence(db,"run-1",{"procurement_notices":3,"contract_awards":2},{"procurement_notices":2,"contract_awards":1})
    assert evidence["records_read"]==evidence["loaded"]+evidence["quarantined"]+evidence["rejected"]
    assert evidence["balance_delta"]==0
    assert evidence["reconciliation_status"]=="balanced"
    assert evidence["acceptance_status"]=="blocked"
    assert len(evidence["evidence_hash"])==64
    assert get_migration_evidence("run-1",dbp)["gates"][0]["passed"] is True

def test_ingestion_exercises_every_control_and_preserves_quarantine_evidence(tmp_path):
    dbp=tmp_path/"controls.db"
    duplicate_a=notice("n-1",deadline_date="2026-08-01",procurement_category=None)
    duplicate_b=notice("n-2",deadline_date="2026-08-01",procurement_category=None)
    missing=notice("n-3",project_id=None,bid_description=None,publication_date="not-a-date",deadline_date="also-bad")
    malformed=notice("n-4",project_id="12")
    records=[duplicate_a,duplicate_b,missing,malformed]
    run=ingest_sample(4,2,dbp,fake_fetcher(records,[award(),award("a-2","bad")]),tmp_path/"raw")
    db=connect(dbp); summary=dict(db.execute("select * from ingestion_runs where run_id=?",(run,)).fetchone())
    assert summary["status"]=="completed"
    assert summary["records_read"]==6
    assert summary["records_read"]==summary["accepted"]+summary["quarantined"]+summary["rejected"]
    assert (summary["accepted"],summary["quarantined"],summary["rejected"])==(3,3,0)
    observed={row[0] for row in db.execute("select distinct control_id from validation_results")}
    assert observed==set(pipeline.CONTROLS)
    quarantined=db.execute("select record_type,record_id,disposition,reason,payload from record_dispositions where run_id=? order by record_type,record_id",(run,)).fetchall()
    assert len(quarantined)==3 and {row["disposition"] for row in quarantined}=={"quarantined"}
    assert all(json.loads(row["payload"]) for row in quarantined)
    evidence=get_migration_evidence(run,dbp)
    assert evidence["reconciliation_status"]=="balanced"
    assert evidence["acceptance_status"]=="accepted_with_quarantine"
    assert all(gate["passed"] for gate in evidence["gates"])
    assert (tmp_path/"raw"/f"{run}.json").exists()

def test_repeated_ingestion_is_idempotent_for_target_and_curated_tables(tmp_path):
    dbp=tmp_path/"idempotent.db"; records=[notice()]; awards=[award()]
    first=ingest_sample(1,1,dbp,fake_fetcher(records,awards),tmp_path/"raw")
    second=ingest_sample(1,1,dbp,fake_fetcher(records,awards),tmp_path/"raw")
    db=connect(dbp)
    assert first!=second
    assert db.execute("select count(*) from ingestion_runs").fetchone()[0]==2
    assert db.execute("select count(*) from procurement_notices").fetchone()[0]==1
    assert db.execute("select count(*) from contract_awards").fetchone()[0]==1
    assert db.execute("select count(*) from projects").fetchone()[0]==1
    assert db.execute("select count(*) from procurement_features").fetchone()[0]==2
    assert db.execute("select count(*) from mapping_executions").fetchone()[0]==4
    assert db.execute("select count(*) from migration_evidence").fetchone()[0]==2

def test_mapping_failure_is_rejected_traceable_and_blocks_acceptance(tmp_path,monkeypatch):
    dbp=tmp_path/"mapping-failure.db"; real_apply=pipeline.apply_mapping
    def fail_notice(mapping_id,*args,**kwargs):
        if mapping_id=="procurement_notice": raise MappingError("forced transformation failure")
        return real_apply(mapping_id,*args,**kwargs)
    monkeypatch.setattr(pipeline,"apply_mapping",fail_notice)
    run=ingest_sample(1,1,dbp,fake_fetcher([notice()],[award()]),tmp_path/"raw")
    db=connect(dbp); summary=db.execute("select * from ingestion_runs where run_id=?",(run,)).fetchone()
    assert (summary["records_read"],summary["accepted"],summary["quarantined"],summary["rejected"])==(2,1,0,1)
    disposition=db.execute("select * from record_dispositions where run_id=?",(run,)).fetchone()
    assert disposition["disposition"]=="rejected" and disposition["reason"].startswith("mapping_error")
    evidence=get_migration_evidence(run,dbp)
    assert evidence["balance_delta"]==0 and evidence["acceptance_status"]=="blocked"
    assert next(g for g in evidence["gates"] if g["id"]=="ERR-001")["passed"] is False

def test_source_failure_closes_run_as_failed_and_reraises(tmp_path):
    dbp=tmp_path/"source-failure.db"
    def unavailable(url,params): raise TimeoutError("source unavailable")
    with pytest.raises(TimeoutError,match="source unavailable"):
        ingest_sample(1,1,dbp,unavailable,tmp_path/"raw")
    run=connect(dbp).execute("select * from ingestion_runs").fetchone()
    assert run["status"]=="failed_source" and run["completed_at"]
    assert run["records_read"]==run["accepted"]==run["rejected"]==run["quarantined"]==0

def test_required_mapping_fields_and_unknown_versions_fail_closed():
    with pytest.raises(MappingError,match="Required target field"):
        apply_mapping("procurement_notice",notice(record_id=None),context={"computed":{"quality_score":1}})
    with pytest.raises(MappingError,match="Unknown mapping version"):
        load_mapping("procurement_notice","9.9.9")
    with pytest.raises(MappingError,match="Unknown mapping"):
        load_mapping("not_registered")

def test_evidence_detects_unbalanced_and_incomplete_control_totals(tmp_path):
    dbp=tmp_path/"unbalanced.db"; db=connect(dbp)
    db.execute("insert into ingestion_runs values(?,?,?,?,?,?,?,?,?,?,?)",("run-x","test","now","now","failed_accounting",4,2,0,0,"checksum","schema")); db.commit()
    evidence=create_migration_evidence(db,"run-x",{"procurement_notices":4},{"procurement_notices":2})
    assert evidence["reconciliation_status"]=="unbalanced"
    assert evidence["balance_delta"]==2
    assert evidence["acceptance_status"]=="blocked"
    failed={gate["id"] for gate in evidence["gates"] if not gate["passed"]}
    assert {"REC-001","MAP-001"}.issubset(failed)

def test_source_fetch_retries_transient_failures_then_succeeds(monkeypatch):
    attempts={"count":0}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"count": 7}'
    def flaky(*args,**kwargs):
        attempts["count"]+=1
        if attempts["count"]<3: raise TimeoutError("temporary")
        return Response()
    monkeypatch.setattr(pipeline,"urlopen",flaky)
    monkeypatch.setattr(pipeline.time,"sleep",lambda *_: None)
    assert pipeline.fetch_json("https://example.org",{},retries=3)=={"count":7}
    assert attempts["count"]==3

def test_source_fetch_exhaustion_raises_original_failure(monkeypatch):
    attempts={"count":0}
    def unavailable(*args,**kwargs):
        attempts["count"]+=1; raise ConnectionError("offline")
    monkeypatch.setattr(pipeline,"urlopen",unavailable)
    monkeypatch.setattr(pipeline.time,"sleep",lambda *_: None)
    with pytest.raises(ConnectionError,match="offline"):
        pipeline.fetch_json("https://example.org",{},retries=3)
    assert attempts["count"]==3
