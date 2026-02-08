terraform {
  required_version = ">= 1.6"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.0"
    }
  }
}

variable "enabled" {
  description = "Whether to deploy ArgoCD"
  type        = bool
  default     = false
}

variable "namespace" {
  description = "Kubernetes namespace for ArgoCD"
  type        = string
  default     = "argocd"
}

variable "argocd_version" {
  description = "ArgoCD Helm chart version"
  type        = string
  default     = "7.3.0"
}

resource "helm_release" "argocd" {
  count = var.enabled ? 1 : 0

  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_version
  namespace        = var.namespace
  create_namespace = true

  values = [yamlencode({
    server = {
      service = {
        type = "ClusterIP"
      }
      resources = {
        requests = {
          memory = "256Mi"
          cpu    = "100m"
        }
      }
    }
    configs = {
      params = {
        "server.insecure" = true
      }
    }
  })]
}

output "enabled" {
  value = var.enabled
}
