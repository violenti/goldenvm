"""Pruebas unitarias de los helpers con filesystem y entorno aislados."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / ".github/scripts" / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_inputs = load_script("check-build-inputs")
image_summary = load_script("image-summary")


class IsolatedRepositoryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="goldenvm-unit-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)


class BuildInputsTests(IsolatedRepositoryTest):
    def setUp(self):
        super().setUp()
        Path("playbook.yml").write_text("---\n- hosts: packer\n")
        os.environ.update({
            "GCP_PROJECT_ID": "test-project",
            "GCP_WIF_PROVIDER": "test-provider",
            "GCP_SERVICE_ACCOUNT": "packer@test-project.iam.gserviceaccount.com",
            "PKR_VAR_ansible_playbook_file": "playbook.yml",
            "PKR_VAR_image_family": "debian-13-base",
            "PKR_VAR_ansible_extra_arguments": "[]",
        })

    def check(self, **overrides):
        with patch.dict(os.environ, overrides), redirect_stdout(io.StringIO()):
            check_inputs.main()

    def test_valid_defaults(self):
        self.check()

    def test_valid_custom_arguments_and_requirements(self):
        Path("requirements.yml").write_text("---\ncollections: []\n")
        self.check(
            ANSIBLE_REQUIREMENTS_FILE="requirements.yml",
            PKR_VAR_ansible_extra_arguments='["--tags", "packages"]',
        )

    def test_missing_gcp_configuration_is_rejected(self):
        for name in ("GCP_PROJECT_ID", "GCP_WIF_PROVIDER", "GCP_SERVICE_ACCOUNT"):
            with self.subTest(name=name), patch.dict(os.environ):
                del os.environ[name]
                with self.assertRaisesRegex(SystemExit, name):
                    self.check()
                os.environ[name] = "   "
                with self.assertRaisesRegex(SystemExit, name):
                    self.check()

    def test_invalid_json_arguments_are_rejected(self):
        for value in ("invalid", "{}", '"--tags"', "null", "[1]", "[true]"):
            with self.subTest(value=value), self.assertRaisesRegex(SystemExit, "lista JSON"):
                self.check(PKR_VAR_ansible_extra_arguments=value)

    def test_family_boundaries(self):
        for family in ("a", "a" * 39, "debian-13-web"):
            with self.subTest(family=family):
                self.check(PKR_VAR_image_family=family)
        for family in ("", "A", "1debian", "debian-", "debian_13", "a" * 40):
            with self.subTest(family=family), self.assertRaisesRegex(SystemExit, "familia"):
                self.check(PKR_VAR_image_family=family)

    def test_missing_files_and_directories_are_rejected(self):
        for value in ("", "missing.yml", "."):
            with self.subTest(value=value), self.assertRaisesRegex(SystemExit, "archivo"):
                self.check(PKR_VAR_ansible_playbook_file=value)
        with self.assertRaisesRegex(SystemExit, "dependencias"):
            self.check(ANSIBLE_REQUIREMENTS_FILE="missing.yml")

    def test_files_outside_repository_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="goldenvm-outside-") as directory:
            outside = Path(directory) / "outside.yml"
            outside.write_text("---\n")
            Path("linked.yml").symlink_to(outside)
            for value in (str(outside), "linked.yml", os.path.relpath(outside)):
                with self.subTest(value=value), self.assertRaisesRegex(SystemExit, "repositorio"):
                    self.check(PKR_VAR_ansible_playbook_file=value)
            with self.assertRaisesRegex(SystemExit, "repositorio"):
                self.check(ANSIBLE_REQUIREMENTS_FILE=str(outside))


class ImageSummaryTests(IsolatedRepositoryTest):
    def test_summary_uses_latest_build_and_appends_to_existing_content(self):
        old = {
            "artifact_id": "test-project:old-image",
            "custom_data": {
                "image_name": "old-image", "image_family": "debian-13-base",
                "playbook": "ansible/playbooks/base.yml",
            },
        }
        latest = {
            "artifact_id": "test-project:debian-13-web-20261012-120000",
            "custom_data": {
                "image_name": "debian-13-web-20261012-120000",
                "image_family": "debian-13-web", "playbook": "ansible/playbooks/web.yml",
            },
        }
        Path("manifest.json").write_text(json.dumps({"builds": [old, latest]}))
        summary = Path("summary.md")
        summary.write_text("Resumen previo\n")
        os.environ.update({
            "GCP_PROJECT_ID": "test-project", "GITHUB_SHA": "test-commit",
            "GITHUB_STEP_SUMMARY": str(summary),
        })
        image_summary.main()
        content = summary.read_text()
        self.assertTrue(content.startswith("Resumen previo\n"))
        for expected in (*latest["custom_data"].values(), latest["artifact_id"], "test-commit"):
            self.assertIn(expected, content)
        self.assertNotIn("old-image", content)
        self.assertIn(
            "projects/test-project/global/images/"
            "debian-13-web-20261012-120000?project=test-project", content,
        )


if __name__ == "__main__":
    unittest.main()
