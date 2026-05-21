# Quickstart

This guide walks you from zero to a fully running deploytracker cluster on AWS.

---

## Prerequisites

Install these tools before you start:

- **AWS CLI** configured (`aws configure`) with an account in `eu-west-3`
- **Terraform** 1.7+
- **Ansible** 2.16+ with required collections:
  ```bash
  ansible-galaxy collection install amazon.aws community.aws community.general
  ```
- **Docker**
- **kubectl** + **helm** 3
- **Python** 3.11+

---

## 1. Clone and bootstrap (one-time only)

```bash
git clone https://github.com/guykopa/deploytracker.git
cd deploytracker

# Create the S3 bucket for Terraform remote state (run once ever)
bash scripts/bootstrap.sh

# Copy and fill in your secrets
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Edit `infra/terraform/terraform.tfvars` and set:

```hcl
db_password            = "your-strong-db-password"
grafana_admin_password = "your-grafana-password"
k3s_token              = "your-k3s-join-token"
alert_email            = "you@example.com"
```

!!! warning "Never commit terraform.tfvars"
    This file contains secrets. It is gitignored. Keep it out of version control.

---

## 2. Start a session

```bash
make startup
```

This single command runs the full sequence:

| Step | What it does |
|---|---|
| 1. `terraform apply` | Provisions VPC, 3 × EC2 t3.small, ECR, IAM roles, SSM parameters, CloudWatch budget |
| 2. Ansible bootstrap | Installs Docker, K3s server on control-plane, joins 2 agent nodes |
| 3. `docker build + push` | Builds the FastAPI image and pushes to ECR |
| 4. Namespaces | Creates `deploytracker` and `observability` namespaces |
| 5. Secrets | Creates `ecr-credentials` pull secret and `deploytracker-secrets` (DB, JWT, admin creds) |
| 6. Helm: observability | Deploys Prometheus, Loki, Grafana, OTel Collector, Promtail |
| 7. Helm: deploytracker | Deploys FastAPI app and PostgreSQL |

Expected time: **8–12 minutes** from scratch.

---

## 3. Verify the cluster

```bash
# Get the public IP of the control-plane
export IP=$(terraform -chdir=infra/terraform output -raw k3s_server_public_ip)

# Check API health
curl http://$IP:30080/health/ready
# → {"status":"ok"}

# Get a JWT token
TOKEN=$(curl -s -X POST http://$IP:30080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=$DEPLOYTRACKER_ADMIN_PASSWORD" \
  | jq -r .access_token)

# Call a protected endpoint
curl -H "Authorization: Bearer $TOKEN" http://$IP:30080/api/v1/services
# → []  (empty list — no services registered yet)

# Open Grafana
make grafana
# Browser: http://$IP:30030  (admin / your grafana password)
```

---

## 4. Generate synthetic load (optional)

```bash
make loadgen-start
```

This deploys a CronJob that simulates 5 services deploying every 10 seconds. After a few minutes, DORA metrics will be visible in Grafana and via the API.

```bash
# Check DORA metrics for a simulated service
curl -H "Authorization: Bearer $TOKEN" \
  http://$IP:30080/api/v1/services/payment-service/dora
```

To stop:
```bash
make loadgen-stop
```

---

## 5. Record a real deployment event

Use this from a GitHub Actions workflow or any CI/CD pipeline:

```bash
TOKEN=$(curl -s -X POST http://$IP:30080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=$DEPLOYTRACKER_ADMIN_PASSWORD" \
  | jq -r .access_token)

curl -X POST http://$IP:30080/api/v1/deployments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "my-service",
    "version": "v1.2.3",
    "environment": "production",
    "commit_sha": "abc123def456",
    "deployer": "github-actions",
    "commit_timestamp": "2026-05-21T10:00:00Z",
    "deployed_at": "2026-05-21T10:30:00Z"
  }'
```

---

## 6. Tear down — CRITICAL

```bash
make destroy-all
```

!!! danger "Always run this at the end of every session"
    Three t3.small instances cost ~$1.64/day. Forgetting to destroy them will cost money.
    
    `make destroy-all` runs:
    1. `helm uninstall deploytracker -n deploytracker`
    2. `helm uninstall observability -n observability`
    3. `kubectl delete ns deploytracker observability`
    4. `terraform destroy`
    
    PersistentVolumes (EBS volumes) are deleted as part of the namespace cleanup.

---

## NodePorts

| Service | Port |
|---|---|
| deploytracker API | `30080` |
| Grafana | `30030` |

---

## Cost summary

| Resource | Cost |
|---|---|
| 3 × t3.small EC2 (eu-west-3) | ~$49/month if running 24/7 |
| 3 × 8 GB EBS gp3 | ~$2/month |
| ECR storage | <$1/month |
| SSM parameters | Free |
| **Total (24/7)** | **~$52/month** |

A CloudWatch budget alarm triggers at **$10/month**, giving early warning before costs accumulate.
