# --- Prometheus + Grafana via Helm ---

resource "helm_release" "prometheus" {
  name             = "prometheus"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true
  version          = "57.0.1"

  values = [
    yamlencode({
      # Grafana
      grafana = {
        enabled = true
        service = {
          type = "LoadBalancer"
        }
        adminPassword = "changeme-on-first-login"
        persistence = {
          enabled = true
          size    = "5Gi"
        }
        "grafana.ini" = {
          security = {
            disable_initial_admin_creation = false
          }
          server = {
            root_url = "/"
          }
        }
      }

      # Prometheus
      prometheus = {
        prometheusSpec = {
          retention         = "7d"
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "20Gi"
                  }
                }
              }
            }
          }
          # Security: disable remote write receiver
          enableRemoteWriteReceiver = false
        }
      }

      # Alertmanager
      alertmanager = {
        enabled = true
        alertmanagerSpec = {
          storage = {
            volumeClaimTemplate = {
              spec = {
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "5Gi"
                  }
                }
              }
            }
          }
        }
      }

      # Node exporter
      nodeExporter = {
        enabled = true
      }

      # Kube state metrics
      kubeStateMetrics = {
        enabled = true
      }
    })
  ]

  depends_on = [module.eks]
}

# --- Network Policies (restrict pod-to-pod traffic) ---
resource "kubernetes_network_policy" "default_deny_ingress" {
  metadata {
    name      = "default-deny-ingress"
    namespace = "default"
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]
  }

  depends_on = [module.eks]
}

resource "kubernetes_network_policy" "monitoring_deny_ingress" {
  metadata {
    name      = "default-deny-ingress"
    namespace = "monitoring"
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]
  }

  depends_on = [helm_release.prometheus]
}
