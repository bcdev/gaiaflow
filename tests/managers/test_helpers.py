import unittest
import tempfile
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch, MagicMock

import yaml

from gaiaflow.constants import BaseAction, Service
from gaiaflow.managers.helpers import (
    JupyterHelper,
    KubeConfigHelper,
    DockerHelper,
    MinikubeHelper,
    BaseDockerHandler,
    MinikubeDockerHandler,
    DockerHandlerMode,
    temporary_copy,
    DockerComposeHelper,
    DockerResources,
    MinikubeUserCustomImageDockerHandler,
    LocalUserCustomImageDockerHandler,
    LocalDockerHandler,
)
from gaiaflow.managers.mlops_manager import MlopsManager


class TestJupyterHelper(unittest.TestCase):
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
             patch("gaiaflow.managers.helpers.env_exists", return_value=True):
            helper.start()
            mock_popen.assert_called()

    @patch("psutil.process_iter")
    def test_stop_terminates_jupyter_processes(self, mock_iter):
        fake_proc = MagicMock()
        helper = JupyterHelper(8895, "mamba", "custom-env", self.manager.gaiaflow_path)
        fake_proc.info = {"pid": 1, "name": "jupyter", "cmdline": ["jupyter-lab"]}
        mock_iter.return_value = [fake_proc]
        helper.stop()
        fake_proc.terminate.assert_called_once()


class TestTemporaryCopy(unittest.TestCase):
    def test_temporary_copy_creates_and_deletes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src.txt"
            dest = Path(tmpdir) / "dest.txt"

            src.write_text("hello")

            with temporary_copy(src, dest):
                self.assertTrue(dest.exists())
                self.assertEqual(dest.read_text(), "hello")

            self.assertFalse(dest.exists())

class TestMinikubeHelper(unittest.TestCase):
    def setUp(self):
        self.helper = MinikubeHelper(profile="test-profile")

    def test_profile_name_is_stored(self):
        self.assertEqual(self.helper.profile, "test-profile")

    def test_has_expected_methods(self):
        for method in ["is_running", "start", "stop", "cleanup", "run_cmd"]:
            self.assertTrue(callable(getattr(self.helper, method)))

    @patch("subprocess.run")
    def test_is_running_true(self, mock_run):
        mock_run.return_value = MagicMock(stdout=b"Running")
        self.assertTrue(self.helper.is_running())

    @patch("subprocess.run")
    def test_is_running_false(self, mock_run):
        mock_run.return_value = MagicMock(stdout=b"Stopped")
        self.assertFalse(self.helper.is_running())

    @patch("gaiaflow.managers.helpers.run")
    @patch("gaiaflow.managers.helpers.is_wsl", return_value=False)
    @patch.object(MinikubeHelper, "is_running", return_value=False)
    def test_start_success(self, mock_is_running, mock_is_wsl, mock_run):
        self.helper.start()
        mock_run.assert_called()
        args = mock_run.call_args
        self.assertEqual(args[0][0], ['minikube', 'start', '--profile',
                                 'test-profile', '--driver=docker', '--cpus=4', '--memory=4g'])

    @patch("gaiaflow.managers.helpers.run")
    @patch("gaiaflow.managers.helpers.is_wsl", return_value=True)
    @patch.object(MinikubeHelper, "is_running", return_value=False)
    def test_start_success_wsl(self, mock_is_running, mock_is_wsl, mock_run):
        self.helper.start()
        mock_run.assert_called()
        args = mock_run.call_args
        self.assertEqual(
            args[0][0],
            [
                "minikube",
                "start",
                "--profile",
                "test-profile",
                "--driver=docker",
                "--cpus=4",
                "--memory=4g",
                "--extra-config=kubelet.cgroup-driver=cgroupfs"
            ],
        )

    @patch("gaiaflow.managers.helpers.run")
    @patch.object(MinikubeHelper, "is_running", return_value=True)
    def test_start_already_running(self, mock_is_running,
                                   mock_run):
        self.helper.start()
        mock_run.assert_not_called()

    @patch(
        "gaiaflow.managers.helpers.run",
        side_effect=subprocess.CalledProcessError(1, "cmd"),
    )
    @patch("gaiaflow.managers.helpers.is_wsl", return_value=False)
    @patch.object(MinikubeHelper, "is_running", return_value=False)
    @patch.object(MinikubeHelper, "cleanup")
    def test_start_retries_after_cleanup(self, mock_cleanup, *_):
        with self.assertRaises(subprocess.CalledProcessError):
            self.helper.start()
        mock_cleanup.assert_called()

    @patch("gaiaflow.managers.helpers.run")
    def test_stop(self, mock_run):
        self.helper.stop()
        mock_run.assert_called()

    @patch("gaiaflow.managers.helpers.run")
    def test_cleanup(self, mock_run):
        self.helper.cleanup()
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_run_cmd(self, mock_run):
        self.helper.run_cmd(["status"])
        mock_run.assert_called()

class TestDockerComposeHelper(unittest.TestCase):
    def setUp(self):
        self.helper = DockerComposeHelper(Path("/fake/path"), is_prod_local=True)


    def test_base_cmd_with_prod_local(self):
        cmd = self.helper._base_cmd()
        self.assertIn("docker", cmd)
        self.assertIn("docker-compose-minikube-network.yml", " ".join(cmd))


    def test_docker_services_for_valid_key(self):
        services = DockerComposeHelper.docker_services_for("airflow")
        self.assertEqual(services, DockerResources.SERVICES["airflow"])


    def test_docker_services_for_invalid_key(self):
        services = DockerComposeHelper.docker_services_for("unknown")
        self.assertEqual(services, [])


    @patch("gaiaflow.managers.helpers.run")
    @patch("gaiaflow.managers.helpers.log_info")
    def test_run_compose_with_service(self, mock_log, mock_run):
        with patch.object(DockerComposeHelper, "docker_services_for", return_value=["svc"]):
            self.helper.run_compose(["up"], service="airflow")
            mock_run.assert_called()


    @patch("gaiaflow.managers.helpers.run")
    def test_prune_runs_expected_cmds(self, mock_run):
        DockerComposeHelper.prune()
        self.assertGreaterEqual(mock_run.call_count, len(DockerResources.IMAGES))

class TestKubeConfigHelper(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.gaia_path = Path(self.tmpdir.name)
        (self.gaia_path / "_docker").mkdir()
        self.helper = KubeConfigHelper(gaiaflow_path=self.gaia_path, os_type="linux")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_kube_config(self, data):
        kube_dir = Path.home() / ".kube"
        kube_dir.mkdir(exist_ok=True)
        kube_config = kube_dir / "config"
        with open(kube_config, "w") as f:
            yaml.dump(data, f)
        return kube_config

    @patch("subprocess.call", return_value=0)
    def test_write_inline_creates_file(self, _):
        kube_config = self._write_kube_config({"clusters": []})
        self.helper._write_inline(kube_config)
        out_file = self.gaia_path / "_docker" / "kube_config_inline"
        self.assertTrue(out_file.exists())

    def test_backup_and_patch_config(self):
        kube_config = self._write_kube_config(
            {"clusters": [{"cluster": {"server": "127.0.0.1"}}]}
        )
        backup = kube_config.with_suffix(".backup")
        self.helper._backup_kube_config(kube_config, backup)
        self.assertTrue(backup.exists())

        self.helper._patch_kube_config(kube_config)
        patched = yaml.safe_load(open(kube_config))
        self.assertIn("clusters", patched)

    @patch("subprocess.call", return_value=0)
    @patch("gaiaflow.managers.helpers.is_wsl", return_value=False)
    def test_create_inline_linux(self, *_):
        helper = KubeConfigHelper(self.gaia_path, os_type="linux")
        self._write_kube_config({"clusters": [{"cluster": {"server": "127.0.0.1"}}]})
        helper.create_inline()
        self.assertTrue(
            (self.gaia_path / "_docker" / "kube_config_inline").exists()
        )

    @patch("gaiaflow.managers.helpers.is_wsl", return_value=False)
    def test_create_inline_windows_branch(self, _):
        helper = KubeConfigHelper(self.gaia_path, os_type="windows")
        kube_config = self._write_kube_config({"clusters": []})
        backup_config = kube_config.with_suffix(".backup")
        backup_config.write_text("backup")

        with (
            patch("shutil.copy") as mock_copy,
            patch.object(Path, "unlink") as mock_unlink,
        ):
            helper.create_inline()

        mock_copy.assert_called_once_with(backup_config, kube_config)
        mock_unlink.assert_called_once()

    @patch("gaiaflow.managers.helpers.is_wsl", return_value=True)
    def test_create_inline_wsl_branch(self, _):
        helper = KubeConfigHelper(self.gaia_path, os_type="linux")
        kube_config = self._write_kube_config({"clusters": []})
        backup_config = kube_config.with_suffix(".backup")
        backup_config.write_text("backup")

        with (
            patch("shutil.copy") as mock_copy,
            patch.object(Path, "unlink") as mock_unlink,
        ):
            helper.create_inline()

        mock_copy.assert_called_once_with(backup_config, kube_config)
        mock_unlink.assert_called_once()

    @patch("gaiaflow.managers.helpers.is_wsl", return_value=True)
    def test_patch_wsl(self, _):
        helper = KubeConfigHelper(self.gaia_path, os_type="linux")
        config = self._write_kube_config({"clusters": [{"cluster": {"server": "localhost"}}]})
        helper._patch_kube_config(config)
        data = yaml.safe_load(open(config))
        assert data["clusters"][0]["cluster"]["insecure-skip-tls-verify"]

    def test_patch_windows(self):
        helper = KubeConfigHelper(self.gaia_path, os_type="windows")
        config = self._write_kube_config({"clusters": [{"cluster": {"server": "127.0.0.1"}}]})
        helper._patch_kube_config(config)
        data = yaml.safe_load(open(config))
        assert data["clusters"][0]["cluster"]["server"] == "host.docker.internal"

class TestBaseDockerHandler(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.tmpdir.name)
        self.dockerfile = self.project_path / "Dockerfile"
        self.dockerfile.write_text("ENV TEST=1\nENTRYPOINT test.sh\n")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_docker_handler_valid_and_invalid(self):
        handler = BaseDockerHandler.get_docker_handler(DockerHandlerMode.LOCAL)
        self.assertIsInstance(handler, LocalDockerHandler)
        with self.assertRaises(ValueError):
            BaseDockerHandler.get_docker_handler("bad-mode")

    @patch("gaiaflow.managers.helpers.find_python_packages", return_value=[
        "pkg1"])
    @patch("gaiaflow.managers.helpers.temporary_copy")
    def test_pre_build_returns_contextmanager(self, mock_temp_copy, _):
        handler = BaseDockerHandler()
        ctx = handler.pre_build("img", self.dockerfile, self.project_path)
        self.assertTrue(hasattr(ctx, "__enter__"))
        mock_temp_copy.assert_called_once()

    def test_add_copy_statements_writes_expected_lines(self):
        BaseDockerHandler._add_copy_statements_to_dockerfile(str(self.dockerfile), ["mypkg"])
        text = self.dockerfile.read_text()
        self.assertIn("COPY mypkg ./mypkg", text)
        self.assertIn("COPY runner.py ./runner.py", text)

    @patch("gaiaflow.managers.helpers.find_python_packages", return_value=["mypkg"])
    def test_base_dockerhandler_update_dockerfile(self, _):
        handler = BaseDockerHandler()
        handler.project_path = (
            self.project_path
        )
        handler._update_dockerfile(self.dockerfile)

        contents = self.dockerfile.read_text()
        self.assertIn("COPY mypkg ./mypkg", contents)
        self.assertIn("COPY runner.py ./runner.py", contents)
        env_index = contents.splitlines().index("ENV TEST=1")
        entry_index = contents.splitlines().index("ENTRYPOINT test.sh")
        copy_index = contents.splitlines().index("COPY mypkg ./mypkg")
        self.assertGreater(copy_index, env_index)
        self.assertLess(copy_index, entry_index)

    def test_abstract_methods_raise(self):
        handler = BaseDockerHandler()
        with self.assertRaises(NotImplementedError):
            handler.build("img", self.dockerfile, self.project_path)
        with self.assertRaises(NotImplementedError):
            handler.list_images()
        with self.assertRaises(NotImplementedError):
            handler.remove_image("img")


class TestDockerHandlers(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.tmpdir.name)
        self.dockerfile = self.project_path / "Dockerfile"
        self.dockerfile.write_text("ENV TEST=1\nENTRYPOINT test.sh\n")


    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("gaiaflow.managers.helpers.run")
    def test_local_docker_handler_build(self, mock_run):
        handler = LocalDockerHandler()
        handler.build("img", self.dockerfile, self.project_path)

        mock_run.assert_called_once()
        cmd, msg = mock_run.call_args[0]
        self.assertEqual(
            cmd,
            [
                "docker",
                "build",
                "-t",
                "img",
                "-f",
                str(self.dockerfile),
                str(self.project_path),
            ],
        )
        self.assertIn("Error building Docker image locally", msg)


    @patch("gaiaflow.managers.helpers.run")
    def test_local_docker_handler_list(self, mock_run):
        handler = LocalDockerHandler()
        handler.list_images()
        handler.remove_image("img")

        cmd1, msg1 = mock_run.call_args_list[0][0]
        self.assertEqual(cmd1, ["docker", "image", "ls"])
        self.assertIn("Error listing Docker images locally", msg1)

    @patch("gaiaflow.managers.helpers.run")
    def test_local_docker_handler_remove(self, mock_run):
        handler = LocalDockerHandler()
        handler.list_images()
        handler.remove_image("img")

        cmd2, msg2 = mock_run.call_args_list[1][0]
        self.assertEqual(cmd2, ["docker", "rmi", "-f", "img"])
        self.assertIn("Error removing Docker image img locally", msg2)


    @patch.object(MinikubeHelper, "is_running", return_value=True)
    @patch("gaiaflow.managers.helpers.run")
    def test_minikube_docker_handler_build(self, mock_run, _):
        handler = MinikubeDockerHandler(MinikubeHelper())
        handler.build("img", self.dockerfile, self.project_path)

        mock_run.assert_called_once()
        cmd, msg = mock_run.call_args[0]
        self.assertEqual(
            cmd,
            [
                "docker",
                "build",
                "-t",
                "img",
                "-f",
                str(self.dockerfile),
                str(self.project_path),
            ],
        )
        self.assertIn("Error building Docker image inside Minikube", msg)
        self.assertIn("env", mock_run.call_args.kwargs)

    @patch.object(MinikubeHelper, "is_running", return_value=True)
    @patch("gaiaflow.managers.helpers.run")
    def test_minikube_docker_handler_list(self, mock_run, _):
        handler = MinikubeDockerHandler(MinikubeHelper())
        handler.list_images()
        handler.remove_image("img")

        cmd1, msg1 = mock_run.call_args_list[0][0]
        self.assertEqual(cmd1, ["docker", "image", "ls"])
        self.assertIn("Error listing Docker images inside Minikube", msg1)
        self.assertIn("env", mock_run.call_args_list[0].kwargs)

    @patch.object(MinikubeHelper, "is_running", return_value=True)
    @patch("gaiaflow.managers.helpers.run")
    def test_minikube_docker_handler_remove(self, mock_run, _):
        handler = MinikubeDockerHandler(MinikubeHelper())
        handler.list_images()
        handler.remove_image("img")

        cmd2, msg2 = mock_run.call_args_list[1][0]
        self.assertEqual(cmd2, ["docker", "rmi", "-f", "img"])
        self.assertIn("Error removing Docker image img inside Minikube", msg2)
        self.assertIn("env", mock_run.call_args_list[1].kwargs)


    def test_parse_minikube_env(self):
        output = 'export FOO="bar"\nexport BAZ="qux"\n'
        env = MinikubeDockerHandler._parse_minikube_env(output)
        self.assertEqual(env["FOO"], "bar")
        self.assertEqual(env["BAZ"], "qux")


    def test_local_user_custom_handler_build(self):
        handler = LocalUserCustomImageDockerHandler()
        with patch.object(LocalDockerHandler, "build") as mock_build:
            handler.build("img", self.dockerfile, self.project_path)
            mock_build.assert_called_once_with("img", self.dockerfile, self.project_path)

    def test_local_user_custom_handler_pre_build_is_none(self):
        handler = LocalUserCustomImageDockerHandler()
        result = handler.pre_build("img", self.dockerfile, self.project_path)
        self.assertIsNone(result)

    def test_minikube_user_custom_handler_build(self):
        with patch.object(MinikubeDockerHandler, "build") as mock_build:
            handler = MinikubeUserCustomImageDockerHandler(MinikubeHelper())
            handler.build("img", self.dockerfile, self.project_path)
            mock_build.assert_called_once_with("img", self.dockerfile, self.project_path)

    def test_minikube_user_custom_handler_pre_build_is_none(self):
        handler = MinikubeUserCustomImageDockerHandler(MinikubeHelper())
        result = handler.pre_build("img", self.dockerfile, self.project_path)
        self.assertIsNone(result)


class TestDockerHelperClass(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.tmpdir.name)
        self.dockerfile = self.project_path / "Dockerfile"
        self.dockerfile.write_text("FROM alpine\n")
        self.handler = MagicMock(spec=BaseDockerHandler)
        self.helper = DockerHelper("test-img", self.project_path, self.handler)

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("gaiaflow.managers.helpers.log_error")
    def test_build_image_missing_dockerfile_logs_error(self, mock_log):
        missing = self.project_path / "DoesNotExist"
        self.helper.build_image(missing)
        mock_log.assert_called_once_with(f"Dockerfile not found at {missing}")
        self.handler.build.assert_not_called()
        self.handler.post_build.assert_not_called()

    def test_build_image_with_prebuild_context(self):
        cm = MagicMock()
        cm.__enter__ = MagicMock()
        cm.__exit__ = MagicMock()
        self.handler.pre_build.return_value = cm

        self.helper.build_image(self.dockerfile)

        self.handler.pre_build.assert_called_once_with("test-img", self.dockerfile, self.project_path)
        cm.__enter__.assert_called_once()
        self.handler.build.assert_called_once_with("test-img", self.dockerfile, self.project_path)
        self.handler.post_build.assert_called_once_with("test-img", self.dockerfile, self.project_path)

    def test_build_image_without_prebuild_context(self):
        self.handler.pre_build.return_value = None

        self.helper.build_image(self.dockerfile)

        self.handler.build.assert_called_once_with("test-img", self.dockerfile, self.project_path)
        self.handler.post_build.assert_called_once_with("test-img", self.dockerfile, self.project_path)

    def test_list_images_delegates(self):
        self.helper.list_images()
        self.handler.list_images.assert_called_once()

    def test_remove_image_delegates(self):
        self.helper.remove_image("some-img")
        self.handler.remove_image.assert_called_once_with("some-img")
