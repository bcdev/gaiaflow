## Version 0.0.3 (in development)

* **Bug fix** - `ExternalPythonOperator` does not need Airflow in external environment now.

* Jupyter Lab can now be started in any conda/mamba environment via Gaiaflow.

* Added user workflow diagram in the `Overview` page of the documentation.

* Added a new subcommand `gaiaflow dev update-deps --help` to update
  dependencies on the fly in Airflow containers for workflow tasks.



## Version 0.0.2

* **Chore**: Update `pyproject.toml` to include `README.md` and necessary links.

## Version 0.0.1

This is an experimental version. A stable release will follow in the future.

* First implementation of Gaiaflow CLI tool for managing local MLOps 
infrastructure.
* Moved all Docker files from the user’s cookiecutter project into this library.
* A documentation site has been created.
* Tested on Windows-WSL2-Ubuntu and Linux Ubuntu.
 
 