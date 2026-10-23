"""Pruebas de la plantilla con el CLI real de Packer, sin construir VMs."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def packer(*arguments, input_text=None):
    # Las variables locales del desarrollador no deben alterar los casos.
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("PKR_VAR_")
    }
    environment["PACKER_PLUGIN_PATH"] = str(ROOT / ".packer.d/plugins")
    return subprocess.run(
        ["packer", *arguments], cwd=ROOT, env=environment,
        input=input_text, capture_output=True, text=True, timeout=30,
    )


class PackerTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("packer") is None:
            raise RuntimeError("Instalar Packer para ejecutar las pruebas de la plantilla.")

    def test_template_syntax(self):
        result = packer("validate", "-syntax-only", "-var", "project_id=test-project", ".")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_image_name_uses_selected_family_and_gcp_compatible_timestamp(self):
        for family in ("debian-13-base", "web", "a" * 39):
            with self.subTest(family=family):
                result = packer(
                    "console", "-var", "project_id=test-project",
                    "-var", f"image_family={family}", ".",
                    input_text="local.image_name\n",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                name = result.stdout.strip().strip('"')
                self.assertRegex(name, rf"^{re.escape(family)}-\d{{8}}-\d{{6}}$")
                self.assertLessEqual(len(name), 63)


class PackerVariableValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("packer") is None:
            raise RuntimeError("Instalar Packer para ejecutar las pruebas de variables.")
        result = packer("plugins", "installed")
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        required_plugins = ("packer-plugin-googlecompute_", "packer-plugin-ansible_")
        if not all(name in result.stdout for name in required_plugins):
            message = "Faltan plugins de Packer: ejecutar packer init ."
            if os.environ.get("CI") == "true":
                raise RuntimeError(message)
            raise unittest.SkipTest(message)

    def validate(self, **variables):
        values = {"project_id": "test-project", **variables}
        arguments = ["validate"]
        for name, value in values.items():
            if isinstance(value, (bool, list)):
                value = json.dumps(value)
            arguments.extend(["-var", f"{name}={value}"])
        return packer(*arguments, ".")

    def test_valid_configuration_variants(self):
        cases = [
            {},
            {"use_iap": False},
            {"image_family": "a"},
            {"image_family": "a" * 39},
            {"ansible_playbook_file": "ansible/playbooks/web.yml"},
            {"ansible_extra_arguments": ["--tags", "packages"]},
        ]
        for variables in cases:
            with self.subTest(variables=variables):
                result = self.validate(**variables)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_project_is_rejected(self):
        for project in ("", "   "):
            with self.subTest(project=project):
                result = self.validate(project_id=project)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Debes indicar project_id", result.stdout + result.stderr)

    def test_invalid_image_families_are_rejected(self):
        for family in ("", "Debian", "1debian", "debian-", "debian_13", "a" * 40):
            with self.subTest(family=family):
                result = self.validate(image_family=family)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Usa hasta 39 caracteres", result.stdout + result.stderr)

    def test_missing_playbook_is_rejected(self):
        result = self.validate(ansible_playbook_file="ansible/playbooks/missing.yml")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("archivo existente", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
