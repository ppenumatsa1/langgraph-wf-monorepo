from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    log_level: str
    fail_risk_once: bool
    fail_credit_randomly: bool
    crash_after_executor: str
    crash_after_step_or_superstep: str
    retry_max_attempts: int
    retry_base_delay_ms: int
    retry_jitter_ms: int
    azure_ai_project_id: str
    azure_ai_project_name: str
    foundry_model_deployment_name: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    database_url: str = ""
    db_auth_mode: str = "password"
    db_sslmode: str = "prefer"
    db_schema_managed_externally: bool = False
    azure_client_id: str = ""
    azure_ai_project_endpoint: str = ""
    foundry_responses_endpoint: str = ""
    foundry_hosted_agent_name: str = "underwriting-hosted"
    foundry_hosted_agent_version: str = ""
    foundry_responses_timeout_seconds: float = 60.0
    frontend_origin: str = "http://localhost:5173"
    execution_mode: str = "hosted"

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?sslmode={self.db_sslmode}"
        )


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "underwriting"),
        db_user=os.getenv("DB_USER", "underwriting"),
        db_password=os.getenv("DB_PASSWORD", "underwriting"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        fail_risk_once=_env_bool("FAIL_RISK_ONCE"),
        fail_credit_randomly=_env_bool("FAIL_CREDIT_RANDOMLY"),
        crash_after_executor=os.getenv("CRASH_AFTER_EXECUTOR", ""),
        crash_after_step_or_superstep=os.getenv("CRASH_AFTER_STEP_OR_SUPERSTEP", ""),
        retry_max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
        retry_base_delay_ms=int(os.getenv("RETRY_BASE_DELAY_MS", "200")),
        retry_jitter_ms=int(os.getenv("RETRY_JITTER_MS", "100")),
        azure_ai_project_id=os.getenv("AZURE_AI_PROJECT_ID", ""),
        azure_ai_project_name=os.getenv("AZURE_AI_PROJECT_NAME", ""),
        foundry_model_deployment_name=os.getenv(
            "UNDERWRITING_MODEL_DEPLOYMENT_NAME",
            os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", ""),
        ),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        db_auth_mode=os.getenv("DB_AUTH_MODE", "password"),
        db_sslmode=os.getenv("DB_SSLMODE", "prefer"),
        db_schema_managed_externally=_env_bool("DB_SCHEMA_MANAGED_EXTERNALLY"),
        azure_client_id=os.getenv("AZURE_CLIENT_ID", ""),
        azure_ai_project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT", ""),
        foundry_responses_endpoint=os.getenv("FOUNDRY_RESPONSES_ENDPOINT", ""),
        foundry_hosted_agent_name=os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "underwriting-hosted"),
        foundry_hosted_agent_version=os.getenv("FOUNDRY_HOSTED_AGENT_VERSION", ""),
        foundry_responses_timeout_seconds=float(
            os.getenv("FOUNDRY_RESPONSES_TIMEOUT_SECONDS", "60")
        ),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/"),
        execution_mode=os.getenv("UNDERWRITING_EXECUTION_MODE", "hosted").lower(),
    )
