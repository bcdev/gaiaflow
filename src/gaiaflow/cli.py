from importlib.metadata import version

import typer

from .commands import minikube, mlflow_model, mlops

pkg_version = version("gaiaflow")

app = typer.Typer(
    add_completion=False,
    help="Gaiaflow CLI is a manager tool "
    "to allow you to create/destroy your local MLOps infrastructure that "
    "mirrors closely to the actual production systems for easier and faster "
    "local development, iteration and testing.",
)

app.add_typer(mlops.app, name="dev", help="Manage Gaiaflow development services.")
app.add_typer(
    minikube.app,
    name="prod-local",
    help="Manage Gaiaflow production-like services. Start this once "
    "you have developed your package and tested your workflow in the dev mode.",
)
app.add_typer(
    mlflow_model.app,
    name="model",
    help="Manage MLFlow models by either deploying or un-deploying them. "
    "NOTE:Currently only local deployments supported.",
)

if __name__ == "__main__":
    app()
