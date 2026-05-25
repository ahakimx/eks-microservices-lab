# Security Review & Hardening Notes

## ✅ Security measures implemented:

### Encryption
- [x] EKS secrets encrypted at rest with KMS (key rotation enabled)
- [x] EBS volumes encrypted on worker nodes
- [x] ECR images encrypted (AES256)

### Network
- [x] Worker nodes in private subnets (no direct internet access)
- [x] NAT gateway for outbound traffic only
- [x] Network policies: default deny ingress on `default` and `monitoring` namespaces
- [x] Cluster endpoint: private access enabled

### IAM & Access
- [x] IRSA enabled (pod-level IAM, no shared node role)
- [x] EKS access entries (no aws-auth ConfigMap, more secure)
- [x] IMDSv2 required on nodes (prevents SSRF-based credential theft)

### Container Security
- [x] ECR image scanning on push (vulnerability detection)
- [x] Immutable image tags (prevents supply chain attacks via tag overwrite)
- [x] ECR lifecycle policy (cleanup old images)

### Logging & Monitoring
- [x] All EKS control plane logs enabled (api, audit, authenticator, controllerManager, scheduler)
- [x] Prometheus + Grafana for cluster monitoring
- [x] Alertmanager for alerting

### Cost Optimization
- [x] Spot instances (60% savings)
- [x] Single NAT gateway (lab environment)
- [x] ECR lifecycle policy (prevent storage bloat)

---

## ⚠️ Known trade-offs (acceptable for lab):

| Item | Lab Setting | Production Recommendation |
|------|-------------|--------------------------|
| Public API endpoint | 0.0.0.0/0 | Restrict to office/VPN CIDR |
| Single NAT gateway | 1 AZ | Multi-AZ for HA |
| Grafana password | Static in TF | Use Secrets Manager |
| Grafana LB | Public | Internal + VPN |
| Spot instances | 100% spot | Mix on-demand + spot |

---

## 🔒 Post-deploy hardening (manual steps):

1. Change Grafana admin password immediately after deploy
2. Consider adding OPA/Gatekeeper for pod security policies
3. Enable GuardDuty EKS protection (free trial 30 days)
4. Add AWS WAF in front of public LoadBalancers if needed
