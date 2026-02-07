# kubeegg

`kubeegg` is a terminal CLI that converts a Pelican / Pterodactyl game egg JSON into a Kustomize-ready Kubernetes manifest set.

## Status Checks

[![CI](https://github.com/NickMagic25/kubeegg/actions/workflows/ci.yml/badge.svg)](https://github.com/NickMagic25/kubeegg/actions/workflows/ci.yml) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=NickMagic25_kubeegg&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=NickMagic25_kubeegg)

## Build & Install (Required)

```bash
uv sync
uv build
uv tool install dist/*.whl
```

Verify:

```bash
kubeegg --help
```

## Usage

```bash
kubeegg <URL-or-path-to-egg.json>
```

Examples:

```bash
kubeegg egg-paper.json
kubeegg https://github.com/pterodactyl/game-eggs/blob/main/minecraft/java/paper/egg-paper.json
```

By default, manifests are written into the current directory. To write to another existing directory:

```bash
kubeegg <egg.json> --out ./some/path
```

To write the Secret as a SOPS-compatible filename:

```bash
kubeegg <egg.json> --sops
```

## Output

The following files are generated in the output directory:

- `kustomization.yaml`
- `namespace.yaml`
- `pvc.yaml`
- `fm-config-pvc.yaml` (file manager config PVC)
- `deployment.yaml`
- `ftp-deployment.yaml` (file manager deployment)
- `service.yaml`
- `ftp-service.yaml` (file manager web UI Service)
- `configmap.yaml` (only if non-sensitive env vars are provided)
- `secret.yaml` (only if sensitive env vars are provided)
- `installer-configmap.yaml` (only if an egg installer script is enabled)

## Notes

- All Services are `ClusterIP` only.
- Storage uses a ReadWriteMany PVC for game data, plus a separate 1Gi ReadWriteOnce PVC mounted at `/config` for the file manager.
- The sidecar exposes a single web UI port for file uploads/downloads.
- No Ingress, Gateway, or LoadBalancer resources are created.
- File manager credentials are not injected; manage users via the file manager UI.
- File manager mounts the PVC at `/data` and `/config` per the image's expectations. citeturn0view0
- Pod security context sets RuntimeDefault seccomp and drops all capabilities. Both pods run as non-root UID/GID 1000 with fsGroup 1000.
- Egg startup commands are exposed via a `STARTUP` environment variable when available.
- If the startup command contains `{{SERVER_MEMORY}}` and a memory limit is set, kubeegg replaces it with the limit (in MB).
- If an egg contains an installer script, kubeegg can add an initContainer that runs it once (guarded by a marker file in the PVC).
- Manifests are deterministic and GitOps-friendly.

[![SonarQube Cloud](https://sonarcloud.io/images/project_badges/sonarcloud-highlight.svg)](https://sonarcloud.io/summary/new_code?id=NickMagic25_kubeegg)
