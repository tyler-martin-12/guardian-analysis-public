from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Any

import pandas as pd

from scripts.llm_probe import LLM_CACHE, SONNET, cached_call, load_api_key, parse_json
from scripts.paths import REPORTS

SAMPLE_PATH = REPORTS / "defensive_rhetoric_sample.csv"
LLM_OUTPUT_PATH = REPORTS / "defensive_rhetoric_llm_labels.csv"

ALLOWED_LABELS = {
    "pro_immigration_or_pro_refugee",
    "restrictive_or_hostile",
    "mixed_or_unclear",
    "not_immigration_stance",
}


def selected_mask(df: pd.DataFrame) -> pd.Series:
    return df["selected"].astype(str).str.lower().isin(["true", "1", "yes"])


def record_for_prompt(row: pd.Series) -> dict[str, Any]:
    text = str(row.get("speech_text", ""))
    return {
        "speech_id": row["speech_id"],
        "date": row.get("date", ""),
        "speaker": row.get("speaker", ""),
        "party": row.get("party", ""),
        "speaker_role": row.get("speaker_role", ""),
        "debate_title": row.get("minor_heading") or row.get("major_heading", ""),
        "sub_type": row.get("sub_type", ""),
        "search_pattern_match": row.get("search_pattern_match", ""),
        "text": text[:5000],
    }


def stance_prompt(records: list[dict[str, Any]]) -> str:
    return f"""
Classify each UK Parliament speech for immigration/asylum/refugee stance.

Use exactly one stance label:
- pro_immigration_or_pro_refugee: speaker substantively supports migrants, refugees, asylum seekers, safe routes, rights, protections, family reunion, compensation for hostile-environment harms, or criticises restrictive policy on humanitarian/rights grounds.
- restrictive_or_hostile: speaker substantively supports control, deterrence, removals, deportation, offshore/third-country processing, inadmissibility, illegal-entry framing, pull-factor arguments, or selective restriction, even if framed in humanitarian or compassionate language.
- mixed_or_unclear: speech contains competing signals, is mainly procedural/operational, or the substantive stance cannot be determined.
- not_immigration_stance: immigration/asylum/refugee language is incidental and the speech is not taking a stance on immigration policy or migrants/refugees/asylum seekers.

Important distinctions:
- Do not treat quoted, criticised, or negated hostile vocabulary as the speaker endorsing that vocabulary.
- If a minister defends restrictive policy using humanitarian language, classify the substantive policy stance as restrictive_or_hostile.
- If a speaker says a restrictive policy is cruel, shameful, immoral, unlawful because of harms to migrants/refugees/asylum seekers, classify as pro_immigration_or_pro_refugee.
- If a speaker only says a policy is inefficient, expensive, or badly drafted, classify as mixed_or_unclear unless there is a clear humanitarian/rights stance.

Return JSON only, as a list of objects with:
speech_id, stance, surface_tone (hostile_words_present / neutral / supportive / mixed), confidence (low / medium / high), rationale_short.

Speeches:
{json.dumps(records, ensure_ascii=False)}
"""


def cache_path(model: str, system: str, prompt: str) -> Any:
    key = hashlib.sha256(
        json.dumps({"model": model, "system": system, "prompt": prompt}, sort_keys=True).encode()
    ).hexdigest()
    return LLM_CACHE / f"{key}.json"


def run_llm(sample: pd.DataFrame, chunk_size: int, cache_only: bool = False) -> pd.DataFrame:
    system = (
        "You are a careful parliamentary discourse analyst. Classify substantive stance, "
        "not surface vocabulary. Be especially careful with negation, quoted hostility, "
        "critique of restrictive policy, and humanitarian language used to defend restriction."
    )
    rows: list[dict[str, Any]] = []
    missing_chunks: list[int] = []
    for start in range(0, len(sample), chunk_size):
        chunk = sample.iloc[start : start + chunk_size]
        records = [record_for_prompt(row) for _, row in chunk.iterrows()]
        prompt = stance_prompt(records)
        path = cache_path(SONNET, system, prompt)
        if cache_only and not path.exists():
            missing_chunks.append(start)
            continue
        result = cached_call(SONNET, system, prompt, max_tokens=5000)
        parsed = parse_llm_json(result["text"])
        if not isinstance(parsed, list):
            raise ValueError(f"Expected list response for chunk starting {start}")
        rows.extend(parsed)

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("No LLM labels were available")
    missing = set(sample["speech_id"]) - set(out["speech_id"])
    if missing and not cache_only:
        raise ValueError(f"LLM response missing {len(missing)} speech IDs: {sorted(missing)[:5]}")
    bad = sorted(set(out["stance"]) - ALLOWED_LABELS)
    if bad:
        raise ValueError(f"Unexpected stance labels: {bad}")
    if missing_chunks:
        print(f"cache-only skipped chunks starting at rows: {missing_chunks}", file=sys.stderr)
    return out


def parse_llm_json(text: str) -> list[dict[str, Any]]:
    try:
        return parse_json(text)
    except json.JSONDecodeError:
        return parse_expected_objects(text)


def parse_expected_objects(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    rows: list[dict[str, Any]] = []
    object_texts = re.findall(r"\{.*?\n\s*\}", stripped, flags=re.DOTALL)
    for object_text in object_texts:
        row: dict[str, Any] = {}
        for field in ("speech_id", "stance", "surface_tone", "confidence"):
            match = re.search(rf'"{field}"\s*:\s*"([^"]*)"', object_text)
            if not match:
                raise ValueError(f"Could not parse {field} from malformed LLM object: {object_text[:200]}")
            row[field] = match.group(1)
        rationale = re.search(r'"rationale_short"\s*:\s*"(.*)"\s*,?\s*\n\s*\}', object_text, flags=re.DOTALL)
        if not rationale:
            raise ValueError(f"Could not parse rationale_short from malformed LLM object: {object_text[:200]}")
        row["rationale_short"] = rationale.group(1).replace('\\"', '"')
        rows.append(row)
    if not rows:
        raise ValueError("Could not recover any objects from malformed LLM JSON")
    return rows


def update_sample(llm: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(SAMPLE_PATH, keep_default_na=False)
    if "llm_label" not in df.columns:
        df["llm_label"] = ""

    label_map = llm.set_index("speech_id")["stance"].to_dict()
    selected = selected_mask(df)
    df.loc[selected, "llm_label"] = df.loc[selected, "speech_id"].map(label_map).fillna(df.loc[selected, "llm_label"])
    df.to_csv(SAMPLE_PATH, index=False)
    return df.loc[selected].copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()

    load_api_key()
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not found in environment or .env")

    df = pd.read_csv(SAMPLE_PATH, keep_default_na=False)
    sample = df[selected_mask(df)].copy()
    llm = run_llm(sample, chunk_size=args.chunk_size, cache_only=args.cache_only)
    llm.to_csv(LLM_OUTPUT_PATH, index=False)
    updated = update_sample(llm)

    print(f"wrote {LLM_OUTPUT_PATH}")
    print(f"updated {SAMPLE_PATH}")
    print(updated["llm_label"].value_counts().to_string())
    print()
    print(pd.crosstab(updated["sub_type"], updated["llm_label"]).to_string())


if __name__ == "__main__":
    main()
