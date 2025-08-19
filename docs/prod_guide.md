# User Guide - `prod_local` and `prod` mode

## Testing your DAGs using Docker Images in `prod_local` mode

Before running your DAGs in **production**, it’s recommended to test them in 
`prod_local` mode. This simulates how tasks will run on the production cluster:  
- Each task within the DAG executes in its own isolated container.  
- You get a realistic, end-to-end test of your workflow. 

To test this, you need a few things:
---


### Step 0. Set Mode
In your DAG code, set the `create_task` parameter to use `prod_local` mode:  

```python
create_task(..., mode = "prod_local")
```

---

### Step 1. Start Local Kubernetes (Minikube)

Spin up a lightweight local Kubernetes cluster:
```bash
gaiaflow prod-local start -p .
```

This may take a few minutes while infrastructure is provisioned.

---

### Step 2. Build your Docker image

Make your project’s Docker image available inside Minikube:

```bash
gaiaflow prod-local dockerize -p .
```

---

### Step 3. Create Secrets (Optional)
If you need to pass sensitive environment variables that shouldn’t go
directly into `env_vars`, store them as Kubernetes secrets:

```bash
gaiaflow prod-local create-secret -p . \
--name <your-secret-name> \
--data SOME_KEY=value \
--data SOME_SECRET=secret
```

---

### Step 4. Configure Airflow (Temporary Step)
Tell Airflow where your Minikube cluster is 
(this step may be automated in the future):

```bash
gaiaflow prod-local create-config -p .
```

---

Once these steps are done, you are ready to test your DAG in production-like 
setting.

Head over to the Airflow UI, you should now see your DAG using
`KubernetesPodOperator`. 
- Trigger the DAG from the UI
- Watch the logs and wait for the DAG to finish execution

If everything works smoothly here, your workflow is ready to move to production.


## BONUS testing

This is optional but in case you want to test each task separately using the 
docker image that you created, you can do so.

To test this, you would need to pass in the arguments that that specific task 
requires.

To test your each task, do this:

```bash
docker run --rm -e \
FUNC_PATH="your_module.your_function" \
-e FUNC_KWARGS='{"param1": "value1", "param2": "value2"}' \
your-image-name:tag
```

Doing this test is to ensure that your task functions are idempotent (i.e. they
will always return the same result, no matter how many time you run it!) and 
that they can run in an isolated environment in production.

Test this for all your tasks individually.


## Running Airflow DAGs in Production

To run your DAGs in a **production Airflow deployment**, a few things need 
to be in place.

### Notes
- These setup steps are required **once per project** (except task secrets, which may change).  
- **MLflow support in production** is coming soon

---

### 1. Centralized DAG Repository (CDR)
Your team or company should maintain a **Centralized DAG Repository (CDR)**.  
For BC, it is available [here](https://github.com/bcdev/airflow-dags)
This repository collects DAGs from multiple projects and makes them available to Airflow.  

---


### 2. Required Secrets
You’ll need to configure the following secrets in your repository:  

- `PYPI_API_TOKEN` → Create from the PyPI website and add as a repo secret  
- `CODECOV_TOKEN` → Create from the Codecov website and add as a repo secret  
- `CDR_PAT` → A GitHub **Personal Access Token (PAT)** used to interact with CDR  

#### Creating the `CDR_PAT`
1. Go to your GitHub **Account Settings**  
2. Navigate to **Developer Settings** (last option in the sidebar)  
3. Create a **Personal access token (classic)**  
   - Select only the `repo` permissions  
   - Generate the token  
   - Copy and save it somewhere safe (e.g., KeePassXC)  
4. Add it to your project as a GitHub Secret:  
   - Go to **Repository Settings → Secrets and Variables → Actions → New repository secret**  
   - Name: `CDR_PAT`  
   - Secret: paste your token  
   - Click **Add Secret**  

---

### 3. Task Secrets
Any **secrets required by your tasks** must also be made available to the cluster running Airflow.  
For this step, `Talk to Tejas`

---

### 4. GitHub Release Workflow
When you create a **GitHub release**, the following steps are triggered automatically:  

-  A Docker image is built and pushed to **AWS ECR**  
-  Your DAGs are uploaded to **S3**  
-  A **dispatch event** is sent to the CDR  
-  CDR pulls DAGs from S3  
-  Airflow reads DAGs from the CDR  

For this to work, your team should provide you with an **AWS Role** that allows CI to push to ECR and S3.  
Add this role as a **GitHub repository secret** so your CI can use it.  

---


### You’re Ready for Production
With all prerequisites in place:  
1. Create a **GitHub release**.  
2. The automation pipeline runs the steps above.  
3. Within a few minutes, your DAG will appear in the **Airflow UI**, ready to be triggered.  

---




