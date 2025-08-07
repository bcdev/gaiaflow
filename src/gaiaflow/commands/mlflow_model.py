import typer

from gaiaflow.constants import BaseActions
from gaiaflow.managers.mlflow_model_manager import MlflowModelManager

app = typer.Typer()


@app.command(help="Deploy a Mlflow model. NOTE: Currently only local model "
                  "deployment is provided.")
def start(
    model_uri: str = typer.Option("", help="S3 URI of the model to serve. "
                                            "This or run_id has to be "
                                            "provided. If you provide both, "
                                           "model_uri takes precedence."),
    run_id: str = typer.Option("", help="MLflow run ID of your model. This "
                                         "or model_uri has to be provided. If you provide both, "
                                           "model_uri takes precedence."),
    image_name: str = typer.Option(..., help="Docker image name"),
    enable_mlserver: bool = typer.Option(True, help="Enable MLServer"),
):
    if not (run_id or model_uri):
        typer.echo("Please provide either run_id or model_uri.")
    kwargs = {
        "params": {
            "model_uri": model_uri,
            "run_id": run_id,
            "image_name": image_name,
            "enable_mlserver": enable_mlserver,
        }
    }
    typer.echo(f"kwargs::{kwargs}")
    MlflowModelManager(
        action=BaseActions.START,
        **kwargs
    )

@app.command(help="Stop a deployed Mlflow model container. NOTE: Currently "
                  "only local model deployment is provided.")
def stop(
    container_id_or_name: str = typer.Option(..., help="Container ID or name"),
):
    kwargs = {
        "params": {
            "container_id_or_name": container_id_or_name,
        }
    }
    typer.echo(f"kwargs::{kwargs}")
    MlflowModelManager(
        action=BaseActions.STOP,
        **kwargs
    )

@app.command(help="Cleanup a deployed Mlflow model container. NOTE: Currently "
                  "only local model deployment is provided.")
def cleanup(
    container_id_or_name: str = typer.Option(..., help="Container ID or name"),
    purge: str = typer.Option(..., "-p", help="Remove the Deployed MLFlow "
                                              "model image"),
):
    kwargs = {
        "params": {
            "container_id_or_name": container_id_or_name,
            "purge": purge,
        }
    }
    typer.echo(f"kwargs::{kwargs}")
    MlflowModelManager(
        action=BaseActions.STOP,
        **kwargs
    )
