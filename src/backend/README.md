# Overview

The project is managed by pyproject.toml and [uv package manager](https://docs.astral.sh/uv/getting-started/installation/).


## Local execution
For local execution init the .venv environment using [uv package manager](https://docs.astral.sh/uv/getting-started/installation/):

```shell
cd src/backend
uv sync
. ./.venv/bin/activate
uvicorn app:app
```

> [INFO!] Environment variables will be read from the AZD env file: `$project/.azure/<selected_azd_environment>/.env` automatically

> [WARNING!] Planner environment variables are incompaible with o1-prevew or o1-mini models


## Testing

Run pytests integration tests using the following command:

```shell
python -m pytest tests/
```