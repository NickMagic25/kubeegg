from __future__ import annotations

import re
import secrets
import string
from typing import Iterable, Tuple



_K8S_NAME_RE = re.compile(r"[^a-z0-9-]+")
_ENV_RE = re.compile(r"[^A-Z0-9_]+")


def normalize_k8s_name(value: str, *, max_length: int = 63) -> str:
    value = value.strip().lower()
    value = _K8S_NAME_RE.sub("-", value)
    value = re.sub(r"-+", "-", value)
    value = value.strip("-")
    if not value:
        return "app"
    if len(value) > max_length:
        value = value[:max_length].rstrip("-")
    if not value:
        return "app"
    if not value[0].isalnum():
        value = f"a-{value}"
    return value


def normalize_port_name(value: str) -> str:
    value = normalize_k8s_name(value)
    if value[0].isdigit():
        value = f"p-{value}"
    return value


def normalize_env_var(value: str) -> str:
    value = value.strip().upper()
    value = _ENV_RE.sub("_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")
    if not value:
        return "VAR"
    if value[0].isdigit():
        value = f"VAR_{value}"
    return value


def parse_ports(text: str) -> list[int]:
    parts = re.split(r"[\s,]+", text.strip())
    ports: list[int] = []
    for part in parts:
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            if start.isdigit() and end.isdigit():
                start_i, end_i = int(start), int(end)
                if start_i > end_i:
                    start_i, end_i = end_i, start_i
                for port in range(start_i, end_i + 1):
                    if 1 <= port <= 65535:
                        ports.append(port)
            continue
        if part.isdigit():
            port = int(part)
            if 1 <= port <= 65535:
                ports.append(port)
    return sorted(set(ports))


def parse_passive_range(text: str) -> Tuple[int, int]:
    cleaned = text.strip().replace(":", "-")
    if "-" not in cleaned:
        raise ValueError("Passive range must look like 21000-21010")
    start_s, end_s = cleaned.split("-", 1)
    if not (start_s.isdigit() and end_s.isdigit()):
        raise ValueError("Passive range must contain only numbers")
    start, end = int(start_s), int(end_s)
    if start <= 0 or end <= 0 or start > end:
        raise ValueError("Passive range must be positive and start <= end")
    if end > 65535:
        raise ValueError("Passive range must be <= 65535")
    return start, end


def ensure_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))




def memory_to_mb(value: str) -> int | None:
    raw = value.strip().lower()
    if not raw:
        return None
    unit = None
    for suffix in ("gib", "gi", "gb", "g", "mib", "mi", "mb", "m"):
        if raw.endswith(suffix):
            unit = suffix
            raw = raw[: -len(suffix)]
            break
    raw = raw.strip()
    if not raw or not raw.replace(".", "", 1).isdigit():
        return None
    amount = float(raw)
    if unit in {"gib", "gi"}:
        mb = amount * 1024
    elif unit in {"gb", "g"}:
        mb = amount * 1000
    else:
        mb = amount
    return int(mb)
