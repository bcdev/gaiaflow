import json
import platform
from datetime import datetime

from airflow.providers.cncf.kubernetes.operators.pod import \
    KubernetesPodOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.standard.operators.python import ExternalPythonOperator
from kubernetes.client import V1ResourceRequirements

from gaiaflow.constants import (DEFAULT_MINIO_AWS_ACCESS_KEY_ID,
                                DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY,
                                RESOURCE_PROFILES)

from .utils import build_env_from_secrets, inject_params_as_env_vars


class FromTask:
    def __init__(self, task: str, key: str = "return_value"):
        self.task = task
        self.key = key

    def to_dict(self) -> dict:
        return {"task": self.task, "key": self.key}


def split_args_kwargs(func_args=None, func_kwargs=None):
    func_args = func_args or []
    func_kwargs = func_kwargs or {}

    user_args = []
    xcom_args = {}
    for idx, arg in enumerate(func_args):
        if isinstance(arg, FromTask):
            xcom_args[str(idx)] = arg.to_dict()
        else:
            user_args.append(arg)

    user_kwargs = {}
    xcom_kwargs = {}
    for k, v in func_kwargs.items():
        if isinstance(v, FromTask):
            xcom_kwargs[k] = v.to_dict()
        else:
            user_kwargs[k] = v

    return user_args, xcom_args, user_kwargs, xcom_kwargs


class BaseTaskOperator:
    def __init__(
        self,
        task_id: str,
        func_path: str,
        func_args: list,
        func_kwargs: dict,
        image: str | None,
        secrets: list[str] | None,
        env_vars: dict,
        retries: int,
        params: dict,
        mode: str,
    ):
        self.task_id = task_id
        self.func_path = func_path
        self.image = image
        self.secrets = secrets
        self.env_vars = env_vars
        self.retries = retries
        self.params = params
        self.mode = mode

        (
            self.func_args,
            self.func_args_from_tasks,
            self.func_kwargs,
            self.func_kwargs_from_tasks,
        ) = split_args_kwargs(func_args, func_kwargs)

        self.func_args_from_tasks = self.func_args_from_tasks or {}
        self.func_kwargs_from_tasks = self.func_kwargs_from_tasks or {}

        self.func_kwargs_from_tasks = {
            k: (v if isinstance(v, dict) and "task" in v else FromTask(v).to_dict())
            for k, v in self.func_kwargs_from_tasks.items()
        }

    def create_task(self):
        raise NotImplementedError

    def _resolve_xcom_value(self, from_task_config):
        task_id = from_task_config["task"]
        key = from_task_config.get("key", "return_value")

        if key == "return_value":
            return f"{{{{ ti.xcom_pull(task_ids='{task_id}') }}}}"
        return f"{{{{ ti.xcom_pull(task_ids='{task_id}')['{key}'] }}}}"

    def resolve_args_kwargs(self):
        resolved_args = self.func_args or []
        resolved_kwargs = self.func_kwargs or {}

        for index_str, from_task_config in (self.func_args_from_tasks or {}).items():
            index = int(index_str)
            while len(resolved_args) <= index:
                resolved_args.append(None)
            resolved_args[index] = self._resolve_xcom_value(from_task_config)

        for k, from_task_config in (self.func_kwargs_from_tasks or {}).items():
            resolved_kwargs[k] = self._resolve_xcom_value(from_task_config)

        return resolved_args, resolved_kwargs

    def create_func_env_vars(self):
        final_args, final_kwargs = self.resolve_args_kwargs()
        return {
            "FUNC_PATH": self.func_path,
            "FUNC_ARGS": json.dumps(final_args),
            "FUNC_KWARGS": json.dumps(final_kwargs),
        }


class DevTaskOperator(BaseTaskOperator):
    def create_task(self):
        from gaiaflow.core.runner import run

        args, kwargs = self.resolve_args_kwargs()
        kwargs["params"] = self.params
        op_kwargs = {"func_path": self.func_path, "args": args, "kwargs": kwargs}

        return ExternalPythonOperator(
            task_id=self.task_id,
            python="/home/airflow/.local/share/mamba/envs/default_user_env/bin/python",
            python_callable=run,
            op_kwargs=op_kwargs,
            do_xcom_push=True,
            retries=self.retries,
        )


class ProdLocalTaskOperator(BaseTaskOperator):
    def create_task(self):
        if not self.image:
            raise ValueError("Docker image must be provided for Kubernetes tasks.")

        os_type = platform.system().lower()

        minikube_gateway = "NOTSET"

        if os_type == "linux":
            minikube_gateway = "192.168.49.1"
        elif os_type == "windows":
            minikube_gateway = "host.docker.internal"

        # If the user provides a gateway, that takes precedence.
        if "MINIKUBE_GATEWAY" in self.env_vars:
            minikube_gateway = self.env_vars.get("MINIKUBE_GATEWAY")

        mlflow_env_vars = {
            "MLFLOW_TRACKING_URI": f"http://{minikube_gateway}:5000",
            "MLFLOW_S3_ENDPOINT_URL": f"http://{minikube_gateway}:9000",
        }

        aws_access_key_id = DEFAULT_MINIO_AWS_ACCESS_KEY_ID
        if "AWS_ACCESS_KEY_ID" in self.env_vars:
            aws_access_key_id = self.env_vars.pop("AWS_ACCESS_KEY_ID")

        aws_secret_access_key = DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY
        if "AWS_SECRET_ACCESS_KEY" in self.env_vars:
            aws_secret_access_key = self.env_vars.pop("AWS_SECRET_ACCESS_KEY")

        minio_env_vars = {
            "AWS_ACCESS_KEY_ID": aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
        }

        all_env_vars = {
            "MODE": self.mode.value,
            **self.env_vars,
            **inject_params_as_env_vars(self.params),
            **mlflow_env_vars,
            **minio_env_vars,
            **self.create_func_env_vars(),
        }
        env_from = build_env_from_secrets(self.secrets or [])

        profile_name = self.params.get("resource_profile", "low")
        profile = RESOURCE_PROFILES.get(profile_name)
        if profile is None:
            raise ValueError(f"Unknown resource profile: {profile_name}")

        resources = V1ResourceRequirements(
            requests={
                "cpu": profile["request_cpu"],
                "memory": profile["request_memory"],
            },
            limits={
                "cpu": profile["limit_cpu"],
                "memory": profile["limit_memory"],
                # "gpu": profile.get["limit_gpu"],
            },
        )

        return KubernetesPodOperator(
            task_id=self.task_id,
            image=self.image,
            cmds=["python", "-m", "runner"],
            env_vars=all_env_vars,
            env_from=env_from,
            get_logs=True,
            is_delete_operator_pod=True,
            log_events_on_failure=True,
            in_cluster=(self.mode == self.mode.PROD),
            do_xcom_push=True,
            retries=self.retries,
            params=self.params,
            container_resources=resources,
        )


class ProdTaskOperator(ProdLocalTaskOperator):
    """"""


class DockerTaskOperator(ProdLocalTaskOperator):
    def create_task(self):
        mlflow_tracking_uri = "http://mlflow:5000"
        if "MLFLOW_TRACKING_URI" in self.env_vars:
            mlflow_tracking_uri = self.env_vars.pop("MLFLOW_TRACKING_URI")

        mlflow_s3_endpoint_url = "http://minio:9000"
        if "MLFLOW_S3_ENDPOINT_URL" in self.env_vars:
            mlflow_s3_endpoint_url = self.env_vars.pop("MLFLOW_S3_ENDPOINT_URL")

        mlflow_env_vars = {
            "MLFLOW_TRACKING_URI": mlflow_tracking_uri,
            "MLFLOW_S3_ENDPOINT_URL": mlflow_s3_endpoint_url,
        }

        aws_access_key_id = DEFAULT_MINIO_AWS_ACCESS_KEY_ID
        if "AWS_ACCESS_KEY_ID" in self.env_vars:
            aws_access_key_id = self.env_vars.pop("AWS_ACCESS_KEY_ID")

        aws_secret_access_key = DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY
        if "AWS_SECRET_ACCESS_KEY" in self.env_vars:
            aws_secret_access_key = self.env_vars.pop("AWS_SECRET_ACCESS_KEY")

        minio_env_vars = {
            "AWS_ACCESS_KEY_ID": aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
        }

        combined_env = {
            "MODE": self.mode.value,
            **self.create_func_env_vars(),
            **self.env_vars,
            **inject_params_as_env_vars(self.params),
            **mlflow_env_vars,
            **minio_env_vars,
        }

        safe_image_name = self.image.replace(":", "_").replace("/", "_")

        return DockerOperator(
            task_id=self.task_id,
            image=self.image,
            container_name=safe_image_name
            + "_"
            + self.task_id
            + "_"
            + datetime.now().strftime("%Y%m%d%H%M%S")
            + "_container",
            api_version="auto",
            auto_remove="success",
            command=["python", "-m", "runner"],
            docker_url="unix://var/run/docker.sock",
            # docker_url="tcp://host.docker.internal:2375",
            environment=combined_env,
            network_mode="docker-compose_ml-network",
            mount_tmp_dir=False,
            do_xcom_push=True,
            retrieve_output=True,
            retrieve_output_path="/tmp/script.out",
            xcom_all=False,
        )
