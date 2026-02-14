import hashlib

from kubeegg.models import EnvSelection, FileManagerConfig, InstallConfig, PVCSpec, PortSpec, ResourceValues, UserConfig
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


def _make_install_config(script="echo install"):
    version_hash = hashlib.sha256(script.encode()).hexdigest()[:8]
    return UserConfig(
        app_name="mygame",
        namespace="mygame",
        image="example/image:latest",
        pvc=PVCSpec(
            name="mygame-data",
            size="10Gi",
            mount_path="/home/container",
            access_modes=["ReadWriteMany"],
            storage_class_name=None,
        ),
        env=[
            EnvSelection(key="MODE", value="survival", sensitive=False),
        ],
        ports=[
            PortSpec(container_port=27015, protocol="TCP", name="game-27015"),
        ],
        file_manager=FileManagerConfig(image="hurlenko/filebrowser:latest", port=8080),
        install=InstallConfig(
            image="alpine:3.19",
            entrypoint="ash",
            script=script,
            version_hash=version_hash,
        ),
    )


def test_installer_job_generated():
    config = _make_install_config()
    manifests = render_all(config)

    assert "installer-job.yaml" in manifests
    job = manifests["installer-job.yaml"]
    assert job["apiVersion"] == "batch/v1"
    assert job["kind"] == "Job"
    assert config.install.version_hash in job["metadata"]["name"]
    assert job["metadata"]["name"] == f"mygame-installer-{config.install.version_hash}"
    assert job["spec"]["backoffLimit"] == 3
    assert job["spec"]["template"]["spec"]["restartPolicy"] == "OnFailure"

    container = job["spec"]["template"]["spec"]["containers"][0]
    assert container["name"] == "installer"
    assert container["image"] == "alpine:3.19"
    assert container["command"] == ["ash", "/kubeegg-installer/install.sh"]
    mount_names = {m["name"] for m in container["volumeMounts"]}
    assert "data" in mount_names
    assert "installer" in mount_names

    volumes = job["spec"]["template"]["spec"]["volumes"]
    volume_names = {v["name"] for v in volumes}
    assert "data" in volume_names
    assert "installer" in volume_names


def test_deployment_has_wait_for_install_init_container():
    config = _make_install_config()
    manifests = render_all(config)

    deployment = manifests["deployment.yaml"]
    init_containers = deployment["spec"]["template"]["spec"].get("initContainers", [])
    assert len(init_containers) == 1

    wait = init_containers[0]
    assert wait["name"] == "wait-for-install"
    assert wait["image"] == "busybox:1.37"
    assert config.install.version_hash in wait["command"][2]
    assert f".kubeegg_installed_{config.install.version_hash}" in wait["command"][2]

    mount_names = {m["name"] for m in wait["volumeMounts"]}
    assert "data" in mount_names


def test_deployment_no_full_installer_init_container():
    config = _make_install_config()
    manifests = render_all(config)

    deployment = manifests["deployment.yaml"]
    init_containers = deployment["spec"]["template"]["spec"].get("initContainers", [])
    assert not any(c["name"] == "installer" for c in init_containers)

    volume_names = {v["name"] for v in deployment["spec"]["template"]["spec"]["volumes"]}
    assert "installer" not in volume_names


def test_installer_job_version_hash_changes_with_script():
    config_a = _make_install_config(script="echo install_v1")
    config_b = _make_install_config(script="echo install_v2")

    manifests_a = render_all(config_a)
    manifests_b = render_all(config_b)

    job_a = manifests_a["installer-job.yaml"]
    job_b = manifests_b["installer-job.yaml"]
    assert job_a["metadata"]["name"] != job_b["metadata"]["name"]


def test_no_install_no_init_containers():
    config = UserConfig(
        app_name="plain",
        namespace="plain",
        image="example/image:latest",
        pvc=PVCSpec(
            name="plain-data",
            size="5Gi",
            mount_path="/data",
            access_modes=["ReadWriteOnce"],
            storage_class_name=None,
        ),
        env=[],
        ports=[],
        file_manager=FileManagerConfig(image="hurlenko/filebrowser:latest", port=8080),
    )
    manifests = render_all(config)
    deployment = manifests["deployment.yaml"]
    assert "initContainers" not in deployment["spec"]["template"]["spec"]
    assert "installer-job.yaml" not in manifests
