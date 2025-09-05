import unittest
from typer.testing import CliRunner

from gaiaflow.cli.cli import app as root_app

runner = CliRunner()


class TestGaiaflowRootCLI(unittest.TestCase):

    def test_help_message_shows(self):
        result = runner.invoke(root_app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Gaiaflow CLI is a manager tool", result.stdout)
        self.assertIn("dev", result.stdout)
        self.assertIn("prod-local", result.stdout)