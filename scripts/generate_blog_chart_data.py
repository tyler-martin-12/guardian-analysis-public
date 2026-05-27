from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

INPUT = Path("data/processed/echo_stop_the_boats_llm.parquet")
OUTPUT = Path("data/processed/stop_the_boats_chart_data.json")

PARTIES = [
    "conservative",
    "labour",
    "scottish-national-party",
    "liberal-democrat",
    "labourco-operative",
    "reform",
    "independent",
]

PARTY_LABELS = {
    "conservative": "Conservative",
    "labour": "Labour",
    "scottish-national-party": "SNP",
    "liberal-democrat": "Liberal Democrat",
    "labourco-operative": "Labour/Co-op",
    "reform": "Reform",
    "independent": "Independent",
}

PARTY_COLORS = {
    "conservative": "#0087dc",
    "labour": "#e4003b",
    "scottish-national-party": "#fdf38e",
    "liberal-democrat": "#faa61a",
    "labourco-operative": "#722f37",
    "reform": "#12b6cf",
    "independent": "#7f7f7f",
}


def main() -> None:
    df = pd.read_parquet(INPUT)
    df = df[df["immigration_context"].eq("yes") & df["party"].isin(PARTIES)].copy()
    rows = (
        df.groupby(["year", "party", "echo_type"])
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["year", "echo_type", "party"])
    )
    payload = {
        "years": list(range(2015, 2026)),
        "parties": PARTIES,
        "party_labels": PARTY_LABELS,
        "party_colors": PARTY_COLORS,
        "rows": rows.to_dict(orient="records"),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
