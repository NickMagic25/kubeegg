from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from ruamel.yaml import YAML

from .egg import parse_egg
from .fetch import load_egg_json
from .kustomize import write_kustomization
from .models import UserConfig
from .prompts import collect_user_config
from .render import render_all

app = typer.Typer(add_completion=False, invoke_without_command=True)
console = Console()


def _write_yaml(path: Path, data: dict) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def _ensure_output_dir(out_dir: Path) -> None:
    if not out_dir.exists():
        raise typer.BadParameter("Output directory does not exist. Create it first.")
    if not out_dir.is_dir():
        raise typer.BadParameter("Output path must be a directory.")


def _prompt_overwrite(existing: list[Path]) -> bool:
    if not existing:
        return True
    console.print("The following files already exist:")
    for path in existing:
        console.print(f"  - {path.name}")
    choice = Prompt.ask("overwrite or abort", choices=["overwrite", "abort"], default="abort")
    return choice.strip().lower() == "overwrite"


def _write_outputs(out_dir: Path, manifests: dict[str, dict], extra_files: list[str], force: bool) -> list[str]:
    filenames = list(manifests.keys())
    to_check = filenames + extra_files
    existing = [out_dir / name for name in to_check if (out_dir / name).exists()]
    if existing and not force:
        if not _prompt_overwrite(existing):
            raise typer.Exit(code=1)
    for name, data in manifests.items():
        _write_yaml(out_dir / name, data)
    return filenames


def _summarize_config(config: UserConfig) -> None:
    console.print("\nSummary:")
    console.print(f"App name: {config.app_name}")
    console.print(f"Namespace: {config.namespace}")
    console.print(f"Image: {config.image}")


@app.callback()
def main(
    egg: str = typer.Argument(..., help="Path or URL to egg JSON"),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Output directory"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files"),
    sops: bool = typer.Option(False, "--sops", "-s", help="Write Secret as secrets.sops.yaml"),
) -> None:
    try:
        _ensure_output_dir(out)
    except typer.BadParameter as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    try:
        result = load_egg_json(egg)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    try:
        egg_model = parse_egg(result.data)
    except Exception as exc:  # pragma: no cover - defensive
        console.print(f"[red]Failed to parse egg JSON: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    config = collect_user_config(egg_model)
    _summarize_config(config)

    secret_filename = "secrets.sops.yaml" if sops else "secret.yaml"
    manifests = render_all(config, secret_filename=secret_filename)
    written = _write_outputs(out, manifests, ["kustomization.yaml"], force)

    write_kustomization(out / "kustomization.yaml", written, {
        "app.kubernetes.io/name": config.app_name,
        "app.kubernetes.io/managed-by": "kubeegg",
    })

    console.print("\nGenerated:")
    for name in ["kustomization.yaml"] + written:
        console.print(f"  - {name}")


if __name__ == "__main__":
    app()
