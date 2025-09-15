import json
import unittest
from unittest.mock import patch

import gaiaflow.core.operators as operators
from gaiaflow.core.create_task import GaiaflowMode


class TestBaseTaskOperator(unittest.TestCase):
    def setUp(self):
        self.base_op = operators.BaseTaskOperator(
            task_id="t1",
            func_path="mymod:func",
            func_args=[1, operators.FromTask("taskX", "key1")],
            func_kwargs={"foo": operators.FromTask("taskY")},
            image="img",
            secrets=["s1"],
            env_vars={"ENV": "value"},
            retries=1,
            params={"p": "q"},
            mode="dev",
        )

    def test_resolve_xcom_value_default_key(self):
        val = self.base_op._resolve_xcom_value({"task": "up_task"})
        self.assertIn("ti.xcom_pull(task_ids='up_task')", val)

    def test_resolve_xcom_value_custom_key(self):
        val = self.base_op._resolve_xcom_value({"task": "up_task", "key": "out"})
        self.assertIn("['out']", val)

    def test_resolve_args_kwargs(self):
        args, kwargs = self.base_op.resolve_args_kwargs()
        self.assertEqual(args[1], ("{{ ti.xcom_pull(task_ids='taskX')['key1'] }}"))
        self.assertEqual(kwargs["foo"], "{{ ti.xcom_pull(task_ids='taskY') }}")

    def test_create_func_env_vars(self):
        envs = self.base_op.create_func_env_vars()
        self.assertIn("FUNC_PATH", envs)
        self.assertTrue(isinstance(json.loads(envs["FUNC_ARGS"]), list))
        self.assertTrue(isinstance(json.loads(envs["FUNC_KWARGS"]), dict))

    def test_create_task(self):
        with self.assertRaises(NotImplementedError):
            self.base_op.create_task()


class TestOperators(unittest.TestCase):
    def test_to_dict(self):
        ft = operators.FromTask("upstream_task", key="mykey")
        self.assertEqual(ft.to_dict(), {"task": "upstream_task", "key": "mykey"})

    def test_split_args_and_kwargs(self):
        ft1 = operators.FromTask("task1", "key1")
        ft2 = operators.FromTask("task1")
        args, x_args, kwargs, x_kwargs = operators.split_args_kwargs(
            func_args=[1, ft1, "a"], func_kwargs={"x": 1, "key2": ft2}
        )
        self.assertEqual(args, [1, "a"])
        self.assertEqual(kwargs, {"x": 1})
        self.assertEqual(x_args, {"1": {"task": "task1", "key": "key1"}})
        self.assertEqual(x_kwargs, {"key2": {"task": "task1", "key": "return_value"}})

    @patch("gaiaflow.core.operators.ExternalPythonOperator")
    def test_create_dev_task(self, mock_ext_op):
        op = operators.DevTaskOperator(
            task_id="devtask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image=None,
            secrets=[],
            env_vars={},
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.DEV,
        )
        op.create_task()
        args, kwargs = mock_ext_op.call_args
        self.assertEqual(kwargs["op_kwargs"]["func_path"], "mod:fn")
        self.assertEqual(kwargs["op_kwargs"]["args"], [1])
        self.assertEqual(
            kwargs["op_kwargs"]["kwargs"], {"params": {"x": "y"}, "test": "123"}
        )
        self.assertEqual(kwargs["expect_airflow"], False)
        self.assertEqual(kwargs["expect_pendulum"], False)

    def test_create_prod_local_task_no_image(self):
        with self.assertRaises(ValueError):
            operators.ProdLocalTaskOperator(
                task_id="prodlocaltask",
                func_path="mod:fn",
                func_args=[1],
                func_kwargs={"test": "123"},
                image=None,
                secrets=[],
                env_vars={},
                retries=2,
                params={"x": "y"},
                mode=GaiaflowMode.PROD_LOCAL,
            ).create_task()

    @patch("gaiaflow.core.operators.KubernetesPodOperator")
    def test_create_prod_local_task(self, mock_ext_op):
        op = operators.ProdLocalTaskOperator(
            task_id="prodlocaltask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image="random_image:v1",
            secrets=[],
            env_vars={},
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.PROD_LOCAL,
        )
        op.create_task()
        args, kwargs = mock_ext_op.call_args
        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["cmds"], ["python", "-m", "runner"])
        self.assertEqual(
            kwargs["env_vars"],
            {
                "MODE": "prod_local",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "http://192.168.49.1:5000",
                "MLFLOW_S3_ENDPOINT_URL": "http://192.168.49.1:9000",
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )
        self.assertEqual(kwargs["params"], {"x": "y"})
        self.assertEqual(kwargs["in_cluster"], False)

        with patch("platform.system", return_value="Windows"):
            op.create_task()
        args, kwargs = mock_ext_op.call_args

        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["cmds"], ["python", "-m", "runner"])
        self.assertEqual(
            kwargs["env_vars"],
            {
                "MODE": "prod_local",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "http://host.docker.internal:5000",
                "MLFLOW_S3_ENDPOINT_URL": "http://host.docker.internal:9000",
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )
        self.assertEqual(kwargs["params"], {"x": "y"})
        self.assertEqual(kwargs["in_cluster"], False)

    def test_create_task_unknown_profile_raises(self):
        op = operators.ProdLocalTaskOperator(
            task_id="prodlocaltask",
            func_path="mod:fn",
            func_args=[],
            func_kwargs={},
            image="img",
            secrets=[],
            env_vars={},
            retries=1,
            params={"resource_profile": "unknown"},
            mode=GaiaflowMode.PROD_LOCAL,
        )
        with self.assertRaises(ValueError):
            op.create_task()

    @patch("gaiaflow.core.operators.KubernetesPodOperator")
    def test_create_prod_task(self, mock_ext_op):
        op = operators.ProdTaskOperator(
            task_id="prodtask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image="random_image:v1",
            secrets=["my-secret"],
            env_vars={},
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.PROD,
        )
        op.create_task()
        args, kwargs = mock_ext_op.call_args
        print(args, kwargs)
        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["cmds"], ["python", "-m", "runner"])
        self.assertEqual(
            kwargs["env_vars"],
            {
                "MODE": "prod",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "http://192.168.49.1:5000",
                "MLFLOW_S3_ENDPOINT_URL": "http://192.168.49.1:9000",
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )
        self.assertEqual(kwargs["params"], {"x": "y"})
        self.assertEqual(kwargs["in_cluster"], True)
        self.assertEqual(
            kwargs["env_from"][0].to_dict(),
            {
                "config_map_ref": None,
                "prefix": None,
                "secret_ref": {"name": "my-secret", "namespace": None},
            },
        )
        # self.assertEqual(
        #     kwargs["container_resources"].to_dict(),
        #     {
        #         "claims": None,
        #         "limits": {"cpu": "500m", "memory": "1Gi"},
        #         "requests": {"cpu": "250m", "memory": "512Mi"},
        #     },
        # )

    @patch("gaiaflow.core.operators.KubernetesPodOperator")
    def test_create_prod_task_windows(self, mock_ext_op):
        op = operators.ProdTaskOperator(
            task_id="prodtask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image="random_image:v1",
            secrets=["my-secret"],
            env_vars={},
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.PROD,
        )
        with patch("platform.system", return_value="Windows"):
            op.create_task()
        args, kwargs = mock_ext_op.call_args

        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["cmds"], ["python", "-m", "runner"])
        self.assertEqual(
            kwargs["env_vars"],
            {
                "MODE": "prod",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "http://host.docker.internal:5000",
                "MLFLOW_S3_ENDPOINT_URL": "http://host.docker.internal:9000",
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )
        self.assertEqual(kwargs["params"], {"x": "y"})
        self.assertEqual(kwargs["in_cluster"], True)

    @patch("gaiaflow.core.operators.KubernetesPodOperator")
    def test_create_prod_task_custom_env_vars(self, mock_ext_op):
        op = operators.ProdTaskOperator(
            task_id="prodtask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image="random_image:v1",
            secrets=["my-secret"],
            env_vars={"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY":
                "test2", "MINIKUBE_GATEWAY": "test3"},
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.PROD,
        )
        op.create_task()
        args, kwargs = mock_ext_op.call_args
        print(args, kwargs)
        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["cmds"], ["python", "-m", "runner"])
        self.assertEqual(
            kwargs["env_vars"],
            {
                "MODE": "prod",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "http://test3:5000",
                "MLFLOW_S3_ENDPOINT_URL": "http://test3:9000",
                "AWS_ACCESS_KEY_ID": "test",
                "AWS_SECRET_ACCESS_KEY": "test2",
                "MINIKUBE_GATEWAY": "test3",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )
        self.assertEqual(kwargs["params"], {"x": "y"})
        self.assertEqual(kwargs["in_cluster"], True)
        self.assertEqual(
            kwargs["env_from"][0].to_dict(),
            {
                "config_map_ref": None,
                "prefix": None,
                "secret_ref": {"name": "my-secret", "namespace": None},
            },
        )
        # self.assertEqual(
        #     kwargs["container_resources"].to_dict(),
        #     {
        #         "claims": None,
        #         "limits": {"cpu": "500m", "memory": "1Gi"},
        #         "requests": {"cpu": "250m", "memory": "512Mi"},
        #     },
        # )

    @patch("gaiaflow.core.operators.DockerOperator")
    def test_create_dev_docker_task(self, mock_ext_op):
        op = operators.DockerTaskOperator(
            task_id="devdockertask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image="random_image:v1",
            secrets=[],
            env_vars={},
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.DEV_DOCKER,
        )
        op.create_task()
        args, kwargs = mock_ext_op.call_args
        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["command"], ["python", "-m", "runner"])
        self.assertEqual(kwargs["docker_url"], "unix://var/run/docker.sock")
        self.assertEqual(kwargs["retrieve_output"], True)
        self.assertEqual(kwargs["retrieve_output_path"], "/tmp/script.out")
        self.assertEqual(
            kwargs["environment"],
            {
                "MODE": "dev_docker",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "http://mlflow:5000",
                "MLFLOW_S3_ENDPOINT_URL": "http://minio:9000",
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )

    @patch("gaiaflow.core.operators.DockerOperator")
    def test_create_dev_docker_task_with_custom_env_vars(self, mock_ext_op):
        op = operators.DockerTaskOperator(
            task_id="devdockertask",
            func_path="mod:fn",
            func_args=[1],
            func_kwargs={"test": "123"},
            image="random_image:v1",
            secrets=[],
            env_vars={
                "MLFLOW_TRACKING_URI": "test",
                "MLFLOW_S3_ENDPOINT_URL": "test2",
                "AWS_ACCESS_KEY_ID": "test3",
                "AWS_SECRET_ACCESS_KEY": "test4"
            },
            retries=2,
            params={"x": "y"},
            mode=GaiaflowMode.DEV_DOCKER,
        )
        op.create_task()
        args, kwargs = mock_ext_op.call_args
        self.assertEqual(kwargs["image"], "random_image:v1")
        self.assertEqual(kwargs["command"], ["python", "-m", "runner"])
        self.assertEqual(kwargs["docker_url"], "unix://var/run/docker.sock")
        self.assertEqual(kwargs["retrieve_output"], True)
        self.assertEqual(kwargs["retrieve_output_path"], "/tmp/script.out")
        self.assertEqual(
            kwargs["environment"],
            {
                "MODE": "dev_docker",
                "PARAMS_X": "{{ params.x }}",
                "MLFLOW_TRACKING_URI": "test",
                "MLFLOW_S3_ENDPOINT_URL": "test2",
                "AWS_ACCESS_KEY_ID": "test3",
                "AWS_SECRET_ACCESS_KEY": "test4",
                "FUNC_PATH": "mod:fn",
                "FUNC_ARGS": "[1]",
                "FUNC_KWARGS": '{"test": "123"}',
            },
        )
