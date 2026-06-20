"""Carbon-aware data-pipeline integrations (Airflow, Celery, Dagster, Prefect).

Each integration's framework is an optional dependency, so the modules import
without it and only raise when you actually build the integration object
"""


def _require(flag: bool, name: str, pip_name: str) -> None:
    """Raise a uniform ImportError when an optional integration dependency is missing."""
    if not flag:
        raise ImportError(
            f"The {name} integration needs {name} installed (pip install {pip_name})."
        )
