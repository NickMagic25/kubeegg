from __future__ import annotations

from typing import Any

from .models import EnvSelection, PortSpec, UserConfig
from .util import normalize_port_name


def _labels(app_name: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/name": app_name,
        "app.kubernetes.io/managed-by": "kubeegg",
    }


def _split_env(env: list[EnvSelection]) -> tuple[dict[str, str], dict[str, str]]:
    configmap: dict[str, str] = {}
    secret: dict[str, str] = {}
    for item in env:
        if item.sensitive:
            secret[item.key] = item.value
        else:
            configmap[item.key] = item.value
    return configmap, secret


def render_namespace(config: UserConfig) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": config.namespace,
            "labels": _labels(config.app_name),
        },
    }


def render_pvc(config: UserConfig) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "accessModes": config.pvc.access_modes,
        "resources": {"requests": {"storage": config.pvc.size}},
    }
    if config.pvc.storage_class_name:
        spec["storageClassName"] = config.pvc.storage_class_name
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": config.pvc.name,
            "namespace": config.namespace,
            "labels": _labels(config.app_name),
        },
        "spec": spec,
    }


def render_configmap(config: UserConfig, data: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"{config.app_name}-config",
            "namespace": config.namespace,
            "labels": _labels(config.app_name),
        },
        "data": data,
    }


def render_secret(config: UserConfig, data: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{config.app_name}-secret",
            "namespace": config.namespace,
            "labels": _labels(config.app_name),
        },
        "type": "Opaque",
        "stringData": data,
    }


def _resources_block(config: UserConfig) -> dict[str, Any] | None:
    if not config.resources:
        return None
    requests: dict[str, str] = {}
    limits: dict[str, str] = {}
    if config.resources.requests_cpu:
        requests["cpu"] = config.resources.requests_cpu
    if config.resources.requests_memory:
        requests["memory"] = config.resources.requests_memory
    if config.resources.limits_cpu:
        limits["cpu"] = config.resources.limits_cpu
    if config.resources.limits_memory:
        limits["memory"] = config.resources.limits_memory
    if not requests and not limits:
        return None
    resources: dict[str, Any] = {}
    if requests:
        resources["requests"] = requests
    if limits:
        resources["limits"] = limits
    return resources


def render_deployment(
    config: UserConfig,
    configmap_data: dict[str, str],
    secret_name: str,
    sensitive_env_keys: list[str],
) -> dict[str, Any]:
    labels = _labels(config.app_name)
    configmap_name = f"{config.app_name}-config" if configmap_data else None

    main_container_env: list[dict[str, Any]] = []
    main_env_from: list[dict[str, Any]] = []
    if configmap_name:
        main_env_from.append({"configMapRef": {"name": configmap_name}})

    for key in sensitive_env_keys:
        main_container_env.append({
            "name": key,
            "valueFrom": {"secretKeyRef": {"name": secret_name, "key": key}},
        })

    main_container: dict[str, Any] = {
        "name": "app",
        "image": config.image,
        "volumeMounts": [{"name": "data", "mountPath": config.pvc.mount_path}],
    }
    if config.ports:
        main_container["ports"] = [
            {"containerPort": p.container_port, "protocol": p.protocol, "name": p.name} for p in config.ports
        ]
    resources = _resources_block(config)
    if resources:
        main_container["resources"] = resources
    if main_container_env:
        main_container["env"] = main_container_env
    if main_env_from:
        main_container["envFrom"] = main_env_from

    file_manager_env: list[dict[str, Any]] = [
        {
            "name": "FB_USERNAME",
            "valueFrom": {"secretKeyRef": {"name": secret_name, "key": "FB_USERNAME"}},
        },
        {
            "name": "FB_PASSWORD",
            "valueFrom": {"secretKeyRef": {"name": secret_name, "key": "FB_PASSWORD"}},
        },
        {"name": "FB_ROOT", "value": config.pvc.mount_path},
        {"name": "FB_ADDRESS", "value": "0.0.0.0"},
        {"name": "FB_PORT", "value": str(config.file_manager.port)},
        {"name": "FB_DATABASE", "value": f"{config.pvc.mount_path}/.filebrowser.db"},
    ]

    file_manager_container = {
        "name": "file-manager",
        "image": config.file_manager.image,
        "env": file_manager_env,
        "ports": [
            {
                "containerPort": config.file_manager.port,
                "protocol": "TCP",
                "name": normalize_port_name("file-ui"),
            }
        ],
        "volumeMounts": [{"name": "data", "mountPath": config.pvc.mount_path}],
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": config.app_name,
            "namespace": config.namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app.kubernetes.io/name": config.app_name}},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [main_container, file_manager_container],
                    "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": config.pvc.name}}],
                },
            },
        },
    }


def render_service(config: UserConfig) -> dict[str, Any]:
    ports: list[dict[str, Any]] = []
    for spec in config.ports:
        ports.append({
            "name": spec.name,
            "port": spec.container_port,
            "targetPort": spec.container_port,
            "protocol": spec.protocol,
        })
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": config.app_name,
            "namespace": config.namespace,
            "labels": _labels(config.app_name),
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"app.kubernetes.io/name": config.app_name},
            "ports": ports,
        },
    }


def render_file_manager_service(config: UserConfig) -> dict[str, Any]:
    ports: list[dict[str, Any]] = [
        {
            "name": normalize_port_name("file-ui"),
            "port": config.file_manager.port,
            "targetPort": config.file_manager.port,
            "protocol": "TCP",
        }
    ]
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": f"{config.app_name}-ftp",
            "namespace": config.namespace,
            "labels": _labels(config.app_name),
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"app.kubernetes.io/name": config.app_name},
            "ports": ports,
        },
    }


def render_all(config: UserConfig, secret_filename: str = "secret.yaml") -> dict[str, dict[str, Any]]:
    configmap_data, secret_env = _split_env(config.env)

    secret_data = {
        "FB_USERNAME": config.file_manager.username,
        "FB_PASSWORD": config.file_manager.password_hash,
    }
    secret_data.update(secret_env)
    secret_name = f"{config.app_name}-secret"

    manifests: dict[str, dict[str, Any]] = {
        "namespace.yaml": render_namespace(config),
        "pvc.yaml": render_pvc(config),
    }
    if configmap_data:
        manifests["configmap.yaml"] = render_configmap(config, configmap_data)
    manifests[secret_filename] = render_secret(config, secret_data)
    manifests["deployment.yaml"] = render_deployment(config, configmap_data, secret_name, list(secret_env.keys()))
    if config.ports:
        manifests["service.yaml"] = render_service(config)
    manifests["ftp-service.yaml"] = render_file_manager_service(config)
    return manifests
