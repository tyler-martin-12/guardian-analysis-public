from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "reports"

for path in (RAW, CACHE, PROCESSED, REPORTS):
    path.mkdir(parents=True, exist_ok=True)

