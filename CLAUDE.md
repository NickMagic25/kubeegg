# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`kubeegg` is a Python CLI tool that converts Pterodactyl/Pelican game server "egg" JSON files into production-ready Kubernetes manifests with Kustomize support. The tool generates a complete set of manifests including deployments, services, PVCs, and an optional file manager sidecar for web-based file uploads/downloads.

## Build & Development Commands

```bash
# Initial setup - sync dependencies and build
uv sync
uv build

# Install the CLI tool locally
uv tool install dist/*.whl

# Verify installation
kubeegg --help

# Run tests
pytest

# Run a specific test
pytest tests/test_egg.py::test_parse_egg_basic -v
```

## Architecture

### Entry Point Flow

1. **CLI (`cli.py`)** - Typer-based command-line interface that:
   - Validates output directory
   - Calls `fetch.py` to load egg JSON (from URL or local file)
   - Calls `egg.py` to parse the egg JSON into structured models
   - Calls `prompts.py` to interactively collect user configuration
   - Calls `render.py` to generate Kubernetes manifests
   - Writes YAML files using ruamel.yaml

2. **Fetch (`fetch.py`)** - Handles egg JSON loading:
   - Detects if source is URL or local file path
   - Converts GitHub blob URLs to raw.githubusercontent.com URLs
   - Returns `FetchResult` with parsed JSON data

3. **Egg Parser (`egg.py`)** - Extracts structured data from various egg JSON formats:
   - Handles multiple field name variations (snake_case, camelCase)
   - Extracts Docker images from multiple possible locations
   - Parses environment variables from `variables` array or `environment` dict
   - Infers ports from `config.ports`, `ports`, and PORT-related env vars
   - Extracts optional installer scripts from `scripts.installation`

4. **Prompts (`prompts.py`)** - Interactive user configuration:
   - Collects app name, namespace, image selection
   - Prompts for PVC configuration (name, size, mount path, storage class)
   - Interactively configures environment variables with sensitivity detection
   - Prompts for port specifications and protocols
   - Configures file manager sidecar settings
   - Optionally collects CPU/memory resource limits

5. **Render (`render.py`)** - Generates Kubernetes manifests:
   - Splits env vars into ConfigMap (non-sensitive) and Secret (sensitive)
   - Handles `{{SERVER_MEMORY}}` placeholder substitution in startup commands
   - Generates main game deployment with optional initContainer for installer script
   - Generates separate file manager deployment with dual PVC mounts
   - Creates ClusterIP Services for game and file manager
   - Applies security contexts: RuntimeDefault seccomp, non-root UID/GID 1000, drops all capabilities

### Data Models (`models.py`)

Core data structures:
- **Egg** - Parsed egg JSON (name, startup, docker_images, variables, ports, install_script)
- **UserConfig** - Complete user-provided configuration for manifest generation
- **EnvSelection** - Environment variable with sensitivity flag
- **PortSpec** - Port configuration (container_port, protocol, name)
- **PVCSpec** - PVC configuration (name, size, mount_path, access_modes, storage_class_name)
- **InstallConfig** - Optional installer script configuration
- **FileManagerConfig** - File manager sidecar configuration

### Manifest Generation Strategy

The tool generates deterministic, GitOps-friendly manifests:
- **Two Deployments**: Main game container + file manager sidecar (separate deployments to avoid restart coupling)
- **Two PVCs**: ReadWriteMany for game data + ReadWriteOnce (1Gi) for file manager config
- **Security Hardening**: RuntimeDefault seccomp, non-root UID/GID 1000, fsGroup 1000, all capabilities dropped
- **Optional initContainer**: Runs installer script once (guarded by `.kubeegg_installed` marker file)
- **No Ingress/Gateway**: Only ClusterIP services (user must configure ingress separately)
- **SOPS Support**: Can write Secret as `secrets.sops.yaml` via `--sops` flag

### Key Design Decisions

1. **Dual PVC Strategy**: Separate PVCs for game data (RWX) and file manager config (RWO) to support shared storage patterns while keeping file manager state isolated
2. **Separate Deployments**: Game and file manager are separate deployments to avoid restarting game server when file manager is updated
3. **Installer Script Wrapping**: Installer scripts are wrapped with marker file logic to run only once, even if pod restarts
4. **No set -e in Installer**: Pterodactyl egg scripts use grep for conditionals which return exit code 1, so set -e is intentionally omitted
5. **Startup Command as Env Var**: Startup commands are exposed as `STARTUP` env var rather than overriding entrypoint
6. **Sensitivity Detection**: Env vars with PASS/SECRET/TOKEN/KEY are automatically flagged as sensitive, with forced secrets for FTP_USERNAME/FTP_PASSWORD

## Common Workflows

### Adding New Manifest Types

To add a new manifest type:
1. Add a `render_<resource>()` function in `render.py`
2. Add the manifest to the return dict in `render_all()`
3. Update the filename list in `cli.py` if needed

### Modifying Egg Parsing

To support new egg JSON field variations:
1. Update extraction logic in `egg.py` (_extract_images, _extract_variables, etc.)
2. Add test case in `tests/test_egg.py`
3. Ensure backward compatibility with existing egg formats

### Testing Changes

Run full test suite with `pytest`. Tests cover:
- Egg JSON parsing with various formats
- Fetch logic for URLs and local files
- Manifest rendering with different configurations
