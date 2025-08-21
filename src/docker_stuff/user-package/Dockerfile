# This Dockerfile is to create an image that contains the dependencies the user's package needs as well as the package
# itself. This image will be then used to run the DAGs on the Airflow hosted on our development and Kubernetes cluster
# in AWS.

FROM  mambaorg/micromamba:latest

WORKDIR /app

COPY environment.yml .

RUN micromamba install -f environment.yml -n base

ENV PATH=/opt/conda/bin:$PATH

ENTRYPOINT ["python", "-m", "runner"]