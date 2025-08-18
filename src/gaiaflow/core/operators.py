import json
import platform
from datetime import datetime

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.standard.operators.python import ExternalPythonOperator
from kubernetes.client import V1ResourceRequirements

from gaiaflow.constants import (
    DEFAULT_MINIO_AWS_ACCESS_KEY_ID,
    DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY,
    RESOURCE_PROFILES,
)

from .utils import (
    build_env_from_secrets,
    build_env_vars,
    build_xcom_templates,
    inject_params_as_env_vars,
    XComConfig,
)


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
        image: str,
        secrets: list[str],
        env_vars: dict,
        retries: int,
        params: dict,
        environment: str,
    ):
        self.task_id = task_id
        self.func_path = func_path
        self.image = image
        self.secrets = secrets
        self.env_vars = env_vars
        self.retries = retries
        self.params = params
        self.environment = environment

        (
            self.func_args,
            self.func_args_from_tasks,
            self.func_kwargs,
            self.func_kwargs_from_tasks,
        ) = split_args_kwargs(func_args, func_kwargs)

        self.func_args_from_tasks = self.func_args_from_tasks or {}
        self.func_kwargs_from_tasks = self.func_kwargs_from_tasks or {}

        self.func_kwargs_from_tasks = {
            k: (v if isinstance(v, dict) and "task" in v else XComConfig(v).to_dict())
            for k, v in self.func_kwargs_from_tasks.items()
        }

    def create_task(self):
        raise NotImplementedError


class DevTaskOperator(BaseTaskOperator):
    def create_task(self):
        from gaiaflow.core.runner import run

        op_kwargs = {
            "func_path": self.func_path,
            "args": self._resolve_xcom_args(),
            "kwargs": self._resolve_xcom_kwargs(),
        }

        return ExternalPythonOperator(
            task_id=self.task_id,
            python="/home/airflow/.local/share/mamba/envs/default_user_env/bin/python",
            python_callable=run,
            op_kwargs=op_kwargs,
            do_xcom_push=True,
            retries=self.retries,
            params=self.params,
        )

    def _resolve_xcom_kwargs(self):
        resolved_kwargs = self.func_kwargs or {}

        if self.func_kwargs_from_tasks:
            for arg_key, from_task_config in self.func_kwargs_from_tasks.items():
                if isinstance(from_task_config, dict) and "task" in from_task_config:
                    task_id = from_task_config["task"]
                    key = from_task_config.get("key", "return_value")

                    if key == "return_value":
                        template = f"{{{{ ti.xcom_pull(task_ids='{task_id}') }}}}"
                    else:
                        template = (
                            f"{{{{ ti.xcom_pull(task_ids='{task_id}')['{key}'] }}}}"
                        )

                    resolved_kwargs[arg_key] = template

        return resolved_kwargs

    def _resolve_xcom_args(self):
        resolved_args = self.func_args or []

        if self.func_args_from_tasks:
            for index_str, from_task_config in self.func_args_from_tasks.items():
                index = int(index_str)

                while len(resolved_args) <= index:
                    resolved_args.append(None)

                if isinstance(from_task_config, dict) and "task" in from_task_config:
                    task_id = from_task_config["task"]
                    key = from_task_config.get("key", "return_value")

                    if key == "return_value":
                        template = f"{{{{ ti.xcom_pull(task_ids='{task_id}') }}}}"
                    else:
                        template = (
                            f"{{{{ ti.xcom_pull(task_ids='{task_id}')['{key}'] }}}}"
                        )

                    resolved_args[index] = template

        return resolved_args


class ProdLocalTaskOperator(BaseTaskOperator):
    def create_task(self):
        if not self.image:
            raise ValueError("Docker image must be provided for Kubernetes tasks.")

        xcom_kwargs_pull = build_xcom_templates(self.func_kwargs_from_tasks)
        xcom_args_pull = build_xcom_templates(self.func_args_from_tasks)

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

        env_vars = build_env_vars(
            # func_path=self.func_path,
            # func_args=self.func_args,
            # func_kwargs=self.func_kwargs,
            # func_args_from_tasks=self.func_args_from_tasks,
            # func_kwargs_from_tasks=self.func_kwargs_from_tasks,
            xcom_args_pull_results=xcom_args_pull,
            xcom_kwargs_pull_results=xcom_kwargs_pull,
            custom_env_vars=self.env_vars,
            env=self.environment.value,
        )

        all_env_vars = {
            **inject_params_as_env_vars(self.params),
            **env_vars,
            **mlflow_env_vars,
            **minio_env_vars,
            **self._create_env_vars_with_xcom()
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
            in_cluster=(self.environment == self.environment.PROD),
            do_xcom_push=True,
            retries=self.retries,
            params=self.params,
            container_resources=resources,
        )

    def _create_env_vars_with_xcom(self):
        env_vars = {
            "FUNC_PATH": self.func_path,
        }

        base_args = list(self.func_args) if self.func_args else []
        base_kwargs = dict(self.func_kwargs) if self.func_kwargs else {}

        final_args = base_args.copy()
        if self.func_args_from_tasks:
            sorted_args_from_tasks = sorted(
                self.func_args_from_tasks.items(), key=lambda x: int(x[0])
            )

            for index_str, from_task_config in sorted_args_from_tasks:
                index = int(index_str)

                while len(final_args) <= index:
                    final_args.append(None)

                task_id = from_task_config["task"]
                key = from_task_config.get("key", "return_value")

                if key == "return_value":
                    template = f"{{{{ ti.xcom_pull(task_ids='{task_id}') }}}}"
                else:
                    template = f"{{{{ ti.xcom_pull(task_ids='{task_id}')['{key}'] }}}}"

                final_args[index] = template

        final_kwargs = base_kwargs.copy()
        if self.func_kwargs_from_tasks:
            for arg_key, from_task_config in self.func_kwargs_from_tasks.items():
                task_id = from_task_config["task"]
                key = from_task_config.get("key", "return_value")

                if key == "return_value":
                    template = f"{{{{ ti.xcom_pull(task_ids='{task_id}') }}}}"
                else:
                    template = f"{{{{ ti.xcom_pull(task_ids='{task_id}')['{key}'] }}}}"

                final_kwargs[arg_key] = template

        env_vars["FUNC_ARGS"] = json.dumps(final_args)
        env_vars["FUNC_KWARGS"] = json.dumps(final_kwargs)

        return env_vars


class ProdTaskOperator(ProdLocalTaskOperator):
    """"""


class DockerTaskOperator(ProdLocalTaskOperator):
    def create_task(self):
        """"""
        # xcom_kwargs_pull = build_xcom_templates(self.func_kwargs_from_tasks)
        # xcom_args_pull = build_xcom_templates(self.func_args_from_tasks)

        # environment = {
        #     "FUNC_PATH": self.func_path,
        #     "FUNC_ARGS": json.dumps(self.func_args or []),
        #     "FUNC_KWARGS": json.dumps(self.func_kwargs or {}),
        #     "XCOM_PULL_KWARGS": json.dumps(self.func_kwargs_from_tasks or {}),
        #     "XCOM_PULL_ARGS": json.dumps(self.func_args_from_tasks or []),
        #     "XCOM_PULL_ARGS_RESULTS": json.dumps(xcom_args_pull or {}),
        #     "XCOM_PULL_KWARGS_RESULTS": json.dumps(xcom_kwargs_pull or {}),
        # }

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
            "ENV": self.environment.value,
            **self._create_env_vars_with_xcom(),
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
            environment=combined_env,
            network_mode="docker-compose_ml-network",
            mount_tmp_dir=False,
            do_xcom_push=True,
            retrieve_output=True,
            retrieve_output_path="/tmp/script.out",
            xcom_all=False,
        )
