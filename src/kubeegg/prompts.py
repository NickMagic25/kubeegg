from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm, Prompt

from .models import EnvSelection, FileManagerConfig, InstallConfig, PortSpec, PVCSpec, ResourceValues, UserConfig
from .util import (
    generate_password,
    normalize_env_var,
    normalize_k8s_name,
    normalize_port_name,
    parse_ports,
)

console = Console()

FILE_MANAGER_IMAGE = "hurlenko/filebrowser:latest"
FORCE_SECRET_VARS = {"FTP_USERNAME", "FTP_PASSWORD"}


def _print_env_info(name: str, description: str | None, default_value: str | None, required: bool) -> None:
    console.print(f"[bold]{name}[/bold]")
    if description:
        console.print(description)
    if default_value is not None:
        console.print(f"Default: [cyan]{default_value}[/cyan]")
    console.print(f"Required: {'yes' if required else 'no'}")


def prompt_app_identity(egg_name: str | None) -> tuple[str, str]:
    default_app = normalize_k8s_name(egg_name or "game-server")
    app_name = Prompt.ask("App name", default=default_app)
    app_name = normalize_k8s_name(app_name)
    namespace = Prompt.ask("Namespace", default=app_name)
    namespace = normalize_k8s_name(namespace)
    return app_name, namespace


def prompt_image(images: dict[str, str]) -> str:
    if not images:
        return Prompt.ask("Container image")

    console.print("Detected images:")
    labels = list(images.keys())
    for idx, label in enumerate(labels, start=1):
        console.print(f"  {idx}. {label}: {images[label]}")
    other_index = len(labels) + 1
    console.print(f"  {other_index}. Other Image")

    while True:
        selection = Prompt.ask("Select image number", default="1")
        if not selection.isdigit():
            console.print("[red]Enter a number from the list.[/red]")
            continue
        idx = int(selection)
        if 1 <= idx <= len(labels):
            return images[labels[idx - 1]]
        if idx == other_index:
            custom = Prompt.ask("Container image")
            if custom.strip():
                return custom.strip()
            console.print("[red]Image cannot be empty.[/red]")
            continue
        console.print("[red]Selection out of range.[/red]")


def prompt_pvc(app_name: str) -> PVCSpec:
    pvc_name = Prompt.ask("PVC name", default=f"{app_name}-data")
    pvc_name = normalize_k8s_name(pvc_name)
    size = Prompt.ask("PVC size", default="10Gi")
    mount_path = Prompt.ask("PVC mount path", default="/home/container")
    storage_class = Prompt.ask("storageClassName (optional)", default="")
    storage_class = storage_class.strip() or None
    return PVCSpec(
        name=pvc_name,
        size=size,
        mount_path=mount_path,
        access_modes=["ReadWriteMany"],
        storage_class_name=storage_class,
    )


def prompt_env_vars(variables) -> list[EnvSelection]:
    selections: list[EnvSelection] = []
    if not variables:
        return selections
    console.print("\nEnvironment variables:")
    for var in variables:
        env_name = var.env_variable or normalize_env_var(var.name or "VAR")
        _print_env_info(env_name, var.description, var.default_value, var.required)
        if not var.env_variable:
            env_name = Prompt.ask("Env var name", default=env_name)
            env_name = normalize_env_var(env_name)
        default_value = var.default_value or ""
        value = Prompt.ask("Value (leave blank to skip)" if not var.required else "Value", default=default_value)
        if not value and not var.required:
            continue
        while not value and var.required:
            value = Prompt.ask("Value", default=default_value)
        env_upper = env_name.upper()
        force_secret = env_upper in FORCE_SECRET_VARS
        sensitive_default = any(token in env_upper for token in ["PASS", "SECRET", "TOKEN", "KEY"])
        used_default = bool(default_value) and value == default_value
        if force_secret:
            sensitive = True
        elif used_default:
            sensitive = sensitive_default
        else:
            sensitive = Confirm.ask("Is this value sensitive?", default=sensitive_default)
        selections.append(EnvSelection(key=env_name, value=value, sensitive=sensitive))
        console.print("")
    return selections


def prompt_startup(startup: str | None) -> str | None:
    if startup:
        if Confirm.ask("Use detected startup command?", default=True):
            return startup
        custom = Prompt.ask("Startup command (leave blank to skip)", default="")
        return custom.strip() or None
    custom = Prompt.ask("Startup command (leave blank to skip)", default="")
    return custom.strip() or None


def prompt_install_script(egg) -> InstallConfig | None:
    if not egg.install_script or not egg.install_image:
        return None
    console.print("\nInstaller script detected.")
    enable = Confirm.ask("Run installer initContainer on first start?", default=True)
    if not enable:
        return None
    return InstallConfig(
        image=egg.install_image,
        entrypoint=egg.install_entrypoint,
        script=egg.install_script,
    )


def prompt_ports(detected_ports: list[int]) -> list[PortSpec]:
    while True:
        ports: list[int] = []
        if detected_ports:
            display = ", ".join(str(p) for p in detected_ports)
            use_detected = Confirm.ask(f"Use detected ports [{display}]?", default=True)
            if use_detected:
                ports = detected_ports
        if not ports:
            raw = Prompt.ask("Container ports to expose (comma-separated, empty to skip)", default="")
            if raw.strip():
                ports = parse_ports(raw)
        if ports:
            break
        if Confirm.ask("No ports selected. Continue without a game Service?", default=False):
            return []
    port_specs: list[PortSpec] = []
    for port in ports:
        protocol = Prompt.ask(f"Protocol for port {port}", default="TCP")
        protocol = protocol.strip().upper() or "TCP"
        if protocol not in {"TCP", "UDP"}:
            protocol = "TCP"
        name_default = normalize_port_name(f"game-{port}")
        name = Prompt.ask(f"Service port name for {port}", default=name_default)
        name = normalize_port_name(name)
        port_specs.append(PortSpec(container_port=port, protocol=protocol, name=name))
    return port_specs


def prompt_file_manager(mount_path: str) -> FileManagerConfig:
    console.print("\nFile manager sidecar:")
    console.print("File manager root directory: /data")
    image = Prompt.ask("File manager image", default=FILE_MANAGER_IMAGE)
    username = Prompt.ask("File manager username", default="admin")
    auto_password = Confirm.ask("Auto-generate file manager password?", default=True)
    if auto_password:
        password = generate_password()
        console.print("Generated file manager password:")
        console.print(password)
    else:
        password = Prompt.ask("File manager password", password=True)
    while not password:
        password = Prompt.ask("File manager password", password=True)
    port_raw = Prompt.ask("File manager web UI port", default="8080")
    while not port_raw.isdigit() or not (1 <= int(port_raw) <= 65535):
        console.print("[red]Port must be between 1 and 65535[/red]")
        port_raw = Prompt.ask("File manager web UI port", default="8080")
    return FileManagerConfig(
        image=image.strip() or FILE_MANAGER_IMAGE,
        username=username,
        password=password,
        port=int(port_raw),
    )


def prompt_resources() -> ResourceValues | None:
    configure = Confirm.ask("Configure CPU/memory requests & limits?", default=False)
    if not configure:
        return None

    def _normalize_cpu(value: str) -> str | None:
        raw = value.strip().lower()
        if not raw:
            return None
        if raw.endswith("m"):
            raw = raw[:-1]
        if not raw.replace(".", "", 1).isdigit():
            return None
        if raw.endswith("."):
            raw = raw[:-1]
        return f"{raw}m"

    def _normalize_memory(value: str) -> str | None:
        raw = value.strip().lower()
        if not raw:
            return None
        for suffix in ("gb", "g", "gi"):
            if raw.endswith(suffix):
                raw = raw[: -len(suffix)]
                break
        raw = raw.strip()
        if not raw.replace(".", "", 1).isdigit():
            return None
        if raw.endswith("."):
            raw = raw[:-1]
        return f"{raw}Gi"

    def _ask_cpu(label: str) -> str | None:
        while True:
            value = Prompt.ask(label, default="")
            normalized = _normalize_cpu(value)
            if value.strip() and normalized is None:
                console.print("[red]Enter CPU in millicores (m), e.g. 500 or 250m.[/red]")
                continue
            return normalized

    def _ask_memory(label: str) -> str | None:
        while True:
            value = Prompt.ask(label, default="")
            normalized = _normalize_memory(value)
            if value.strip() and normalized is None:
                console.print("[red]Enter memory in GB, e.g. 2 or 0.5.[/red]")
                continue
            return normalized

    requests_cpu = _ask_cpu("CPU request (m, optional)")
    requests_memory = _ask_memory("Memory request (GB, optional)")
    limits_cpu = _ask_cpu("CPU limit (m, optional)")
    limits_memory = _ask_memory("Memory limit (GB, optional)")
    return ResourceValues(
        requests_cpu=requests_cpu,
        requests_memory=requests_memory,
        limits_cpu=limits_cpu,
        limits_memory=limits_memory,
    )


def collect_user_config(egg) -> UserConfig:
    app_name, namespace = prompt_app_identity(egg.name)
    image = prompt_image(egg.docker_images)
    pvc = prompt_pvc(app_name)
    env = prompt_env_vars(egg.variables)
    startup_command = prompt_startup(egg.startup)
    ports = prompt_ports(egg.ports)
    file_manager = prompt_file_manager(pvc.mount_path)
    install = prompt_install_script(egg)
    resources = prompt_resources()
    return UserConfig(
        app_name=app_name,
        namespace=namespace,
        image=image,
        pvc=pvc,
        env=env,
        ports=ports,
        file_manager=file_manager,
        startup_command=startup_command,
        install=install,
        resources=resources,
    )
