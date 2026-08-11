from pathlib import Path
import sqlite3
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from .pipeline import DB, CONTROLS, connect, ingest_sample, search

app=FastAPI(title="Procurement Data Modernization Workbench API",version="0.1.0")
class SearchRequest(BaseModel):
    query: str = Field(min_length=3,max_length=500)
    country: Optional[str]=None
    project_id: Optional[str]=None
    limit: int=Field(default=8,ge=1,le=25)

def rows(sql,args=()): return [dict(r) for r in connect().execute(sql,args).fetchall()]
@app.get("/health")
def health(): return {"status":"ok","database":DB.exists(),"mode":"deterministic-retrieval"}
@app.get("/ingestion/runs")
def runs(limit:int=Query(20,ge=1,le=100)): return rows("select * from ingestion_runs order by started_at desc limit ?",(limit,))
@app.get("/quality/summary")
def quality(): return {"issues":rows("select control_id,severity,result,count(*) affected from validation_results group by control_id,severity,result order by control_id"),"catalog":[{"control_id":k,"name":v[0],"severity":v[1],"recommended_handling":v[2]} for k,v in CONTROLS.items()]}
@app.get("/quality/issues")
def issues(limit:int=Query(100,ge=1,le=500)): return rows("select * from validation_results order by id desc limit ?",(limit,))
@app.get("/projects")
def projects(limit:int=Query(50,ge=1,le=200)): return rows("select p.*,f.notice_count,f.award_count,f.award_amount,f.linkage_status,f.quality_score from projects p left join procurement_features f using(project_id) limit ?",(limit,))
@app.get("/projects/{project_id}")
def project(project_id:str):
    p=rows("select * from projects where project_id=?",(project_id.upper(),))
    if not p: raise HTTPException(404,"Project not found in prototype scope")
    return {"project":p[0],"notices":rows("select * from procurement_notices where project_id=?",(project_id.upper(),)),"awards":rows("select * from contract_awards where project_id=?",(project_id.upper(),)),"features":rows("select * from procurement_features where project_id=?",(project_id.upper(),))}
@app.get("/procurement/notices")
def notices(country:Optional[str]=None,project_id:Optional[str]=None,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):
    clauses=[]; args=[]
    if country: clauses.append("country like ?");args.append(f"%{country}%")
    if project_id: clauses.append("project_id=?");args.append(project_id.upper())
    where=" where "+" and ".join(clauses) if clauses else ""; args += [limit,offset]
    return rows(f"select * from procurement_notices{where} order by publication_date desc limit ? offset ?",args)
@app.post("/procurement/search")
def retrieval(req:SearchRequest): return search(req.query,req.country,req.project_id,req.limit)
@app.post("/ingestion/sample",status_code=202)
def ingestion(notices:int=Query(300,ge=10,le=1000),awards:int=Query(300,ge=10,le=1000)): return {"run_id":ingest_sample(notices,awards),"status":"completed"}
