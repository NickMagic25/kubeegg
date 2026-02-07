from __future__ import annotations

from typing import Any

from .models import Egg, EggVariable


_DEF_REQUIRED_KEYS = {"required", "is_required"}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _extract_images(data: dict[str, Any]) -> dict[str, str]:
    images: dict[str, str] = {}
    docker_images = data.get("docker_images") or data.get("dockerImages")
    if isinstance(docker_images, dict):
        images.update({str(k): str(v) for k, v in docker_images.items() if v})
    elif isinstance(docker_images, list):
        for idx, value in enumerate(docker_images, start=1):
            if isinstance(value, str) and value:
                images[f"image-{idx}"] = value
    docker_image = data.get("docker_image") or data.get("dockerImage") or data.get("image")
    if isinstance(docker_image, str) and docker_image:
        images.setdefault("default", docker_image)
    return images


def _extract_variables(data: dict[str, Any]) -> list[EggVariable]:
    variables: list[EggVariable] = []
    raw_vars = data.get("variables")
    if isinstance(raw_vars, list):
        for item in raw_vars:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("env_variable") or item.get("envVariable") or "")
            env_variable = item.get("env_variable") or item.get("envVariable")
            env_variable = str(env_variable) if env_variable else None
            description = item.get("description")
            default_value = item.get("default_value")
            if default_value is None:
                default_value = item.get("default")
            required_val = False
            for key in _DEF_REQUIRED_KEYS:
                if key in item:
                    required_val = _as_bool(item.get(key))
                    break
            variables.append(
                EggVariable(
                    name=name or (env_variable or ""),
                    env_variable=env_variable,
                    description=str(description) if description is not None else None,
                    default_value=str(default_value) if default_value is not None else None,
                    required=required_val,
                )
            )
    elif isinstance(data.get("environment"), dict):
        for key, value in data["environment"].items():
            variables.append(
                EggVariable(
                    name=str(key),
                    env_variable=str(key),
                    description=None,
                    default_value=str(value) if value is not None else None,
                    required=False,
                )
            )
    return variables


def _extract_ports(data: dict[str, Any], variables: list[EggVariable]) -> list[int]:
    ports: set[int] = set()

    def add_port(val: Any) -> None:
        if isinstance(val, int):
            if val > 0:
                ports.add(val)
            return
        if isinstance(val, str):
            text = val.strip()
            if text.isdigit():
                ports.add(int(text))

    config = data.get("config")
    if isinstance(config, dict):
        raw_ports = config.get("ports") or config.get("port")
        if isinstance(raw_ports, list):
            for item in raw_ports:
                add_port(item)
        else:
            add_port(raw_ports)

    raw_ports = data.get("ports")
    if isinstance(raw_ports, list):
        for item in raw_ports:
            add_port(item)

    for var in variables:
        if not var.env_variable:
            continue
        if "PORT" in var.env_variable.upper():
            if var.default_value and var.default_value.isdigit():
                ports.add(int(var.default_value))

    return sorted(ports)


def _extract_installation(data: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return None, None, None
    installation = scripts.get("installation")
    if not isinstance(installation, dict):
        return None, None, None
    script = installation.get("script")
    if isinstance(script, str):
        script = script.replace("\r\n", "\n")
    else:
        script = None
    image = installation.get("container")
    entrypoint = installation.get("entrypoint")
    return script, str(image) if image else None, str(entrypoint) if entrypoint else None


def parse_egg(data: dict[str, Any]) -> Egg:
    name = data.get("name") or data.get("title")
    description = data.get("description")
    startup = data.get("startup")
    images = _extract_images(data)
    variables = _extract_variables(data)
    ports = _extract_ports(data, variables)
    install_script, install_image, install_entrypoint = _extract_installation(data)
    return Egg(
        name=str(name) if name is not None else None,
        description=str(description) if description is not None else None,
        startup=str(startup) if startup is not None else None,
        docker_images=images,
        variables=variables,
        ports=ports,
        install_script=install_script,
        install_image=install_image,
        install_entrypoint=install_entrypoint,
    )
