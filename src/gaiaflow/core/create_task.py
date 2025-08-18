# import json
# from enum import Enum
# from typing import Optional, List
#
# from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
# from airflow.providers.standard.operators.python import PythonOperator
# from kubernetes.client import V1EnvFromSource, V1SecretReference
#
#
# class GaiaflowMode(Enum):
#     DEV = "dev"
#     PROD_LOCAL = "prod_local"
#     PROD = "prod"
#
#
# # TASK_REGISTRY = {
# #     GaiaflowMode.DEV: _create_python_task,
# #     GaiaflowMode.PROD: _create_kubernetes_task,
# #     GaiaflowMode.PROD_LOCAL: _create_kubernetes_task,
# # }
#
#
# class XComConfig:
#     def __init__(self, task: str, key: str = "return_value"):
#         self.task = task
#         self.key = key
#
#     def to_dict(self) -> dict:
#         return {"task": self.task, "key": self.key}
#
# def is_xcom_config_dict(val):
#     return isinstance(val, dict) and "task" in val and "key" in val
#
#
# def create_task(
#     task_id: str,
#     func_path: str,
#     func_kwargs: dict = None,
#     func_args: list = None,
#     image: str = None,
#     env: str = "dev",
#     func_args_from_tasks: dict = None,
#     func_kwargs_from_tasks: dict = None,
#     secrets: list = None,
#     env_vars: dict = None,
#     retries: int = 3,
#     dag = None,
#     params = None,
# ):
#     """
#     Create an Airflow task that can run in different environments.
#
#     Args:
#         task_id: Unique task identifier
#         func_path: Python import path to the function (e.g.,'my.module:myfunction')
#         func_args: Static positional arguments to pass to the function
#         func_kwargs: Static keyword arguments to pass to the function
#         image: Docker image for production and prod-like environments
#         env: GaiaflowMode to run in ('dev', 'prod_local', 'prod')
#         func_kwargs_from_tasks: Dynamic keyword arguments from other tasks via XCom
#         secrets: List of Kubernetes secrets to mount
#         env_vars: GaiaflowMode variables for the task for production and prod-like environments
#         retries: Number of retries on failure
#         func_args_from_tasks:
#     """
#
#     try:
#         environment = GaiaflowMode(env)
#     except ValueError:
#         raise ValueError(
#             f"env must be one of {[e.value for e in GaiaflowMode]}, got '{env}'"
#         )
#
#     if func_kwargs is None:
#         func_kwargs = {}
#
#     if func_args is None:
#         func_args = []
#
#     if env_vars is None:
#         env_vars = {}
#
#     if dag and hasattr(dag, "params"):
#         dag_params = dag.params or {}
#     else:
#         dag_params = {}
#
#     combined_params = {**dag_params, **(params or {})}
#     # if combined_params:
#     #     func_kwargs["params"] = combined_params
#
#     func_kwargs_from_tasks_dict = {}
#     if func_kwargs_from_tasks:
#         func_kwargs_from_tasks_dict = {
#             k: (v if is_xcom_config_dict(v) else XComConfig(
#                 v).to_dict())
#             for k, v in func_kwargs_from_tasks.items()
#         }
#
#     # func_args_from_tasks_dict = {}
#     # if func_args_from_tasks:
#     #     func_args_from_tasks_dict = {
#     #         k: (v if is_xcom_config_dict(v) else XComConfig(v).to_dict())
#     #         for k, v in func_args_from_tasks.items()
#     #     }
#
#
#     if environment == GaiaflowMode.DEV:
#         return _create_python_task(
#             task_id=task_id,
#             func_path=func_path,
#             func_args=func_args,
#             func_kwargs=func_kwargs,
#             func_kwargs_from_tasks=func_kwargs_from_tasks_dict,
#             func_args_from_tasks=func_args_from_tasks,
#             xcom_push=True,
#             retries=retries,
#             params=combined_params,
#         )
#
#     elif environment in [GaiaflowMode.PROD, GaiaflowMode.PROD_LOCAL]:
#         if not image:
#             raise ValueError(f"Docker image is required for {env} environment")
#
#         return _create_kubernetes_task(
#             task_id=task_id,
#             func_path=func_path,
#             func_args=func_args,
#             func_kwargs=func_kwargs,
#             func_kwargs_from_tasks=func_kwargs_from_tasks_dict,
#             func_args_from_tasks=func_args_from_tasks,
#             image=image,
#             secrets=secrets,
#             env_vars=env_vars,
#             xcom_push=True,
#             retries=retries,
#             in_cluster=(environment == GaiaflowMode.PROD),
#             params=combined_params
#         )
#
# def _create_python_task(
#     task_id: str,
#     func_path: str,
#     func_args: list,
#     func_kwargs: dict,
#     func_args_from_tasks: dict,
#     func_kwargs_from_tasks: dict,
#     xcom_push: bool,
#     retries: int,
#     params: dict
# ) -> PythonOperator:
#     from .runner import run
#
#     full_kwargs = {
#         "func_path": func_path,
#         "args": func_args,
#         "kwargs": func_kwargs,
#     }
#
#     if func_kwargs_from_tasks:
#         full_kwargs["xcom_pull_kwargs"] = func_kwargs_from_tasks
#
#     if func_args_from_tasks:
#         full_kwargs["xcom_pull_args"] = func_args_from_tasks
#
#     return PythonOperator(
#         task_id=task_id,
#         python_callable=run,
#         op_kwargs=full_kwargs,
#         do_xcom_push=xcom_push,
#         retries=retries,
#         params=params
#     )
#
# def _inject_params_as_env_vars(params: dict[str, str]) -> dict[str, str]:
#     return {
#         f"PARAMS_{k.upper()}": f"{{{{ params.{k} }}}}"
#         for k in params
#     }
#
# def _create_kubernetes_task(
#     task_id: str,
#     func_path: str,
#     func_args: list,
#     func_kwargs: dict,
#     func_kwargs_from_tasks: dict,
#     func_args_from_tasks: dict,
#     image: str,
#     secrets: Optional[List[str]],
#     env_vars: dict,
#     xcom_push: bool,
#     retries: int,
#     in_cluster: bool,
#         params: dict,
# ) -> KubernetesPodOperator:
#
#     if func_kwargs_from_tasks:
#         xcom_kwargs_pull_results = _build_xcom_templates(func_kwargs_from_tasks)
#     else:
#         xcom_kwargs_pull_results= {}
#     if func_args_from_tasks:
#         xcom_args_pull_results = _build_args_xcom_templates(func_args_from_tasks)
#     else:
#         xcom_args_pull_results = {}
#
#     task_env_vars = _build_env_vars(
#         func_path=func_path,
#         func_args=func_args,
#         func_kwargs=func_kwargs,
#         func_args_from_tasks=func_args_from_tasks,
#         func_kwargs_from_tasks=func_kwargs_from_tasks,
#         xcom_args_pull_results=xcom_args_pull_results,
#         xcom_kwargs_pull_results=xcom_kwargs_pull_results,
#         custom_env_vars=env_vars,
#     )
#
#     env_from = _build_env_from_secrets(secrets) if secrets else None
#
#     return KubernetesPodOperator(
#         task_id=task_id,
#         image=image,
#         cmds=["python", "-m", "gaiaflow.core.runner"],
#         env_vars={**_inject_params_as_env_vars(params), **task_env_vars},
#         params=params,
#         env_from=env_from,
#         get_logs=True,
#         is_delete_operator_pod=True,
#         log_events_on_failure=True,
#         in_cluster=in_cluster,
#         do_xcom_push=xcom_push,
#         retries=retries,
#     )
#
#
# def _build_xcom_templates(func_from_tasks: dict) -> dict:
#     xcom_pull_results = {}
#
#     for arg_key, pull_config in func_from_tasks.items():
#         source_task = pull_config["task"]
#         key = pull_config.get("key", "return_value")
#         xcom_pull_results[source_task] = (
#             "{{ ti.xcom_pull(task_ids='" + source_task + "', key='" + key + "') }}"
#         )
#
#     return xcom_pull_results
#
# def _build_args_xcom_templates(func_from_tasks: dict) -> dict:
#     xcom_pull_results = {}
#
#     for arg_key, pull_config in func_from_tasks.items():
#         source_task = pull_config["task"]
#
#         key = "return_value"
#         xcom_pull_results[source_task] = (
#             "{{ ti.xcom_pull(task_ids='" + source_task + "', key='" + key + "') }}"
#         )
#
#     return xcom_pull_results
#
#
# def _build_env_vars(
#     func_path: str,
#     func_kwargs: dict,
#     func_args: list,
#     func_args_from_tasks: dict,
#     func_kwargs_from_tasks: dict,
#     xcom_kwargs_pull_results: dict,
#     xcom_args_pull_results: dict,
#     custom_env_vars: dict,
# ) -> dict:
#     print("DEBUG: xcom_args_pull_results:", xcom_args_pull_results)
#     print("DEBUG: xcom_kwargs_pull_results:", xcom_kwargs_pull_results)
#
#     default_env_vars = {
#         "FUNC_PATH": func_path,
#         "FUNC_ARGS": json.dumps(func_args),
#         "FUNC_KWARGS": json.dumps(func_kwargs),
#         "XCOM_PULL_ARGS": json.dumps(func_args_from_tasks),
#         "XCOM_PULL_KWARGS": json.dumps(func_kwargs_from_tasks),
#         "XCOM_PULL_ARGS_RESULTS": json.dumps(xcom_args_pull_results),
#         "XCOM_PULL_KWARGS_RESULTS": json.dumps(xcom_kwargs_pull_results),
#         "ENV": "prod",
#     }
#
#     print(
#         "DEBUG: XCOM_PULL_ARGS_RESULTS env var:",
#         default_env_vars["XCOM_PULL_ARGS_RESULTS"],
#     )
#     print(
#         "DEBUG: XCOM_PULL_KWARGS_RESULTS env var:",
#         default_env_vars["XCOM_PULL_KWARGS_RESULTS"],
#     )
#     final_env_vars = {**default_env_vars, **custom_env_vars}
#
#     return final_env_vars
#
#
# def _build_env_from_secrets(secrets: List[str]) -> List[V1EnvFromSource]:
#     return [
#         V1EnvFromSource(secret_ref=V1SecretReference(name=secret)) for secret in secrets
#     ]


from enum import Enum

from .operators import (
    DevTaskOperator,
    DockerTaskOperator,
    ProdLocalTaskOperator,
    ProdTaskOperator,
)
from .utils import XComConfig


class GaiaflowMode(Enum):
    DEV = "dev"
    PROD_LOCAL = "prod_local"
    PROD = "prod"
    DEV_DOCKER = "dev_docker"


OPERATOR_MAP = {
    GaiaflowMode.DEV: DevTaskOperator,
    GaiaflowMode.PROD: ProdLocalTaskOperator,
    GaiaflowMode.PROD_LOCAL: ProdTaskOperator,
    GaiaflowMode.DEV_DOCKER: DockerTaskOperator,
}

# TODO: Use kwargs and args as a tuple to reduce verbosity
def create_task(
    task_id: str,
    func_path: str,
    func_kwargs: dict | None = None,
    func_args: list | None = None,
    image: str | None = None,
    env: str = "dev",
    secrets: list | None = None,
    env_vars: dict | None = None,
    retries: int = 3,
    dag=None,
    params=None,
):
    try:
        environment = GaiaflowMode(env)
    except ValueError:
        raise ValueError(
            f"env must be one of {[e.value for e in GaiaflowMode]}, got '{env}'"
        )

    func_args = func_args or []
    func_kwargs = func_kwargs or {}
    if env_vars is None:
        env_vars = {}
    # env_vars = env_vars or {}

    # func_args_from_tasks = func_args_from_tasks or {}
    # func_kwargs_from_tasks = func_kwargs_from_tasks or {}

    dag_params = getattr(dag, "params", {}) if dag else {}
    combined_params = {**dag_params, **(params or {})}

    # normalized_kwargs_from_tasks = {
    #     k: (v if isinstance(v, dict) and "task" in v else XComConfig(v).to_dict())
    #     for k, v in func_kwargs_from_tasks.items()
    # }

    operator_cls = OPERATOR_MAP.get(environment)
    if not operator_cls:
        raise ValueError(f"No task creation operator defined for {environment}")

    operator = operator_cls(
        task_id=task_id,
        func_path=func_path,
        func_args=func_args,
        func_kwargs=func_kwargs,
        # func_kwargs_from_tasks=normalized_kwargs_from_tasks,
        # func_args_from_tasks=func_args_from_tasks,
        image=image,
        secrets=secrets,
        env_vars=env_vars,
        retries=retries,
        params=combined_params,
        environment=environment,
    )

    return operator.create_task()
