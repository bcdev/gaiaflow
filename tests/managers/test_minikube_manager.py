import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
import subprocess

import yaml

from gaiaflow.constants import BaseAction, ExtendedAction
from gaiaflow.managers.helpers import temporary_copy, DockerHandlerMode
from gaiaflow.managers.minikube_manager import (
    MinikubeManager,
    MinikubeHelper,
    DockerHelper,
    KubeConfigHelper,
)

class TestMinikubeManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.manager = MinikubeManager(
            gaiaflow_path=Path(self.tmpdir.name),
            user_project_path=Path(self.tmpdir.name),
            action=BaseAction.START,
            docker_handler_mode=DockerHandlerMode.MINIKUBE,
            image_name="img",
        )


    def tearDown(self):
        self.tmpdir.cleanup()

    def test_init_with_allowed_kwargs(self):
        mgr = MinikubeManager(
            Path(self.tmpdir.name),
            Path(self.tmpdir.name),
            BaseAction.START,
            secret_name="my-secret",
            secret_data={"k": "v"},
            dockerfile_path=Path("/tmp/Dockerfile"),
        )
        self.assertIsInstance(mgr, MinikubeManager)

    def test_init_with_unexpected_kwarg_raises(self):
        with self.assertRaises(TypeError) as ctx:
            MinikubeManager(
                Path(self.tmpdir.name),
                Path(self.tmpdir.name),
                BaseAction.START,
                bad_arg="oops",
            )


    def test_valid_actions(self):
        actions = self.manager._get_valid_actions()
        self.assertIn(ExtendedAction.DOCKERIZE, actions)


    def test_run_raises_on_missing_action(self):
        with self.assertRaises(ValueError):
            MinikubeManager.run()


    def test_run_raises_on_unknown_action(self):
        with self.assertRaises(ValueError):
            MinikubeManager.run(gaiaflow_path=Path(self.tmpdir.name),
            user_project_path=Path(self.tmpdir.name),action="not-real")


    @patch.object(MinikubeManager, "start")
    def test_run_start_action(self, mock_start):
        MinikubeManager.run(
            gaiaflow_path=Path(self.tmpdir.name),
            user_project_path=Path(self.tmpdir.name),
            action=BaseAction.START,
        )
        mock_start.assert_called()


    @patch("subprocess.run", return_value=MagicMock(returncode=1))
    def test_create_secrets_creates_new(self, mock_run):
        with patch("subprocess.check_call") as mock_call:
            self.manager.create_secrets("new-secret", {"k": "v"})
            mock_call.assert_called()


    @patch("subprocess.run", return_value=MagicMock(returncode=0))
    def test_create_secrets_skips_existing(self, _):
        self.manager.create_secrets("existing-secret", {"k": "v"})  # should not raise


    @patch("gaiaflow.managers.minikube_manager.run")
    def test_cleanup_runs(self, mock_run):
        self.manager.cleanup()
        self.assertTrue(mock_run.called)

    @patch("gaiaflow.managers.minikube_manager.MlopsManager.run")
    def test_stop_and_start_mlops(self, mock_run):
        self.manager._stop_mlops()
        self.manager._start_mlops()
        assert mock_run.call_count == 2

    @patch.object(KubeConfigHelper, "create_inline")
    @patch.object(MinikubeHelper, "start")
    @patch.object(MinikubeManager, "_stop_mlops")
    @patch.object(MinikubeManager, "_start_mlops")
    def test_start_calls_helpers(
        self, mock_start_mlops, mock_stop_mlops, mock_mini_start, mock_inline
    ):
        self.manager.start()
        mock_stop_mlops.assert_called()
        mock_mini_start.assert_called()
        mock_start_mlops.assert_called()

    @patch.object(MinikubeHelper, "stop")
    def test_stop(self, mock_stop):
        self.manager.stop()
        mock_stop.assert_called()

    @patch.object(KubeConfigHelper, "create_inline")
    def test_create_kube_config_inline(self, mock_inline):
        self.manager.create_kube_config_inline()
        mock_inline.assert_called()

    @patch.object(DockerHelper, "build_image")
    def test_build_docker_image(self, mock_build):
        self.manager.build_docker_image()
        mock_build.assert_called()

    @patch.object(DockerHelper, "list_images")
    def test_list_docker_images(self, mock_list_images):
        self.manager.list_images()
        mock_list_images.assert_called()

    @patch.object(DockerHelper, "remove_image")
    def test_remove_docker_images(self, mock_remove_image):
        self.manager.remove_image("img")
        mock_remove_image.assert_called_with("img")

