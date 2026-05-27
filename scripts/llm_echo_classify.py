from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.llm_probe import SONNET, cached_call, load_api_key, parse_json
from scripts.paths import PROCESSED, REPORTS


PROMPT_TEMPLATE = """You are classifying UK Parliament Hansard excerpts for a rhetorical-echo analysis.

For each excerpt, decide two things:

1. immigration_context
Whether the matched term is being used in an immigration/asylum/refugee/border-control context.

Labels:
- yes: the passage is about immigration, asylum, refugees, migrants, border control, Channel crossings, deportation, removals, trafficking/smuggling in a migration context, or related Home Office migration policy.
- no: the passage uses the term in another context, such as fishing boats, military invasion, public services being swamped, generic metaphor, Covid, Ukraine, defence, etc.
- unclear: the passage is too ambiguous to decide from the provided context.

2. echo_type
Whether the speaker is using the matched term as their own framing, or quoting/referring to/criticising someone else's wording or slogan.

Labels:
- own_voice: the speaker appears to be using the term directly as their own description/framing.
- quoted_or_critical: the speaker is quoting, paraphrasing, naming, distancing from, criticising, or discussing someone else's phrase, slogan, or rhetoric.
- unclear: not enough context to distinguish.

Important guidance:
- Quotation marks are evidence for quoted_or_critical, but not required.
- Phrases like "the Prime Minister's slogan", "the Home Secretary called it", "the language of", "rhetoric of", "so-called", "vile language", "dehumanising language", or explicit criticism of wording should usually be quoted_or_critical.
- A speaker can mention a slogan without endorsing it; classify that as quoted_or_critical if they are referring to the slogan as a slogan.
- If a minister or MP repeats a policy slogan approvingly or uses it as a direct policy frame, classify as own_voice.
- For "small boats", distinguish literal fishing/maritime uses from immigration Channel-crossing uses.
- For "invasion", distinguish military/geopolitical invasion from migration rhetoric.
- For "swamped", distinguish general overload metaphors from immigration-related uses.

Return JSON only as a list of objects, one per input item:
[
  {{
    "row_id": "...",
    "immigration_context": "yes/no/unclear",
    "echo_type": "own_voice/quoted_or_critical/unclear",
    "confidence": "low/medium/high",
    "rationale_short": "Brief reason, max 25 words."
  }}
]

Classify these excerpts:

{records_json}
"""


def records_for_prompt(df: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for row in df.itertuples(index=False):
        records.append(
            {
                "row_id": row.row_id,
                "speech_id": row.speech_id,
                "date": row.date,
                "speaker": row.speaker,
                "party": row.party,
                "debate": row.debate,
                "matched_term": row.full_match,
                "sentence_context": row.sentence_context,
            }
        )
    return records


def classify(slug: str, chunk_size: int) -> pd.DataFrame:
    path = PROCESSED / f"echo_{slug}.parquet"
    df = pd.read_parquet(path).reset_index(drop=True)
    df["row_id"] = [f"{slug}_{idx}" for idx in range(len(df))]

    load_api_key()
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not found")

    labels: list[dict[str, Any]] = []
    system = "You are a careful UK parliamentary discourse analyst. Return strict JSON only."
    for start in range(0, len(df), chunk_size):
        chunk = df.iloc[start : start + chunk_size]
        prompt = PROMPT_TEMPLATE.format(records_json=json.dumps(records_for_prompt(chunk), ensure_ascii=False))
        result = cached_call(SONNET, system, prompt, max_tokens=5000)
        parsed = parse_json(result["text"])
        if not isinstance(parsed, list):
            raise ValueError(f"Expected list response for chunk starting {start}")
        labels.extend(parsed)

    labels_df = pd.DataFrame(labels)
    missing = set(df["row_id"]) - set(labels_df["row_id"])
    if missing:
        raise ValueError(f"Missing {len(missing)} row IDs from LLM response")

    merged = df.merge(labels_df, on="row_id", how="left")
    out_path = PROCESSED / f"echo_{slug}_llm.parquet"
    merged.to_parquet(out_path, index=False)
    csv_path = REPORTS / f"echo_{slug}_llm_classifications.csv"
    merged.to_csv(csv_path, index=False)
    return merged


def plot_mentions(slug: str, df: pd.DataFrame) -> None:
    main_parties = [
        "conservative",
        "labour",
        "scottish-national-party",
        "liberal-democrat",
        "labourco-operative",
        "reform",
    ]
    labels = {
        "conservative": "Conservative",
        "labour": "Labour",
        "scottish-national-party": "SNP",
        "liberal-democrat": "Liberal Democrat",
        "labourco-operative": "Labour/Co-op",
        "reform": "Reform",
    }
    colors = {
        "conservative": "#1f77b4",
        "labour": "#d62728",
        "scottish-national-party": "#f2c300",
        "liberal-democrat": "#ff7f0e",
        "labourco-operative": "#8c1d40",
        "reform": "#12b6cf",
    }

    import matplotlib.pyplot as plt

    years = list(range(2015, 2026))
    counts = (
        df[df["party"].isin(main_parties)]
        .groupby(["year", "party"])
        .size()
        .rename("mentions")
        .reset_index()
    )
    pivot = counts.pivot_table(index="year", columns="party", values="mentions", fill_value=0).reindex(years, fill_value=0)
    for party in main_parties:
        if party not in pivot.columns:
            pivot[party] = 0
    pivot = pivot[main_parties]

    fig, ax = plt.subplots(figsize=(10, 6))
    for party in main_parties:
        ax.plot(pivot.index, pivot[party], marker="o", linewidth=2.2, label=labels[party], color=colors[party])
    title = slug.replace("_", " ")
    ax.set_title(f'Hansard mentions of "{title}" by party, 2015-2025')
    ax.set_xlabel("Year")
    ax.set_ylabel("Mentions")
    ax.set_xticks(years)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(REPORTS / f"{slug}_mentions_by_party.png", dpi=180)
    plt.close(fig)
    pivot.rename(columns=labels).to_csv(REPORTS / f"{slug}_mentions_by_party.csv", index_label="year")


def write_report(slug: str, df: pd.DataFrame) -> None:
    summary = (
        df.groupby(["immigration_context", "echo_type"])
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
    )
    party_summary = (
        df[df["immigration_context"] == "yes"]
        .groupby(["party", "echo_type"])
        .size()
        .reset_index(name="n")
        .sort_values(["party", "n"], ascending=[True, False])
    )
    year_party = (
        df.groupby(["year", "party"])
        .size()
        .reset_index(name="n")
        .sort_values(["year", "n"], ascending=[True, False])
    )
    examples = df[
        [
            "row_id",
            "date",
            "speaker",
            "party",
            "debate",
            "immigration_context",
            "echo_type",
            "confidence",
            "rationale_short",
            "sentence_context",
        ]
    ].sample(min(12, len(df)), random_state=9)
    report = f"""# LLM Echo Classification: {slug.replace("_", " ")}

Model: Sonnet via `scripts/llm_echo_classify.py`.

Total occurrences classified: {len(df)}

Plot: `reports/{slug}_mentions_by_party.png`

## Context and Echo Type

{summary.to_markdown(index=False)}

## Immigration-Context Uses by Party and Echo Type

{party_summary.to_markdown(index=False)}

## Mentions by Year and Party

{year_party.to_markdown(index=False)}

## Random Examples

{examples.to_markdown(index=False)}
"""
    (REPORTS / f"{slug}_llm_classification.md").write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--chunk-size", type=int, default=20)
    args = parser.parse_args()
    df = classify(args.slug, args.chunk_size)
    plot_mentions(args.slug, df)
    write_report(args.slug, df)
    print(df.groupby(["immigration_context", "echo_type"]).size().to_string())
    print(f"wrote {PROCESSED / f'echo_{args.slug}_llm.parquet'}")
    print(f"wrote {REPORTS / f'{args.slug}_mentions_by_party.png'}")
    print(f"wrote {REPORTS / f'{args.slug}_llm_classification.md'}")


if __name__ == "__main__":
    main()
