# ADR-003: K3s on EC2 vs Amazon EKS

**Date:** 2026-05-21
**Status:** Accepted

## Context

The deploytracker project requires a Kubernetes cluster to demonstrate real-world
deployment patterns (rolling updates, namespaced workloads, Helm chart management,
RBAC). The cluster must run at near-zero cost on AWS, targeting the EC2 free tier
(t2.micro instances, 750 hours/month for 12 months).

Three orchestration approaches were evaluated:

| Option          | Control plane cost | Worker nodes | Suitable for cloud demo? |
|-----------------|--------------------|--------------|--------------------------|
| Amazon EKS      | $0.10/hour         | EC2 (extra)  | No — $73+/month          |
| K3s on EC2      | $0 (self-managed)  | EC2 t2.micro | Yes                      |
| Kind / Minikube | $0                 | Local only   | No — not cloud-deployed  |

## Decision

Self-host **K3s** on three EC2 t2.micro instances (1 server + 2 agents) provisioned
by Terraform and configured by Ansible.

K3s is a CNCF-certified, production-grade Kubernetes distribution packaged as a single
binary (~70 MiB). It strips optional components (cloud-controller-manager, in-tree
volume plugins) to reduce the idle RAM footprint to ~300 MiB for the control plane.

The cluster topology:
- `k3s-server` (control plane + etcd) — 1 × t2.micro
- `k3s-agent-1`, `k3s-agent-2` (workers) — 2 × t2.micro

## Alternatives Considered

### Amazon EKS

EKS is the canonical Kubernetes offering on AWS and provides a fully managed control
plane, seamless IAM integration, and automatic upgrades. However, the control plane
alone costs **$0.10 per hour = $72.80/month**. Adding three t2.micro worker nodes
(~$0.0116/hour each) brings the monthly total to ~$81. This is approximately **7,300×
the budget** of the free-tier EC2 approach.

EKS also requires additional IAM roles, VPC CNI plugin configuration, and a longer
provisioning time, which increases complexity for a demo project.

Rejected: **cost is prohibitive for a zero-budget project.**

### Kind (Kubernetes IN Docker) / Minikube

Both tools create a local single-node or multi-node Kubernetes cluster inside Docker or
a VM on the developer's workstation. They are ideal for local development and CI
testing but cannot demonstrate a real cloud deployment: there is no public IP, no AWS
load balancer, no persistent storage backed by EBS, and no demonstration of Ansible
provisioning over SSH.

Rejected: **not a cloud deployment; cannot validate the full infrastructure pipeline.**

## Consequences

### Positive
- Total EC2 cost: $0 within the AWS free tier (750 h/month × 3 instances).
- K3s passes the CNCF Kubernetes conformance tests; workloads and manifests are
  portable to EKS or GKE without modification.
- The single-binary architecture simplifies Ansible provisioning: one `curl | sh`
  command installs and starts K3s.
- NodePort services (API: 30080, Grafana: 30030) are reachable directly on the server
  public IP without an AWS load balancer.

### Negative
- No managed control plane: K3s upgrades (e.g., CVE patches) must be applied manually
  via Ansible.
- Single control-plane node is a single point of failure; K3s HA mode (embedded etcd
  with 3 server nodes) would require 3 additional instances, exceeding the free tier.
- No AWS cloud-controller-manager integration out of the box: `LoadBalancer` service
  types are not automatically provisioned (NodePort is used instead).
- etcd is replaced by SQLite by default in K3s single-server mode, which limits
  cluster state to the server node's local disk.

## References

- K3s documentation — <https://docs.k3s.io/>
- CNCF K3s conformance — <https://landscape.cncf.io/?item=platform--certified-kubernetes-distribution--k3s>
- AWS EC2 free tier — <https://aws.amazon.com/free/>
- EKS pricing — <https://aws.amazon.com/eks/pricing/>
- `infra/terraform/` — cluster provisioning
- `infra/ansible/` — K3s installation playbooks
