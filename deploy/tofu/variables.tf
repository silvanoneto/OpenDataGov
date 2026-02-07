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
