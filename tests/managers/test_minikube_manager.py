import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
import subprocess

import yaml

from gaiaflow.constants import BaseAction, ExtendedAction
from gaiaflow.managers.minikube_manager import (
    MinikubeManager,
    MinikubeHelper,
    DockerHelper,
    KubeConfigHelper,
    temporary_copy,
)


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

    @patch("gaiaflow.managers.minikube_manager.run")
    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=False)
    @patch.object(MinikubeHelper, "is_running", return_value=False)
    def test_start_success(self, mock_is_running, mock_is_wsl, mock_run):
        self.helper.start()
        mock_run.assert_called()
        args = mock_run.call_args
        self.assertEqual(args[0][0], ['minikube', 'start', '--profile',
                                 'test-profile', '--driver=docker', '--cpus=4', '--memory=4g'])

    @patch("gaiaflow.managers.minikube_manager.run")
    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=True)
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

    @patch("gaiaflow.managers.minikube_manager.run")
    @patch.object(MinikubeHelper, "is_running", return_value=True)
    def test_start_already_running(self, mock_is_running,
                                   mock_run):
        self.helper.start()
        mock_run.assert_not_called()

    @patch(
        "gaiaflow.managers.minikube_manager.run",
        side_effect=subprocess.CalledProcessError(1, "cmd"),
    )
    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=False)
    @patch.object(MinikubeHelper, "is_running", return_value=False)
    @patch.object(MinikubeHelper, "cleanup")
    def test_start_retries_after_cleanup(self, mock_cleanup, *_):
        with self.assertRaises(subprocess.CalledProcessError):
            self.helper.start()
        mock_cleanup.assert_called()

    @patch("gaiaflow.managers.minikube_manager.run")
    def test_stop(self, mock_run):
        self.helper.stop()
        mock_run.assert_called()

    @patch("gaiaflow.managers.minikube_manager.run")
    def test_cleanup(self, mock_run):
        self.helper.cleanup()
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_run_cmd(self, mock_run):
        self.helper.run_cmd(["status"])
        mock_run.assert_called()

class TestDockerHelper(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.tmpdir.name)
        self.helper = DockerHelper(
            image_name="test-image",
            project_path=self.project_path,
            local=True,
            minikube_helper=MinikubeHelper(),
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_dockerfile(self):
        dockerfile = self.project_path / "Dockerfile"
        dockerfile.write_text("ENV TEST=1\nENTRYPOINT test.sh\n")
        return dockerfile

    def test_stores_init_params(self):
        self.assertEqual(self.helper.image_name, "test-image")
        self.assertEqual(self.helper.project_path, self.project_path)
        self.assertTrue(self.helper.local)

    def test_has_expected_methods(self):
        for method in [
            "build_image",
            "_update_dockerfile",
            "_build_local",
            "_build_minikube",
        ]:
            self.assertTrue(hasattr(self.helper, method))

    @patch(
        "gaiaflow.managers.minikube_manager.find_python_packages",
        return_value=["mypkg"],
    )
    def test_update_dockerfile_inserts_copy(self, _):
        dockerfile = self._write_dockerfile()
        self.helper._update_dockerfile(dockerfile)
        text = dockerfile.read_text()
        self.assertIn("COPY mypkg ./mypkg", text)
        self.assertIn("COPY runner.py ./runner.py", text)

    def test_add_copy_statements_raises_without_env(self):
        dockerfile = self.project_path / "Dockerfile"
        dockerfile.write_text("ENTRYPOINT test.sh\n")
        with self.assertRaises(ValueError):
            DockerHelper._add_copy_statements_to_dockerfile(str(dockerfile), [])

    def test_add_copy_statements_raises_without_entrypoint(self):
        dockerfile = self.project_path / "Dockerfile"
        dockerfile.write_text("ENV TEST=1\n")
        with self.assertRaises(ValueError):
            DockerHelper._add_copy_statements_to_dockerfile(str(dockerfile), [])

    def test_parse_minikube_env(self):
        output = 'export FOO="bar"\nexport BAZ="qux"\n'
        env = DockerHelper._parse_minikube_env(output)
        self.assertEqual(env["FOO"], "bar")
        self.assertEqual(env["BAZ"], "qux")

    @patch("gaiaflow.managers.minikube_manager.run")
    def test_build_local(self, mock_run):
        dockerfile = self._write_dockerfile()
        self.helper._build_local(dockerfile)
        mock_run.assert_called()

    @patch("gaiaflow.managers.minikube_manager.run")
    @patch.object(MinikubeHelper, "run_cmd")
    def test_build_minikube(self, mock_run_cmd, mock_run):
        mock_run_cmd.return_value = MagicMock(stdout=b'export DOCKER_TLS_VERIFY="1"\n')
        dockerfile = self._write_dockerfile()
        self.helper._build_minikube(dockerfile)
        mock_run.assert_called()

    @patch("gaiaflow.managers.minikube_manager.log_error")
    def test_build_image_missing_dockerfile(self, mock_log_error):
        bad_path = self.project_path / "Dockerfile"
        self.assertFalse(bad_path.exists())
        with (
            patch.object(self.helper, "_update_dockerfile") as mock_update,
            patch.object(self.helper, "_build_local") as mock_local,
            patch.object(self.helper, "_build_minikube") as mock_minikube,
        ):
            self.helper.build_image(bad_path)

        mock_log_error.assert_called_once()
        mock_update.assert_not_called()
        mock_local.assert_not_called()
        mock_minikube.assert_not_called()

    @patch(
        "gaiaflow.managers.minikube_manager.find_python_packages",
        return_value=["mypkg"],
    )
    @patch("gaiaflow.managers.minikube_manager.temporary_copy")
    def test_build_image_local(self, mock_temp_copy, _):
        dockerfile = self._write_dockerfile()
        self.helper.local = True

        with (
            patch.object(self.helper, "_update_dockerfile") as mock_update,
            patch.object(self.helper, "_build_local") as mock_local,
        ):
            self.helper.build_image(dockerfile)

        mock_update.assert_called_once_with(dockerfile)
        mock_local.assert_called_once_with(dockerfile)
        mock_temp_copy.assert_called_once()  # runner.py should be copied

    @patch(
        "gaiaflow.managers.minikube_manager.find_python_packages",
        return_value=["mypkg"],
    )
    @patch("gaiaflow.managers.minikube_manager.temporary_copy")
    def test_build_image_minikube(self, mock_temp_copy, _):
        dockerfile = self._write_dockerfile()
        self.helper.local = False

        with (
            patch.object(self.helper, "_update_dockerfile") as mock_update,
            patch.object(self.helper, "_build_minikube") as mock_minikube,
        ):
            self.helper.build_image(dockerfile)

        mock_update.assert_called_once_with(dockerfile)
        mock_minikube.assert_called_once_with(dockerfile)
        mock_temp_copy.assert_called_once()


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
    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=False)
    def test_create_inline_linux(self, *_):
        helper = KubeConfigHelper(self.gaia_path, os_type="linux")
        self._write_kube_config({"clusters": [{"cluster": {"server": "127.0.0.1"}}]})
        helper.create_inline()
        self.assertTrue(
            (self.gaia_path / "_docker" / "kube_config_inline").exists()
        )

    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=False)
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

    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=True)
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

    @patch("gaiaflow.managers.minikube_manager.is_wsl", return_value=True)
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


class TestMinikubeManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.manager = MinikubeManager(
            gaiaflow_path=Path(self.tmpdir.name),
            user_project_path=Path(self.tmpdir.name),
            action=BaseAction.START,
            local=True,
            image_name="img",
        )


    def tearDown(self):
        self.tmpdir.cleanup()


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
