from pathlib import Path
import sqlite3
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from .pipeline import DB, CONTROLS, connect, ingest_sample, search, create_review_case, update_review_case, get_review_case

app=FastAPI(title="Procurement Data Modernization Workbench API",version="0.1.0")
class SearchRequest(BaseModel):
    query: str = Field(min_length=3,max_length=500)
    country: Optional[str]=None
    project_id: Optional[str]=None
    limit: int=Field(default=8,ge=1,le=25)
class ReviewCreate(BaseModel):
    validation_result_id:int
    actor:str=Field(min_length=2,max_length=100)
    assigned_to:Optional[str]=Field(default=None,max_length=100)
    priority:str=Field(default="medium",pattern="^(low|medium|high|critical)$")
class ReviewUpdate(BaseModel):
    actor:str=Field(min_length=2,max_length=100)
    status:Optional[str]=None
    assigned_to:Optional[str]=Field(default=None,max_length=100)
    resolution:Optional[str]=None
    rationale:Optional[str]=Field(default=None,min_length=20,max_length=2000)
    retest_status:Optional[str]=Field(default=None,pattern="^(pending|passed|failed|not_required)$")

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
@app.get("/reviews")
def reviews(status:Optional[str]=None,limit:int=Query(50,ge=1,le=200)):
    where=" where c.status=?" if status else ""; args=(status,limit) if status else (limit,)
    return rows(f"select c.*,v.control_id,v.severity,v.result,v.record_type,v.record_id from review_cases c join validation_results v on v.id=c.validation_result_id{where} order by c.updated_at desc limit ?",args)
@app.post("/reviews",status_code=201)
def open_review(req:ReviewCreate):
    try: case_id=create_review_case(req.validation_result_id,req.actor,req.assigned_to,req.priority)
    except ValueError as exc: raise HTTPException(404,str(exc))
    return get_review_case(case_id)
@app.get("/reviews/{case_id}")
def review(case_id:str):
    result=get_review_case(case_id)
    if not result: raise HTTPException(404,"Review case not found")
    return result
@app.patch("/reviews/{case_id}")
def revise_review(case_id:str,req:ReviewUpdate):
    try: update_review_case(case_id,req.actor,req.status,req.assigned_to,req.resolution,req.rationale,req.retest_status)
    except ValueError as exc: raise HTTPException(400,str(exc))
    return get_review_case(case_id)
