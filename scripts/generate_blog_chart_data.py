from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

INPUT = Path("data/processed/echo_stop_the_boats_llm.parquet")
OUTPUT = Path("data/processed/stop_the_boats_chart_data.json")
BLOG_HTML = Path("blog/index.html")

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
    formatted = json.dumps(payload, indent=2)
    OUTPUT.write_text(formatted)

    if BLOG_HTML.exists():
        html = BLOG_HTML.read_text()
        start = '<script id="stop-boats-chart-data" type="application/json">'
        end = "</script>"
        start_index = html.find(start)
        if start_index != -1:
            content_start = start_index + len(start)
            content_end = html.find(end, content_start)
            if content_end == -1:
                raise RuntimeError("Could not find closing script tag for inline chart data")
            html = html[:content_start] + "\n" + formatted + "\n" + html[content_end:]
            BLOG_HTML.write_text(html)


if __name__ == "__main__":
    main()
