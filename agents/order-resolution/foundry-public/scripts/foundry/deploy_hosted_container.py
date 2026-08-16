from __future__ import annotations

import os
import re
import sys
import time

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


def build_environment_variables() -> dict[str, str]:
    placeholder = runtime_connection_placeholder(require("FOUNDRY_RUNTIME_CONNECTION_NAME"))
    return {
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": require("FOUNDRY_MODEL_DEPLOYMENT_NAME"),
        "DATABASE_URL": placeholder,
        "RUNTIME_DATABASE_URL": placeholder,
        "APP_ENV": require("APP_ENV"),
        "STORE_PROVIDER": require("STORE_PROVIDER"),
        "DB_SCHEMA_MANAGED_EXTERNALLY": require("DB_SCHEMA_MANAGED_EXTERNALLY"),
        "ENABLE_TELEMETRY": require("ENABLE_TELEMETRY"),
        "ENABLE_INSTRUMENTATION": require("ENABLE_INSTRUMENTATION"),
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
        "OTEL_SERVICE_NAME": require("OTEL_SERVICE_NAME"),
        "OTEL_SERVICE_NAMESPACE": require("OTEL_SERVICE_NAMESPACE"),
        "OTEL_RECORD_CONTENT": require("OTEL_RECORD_CONTENT"),
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", ""),
        "TRACE_EVALUATION_RECORD_CONTENT": require("TRACE_EVALUATION_RECORD_CONTENT"),
    }


def build_hosted_agent_definition() -> HostedAgentDefinition:
    return HostedAgentDefinition(
        cpu="0.5",
        memory="1Gi",
        container_configuration=ContainerConfiguration(image=require("FOUNDRY_IMAGE")),
        environment_variables=build_environment_variables(),
        protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
    )


def main() -> None:
    endpoint = require("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = require("FOUNDRY_HOSTED_AGENT_NAME")
    image = require("FOUNDRY_IMAGE")

    with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
        created = project.agents.create_version(
            agent_name=agent_name,
            description="Order Resolution LangGraph hosted workflow agent.",
            definition=build_hosted_agent_definition(),
        )
        print(f"Created {agent_name} version {created.version} from {image}.")

        for attempt in range(60):
            version = project.agents.get_version(
                agent_name=agent_name, agent_version=created.version
            )
            status = version["status"]
            print(f"{attempt + 1}/60: {status}")
            if status == "active":
                identity = version.get("instance_identity")
                principal_id = (
                    identity.get("principal_id")
                    if isinstance(identity, dict)
                    else getattr(identity, "principal_id", "")
                )
                if not principal_id:
                    time.sleep(10)
                    continue
                print(f"Hosted agent {agent_name} version {created.version} is active.")
                print(f"HOSTED_AGENT_VERSION={created.version}")
                print(f"HOSTED_AGENT_PRINCIPAL_ID={principal_id}")
                return
            if status == "failed":
                raise RuntimeError(dict(version))
            time.sleep(10)

    raise TimeoutError("Hosted agent did not become active.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise
