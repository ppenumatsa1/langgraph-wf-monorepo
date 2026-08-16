SHELL := /bin/bash
COMPOSE_ENV_FILE ?= $(if $(wildcard backend/.env),backend/.env,backend/.env.example)
FOUNDRY_PACKAGE_ENV_NAME ?= order-resolution-package-validation
FOUNDRY_PACKAGE_VALIDATION_PROFILE ?= deployment/profiles/foundry-public-package-validation.env

.PHONY: help bootstrap venv-backend install-backend install-frontend ensure-backend-env ensure-test-postgres \
	run-backend run-frontend format lint test test-backend eval-backend eval-foundry eval-foundry-config eval-all test-e2e manual-matrix \
	test-e2e-selected-thread \
	run-mock-mcp up down logs ps docker-test \
	validate-quick validate-full test-scripts test-deployment-profile clean \
	foundry-profile-apply foundry-bootstrap foundry-bootstrap-env foundry-package-validation-env foundry-iac-build foundry-package foundry-up foundry-provision foundry-provision-ready \
	foundry-postgres-schema foundry-postgres-credentials \
	foundry-postgres-readiness foundry-backend-deploy foundry-backend-deploy-ready \
	foundry-frontend-deploy foundry-frontend-deploy-ready foundry-app-deploy \
	foundry-deploy foundry-deploy-ready foundry-release-deploy foundry-smoke \
	foundry-model-preflight foundry-runtime-connection foundry-runtime-connection-ready \
	foundry-hosted-rbac foundry-hosted-e2e \
	foundry-eval foundry-appinsights-connection foundry-telemetry \
	foundry-verify foundry-evidence foundry-release foundry-release-migration-plan

help:
	@echo "Available targets:"
	@echo "  up              - Start all servers with Docker (backend, frontend, mock-mcp)"
	@echo "  down            - Stop all Docker servers"
	@echo "  logs            - Tail Docker logs"
	@echo "  ps              - Show running Docker services"
	@echo "  bootstrap       - Create backend venv + install backend/frontend/playwright deps"
	@echo "  run-backend     - Start FastAPI backend locally on :8000"
	@echo "  run-frontend    - Start Vite frontend locally on :5173"
	@echo "  format          - Format Python files (ruff format)"
	@echo "  lint            - Lint Python files (ruff check)"
	@echo "  test            - Run lint + backend tests"
	@echo "  test-backend    - Run backend pytest suite"
	@echo "  eval-backend    - Run deterministic workflow contract eval harness"
	@echo "  eval-foundry    - Run report-only Foundry evaluator using nested azd configuration"
	@echo "  eval-foundry-config - Verify the selected nested azd evaluator configuration"
	@echo "  eval-all        - Run deterministic and Foundry evals"
	@echo "  test-e2e        - Run workflow and selected-thread Playwright tests"
	@echo "  test-e2e-selected-thread - Run the focused selected-thread integration test"
	@echo "  manual-matrix   - Run ORD-1001..ORD-1010 manual verification matrix"
	@echo "  run-mock-mcp    - Start local authenticated MCP simulator"
	@echo "  docker-test     - Run Playwright tests in Docker compose profile"
	@echo "  validate-quick  - Fast redeploy validation (Playwright + smoke if API_URL set)"
	@echo "  validate-full   - Full validation (test + eval + e2e + design-review)"
	@echo "  test-scripts     - Run portable bootstrap and PostgreSQL helper contracts"
	@echo "  test-deployment-profile - Validate secret-free target profiles"
	@echo "  foundry-profile-apply FOUNDRY_DEPLOYMENT_PROFILE=/secure/path/profile.env"
	@echo "                   - Select a secret-free bootstrap or reuse target"
	@echo "  foundry-bootstrap - Hydrate local AZD outputs for an existing target"
	@echo "  foundry-bootstrap-env - Populate deterministic bootstrap parameters"
	@echo "  foundry-package-validation-env - Seed the local-only AZD packaging environment"
	@echo "  foundry-iac-build - Compile the public Foundry Bicep template"
	@echo "  foundry-package - Freshly sync hosted source and validate AZD packaging locally"
	@echo "  foundry-provision - Apply bootstrap creation or non-mutating reuse"
	@echo "  foundry-postgres-schema - Apply the canonical PostgreSQL schema"
	@echo "  foundry-postgres-credentials - Provision/rotate the runtime credential"
	@echo "  foundry-app-deploy - Verify readiness once, then deploy backend and frontend concurrently"
	@echo "  foundry-deploy  - Verify readiness, package, and deploy the hosted agent"
	@echo "  foundry-release-deploy - Package, verify readiness once, and deploy all runtime legs concurrently"
	@echo "  foundry-model-preflight - Read-only validation of the chat/embeddings/evaluator deployments and quota"
	@echo "  foundry-runtime-connection - Verify PostgreSQL readiness and converge the project CustomKeys connection"
	@echo "  foundry-hosted-rbac - Converge the hosted identity's account-scoped OpenAI User role"
	@echo "  foundry-smoke   - Invoke hosted agent health check and write secret-free evidence"
	@echo "  foundry-hosted-e2e - Run fresh low/high-risk and damaged-item HITL approval/resume checks"
	@echo "  foundry-eval    - Run the report-only Foundry trace-evaluation gate"
	@echo "  foundry-telemetry - Verify Application Insights after hosted E2E evidence exists"
	@echo "  foundry-verify  - Verify exact active images, topology, proxy health, hosted version, RBAC, and DB parity"
	@echo "  foundry-evidence - Aggregate the current release window into one secret-free JSON report"
	@echo "  foundry-release - Run the authenticated, gated public release DAG"
	@echo "  clean           - Remove caches and test artifacts"

bootstrap: install-backend install-frontend

venv-backend:
	cd backend && python3 -m venv .venv

install-backend: venv-backend
	cd backend && . .venv/bin/activate && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install
	cd scripts/playwright && npm install

ensure-backend-env:
	test -d backend/.venv || $(MAKE) venv-backend
	. backend/.venv/bin/activate && python -c "import pytest" >/dev/null 2>&1 || $(MAKE) install-backend

ensure-test-postgres:
	@DATABASE_URL="$${DATABASE_URL:-$${FOUNDRY_RUNTIME_DATABASE_URL:-$${RUNTIME_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/langgraph_workflow?sslmode=disable}}}" \
		./scripts/local/ensure_test_postgres.sh

run-backend: ensure-backend-env
	UVICORN_RELOAD=true ./infra/foundry-hosted/runtime/entrypoint.sh

run-frontend:
	cd frontend && npm run dev

format: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff format .

lint: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff check .

test: lint test-backend

test-backend: ensure-backend-env
	./scripts/local/run_with_test_postgres.sh bash -lc 'cd backend && . .venv/bin/activate && pytest -q'

test-scripts:
	PYTHONPATH=backend:. backend/.venv/bin/pytest -q \
		scripts/foundry/tests/test_postgres_runtime_credentials.py \
		scripts/foundry/tests/test_hosted_deployment_contract.py \
		scripts/foundry/tests/test_release_evidence.py
	bash scripts/foundry/tests/test_bootstrap_infrastructure_contract.sh
	bash scripts/foundry/tests/test_package_validation_contract.sh
	bash scripts/foundry/tests/test_release_scripts_contract.sh

test-deployment-profile:
	bash deployment/tests/test-profile.sh

eval-backend: ensure-backend-env
	./scripts/local/run_with_test_postgres.sh bash -lc 'cd backend && . .venv/bin/activate && python -m evals.eval_runner'

eval-foundry: ensure-backend-env
	./scripts/foundry/run_foundry_eval.sh

foundry-eval: eval-foundry

eval-foundry-config:
	./scripts/foundry/run_foundry_eval.sh --check

eval-all: eval-backend eval-foundry

test-e2e-selected-thread:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd frontend && PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	else \
		cd frontend && npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	fi

test-e2e:
	@set -euo pipefail; \
	if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd scripts/playwright && npm run test:e2e; \
		PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" $(MAKE) -C "$(CURDIR)" test-e2e-selected-thread; \
	else \
		set -euo pipefail; \
		free_port() { python3 scripts/local/find_free_port.py; }; \
		backend_port="$${E2E_BACKEND_HOST_PORT:-$$(free_port)}"; \
		postgres_port="$${E2E_POSTGRES_HOST_PORT:-$$(free_port)}"; \
		mock_mcp_port="$${E2E_MOCK_MCP_HOST_PORT:-$$(free_port)}"; \
		compose_project="$${E2E_COMPOSE_PROJECT_NAME:-langgraph-e2e-$${backend_port}}"; \
		echo "Starting isolated E2E stack '$${compose_project}' with backend on :$${backend_port}."; \
		cleanup() { \
			if [[ -n "$${frontend_pid:-}" ]]; then kill "$${frontend_pid}" 2>/dev/null || true; wait "$${frontend_pid}" 2>/dev/null || true; fi; \
			COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans >/dev/null 2>&1 || true; \
		}; \
		trap cleanup EXIT; \
		COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend; \
		backend_url="http://127.0.0.1:$${backend_port}"; \
		for _ in {1..60}; do \
			curl -fsS "$${backend_url}/health" >/dev/null && break; \
			sleep 1; \
		done; \
		curl -fsS "$${backend_url}/health" >/dev/null; \
		frontend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		frontend_url="http://127.0.0.1:$${frontend_port}"; \
		(cd frontend && VITE_PROXY_TARGET="$${backend_url}" node_modules/.bin/vite --host 127.0.0.1 --port "$${frontend_port}" --strictPort) >/dev/null 2>&1 & \
		frontend_pid="$$!"; \
		for _ in {1..30}; do \
			curl -fsS "$${frontend_url}" >/dev/null && break; \
			sleep 1; \
		done; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" bash -c 'cd scripts/playwright && npm run test:e2e'; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" $(MAKE) -C "$(CURDIR)" test-e2e-selected-thread; \
	fi

manual-matrix:
	scripts/manual/run-manual-matrix.sh "$${API_URL:-http://localhost:8000}" $${MANUAL_MATRIX_ARGS:-}

run-mock-mcp: ensure-backend-env
	. backend/.venv/bin/activate && uvicorn scripts.mcp.mock_mcp_server:app --reload --port 8011

up:
	@set -euo pipefail; \
	workflow_mode="$$(grep -E '^[[:space:]]*WORKFLOW_MODE=' $(COMPOSE_ENV_FILE) | tail -1 | cut -d= -f2- | tr -d '"' || true)"; \
	hosted_key="$$(grep -E '^[[:space:]]*FOUNDRY_HOSTED_API_KEY=' $(COMPOSE_ENV_FILE) | tail -1 | cut -d= -f2- | tr -d '"' || true)"; \
	if [[ "$$workflow_mode" == "foundry_hosted" && -z "$$hosted_key" ]]; then \
		if command -v az >/dev/null 2>&1; then \
			token="$$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv 2>/dev/null || true)"; \
			if [[ -n "$$token" ]]; then \
				echo "Using host Azure CLI token for Foundry hosted responses."; \
				FOUNDRY_HOSTED_API_KEY="Bearer $$token" docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
			else \
				echo "WARN: Could not acquire Azure CLI token. Set FOUNDRY_HOSTED_API_KEY in $(COMPOSE_ENV_FILE)."; \
				docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
			fi; \
		else \
			echo "WARN: Azure CLI not found on host. Set FOUNDRY_HOSTED_API_KEY in $(COMPOSE_ENV_FILE)."; \
			docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
		fi; \
	else \
		docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
	fi
	@echo "Frontend: http://localhost:5173"
	@echo "Backend health: http://localhost:8000/health"

down:
	docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans

logs:
	docker compose --env-file $(COMPOSE_ENV_FILE) logs -f --tail=200

ps:
	docker compose --env-file $(COMPOSE_ENV_FILE) ps

docker-test:
	@set -euo pipefail; \
	free_port() { python3 scripts/local/find_free_port.py; }; \
	backend_port="$${E2E_BACKEND_HOST_PORT:-$$(free_port)}"; \
	frontend_port="$${E2E_FRONTEND_HOST_PORT:-$$(free_port)}"; \
	postgres_port="$${E2E_POSTGRES_HOST_PORT:-$$(free_port)}"; \
	mock_mcp_port="$${E2E_MOCK_MCP_HOST_PORT:-$$(free_port)}"; \
	compose_project="$${E2E_COMPOSE_PROJECT_NAME:-langgraph-e2e-docker-$${backend_port}}"; \
	cleanup() { \
		COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" FRONTEND_HOST_PORT="$${frontend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans >/dev/null 2>&1 || true; \
	}; \
	trap cleanup EXIT; \
	COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" FRONTEND_HOST_PORT="$${frontend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) --profile test up --build --abort-on-container-exit --exit-code-from playwright playwright

validate-quick:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		$(MAKE) test-e2e; \
	elif [[ -n "$${WEB_URL:-}" ]]; then \
		PLAYWRIGHT_BASE_URL="$${WEB_URL}" $(MAKE) test-e2e; \
	else \
		$(MAKE) test-e2e; \
	fi
validate-full:
	$(MAKE) test
	$(MAKE) eval-backend
	$(MAKE) test-e2e
	./scripts/skills/design-review-skill.sh

foundry-bootstrap:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/bootstrap_azd_env.sh

foundry-bootstrap-env:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/prepare_bootstrap_env.sh

foundry-package-validation-env:
	FOUNDRY_PACKAGE_ENV_NAME="$(FOUNDRY_PACKAGE_ENV_NAME)" \
	FOUNDRY_PACKAGE_VALIDATION_PROFILE="$(FOUNDRY_PACKAGE_VALIDATION_PROFILE)" \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/prepare_package_validation_env.sh

foundry-profile-apply:
	@set -euo pipefail; \
	shared_profile="../deployment/profiles/foundry-public.env"; \
	legacy_profile="deployment/profiles/foundry-public.env"; \
	profile="$(FOUNDRY_DEPLOYMENT_PROFILE)"; \
	if [[ -z "$$profile" && -f "$$shared_profile" ]]; then profile="$$shared_profile"; fi; \
	if [[ -z "$$profile" ]]; then \
		profile="$$legacy_profile"; \
		echo "WARN: Using legacy_pending_cutover profile $$legacy_profile; prefer $$shared_profile." >&2; \
	elif [[ "$$profile" == "$$legacy_profile" ]]; then \
		echo "WARN: Using legacy_pending_cutover profile $$legacy_profile; prefer $$shared_profile." >&2; \
	fi; \
	bash ./deployment/apply-azd-profile.sh "$$profile"

foundry-iac-build:
	az bicep build --file infra/foundry-hosted/iac/main.bicep
	az bicep build --file infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep --stdout >/dev/null

foundry-package:
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then \
		timing_enabled=1; \
		python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage package_build --action start >/dev/null; \
	fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage package_build --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	FOUNDRY_PACKAGE_ENV_NAME="$(FOUNDRY_PACKAGE_ENV_NAME)" FOUNDRY_PACKAGE_VALIDATION_PROFILE="$(FOUNDRY_PACKAGE_VALIDATION_PROFILE)" ./scripts/foundry/prepare_package_validation_env.sh; \
	./scripts/foundry/sync_hosted_source.sh; \
	(cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd package --all --environment "$(FOUNDRY_PACKAGE_ENV_NAME)" --no-prompt); \
	status=succeeded

foundry-provision:
	./scripts/foundry/bootstrap_azd_env.sh
	$(MAKE) foundry-iac-build
	$(MAKE) foundry-provision-ready
	FOUNDRY_BOOTSTRAP_HYDRATE=1 ./scripts/foundry/bootstrap_azd_env.sh

foundry-provision-ready:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/ensure_foundry_azd_defaults.sh
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt $(if $(FOUNDRY_PROVISION_NO_STATE),--no-state,)

foundry-postgres-schema:
	./scripts/foundry/bootstrap_postgres_schema.sh

foundry-postgres-credentials:
	./scripts/foundry/provision_postgres_runtime_credentials.sh

foundry-backend-deploy: foundry-postgres-readiness
	$(MAKE) foundry-backend-deploy-ready

foundry-backend-deploy-ready:
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then timing_enabled=1; python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage backend_deployment --action start >/dev/null; fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage backend_deployment --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	./scripts/foundry/deploy_public_backend.sh; \
	status=succeeded

foundry-frontend-deploy:
	$(MAKE) foundry-frontend-deploy-ready

foundry-frontend-deploy-ready:
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then timing_enabled=1; python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage frontend_deployment --action start >/dev/null; fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage frontend_deployment --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	./scripts/foundry/deploy_public_frontend.sh; \
	status=succeeded

foundry-app-deploy:
	$(MAKE) foundry-postgres-readiness
	$(MAKE) -j2 foundry-backend-deploy-ready foundry-frontend-deploy-ready

foundry-deploy: foundry-postgres-readiness
	$(MAKE) foundry-package
	$(MAKE) foundry-model-preflight
	$(MAKE) foundry-runtime-connection-ready
	$(MAKE) foundry-deploy-ready

foundry-deploy-ready:
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then timing_enabled=1; python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage hosted_deployment_activation --action start >/dev/null; fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage hosted_deployment_activation --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	test -f backend/Dockerfile.hosted; \
	test -f infra/foundry-hosted/runtime/launch_hosted_agent.py; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_hosted_container.sh; \
	status=succeeded

foundry-release-deploy:
	$(MAKE) -j3 foundry-package foundry-model-preflight foundry-postgres-readiness
	$(MAKE) foundry-runtime-connection-ready
	$(MAKE) -j3 foundry-backend-deploy-ready foundry-frontend-deploy-ready foundry-deploy-ready

foundry-up:
	$(MAKE) foundry-provision
	$(MAKE) foundry-release-deploy
	$(MAKE) foundry-appinsights-connection

foundry-smoke:
	./scripts/foundry/hosted_smoke.sh

foundry-postgres-readiness:
	./scripts/foundry/check_public_postgres_readiness.sh

foundry-model-preflight:
	./scripts/foundry/preflight_models.sh

foundry-runtime-connection:
	$(MAKE) foundry-postgres-readiness
	$(MAKE) foundry-runtime-connection-ready

foundry-runtime-connection-ready:
	az bicep build --file infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep --stdout >/dev/null
	./scripts/foundry/converge_runtime_secret_connection.sh

foundry-hosted-rbac:
	./scripts/foundry/ensure_hosted_agent_rbac.sh

foundry-hosted-e2e:
	./scripts/foundry/hosted_e2e.sh

foundry-appinsights-connection:
	./scripts/foundry/verify_project_appinsights_connection.sh

foundry-telemetry:
	./scripts/foundry/verify_telemetry.sh

foundry-verify:
	./scripts/foundry/verify_deployment.sh

foundry-evidence: ensure-backend-env
	@test -n "$${FOUNDRY_RELEASE_ID:-}" || { echo "FOUNDRY_RELEASE_ID is required." >&2; exit 2; }
	@set -euo pipefail; \
	python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage final_evidence --action start >/dev/null; \
	status=failed; \
	trap 'python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage final_evidence --action end --status "$$status" >/dev/null || true' EXIT; \
	PYTHONPATH=. backend/.venv/bin/python scripts/foundry/release_evidence.py aggregate --release-id "$${FOUNDRY_RELEASE_ID}"; \
	status=succeeded
	PYTHONPATH=. backend/.venv/bin/python scripts/foundry/release_evidence.py finalize --release-id "$${FOUNDRY_RELEASE_ID}" --status succeeded

foundry-release-migration-plan:
	python3 scripts/foundry/release_migration.py

foundry-release:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_public_dev.sh

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache \
		scripts/playwright/test-results scripts/playwright/playwright-report \
		frontend/test-results frontend/playwright-report
