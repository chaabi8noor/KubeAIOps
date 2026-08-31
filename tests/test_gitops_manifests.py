from pathlib import Path
import unittest

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class KindGitOpsApplicationTests(unittest.TestCase):
    def load_application(self, filename: str) -> dict:
        manifest = REPOSITORY_ROOT / "gitops" / "applications" / filename

        self.assertTrue(manifest.is_file())
        return yaml.safe_load(manifest.read_text(encoding="utf-8"))

    def test_application_uses_the_member_three_branch_and_local_values(self):
        application = self.load_application("capacity-api-kind.yaml")

        self.assertEqual(application["metadata"]["name"], "capacity-api-kind")
        self.assertEqual(application["spec"]["source"]["targetRevision"], "member3-capacityHealth")
        self.assertEqual(application["spec"]["source"]["helm"]["valueFiles"], ["values-local.yaml"])
        self.assertEqual(application["spec"]["destination"]["namespace"], "kubeaiops")

    def test_anomaly_application_uses_the_completed_member_one_branch_and_local_image(self):
        application = self.load_application("anomaly-api-kind.yaml")

        self.assertEqual(application["metadata"]["name"], "anomaly-api-kind")
        self.assertEqual(application["spec"]["source"]["targetRevision"], "member1-infrastructure")
        self.assertEqual(application["spec"]["source"]["path"], "member-1-infrastructure/helm/anomaly-api")
        self.assertEqual(
            application["spec"]["source"]["helm"]["parameters"],
            [{"name": "image.pullPolicy", "value": "Never"}],
        )
        self.assertEqual(application["spec"]["destination"]["namespace"], "kubeaiops")

    def test_release_risk_application_uses_the_completed_member_two_branch_and_image(self):
        application = self.load_application("release-risk-api-kind.yaml")

        self.assertEqual(application["metadata"]["name"], "release-risk-api-kind")
        self.assertEqual(application["spec"]["source"]["targetRevision"], "member2/containerize-and-deploy")
        self.assertEqual(application["spec"]["source"]["path"], "member-2-release/helm/release-risk-api")
        self.assertEqual(
            application["spec"]["source"]["helm"]["parameters"],
            [{"name": "image.tag", "value": "95e5aef"}],
        )
        self.assertEqual(application["spec"]["destination"]["namespace"], "kubeaiops")
