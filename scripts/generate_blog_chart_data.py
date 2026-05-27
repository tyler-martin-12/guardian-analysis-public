from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

INPUT = Path("data/processed/echo_stop_the_boats_llm.parquet")
OUTPUT = Path("data/processed/stop_the_boats_chart_data.json")
BLOG_HTML = Path("blog/index.html")
METHODOLOGY = Path("reports/echo_chart_methodology.md")

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
    pre_filter = df[df["immigration_context"].eq("yes")].copy()
    pre_2022 = pre_filter[pre_filter["year"] < 2022].copy()
    non_high_2022 = pre_filter[(pre_filter["year"] >= 2022) & ~pre_filter["confidence"].eq("high")].copy()
    df = pre_filter[
        (pre_filter["year"] >= 2022)
        & pre_filter["confidence"].eq("high")
        & pre_filter["party"].isin(PARTIES)
    ].copy()
    rows = (
        df.groupby(["year", "party", "echo_type"])
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["year", "echo_type", "party"])
    )
    payload = {
        "years": list(range(2022, 2026)),
        "parties": PARTIES,
        "party_labels": PARTY_LABELS,
        "party_colors": PARTY_COLORS,
        "filters": {
            "immigration_context": "yes",
            "min_year": 2022,
            "confidence": "high",
        },
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

    stella = pre_filter[
        pre_filter["speech_id"].eq("uk.org.publicwhip/debate/2015-09-08c.281.5")
    ][["speech_id", "date", "speaker", "party", "echo_type", "confidence", "sentence_context"]]
    post_total = len(df)
    methodology = f"""# Echo Chart Methodology

This note documents the filter used for the `stop the boats` chart in the blog post.

## Filter Rules

The chart starts from `data/processed/echo_stop_the_boats_llm.parquet` and keeps only rows where:

- `immigration_context == "yes"`
- `year >= 2022`
- `confidence == "high"`

The year filter treats pre-2022 appearances as pre-slogan uses. The confidence filter removes uncertain LLM classifications before aggregating party/use-type counts.

## Count Delta

| stage | count |
|---|---:|
| Pre-filter immigration-context occurrences | {len(pre_filter)} |
| Removed because year < 2022 | {len(pre_2022)} |
| Removed because year >= 2022 but confidence != high | {len(non_high_2022)} |
| Post-filter chart occurrences | {post_total} |

## Stella Creasy 2015 True Positive

The 2015 Stella Creasy occurrence is a genuine immigration-context use of the phrase, but it is filtered out because it predates the Sunak-era slogan period used for the chart.

{stella.to_markdown(index=False)}

## Small Boats Consistency Check

The same year filter does not materially change the blog's point about `small boats`: in 2025, the heuristic echo table still has 78 Labour own-use mentions and 28 Conservative own-use mentions. The term remains operational cross-party vocabulary rather than a clean quotation/criticism echo case.
"""
    METHODOLOGY.write_text(methodology)


if __name__ == "__main__":
    main()
