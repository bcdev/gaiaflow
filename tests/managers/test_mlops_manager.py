import shutil
import socket
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

import yaml

from gaiaflow.constants import BaseAction, Service
from gaiaflow.managers.mlops_manager import (
    MlopsManager,
    JupyterHelper,
    DockerComposeHelper,
    DockerResources,
)


class TestMlopsManager(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)

        self.user_project = self.base_path / "project"
        self.user_project.mkdir()
        (self.user_project / "environment.yml").write_text("name: test-env")
        (self.user_project / "pyproject.toml").write_text("[project]\nname='test'")
        (self.user_project / "dummy_package").mkdir()
        (self.user_project / "dummy_package" / "__init__.py").write_text("")

        self.gaiaflow_context = self.base_path / "gaiaflow"
        docker_dir = self.gaiaflow_context / "_docker" / "docker-compose"
        docker_dir.mkdir(parents=True)
        (docker_dir / "docker-compose.yml").write_text(
            yaml.dump({"x-airflow-common": {"volumes": ["./logs:/opt/airflow/logs"]}})
        )
        (docker_dir / "entrypoint.sh").write_text("#!/bin/bash\necho hi")
        (self.gaiaflow_context / "_docker" / "kube_config_inline").write_text("kube")
        (self.gaiaflow_context / "environment.yml").write_text("name: test-env")

        self.manager = MlopsManager(
            gaiaflow_path=self.gaiaflow_context,
            user_project_path=self.user_project,
            action=BaseAction.START,
            service=Service.all,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_invalid_env_tool(self):
        with self.assertRaises(ValueError):
            MlopsManager(self.gaiaflow_context, self.user_project, BaseAction.START, env_tool="pip")

    def test_unexpected_kwargs(self):
        with self.assertRaises(TypeError):
            MlopsManager(self.gaiaflow_context, self.user_project, BaseAction.START, bad_kwarg=True)

    @patch("gaiaflow.managers.mlops_manager.run")
    @patch("gaiaflow.managers.mlops_manager.subprocess.Popen")
    @patch("gaiaflow.managers.mlops_manager.env_exists")
    def test_run_dispatches_start(self, mock_env_exists, mock_popen,
                                  mock_run):
        mock_env_exists.return_value = True
        MlopsManager.run(
            gaiaflow_path=self.manager.gaiaflow_path,
            user_project_path=self.manager.user_project_path,
            action=BaseAction.START,
            service=Service.all,
        )
        args, kwargs = mock_run.call_args

        self.assertIn("docker", args[0])
        self.assertIn("compose", args[0])
        self.assertIn("up", args[0])
        self.assertIn("-d", args[0])
        self.assertTrue(any("docker-compose.yml" in x for x in args[0]))
        self.assertIn("Error running docker compose", args[1])

        args, kwargs = mock_popen.call_args
        print("subprocess.Popen args:", args)
        print("subprocess.Popen kwargs:", kwargs)

        self.assertIn("jupyter", args[0])
        self.assertIn("lab", args[0])
        self.assertIn("test-env", args[0])
        self.assertIn("--port=8895", args[0])
        self.assertIn("mamba", args[0])

    @patch("gaiaflow.managers.mlops_manager.run")
    @patch("gaiaflow.managers.mlops_manager.subprocess.Popen")
    @patch("gaiaflow.managers.mlops_manager.env_exists")
    def test_run_dispatches_start_jupyter_custom_values(self, mock_env_exists,
                                              mock_popen,
                                    mock_run):
        mock_env_exists.return_value = True
        MlopsManager.run(
            gaiaflow_path=self.manager.gaiaflow_path,
            user_project_path=self.manager.user_project_path,
            action=BaseAction.START,
            service=Service.all,
            jupyter_port=8181,
            env_tool="conda",
        )
        args, kwargs = mock_run.call_args

        self.assertIn("docker", args[0])
        self.assertIn("compose", args[0])
        self.assertIn("up", args[0])
        self.assertIn("-d", args[0])
        self.assertTrue(any("docker-compose.yml" in x for x in args[0]))
        self.assertIn("Error running docker compose", args[1])

        args, kwargs = mock_popen.call_args
        print("subprocess.Popen args:", args)
        print("subprocess.Popen kwargs:", kwargs)

        self.assertIn("jupyter", args[0])
        self.assertIn("lab", args[0])
        self.assertIn("test-env", args[0])
        self.assertIn("--port=8181", args[0])
        self.assertIn("conda", args[0])

    def test_run_invalid_action(self):
        with self.assertRaises(ValueError):
            MlopsManager.run(
                gaiaflow_path=self.manager.gaiaflow_path,
                user_project_path=self.manager.user_project_path,
                action="not-an-action",
            )

    @patch("gaiaflow.managers.mlops_manager.env_exists")
    @patch("gaiaflow.managers.mlops_manager.subprocess.Popen")
    def test_start_force_new(self, mock_popen, mock_env_exists):
        self.manager.force_new = True
        with patch.object(self.manager, "cleanup") as mock_cleanup:
            self.manager.start()
            mock_cleanup.assert_called_once()

    @patch("gaiaflow.managers.mlops_manager.env_exists")
    @patch("gaiaflow.managers.mlops_manager.subprocess.Popen")
    def test_start_service_jupyter(self, mock_popen, mock_env_exists):
        self.manager.service = Service.jupyter
        with patch.object(self.manager.jupyter, "check_port") as mock_check, \
             patch.object(self.manager.jupyter, "start") as mock_start:
            self.manager.start()
            mock_check.assert_called_once()
            mock_start.assert_called_once()

    def test_start_single_service(self):
        self.manager.service = Service.airflow
        with patch.object(self.manager.docker, "run_compose") as mock_compose:
            self.manager.start()
            mock_compose.assert_called_with(["up", "-d"], Service.airflow)

        self.manager.service = Service.mlflow
        with patch.object(self.manager.docker, "run_compose") as mock_compose:
            self.manager.start()
            mock_compose.assert_called_with(["up", "-d"], Service.mlflow)

    def test_run_missing_action_raises(self):
        with self.assertRaises(ValueError) as ctx:
            MlopsManager.run(
                gaiaflow_path=self.manager.gaiaflow_path,
                user_project_path=self.manager.user_project_path,
                service=Service.all,
            )
        self.assertIn("Missing required argument 'action'", str(ctx.exception))

    @patch("gaiaflow.managers.mlops_manager.run")
    @patch.object(MlopsManager, "_build_docker_images")
    def test_start_triggers_build_docker_images(self, mock_build, mock_run):
        self.manager.docker_build = True
        self.manager.service = Service.airflow
        self.manager.start()
        mock_build.assert_called_once()

    def test_build_docker_images_cache_and_no_cache(self):
        mock_docker = MagicMock()
        self.manager.docker = mock_docker
        mock_docker.run_compose = MagicMock()

        self.manager.cache = False
        self.manager.service = Service.all

        self.manager._build_docker_images()
        args, _ = mock_docker.run_compose.call_args
        self.assertIn("--no-cache", args[0])

        self.manager.cache = True
        self.manager.service = Service.airflow

        self.manager._build_docker_images()
        args, _ = mock_docker.run_compose.call_args
        self.assertNotIn("--no-cache", args[0])

    def test_stop_all(self):
        with patch.object(self.manager, "jupyter") as mock_jupyter, \
             patch.object(self.manager, "docker") as mock_docker:
            self.manager.stop()
            mock_jupyter.stop.assert_called()
            mock_docker.run_compose.assert_called()

            self.manager.delete_volume = True
            self.manager.stop()
            mock_jupyter.stop.assert_called()
            mock_docker.run_compose.assert_called()

    def test_stop_jupyter(self):
        self.manager.service = Service.jupyter
        with patch.object(self.manager.jupyter, "stop") as mock_stop:
            self.manager.stop()
            mock_stop.assert_called_once()

    def test_stop_single_service_with_volume(self):
        self.manager.service = Service.mlflow
        self.manager.delete_volume = True
        with patch.object(self.manager.docker, "run_compose") as mock_compose:
            self.manager.stop()
            args, _ = mock_compose.call_args
            self.assertIn("-v", args[0])

    def test_cleanup_with_prune(self):
        self.manager.prune = True
        with patch("shutil.rmtree") as mock_rm, \
             patch("gaiaflow.managers.mlops_manager.delete_project_state") as mock_del, \
             patch.object(self.manager.docker, "prune") as mock_prune:
            self.manager.cleanup()
            mock_rm.assert_called_once()
            mock_del.assert_called_once()
            mock_prune.assert_called_once()

    def test_cleanup_missing_context(self):
        shutil.rmtree(self.gaiaflow_context)
        with patch("gaiaflow.managers.mlops_manager.log_error") as mock_log:
            self.manager.cleanup()
            mock_log.assert_called()

    def test_delete_volume_logging(self):
        self.manager.delete_volume = True
        down_cmd = ["down"]
        if self.manager.delete_volume:
            down_cmd.append("-v")
        self.assertIn("-v", down_cmd)

    def test_update_env_file_sets_uid(self):
        env_path = self.base_path / ".env"
        self.manager._update_env_file_with_airflow_uid(env_path)
        self.assertIn("AIRFLOW_UID", env_path.read_text())

        env_path.write_text("SOME_VAR=1\nAIRFLOW_UID=2\n")
        self.manager._update_env_file_with_airflow_uid(env_path)
        self.assertIn("SOME_VAR", env_path.read_text())
        self.assertIn("AIRFLOW_UID", env_path.read_text())

    def test_update_env_file_updates_existing(self):
        env_path = self.base_path / ".env"
        env_path.write_text("AIRFLOW_UID=9999\n")
        self.manager._update_env_file_with_airflow_uid(env_path)
        content = env_path.read_text()
        self.assertNotIn("9999", content)

    def test_update_files_rewrites_compose(self):
        with patch("gaiaflow.managers.mlops_manager.find_python_packages", return_value=["dummy_package"]), \
             patch("gaiaflow.managers.mlops_manager.set_permissions"):
            self.manager._update_files()
        compose_path = self.gaiaflow_context / "_docker" / "docker-compose" / "docker-compose.yml"
        data = yaml.safe_load(compose_path.read_text())
        vols = data["x-airflow-common"]["volumes"]
        self.assertTrue(any("dummy_package" in v for v in vols))
        self.assertTrue(any("/var/run/docker.sock" in v for v in vols))

    @patch("gaiaflow.managers.mlops_manager.update_micromamba_env_in_docker")
    def test_update_deps_calls_update_and_logs(self, mock_update):
        MlopsManager.update_deps()
        mock_update.assert_called_once_with(DockerResources.AIRFLOW_CONTAINERS)

    def test_jupyter_port_in_use(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.listen(1)

        helper = JupyterHelper(port, "mamba", None, self.manager.gaiaflow_path)
        with self.assertRaises(SystemExit):
            helper.check_port()
        sock.close()

    def test_jupyter_get_env_name(self):
        helper = JupyterHelper(8895, "mamba", None, self.manager.gaiaflow_path)
        name = helper.get_env_name()
        self.assertEqual(name, "test-env")

    def test_jupyter_start_runs_subprocess(self):
        helper = JupyterHelper(8895, "mamba", "custom-env", self.manager.gaiaflow_path)
        with patch("subprocess.Popen") as mock_popen, \
             patch("gaiaflow.managers.mlops_manager.env_exists", return_value=True):
            helper.start()
            mock_popen.assert_called()

    @patch("psutil.process_iter")
    def test_stop_jupyter_processes(self, mock_iter):
        proc_mock = MagicMock()
        proc_mock.info = {"pid": 123, "name": "jupyter", "cmdline": []}
        mock_iter.return_value = [proc_mock]
        self.manager.stop()
        proc_mock.terminate.assert_called_once()
        proc_mock.wait.assert_called_once_with(timeout=5)

    @patch("gaiaflow.managers.mlops_manager.env_exists", return_value=False)
    @patch("subprocess.Popen")
    def test_start_jupyter_env_not_exists(self, mock_popen, mock_env):
        env_name = "test-env"
        self.manager.get_env_name = MagicMock(return_value=env_name)
        self.manager.jupyter.start()
        mock_popen.assert_not_called()

    def test_docker_helper_builds_command(self):
        helper = DockerComposeHelper(self.manager.gaiaflow_path, is_prod_local=False)
        cmd = helper._base_cmd()
        self.assertIn("docker", cmd)
        self.assertIn("compose", cmd)
        self.assertEqual(cmd.count("-f"), 1)

    def test_docker_helper_builds_command_prod_local(self):
        helper = DockerComposeHelper(self.manager.gaiaflow_path, is_prod_local=True)
        cmd = helper._base_cmd()
        self.assertIn("docker", cmd)
        self.assertIn("compose", cmd)
        self.assertEqual(cmd.count("-f"), 2)


    def test_docker_services_for_known_and_unknown(self):
        helper = DockerComposeHelper(Path("/tmp"), False)
        self.assertIn("mlflow", helper.docker_services_for("mlflow"))
        self.assertEqual(helper.docker_services_for("unknown"), [])

    @patch("gaiaflow.managers.mlops_manager.handle_error")
    @patch("gaiaflow.managers.mlops_manager.run")
    def test_run_compose_with_service_and_unknown_service(self, mock_run, mock_handle):
        with patch.object(self.manager.docker, "docker_services_for",
                          return_value=[]):
            self.manager.docker.run_compose(["up"], service="unknown_service")
            mock_handle.assert_called_once()

    def test_docker_prune(self):
        helper = self.manager.docker
        with patch("gaiaflow.managers.mlops_manager.run") as mock_run:
            helper.prune()
            self.assertGreaterEqual(mock_run.call_count, len(DockerResources.IMAGES))
