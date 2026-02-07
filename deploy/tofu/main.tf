terraform {
  required_version = ">= 1.6"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

resource "helm_release" "opendatagov" {
  name             = "opendatagov"
  chart            = "${path.module}/../helm/opendatagov"
  namespace        = var.namespace
  create_namespace = true
  wait             = var.wait

  values = [
    file("${path.module}/../helm/opendatagov/${var.values_file}")
  ]
}
