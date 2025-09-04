import os
import unittest

from gaiaflow.testing import set_env_cm


class TestingTest(unittest.TestCase):
    def test_set_env_cm(self):
        old_env = dict(os.environ)
        with set_env_cm(PARAM_example="abc", PARAM_EXAMPLE="xyz"):
            self.assertEqual("abc", os.environ.get("PARAM_example"))
            self.assertEqual("xyz", os.environ.get("PARAM_EXAMPLE"))
            self.assertNotEqual(old_env, os.environ)
            with set_env_cm(PARAM_example=None, PARAM_EXAMPLE=None):
                self.assertEqual(None, os.environ.get("PARAM_example"))
                self.assertEqual(None, os.environ.get("PARAM_EXAMPLE"))
            self.assertEqual("abc", os.environ.get("PARAM_example"))
            self.assertEqual("xyz", os.environ.get("PARAM_EXAMPLE"))
            self.assertNotEqual(old_env, os.environ)
        self.assertEqual(old_env, os.environ)
