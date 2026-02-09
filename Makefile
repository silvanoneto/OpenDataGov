.PHONY: help install lint lint-python lint-go lint-tofu lint-md test test-python test-go build compose-up compose-down compose-full-up compose-full-down compose-datahub-up compose-datahub-down compose-auth-up compose-auth-down compose-vault-up compose-vault-down compose-all-up compose-logs quick-start full-test airgap-sim airgap-bundle compliance-check kind-up kind-down kind-load tofu-init tofu-apply tofu-destroy proto clean

PYTHON_SERVICES := libs/python/odg-core services/governance-engine services/lakehouse-agent services/data-expert services/quality-gate
GO_SERVICES := services/gateway

COMPOSE_FILE := deploy/docker-compose/docker-compose.yml
COMPOSE_FULL := deploy/docker-compose/docker-compose.full.yml
COMPOSE_DATAHUB := deploy/docker-compose/docker-compose.datahub.yml
COMPOSE_AUTH := deploy/docker-compose/docker-compose.auth.yml
COMPOSE_VAULT := deploy/docker-compose/docker-compose.vault.yml
DEPLOY_DIR := deploy/docker-compose
KIND_CLUSTER := opendatagov
TOFU_DIR := deploy/tofu
APP_IMAGES := opendatagov/governance-engine opendatagov/lakehouse-agent opendatagov/data-expert opendatagov/quality-gate opendatagov/gateway

install: ## Set up local dev environment
	@./scripts/setup-dev.sh

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Lint ─────────────────────────────────────────────────

lint: lint-python lint-go lint-tofu lint-md ## Run all linters

lint-python: ## Run ruff + mypy on Python code
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Linting $$svc"; \
		(cd $$svc && uv run ruff check . && uv run mypy .) || exit 1; \
	done

lint-go: ## Run golangci-lint on Go code
	@for svc in $(GO_SERVICES); do \
		echo "==> Linting $$svc"; \
		(cd $$svc && golangci-lint run ./...) || exit 1; \
	done

lint-tofu: ## Run tofu fmt check + tflint on OpenTofu code
	@echo "==> Checking tofu format"
	cd $(TOFU_DIR) && tofu fmt -check -diff
	@if command -v tflint >/dev/null 2>&1; then \
		echo "==> Running tflint"; \
		cd $(TOFU_DIR) && tflint --init && tflint; \
	else \
		echo "==> tflint not installed, skipping"; \
	fi

lint-md: ## Run mdformat on Markdown files
	@echo "==> Checking markdown format"
	uv run mdformat --check README.md CONTRIBUTING.md SECURITY.md docs/

# ─── Test ─────────────────────────────────────────────────

test: test-python test-go ## Run all tests

test-python: ## Run pytest on Python services
	@for svc in $(PYTHON_SERVICES); do \
		echo "==> Testing $$svc"; \
		(cd $$svc && uv run pytest --cov -q) || exit 1; \
	done

test-go: ## Run go test on Go services
	@for svc in $(GO_SERVICES); do \
		echo "==> Testing $$svc"; \
		(cd $$svc && go test ./... -v) || exit 1; \
	done

# ─── Build ────────────────────────────────────────────────

build: ## Build all Docker images via docker compose
	docker compose -f $(COMPOSE_FILE) build
	@for img in $(APP_IMAGES); do \
		svc=$$(echo $$img | sed 's|opendatagov/||'); \
		docker tag docker-compose-$$svc:latest $$img:0.1.0; \
	done
	@echo "==> Tagged images: $(APP_IMAGES)"

# ─── Compose (Profile-based) ─────────────────────────────

PROFILE ?= dev

compose-embedded: ## Start embedded profile (edge computing, 1-2 vCPU, 2-4GB RAM)
	$(MAKE) compose-up PROFILE=embedded

compose-dev: ## Start dev profile (local development, 4 vCPU, 16GB RAM)
	$(MAKE) compose-up PROFILE=dev

compose-small: ## Start small profile (small teams, 16 vCPU, 64GB RAM)
	$(MAKE) compose-up PROFILE=small

compose-medium: ## Start medium profile (enterprise, 64 vCPU, 256GB RAM, 1 GPU)
	$(MAKE) compose-up PROFILE=medium

compose-large: ## Start large profile (large-scale, 256+ vCPU, 1TB+ RAM, 2+ GPUs)
	$(MAKE) compose-up PROFILE=large

compose-up: ## Start OpenDataGov (PROFILE=embedded|dev|small|medium|large)
	@cd $(DEPLOY_DIR) && ./scripts/compose-up.sh $(PROFILE)

compose-down: ## Stop OpenDataGov (PROFILE=embedded|dev|small|medium|large)
	@cd $(DEPLOY_DIR) && ./scripts/compose-down.sh $(PROFILE)

compose-logs: ## Tail logs (PROFILE=embedded|dev|small|medium|large)
	@cd $(DEPLOY_DIR) && docker compose -f profiles/$(PROFILE).yml logs -f

compose-validate: ## Validate profile configuration (PROFILE=embedded|dev|small|medium|large)
	@cd $(DEPLOY_DIR) && ./scripts/validate-profile.sh $(PROFILE)

compose-health: ## Check service health (PROFILE=embedded|dev|small|medium|large)
	@cd $(DEPLOY_DIR) && ./scripts/health-check.sh $(PROFILE)

# ─── Compose (Deprecated - Backward Compatibility) ────────

compose-full-up: ## [DEPRECATED] Use compose-small instead
	@echo "Warning: compose-full-up is deprecated. Use 'make compose-small' instead."
	$(MAKE) compose-small

compose-full-down: ## [DEPRECATED] Use compose-down PROFILE=small instead
	@echo "Warning: compose-full-down is deprecated. Use 'make compose-down PROFILE=small' instead."
	$(MAKE) compose-down PROFILE=small

compose-datahub-up: ## [DEPRECATED] Use compose-small instead
	@echo "Warning: compose-datahub-up is deprecated. Use 'make compose-small' instead."
	$(MAKE) compose-small

compose-datahub-down: ## [DEPRECATED] Use compose-down PROFILE=small instead
	@echo "Warning: compose-datahub-down is deprecated. Use 'make compose-down PROFILE=small' instead."
	$(MAKE) compose-down PROFILE=small

compose-auth-up: ## [DEPRECATED] Use compose-small instead
	@echo "Warning: compose-auth-up is deprecated. Use 'make compose-small' instead."
	$(MAKE) compose-small

compose-auth-down: ## [DEPRECATED] Use compose-down PROFILE=small instead
	@echo "Warning: compose-auth-down is deprecated. Use 'make compose-down PROFILE=small' instead."
	$(MAKE) compose-down PROFILE=small

compose-vault-up: ## [DEPRECATED] Use compose-small instead
	@echo "Warning: compose-vault-up is deprecated. Use 'make compose-small' instead."
	$(MAKE) compose-small

compose-vault-down: ## [DEPRECATED] Use compose-down PROFILE=small instead
	@echo "Warning: compose-vault-down is deprecated. Use 'make compose-down PROFILE=small' instead."
	$(MAKE) compose-down PROFILE=small

compose-all-up: ## [DEPRECATED] Use compose-large instead
	@echo "Warning: compose-all-up is deprecated. Use 'make compose-large' instead."
	$(MAKE) compose-large

# ─── Quick Start ─────────────────────────────────────────

quick-start: ## Start base stack and wait for healthy services
	@echo "==> Starting OpenDataGov base stack..."
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "==> Waiting for services to be healthy..."
	@for i in $$(seq 1 30); do \
		if docker compose -f $(COMPOSE_FILE) ps --format '{{.Status}}' | grep -q "unhealthy\|starting"; then \
			printf "."; sleep 2; \
		else \
			echo ""; echo "==> All services healthy!"; \
			docker compose -f $(COMPOSE_FILE) ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'; \
			exit 0; \
		fi; \
	done; \
	echo ""; echo "==> Timeout waiting for services. Current status:"; \
	docker compose -f $(COMPOSE_FILE) ps

# ─── Full Test + Air-Gap ─────────────────────────────────

full-test: ## Run full integration test (unit + compose + kind)
	@./scripts/full-test.sh

airgap-bundle: build ## Create air-gap image bundle
	@./deploy/scripts/airgap-bundle.sh

airgap-sim: ## Simulate air-gapped deployment
	@./scripts/airgap-simulate.sh

compliance-check: ## Run compliance checks on odg-core
	@cd libs/python/odg-core && uv run python -c "from odg_core.compliance.registry import create_default_registry; r = create_default_registry(); print(r)"

# ─── Kind + Tofu ─────────────────────────────────────────

kind-up: build ## Create kind cluster, load images, deploy via tofu
	@kind create cluster --name $(KIND_CLUSTER) --config deploy/kind/kind-config.yaml 2>/dev/null || true
	@for img in $(APP_IMAGES); do \
		echo "==> Loading $$img:0.1.0 into kind"; \
		kind load docker-image $$img:0.1.0 --name $(KIND_CLUSTER); \
	done
	cd $(TOFU_DIR) && tofu init -input=false && tofu apply -auto-approve

kind-load: build ## Rebuild, reload images, and restart pods
	@for img in $(APP_IMAGES); do \
		echo "==> Loading $$img:0.1.0 into kind"; \
		kind load docker-image $$img:0.1.0 --name $(KIND_CLUSTER); \
	done
	kubectl rollout restart deploy -n opendatagov -l app.kubernetes.io/part-of=opendatagov

kind-down: ## Delete kind cluster and clean tofu state
	kind delete cluster --name $(KIND_CLUSTER)
	rm -f $(TOFU_DIR)/terraform.tfstate $(TOFU_DIR)/terraform.tfstate.backup

tofu-init: ## Initialize tofu providers
	cd $(TOFU_DIR) && tofu init -input=false

tofu-apply: ## Apply tofu (deploy/update helm release)
	cd $(TOFU_DIR) && tofu apply -auto-approve

tofu-destroy: ## Destroy tofu-managed resources
	cd $(TOFU_DIR) && tofu destroy -auto-approve

# ─── Proto ────────────────────────────────────────────────

proto: ## Generate protobuf code (Go + Python)
	./scripts/generate-proto.sh

# ─── Clean ────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
