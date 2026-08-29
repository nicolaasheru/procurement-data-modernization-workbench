import sqlite3
import pytest
from pathlib import Path
from backend.app.pipeline import connect,norm_project,norm_date,vector,build_curated,search,create_review_case,update_review_case,get_review_case
from backend.app.mappings import apply_mapping, list_mappings, load_mapping
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
