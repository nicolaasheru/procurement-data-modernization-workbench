import sqlite3
from pathlib import Path
from backend.app.pipeline import connect,norm_project,norm_date,vector,build_curated,search
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
