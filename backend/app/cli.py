import argparse, json
from .pipeline import DB, ingest_sample
from .retrieval import PgVectorRetrieval
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    i=sub.add_parser("ingest-sample"); i.add_argument("--notices",type=int,default=300);i.add_argument("--awards",type=int,default=300)
    sub.add_parser("retrieval-migrate")
    index=sub.add_parser("retrieval-index"); index.add_argument("--sqlite",default=str(DB))
    s=sub.add_parser("search");s.add_argument("query");s.add_argument("--country");s.add_argument("--project-id")
    a=p.parse_args()
    if a.cmd=="ingest-sample": print(ingest_sample(a.notices,a.awards))
    elif a.cmd=="retrieval-migrate": PgVectorRetrieval().migrate(); print("Retrieval schema ready")
    elif a.cmd=="retrieval-index": print(json.dumps({"indexed":PgVectorRetrieval().index_sqlite(__import__('pathlib').Path(a.sqlite))}))
    else: print(json.dumps(PgVectorRetrieval().search(a.query,a.country,a.project_id),indent=2))
if __name__=="__main__": main()
