from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ruamel.yaml import YAML


def write_kustomization(path: Path, resources: Iterable[str], labels: dict[str, str]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    data = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "resources": list(resources),
        "labels": [
            {
                "pairs": labels,
            }
        ],
    }
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)
