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

    with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
        created = project.agents.create_version(
            agent_name=agent_name,
            description="Order Resolution private LangGraph hosted workflow agent.",
            definition=build_definition(),
        )
        for _ in range(60):
            version = project.agents.get_version(
                agent_name=agent_name, agent_version=created.version
            )
            status = str(read_value(version, "status") or "").lower()
            if status == "active":
                identity = read_value(version, "instance_identity")
                principal_id = (
                    identity.get("principal_id")
                    if isinstance(identity, dict)
                    else getattr(identity, "principal_id", "")
                )
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
