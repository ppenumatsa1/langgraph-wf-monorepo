from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLACEHOLDER = "${{connections.underwritingruntimesecrets.credentials.database_url}}"


class HostedRuntimeSecretContractTests(unittest.TestCase):
    def test_hosted_definition_uses_only_connection_placeholders(self) -> None:
        deploy = (ROOT / "scripts/foundry/deploy_hosted_container.py").read_text()
        azure_yaml = (ROOT / "infra/foundry-hosted/azure.yaml").read_text()

        self.assertIn("connections.{runtime_connection_name}.credentials.database_url", deploy)
        self.assertNotIn('"DATABASE_URL": runtime_database_url', deploy)
        self.assertNotIn('"RUNTIME_DATABASE_URL": runtime_database_url', deploy)
        self.assertEqual(azure_yaml.count(f"${PLACEHOLDER}"), 2)
        self.assertNotIn("DATABASE_URL: ${RUNTIME_DATABASE_URL}", azure_yaml)

    def test_custom_keys_connection_uses_secure_bicep_parameter(self) -> None:
        module = (
            ROOT / "infra/foundry-hosted/iac/modules/underwriting-runtime-secret-connection.bicep"
        ).read_text()
        convergence = (ROOT / "scripts/foundry/converge_runtime_secret_connection.sh").read_text()

        self.assertIn("@secure()", module)
        self.assertIn("category: 'CustomKeys'", module)
        self.assertIn("authType: 'CustomKeys'", module)
        self.assertIn("database_url: runtimeDatabaseUrl", module)
        self.assertIn("--parameters @/dev/stdin", convergence)
        self.assertNotIn("parameters_file", convergence)
        self.assertNotIn("backend/.tmp", convergence)
        self.assertIn('--subscription "$subscription_id"', convergence)

    def test_verification_checks_metadata_placeholder_not_secret(self) -> None:
        inspector = (ROOT / "scripts/foundry/inspect_hosted_agent.py").read_text()
        verifier = (ROOT / "scripts/foundry/verify_foundry_release.sh").read_text()

        self.assertIn("database_url_placeholder", inspector)
        self.assertIn("runtime_database_url_placeholder", inspector)
        self.assertNotIn("EXPECTED_RUNTIME_DATABASE_URL", inspector)
        self.assertNotIn("EXPECTED_RUNTIME_DATABASE_URL", verifier)
        self.assertIn("FOUNDRY_RUNTIME_CONNECTION_NAME", verifier)

    def test_release_builds_then_activates_hosted_before_apps(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        release = makefile.split("foundry-release-deploy:", 1)[1].split("\n\n", 1)[0]

        expected = [
            "$(MAKE) foundry-release-readiness",
            "$(MAKE) foundry-release-package",
            "$(MAKE) foundry-release-build",
            "$(MAKE) foundry-release-hosted-activate",
            "$(MAKE) foundry-release-app-deploy",
        ]
        offsets = [release.index(command) for command in expected]
        self.assertEqual(offsets, sorted(offsets))

    def test_release_dry_run_preserves_two_phase_deployment(self) -> None:
        result = subprocess.run(
            ["make", "-n", "foundry-release-deploy"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        expected = [
            "make foundry-release-readiness",
            "make foundry-release-package",
            "make foundry-release-build",
            "make foundry-release-hosted-activate",
            "make foundry-release-app-deploy",
        ]
        offsets = [output.index(command) for command in expected]
        self.assertEqual(offsets, sorted(offsets))

    def test_release_requires_committed_source(self) -> None:
        release = (ROOT / "scripts/foundry/deploy_public_dev.sh").read_text()

        self.assertIn("git status --porcelain --untracked-files=normal -- .", release)
        self.assertIn("Release requires a clean lane worktree committed at HEAD.", release)

    def test_frontend_build_uses_acr_without_local_registry_credentials(self) -> None:
        build = (ROOT / "scripts/foundry/build_release_images.sh").read_text()
        deploy = (ROOT / "scripts/foundry/deploy_public_frontend.sh").read_text()

        self.assertIn('build_acr_image \\\n    "$frontend_repository"', build)
        self.assertNotIn("az acr login", build)
        self.assertNotIn("docker push", build)
        self.assertNotIn("az acr build", deploy)
        self.assertIn("PUBLIC_FRONTEND_PREBUILT_IMAGE", deploy)
        self.assertIn("Reusing healthy frontend revision", deploy)

    def test_backend_reuse_requires_exact_version_and_live_health(self) -> None:
        deploy = (ROOT / "scripts/foundry/deploy_public_backend.sh").read_text()

        self.assertIn("FOUNDRY_HOSTED_AGENT_VERSION", deploy)
        self.assertIn('current_image" == "$image"', deploy)
        self.assertIn('current_hosted_version" == "$hosted_agent_version"', deploy)
        self.assertIn('current_target_port" == "8000"', deploy)
        self.assertIn("--target-port 8000", deploy)
        self.assertIn("/backend-health", deploy)
        self.assertIn("Reusing healthy backend revision", deploy)

    def test_backend_deploy_reads_hosted_version_after_activation(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        release = makefile.split("foundry-release-deploy:", 1)[1].split("\n\n", 1)[0]

        self.assertLess(
            release.index("$(MAKE) foundry-release-hosted-activate"),
            release.index("$(MAKE) foundry-release-app-deploy"),
        )

    def test_hosted_deploy_reuses_exact_active_image_version(self) -> None:
        deploy = (ROOT / "scripts/foundry/deploy_hosted_container.sh").read_text()

        self.assertIn("AGENT_UNDERWRITING_HOSTED_VERSION", deploy)
        self.assertIn('existing_status" == "active"', deploy)
        self.assertIn('existing_image" == "$image"', deploy)
        self.assertIn("Reusing active %s version %s", deploy)
        self.assertIn("Hosted agent RBAC verified", deploy)
        self.assertIn('reused_existing_version" != true', deploy)

    def test_standalone_azure_scripts_select_subscription(self) -> None:
        scripts = [
            "converge_hosted_agent_rbac.sh",
            "converge_runtime_secret_connection.sh",
            "deploy_hosted_container.sh",
            "deploy_public_backend.sh",
            "deploy_public_frontend.sh",
            "hosted_e2e.sh",
            "internalize_backend_ingress.sh",
            "preflight_foundry_model.sh",
            "verify_foundry_release.sh",
            "verify_project_appinsights_connection.sh",
            "verify_telemetry.sh",
        ]
        for name in scripts:
            source = (ROOT / "scripts/foundry" / name).read_text()
            with self.subTest(script=name):
                self.assertIn("AZURE_SUBSCRIPTION_ID", source)
                self.assertIn("az account set --subscription", source)


if __name__ == "__main__":
    unittest.main()
