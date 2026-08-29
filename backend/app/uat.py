from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .pipeline import DB, connect, utc_now

SUITE_VERSION = "1.0.0"
SCENARIOS = [
    {"id": "UAT-001", "title": "Reconciled record population", "expected": "Every source record is loaded, quarantined or rejected with a zero balance delta."},
    {"id": "UAT-002", "title": "Versioned transformation contracts", "expected": "Both mapping executions retain a version and SHA-256 contract fingerprint."},
    {"id": "UAT-003", "title": "Excluded-record traceability", "expected": "Quarantine and rejection totals equal their record-level disposition evidence."},
    {"id": "UAT-004", "title": "Trusted records are queryable", "expected": "The accepted notice and award population is available in the curated target tables."},
]


def _latest_run(db):
    row = db.execute(
        "select run_id from migration_evidence order by generated_at desc limit 1"
    ).fetchone()
    return row["run_id"] if row else None


def _result(scenario, passed, observed, evidence):
    return {
        "scenario_id": scenario["id"],
        "title": scenario["title"],
        "status": "passed" if passed else "failed",
        "expected": scenario["expected"],
        "observed": observed,
        "evidence": evidence,
    }


def execute_uat(tester: str, release_id: str, environment: str = "production", run_id: str | None = None, db_path: Path = DB):
    tester = tester.strip()
    release_id = release_id.strip()
    environment = environment.strip()
    if len(tester) < 2:
        raise ValueError("Tester name must contain at least 2 characters")
    if len(release_id) < 2:
        raise ValueError("Release ID must contain at least 2 characters")
    if environment not in {"development", "staging", "production"}:
        raise ValueError("Environment must be development, staging or production")

    db = connect(db_path)
    run_id = run_id or _latest_run(db)
    if not run_id:
        raise ValueError("No migration evidence is available for UAT")
    migration = db.execute(
        "select * from migration_evidence where run_id=?", (run_id,)
    ).fetchone()
    if not migration:
        raise ValueError("Migration run was not found")

    results = []
    scenario = SCENARIOS[0]
    passed = migration["reconciliation_status"] == "balanced" and migration["balance_delta"] == 0
    results.append(_result(
        scenario,
        passed,
        f"Reconciliation {migration['reconciliation_status']}; balance delta {migration['balance_delta']}.",
        {"run_id": run_id, "migration_evidence_hash": migration["evidence_hash"], "balance_delta": migration["balance_delta"]},
    ))

    scenario = SCENARIOS[1]
    mappings = [dict(row) for row in db.execute(
        "select mapping_id,mapping_version,mapping_hash,record_count from mapping_executions where run_id=? order by mapping_id", (run_id,)
    )]
    passed = len(mappings) == 2 and all(item["mapping_version"] and len(item["mapping_hash"]) == 64 for item in mappings)
    results.append(_result(
        scenario,
        passed,
        f"{len(mappings)} mapping contracts recorded; {sum(item['record_count'] for item in mappings)} records transformed.",
        {"run_id": run_id, "mappings": mappings},
    ))

    scenario = SCENARIOS[2]
    migration_json = json.loads(migration["evidence_json"])
    expected_counts = {key: int(migration_json.get(key, 0)) for key in ("quarantined", "rejected")}
    actual_counts = {row["disposition"]: row["count"] for row in db.execute(
        "select disposition,count(*) count from record_dispositions where run_id=? group by disposition", (run_id,)
    )}
    actual_counts = {key: int(actual_counts.get(key, 0)) for key in ("quarantined", "rejected")}
    passed = actual_counts == expected_counts
    results.append(_result(
        scenario,
        passed,
        f"Expected {expected_counts['quarantined']} quarantined and {expected_counts['rejected']} rejected; found {actual_counts['quarantined']} and {actual_counts['rejected']} disposition records.",
        {"run_id": run_id, "expected_counts": expected_counts, "record_level_counts": actual_counts},
    ))

    scenario = SCENARIOS[3]
    loaded_expected = int(migration_json.get("loaded", sum(item["record_count"] for item in mappings)))
    notice_count = db.execute("select count(*) count from procurement_notices").fetchone()["count"]
    award_count = db.execute("select count(*) count from contract_awards").fetchone()["count"]
    queryable = notice_count + award_count
    passed = loaded_expected > 0 and queryable >= loaded_expected
    results.append(_result(
        scenario,
        passed,
        f"{queryable} curated records are queryable for {loaded_expected} accepted records in this bounded run.",
        {"expected_loaded": loaded_expected, "queryable_notices": notice_count, "queryable_awards": award_count},
    ))

    now = utc_now()
    execution_id = f"UAT-{uuid.uuid4().hex[:12].upper()}"
    status = "passed" if all(item["status"] == "passed" for item in results) else "failed"
    canonical = json.dumps({"execution_id": execution_id, "release_id": release_id, "run_id": run_id, "suite_version": SUITE_VERSION, "results": results}, sort_keys=True, separators=(",", ":"))
    evidence_hash = hashlib.sha256(canonical.encode()).hexdigest()
    db.execute(
        "insert into uat_executions(execution_id,release_id,run_id,environment,tester,started_at,completed_at,status,suite_version,evidence_hash) values(?,?,?,?,?,?,?,?,?,?)",
        (execution_id, release_id, run_id, environment, tester, now, now, status, SUITE_VERSION, evidence_hash),
    )
    for item in results:
        db.execute(
            "insert into uat_results values(?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), execution_id, item["scenario_id"], item["title"], item["status"], item["expected"], item["observed"], json.dumps(item["evidence"], sort_keys=True), now),
        )
    db.commit()
    return get_uat_execution(execution_id, db_path)


def get_uat_execution(execution_id: str, db_path: Path = DB):
    db = connect(db_path)
    execution = db.execute("select * from uat_executions where execution_id=?", (execution_id,)).fetchone()
    if not execution:
        return None
    results = []
    for row in db.execute("select * from uat_results where execution_id=? order by scenario_id", (execution_id,)):
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json"))
        results.append(item)
    return {"execution": dict(execution), "results": results}


def list_uat_executions(limit: int = 20, db_path: Path = DB):
    db = connect(db_path)
    return [dict(row) for row in db.execute("select * from uat_executions order by completed_at desc limit ?", (limit,))]


def sign_off_uat(execution_id: str, approver: str, note: str, db_path: Path = DB):
    approver, note = approver.strip(), note.strip()
    if len(approver) < 2:
        raise ValueError("Approver name must contain at least 2 characters")
    if len(note) < 20:
        raise ValueError("Sign-off note must contain at least 20 characters")
    db = connect(db_path)
    execution = db.execute("select * from uat_executions where execution_id=?", (execution_id,)).fetchone()
    if not execution:
        raise ValueError("UAT execution was not found")
    if execution["status"] != "passed":
        raise ValueError("Only a passing UAT execution can be signed off")
    if execution["signed_off_at"]:
        raise ValueError("UAT execution is already signed off")
    db.execute("update uat_executions set signed_off_by=?,signed_off_at=?,sign_off_note=? where execution_id=?", (approver, utc_now(), note, execution_id))
    db.commit()
    return get_uat_execution(execution_id, db_path)
