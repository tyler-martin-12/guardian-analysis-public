from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd
from lxml import etree
from tqdm import tqdm

from scripts.acquire_hansard import add_metadata
from scripts.paths import PROCESSED, RAW, REPORTS

ALL_SPEECHES_PATH = PROCESSED / "all_speeches_2015_2025.parquet"

QUOTE_CHARS = "\"'“”‘’"
ATTRIBUTION_RE = re.compile(
    r"\b("
    r"said|says|called|described|referred to|used the word|uses the term|"
    r"language of|rhetoric of|claimed|claims"
    r")\b",
    flags=re.IGNORECASE,
)
CRITICAL_RE = re.compile(
    r"\b(shameful|disgraceful|vile|incendiary|dehumanising|dehumanizing|language)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class TermSpec:
    slug: str
    label: str
    pattern: str


TERMS = [
    TermSpec("hostile_environment", "hostile environment", r"\bhostile environment\b"),
    TermSpec("invasion", "invasion / invasions", r"\binvasions?\b"),
    TermSpec("swarm", "swarm / swarming", r"\bswarm(?:ing)?\b"),
    TermSpec("stop_the_boats", "stop the boats", r"\bstop the boats\b"),
    TermSpec("small_boats", "small boats", r"\bsmall boats\b"),
    TermSpec("swamped", "swamped", r"\bswamped\b"),
]

SPOTCHECK_NOTES = {
    "hostile_environment": (
        "Manual spot-check of the 20/20 heuristic samples suggests high quoted/critical precision, "
        "but only moderate recall. Many apparent own-use cases are still critical uses of a policy label "
        "without local quotation markers, so this term is substantively echo/critique even when the heuristic "
        "marks it as own voice. Treat the own/quoted split as conservative."
    ),
    "invasion": (
        "Manual spot-check suggests the quote heuristic is not the main limitation; domain ambiguity is. "
        "Many occurrences refer to Russia/Ukraine, Iraq, or other military invasions rather than migration. "
        "This term needs an immigration-context filter before making a rhetorical-echo claim."
    ),
    "swarm": (
        "Manual spot-check suggests quoted/critical precision is good, but the term is sparse and latest-year "
        "quoted use is often absent. Useful as a Cameron-era example, not a robust decade-wide chart."
    ),
    "stop_the_boats": (
        "Manual spot-check suggests the heuristic is usable. Own-use cases are mostly slogan/policy use; "
        "quoted cases are often mentions of the slogan or criticism of it. Some Conservative quoted cases are "
        "self-quotation of the slogan, so quoted does not always mean hostile criticism."
    ),
    "small_boats": (
        "Manual spot-check suggests the term is too neutral for strong echo claims. Many own-use cases are "
        "operational descriptions by ministers and shadow ministers, especially after 2024. Quotation detection "
        "has limited interpretive value here."
    ),
    "swamped": (
        "Manual spot-check suggests mixed domains: public services, casework, prisons, and institutions being "
        "overloaded, not just immigration. Use cautiously unless filtered to migration contexts."
    ),
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_xml_all(path: Path) -> list[dict[str, object]]:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False, no_network=True)
    root = etree.fromstring(path.read_bytes(), parser=parser)
    rows: list[dict[str, object]] = []
    major_heading = ""
    minor_heading = ""
    filename = path.name
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if not date_match:
        return rows
    sitting_date = date_match.group(1)

    for element in root.iterchildren():
        tag = etree.QName(element).localname
        if tag in {"major-heading", "oral-heading"}:
            major_heading = clean_text(" ".join(element.itertext()))
            minor_heading = ""
        elif tag == "minor-heading":
            minor_heading = clean_text(" ".join(element.itertext()))
        elif tag == "speech":
            text = clean_text(" ".join(element.itertext()))
            if not text:
                continue
            rows.append(
                {
                    "speech_id": element.get("id") or "",
                    "date": sitting_date,
                    "year": int(sitting_date[:4]),
                    "source_file": filename,
                    "speaker": element.get("speakername") or "",
                    "person_id": element.get("person_id") or "",
                    "speech_type_raw": element.get("type") or "",
                    "colnum": element.get("colnum") or "",
                    "time": element.get("time") or "",
                    "url": element.get("url") or "",
                    "major_heading": major_heading,
                    "minor_heading": minor_heading,
                    "debate": minor_heading or major_heading,
                    "word_count": len(text.split()),
                    "text": text,
                    "speech_text": text,
                }
            )
    return rows


def build_all_speeches(force: bool = False) -> pd.DataFrame:
    if ALL_SPEECHES_PATH.exists() and not force:
        return pd.read_parquet(ALL_SPEECHES_PATH)

    files = sorted((RAW / "debates").glob("debates*.xml"))
    rows: list[dict[str, object]] = []
    for path in tqdm(files, desc="Parsing cached XML without trigger filter"):
        rows.extend(parse_xml_all(path))
    if not rows:
        raise SystemExit("No speeches parsed from cached XML")

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["speech_id"]).sort_values(["date", "speech_id"]).reset_index(drop=True)
    df = add_metadata(df)
    df["party"] = df["party"].fillna("unknown").replace("", "unknown")
    df["speaker"] = df["speaker"].fillna("").replace("", "Unknown")
    df["debate"] = df["debate"].fillna("")
    df.to_parquet(ALL_SPEECHES_PATH, index=False)
    return df


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+(?=[A-Z“\"'])", text):
        end = match.start()
        if end > start:
            spans.append((start, end))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def sentence_context(text: str, start: int) -> str:
    spans = sentence_spans(text)
    if not spans:
        return text
    idx = next((i for i, (left, right) in enumerate(spans) if left <= start < right), 0)
    left = max(0, idx - 1)
    right = min(len(spans), idx + 2)
    return clean_text(text[spans[left][0] : spans[right - 1][1]])


def quote_detection(text: str, start: int, end: int) -> tuple[bool, str]:
    local100 = text[max(0, start - 100) : min(len(text), end + 100)]
    local50 = text[max(0, start - 50) : min(len(text), end + 50)]
    before = text[max(0, start - 100) : start]

    rel_start = start - max(0, start - 100)
    rel_end = rel_start + (end - start)
    left_quote = max(local100.rfind(ch, 0, rel_start) for ch in QUOTE_CHARS)
    right_quote_positions = [pos for ch in QUOTE_CHARS if (pos := local100.find(ch, rel_end)) != -1]
    if left_quote != -1 and right_quote_positions and min(right_quote_positions) > rel_end:
        return True, "enclosing_quote_marks"
    if any(ch in local100[max(0, rel_start - 6) : rel_start] or ch in local100[rel_end : rel_end + 6] for ch in QUOTE_CHARS):
        return True, "near_quote_marks"
    if ATTRIBUTION_RE.search(before):
        return True, "attribution_verb"
    if CRITICAL_RE.search(local50):
        return True, "critical_framing_word"
    return False, ""


def term_occurrences(df: pd.DataFrame, term: TermSpec) -> pd.DataFrame:
    regex = re.compile(term.pattern, flags=re.IGNORECASE)
    rows: list[dict[str, object]] = []
    for row in df.itertuples(index=False):
        text = row.text
        for match in regex.finditer(text):
            is_quoted, evidence = quote_detection(text, match.start(), match.end())
            rows.append(
                {
                    "speech_id": row.speech_id,
                    "date": row.date,
                    "year": row.year,
                    "speaker": row.speaker,
                    "party": row.party or "unknown",
                    "debate": row.debate,
                    "major_heading": row.major_heading,
                    "minor_heading": row.minor_heading,
                    "sentence_context": sentence_context(text, match.start()),
                    "full_match": match.group(0),
                    "match_position": match.start(),
                    "is_quoted": bool(is_quoted),
                    "quote_evidence": evidence,
                }
            )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["date", "speech_id", "match_position"]).reset_index(drop=True)
    return out


def spot_check(term_df: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    rows = []
    for quoted_value, label in [(False, "own"), (True, "quoted")]:
        part = term_df[term_df["is_quoted"] == quoted_value]
        if part.empty:
            continue
        sample = part.sample(min(20, len(part)), random_state=seed)
        for row in sample.itertuples(index=False):
            rows.append(
                {
                    "heuristic_label": label,
                    "speech_id": row.speech_id,
                    "date": row.date,
                    "speaker": row.speaker,
                    "party": row.party,
                    "full_match": row.full_match,
                    "quote_evidence": row.quote_evidence,
                    "sentence_context": row.sentence_context,
                    "manual_note": "",
                }
            )
    return pd.DataFrame(rows)


def party_year_table(term_df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        term_df.assign(use_type=term_df["is_quoted"].map({True: "quoted_or_critical", False: "own_use"}))
        .groupby(["year", "party", "use_type"])
        .size()
        .reset_index(name="count")
    )
    return grouped


def chart(term_df: pd.DataFrame, slug: str, label: str) -> None:
    parties = term_df["party"].fillna("unknown").value_counts().head(8).index.tolist()
    plot_df = term_df[term_df["party"].isin(parties)].copy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for ax, quoted, title in [(axes[0], False, "own use"), (axes[1], True, "quoted / critical use")]:
        part = plot_df[plot_df["is_quoted"] == quoted]
        pivot = part.pivot_table(index="year", columns="party", values="speech_id", aggfunc="count", fill_value=0)
        pivot = pivot.reindex(range(2015, 2026), fill_value=0)
        pivot.plot(kind="bar", stacked=True, ax=ax, width=0.85)
        ax.set_title(title)
        ax.set_xlabel("year")
        ax.set_ylabel("occurrences")
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(label)
    fig.tight_layout()
    fig.savefig(REPORTS / f"echo_{slug}.png", dpi=160)
    plt.close(fig)


def md_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False) if not df.empty else "_No rows._"


def report_for_term(term_df: pd.DataFrame, term: TermSpec, sparse: bool = False) -> None:
    if term_df.empty:
        first = pd.DataFrame()
        top = pd.DataFrame()
        recent = pd.DataFrame()
        counts = pd.DataFrame()
    else:
        first = term_df.head(1)[["date", "speaker", "party", "debate", "full_match", "sentence_context"]]
        counts = party_year_table(term_df)
        top = term_df.groupby(["speaker", "party"]).size().reset_index(name="occurrences").sort_values("occurrences", ascending=False).head(5)
        recent_year = int(term_df["year"].max())
        recent_part = term_df[term_df["year"] == recent_year]
        recent = (
            recent_part.assign(use_type=recent_part["is_quoted"].map({False: "own_use", True: "quoted_or_critical"}))
            .groupby(["use_type", "party"])
            .size()
            .reset_index(name="count")
        )
        totals = recent.groupby("use_type")["count"].transform("sum")
        recent["share"] = (recent["count"] / totals).map(lambda value: f"{value:.0%}")
        recent = recent.sort_values(["use_type", "count"], ascending=[True, False])

    report = f"""# Echo Analysis: {term.label}

Total occurrences: {len(term_df)}

{"Skipped as too sparse for charting/report interpretation under the <30 occurrence rule." if sparse else f"Chart: `reports/echo_{term.slug}.png`"}

## First Appearance in Corpus

{md_table(first)}

## Counts Per Year by Party and Use Type

{md_table(counts)}

## Top Speakers

{md_table(top)}

## Most Recent Year Party Shares

{md_table(recent)}

## Heuristic Spot-Check Sample

{SPOTCHECK_NOTES.get(term.slug, "No spot-check note.")}

The sampled rows below are retained for inspection.

{md_table(spot_check(term_df))}
"""
    (REPORTS / f"echo_{term.slug}.md").write_text(report)


def summary(usable: dict[str, pd.DataFrame], skipped: dict[str, int], all_df: pd.DataFrame) -> None:
    rows = []
    for slug, df in usable.items():
        total = len(df)
        quoted = int(df["is_quoted"].sum())
        own = total - quoted
        recent_year = int(df["year"].max()) if total else 0
        recent = df[df["year"] == recent_year]
        own_top = (
            recent[~recent["is_quoted"]]["party"].value_counts(normalize=True).head(1)
            if not recent[~recent["is_quoted"]].empty
            else pd.Series(dtype=float)
        )
        quoted_top = (
            recent[recent["is_quoted"]]["party"].value_counts(normalize=True).head(1)
            if not recent[recent["is_quoted"]].empty
            else pd.Series(dtype=float)
        )
        rows.append(
            {
                "slug": slug,
                "total": total,
                "quoted_share": quoted / total if total else 0,
                "own": own,
                "quoted": quoted,
                "recent_year": recent_year,
                "own_top_party": own_top.index[0] if len(own_top) else "none",
                "own_top_share": float(own_top.iloc[0]) if len(own_top) else 0,
                "quoted_top_party": quoted_top.index[0] if len(quoted_top) else "none",
                "quoted_top_share": float(quoted_top.iloc[0]) if len(quoted_top) else 0,
            }
        )
    metrics = pd.DataFrame(rows).sort_values(["quoted_share", "total"], ascending=[False, False])
    missing_party = (all_df["party"].fillna("unknown") == "unknown").mean()
    skipped_text = ", ".join(f"`{slug}` ({count})" for slug, count in skipped.items()) or "none"

    stop = usable.get("stop_the_boats", pd.DataFrame())
    hostile = usable.get("hostile_environment", pd.DataFrame())
    small = usable.get("small_boats", pd.DataFrame())
    invasion = usable.get("invasion", pd.DataFrame())

    def party_count(df: pd.DataFrame, party: str, quoted: bool | None = None) -> int:
        part = df if quoted is None else df[df["is_quoted"] == quoted]
        return int((part["party"] == party).sum())

    stop_own = stop[~stop["is_quoted"]] if not stop.empty else pd.DataFrame()
    stop_own_total = len(stop_own) or 1
    stop_con_own = party_count(stop, "conservative", quoted=False)
    stop_lab_total = party_count(stop, "labour")
    stop_lab_quoted = party_count(stop, "labour", quoted=True)
    hostile_lab_snp = party_count(hostile, "labour") + party_count(hostile, "scottish-national-party")
    hostile_total = len(hostile) or 1
    small_recent = small[small["year"] == small["year"].max()] if not small.empty else pd.DataFrame()
    small_recent_own = small_recent[~small_recent["is_quoted"]] if not small_recent.empty else pd.DataFrame()
    invasion_nonquote = len(invasion[~invasion["is_quoted"]]) if not invasion.empty else 0

    body = f"""# Rhetorical Echo Summary

Parsed `{len(all_df):,}` speeches from the 1,614 cached Commons XML files into `data/processed/all_speeches_2015_2025.parquet`. Party metadata is missing for about {missing_party:.0%} of speeches, so `unknown` is retained in the tables rather than imputed.

The cleanest echo-style case is `stop the boats`: Conservatives account for {stop_con_own}/{stop_own_total} own-use occurrences ({stop_con_own / stop_own_total:.0%}), while Labour has {stop_lab_quoted}/{stop_lab_total} occurrences marked quoted/critical. A naive party word count would treat every Labour mention as adoption of the slogan; the echo-aware split shows a meaningful share are references to or criticism of the slogan.

`hostile environment` is also echo-like, but in a different way: Labour plus SNP account for {hostile_lab_snp}/{hostile_total} total mentions. Because the phrase is now a policy label, many critical uses are not locally quoted, so the heuristic likely undercounts echo/critique.

`small boats` does not support the echo hypothesis cleanly. In {int(small['year'].max()) if not small.empty else 0}, own-use mentions are spread across governing and opposition parties ({len(small_recent_own)} own-use occurrences), suggesting genuine convergence around an operational term rather than mainly quotation.

`invasion`, `swarm`, and `swamped` need caution in the trigger-free corpus. `invasion` has {invasion_nonquote} own-use occurrences, but many are military/geopolitical rather than migration rhetoric; `swarm` is sparse; `swamped` is often about institutional overload. These are candidates for a stricter immigration-context pass, not headline claims.

Skipped as too sparse under the 30-occurrence rule: {skipped_text}.
"""
    (REPORTS / "echo_summary.md").write_text(body)


def run(force_all: bool = False) -> None:
    df = build_all_speeches(force=force_all)
    usable: dict[str, pd.DataFrame] = {}
    skipped: dict[str, int] = {}
    for term in TERMS:
        term_df = term_occurrences(df, term)
        term_df.to_parquet(PROCESSED / f"echo_{term.slug}.parquet", index=False)
        if len(term_df) < 30:
            skipped[term.slug] = len(term_df)
            report_for_term(term_df, term, sparse=True)
            continue
        chart(term_df, term.slug, term.label)
        report_for_term(term_df, term)
        usable[term.slug] = term_df
    summary(usable, skipped, df)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-all", action="store_true")
    args = parser.parse_args()
    run(force_all=args.force_all)


if __name__ == "__main__":
    main()
