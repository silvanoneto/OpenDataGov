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
  description = "Whether to deploy DataHub"
  type        = bool
  default     = false
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "opendatagov"
}

variable "datahub_version" {
  description = "DataHub Helm chart version"
  type        = string
  default     = "0.4.0"
}

resource "helm_release" "datahub_prerequisites" {
  count = var.enabled ? 1 : 0

  name             = "datahub-prerequisites"
  repository       = "https://helm.datahubproject.io/"
  chart            = "datahub-prerequisites"
  version          = var.datahub_version
  namespace        = var.namespace
  create_namespace = true

  values = [yamlencode({
    elasticsearch = {
      replicas = 1
    }
  })]
}

resource "helm_release" "datahub" {
  count = var.enabled ? 1 : 0

  name             = "datahub"
  repository       = "https://helm.datahubproject.io/"
  chart            = "datahub"
  version          = var.datahub_version
  namespace        = var.namespace
  create_namespace = true

  depends_on = [helm_release.datahub_prerequisites]

  values = [yamlencode({
    datahub-gms = {
      resources = {
        requests = {
          memory = "512Mi"
        }
      }
    }
    datahub-frontend = {
      resources = {
        requests = {
          memory = "256Mi"
        }
      }
    }
  })]
}

output "enabled" {
  value = var.enabled
}
