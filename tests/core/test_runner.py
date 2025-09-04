import os
import shutil
import tempfile
import types
import unittest
from unittest.mock import Mock, mock_open, patch

from gaiaflow.core import runner
from gaiaflow.testing import set_env_cm


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.xcom_dir = os.path.join(self.temp_dir, "airflow", "xcom")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_params_empty_env(self):
        with set_env_cm():
            result = runner._extract_params_from_env()
        self.assertEqual(result, {})

    def test_extract_params_with_params(self):
        with set_env_cm(
            PARAMS_KEY1="value1",
            PARAMS_KEY2="value2",
            OTHER_VAR="not_included",
            PARAMS_NESTED_KEY="nested_value",
        ):
            result = runner._extract_params_from_env()
        expected = {"key1": "value1", "key2": "value2", "nested_key": "nested_value"}
        self.assertEqual(result, expected)

    def test_extract_params_case_conversion(self):
        with set_env_cm(
            PARAMS_UPPER_CASE="value",
            PARAMS_MixedCase="value2",
        ):
            result = runner._extract_params_from_env()
        expected = {"upper_case": "value", "mixedcase": "value2"}
        self.assertEqual(result, expected)

    def test_extract_params_custom_prefix(self):
        with set_env_cm(
            CUSTOM_KEY1="value",
            CUSTOM_KEY2="value2",
        ):
            result = runner._extract_params_from_env("CUSTOM_")
        expected = {"key1": "value", "key2": "value2"}
        self.assertEqual(result, expected)

    @patch("gaiaflow.core.runner.os.makedirs")
    @patch("gaiaflow.core.runner.open", new_callable=mock_open)
    @patch("gaiaflow.core.runner.json.dump")
    def test_write_xcom_result_success(
        self, mock_json_dump, mock_file_open, mock_makedirs
    ):
        result = {"key": "value", "number": 123}

        runner._write_xcom_result(result)

        mock_makedirs.assert_called_once_with("/airflow/xcom", exist_ok=True)
        mock_file_open.assert_called_once_with("/airflow/xcom/return.json", "w")
        mock_json_dump.assert_called_once_with(
            result, mock_file_open.return_value.__enter__.return_value
        )

    @patch("gaiaflow.core.runner.os.makedirs")
    def test_write_xcom_result_makedirs_failure(self, mock_makedirs):
        result = {"key": "value"}
        mock_makedirs.side_effect = OSError("Permission denied")

        with self.assertRaises(OSError):
            runner._write_xcom_result(result)

    def test_run_no_func_path_raises_error(self):
        with self.assertRaises(ValueError) as context:
            runner.run()

        self.assertEqual(str(context.exception), "func_path must be provided")

    def test_import_function_success(self):
        def dummy_func():
            return "ok"

        fake_module = types.SimpleNamespace(myfunc=dummy_func)

        with patch("importlib.import_module", return_value=fake_module):
            func = runner._import_function("fake_module:myfunc")

        self.assertEqual(func, dummy_func)

    def test_import_function_invalid_path(self):
        with self.assertRaises(ValueError):
            runner._import_function("not_a_valid_path")

    def test_resolve_inputs_dev_mode(self):
        func_path, args, kwargs = runner._resolve_inputs(
            "mymod:func", [1, 2], {"a": 3}, "dev"
        )
        self.assertEqual(func_path, "mymod:func")
        self.assertEqual(args, [1, 2])
        self.assertEqual(kwargs, {"a": 3})

    def test_resolve_inputs_prod_local_mode(self):
        # This test will be the same for dev_docker and prod mode as well
        # because they all expect the func_path, args and kwargs as env
        # variables.
        with set_env_cm(
            FUNC_PATH="mod:func",
            FUNC_ARGS="[10, 20]",
            FUNC_KWARGS='{"foo": "bar"}',
        ):
            with patch(
                "gaiaflow.core.runner._extract_params_from_env", return_value={"x": 1}
            ):
                func_path, args, kwargs = runner._resolve_inputs(
                    None, None, None, "prod"
                )

        self.assertEqual(func_path, "mod:func")
        self.assertEqual(args, [10, 20])
        self.assertEqual(kwargs, {"foo": "bar", "params": {"x": 1}})

    def test_run_dev_mode(self):
        dummy_func = Mock(return_value={"res": "ok"})
        fake_module = types.SimpleNamespace(myfunc=dummy_func)

        with patch("importlib.import_module", return_value=fake_module):
            result = runner.run(
                func_path="fake_module:myfunc",
                args=[1, 2],
                kwargs={"k": "v"},
            )

        self.assertEqual(result, {"res": "ok"})
        dummy_func.assert_called_once_with(1, 2, k="v")

    def test_run_prod_mode_with_xcom(self):
        dummy_func = Mock(return_value={"done": True})
        fake_module = types.SimpleNamespace(myfunc=dummy_func)

        with set_env_cm(
            MODE="prod",
            FUNC_PATH="fake_module:myfunc",
            FUNC_ARGS="[100]",
            FUNC_KWARGS='{"alpha": 1}',
        ):
            with (
                patch("gaiaflow.core.runner._write_xcom_result") as mock_xcom,
                patch("importlib.import_module", return_value=fake_module),
            ):
                result = runner.run()

        self.assertEqual(result, {"done": True})
        dummy_func.assert_called_once_with(100, alpha=1, params={})
        mock_xcom.assert_called_once_with({"done": True})

    @patch("gaiaflow.core.runner.pickle.dump")
    @patch("gaiaflow.core.runner.open", new_callable=mock_open)
    def test_run_dev_docker_mode(self, mock_file_open, mock_pickle_dump):
        dummy_func = Mock(return_value={"docker": "ok"})
        fake_module = types.SimpleNamespace(myfunc=dummy_func)

        with set_env_cm(
            MODE="dev_docker",
            FUNC_PATH="fake_module:myfunc",
            FUNC_ARGS="[1]",
            FUNC_KWARGS='{"flag": true}',
        ):
            with patch("importlib.import_module", return_value=fake_module):
                result = runner.run()

        self.assertEqual(result, {"docker": "ok"})
        dummy_func.assert_called_once_with(1, flag=True, params={})

        mock_file_open.assert_called_once_with("/tmp/script.out", "wb+")
        mock_pickle_dump.assert_called_once_with(
            {"docker": "ok"},
            mock_file_open.return_value.__enter__.return_value,
        )
