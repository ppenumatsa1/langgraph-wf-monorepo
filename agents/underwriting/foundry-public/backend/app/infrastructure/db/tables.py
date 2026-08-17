from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

workflow_runs = Table(
    "workflow_runs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workflow_type", Text, nullable=False),
    Column("application_id", Text, nullable=False, index=True),
    Column("applicant_name", Text, nullable=True, index=True),
    Column("status", Text, nullable=False, index=True),
    Column("latest_output", JSONB().with_variant(JSON, "sqlite"), nullable=True),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("started_at", DateTime, nullable=True),
    Column("completed_at", DateTime, nullable=True),
    Column("duration_ms", BigInteger, nullable=True),
)

business_state = Table(
    "business_state",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("workflow_run_id", Text, nullable=False, index=True),
    Column("application_id", Text, nullable=False, index=True),
    Column("state_key", Text, nullable=False),
    Column("state_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
    UniqueConstraint("workflow_run_id", "state_key", name="ux_business_state_run_key"),
)

underwriting_results = Table(
    "underwriting_results",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("workflow_run_id", Text, nullable=False, index=True),
    Column("application_id", Text, nullable=False, index=True),
    Column("check_type", Text, nullable=False),
    Column("result_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("idempotency_key", Text, nullable=False, unique=True, index=True),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

workflow_events = Table(
    "workflow_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("workflow_run_id", Text, nullable=False, index=True),
    Column("event_type", Text, nullable=False),
    Column("executor_name", Text, nullable=False),
    Column("payload_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("idempotency_key", Text, primary_key=True),
    Column("operation_name", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("result_json", JSONB().with_variant(JSON, "sqlite"), nullable=True),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

workflow_checkpoints = Table(
    "workflow_checkpoints",
    metadata,
    Column("workflow_run_id", Text, nullable=False, index=True),
    Column("checkpoint_ns", Text, nullable=False, default=""),
    Column("checkpoint_id", Text, nullable=False),
    Column("parent_checkpoint_id", Text, nullable=True),
    Column("metadata_json", JSONB().with_variant(JSON, "sqlite"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    UniqueConstraint(
        "workflow_run_id",
        "checkpoint_ns",
        "checkpoint_id",
        name="workflow_checkpoints_pkey",
    ),
)
