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
  description = "Whether to deploy Keycloak"
  type        = bool
  default     = false
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "opendatagov"
}

variable "keycloak_version" {
  description = "Keycloak image tag"
  type        = string
  default     = "25.0"
}

resource "helm_release" "keycloak" {
  count = var.enabled ? 1 : 0

  name             = "keycloak"
  repository       = "https://codecentric.github.io/helm-charts"
  chart            = "keycloakx"
  version          = "2.4.0"
  namespace        = var.namespace
  create_namespace = true

  values = [yamlencode({
    image = {
      tag = var.keycloak_version
    }
    http = {
      relativePath = "/auth"
    }
    replicas = 1
    resources = {
      requests = {
        memory = "512Mi"
        cpu    = "250m"
      }
    }
  })]
}

output "enabled" {
  value = var.enabled
}
