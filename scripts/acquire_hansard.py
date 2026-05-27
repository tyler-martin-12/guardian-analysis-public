from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree
from tqdm import tqdm

from scripts.paths import CACHE, PROCESSED, RAW

BASE = "https://www.theyworkforyou.com/pwdata/scrapedxml/debates/"
PEOPLE_URL = "https://raw.githubusercontent.com/mysociety/parlparse/master/members/people.json"
MINISTERS_URL = "https://raw.githubusercontent.com/mysociety/parlparse/master/members/ministers.json"

TRIGGER_TERMS = [
    "immigrant",
    "immigrants",
    "immigration",
    "asylum",
    "asylum seeker",
    "asylum seekers",
    "migrant",
    "migrants",
    "migration",
    "refugee",
    "refugees",
    "border",
    "borders",
    "deportation",
    "deport",
    "deported",
    "small boat",
    "small boats",
    "channel crossing",
    "channel crossings",
    "illegal entry",
    "illegal migration",
    "net migration",
    "right to remain",
    "leave to remain",
    "hostile environment",
    "windrush",
    "rwanda scheme",
    "rwanda plan",
]

TRIGGER_RE = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in sorted(TRIGGER_TERMS, key=len, reverse=True)) + r")\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class DebateFile:
    filename: str
    sitting_date: date
    suffix: str


def get_text(url: str, cache_path: Path) -> str:
    if cache_path.exists():
        return cache_path.read_text()
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(response.text)
    return response.text


def latest_debate_files(start_year: int, end_year: int) -> list[DebateFile]:
    html = get_text(BASE, CACHE / "debates_index.html")
    soup = BeautifulSoup(html, "html.parser")
    files: dict[date, DebateFile] = {}
    pattern = re.compile(r"debates(\d{4}-\d{2}-\d{2})([a-z])\.xml$")
    for link in soup.find_all("a"):
        name = link.get("href", "")
        match = pattern.match(name)
        if not match:
            continue
        sitting_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        if not (start_year <= sitting_date.year <= end_year):
            continue
        candidate = DebateFile(name, sitting_date, match.group(2))
        current = files.get(sitting_date)
        if current is None or candidate.suffix > current.suffix:
            files[sitting_date] = candidate
    return [files[key] for key in sorted(files)]


def download_file(filename: str) -> Path:
    path = RAW / "debates" / filename
    if path.exists():
        return path
    response = requests.get(BASE + filename, timeout=90)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def parse_xml(path: Path) -> list[dict]:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False, no_network=True)
    root = etree.fromstring(path.read_bytes(), parser=parser)
    rows: list[dict] = []
    major_heading = None
    minor_heading = None
    filename = path.name
    sitting_date = re.search(r"(\d{4}-\d{2}-\d{2})", filename).group(1)
    for element in root.iterchildren():
        tag = etree.QName(element).localname
        if tag == "major-heading":
            major_heading = clean_text(" ".join(element.itertext()))
            minor_heading = None
        elif tag == "minor-heading":
            minor_heading = clean_text(" ".join(element.itertext()))
        elif tag == "speech":
            text = clean_text(" ".join(element.itertext()))
            if not text:
                continue
            matches = sorted(set(match.group(0).lower() for match in TRIGGER_RE.finditer(text)))
            if not matches:
                continue
            if set(matches).issubset({"border", "borders"}):
                continue
            rows.append(
                {
                    "speech_id": element.get("id"),
                    "date": sitting_date,
                    "year": int(sitting_date[:4]),
                    "source_file": filename,
                    "speaker": element.get("speakername"),
                    "person_id": element.get("person_id"),
                    "speech_type_raw": element.get("type"),
                    "colnum": element.get("colnum"),
                    "time": element.get("time"),
                    "url": element.get("url"),
                    "major_heading": major_heading,
                    "minor_heading": minor_heading,
                    "trigger_terms": "|".join(matches),
                    "word_count": len(text.split()),
                    "text": text,
                }
            )
    return rows


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def load_json(url: str, path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    path.write_text(response.text)
    return response.json()


def active_record(records: Iterable[dict], person_id: str, day: str) -> dict | None:
    day_date = datetime.strptime(day, "%Y-%m-%d").date()
    candidates = []
    for record in records:
        if record.get("person_id") != person_id:
            continue
        start = parse_date(record.get("start_date")) or date.min
        end = parse_date(record.get("end_date")) or date.max
        if start <= day_date <= end:
            candidates.append(record)
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: row.get("start_date") or "")[-1]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def add_metadata(df: pd.DataFrame) -> pd.DataFrame:
    people = load_json(PEOPLE_URL, CACHE / "people.json")
    ministers = load_json(MINISTERS_URL, CACHE / "ministers.json")
    memberships = index_by_person(people.get("memberships", []))
    offices = index_by_person(ministers.get("memberships", []))

    party = []
    minister_role = []
    speaker_role = []
    for row in df.itertuples(index=False):
        membership = active_record(memberships.get(row.person_id, []), row.person_id, row.date) if row.person_id else None
        office = active_record(offices.get(row.person_id, []), row.person_id, row.date) if row.person_id else None
        party_id = membership.get("on_behalf_of_id") if membership else None
        role = office.get("role") if office else None
        raw_type = "" if pd.isna(row.speech_type_raw) else str(row.speech_type_raw).lower()
        if role:
            derived = "minister_or_shadow"
        elif "question" in raw_type:
            derived = "questioner"
        elif "answer" in raw_type:
            derived = "answerer"
        else:
            derived = "backbench_or_unknown"
        party.append(party_id)
        minister_role.append(role)
        speaker_role.append(derived)

    enriched = df.copy()
    enriched["party"] = party
    enriched["minister_role"] = minister_role
    enriched["speaker_role"] = speaker_role
    return enriched


def index_by_person(records: Iterable[dict]) -> dict[str, list[dict]]:
    indexed: dict[str, list[dict]] = {}
    for record in records:
        person_id = record.get("person_id")
        if person_id:
            indexed.setdefault(person_id, []).append(record)
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--max-files", type=int, default=None)
    args = parser.parse_args()

    files = latest_debate_files(args.start_year, args.end_year)
    if args.max_files:
        files = files[: args.max_files]

    rows: list[dict] = []
    for item in tqdm(files, desc="Downloading/parsing Commons debates"):
        path = download_file(item.filename)
        rows.extend(parse_xml(path))

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No matching speeches found.")
    df = df.drop_duplicates(subset=["speech_id"]).sort_values(["date", "speech_id"])
    df = add_metadata(df)

    out_path = PROCESSED / f"immigration_speeches_{args.start_year}_{args.end_year}.parquet"
    df.to_parquet(out_path, index=False)
    df.to_csv(PROCESSED / f"immigration_speeches_{args.start_year}_{args.end_year}.csv", index=False)

    counts = {
        "files_considered": len(files),
        "matching_speeches": int(len(df)),
        "by_year": df.groupby("year").size().to_dict(),
        "by_party": df["party"].fillna("unknown").value_counts().head(30).to_dict(),
        "by_speaker_role": df["speaker_role"].fillna("unknown").value_counts().to_dict(),
    }
    (PROCESSED / "summary_counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True))
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
