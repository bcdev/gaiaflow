# Getting Started with Gaiaflow

This guide will help you set up your environment, install dependencies, and 
generate your first project using the GaiaFlow template.

The following section provides an overview of the services provided by the 
Gaiaflow framework. For first-time users, we recommend that you read/skim 
through this to get an idea of what Gaiaflow can currently offer.

If you would like to start right away, then get [started here](#getting-started)


## Overview

Gaiaflow integrates essential MLOps tools:

- **Cookiecutter**: For providing a standardized project structure
- **Apache Airflow**: For orchestrating ML pipelines and workflows
- **MLflow**: For experiment tracking and model registry
- **JupyterLab**: For interactive development and experimentation
- **MinIO**: For local object storage for ML artifacts
- **Minikube**: For local lightweight Kubernetes cluster


### MLOps Components

Before you get started, let's explore the tools that we are using for this 
standardized MLOps framework 

### 0. Cookiecutter
Purpose: Project scaffolding and template generation

- Provides a standardized way to create ML projects with predefined structures.
- Ensures consistency across different ML projects
- Get started [here](https://github.com/bcdev/gaiaflow-cookiecutter)


### 1. Apache Airflow

Purpose: Workflow orchestration

- Manages and schedules data pipelines.
- Automates end-to-end ML workflows, including data ingestion, training, deployment and re-training.
- Provides a user-friendly web interface for tracking task execution's status.


#### Key Concepts in Airflow

##### DAG (Directed Acyclic Graph)
A DAG is a collection of tasks organized in a structure that reflects their 
execution order. DAGs do not allow for loops, ensuring deterministic scheduling 
and execution.

##### Task
A Task represents a single unit of work within a DAG. Each task is an instance
of an **Operator**. Gaiaflow provides [create_task](#gaiaflow-core) for the
ease of defining tasks in a DAG.

##### Operator
Operators define the type of work to be done. They are templates that 
encapsulate logic.

Common Operators:

- **PythonOperator**: Executes a Python function.

- **BashOperator**: Executes bash commands.

- **KubernetesPodOperator**: Executes code inside a Kubernetes pod.

- **DummyOperator**: No operation — used for DAG design.

For ease of use of Airflow, we have created a function `create_task` that 
allows the user to create these tasks without worrying about which operator to
use. Read more [here](#gaiaflow-core)

##### Scheduler
The scheduler is responsible for triggering DAG runs based on a schedule. 
It evaluates DAGs, resolves dependencies, and queues tasks for execution.

##### XCom (Cross-Communication)
A lightweight mechanism for passing small data between tasks. Data is stored 
in Airflow’s metadata DB and fetched using Jinja templates or Python.


#### Airflow UI

- **DAGs (Directed Acyclic Graphs)**: A workflow representation in Airflow. You 
can enable, disable, and trigger DAGs from the UI.
- **Graph View**: Visual representation of task dependencies.
- **Tree View**: Displays DAG execution history over time.
- T**ask Instance**: A single execution of a task in a DAG.
- **Logs**: Each task's execution details and errors.
- **Code View**: Shows the Python code of a DAG.
- **Trigger DAG**: Manually start a DAG run.
- **Pause DAG**: Stops automatic DAG execution.

Common Actions

- **Enable a DAG**: Toggle the On/Off button.
- **Manually trigger a DAG**: Click Trigger DAG ▶️.
- **View logs**: Click on a task instance and select Logs.
- **Restart a failed task**: Click Clear to rerun a specific task.

### 2. MLflow

Purpose: Experiment tracking and model management

- Tracks and records machine learning experiments, including hyperparameters, performance metrics, and model artifacts.
- Facilitates model versioning and reproducibility.
- Supports multiple deployment targets, including cloud platforms, Kubernetes, and on-premises environments.


#### Core Components

##### Tracking
Allows logging of metrics, parameters, artifacts, and models for every 
experiment.

##### Models
MLflow models are saved in a standard format that supports deployment to 
various serving platform.

##### Model Registry
Central hub for managing ML models where one can register and version models.


#### MLFlow UI

- **Experiments**: Group of runs tracking different versions of ML models.
- **Runs**: A single execution of an ML experiment with logged parameters, 
metrics, and artifacts.
- **Parameters**: Hyperparameters or inputs logged during training.
- **Metrics**: Performance indicators like accuracy or loss.
- **Artifacts**: Files such as models, logs, or plots.
- **Model Registry**: Centralized storage for trained models with versioning.

Common Actions

- **View experiment runs**: Go to Experiments > Select an experiment
- **Compare runs**: Select multiple runs and click Compare.
- **View parameters and metrics**: Click on a run to see details.
- **View registered model**: Under Artifacts, select a model and click Register 
Model.

For a quick MLFLow tutorial, see `notebooks/examples/mlflow_introduction.ipynb`

### 3. JupyterLab

Purpose: Interactive development environment

- Provides an intuitive and interactive web-based interface for exploratory data analysis, visualization, and model development.

### 4. MinIO

Purpose: Object storage for ML artifacts

- Acts as a cloud-native storage solution for datasets and models.
- Provides an S3-compatible API for seamless integration with ML tools.
- Suitable for Local development iterations using a portion of the data

### 5. Minikube

Purpose: Local Kubernetes cluster for development & testing

- Allows you to run a single-node Kubernetes cluster locally.
- Simulates a production-like environment to test Airflow DAGs end-to-end.
- Great for validating KubernetesExecutor, and Dockerized task behavior before deploying to a real cluster.
- Mimics production deployment without the cost or risk of real cloud infrastructure.


## Getting Started
Before starting, ensure you have the following installed from the 
links provided:

If you face any issues, please check out the [troubleshooting section](#troubleshooting)

### Prerequisites

- [Docker and Docker Compose](#docker-and-docker-compose-plugin-installation)
- [Mamba](https://github.com/conda-forge/miniforge) - Please make sure you 
install `Python 3.12` as this repository has been tested with that version.
- [Minikube on Linux](https://minikube.sigs.k8s.io/docs/start/?arch=%2Flinux%2Fx86-64%2Fstable%2Fbinary+download)
- [Minikube on Windows](https://minikube.sigs.k8s.io/docs/start/?arch=%2Fwindows%2Fx86-64%2Fstable%2F.exe+download)
- [Create a Gaiaflow cookiecutter project](https://github.com/bcdev/gaiaflow-cookiecutter)
- [Gaiaflow](#gaiaflow-installation)

### Docker and Docker compose plugin Installation

For Linux users: please follow the steps mentioned in this [link](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)

For Windows users: please follow the steps mentioned in this [link](https://docs.docker.com/desktop/setup/install/windows-install/)

This should install both Docker and Docker compose plugin.
You can verify the installation by these commands
```bash
   docker --version
   docker compose version
```
and output would be something like:
```commandline
  Docker version 27.5.1, build 9f9e405
  Docker Compose version v2.32.4
```
This means now you have successfully installed Docker.


### Gaiaflow Installation

In Windows, install `gaiaflow` using WSL2 terminal in a new mamba/conda environment.

You can install Gaiaflow directly via pip:

`pip install gaiaflow`

Verify installation:

`gaiaflow --help`

### Gaiaflow Cookiecutter

Once you created the project template using the Gaiaflow cookiecutter,
it will contain the following files and folders.

Any files or folders marked with `*` are off-limits—no need to change, modify, 
or even worry about them. Just focus on the ones without the mark!

Any files or folders marked with `^` can be extended, but carefully.
```
├── .github/             # GitHub Actions workflows (you are provided with a starter CI)
├── dags/                # Airflow DAG definitions 
│                          (you can either define dags using a config-file (dag-factory)
│                           or use Python scripts.)
├── notebooks/           # JupyterLab notebooks
├── your_package/                  
│   │                     (For new projects, it would be good to follow this standardized folder structure.
│   │                      You are of course allowed to add anything you like to it.)
│   ├── dataloader/      # Your Data loading scripts
│   ├── train/           # Your Model training scripts
│   ├── preprocess/      # Your Feature engineering/preprocessing scripts
│   ├── postprocess/     # Your Postprocessing model output scripts
│   ├── model/           # Your Model defintion
│   ├── model_pipeline/  # Your Model Pipeline to be used for inference
│   └── utils/           # Utility functions
├── tests/               # Unit and integration tests
├── data/                # If you have data locally, move it here and use it so that airflow has access to it.
├── README.md            # Its a readme. Feel to change it!
├── CHANGES.md           # You put your changelog for every version here.
├── pyproject.toml       # Config file containing your package's build information and its metadata
├── .env * ^             # Your environment variables that docker compose and python scripts can use (already added to .gitignore)
├── .gitignore * ^       # Files to ignore when pushing to git.
├── environment.yml      # Libraries required for local mlops and your project
└── airflow_test.cfg *   # This file is needed for testing your airflow dags.
```

In your package, you are provided with scripts
starting with `change_me_*`. Please have a look at the comments in these files
before starting.

If you chose to have examples for dags and the package, you will find the files 
starting with `example_*`. Please have a look at these files to get more info 
and to get started.

### Next step

Once the pre-requisites are done, please follow along [here](dev_guide.md).


## Troubleshooting
0. If you are windows, please use the `miniforge prompt` commandline.

1. If you face issue like `Docker Daemon not started`, start it using:
```bash
  sudo systemctl start docker
```
and try the docker commands again in a new terminal.


2. If you face an issue as follows:
`Got permission denied while trying to connect to the Docker daemon socket at 
unix:///var/run/docker.sock: `,
do the following
```bash
  sudo chmod 666 /var/run/docker.sock
```
and try the docker commands again in a new terminal.


3. If you face an issue like
`Cannot connect to the Docker daemon at unix:///home//.docker/desktop/docker.sock. 
Is the docker daemon running?`,
it is likely because of you have two contexts of docker running.

To view the docker contexts,
```bash
   docker context ls
```
This will show the list of docker contexts. Check if default is enabled (it 
should have a * beside it)
If not, you might probably have desktop as your context enabled.
To confirm which context you are in:
```bash
   docker context show
```

To use the default context, do this:
```bash
   docker context use default
```

Check for the following file:
```bash
  cat ~/.docker/config.json
```
If it is empty, all good, if not, it might be something like this:
```
  {
	"auths": {},
	"credsStore": "desktop"
  }
```
Completely move this file away from this location or delete it and try running 
docker again.

4. If you face some permissions issues on some files like `Permission Denied`, 
as a workaround, please use this and let us know so that we can update this 
repo.
```bash
  sudo chmod 666 <your-filename> 
```

If you face any other problems not mentioned above, please reach out to us.