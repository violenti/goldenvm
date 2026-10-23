packer {
  required_version = ">= 1.14.0"

  required_plugins {
    googlecompute = {
      source  = "github.com/hashicorp/googlecompute"
      version = "= 1.2.7"
    }
    ansible = {
      source  = "github.com/hashicorp/ansible"
      version = "= 1.1.6"
    }
  }
}

source "googlecompute" "debian13" {
  project_id = var.project_id
  zone       = var.zone

  source_image_project_id = ["debian-cloud"]
  source_image_family     = "debian-13"
  source_image            = var.source_image

  machine_type = var.machine_type
  disk_size    = 20
  disk_type    = "pd-balanced"

  network            = var.network
  subnetwork         = var.subnetwork
  network_project_id = var.network_project_id
  tags               = ["packer-build"]

  use_iap          = var.use_iap
  omit_external_ip = var.use_iap
  use_internal_ip  = var.use_iap

  # La identidad que ejecuta Packer autentica por ADC. La VM no necesita una SA.
  disable_default_service_account = true
  use_os_login                    = true
  ssh_username                    = "packer"
  ssh_timeout                     = "10m"

  image_name        = local.image_name
  image_family      = var.image_family
  image_description = "Debian 13 amd64 para GCP, actualizado con Packer. Build ${local.build_id}."
  image_labels = {
    os         = "debian"
    os_version = "13"
    managed_by = "packer"
  }
}
