import os
from contextlib import contextmanager
from typing import Callable
from collections.abc import Generator


@contextmanager
def set_env_cm(**new_env: str | None) -> Generator[dict[str, str | None]]:
    """Run the code in the block with a new environment `new_env`."""
    restore_env = set_env(**new_env)
    try:
        yield new_env
    finally:
        restore_env()


def set_env(**new_env: str | None) -> Callable[[], None]:
    """
    Set the new environment in `new_env` and return a no-arg
    function to restore the old environment.
    """
    old_env = {k: os.environ.get(k) for k in new_env.keys()}

    def restore_env():
        for ko, vo in old_env.items():
            if vo is not None:
                os.environ[ko] = vo
            elif ko in os.environ:
                del os.environ[ko]

    for kn, vn in new_env.items():
        if vn is not None:
            os.environ[kn] = vn
        elif kn in os.environ:
            del os.environ[kn]

    return restore_env