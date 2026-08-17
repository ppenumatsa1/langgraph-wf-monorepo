from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_azure_yaml_has_only_two_container_app_services() -> None:
    azure_yaml = read("azure.yaml")
    assert azure_yaml.count("host: containerapp") == 2
    assert "azure.ai.agent" not in azure_yaml
    assert "order-resolution-hosted" not in azure_yaml


def test_release_has_no_hosted_agent_leg() -> None:
    release = read("scripts/azure/release.sh")
    makefile = read("Makefile")
    assert "deploy_hosted" not in release
    assert "hosted-agent" not in release
    assert "azure.ai.agent" not in makefile
    assert "azure-release" in makefile


def test_topology_and_release_gates_are_wired() -> None:
    apps = read("infra/azure-apphosted/iac/modules/container-apps.bicep")
    release = read("scripts/azure/release.sh")
    assert "external: false" in apps
    assert "external: true" in apps
    assert "NGINX_API_UPSTREAM" in apps
    for gate in (
        "preflight",
        "model_preflight",
        "images",
        "deployment",
        "verification",
        "smoke",
        "domain_e2e",
        "browser_e2e",
        "evaluation",
        "telemetry",
    ):
        assert f"timed {gate}" in release


def test_postgres_dual_auth_and_public_poc_guardrails() -> None:
    postgres = read("infra/azure-apphosted/iac/modules/postgres.bicep")
    main = read("infra/azure-apphosted/iac/main.bicep")
    parameters = read("infra/azure-apphosted/iac/main.parameters.json")
    verification = read("scripts/azure/verify_deployment.sh")
    assert "activeDirectoryAuth: 'Enabled'" in postgres
    assert "passwordAuth: 'Enabled'" in postgres
    assert "administratorLoginPassword: serverAdministratorPassword" in postgres
    assert "@secure()" in main
    assert "POSTGRES_SERVER_ADMIN_PASSWORD" in parameters
    assert "public-poc-allow-azure-services" in postgres
    assert "require_secure_transport" in verification
    assert "postgres_dual_auth:true" in verification


def test_backend_is_single_replica_until_distributed_hitl_locking() -> None:
    apps = read("infra/azure-apphosted/iac/modules/container-apps.bicep")
    deployment = read("scripts/azure/deploy_apps.sh")
    verification = read("scripts/azure/verify_deployment.sh")
    backend_section = apps.split("resource backend ", 1)[1].split("resource frontend ", 1)[0]
    assert "distributed" in backend_section
    assert "maxReplicas: 1" in backend_section
    assert "--max-replicas 1" in deployment
    assert ".properties.template.scale.maxReplicas" in verification
    assert "backend_max_replicas:1" in verification


def test_domain_e2e_timestamp_covers_the_executed_workflows() -> None:
    matrix = read("scripts/manual/run_manual_matrix.py")
    telemetry = read("scripts/azure/verify_telemetry.sh")
    foundry_eval = read("backend/evals/foundry_eval_runner.py")
    assert 'started_at = datetime.now(timezone.utc).isoformat()' in matrix
    assert '"started_at": started_at' in matrix
    assert "'.started_at // empty'" in telemetry
    assert '_parse_evidence_timestamp(payload, "started_at")' in foundry_eval


def test_live_verification_requires_exact_apps_and_no_foundry_agents() -> None:
    verification = read("scripts/azure/verify_deployment.sh")
    assert "az containerapp list" in verification
    assert "must contain exactly the expected backend and frontend" in verification
    assert "/agents?api-version=2025-05-15-preview" in verification
    assert '--resource "https://ai.azure.com"' in verification
    assert '[[ "$hosted_agent_count" == "0" ]]' in verification
    assert "hosted_agent_applications:0" in verification
    assert "hosted_agent_versions:0" in verification


def test_bootstrap_generates_server_admin_secret_in_local_azd_state() -> None:
    bootstrap = read("scripts/azure/bootstrap.sh")
    provision = read("scripts/azure/provision_infrastructure.sh")
    postgres = read("infra/azure-apphosted/iac/modules/postgres.bicep")
    assert "secrets.SystemRandom().shuffle" in bootstrap
    assert "azd env set POSTGRES_SERVER_ADMIN_PASSWORD" in bootstrap
    assert "postgres_server_admin_password" in bootstrap
    assert "AZURE_BOOTSTRAP_APPROVED" not in bootstrap
    assert 'azd provision --cwd "$ROOT_DIR" --preview --no-prompt' in provision
    assert "Delete or Replace changes" in provision
    assert '"$SCRIPT_DIR/provision_infrastructure.sh"' in bootstrap
    assert "microsoft-entra-admin create" in bootstrap
    assert "administrators@" not in postgres


def test_operational_scripts_never_prompt_for_human_confirmation() -> None:
    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "scripts" / "azure").glob("*.sh")
    )
    assert "read -r -s -p" not in scripts
    assert "AZURE_BOOTSTRAP_APPROVED" not in scripts


def test_direct_langgraph_runtime_only() -> None:
    config = read("backend/app/core/config.py")
    requirements = read("backend/requirements.txt")
    assert "direct_langgraph" in config
    assert "responses_wrapper" not in config
    assert "azure-ai-agentserver" not in requirements
