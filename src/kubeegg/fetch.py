from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass
class FetchResult:
    data: dict[str, Any]
    source: str
    resolved_source: str


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def github_blob_to_raw(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        return url
    parts = parsed.path.lstrip("/").split("/")
    if len(parts) < 5:
        return url
    if parts[2] != "blob":
        return url
    org, repo, _, ref = parts[:4]
    rest = "/".join(parts[4:])
    return f"https://raw.githubusercontent.com/{org}/{repo}/{ref}/{rest}"


def load_egg_json(source: str) -> FetchResult:
    if is_url(source):
        resolved = github_blob_to_raw(source)
        try:
            response = httpx.get(resolved, timeout=20.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to fetch egg JSON from {resolved}: {exc}") from exc
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Response from {resolved} is not valid JSON") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Egg JSON must be an object at the top level")
        return FetchResult(data=data, source=source, resolved_source=resolved)

    path = Path(source)
    if not path.exists():
        raise RuntimeError(f"File not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read file: {path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"File {path} is not valid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Egg JSON must be an object at the top level")
    return FetchResult(data=data, source=str(path), resolved_source=str(path))
