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
            username="admin",
            password_hash="$2b$12$exampleexampleexampleexamplE5QzCOpR1vG9Q2o/UVUqqNn7hRy",
            port=8080,
        ),
        resources=ResourceValues(requests_cpu="100m", requests_memory="256Mi"),
    )

    manifests = render_all(config)

    assert "deployment.yaml" in manifests
    assert "pvc.yaml" in manifests
    assert "service.yaml" in manifests
    assert "ftp-service.yaml" in manifests
    assert "secret.yaml" in manifests
    assert "configmap.yaml" in manifests

    deployment = manifests["deployment.yaml"]
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert any(c["name"] == "app" for c in containers)
    assert any(c["name"] == "file-manager" for c in containers)

    secret = manifests["secret.yaml"]
    assert secret["stringData"]["FB_USERNAME"] == "admin"
    assert secret["stringData"]["SECRET_VAR"] == "bar"

    service = manifests["service.yaml"]
    assert service["spec"]["type"] == "ClusterIP"
    assert service["spec"]["ports"][0]["port"] == 25565

    file_service = manifests["ftp-service.yaml"]
    assert file_service["spec"]["ports"][0]["port"] == 8080
