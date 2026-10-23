"""Comprueba la configuración de un build manual antes de autenticar con GCP."""

import json
import os
import re
from pathlib import Path


def repository_file(value: str, label: str) -> None:
    root = Path.cwd().resolve()
    path = Path(value).resolve()
    if not value or not path.is_relative_to(root) or not path.is_file():
        raise SystemExit(f"{label} debe ser un archivo dentro del repositorio.")


def main() -> None:
    for name in ("GCP_PROJECT_ID", "GCP_WIF_PROVIDER", "GCP_SERVICE_ACCOUNT"):
        if not os.environ.get(name, "").strip():
            raise SystemExit(f"Falta configurar la variable de GitHub Actions {name}.")

    repository_file(os.environ["PKR_VAR_ansible_playbook_file"], "El playbook")
    requirements = os.environ.get("ANSIBLE_REQUIREMENTS_FILE", "")
    if requirements:
        repository_file(requirements, "El archivo de dependencias Ansible")

    family = os.environ["PKR_VAR_image_family"]
    if not re.fullmatch(r"[a-z]([-a-z0-9]{0,37}[a-z0-9])?", family):
        raise SystemExit("La familia debe tener hasta 39 caracteres válidos para GCP.")

    try:
        arguments = json.loads(os.environ["PKR_VAR_ansible_extra_arguments"])
    except json.JSONDecodeError as exc:
        raise SystemExit("Los argumentos de Ansible deben ser una lista JSON.") from exc
    if not isinstance(arguments, list) or not all(isinstance(v, str) for v in arguments):
        raise SystemExit("Los argumentos de Ansible deben ser una lista JSON de strings.")

    print("Configuración e inputs del build válidos.")


if __name__ == "__main__":
    main()
