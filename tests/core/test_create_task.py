import unittest
from unittest.mock import Mock, patch

from gaiaflow.core.create_task import GaiaflowMode, create_task


class TestCreateTask(unittest.TestCase):
    def setUp(self):
        self.mock_operator_instance = Mock()
        self.mock_operator_instance.create_task.return_value = "mock_task"

        self.mock_operator_class = Mock()
        self.mock_operator_class.return_value = self.mock_operator_instance

        self.operator_map_patcher = patch("gaiaflow.core.create_task.OPERATOR_MAP")
        self.mock_operator_map = self.operator_map_patcher.start()
        self.mock_operator_map.get.return_value = self.mock_operator_class

    def tearDown(self):
        self.operator_map_patcher.stop()

    def test_enum_values(self):
        self.assertEqual(GaiaflowMode.DEV.value, "dev")
        self.assertEqual(GaiaflowMode.DEV_DOCKER.value, "dev_docker")
        self.assertEqual(GaiaflowMode.PROD_LOCAL.value, "prod_local")
        self.assertEqual(GaiaflowMode.PROD.value, "prod")

    def test_enum_invalid_value(self):
        with self.assertRaises(ValueError):
            GaiaflowMode("invalid_mode")

    def test_enum_creation_from_string(self):
        self.assertEqual(GaiaflowMode("dev"), GaiaflowMode.DEV)
        self.assertEqual(GaiaflowMode("dev_docker"), GaiaflowMode.DEV_DOCKER)
        self.assertEqual(GaiaflowMode("prod_local"), GaiaflowMode.PROD_LOCAL)
        self.assertEqual(GaiaflowMode("prod"), GaiaflowMode.PROD)

    def test_create_task_basic(self):
        result = create_task(task_id="test_task", func_path="test.module:function")

        self.assertEqual(result, "mock_task")
        self.mock_operator_class.assert_called_once()
        self.mock_operator_instance.create_task.assert_called_once()

    def test_create_task_with_all_parameters(self):
        mock_dag = Mock()
        mock_dag.params = {"param1": "value1"}

        result = create_task(
            task_id="test_task",
            func_path="test.module:function",
            func_kwargs={"key": "value"},
            func_args=["arg1", "arg2"],
            image="test_image:latest",
            mode="prod",
            secrets=["secret1", "secret2"],
            env_vars={"ENV_VAR": "value"},
            retries=5,
            dag=mock_dag,
        )

        self.assertEqual(result, "mock_task")

        self.mock_operator_class.assert_called_once_with(
            task_id="test_task",
            func_path="test.module:function",
            func_args=["arg1", "arg2"],
            func_kwargs={"key": "value"},
            image="test_image:latest",
            secrets=["secret1", "secret2"],
            env_vars={"ENV_VAR": "value"},
            retries=5,
            params={"param1": "value1"},
            mode=GaiaflowMode.PROD,
        )

    def test_create_task_default_values(self):
        create_task(task_id="test_task", func_path="test.module:function")

        call_args = self.mock_operator_class.call_args
        self.assertEqual(call_args.kwargs["func_args"], [])
        self.assertEqual(call_args.kwargs["func_kwargs"], {})
        self.assertEqual(call_args.kwargs["env_vars"], {})
        self.assertEqual(call_args.kwargs["retries"], 3)
        self.assertEqual(call_args.kwargs["mode"], GaiaflowMode.DEV)
        self.assertEqual(call_args.kwargs["params"], {})

    def test_create_task_invalid_mode(self):
        with self.assertRaises(ValueError) as context:
            create_task(
                task_id="test_task",
                func_path="test.module:function",
                mode="invalid_mode",
            )

        self.assertIn("env must be one of", str(context.exception))
        self.assertIn("invalid_mode", str(context.exception))

    def test_create_task_no_operator_for_mode(self):
        self.mock_operator_map.get.return_value = None

        with self.assertRaises(ValueError) as context:
            create_task(
                task_id="test_task", func_path="test.module:function", mode="dev"
            )

        self.assertIn("No task creation operator defined for", str(context.exception))

    def test_create_task_with_dag_no_params(self):
        mock_dag = Mock(spec=[])  # DAG without params attribute

        create_task(task_id="test_task", func_path="test.module:function", dag=mock_dag)

        call_args = self.mock_operator_class.call_args
        self.assertEqual(call_args.kwargs["params"], {})

    def test_create_task_none_values_converted_to_defaults(self):
        create_task(
            task_id="test_task",
            func_path="test.module:function",
            func_kwargs=None,
            func_args=None,
            env_vars=None,
        )

        call_args = self.mock_operator_class.call_args
        self.assertEqual(call_args.kwargs["func_args"], [])
        self.assertEqual(call_args.kwargs["func_kwargs"], {})
        self.assertEqual(call_args.kwargs["env_vars"], {})

    def test_create_task_different_modes(self):
        modes = ["dev", "dev_docker", "prod_local", "prod"]
        expected_enums = [
            GaiaflowMode.DEV,
            GaiaflowMode.DEV_DOCKER,
            GaiaflowMode.PROD_LOCAL,
            GaiaflowMode.PROD,
        ]

        for mode, expected_enum in zip(modes, expected_enums):
            with self.subTest(mode=mode):
                create_task(
                    task_id="test_task", func_path="test.module.function", mode=mode
                )

                call_args = self.mock_operator_class.call_args
                self.assertEqual(call_args.kwargs["mode"], expected_enum)
