# kubeegg

`kubeegg` is a terminal CLI that converts a Pelican / Pterodactyl game egg JSON into a Kustomize-ready Kubernetes manifest set.

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
- `deployment.yaml`
- `service.yaml`
- `ftp-service.yaml` (file manager web UI Service)
- `configmap.yaml` (only if non-sensitive env vars are provided)
- `secret.yaml` (always includes file manager credentials; also includes sensitive env vars)

## Notes

- All Services are `ClusterIP` only.
- Storage uses a ReadWriteMany PVC mounted into both the game container and the file manager sidecar.
- The sidecar exposes a single web UI port for file uploads/downloads.
- No Ingress, Gateway, or LoadBalancer resources are created.
- File manager credentials are stored in the Secret as File Browser-compatible values.
- Manifests are deterministic and GitOps-friendly.
