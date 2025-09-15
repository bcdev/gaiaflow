import json
import tempfile
import unittest
from pathlib import Path
import docker
from unittest.mock import patch, mock_open, MagicMock

from gaiaflow.managers import utils


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name)
        self.gaiaflow_path = self.base_path / "gaiaflow-project"
        self.gaiaflow_path.mkdir()

        required_structure = {
            "_docker": {
                "docker-compose": [
                    "docker-compose.yml",
                    "docker-compose-minikube-network.yml",
                    "entrypoint.sh",
                ],
                "airflow": ["Dockerfile"],
                "mlflow": ["Dockerfile", "requirements.txt"],
                "user-package": ["Dockerfile"],
                "_files_": ["kube_config_inline"],
            }
        }

        self.gaiaflow_project_path = self.gaiaflow_path / "_docker"
        self.gaiaflow_project_path.mkdir(exist_ok=True)
        for folder, contents in required_structure["_docker"].items():
            if folder != "_files_":
                folder_path = self.gaiaflow_project_path / folder
                folder_path.mkdir(parents=True, exist_ok=True)
                for file in contents:
                    (folder_path / file).write_text(f"dummy {file}")
            else:
                for file in contents:
                    (self.gaiaflow_project_path / file).write_text(f"dummy {file}")

        self.state_file_folder = self.base_path / ".gaiaflow"
        self.state_file_folder.mkdir(exist_ok=True)
        self.state_file = self.state_file_folder  / "state.json"
        self.state_data = {str(self.gaiaflow_path): {"project_path": str(self.base_path)}}
        self.state_file.write_text(json.dumps(self.state_data))
        patcher = patch("gaiaflow.managers.utils.GAIAFLOW_STATE_FILE",
                        self.state_file)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_get_gaialfow_version_from_pyproject(self):
        with patch("importlib.metadata.version", side_effect=Exception):
            pyproject_path = self.base_path / "pyproject.toml"
            pyproject_path.write_text("[project]\nversion = '1.2.3'\n")

            with patch(
                "pathlib.Path.read_text", return_value=pyproject_path.read_text()
            ):
                version = utils.get_gaiaflow_version()
                self.assertEqual(version, "1.2.3")

    def test_path_exists_in_state_and_fs(self):
        exists = utils.gaiaflow_path_exists_in_state(self.gaiaflow_path, check_fs=True)
        self.assertTrue(exists)

    def test_path_missing_in_state(self):
        missing_path = self.base_path / "missing"
        exists = utils.gaiaflow_path_exists_in_state(missing_path)
        self.assertFalse(exists)

    def test_path_exists_only_in_state(self):
        missing_path = self.base_path / "nonexistent"
        state = json.loads(self.state_file.read_text())
        state[str(missing_path)] = {"project_path": str(self.base_path)}
        self.state_file.write_text(json.dumps(state))
        exists = utils.gaiaflow_path_exists_in_state(missing_path, check_fs=False)
        self.assertTrue(exists)

    def test_check_fs_path_missing_on_disk(self):
        missing_on_disk = self.base_path / "nonexistent"
        state = json.loads(self.state_file.read_text())
        state[str(missing_on_disk)] = {"project_path": str(self.base_path)}
        self.state_file.write_text(json.dumps(state))

        with patch("typer.echo") as mock_echo:
            exists = utils.gaiaflow_path_exists_in_state(missing_on_disk, check_fs=True)
            self.assertFalse(exists)
            mock_echo.assert_called_once()
            self.assertIn(
                "Gaiaflow path exists in state but not on disk",
                mock_echo.call_args[0][0],
            )

    def test_check_fs_structure_invalid(self):
        invalid_path = self.base_path / "bad_project"
        invalid_path.mkdir()
        state = json.loads(self.state_file.read_text())
        state[str(invalid_path)] = {"project_path": str(self.base_path)}
        self.state_file.write_text(json.dumps(state))

        with patch("gaiaflow.managers.utils.check_structure",
                    return_value=False):
            exists = utils.gaiaflow_path_exists_in_state(invalid_path, check_fs=True)
            self.assertFalse(exists)

    def test_invalid_state_file_returns_false(self):
        self.state_file.write_text("not a json")
        exists = utils.gaiaflow_path_exists_in_state(self.gaiaflow_path)
        self.assertFalse(exists)

    def test_convert_crlf_to_lf(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"line1\r\nline2\r\n")
            tmp.close()
            utils.convert_crlf_to_lf(tmp.name)
            content = Path(tmp.name).read_bytes()
            self.assertNotIn(b"\r\n", content)
            self.assertIn(b"\n", content)

    def test_find_python_packages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pkg = tmp / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("# package")
            (tmp / "nopkg").mkdir()
            packages = utils.find_python_packages(tmp)
            self.assertIn("pkg", packages)
            self.assertNotIn("nopkg", packages)

    def test_is_wsl_false(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertFalse(utils.is_wsl())

        m = mock_open(read_data="Linux version ... Microsoft WSL2 ...")
        with patch("builtins.open", m):
            self.assertTrue(utils.is_wsl())

    def test_log_info_and_error(self):
        utils.log_info("info")
        utils.log_error("error")

    @patch("subprocess.call", return_value=0)
    def test_run_success(self, mock_call):
        utils.run(["echo"], "fail")
        mock_call.assert_called_once()

    @patch("gaiaflow.managers.utils.subprocess.call",
           side_effect=FileNotFoundError("cmd not found"))
    def test_run_fail(self, mock_call):
        with self.assertRaises(FileNotFoundError):
            utils.run(["nonexistent_command"], "fail")
        mock_call.assert_called_once()

    def test_handle_error_exits(self):
        with self.assertRaises(SystemExit):
            utils.handle_error("fail")

    def test_save_and_load_project_state(self):
        project_path = self.base_path / "proj"
        project_path.mkdir()
        gaiaflow_path = self.base_path / "gflow"
        gaiaflow_path.mkdir()
        utils.save_project_state(project_path, gaiaflow_path)
        state = utils.load_project_state()
        self.assertIn(str(gaiaflow_path), state)

    def test_save_with_no_project_state(self):
        project_path = self.base_path / "proj"
        project_path.mkdir()
        self.state_file.unlink()
        utils.save_project_state(project_path, self.gaiaflow_path)


    def test_load_project_state_no_file(self):
        if self.state_file.exists():
            self.state_file.unlink()
        self.assertIsNone(utils.load_project_state())

    def test_delete_project_state_removes_key(self):
        project_path = self.base_path / "proj"
        project_path.mkdir()
        gaiaflow_path = self.base_path / "gflow"
        gaiaflow_path.mkdir()

        utils.save_project_state(project_path, gaiaflow_path)
        state = json.loads(self.state_file.read_text())
        self.assertIn(str(gaiaflow_path), state)

        utils.delete_project_state(gaiaflow_path)
        state = json.loads(self.state_file.read_text())
        self.assertNotIn(str(gaiaflow_path), state)

    def test_state_file_missing(self):
        self.state_file.unlink()
        utils.delete_project_state(self.gaiaflow_path)
        self.assertFalse(self.state_file.exists())

    def test_delete_raises_jsondecodeerror(self):
        self.state_file.write_text("{ invalid_data }")
        with self.assertRaises(json.JSONDecodeError):
            utils.delete_project_state(self.gaiaflow_path)

    def test_delete_raises_when_state_is_string(self):
        self.state_file.write_text(json.dumps("invalid_data"))
        with self.assertRaises(AttributeError):
            utils.delete_project_state(self.gaiaflow_path)

    def test_update_project_state(self):
        project_path = self.base_path / "proj"
        project_path.mkdir()
        gaiaflow_path = self.base_path / "gflow"
        gaiaflow_path.mkdir()

        utils.save_project_state(project_path, gaiaflow_path)
        state = json.loads(self.state_file.read_text())
        self.assertIn(str(gaiaflow_path), state)

        gaiaflow_path2 = self.base_path / "gflow_v2"
        gaiaflow_path2.mkdir()

        utils.save_project_state(project_path, gaiaflow_path2)
        state = json.loads(self.state_file.read_text())
        self.assertIn(str(gaiaflow_path2), state)
        self.assertNotIn(str(gaiaflow_path), state)

    def test_check_structure_success_and_fail(self):
        folder = self.base_path / "folder"
        folder.mkdir()
        (folder / "file.txt").write_text("hi")
        structure = {"folder": ["file.txt"]}
        self.assertTrue(utils.check_structure(self.base_path, structure))

        structure = {"folder": ["missing.txt"]}
        self.assertFalse(utils.check_structure(self.base_path, structure))

        structure = {"missing_folder": ["file.txt"]}
        self.assertFalse(utils.check_structure(self.base_path, structure))

        nested_folder = folder / "nested"
        nested_folder.mkdir()
        (nested_folder / "nested_file.txt").write_text("ok")
        structure = {"folder": {"nested": ["nested_file.txt"]}}
        self.assertTrue(utils.check_structure(self.base_path, structure))

        structure = {"folder": {"nested": ["missing_file.txt"]}}
        self.assertFalse(utils.check_structure(self.base_path, structure))

        (self.base_path / "file1.txt").write_text("ok")
        structure = {"_files_": ["file1.txt"]}
        self.assertTrue(utils.check_structure(self.base_path, structure))

        structure = {"_files_": ["missing_file.txt"]}
        self.assertFalse(utils.check_structure(self.base_path, structure))

    def test_parse_key_value_pairs(self):
        pairs = ["a=1", "b=2"]
        result = utils.parse_key_value_pairs(pairs)
        self.assertEqual(result, {"a": "1", "b": "2"})
        with self.assertRaises(Exception):
            utils.parse_key_value_pairs(["invalid"])

    def test_create_directory_and_permissions(self):
        dir_path = self.base_path / "newdir"
        utils.create_directory(str(dir_path))
        self.assertTrue(dir_path.exists())
        utils.set_permissions(dir_path)

    def test_create_directory_already_exists(self):
        dir_path = self.base_path / "newdir"
        utils.create_directory(str(dir_path))
        self.assertTrue(dir_path.exists())
        utils.create_directory(str(dir_path))

    @patch("gaiaflow.managers.utils.fs")
    def test_create_directory_makedirs_fails(self, mock_fs):
        mock_fs.exists.return_value = False
        mock_fs.makedirs.side_effect = Exception("boom")
        with self.assertRaises(SystemExit):
            utils.create_directory("fail_dir")

    @patch("subprocess.run")
    def test_env_exists_true_false(self, mock_run):
        mock_run.return_value.stdout = json.dumps({"envs": ["env1", "env2"]})
        self.assertTrue(utils.env_exists("env1"))
        self.assertFalse(utils.env_exists("envX"))

    @patch("gaiaflow.managers.utils.docker.from_env")
    @patch("gaiaflow.managers.utils.log_info")
    @patch("gaiaflow.managers.utils.log_error")
    def test_update_micromamba_env_in_docker(self, mock_error, mock_info, mock_docker):
        client_mock = MagicMock()
        mock_docker.return_value = client_mock

        container1 = MagicMock()
        container1.exec_run.return_value = (0, b"success")
        container2 = MagicMock()
        container2.exec_run.return_value = (1, b"fail")
        # container 3: container not found
        # will raise docker.errors.NotFound
        container4 = MagicMock()
        container4.exec_run.side_effect = RuntimeError("boom")

        def get_container(name):
            if name == "c1":
                return container1
            if name == "c2":
                return container2
            if name == "c3":
                raise docker.errors.NotFound("not found")
            if name == "c4":
                return container4
            raise ValueError("Unexpected container")

        client_mock.containers.get.side_effect = get_container

        containers = ["c1", "c2", "c3", "c4"]
        utils.update_micromamba_env_in_docker(containers, env_name="test_env", max_workers=4)

        client_mock.containers.get.assert_any_call("c1")
        client_mock.containers.get.assert_any_call("c2")
        client_mock.containers.get.assert_any_call("c3")
        client_mock.containers.get.assert_any_call("c4")

        container1.exec_run.assert_called_once()
        container2.exec_run.assert_called_once()
        container4.exec_run.assert_called_once()

        mock_info.assert_any_call("[c1] Updated successfully.")
        mock_error.assert_any_call("[c2] micromamba failed: fail")
        mock_error.assert_any_call("Container 'c3' not found. Skipping.")
        self.assertTrue(
            any("[c4] Unexpected error: boom" in args[0] for args,
            _ in mock_error.call_args_list)
        )

    def test_project_path_not_found(self):
        missing_path = Path(self.tmp_dir.name) / "missing"
        with self.assertRaises(FileNotFoundError) as ctx:
            utils.create_gaiaflow_context_path(missing_path)
        self.assertIn("not found", str(ctx.exception))

    @patch("gaiaflow.managers.utils.get_gaiaflow_version", return_value="1.2.3")
    def test_successful_context_path(self, mock_version):
        project_path = self.base_path / "proj"
        project_path.mkdir()
        gaiaflow_path, user_project_path = utils.create_gaiaflow_context_path(project_path)
        self.assertEqual(user_project_path, project_path.resolve())
        self.assertIn("gaiaflow-1.2.3-proj", str(gaiaflow_path))
        self.assertEqual(gaiaflow_path.parent, Path(tempfile.gettempdir()))
        mock_version.assert_called_once()