from importlib.metadata import version

import typer
from ruamel.yaml import YAML

from .commands import minikube, mlops

pkg_version = version("gaiaflow")

app = typer.Typer(add_completion=False)

app.add_typer(mlops.app, name="dev", help="Manage Gaiaflow development services.")
app.add_typer(
    minikube.app,
    name="prod-local",
    help="Manage Gaiaflow production-like services. Start this once "
    "you have developed your package and tested your workflow in the dev mode.",
)

if __name__ == "__main__":
    app()
