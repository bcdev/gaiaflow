import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
from types import SimpleNamespace
from typer.testing import CliRunner

from gaiaflow.constants import Service, DEFAULT_IMAGE_NAME, BaseAction, \
    ExtendedAction
from gaiaflow.cli.commands.mlops import app, load_imports
from gaiaflow.managers.helpers import DockerHandlerMode


class TestGaiaflowCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_project_path = Path("/test/project")
        self.test_gaiaflow_path = Path("/tmp/gaiaflow/test")

        self.mock_imports = SimpleNamespace(
            BaseAction=BaseAction,
            ExtendedAction=ExtendedAction,
            MlopsManager=MagicMock(),
            MinikubeManager=MagicMock(),
            create_gaiaflow_context_path=MagicMock(
                return_value=(self.test_gaiaflow_path, self.test_project_path)
            ),
            gaiaflow_path_exists_in_state=MagicMock(return_value=True),
            save_project_state=MagicMock(),
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_start_command_with_all_services(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "start",
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.gaiaflow_path_exists_in_state.assert_called_once_with(
            self.test_gaiaflow_path, True
        )

        self.mock_imports.MlopsManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            force_new=False,
            action=BaseAction.START,
            service=Service.all,
            cache=False,
            jupyter_port=8895,
            docker_build=False,
            user_env_name=None,
            env_tool="mamba",
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_start_command_with_specific_services(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "start",
            "--service", "jupyter",
            "--service", "airflow",
            "--cache",
            "--jupyter-port", "9000",
            "--docker-build",
            "--env", "myenv",
            "--env-tool", "conda"
        ])

        self.assertEqual(result.exit_code, 0)

        self.assertEqual(self.mock_imports.MlopsManager.run.call_count, 2)

        expected_calls = [
            call(
                gaiaflow_path=self.test_gaiaflow_path,
                user_project_path=self.test_project_path,
                force_new=False,
                action=BaseAction.START,
                service="jupyter",
                cache=True,
                jupyter_port=9000,
                docker_build=True,
                user_env_name="myenv",
                env_tool="conda",
            ),
            call(
                gaiaflow_path=self.test_gaiaflow_path,
                user_project_path=self.test_project_path,
                force_new=False,
                action=BaseAction.START,
                service="airflow",
                cache=True,
                jupyter_port=9000,
                docker_build=True,
                user_env_name="myenv",
                env_tool="conda",
            )
        ]
        self.mock_imports.MlopsManager.run.assert_has_calls(expected_calls)

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_start_command_saves_project_state_when_not_exists(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports
        self.mock_imports.gaiaflow_path_exists_in_state.return_value = False

        result = self.runner.invoke(app, [
            "start",
        ])

        self.assertEqual(result.exit_code, 0)
        self.mock_imports.save_project_state.assert_called_once_with(
            self.test_project_path, self.test_gaiaflow_path
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_stop_command_with_all_services(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "stop",
            "--delete-volume"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MlopsManager.run.assert_called_once_with(
            gaiaflow_path=Path(self.test_gaiaflow_path),
            user_project_path=Path(self.test_project_path),
            service=Service.all,
            action=BaseAction.STOP,
            delete_volume=True,
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_stop_command_with_specific_services(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "stop",
            "--service", "jupyter"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MlopsManager.run.assert_called_once_with(
            gaiaflow_path=Path(self.test_gaiaflow_path),
            user_project_path=Path(self.test_project_path),
            action=BaseAction.STOP,
            service="jupyter",
            delete_volume=False,
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_restart_command_with_all_services(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "restart",
            "--force-new",
            "--cache",
            "--jupyter-port", "9001",
            "--docker-build",
            "--delete-volume"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MlopsManager.run.assert_called_once_with(
            gaiaflow_path=Path(self.test_gaiaflow_path),
            user_project_path=Path(self.test_project_path),
            force_new=True,
            action=BaseAction.RESTART,
            cache=True,
            jupyter_port=9001,
            delete_volume=True,
            docker_build=True,
            service=Service.all,
        )

    @patch("gaiaflow.cli.commands.mlops.load_imports")
    def test_restart_command_with_specific_services(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(
            app,
            [
                "restart",
                "--service",
                "jupyter",
                "--service",
                "airflow",
            ],
        )

        self.assertEqual(result.exit_code, 0)

        self.assertEqual(self.mock_imports.MlopsManager.run.call_count, 2)

        expected_calls = [
            call(
                gaiaflow_path=self.test_gaiaflow_path,
                user_project_path=self.test_project_path,
                force_new=False,
                action=BaseAction.RESTART,
                service="jupyter",
                cache=False,
                jupyter_port=8895,
                delete_volume=False,
                docker_build=False,
            ),
            call(
                gaiaflow_path=self.test_gaiaflow_path,
                user_project_path=self.test_project_path,
                force_new=False,
                action=BaseAction.RESTART,
                service="airflow",
                cache=False,
                jupyter_port=8895,
                delete_volume=False,
                docker_build=False,
            ),
        ]
        self.mock_imports.MlopsManager.run.assert_has_calls(expected_calls)

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_cleanup_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "cleanup",
            "--prune"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MlopsManager.run.assert_called_once_with(
            gaiaflow_path=Path(self.test_gaiaflow_path),
            user_project_path=Path(self.test_project_path),
            action=BaseAction.CLEANUP,
            prune=True,
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_dockerize_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports
        self.mock_imports.gaiaflow_path_exists_in_state.return_value = False

        result = self.runner.invoke(app, [
            "dockerize",
            "--image-name", "custom-image"
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.save_project_state.assert_called_once_with(
            self.test_project_path, self.test_gaiaflow_path
        )

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.DOCKERIZE,
            docker_build_mode=DockerHandlerMode.LOCAL,
            image_name="custom-image"
        )

    @patch("gaiaflow.cli.commands.mlops.load_imports")
    def test_list_images_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, ["list-images"])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.LIST_IMAGES,
            docker_handler_mode=DockerHandlerMode.LOCAL,
        )

    @patch("gaiaflow.cli.commands.mlops.load_imports")
    def test_remove_image_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(
            app, ["remove-image", "--image-name", "my-custom-image"]
        )

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.REMOVE_IMAGE,
            docker_handler_mode=DockerHandlerMode.LOCAL,
            image_name="my-custom-image",
        )


    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_dockerize_command_with_default_image_name(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "dockerize",
        ])

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MinikubeManager.run.assert_called_once()
        call_args = self.mock_imports.MinikubeManager.run.call_args
        self.assertEqual(call_args.kwargs['image_name'], DEFAULT_IMAGE_NAME)

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_update_deps_command(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(
            app, ["update-deps"]
        )

        self.assertEqual(result.exit_code, 0)

        self.mock_imports.MlopsManager.run.assert_called_once_with(
            gaiaflow_path=self.test_gaiaflow_path,
            user_project_path=self.test_project_path,
            action=ExtendedAction.UPDATE_DEPS,
        )

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_commands_handle_missing_project_gracefully(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports
        self.mock_imports.gaiaflow_path_exists_in_state.return_value = False

        failing_commands = ["stop", "restart", "cleanup"]

        for command in failing_commands:
            with self.subTest(command=command):
                result = self.runner.invoke(app, [
                    command,
                ])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Please create a project with Gaiaflow", result.output)

    def test_load_imports_function(self):
        imports = load_imports()

        expected_attributes = [
            'BaseAction', 'ExtendedAction', 'MlopsManager', 'MinikubeManager',
            'create_gaiaflow_context_path', 'gaiaflow_path_exists_in_state',
            'save_project_state'
        ]

        for attr in expected_attributes:
            with self.subTest(attribute=attr):
                self.assertTrue(hasattr(imports, attr),
                                f"Missing attribute: {attr}")

    @patch('gaiaflow.cli.commands.mlops.load_imports')
    def test_argument_type_conversion(self, mock_load_imports):
        mock_load_imports.return_value = self.mock_imports

        result = self.runner.invoke(app, [
            "start",
        ])

        self.assertEqual(result.exit_code, 0)

        call_args = self.mock_imports.create_gaiaflow_context_path.call_args
        self.assertIsInstance(call_args[0][0], Path)


if __name__ == '__main__':
    unittest.main()