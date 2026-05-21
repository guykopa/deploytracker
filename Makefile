ECR_URL     := 378202225330.dkr.ecr.eu-west-3.amazonaws.com/deploytracker
REGION      := eu-west-3
APP_DIR     := app
CHART_DIR   := charts/deploytracker
OBS_CHART   := charts/observability
TF_DIR      := infra/terraform
ANSIBLE_DIR := infra/ansible
SSH_KEY     := /home/kopa/deploytracker/cle-ssh.pem
ANSIBLE     := /home/kopa/deploytracker/app/.venv/bin/ansible-playbook

.PHONY: all help infra-up infra-down infra-down-full configure deploy-app deploy-observ deploy-all \
        loadgen-start loadgen-stop grafana logs shell \
        lint test typecheck docker-build docker-push ecr-login destroy-all

all: help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# ─── Infrastructure ────────────────────────────────────────────────────────────

infra-up: ## Provision AWS infrastructure with Terraform
	cd $(TF_DIR) && terraform init && terraform apply -auto-approve

infra-down: ## Destroy session resources only (EC2 + EIP) — keeps ECR, IAM, VPC alive
	cd $(TF_DIR) && terraform destroy -auto-approve \
		-target=aws_instance.k3s_server \
		-target=aws_instance.k3s_agent1 \
		-target=aws_instance.k3s_agent2 \
		-target=aws_eip.k3s_server

infra-down-full: ## Full infrastructure teardown including ECR and IAM (rare — breaks CI/CD)
	cd $(TF_DIR) && terraform destroy -auto-approve

configure: ## Configure K3s cluster with Ansible
	cd $(ANSIBLE_DIR) && $(ANSIBLE) playbooks/01-bootstrap.yml
	cd $(ANSIBLE_DIR) && $(ANSIBLE) playbooks/02-k3s-server.yml
	cd $(ANSIBLE_DIR) && $(ANSIBLE) playbooks/03-k3s-agents.yml
	cd $(ANSIBLE_DIR) && $(ANSIBLE) playbooks/04-fetch-kubeconfig.yml

# ─── Deployment ────────────────────────────────────────────────────────────────

ecr-login: ## Authenticate Docker to ECR
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(ECR_URL)

deploy-app: ## Deploy deploytracker application via Helm
	helm upgrade --install deploytracker $(CHART_DIR) \
		--namespace deploytracker --create-namespace \
		--wait --timeout 5m

deploy-observ: ## Deploy observability stack via Helm
	helm dependency update $(OBS_CHART)
	helm upgrade --install observability $(OBS_CHART) \
		--namespace observability --create-namespace \
		--wait --timeout 10m

deploy-all: deploy-observ deploy-app ## Deploy all workloads

# ─── Operations ────────────────────────────────────────────────────────────────

loadgen-start: ## Start the load generator
	kubectl apply -f loadgen/cronjob.yaml

loadgen-stop: ## Stop the load generator
	kubectl delete -f loadgen/cronjob.yaml --ignore-not-found

grafana: ## Open Grafana in browser
	@K3S_IP=$(shell cd $(TF_DIR) && terraform output -raw k3s_server_public_ip 2>/dev/null || echo "localhost") && \
	echo "Grafana: http://$$K3S_IP:30030" && \
	xdg-open "http://$$K3S_IP:30030" 2>/dev/null || open "http://$$K3S_IP:30030" 2>/dev/null || true

logs: ## Tail deploytracker pod logs
	kubectl logs -f -l app.kubernetes.io/name=deploytracker -n deploytracker --tail=100

shell: ## Open a shell in a deploytracker pod
	kubectl exec -it -n deploytracker $$(kubectl get pod -n deploytracker -l app.kubernetes.io/name=deploytracker -o jsonpath='{.items[0].metadata.name}') -- /bin/bash

# ─── Development ───────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	cd $(APP_DIR) && poetry run ruff check src tests

test: ## Run tests with coverage (minimum 80%)
	cd $(APP_DIR) && poetry run pytest tests/ \
		--cov=deploytracker --cov-report=term-missing \
		--cov-fail-under=80 -v

typecheck: ## Run mypy strict type checking
	cd $(APP_DIR) && poetry run mypy src/

docker-build: ## Build Docker image locally
	docker build -t deploytracker:local $(APP_DIR)

docker-push: ecr-login docker-build ## Build and push image to ECR
	docker tag deploytracker:local $(ECR_URL):latest
	docker push $(ECR_URL):latest

# ─── Session ───────────────────────────────────────────────────────────────────

startup: ## Full startup: infra + K3s + secrets + Helm deploy (run after make infra-up)
	bash scripts/startup.sh

# ─── Safety ────────────────────────────────────────────────────────────────────

destroy-all: ## Full teardown (helm uninstall + terraform destroy)
	helm uninstall deploytracker -n deploytracker --ignore-not-found
	helm uninstall observability -n observability --ignore-not-found
	kubectl delete namespace deploytracker --ignore-not-found
	kubectl delete namespace observability --ignore-not-found
	$(MAKE) infra-down
