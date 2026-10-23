"""Publica el identificador de la imagen creada en el resumen de GitHub Actions."""

import json
import os
from pathlib import Path


def main() -> None:
    manifest = json.loads(Path("manifest.json").read_text())
    build = manifest["builds"][-1]
    data = build["custom_data"]
    image_name = data["image_name"]
    project = os.environ["GCP_PROJECT_ID"]
    lines = [
        "## Imagen Debian 13 creada",
        "",
        f"- Proyecto: `{project}`",
        f"- Imagen: `{image_name}`",
        f"- Familia: `{data['image_family']}`",
        f"- Playbook: `{data['playbook']}`",
        f"- Artefacto Packer: `{build['artifact_id']}`",
        f"- Commit: `{os.environ['GITHUB_SHA']}`",
        "",
        f"[Ver imagen en GCP](https://console.cloud.google.com/compute/imagesDetail/"
        f"projects/{project}/global/images/{image_name}?project={project})",
        "",
    ]
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
        summary.write("\n".join(lines))


if __name__ == "__main__":
    main()
