from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


def test_compose_is_local_only_and_persists_data():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    service = compose["services"]["worthit"]

    assert service["ports"] == ["127.0.0.1:5000:5000"]
    assert "worthit_data:/app/data" in service["volumes"]
    assert service["env_file"] == [".env"]
    assert "no-new-privileges:true" in service["security_opt"]


def test_docker_build_context_excludes_private_and_generated_data():
    ignored = set((ROOT / ".dockerignore").read_text().splitlines())

    assert {".env", "data", ".git", ".venv", "*.db"} <= ignored
    assert "!.env.example" in ignored


def test_container_uses_non_root_single_worker_runtime():
    dockerfile = (ROOT / "Dockerfile").read_text()
    entrypoint = (ROOT / "scripts" / "container_entrypoint.sh").read_text()

    assert "USER worthit" in dockerfile
    assert "python scripts/check_config.py" in entrypoint
    assert "--workers 1" in entrypoint
