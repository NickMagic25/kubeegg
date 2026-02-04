from __future__ import annotations

from typing import Any

from .models import EnvSelection, PortSpec, UserConfig
from .util import memory_to_mb, normalize_port_name


def _labels(app_name: str, component: str | None = None) -> dict[str, str]:
    labels = {
        "app.kubernetes.io/name": app_name,
        "app.kubernetes.io/managed-by": "kubeegg",
    }
    if component:
        labels["app.kubernetes.io/component"] = component
    return labels


def _selector_labels(app_name: str, component: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/name": app_name,
        "app.kubernetes.io/component": component,
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


def render_file_manager_config_pvc(config: UserConfig) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "accessModes": ["ReadWriteOnce"],
        "resources": {"requests": {"storage": "1Gi"}},
    }
    if config.pvc.storage_class_name:
        spec["storageClassName"] = config.pvc.storage_class_name
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": f"{config.app_name}-fm-config",
            "namespace": config.namespace,
            "labels": _labels(config.app_name, component="file-manager"),
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


def _wrap_install_script(script: str) -> str:
    return "\n".join(
        [
            "#!/bin/sh",
            "# Note: set -e is intentionally omitted because Pterodactyl egg scripts",
            "# use grep for condition checks, which returns exit code 1 on no match.",
            "MARKER=/mnt/server/.kubeegg_installed",
            "if [ -f \"$MARKER\" ]; then",
            "  echo \"Installer already completed.\"",
            "  exit 0",
            "fi",
            script.strip(),
            "touch \"$MARKER\"",
        ]
    )


def render_installer_configmap(config: UserConfig) -> dict[str, Any]:
    script = _wrap_install_script(config.install.script)
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"{config.app_name}-installer",
            "namespace": config.namespace,
            "labels": _labels(config.app_name, component="installer"),
        },
        "data": {
            "install.sh": script,
        },
    }


def _build_init_container(
    config: UserConfig,
    configmap_name: str | None,
    secret_name: str,
) -> dict[str, Any]:
    install = config.install
    command = [install.entrypoint or "sh", "/kubeegg-installer/install.sh"]
    env_from: list[dict[str, Any]] = []
    if configmap_name:
        env_from.append({"configMapRef": {"name": configmap_name}})
    env_from.append({"secretRef": {"name": secret_name}})
    init_container: dict[str, Any] = {
        "name": "installer",
        "image": install.image,
        "command": command,
        "envFrom": env_from,
        "volumeMounts": [
            {"name": "data", "mountPath": "/mnt/server"},
            {"name": "installer", "mountPath": "/kubeegg-installer"},
        ],
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
        },
    }
    return init_container


def render_deployment(
    config: UserConfig,
    configmap_data: dict[str, str],
    secret_name: str,
    sensitive_env_keys: list[str],
) -> dict[str, Any]:
    labels = _labels(config.app_name, component="game")
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
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
        },
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
            "selector": {"matchLabels": _selector_labels(config.app_name, "game")},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "securityContext": {
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [main_container],
                    "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": config.pvc.name}}],
                },
            },
        },
    }


def render_file_manager_deployment(
    config: UserConfig,
    secret_name: str,
) -> dict[str, Any]:
    labels = _labels(config.app_name, component="file-manager")
    file_manager_env: list[dict[str, Any]] = [
        {
            "name": "FB_USERNAME",
            "valueFrom": {"secretKeyRef": {"name": secret_name, "key": "FB_USERNAME"}},
        },
        {
            "name": "FB_PASSWORD",
            "valueFrom": {"secretKeyRef": {"name": secret_name, "key": "FB_PASSWORD"}},
        },
        {"name": "FB_ROOT", "value": "/data"},
        {"name": "FB_ADDRESS", "value": "0.0.0.0"},
        {"name": "FB_PORT", "value": str(config.file_manager.port)},
        {"name": "FB_DATABASE", "value": "/config/filebrowser.db"},
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
        "volumeMounts": [
            {"name": "data", "mountPath": "/data"},
            {"name": "config", "mountPath": "/config"},
        ],
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "runAsNonRoot": True,
        },
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"{config.app_name}-ftp",
            "namespace": config.namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": _selector_labels(config.app_name, "file-manager")},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "securityContext": {
                        "seccompProfile": {"type": "RuntimeDefault"},
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "fsGroup": 1000,
                    },
                    "containers": [file_manager_container],
                    "volumes": [
                        {"name": "data", "persistentVolumeClaim": {"claimName": config.pvc.name}},
                        {"name": "config", "persistentVolumeClaim": {"claimName": f"{config.app_name}-fm-config"}},
                    ],
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
            "labels": _labels(config.app_name, component="game"),
        },
        "spec": {
            "type": "ClusterIP",
            "selector": _selector_labels(config.app_name, "game"),
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
            "labels": _labels(config.app_name, component="file-manager"),
        },
        "spec": {
            "type": "ClusterIP",
            "selector": _selector_labels(config.app_name, "file-manager"),
            "ports": ports,
        },
    }


def render_all(config: UserConfig, secret_filename: str = "secret.yaml") -> dict[str, dict[str, Any]]:
    configmap_data, secret_env = _split_env(config.env)
    if config.startup_command:
        startup = config.startup_command
        if "{{SERVER_MEMORY}}" in startup and config.resources and config.resources.limits_memory:
            mb = memory_to_mb(config.resources.limits_memory)
            if mb:
                startup = startup.replace("{{SERVER_MEMORY}}", str(mb))
        configmap_data = dict(configmap_data)
        configmap_data["STARTUP"] = startup

    secret_data = {
        "FB_USERNAME": config.file_manager.username,
        "FB_PASSWORD": config.file_manager.password,
    }
    secret_data.update(secret_env)
    secret_name = f"{config.app_name}-secret"

    manifests: dict[str, dict[str, Any]] = {
        "namespace.yaml": render_namespace(config),
        "pvc.yaml": render_pvc(config),
    }
    manifests["fm-config-pvc.yaml"] = render_file_manager_config_pvc(config)
    if configmap_data:
        manifests["configmap.yaml"] = render_configmap(config, configmap_data)
    manifests[secret_filename] = render_secret(config, secret_data)
    if config.install:
        manifests["installer-configmap.yaml"] = render_installer_configmap(config)
    deployment = render_deployment(config, configmap_data, secret_name, list(secret_env.keys()))
    if config.install:
        configmap_name = f"{config.app_name}-config" if configmap_data else None
        init_container = _build_init_container(config, configmap_name, secret_name)
        deployment["spec"]["template"]["spec"]["initContainers"] = [init_container]
        volumes = deployment["spec"]["template"]["spec"]["volumes"]
        volumes.append(
            {
                "name": "installer",
                "configMap": {"name": f"{config.app_name}-installer"},
            }
        )
    manifests["deployment.yaml"] = deployment
    manifests["ftp-deployment.yaml"] = render_file_manager_deployment(config, secret_name)
    if config.ports:
        manifests["service.yaml"] = render_service(config)
    manifests["ftp-service.yaml"] = render_file_manager_service(config)
    return manifests
