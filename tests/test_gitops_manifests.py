from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class KindGitOpsApplicationTests(unittest.TestCase):
    def test_application_uses_the_member_three_branch_and_local_values(self):
        manifest = REPOSITORY_ROOT / "gitops" / "applications" / "capacity-api-kind.yaml"

        self.assertTrue(manifest.is_file())
        contents = manifest.read_text(encoding="utf-8")

        self.assertIn("name: capacity-api-kind", contents)
        self.assertIn("targetRevision: member3-capacityHealth", contents)
        self.assertIn("- values-local.yaml", contents)
        self.assertIn("namespace: kubeaiops", contents)
