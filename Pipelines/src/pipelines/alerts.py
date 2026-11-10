"""Alerting for Airflow task failures and retries.

Callbacks are wired into the DAG's ``default_args``. They post to a Slack
incoming webhook when ``SLACK_WEBHOOK_URL`` is set and always write to the
task log, so the pipeline is observable even with no webhook configured.

Callbacks must never raise: an exception here would mask the real failure.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

import requests

from pipelines.config import Settings, get_settings

log = logging.getLogger(__name__)


def _ti_attr(ti: Any, name: str, default: Any = None) -> Any:
    return getattr(ti, name, default) if ti is not None else default


def describe_task(context: Mapping[str, Any], settings: Settings) -> Dict[str, Any]:
    """Pull the fields worth alerting on out of an Airflow task context."""
    ti = context.get("task_instance") or context.get("ti")
    dag = context.get("dag")
    dag_run = context.get("dag_run")

    dag_id = _ti_attr(ti, "dag_id") or getattr(dag, "dag_id", "unknown_dag")
    task_id = _ti_attr(ti, "task_id", "unknown_task")
    run_id = getattr(dag_run, "run_id", None) or context.get("run_id") or "unknown_run"
    try_number = int(_ti_attr(ti, "try_number", 0) or 0)
    max_tries = int(_ti_attr(ti, "max_tries", 0) or 0)

    log_url = _ti_attr(ti, "log_url")
    if not log_url:
        log_url = (
            f"{settings.airflow_base_url.rstrip('/')}/dags/{dag_id}/runs/{run_id}/tasks/{task_id}"
        )

    exception = context.get("exception")
    return {
        "dag_id": dag_id,
        "task_id": task_id,
        "run_id": run_id,
        "logical_date": str(context.get("ds") or context.get("logical_date") or ""),
        "try_number": try_number,
        "max_tries": max_tries,
        "log_url": log_url,
        "exception": f"{type(exception).__name__}: {exception}" if exception else None,
    }


def format_failure(info: Mapping[str, Any]) -> str:
    lines = [
        f":rotating_light: *Airflow task FAILED* `{info['dag_id']}.{info['task_id']}`",
        f"run: `{info['run_id']}`  logical date: {info['logical_date'] or 'n/a'}",
        f"attempts exhausted: {info['try_number']}/{info['max_tries'] + 1}",
    ]
    if info.get("exception"):
        lines.append(f"error: `{info['exception'][:500]}`")
    lines.append(f"logs: {info['log_url']}")
    return "\n".join(lines)


def format_retry(info: Mapping[str, Any]) -> str:
    lines = [
        f":warning: *Airflow task retrying* `{info['dag_id']}.{info['task_id']}`",
        f"run: `{info['run_id']}`  attempt {info['try_number']} of {info['max_tries'] + 1} failed",
    ]
    if info.get("exception"):
        lines.append(f"error: `{info['exception'][:300]}`")
    lines.append(f"logs: {info['log_url']}")
    return "\n".join(lines)


def send_slack(text: str, webhook_url: Optional[str], timeout: float = 10.0) -> bool:
    """POST to a Slack incoming webhook. Returns True when delivered."""
    if not webhook_url:
        log.warning("SLACK_WEBHOOK_URL not set; alert only logged:\n%s", text)
        return False
    try:
        response = requests.post(webhook_url, json={"text": text}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        log.error("Slack alert delivery failed: %s\n%s", exc, text)
        return False
    log.info("Slack alert delivered")
    return True


def on_failure_callback(context: Mapping[str, Any]) -> None:
    """Fires once, after all retries are exhausted."""
    try:
        settings = get_settings()
        info = describe_task(context, settings)
        text = format_failure(info)
        log.error(text)
        send_slack(text, settings.slack_webhook_url)
    except Exception:  # noqa: BLE001 - never let alerting break the task lifecycle
        log.exception("on_failure_callback itself failed")


def on_retry_callback(context: Mapping[str, Any]) -> None:
    """Fires on every failed attempt that will be retried."""
    try:
        settings = get_settings()
        info = describe_task(context, settings)
        text = format_retry(info)
        log.warning(text)
        if settings.alert_on_retry:
            send_slack(text, settings.slack_webhook_url)
    except Exception:  # noqa: BLE001
        log.exception("on_retry_callback itself failed")


def on_dag_success_callback(context: Mapping[str, Any]) -> None:
    """Optional heartbeat: a short confirmation when the whole DAG succeeds."""
    try:
        settings = get_settings()
        dag = context.get("dag")
        dag_run = context.get("dag_run")
        dag_id = getattr(dag, "dag_id", "unknown_dag")
        run_id = getattr(dag_run, "run_id", "unknown_run")
        text = f":white_check_mark: `{dag_id}` succeeded (run `{run_id}`)"
        log.info(text)
        send_slack(text, settings.slack_webhook_url)
    except Exception:  # noqa: BLE001
        log.exception("on_dag_success_callback itself failed")
