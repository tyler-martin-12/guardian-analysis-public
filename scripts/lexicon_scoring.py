from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

NEGATIVE_LEXICON = [
    "illegal",
    "criminal",
    "abuse",
    "bogus",
    "invasion",
    "flood",
    "swamp",
    "threat",
    "burden",
    "deport",
    "detain",
    "hostile",
    "crack down",
    "stop the boats",
]

DEFENSIVE_CUES = [
    "not",
    "never",
    "wrong to",
    "should not",
    "must not",
    "it is unfair",
    "it is shameful",
    "scapegoat",
    "demonise",
    "demonize",
    "welcome refugees",
    "contribution",
    "compassion",
    "safe routes",
    "sanctuary",
]


def score_terms(text: str, terms: list[str]) -> int:
    lowered = str(text).lower()
    return sum(len(re.findall(r"\b" + re.escape(term) + r"\b", lowered)) for term in terms)


def lexicon_label(negative_score: int, defensive_score: int) -> str:
    rough_score = defensive_score - negative_score
    if rough_score > 0:
        return "pro_immigration_or_pro_refugee"
    if rough_score < 0:
        return "restrictive_or_hostile"
    return "mixed_or_unclear"


def score_file(input_path: Path, output_path: Path) -> None:
    df = pd.read_parquet(input_path) if input_path.suffix == ".parquet" else pd.read_csv(input_path)
    text_col = "speech_text" if "speech_text" in df.columns else "text"
    df["negative_lexicon_score"] = df[text_col].map(lambda text: score_terms(text, NEGATIVE_LEXICON))
    df["defensive_cue_score"] = df[text_col].map(lambda text: score_terms(text, DEFENSIVE_CUES))
    df["rough_sentiment"] = df["defensive_cue_score"] - df["negative_lexicon_score"]
    df["lexicon_label"] = df.apply(
        lambda row: lexicon_label(row["negative_lexicon_score"], row["defensive_cue_score"]),
        axis=1,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix == ".parquet":
        df.to_parquet(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/defensive_rhetoric_sample.parquet")
    parser.add_argument("--output", default="data/processed/defensive_rhetoric_sample.parquet")
    args = parser.parse_args()
    score_file(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
