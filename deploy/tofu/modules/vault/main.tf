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
  description = "Whether to deploy HashiCorp Vault"
  type        = bool
  default     = false
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "opendatagov"
}

variable "vault_version" {
  description = "Vault Helm chart version"
  type        = string
  default     = "0.28.0"
}

resource "helm_release" "vault" {
  count = var.enabled ? 1 : 0

  name             = "vault"
  repository       = "https://helm.releases.hashicorp.com"
  chart            = "vault"
  version          = var.vault_version
  namespace        = var.namespace
  create_namespace = true

  values = [yamlencode({
    server = {
      dev = {
        enabled = true
      }
      resources = {
        requests = {
          memory = "256Mi"
          cpu    = "100m"
        }
      }
    }
    injector = {
      enabled = false
    }
  })]
}

output "enabled" {
  value = var.enabled
}
