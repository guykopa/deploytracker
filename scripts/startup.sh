#!/usr/bin/env bash
set -euo pipefail

REGION="eu-west-3"
ECR_URL="378202225330.dkr.ecr.eu-west-3.amazonaws.com/deploytracker"
ANSIBLE="/home/kopa/deploytracker/app/.venv/bin/ansible-playbook"
ANSIBLE_DIR="/home/kopa/deploytracker/infra/ansible"

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── 1. Infrastructure ─────────────────────────────────────────────────────────
log "Provisioning AWS infrastructure..."
cd /home/kopa/deploytracker/infra/terraform
terraform init -reconfigure -input=false
terraform apply -auto-approve

# ── 2. K3s cluster ────────────────────────────────────────────────────────────
log "Configuring K3s cluster..."
cd "$ANSIBLE_DIR"
$ANSIBLE playbooks/01-bootstrap.yml
$ANSIBLE playbooks/02-k3s-server.yml
$ANSIBLE playbooks/03-k3s-agents.yml
$ANSIBLE playbooks/04-fetch-kubeconfig.yml

# ── 3. Docker image ───────────────────────────────────────────────────────────
log "Building and pushing Docker image..."
cd /home/kopa/deploytracker
make docker-push

# ── 4. Kubernetes namespaces with Helm labels ─────────────────────────────────
log "Creating namespaces..."
for NS in observability deploytracker; do
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
  kubectl label namespace "$NS" app.kubernetes.io/managed-by=Helm --overwrite
  kubectl annotate namespace "$NS" \
    meta.helm.sh/release-name="$NS" \
    meta.helm.sh/release-namespace="$NS" --overwrite
done

# ── 5. Kubernetes secrets ─────────────────────────────────────────────────────
log "Creating secrets..."

# ECR credentials
ECR_TOKEN=$(aws ecr get-login-password --region "$REGION")
kubectl create secret docker-registry ecr-credentials \
  --docker-server="$ECR_URL" \
  --docker-username=AWS \
  --docker-password="$ECR_TOKEN" \
  --namespace deploytracker \
  --dry-run=client -o yaml | kubectl apply -f -

# DB password from SSM
DB_PASSWORD=$(aws ssm get-parameter --region "$REGION" \
  --name /deploytracker/db_password --with-decryption \
  --query Parameter.Value --output text)
GRAFANA_PASSWORD=$(aws ssm get-parameter --region "$REGION" \
  --name /deploytracker/grafana_admin_password --with-decryption \
  --query Parameter.Value --output text)

kubectl create secret generic deploytracker-secrets \
  --from-literal=db_password="$DB_PASSWORD" \
  --from-literal=DEPLOYTRACKER_DATABASE_URL="postgresql://deploytracker:${DB_PASSWORD}@postgres.deploytracker.svc.cluster.local:5432/deploytracker" \
  --namespace deploytracker \
  --dry-run=client -o yaml | kubectl apply -f -

# ── 6. Helm deployments ───────────────────────────────────────────────────────
log "Deploying observability stack..."
helm dependency update /home/kopa/deploytracker/charts/observability
helm upgrade --install observability /home/kopa/deploytracker/charts/observability \
  --namespace observability --wait --timeout 12m

log "Deploying deploytracker application..."
helm upgrade --install deploytracker /home/kopa/deploytracker/charts/deploytracker \
  --namespace deploytracker \
  --set grafana.adminPassword="$GRAFANA_PASSWORD" \
  --wait --timeout 5m

# ── 7. Done ───────────────────────────────────────────────────────────────────
SERVER_IP=$(cd /home/kopa/deploytracker/infra/terraform && terraform output -raw k3s_server_public_ip 2>/dev/null)
log "Done!"
echo ""
echo "  API:     http://${SERVER_IP}:30080/docs"
echo "  Grafana: http://${SERVER_IP}:30030  (admin / ${GRAFANA_PASSWORD})"
echo ""
