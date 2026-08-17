from __future__ import annotations

import os
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ContainerConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
agent_name = required("HOSTED_AGENT_NAME")
image = required("HOSTED_AGENT_IMAGE")
runtime_connection_name = required("FOUNDRY_RUNTIME_CONNECTION_NAME")
runtime_database_placeholder = (
    f"${{{{connections.{runtime_connection_name}.credentials.database_url}}}}"
)

environment_variables = {
    "APP_ENV": "production",
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
    "DATABASE_URL": runtime_database_placeholder,
    "RUNTIME_DATABASE_URL": runtime_database_placeholder,
    "DB_AUTH_MODE": "password",
    "DB_SCHEMA_MANAGED_EXTERNALLY": required("DB_SCHEMA_MANAGED_EXTERNALLY"),
    "WORKFLOW_POOL_MAX_SIZE": "2",
    "LANGGRAPH_POOL_MAX_SIZE": "2",
    "UNDERWRITING_MODEL_DEPLOYMENT_NAME": required("UNDERWRITING_MODEL_DEPLOYMENT_NAME"),
    "AZURE_OPENAI_ENDPOINT": required("AZURE_OPENAI_ENDPOINT"),
    "ENABLE_INSTRUMENTATION": "true",
    "ENABLE_TELEMETRY": "true",
    "OTEL_SERVICE_NAME": "underwriting-hosted",
    "UNDERWRITING_APPINSIGHTS_CONNECTION_STRING": required(
        "UNDERWRITING_APPINSIGHTS_CONNECTION_STRING"
    ),
}

with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
    created = project.agents.create_version(
        agent_name=agent_name,
        description="Underwriting LangGraph hosted workflow agent.",
        definition=HostedAgentDefinition(
            cpu="0.5",
            memory="1Gi",
            container_configuration=ContainerConfiguration(image=image),
            environment_variables=environment_variables,
            protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
        ),
    )
    print(f"Created {agent_name} version {created.version} from {image}.")

    for attempt in range(60):
        version = project.agents.get_version(agent_name=agent_name, agent_version=created.version)
        status = version["status"]
        print(f"{attempt + 1}/60: {status}")
        if status == "active":
            print(f"HOSTED_AGENT_VERSION={created.version}")
            sys.exit(0)
        if status == "failed":
            raise RuntimeError(dict(version))
        time.sleep(10)

raise TimeoutError("Hosted agent did not become active.")
