variable "project_id" {
  type        = string
  description = "Proyecto donde se crea la VM temporal y se guarda la imagen."

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "Debes indicar project_id."
  }
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "Zona de construcción; debe coincidir con la región de la subred."
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "network" {
  type        = string
  default     = "default"
  description = "Nombre o URL de una VPC existente."
}

variable "subnetwork" {
  type        = string
  default     = ""
  description = "Nombre o URL de subred; obligatorio para VPC con subredes personalizadas."
}

variable "network_project_id" {
  type        = string
  default     = ""
  description = "Proyecto host para Shared VPC; vacío utiliza project_id."
}

variable "use_iap" {
  type        = bool
  default     = true
  description = "IAP y VM sin IP externa. Requiere salida a repositorios mediante NAT o proxy."
}

variable "source_image" {
  type        = string
  default     = ""
  description = "Imagen concreta de debian-cloud. Vacío selecciona la última de debian-13."
}

variable "image_family" {
  type    = string
  default = "debian-13-base"

  validation {
    condition     = can(regex("^[a-z]([-a-z0-9]{0,37}[a-z0-9])?$", var.image_family))
    error_message = "Usa hasta 39 caracteres, minúsculas, números y guiones; comienza con letra y termina con letra o número."
  }
}

variable "ansible_playbook_file" {
  type        = string
  default     = "ansible/playbooks/base.yml"
  description = "Playbook local a ejecutar. Admite ruta absoluta o relativa al directorio de ejecución."

  validation {
    condition     = fileexists(var.ansible_playbook_file)
    error_message = "La variable ansible_playbook_file debe apuntar a un archivo existente."
  }
}

variable "ansible_extra_arguments" {
  type        = list(string)
  default     = []
  description = "Argumentos adicionales para ansible-playbook, por ejemplo --extra-vars o --tags."
}
