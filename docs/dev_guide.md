# User Guide - `dev` and `dev_docker` mode

Now that you have created a project using the template provided, and have the 
prerequisites installed please follow the steps below to start your ML journey.

### 0. Git Fundamentals. 

First, we need to initialize a Git repository to make the initial commit.
```bash
  cd {{ cookiecutter.folder_name }}
  git init -b main
  git add .
  git commit -m "Initial commit"
```

Next, create a repository in Github. Once created, copy the remote repository 
URL. Open the terminal with this project as the current working directory.
Then, replace the REMOTE-URL with your repo's URL on Github
```bash
  git remote add origin REMOTE-URL
```
Verify if the remote URL was set correctly.
```bash
  git remote -v
```
To push the changes, do the following:
```bash
  git push origin main
```
Now you have created a git repository with an initial commit of this project.
To proceed, create a new branch and start working in it.
```
  git checkout -b name-of-your-branch
```

### 1. Create and activate mamba environment

You can update the `environment.yml` to include your libraries, or you can 
update them later as well.
```bash
  mamba env create
  mamba activate <your-env-name>
```

If you have created an environment using the steps above, and would like to 
update the mamba env after adding new libraries in `environment.yml`, do this:
```bash
  mamba env update
```
To reflect these changes in Airflow as well, please restart the services as 
shown in the next step.

### 2. Start the services
The following command spins up a docker compose containers for Airflow, MLFLow, 
MinIO and a Jupyter Lab service (not in a container).

```bash
gaiaflow start dev -p .
```

NOTE: You can always choose which services you want to start using 
`--service` flag in the command. 

Check `gaiaflow start dev --help`

For e.g., if you just want to start a JupyterLab for starters, run:

```bash
gaiaflow start dev -p . --service jupyter
```

### 3. Accessing the services

Wait for the services to start (usually takes around 5 mins for the first run)

- Airflow UI
    - URL: [http://localhost:8080](http://localhost:8080)
    - username: `admin`
    - password: `admin`
- Mlflow UI
    - URL: [http://localhost:5000](http://localhost:5000)
- Minio (Local S3)
    - URL: [http://localhost:9000](http://localhost:9000)
    - username: `minio`
    - password: `minio123`
- JupyterLab
    - URL: Opens up JupyterLab automatically at port **8895** 
      (unless you change it using the `-j` flag)

### 4. Development Workflow

---

#### 1. Experiment in JupyterLab
- When services start, `JupyterLab` opens automatically in your browser.  
- Navigate to the `notebooks/` folder and create notebooks to **experiment with 
data, models, and logging** (metrics, params, and artifacts to MLflow).  
- Starter notebooks are available in the `examples/` folder:  
    - Learn how to use MLflow for experiment tracking.  
    - Perform inference on MLflow-logged models.  
- If your data comes from S3 (hosted by BC), it’s best to **download a small 
sample** and upload it to your local S3 storage (MinIO) for development and testing.
_NOTE: This is recommended because there are egress-costs (costs that occur when 
the data is pulled out from the AWS ecosystem) for everytime you pull the data._
- For local datasets, upload them to MinIO as well. Later, when your workflow
moves to production, ensure the data is available in S3.  
`aws s3 sync /path/to/source /path/to/target --delete`
Use `--delete` if you want the target to look exactly as the source
---

#### 2. Refactor to Production Code
- Once your logic (data ingestion, preprocessing, training, or post-processing) 
is ready, **refactor it into production code** inside the Python package directory.  
- Modify the files starting with `change_me_*`.  
- If you included examples when creating this project, explore files starting 
with `example_*` for guidance and delete them later on.  
- **Important:** Functions intended to run as tasks in Airflow must:  
     - Accept and return small data (strings, numbers, booleans).  
     - Return results wrapped in a `dict`, so downstream tasks can consume them.  

---
#### 3. Write Tests
- Add tests in the `tests/` directory to validate:  
    - Data preprocessing methods.  
    - Data schemas, transformations, etc.  
- Ensure your tests pass (make them green).  

---

#### 4. Create Your Workflows
- Navigate to the `dags/` folder and open the `change_me_*` files.  
- These files include **instructions on how to define DAGs**.  
- If examples are present, check `example_*` files to learn how DAGs are structured.  
- Workflows are created using the provided `create_task` function.  
- During early development:  
    - Use `mode = "dev"`.  
    - To pass environment variables, simply add them to your `.env` file.  

---
#### 5. Run and Monitor Your DAG
- Open the **Airflow UI**.  
- Find your DAG and trigger it with the ▶️ **Trigger DAG** button.  
- Monitor execution status and view logs directly in the UI.  

---

#### 6. Validate Outputs
- Check the **MinIO UI** to ensure data and artifacts were generated correctly.  

---


#### 7. Track Experiments
- While your model is training, open the **MLflow UI** to track experiments,
parameters, metrics, and artifacts.  

---

#### 8. Deploy Your Model
- Once training is complete, deploy your locally to test it using docker or 
test it directly (see next section for details).   

---


#### 9. Containerize for Dev-Docker Mode
- If your DAG works in `dev` mode, you can containerize your package and test 
it inside a Docker environment:  

```bash
gaiaflow dev dockerize -p .
```

- This builds an image for your package
- Use the generated image name in the `image` parameter of `create_task`.
- Pass environment variables via the `env_vars` parameter.
- Set `mode = "dev_docker"` and trigger your workflow again.
- If everything works, you’re ready to test in a [production-like setting](prod_guide.md).

_(Note: This step is optional — you can skip directly to production-like testing if preferred.)_

---


### 5. Stopping the services
You should stop these container services when you're done working with your 
project, need to free up system resources, or want to apply some 
updates. To gracefully stop the services, run this in the terminal where you
started them:

```bash
gaiaflow dev stop -p .
```

### 6. Cleanup
When you docker a lot on your local system to build images, it caches the 
layers that it builds and overtime, this takes up a lot of memory. 
To remove the cache, run this:

```bash
gaiaflow dev cleanup -p .
```


## MLFlow Model Deployment workflow locally


Once you have a model trained, you can deploy it locally either as
container or serve it directly from MinIO S3.
We recommend to deploy it as a container as this makes sure that it has its 
own environment for serving.

### Deploying Model as a Container locally

Since we have been working with docker containers so far, all the environment 
variables have been set for them, but now as we need to deploy them,
we would need to export a few variables so that MLFLow has access to them and 
can pull the required models from MinIO S3.

```bash
  export MLFLOW_TRACKING_URI=http://127.0.0.1:5000 
  export MLFLOW_S3_ENDPOINT_URL=http://127.0.0.1:9000 
  export AWS_ACCESS_KEY_ID=minio
  export AWS_SECRET_ACCESS_KEY=minio123
```

Once we have this variables exported, find out the `run_id` or the `s3_path` of 
the model you 
want to deploy from the MLFlow UI and run the following command:

```bash
  mlflow models build-docker -m runs:/<run-id>/model -n <name-of-your-container> --enable-mlserver --env-manager conda
```
or 
```bash
  mlflow models build-docker -m <s3_path> -n <name-of-your-container> --enable-mlserver --env-manager conda
```

After this finishes, you can run the docker container by:

```bash
  docker run -p 5002:8080 <name-of-your-container> 
```

Now you have an endpoint ready at `127.0.0.1:5002`.

Have a look at `notebooks/examples/mlflow_local_deploy_inference.ipynb` for an 
example on how to get the predictions.


###  Deploying local inference server

Prerequisites

- [Pyenv](https://github.com/pyenv/pyenv-installer)
- Make sure standard libraries in linux are upto date.
  ```
  sudo apt-get update
  sudo apt-get install -y build-essential
  sudo apt-get install --reinstall libffi-dev
  ```
- Run these commands to export the AWS (Local Minio server running)
  ```bash
   export AWS_ACCESS_KEY_ID=minio 
   export AWS_SECRET_ACCESS_KEY=minio123
   export MLFLOW_S3_ENDPOINT_URL=http://127.0.0.1:9000
  ```
- Now we are ready for local inference server. Run this after replacing the 
required stuff
    ```bash
    mlflow models serve -m s3://mlflow/0/<run_id>/artifacts/<model_name> -h 0.0.0.0 -p 3333
    ```
- We can now run inference against this server on the `/invocations` endpoint,
- Have a look at `notebooks/examples/mlflow_local_deploy_inference.ipynb` for an 
example on how to get the predictions.


## Testing

The template package comes with an initial template suite of tests. 
Please update these tests after you update the code in your package.

To test your dags along with your package, run this:

In Windows:
```bash
set AIRFLOW_CONFIG=%cd%\airflow_test.cfg
```
```bash
pytest --ignore=logs
```

In Linux:
```bash
export AIRFLOW_CONFIG=$(pwd)/airflow_test.cfg
```

```bash
pytest
```


## Code formatting practices while developing your package

### Ruff Check (linting)

```bash
ruff check .
```

### Ruff Check with Auto-fix (as much as possible)


```bash
ruff check .  --fix
```

### Ruff Format (Code formatting)

```bash
ruff format .
```

### isort (import sorting)

```bash
isort. 
```


## (Optional) Creating your python package distribution

There are two options:

1. You can use the provided CI workflow `.github/workflows/publish.yml` which 
   is triggered everytime you create a `Release`. If you choose this method, 
   please add `PYPI_API_TOKEN` to the secrets for this repository.
   (or)
2. You can do it manually as shown below:

First update the `pyproject.toml` as required for your package.

Then install the [PyPi build](https://build.pypa.io/en/latest/) if you 
dont have already have it.
```bash
  pip install build
```

Then from the root of this project, run:
```bash
  python -m build
```

Once this command runs successfully, you can install your package using:
```bash
  pip install dist/your-package
```

If you would like to upload your package to PyPi, follow the steps below:
1. Install `twine`
```bash
  pip install twine
```
2. Register yourself at PyPi if you have not already. Create an API token that 
you will use for uploading it to PyPi
3. Run this and enter your username and API token when prompted
```bash
  twine upload dist/*
```
4. Now your package should have been uploaded to PyPi.
5. You can test it by:
```bash
  pip install your-package
```

## Accessing/Viewing these services in Pycharm

If you are a Pycharm user, you are amazing!

If not, please consider using it as it provides a lot of functionalities in 
its community version.

Now, let's use one of its features called Services. It is a small hexagonal 
button
with the play icon inside it. You will find it in one of the tool windows.

When you open it, you can add services like Docker and Kubernetes. But for this 
framework, we only need Docker.

To view the docker service here, first we need to install the Docker Plugin in 
Pycharm.

To do so, `PyCharm settings` -> `Plugins` -> Install Docker plugin from 
marketplace

Then, reopen the services window, and when you add a new service, you will find 
Docker.

Just use the default settings.



## Troubleshooting Tips

- If you get Port already in use, change it with -j or free the port.
- Use `-v` to clean up Docker volumes if service states become inconsistent.
- Logs are saved in the logs/ directory.
- Please make sure that none of the `__init__.py` files are
completely empty as this creates some issues with
mlflow logging. You can literally just add a `#` to the
`__init__.py` file. This is needed because while serializing
the files, empty files have 0 bytes of content and that
creates issues with the urllib3 upload to S3 (this
happens inside MLFlow)
- If there are any errors in using the Minikube manager, try restarting it
by `python minikube_manager.py --restart` followed by 
`python mlops_manager.py --restart` to make sure that the changes are synced.
- If you face an issue with pyenv as such:
`python-build: defintion not found: 3.12.9`
then update your python-build definitions by:
`cd ~/.pyenv/plugins/python-build && git pull`

