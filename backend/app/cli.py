import argparse, json
from .pipeline import ingest_sample, search
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    i=sub.add_parser("ingest-sample"); i.add_argument("--notices",type=int,default=300);i.add_argument("--awards",type=int,default=300)
    s=sub.add_parser("search");s.add_argument("query");s.add_argument("--country");s.add_argument("--project-id")
    a=p.parse_args()
    print(ingest_sample(a.notices,a.awards) if a.cmd=="ingest-sample" else json.dumps(search(a.query,a.country,a.project_id),indent=2))
if __name__=="__main__": main()

