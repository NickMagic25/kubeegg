from kubeegg.models import EnvSelection, FileManagerConfig, PVCSpec, PortSpec, ResourceValues, UserConfig
from kubeegg.render import render_all


def test_render_all_outputs():
    config = UserConfig(
        app_name="demo",
        namespace="demo",
        image="example/image:latest",
        pvc=PVCSpec(
            name="demo-data",
            size="10Gi",
            mount_path="/data",
            access_modes=["ReadWriteOnce"],
            storage_class_name=None,
        ),
        env=[
            EnvSelection(key="PUBLIC_VAR", value="foo", sensitive=False),
            EnvSelection(key="SECRET_VAR", value="bar", sensitive=True),
        ],
        ports=[
            PortSpec(container_port=25565, protocol="TCP", name="game-25565"),
        ],
        file_manager=FileManagerConfig(
            image="hurlenko/filebrowser:latest",
            port=8080,
        ),
        startup_command="java -Xmx{{SERVER_MEMORY}}M -jar server.jar",
        resources=ResourceValues(requests_cpu="100m", requests_memory="256Mi", limits_memory="6Gi"),
    )

    manifests = render_all(config)

    assert "deployment.yaml" in manifests
    assert "ftp-deployment.yaml" in manifests
    assert "pvc.yaml" in manifests
    assert "fm-config-pvc.yaml" in manifests
    assert "service.yaml" in manifests
    assert "ftp-service.yaml" in manifests
    assert "secret.yaml" in manifests
    assert "configmap.yaml" in manifests

    deployment = manifests["deployment.yaml"]
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert any(c["name"] == "app" for c in containers)

    fm_deployment = manifests["ftp-deployment.yaml"]
    fm_containers = fm_deployment["spec"]["template"]["spec"]["containers"]
    assert any(c["name"] == "file-manager" for c in fm_containers)

    secret = manifests["secret.yaml"]
    assert secret["stringData"]["SECRET_VAR"] == "bar"

    configmap = manifests["configmap.yaml"]
    assert configmap["data"]["STARTUP"] == "java -Xmx6144M -jar server.jar"

    service = manifests["service.yaml"]
    assert service["spec"]["type"] == "ClusterIP"
    assert service["spec"]["ports"][0]["port"] == 25565

    file_service = manifests["ftp-service.yaml"]
    assert file_service["spec"]["ports"][0]["port"] == 8080

    fm_config_pvc = manifests["fm-config-pvc.yaml"]
    assert fm_config_pvc["spec"]["resources"]["requests"]["storage"] == "1Gi"
    assert "ReadWriteOnce" in fm_config_pvc["spec"]["accessModes"]

    fm_deployment = manifests["ftp-deployment.yaml"]
    fm_container = fm_deployment["spec"]["template"]["spec"]["containers"][0]
    env_names = {item["name"] for item in fm_container["env"]}
    assert "FB_ROOT" in env_names
    assert "FB_DATABASE" in env_names
    mounts = {m["mountPath"] for m in fm_container["volumeMounts"]}
    assert "/data" in mounts
    assert "/config" in mounts
    config_mount = next(m for m in fm_container["volumeMounts"] if m["mountPath"] == "/config")
    assert "readOnly" not in config_mount
