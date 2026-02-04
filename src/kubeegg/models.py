from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EggVariable:
    name: str
    env_variable: Optional[str]
    description: Optional[str]
    default_value: Optional[str]
    required: bool


@dataclass
class Egg:
    name: Optional[str]
    description: Optional[str]
    startup: Optional[str]
    docker_images: dict[str, str]
    variables: list[EggVariable] = field(default_factory=list)
    ports: list[int] = field(default_factory=list)


@dataclass
class EnvSelection:
    key: str
    value: str
    sensitive: bool


@dataclass
class PortSpec:
    container_port: int
    protocol: str
    name: str


@dataclass
class PVCSpec:
    name: str
    size: str
    mount_path: str
    access_modes: list[str]
    storage_class_name: Optional[str]


@dataclass
class FileManagerConfig:
    image: str
    username: str
    password_hash: str
    port: int


@dataclass
class ResourceValues:
    requests_cpu: Optional[str] = None
    requests_memory: Optional[str] = None
    limits_cpu: Optional[str] = None
    limits_memory: Optional[str] = None


@dataclass
class UserConfig:
    app_name: str
    namespace: str
    image: str
    pvc: PVCSpec
    env: list[EnvSelection]
    ports: list[PortSpec]
    file_manager: FileManagerConfig
    resources: Optional[ResourceValues] = None
