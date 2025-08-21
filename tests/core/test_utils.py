import unittest
from kubernetes.client import V1EnvFromSource, V1SecretReference

from gaiaflow.core.utils import inject_params_as_env_vars, \
    build_env_from_secrets


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
