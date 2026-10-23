# Copiar a debian13.pkrvars.hcl y ajustar antes de construir.
project_id = "mi-proyecto-gcp"
zone       = "us-central1-a"

network    = "default"
subnetwork = ""

# IAP necesita firewall y Cloud NAT/proxy para apt; ver README.md.
use_iap = true

machine_type = "e2-standard-2"
image_family = "debian-13-base"

# Cambiar este archivo para construir otra variante de la imagen.
ansible_playbook_file = "ansible/playbooks/base.yml"
# ansible_playbook_file = "ansible/playbooks/web.yml"

# Los argumentos se pasan como lista, sin interpretación por un shell.
ansible_extra_arguments = []
# ansible_extra_arguments = ["--extra-vars", "@/ruta/variables.yml"]

# Opcional: fijar la imagen oficial en vez de seguir debian-13.
# source_image = "nombre-obtenido-con-gcloud"

# Shared VPC: indicar el proyecto host y una subred de ese proyecto.
# network_project_id = "mi-proyecto-host"
