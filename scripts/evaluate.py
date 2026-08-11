import json, statistics, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.pipeline import search

cases=[
 ("Comprehensive Motor Vehicle Insurance Services",{"1894306"},None),
 ("Furniture healthcare Facilities Flood Affected",{"1894368","1894364"},"Pakistan"),
 ("automated weather stations Eastern Province",{"1894200"},"Zambia"),
 ("coffee seedling Batian variety demo farms",{"459853"},None),
 ("Connectivity and Logistics Programme Dominica",{"459857"},None),
]
ps=[];rr=[];cit=[];lat=[];dupes=[];filter_ok=[]
for q,relevant,country in cases:
    r=search(q,country=country,limit=5); ids=[x["record_id"] for x in r["results"]]
    ps.append(len(set(ids)&relevant)/5); rr.append(next((1/(i+1) for i,x in enumerate(ids) if x in relevant),0));cit.append(all(x["official_url"].startswith("https://") for x in r["results"]));lat.append(r["latency_ms"]);dupes.append(len(ids)-len(set(ids)))
    filter_ok.append(all(country.lower() in x["excerpt"].lower() for x in r["results"]) if country and r["results"] else True)
unsupported=search("xylophone nebula quasar")
report={"evaluation_set_size":6,"labeled_retrieval_queries":5,"manual_labels":True,"precision_at_5":round(statistics.mean(ps),3),"mrr":round(statistics.mean(rr),3),"citation_coverage":round(sum(cit)/len(cit),3),"metadata_filter_accuracy":round(sum(filter_ok)/len(filter_ok),3),"mean_latency_ms":round(statistics.mean(lat),2),"zero_result_rate":round((1 if not unsupported["results"] else 0)/6,3),"abstention_behavior_passed":unsupported["abstained"],"duplicate_result_rate":round(sum(dupes)/(5*len(cases)),3),"limitations":"Metrics apply only to a six-query, manually labeled prototype evaluation."}
print(json.dumps(report,indent=2))
