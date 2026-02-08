variable "kubeconfig_path" {
  description = "Path to kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace for opendatagov"
  type        = string
  default     = "opendatagov"
}

variable "values_file" {
  description = "Helm values file to use"
  type        = string
  default     = "values-dev.yaml"
}

variable "wait" {
  description = "Wait for all pods to be ready before marking release as successful"
  type        = bool
  default     = false
}

variable "enable_keycloak" {
  description = "Deploy Keycloak for OIDC authentication"
  type        = bool
  default     = false
}

variable "enable_vault" {
  description = "Deploy HashiCorp Vault for secrets management"
  type        = bool
  default     = false
}

variable "enable_datahub" {
  description = "Deploy DataHub metadata catalog"
  type        = bool
  default     = false
}

variable "enable_argocd" {
  description = "Deploy ArgoCD for GitOps"
  type        = bool
  default     = false
}
