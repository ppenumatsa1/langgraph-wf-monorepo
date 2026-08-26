SHELL := /bin/bash
COMPOSE_ENV_FILE ?= $(if $(wildcard backend/.env),backend/.env,backend/.env.example)
FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE ?= deployment/profiles/foundry-private.env
FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE ?=

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
	foundry-verify foundry-evidence foundry-release foundry-release-migration-plan \
	foundry-private-profile-apply foundry-private-gates foundry-private-iac-build \
	foundry-private-bootstrap-env foundry-private-what-if foundry-private-provision \
	foundry-private-evaluation-storage-plan foundry-private-evaluation-storage-reconcile \
	foundry-private-capability-host-cleanup \
	foundry-private-postgres-schema foundry-private-postgres-credentials foundry-private-postgres-readiness \
	foundry-private-runner-bootstrap foundry-private-model-preflight foundry-private-package foundry-private-backend-deploy \
	foundry-private-frontend-deploy foundry-private-hosted-deploy foundry-private-verify \
	foundry-private-smoke foundry-private-hosted-e2e foundry-private-browser-e2e \
	foundry-private-eval foundry-private-telemetry foundry-private-release

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
	@echo "  eval-foundry    - Unsupported outside the private runner release DAG"
	@echo "  eval-foundry-config - Unsupported outside the private runner release DAG"
	@echo "  eval-all        - Run deterministic evaluation; private Foundry evaluation is release-only"
	@echo "  test-e2e        - Run workflow and selected-thread Playwright tests"
	@echo "  test-e2e-selected-thread - Run the focused selected-thread integration test"
	@echo "  manual-matrix   - Run ORD-1001..ORD-1010 manual verification matrix"
	@echo "  run-mock-mcp    - Start local authenticated MCP simulator"
	@echo "  docker-test     - Run Playwright tests in Docker compose profile"
	@echo "  validate-quick  - Fast redeploy validation (Playwright + smoke if API_URL set)"
	@echo "  validate-full   - Full validation (test + eval + e2e + design-review)"
	@echo "  test-scripts     - Run private automation contracts"
	@echo "  test-deployment-profile - Validate secret-free target profiles"
	@echo "  foundry-profile-apply - Alias for the private runtime profile gate"
	@echo "  foundry-bootstrap[-env] - Alias for deterministic private bootstrap setup"
	@echo "  foundry-iac-build - Compile and enforce the private Bicep contract"
	@echo "  foundry-provision - Explicit one-time private provisioning and reconciliation"
	@echo "  foundry-package, foundry-*-deploy, foundry-smoke, foundry-verify - Private runner aliases"
	@echo "  foundry-model-preflight, foundry-hosted-e2e, foundry-telemetry - Private runner aliases"
	@echo "  foundry-release - Run the authenticated, gated private app-only release DAG"
	@echo "  foundry-private-release - Run the private, runner-only app release DAG"
	@echo "  foundry-private-bootstrap-env - Prepare deterministic private bootstrap values without provisioning"
	@echo "  foundry-private-provision - Explicit one-time private provisioning and reconciliation"
	@echo "  foundry-private-evaluation-storage-plan - Read-only evaluation Storage reconciliation plan"
	@echo "  foundry-private-evaluation-storage-reconcile - Apply the reviewed evaluation Storage-only repair"
	@echo "  foundry-private-runner-bootstrap - Securely sync the exact private GitHub commit to the VNet runner"
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
	@set -euo pipefail; \
	if [[ -x backend/.venv/bin/pytest ]]; then \
		PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:. backend/.venv/bin/pytest -q --basetemp scripts/foundry-private/tests/.pytest-work scripts/foundry-private/tests/test_private_evidence.py scripts/foundry-private/tests/test_extract_azd_agent_json.py; \
	else \
		echo "backend/.venv is unavailable; running script-only tests with system Python."; \
		PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:. python3 -m pytest -q --basetemp scripts/foundry-private/tests/.pytest-work scripts/foundry-private/tests/test_private_evidence.py scripts/foundry-private/tests/test_extract_azd_agent_json.py; \
	fi
	bash scripts/foundry-private/tests/test_private_release_contract.sh

test-deployment-profile:
	bash scripts/foundry-private/tests/test_private_release_contract.sh

eval-backend: ensure-backend-env
	./scripts/local/run_with_test_postgres.sh bash -lc 'cd backend && . .venv/bin/activate && python -m evals.eval_runner'

eval-foundry: ensure-backend-env
	@echo "Foundry-private evaluation is runner-only; use make foundry-private-eval during a release." >&2
	@exit 2

foundry-eval: eval-foundry

eval-foundry-config:
	@echo "Foundry-private evaluation configuration is validated by the private runner preflight." >&2
	@exit 2

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
	$(MAKE) foundry-private-bootstrap-env

foundry-bootstrap-env:
	$(MAKE) foundry-private-bootstrap-env

foundry-package-validation-env:
	@echo "Public package-validation environments are not supported for the private lane." >&2
	@exit 2

foundry-profile-apply:
	$(MAKE) foundry-private-profile-apply

foundry-iac-build:
	$(MAKE) foundry-private-iac-build

foundry-package:
	$(MAKE) foundry-private-package

foundry-provision:
	$(MAKE) foundry-private-provision

foundry-provision-ready:
	$(MAKE) foundry-private-provision

foundry-postgres-schema:
	$(MAKE) foundry-private-postgres-schema

foundry-postgres-credentials:
	$(MAKE) foundry-private-postgres-credentials

foundry-backend-deploy:
	$(MAKE) foundry-private-backend-deploy

foundry-backend-deploy-ready:
	$(MAKE) foundry-private-backend-deploy

foundry-frontend-deploy:
	$(MAKE) foundry-private-frontend-deploy

foundry-frontend-deploy-ready:
	$(MAKE) foundry-private-frontend-deploy

foundry-app-deploy:
	$(MAKE) foundry-private-backend-deploy
	$(MAKE) foundry-private-frontend-deploy

foundry-deploy:
	$(MAKE) foundry-private-hosted-deploy

foundry-deploy-ready:
	$(MAKE) foundry-private-hosted-deploy

foundry-release-deploy:
	$(MAKE) foundry-private-release

foundry-up:
	@echo "Use explicit foundry-private-provision followed by foundry-private-release; foundry-up cannot provision implicitly." >&2
	@exit 2

foundry-smoke:
	$(MAKE) foundry-private-smoke

foundry-postgres-readiness:
	$(MAKE) foundry-private-postgres-readiness

foundry-model-preflight:
	$(MAKE) foundry-private-model-preflight

foundry-runtime-connection:
	$(MAKE) foundry-private-postgres-credentials

foundry-runtime-connection-ready:
	$(MAKE) foundry-private-postgres-credentials

foundry-hosted-rbac:
	@echo "Hosted identity RBAC is converged only by foundry-private-hosted-deploy." >&2
	@exit 2

foundry-hosted-e2e:
	$(MAKE) foundry-private-hosted-e2e

foundry-appinsights-connection:
	$(MAKE) foundry-private-verify

foundry-telemetry:
	$(MAKE) foundry-private-telemetry

foundry-verify:
	$(MAKE) foundry-private-verify

foundry-evidence:
	@echo "Private evidence aggregation is atomic and owned by foundry-private-release." >&2
	@exit 2

foundry-release-migration-plan:
	@echo "Public release migration planning is not applicable to the private lane." >&2
	@exit 2

foundry-release:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/release.sh

foundry-private-profile-apply:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/apply_profile.sh

foundry-private-gates:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/local_gates.sh

foundry-private-iac-build:
	./scripts/foundry-private/iac_contract.sh

foundry-private-bootstrap-env:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/apply_profile.sh
	./scripts/foundry-private/bootstrap_env.sh

foundry-private-what-if:
	FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE="$(FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE)" \
		./scripts/foundry-private/what_if.sh

foundry-private-provision:
	./scripts/foundry-private/provision.sh

foundry-private-evaluation-storage-plan:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/reconcile_evaluation_storage.sh --dry-run

foundry-private-evaluation-storage-reconcile:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/reconcile_evaluation_storage.sh

foundry-private-capability-host-cleanup:
	./scripts/foundry-private/capability_host_cleanup.sh

foundry-private-postgres-schema:
	./scripts/foundry-private/postgres.sh schema

foundry-private-postgres-credentials:
	./scripts/foundry-private/postgres.sh credentials

foundry-private-postgres-readiness:
	./scripts/foundry-private/postgres.sh readiness

foundry-private-model-preflight:
	./scripts/foundry-private/model_preflight.sh

foundry-private-runner-bootstrap:
	./scripts/foundry-private/runner_bootstrap.sh

foundry-private-package:
	./scripts/foundry-private/package.sh

foundry-private-backend-deploy:
	./scripts/foundry-private/deploy.sh backend

foundry-private-frontend-deploy:
	./scripts/foundry-private/deploy.sh frontend

foundry-private-hosted-deploy:
	./scripts/foundry-private/deploy.sh hosted

foundry-private-verify:
	./scripts/foundry-private/verify.sh

foundry-private-smoke:
	./scripts/foundry-private/smoke.sh

foundry-private-hosted-e2e:
	./scripts/foundry-private/hosted_e2e.sh

foundry-private-browser-e2e:
	./scripts/foundry-private/browser_e2e.sh

foundry-private-eval:
	./scripts/foundry-private/evaluate.sh

foundry-private-telemetry:
	./scripts/foundry-private/telemetry.sh

foundry-private-release:
	FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE="$(FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE)" \
		./scripts/foundry-private/release.sh

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache \
		scripts/playwright/test-results scripts/playwright/playwright-report \
		frontend/test-results frontend/playwright-report
