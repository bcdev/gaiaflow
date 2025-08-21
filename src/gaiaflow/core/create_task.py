from enum import Enum

from .operators import (DevTaskOperator, DockerTaskOperator,
                        ProdLocalTaskOperator, ProdTaskOperator)


class GaiaflowMode(Enum):
    DEV = "dev"
    DEV_DOCKER = "dev_docker"
    PROD_LOCAL = "prod_local"
    PROD = "prod"


OPERATOR_MAP = {
    GaiaflowMode.DEV: DevTaskOperator,
    GaiaflowMode.DEV_DOCKER: DockerTaskOperator,
    GaiaflowMode.PROD_LOCAL: ProdLocalTaskOperator,
    GaiaflowMode.PROD: ProdTaskOperator,
}


def create_task(
    task_id: str,
    func_path: str,
    func_kwargs: dict | None = None,
    func_args: list | None = None,
    image: str | None = None,
    mode: str = "dev",
    secrets: list | None = None,
    env_vars: dict | None = None,
    retries: int = 3,
    dag=None,
):
    """It is a high-level abstraction on top of Apache Airflow operators.

    It allows you to define tasks for your DAGs in a uniform, environment-aware
    way, without worrying about which Airflow operator to use for each execution mode.
    """
    try:
        gaiaflow_mode: GaiaflowMode = GaiaflowMode(mode)
    except ValueError:
        raise ValueError(
            f"env must be one of {[e.value for e in GaiaflowMode]}, got '{mode}'"
        )

    func_args = func_args or []
    func_kwargs = func_kwargs or {}
    if env_vars is None:
        env_vars = {}

    dag_params = getattr(dag, "params", {}) if dag else {}

    operator_cls = OPERATOR_MAP.get(gaiaflow_mode)
    if not operator_cls:
        raise ValueError(f"No task creation operator defined for {gaiaflow_mode}")

    operator = operator_cls(
        task_id=task_id,
        func_path=func_path,
        func_args=func_args,
        func_kwargs=func_kwargs,
        image=image,
        secrets=secrets,
        env_vars=env_vars,
        retries=retries,
        params=dag_params,
        mode=gaiaflow_mode,
    )

    return operator.create_task()
