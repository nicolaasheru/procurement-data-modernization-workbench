import json

import pytest

from backend.app.mappings import load_mapping
from backend.app.pipeline import connect, record_disposition
from backend.app.uat import execute_uat, get_uat_execution, sign_off_uat


def seed_release_evidence(db_path, *, balance_delta=0, target_complete=True):
    db = connect(db_path)
    run_id = "run-uat-1"
    evidence = {
        "run_id": run_id,
        "quarantined": 1,
        "rejected": 0,
        "loaded": 2,
        "balance_delta": balance_delta,
    }
    db.execute(
        "insert into migration_evidence values(?,?,?,?,?,?,?)",
        (run_id, "2026-08-29T00:00:00Z", "balanced" if balance_delta == 0 else "unbalanced", "accepted_with_quarantine", balance_delta, "a" * 64, json.dumps(evidence)),
    )
    for mapping_id in ("procurement_notice", "contract_award"):
        mapping = load_mapping(mapping_id)
        db.execute(
            "insert into mapping_executions values(?,?,?,?,?,?)",
            (run_id, mapping_id, mapping["version"], mapping["sha256"], "2026-08-29T00:00:00Z", 1),
        )
    record_disposition(db, run_id, "notice", "n-1", "quarantined", "DQ-001", {"id": "n-1"})
    if target_complete:
        db.execute("insert into procurement_notices(notice_id,project_id,title,raw_json) values(?,?,?,?)", ("n-2", "P100001", "Notice", "{}"))
        db.execute("insert into contract_awards(award_id,project_id,description,raw_json) values(?,?,?,?)", ("a-1", "P100001", "Award", "{}"))
    db.commit()
    return run_id


def test_uat_execution_records_expected_observed_and_fingerprint(tmp_path):
    db_path = tmp_path / "uat.db"
    run_id = seed_release_evidence(db_path)
    package = execute_uat("Amina Okafor", "release-2026.08", "staging", run_id, db_path)
    execution = package["execution"]
    assert execution["status"] == "passed"
    assert execution["suite_version"] == "1.0.0"
    assert len(execution["evidence_hash"]) == 64
    assert len(package["results"]) == 4
    assert all(result["expected"] and result["observed"] for result in package["results"])
    assert get_uat_execution(execution["execution_id"], db_path) == package


def test_uat_failure_is_persisted_and_cannot_be_signed_off(tmp_path):
    db_path = tmp_path / "uat-failed.db"
    run_id = seed_release_evidence(db_path, balance_delta=2, target_complete=False)
    package = execute_uat("Amina Okafor", "release-2026.08", "staging", run_id, db_path)
    assert package["execution"]["status"] == "failed"
    assert {result["scenario_id"] for result in package["results"] if result["status"] == "failed"} == {"UAT-001", "UAT-004"}
    with pytest.raises(ValueError, match="passing"):
        sign_off_uat(package["execution"]["execution_id"], "Release Owner", "All acceptance evidence has been reviewed.", db_path)


def test_passing_uat_requires_substantive_sign_off(tmp_path):
    db_path = tmp_path / "uat-signoff.db"
    run_id = seed_release_evidence(db_path)
    package = execute_uat("Amina Okafor", "release-2026.08", "production", run_id, db_path)
    execution_id = package["execution"]["execution_id"]
    with pytest.raises(ValueError, match="20 characters"):
        sign_off_uat(execution_id, "Release Owner", "Looks good", db_path)
    signed = sign_off_uat(execution_id, "Release Owner", "All four acceptance scenarios were reviewed and accepted.", db_path)
    assert signed["execution"]["signed_off_by"] == "Release Owner"
    assert signed["execution"]["signed_off_at"]
