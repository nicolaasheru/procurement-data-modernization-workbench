"""Export non-sensitive aggregate geography counts for the frontend map."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data"/"workbench.db"
OUTPUT=ROOT/"public"/"data"/"geography-counts.json"

def main():
    db=sqlite3.connect(DB)
    countries=Counter()
    for (metadata,) in db.execute("select metadata from document_chunks"):
        country=(json.loads(metadata or "{}").get("country") or "").strip()
        if country: countries[country]+=1
    payload={"source":"aggregated curated record metadata","count":sum(countries.values()),"countries":dict(sorted(countries.items()))}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8")
    print(f"exported aggregate geography for {payload['count']} records to {OUTPUT}")

if __name__=="__main__": main()
