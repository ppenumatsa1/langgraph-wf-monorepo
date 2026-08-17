from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "as_dict"):
        return value.as_dict()
    return dict(value)


endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
agent_name = required("HOSTED_AGENT_NAME")
agent_version = required("HOSTED_AGENT_VERSION")
runtime_connection_name = required("FOUNDRY_RUNTIME_CONNECTION_NAME")
expected_database_placeholder = (
    f"${{{{connections.{runtime_connection_name}.credentials.database_url}}}}"
)

with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
    version = mapping(
        project.agents.get_version(agent_name=agent_name, agent_version=agent_version)
    )

definition = mapping(version.get("definition") or {})
container = mapping(
    definition.get("container_configuration") or definition.get("containerConfiguration") or {}
)
environment = mapping(
    definition.get("environment_variables") or definition.get("environmentVariables") or {}
)
database_url = str(environment.get("DATABASE_URL") or "")
runtime_database_url = str(environment.get("RUNTIME_DATABASE_URL") or "")

print(
    json.dumps(
        {
            "name": agent_name,
            "version": str(version.get("version") or agent_version),
            "status": str(version.get("status") or ""),
            "image": str(container.get("image") or ""),
            "db_schema_managed_externally": str(
                environment.get("DB_SCHEMA_MANAGED_EXTERNALLY") or ""
            ).lower()
            == "true",
            "runtime_connection_name": runtime_connection_name,
            "database_url_placeholder": database_url == expected_database_placeholder,
            "runtime_database_url_placeholder": (
                runtime_database_url == expected_database_placeholder
            ),
            "database_url_parity": database_url == runtime_database_url,
            "application_insights_configured": bool(
                environment.get("UNDERWRITING_APPINSIGHTS_CONNECTION_STRING")
            ),
        },
        sort_keys=True,
    )
)
