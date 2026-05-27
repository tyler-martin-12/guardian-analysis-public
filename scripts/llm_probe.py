from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from typing import Any

import anthropic
from dotenv import load_dotenv

from scripts.paths import CACHE

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-5"
LLM_CACHE = CACHE / "llm"
LLM_CACHE.mkdir(parents=True, exist_ok=True)


def load_api_key() -> None:
    load_dotenv()


def cached_call(model: str, system: str, prompt: str, max_tokens: int = 1200) -> dict[str, Any]:
    key = hashlib.sha256(
        json.dumps({"model": model, "system": system, "prompt": prompt}, sort_keys=True).encode()
    ).hexdigest()
    path = LLM_CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    result = {
        "model": model,
        "text": "\n".join(block.text for block in message.content if block.type == "text"),
        "usage": message.usage.model_dump() if hasattr(message.usage, "model_dump") else {},
    }
    path.write_text(json.dumps(result, indent=2))
    time.sleep(0.25)
    return result


def parse_json(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check whether ANTHROPIC_API_KEY is configured.")
    args = parser.parse_args()
    load_api_key()
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not found in environment or .env")
    if args.check:
        print("ANTHROPIC_API_KEY is configured")


if __name__ == "__main__":
    main()
