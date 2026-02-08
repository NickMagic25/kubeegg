import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from kubeegg.api import app
from kubeegg.fetch import FetchResult

client = TestClient(app)

SAMPLE_EGG = {
    "name": "Minecraft",
    "description": "Minecraft Java Edition",
    "startup": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar server.jar",
    "docker_images": {"default": "ghcr.io/pterodactyl/yolks:java_17"},
    "variables": [
        {
            "name": "Server Port",
            "env_variable": "SERVER_PORT",
            "description": "The port the server listens on",
            "default_value": "25565",
            "required": True,
        },
        {
            "name": "Server Name",
            "env_variable": "SERVER_NAME",
            "description": "Display name",
            "default_value": "My Server",
            "required": False,
        },
    ],
    "config": {"ports": [25565]},
    "scripts": {
        "installation": {
            "script": "#!/bin/bash\necho install",
            "container": "alpine:3.18",
            "entrypoint": "bash",
        }
    },
}


def test_requirements_success():
    with patch("kubeegg.api.load_egg_json") as mock_fetch:
        mock_fetch.return_value = FetchResult(
            data=SAMPLE_EGG, source="test.json", resolved_source="test.json"
        )
        resp = client.post("/requirements", json={"source": "test.json"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Minecraft"
    assert body["startup"] == "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar server.jar"
    assert body["docker_images"] == {"default": "ghcr.io/pterodactyl/yolks:java_17"}
    assert len(body["variables"]) == 2
    assert body["variables"][0]["env_variable"] == "SERVER_PORT"
    assert body["variables"][0]["required"] is True
    assert 25565 in body["ports"]
    assert body["install_script"] == "#!/bin/bash\necho install"
    assert body["install_image"] == "alpine:3.18"
    assert body["install_entrypoint"] == "bash"


def test_requirements_fetch_failure():
    with patch("kubeegg.api.load_egg_json") as mock_fetch:
        mock_fetch.side_effect = RuntimeError("connection refused")
        resp = client.post("/requirements", json={"source": "http://bad-url"})

    assert resp.status_code == 502
    assert "connection refused" in resp.json()["detail"]


def test_requirements_missing_source():
    resp = client.post("/requirements", json={})
    assert resp.status_code == 422


def test_requirements_minimal_egg():
    minimal = {"docker_images": {"default": "nginx:latest"}}
    with patch("kubeegg.api.load_egg_json") as mock_fetch:
        mock_fetch.return_value = FetchResult(
            data=minimal, source="min.json", resolved_source="min.json"
        )
        resp = client.post("/requirements", json={"source": "min.json"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] is None
    assert body["docker_images"] == {"default": "nginx:latest"}
    assert body["variables"] == []
    assert body["ports"] == []
