import subprocess
import unittest
from unittest.mock import patch

from kubernetes.client import V1EnvFromSource, V1SecretReference

from gaiaflow.core.utils import (
    build_env_from_secrets,
    docker_network_gateway,
    inject_params_as_env_vars,
)


class TestUtils(unittest.TestCase):
    def test_inject_params_as_env_vars(self):
        params = {"foo": "bar", "baz": "qux"}
        expected = {
            "PARAMS_FOO": "{{ params.foo }}",
            "PARAMS_BAZ": "{{ params.baz }}",
        }

        result = inject_params_as_env_vars(params)
        self.assertIsInstance(result, dict)
        self.assertEqual(result, expected)

    def test_inject_params_as_env_vars_empty(self):
        params = {}
        result = inject_params_as_env_vars(params)
        self.assertEqual(result, {})

    def test_build_env_from_secrets(self):
        secrets = ["db-secret", "api-secret"]
        result = build_env_from_secrets(secrets)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(e, V1EnvFromSource) for e in result))

        self.assertIsInstance(result[0].secret_ref, V1SecretReference)
        self.assertEqual(result[0].secret_ref.name, "db-secret")

        self.assertEqual(result[1].secret_ref.name, "api-secret")

    def test_build_env_from_secrets_empty(self):
        result = build_env_from_secrets([])
        self.assertEqual(result, [])

    def test_gateway_found(self):
        mock_output = '{"Gateway": "172.18.0.1"}'
        with patch("gaiaflow.core.utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["docker"], returncode=0, stdout=mock_output
            )
            result = docker_network_gateway()
        self.assertEqual(result, "172.18.0.1")

    def test_gateway_not_found(self):
        with patch("gaiaflow.core.utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["docker"], returncode=0, stdout="{}"
            )
            result = docker_network_gateway()
        self.assertIsNone(result)

    def test_docker_not_installed(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = docker_network_gateway()
        self.assertIsNone(result)
