from __future__ import annotations

import json
from collections import UserDict
from pathlib import Path

import pytest

from scripts.foundry import deploy_hosted_container, verify_hosted_agent

ROOT = Path(__file__).resolve().parents[3]


def test_hosted_definition_uses_connection_placeholder_not_runtime_url(
    monkeypatch,
) -> None:
    runtime_url = (
        "postgresql+psycopg://runtime:do-not-persist@example.postgres.database.azure.com/"
        "order_resolution?sslmode=require"
    )
    values = {
        "FOUNDRY_IMAGE": "example.azurecr.io/order-resolution@sha256:" + "a" * 64,
        "FOUNDRY_RUNTIME_CONNECTION_NAME": "orderresolutionruntimesecrets",
        "FOUNDRY_MODEL_DEPLOYMENT_NAME": "order-resolution-gpt-4-1-mini",
        "APP_ENV": "aca-public",
        "STORE_PROVIDER": "postgres",
        "DB_SCHEMA_MANAGED_EXTERNALLY": "true",
        "ENABLE_TELEMETRY": "true",
        "ENABLE_INSTRUMENTATION": "true",
        "OTEL_SERVICE_NAME": "langgraph-order-resolution-hosted",
        "OTEL_SERVICE_NAMESPACE": "langgraph-order-resolution",
        "OTEL_RECORD_CONTENT": "false",
        "TRACE_EVALUATION_RECORD_CONTENT": "true",
        "RUNTIME_DATABASE_URL": runtime_url,
        "DATABASE_URL": runtime_url,
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    definition = deploy_hosted_container.build_hosted_agent_definition()
    expected = "${{connections.orderresolutionruntimesecrets.credentials.database_url}}"

    assert definition.environment_variables["DATABASE_URL"] == expected
    assert definition.environment_variables["RUNTIME_DATABASE_URL"] == expected
    assert runtime_url not in json.dumps(definition.as_dict())


def test_hosted_scripts_do_not_persist_or_verify_the_runtime_url() -> None:
    deploy_shell = (ROOT / "scripts/foundry/deploy_hosted_container.sh").read_text()
    verify_python = (ROOT / "scripts/foundry/verify_hosted_agent.py").read_text()

    assert "export RUNTIME_DATABASE_URL=" not in deploy_shell
    assert "--arg runtime_database_url" not in deploy_shell
    assert "runtime_connection_name" in deploy_shell
    assert 'require("RUNTIME_DATABASE_URL")' not in verify_python
    assert "database_url_sha256" not in verify_python
    assert "credentials.database_url" in verify_python


def test_hosted_get_metadata_requires_literal_placeholders() -> None:
    runtime_url = (
        "postgresql+psycopg://runtime:do-not-persist@example.postgres.database.azure.com/"
        "order_resolution?sslmode=require"
    )
    placeholder = "${{connections.orderresolutionruntimesecrets.credentials.database_url}}"
    version = {
        "status": "active",
        "definition": {
            "container_configuration": {"image": "example/image@sha256:" + "a" * 64},
            "environment_variables": {
                "DATABASE_URL": placeholder,
                "RUNTIME_DATABASE_URL": placeholder,
                "DB_SCHEMA_MANAGED_EXTERNALLY": "true",
            },
        },
        "instance_identity": {"principal_id": "principal-id"},
    }

    result = verify_hosted_agent.verify_version_metadata(
        version,
        agent_name="order-resolution-hosted",
        agent_version="5",
        expected_image="example/image@sha256:" + "a" * 64,
        runtime_connection_name="orderresolutionruntimesecrets",
    )
    assert runtime_url not in json.dumps(result)

    version["definition"]["environment_variables"]["DATABASE_URL"] = runtime_url
    with pytest.raises(RuntimeError, match="database_connection_placeholder_matches"):
        verify_hosted_agent.verify_version_metadata(
            version,
            agent_name="order-resolution-hosted",
            agent_version="5",
            expected_image="example/image@sha256:" + "a" * 64,
            runtime_connection_name="orderresolutionruntimesecrets",
        )


def test_hosted_get_metadata_accepts_sdk_mapping_models() -> None:
    placeholder = "${{connections.orderresolutionruntimesecrets.credentials.database_url}}"
    image = "example/image@sha256:" + "a" * 64
    version = UserDict(
        {
            "status": "active",
            "definition": UserDict(
                {
                    "container_configuration": UserDict({"image": image}),
                    "environment_variables": {
                        "DATABASE_URL": placeholder,
                        "RUNTIME_DATABASE_URL": placeholder,
                        "DB_SCHEMA_MANAGED_EXTERNALLY": "true",
                    },
                }
            ),
            "instance_identity": UserDict({"principal_id": "principal-id"}),
        }
    )

    result = verify_hosted_agent.verify_version_metadata(
        version,
        agent_name="order-resolution-hosted",
        agent_version="6",
        expected_image=image,
        runtime_connection_name="orderresolutionruntimesecrets",
    )

    assert result["status"] == "active"
    assert result["principal_id"] == "principal-id"


def test_runtime_connection_template_marks_the_url_secure() -> None:
    template = (
        ROOT / "infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep"
    ).read_text()

    assert "@secure()" in template
    assert "param runtimeDatabaseUrl string" in template
    assert "category: 'CustomKeys'" in template
    assert "authType: 'CustomKeys'" in template
    assert "database_url: runtimeDatabaseUrl" in template


def test_infrastructure_and_credentials_are_non_interactive() -> None:
    provision = (ROOT / "scripts/foundry/provision_infrastructure.sh").read_text()
    credentials = (
        ROOT / "scripts/foundry/provision_postgres_runtime_credentials.sh"
    ).read_text()
    makefile = (ROOT / "Makefile").read_text()

    assert "--preview --no-prompt" in provision
    assert "Delete or Replace changes" in provision
    assert "provision_infrastructure.sh" in makefile
    assert "read -r -s -p" not in credentials
    assert "token_urlsafe" in credentials
