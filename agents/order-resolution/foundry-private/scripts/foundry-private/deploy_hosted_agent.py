from __future__ import annotations

import os
import re
import sys
import time
from collections.abc import Mapping

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ContainerConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def runtime_connection_placeholder(connection_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", connection_name):
        raise RuntimeError("FOUNDRY_RUNTIME_CONNECTION_NAME contains invalid characters.")
    return f"${{{{connections.{connection_name}.credentials.database_url}}}}"


def read_value(value: object, name: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def version_identity(version: object) -> str:
    identity = read_value(version, "instance_identity")
    principal_id = read_value(identity, "principal_id") if identity is not None else None
    return str(principal_id or "")


def matching_active_version(
    project: AIProjectClient,
    agent_name: str,
    expected: HostedAgentDefinition,
) -> object | None:
    expected_environment = read_value(expected, "environment_variables")
    expected_container = read_value(expected, "container_configuration")
    expected_image = read_value(expected_container, "image")
    for summary in project.agents.list_versions(agent_name):
        version = project.agents.get_version(
            agent_name=agent_name,
            agent_version=str(read_value(summary, "version") or ""),
        )
        if str(read_value(version, "status") or "").lower() != "active":
            continue
        definition = read_value(version, "definition")
        container = read_value(definition, "container_configuration")
        if (
            read_value(container, "image") == expected_image
            and read_value(definition, "environment_variables") == expected_environment
            and read_value(definition, "cpu") == read_value(expected, "cpu")
            and read_value(definition, "memory") == read_value(expected, "memory")
            and version_identity(version)
        ):
            return version
    return None


def build_definition() -> HostedAgentDefinition:
    placeholder = runtime_connection_placeholder(require("FOUNDRY_RUNTIME_CONNECTION_NAME"))
    return HostedAgentDefinition(
        cpu="0.5",
        memory="1Gi",
        container_configuration=ContainerConfiguration(image=require("FOUNDRY_IMAGE")),
        environment_variables={
            "AZURE_AI_MODEL_DEPLOYMENT_NAME": require("FOUNDRY_MODEL_DEPLOYMENT_NAME"),
            "DATABASE_URL": placeholder,
            "RUNTIME_DATABASE_URL": placeholder,
            "APP_ENV": "aca-private",
            "STORE_PROVIDER": "postgres",
            "DB_SCHEMA_MANAGED_EXTERNALLY": "true",
            "ENABLE_TELEMETRY": "true",
            "ENABLE_INSTRUMENTATION": "true",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
            "OTEL_SERVICE_NAME": "langgraph-order-resolution-private-hosted",
            "OTEL_SERVICE_NAMESPACE": "langgraph-order-resolution-private",
            "OTEL_RECORD_CONTENT": "false",
            "TRACE_EVALUATION_RECORD_CONTENT": "false",
        },
        protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
    )


def main() -> None:
    endpoint = require("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = require("FOUNDRY_HOSTED_AGENT_NAME")
    image = require("FOUNDRY_IMAGE")
    definition = build_definition()

    with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
        existing = matching_active_version(project, agent_name, definition)
        if existing is not None:
            print(f"HOSTED_AGENT_VERSION={read_value(existing, 'version')}")
            print(f"HOSTED_AGENT_PRINCIPAL_ID={version_identity(existing)}")
            return
        created = project.agents.create_version(
            agent_name=agent_name,
            description="Order Resolution private LangGraph hosted workflow agent.",
            definition=definition,
        )
        for _ in range(120):
            version = project.agents.get_version(
                agent_name=agent_name, agent_version=created.version
            )
            status = str(read_value(version, "status") or "").lower()
            if status == "active":
                principal_id = version_identity(version)
                if principal_id:
                    print(f"HOSTED_AGENT_VERSION={created.version}")
                    print(f"HOSTED_AGENT_PRINCIPAL_ID={principal_id}")
                    return
            if status == "failed":
                raise RuntimeError(f"Private hosted agent version failed: {version!r}")
            time.sleep(10)
    raise TimeoutError("Private hosted agent did not become active.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise
