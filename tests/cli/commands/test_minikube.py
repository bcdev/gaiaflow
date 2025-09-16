import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from types import SimpleNamespace
from typer.testing import CliRunner

from gaiaflow.constants import DEFAULT_IMAGE_NAME, BaseAction, \
    ExtendedAction
from gaiaflow.cli.commands.minikube import app as prod_app
from gaiaflow.cli.commands.minikube import load_imports
from gaiaflow.managers.helpers import DockerHandlerMode


class TestGaiaflowProdCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_project_path = Path("/test/project")
        self.test_gaiaflow_path = Path("/tmp/gaiaflow/test")

        self.mock_imports = SimpleNamespace(
            BaseAction=BaseAction,
            ExtendedAction=ExtendedAction,
            MinikubeManager=MagicMock(),
            create_gaiaflow_context_path=MagicMock(
                return_value=(self.test_gaiaflow_path, self.test_project_path)
            ),
            gaiaflow_path_exists_in_state=MagicMock(return_value=True),
            parse_key_value_pairs=MagicMock(return_value={"key1": "value1", "key2": "value2"}),
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_start_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "start",
            "--force-new"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.gaiaflow_path_exists_in_state.assert_called_once_with(
            self.test_gaiaflow_path, True
        )

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=BaseAction.START,
            force_new=True,
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_start_command_exits_when_project_not_exists(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports
        self.mock_imports.gaiaflow_path_exists_in_state.return_value = False

        result = self.runner.invoke(prod_app, [
            "start",
        ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Please create a project with Gaiaflow", result.output)

        self.mock_imports.MinikubeManager.run.assert_not_called()

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_stop_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "stop",
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=BaseAction.STOP,
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_restart_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "restart",
            "--force-new"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=BaseAction.RESTART,
            force_new=True
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_dockerize_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "dockerize",
            "--image-name", "my-custom-image"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.DOCKERIZE,
            docker_handler_mode=DockerHandlerMode.MINIKUBE,
            image_name="my-custom-image", dockerfile_path=None
        )

    @patch("gaiaflow.cli.commands.minikube.load_imports")
    def test_list_images_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(
            prod_app, ["list-images"]
        )

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.LIST_IMAGES,
            docker_handler_mode=DockerHandlerMode.MINIKUBE,
        )

    @patch("gaiaflow.cli.commands.minikube.load_imports")
    def test_remove_image_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, ["remove-image", "--image-name",
                                               "my-custom-image"])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.REMOVE_IMAGE,
            docker_handler_mode=DockerHandlerMode.MINIKUBE,
            image_name="my-custom-image",
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_dockerize_command_with_default_image_name(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "dockerize",
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once()
        call_args = self.mock_imports.MinikubeManager.run.call_args
        self.assertEqual(call_args.kwargs['image_name'], DEFAULT_IMAGE_NAME)

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_create_config_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "create-config",
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.CREATE_CONFIG,
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_create_secret_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "create-secret",
            "--name", "my-secret",
            "--data", "key1=value1",
            "--data", "key2=value2"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.parse_key_value_pairs.assert_called_once_with(
            ["key1=value1", "key2=value2"]
        )

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.CREATE_SECRET,
            secret_name="my-secret",
            secret_data={"key1": "value1", "key2": "value2"},
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_cleanup_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "cleanup",
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action="cleanup",
        )

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_all_commands_handle_missing_project_gracefully(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports
        self.mock_imports.gaiaflow_path_exists_in_state.return_value = False

        commands_and_args = [
            ["start"],
            ["stop"],
            ["restart"],
            ["dockerize"],
            ["create-config"],
            ["create-secret", "--name", "test", "--data", "key=value"],
            ["cleanup"],
        ]

        for command_args in commands_and_args:
            with self.subTest(command=command_args[0]):
                self.mock_imports.MinikubeManager.run.reset_mock()

                result = self.runner.invoke(prod_app, command_args)

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Please create a project with Gaiaflow", result.output)

                self.mock_imports.MinikubeManager.run.assert_not_called()

    def test_load_imports_function(self):
        imports = load_imports()

        expected_attributes = [
            'BaseAction', 'ExtendedAction', 'MinikubeManager',
            'create_gaiaflow_context_path', 'gaiaflow_path_exists_in_state',
            'parse_key_value_pairs'
        ]

        for attr in expected_attributes:
            with self.subTest(attribute=attr):
                self.assertTrue(hasattr(imports, attr),
                                f"Missing attribute: {attr}")

    @patch('gaiaflow.cli.commands.minikube.load_imports')
    def test_action_objects_comparison(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(prod_app, [
            "start",
        ])

        self.assertEqual(result.exit_code, 0)

        call_args = self.mock_imports.MinikubeManager.run.call_args
        passed_action = call_args.kwargs['action']

        self.assertEqual(passed_action, BaseAction.START)
        self.assertEqual(passed_action.name, "start")
