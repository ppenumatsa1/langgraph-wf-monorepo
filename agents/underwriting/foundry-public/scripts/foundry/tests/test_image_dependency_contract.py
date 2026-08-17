from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_runtime_manifests_include_langgraph_postgres_dependencies() -> None:
    for manifest in (ROOT / "pyproject.toml", ROOT / "backend" / "pyproject.toml"):
        text = manifest.read_text(encoding="utf-8")
        assert '"langgraph==1.2.10"' in text
        assert '"langgraph-checkpoint-postgres==3.1.2"' in text
        assert '"psycopg-pool>=3.2.6,<4.0.0"' in text
        assert "agent-framework-" not in text


def test_images_fail_build_when_runtime_imports_are_missing() -> None:
    backend_dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    hosted_dockerfile = (ROOT / "backend" / "Dockerfile.hosted").read_text(encoding="utf-8")
    sync_script = (ROOT / "scripts" / "foundry" / "sync_hosted_source.sh").read_text(
        encoding="utf-8"
    )

    assert "COPY backend/pyproject.toml /app/pyproject.toml" in backend_dockerfile
    assert 'python -c "import langgraph, psycopg_pool"' in backend_dockerfile
    assert "PYTHONPATH=/app/backend" in hosted_dockerfile
    assert 'python -c "import foundry.main, langgraph, psycopg_pool"' in hosted_dockerfile
    assert 'cp "$ROOT_DIR/backend/pyproject.toml" "$TARGET_DIR/"' in sync_script


def test_release_builds_changed_images_in_acr_and_reuses_verified_digests() -> None:
    build_script = (ROOT / "scripts" / "foundry" / "build_release_images.sh").read_text(
        encoding="utf-8"
    )

    assert 'build_acr_image \\\n    "$frontend_repository"' in build_script
    assert "az acr login" not in build_script
    assert "docker push" not in build_script
    assert "validate_prebuilt_image" in build_script
    assert "source_fingerprint" in build_script
    assert "source-${source_fingerprint}" in build_script
    assert "bound to the current" in build_script
    assert 'if [[ -z "$prebuilt_backend" ]]' in build_script
    assert 'if [[ -z "$prebuilt_frontend" ]]' in build_script
    assert 'if [[ -z "$prebuilt_hosted" ]]' in build_script
    assert "Reused verified immutable backend, frontend, and hosted-agent images." in build_script
