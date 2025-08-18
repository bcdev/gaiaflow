# !!PLEASE DO NOT EDIT/DELETE THIS!!
# This file is the main entry point to your package when using Airflow to
# run your tasks from your DAGs called from the task_factory.
# It imports the required function from your package and executes it with the
# arguments provided

import json
import os
import pickle
from typing import Any


def _extract_params_from_env(prefix="PARAMS_") -> dict[str, str]:
    return {
        k[len(prefix) :].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


def run(
    func_path: str | None = None,
    args: list | None = None,
    kwargs: dict[str, str] | None = None,
) -> dict[str, str]:
    mode = os.environ.get("MODE", "dev")
    print(f"## Runner running in {mode} mode ##")
    if mode == "dev":
        print("args", args)
        print("kwargs", kwargs)
    else:
        func_path = os.environ.get("FUNC_PATH", "")
        args = json.loads(os.environ.get("FUNC_ARGS", "{}"))
        kwargs = json.loads(os.environ.get("FUNC_KWARGS", "{}"))
        params = _extract_params_from_env()
        kwargs["params"] = params
        print("args", args)
        print("kwargs", kwargs)

    module_path, func_name = func_path.rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    func = getattr(module, func_name)

    print(f"Running {func_path} with args: {args} and kwargs :{kwargs}")
    result = func(*args, **kwargs)
    print("Function result:", result)
    if (mode == "prod" or mode == "prod_local_minikube"):
        # This is needed when we use KubernetesPodOperator and want to
        # share information via XCOM.
        _write_xcom_result(result)
    if mode == "prod_local_docker":
        with open("/tmp/script.out", "wb+") as tmp:
            pickle.dump(result, tmp)
    return result


def _write_xcom_result(result: Any) -> None:
    try:
        xcom_dir = "/airflow/xcom"
        os.makedirs(xcom_dir, exist_ok=True)

        with open(f"{xcom_dir}/return.json", "w") as f:
            json.dump(result, f)

        print("Result written to XCom successfully")
    except Exception as e:
        print(f"Failed to write XCom result: {e}")
        raise


if __name__ == "__main__":
    run()
