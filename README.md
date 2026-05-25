# EKS Microservices Lab

Production-grade Kubernetes microservices architecture on AWS EKS, with CI/CD, monitoring, and SRE automation.

## Architecture

```
Internet → ALB → Frontend (Node.js)
                      ↓
                API Gateway (Node.js)
                      ↓
               Backend Service (Node.js)
```

## Stack

- **Compute:** AWS EKS 1.34 (Spot instances)
- **Container Registry:** Amazon ECR
- **Monitoring:** Prometheus + Grafana
- **CI/CD:** GitHub Actions
- **IaC:** Terraform
- **Security:** IMDSv2, IRSA, Network Policies, Non-root containers, ECR image scanning

## Project Structure

```
├── terraform/          # Infrastructure as Code
├── microservices/      # Application source code
│   ├── frontend/       # Web UI (Express + HTML)
│   ├── api-gateway/    # API routing & aggregation
│   └── backend-service/# Business logic & data
├── k8s/                # Kubernetes manifests
└── .github/workflows/  # CI/CD pipelines
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 3002 | Web UI, serves HTML, proxies API calls |
| api-gateway | 3001 | Routes requests, aggregates health checks |
| backend-service | 3000 | Product catalog API, business logic |

## Quick Start

### Prerequisites
- AWS CLI configured
- Terraform >= 1.5
- kubectl
- Docker

### Deploy Infrastructure
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Deploy Microservices
```bash
# Login to ECR
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-southeast-1.amazonaws.com

# Build & push
docker build -t <ecr-url>/backend-service:v1.0.0 microservices/backend-service/
docker push <ecr-url>/backend-service:v1.0.0

# Deploy to EKS
kubectl apply -f k8s/microservices.yaml
```

## Monitoring

- **Grafana:** Available via LoadBalancer (namespace: monitoring)
- **Prometheus:** Scrapes `/metrics` from all services
- **Alertmanager:** Configured for alerting

## Security Highlights

- EKS secrets encrypted at rest
- Worker nodes in private subnets
- IMDSv2 enforced (prevents SSRF credential theft)
- IRSA for pod-level IAM (no shared node credentials)
- ECR immutable tags + scan on push
- Network policies restrict pod-to-pod traffic
- Non-root containers

## Author

**Abdul Hakim** — Cloud/DevOps Engineer
- GitHub: [@ahakimx](https://github.com/ahakimx)
- Twitter: [@a_hakimx](https://twitter.com/a_hakimx)
