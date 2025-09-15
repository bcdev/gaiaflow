# !!PLEASE DO NOT EDIT/DELETE THIS!!
# This file is the main entry point to your package when using Airflow to
# run your tasks from your DAGs called from the task_factory.
# It imports the required function from your package and executes it with the
# arguments provided

import json
import os
import pickle
from typing import Any


def run(
    func_path: str | None = None,
    args: list | None = None,
    kwargs: dict[str, Any] | None = None,
) -> dict[str, str]:
    mode = os.environ.get("MODE", "dev")
    print(f"## Runner running in {mode} mode ##")
    func_path, args, kwargs = _resolve_inputs(func_path, args, kwargs, mode)

    if not func_path:
        raise ValueError("func_path must be provided")

    func = _import_function(func_path)

    print(f"Running {func_path} with args: {args} and kwargs :{kwargs}")
    result = func(*args, **kwargs)
    print("Function result:", result)

    _write_result(result, mode)

    return result


def _extract_params_from_env(prefix="PARAMS_") -> dict[str, str]:
    return {
        k[len(prefix) :].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


def _resolve_inputs(func_path: str, args: list[Any], kwargs: dict[Any], mode: str):
    if mode == "dev":
        return func_path, args or [], kwargs or {}
    else:  # all other modes (dev_docker, prod_local and prod)
        func_path = os.environ.get("FUNC_PATH", func_path)
        args = json.loads(os.environ.get("FUNC_ARGS", "[]"))
        kwargs = json.loads(os.environ.get("FUNC_KWARGS", "{}"))
        kwargs["params"] = _extract_params_from_env()
        return func_path, args, kwargs


def _import_function(func_path: str):
    import importlib

    module_path, func_name = func_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def _write_result(result, mode):
    if mode == "prod" or mode == "prod_local":
        _write_xcom_result(result)
    if mode == "dev_docker":
        with open("/tmp/script.out", "wb+") as tmp:
            pickle.dump(result, tmp)


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
