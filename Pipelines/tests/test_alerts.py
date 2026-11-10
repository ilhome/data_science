from __future__ import annotations

import logging
from types import SimpleNamespace

import responses

from pipelines import alerts
from pipelines.config import Settings

WEBHOOK = "https://hooks.slack.test/services/T0/B0/x"


def fake_context(try_number=4, exception=None):
    ti = SimpleNamespace(
        dag_id="fx_rates_pipeline",
        task_id="extract",
        try_number=try_number,
        max_tries=3,
        log_url="http://airflow/logs/1",
    )
    return {
        "task_instance": ti,
        "dag_run": SimpleNamespace(run_id="manual__2024-01-15"),
        "ds": "2024-01-15",
        "exception": exception,
    }


def test_failure_message_contains_the_essentials(settings):
    info = alerts.describe_task(fake_context(exception=RuntimeError("boom")), settings)
    text = alerts.format_failure(info)

    assert "fx_rates_pipeline.extract" in text
    assert "manual__2024-01-15" in text
    assert "4/4" in text
    assert "RuntimeError: boom" in text
    assert "http://airflow/logs/1" in text


def test_log_url_is_derived_when_missing(settings):
    ctx = fake_context()
    ctx["task_instance"].log_url = None

    info = alerts.describe_task(ctx, settings)

    assert info["log_url"].startswith(settings.airflow_base_url)
    assert "fx_rates_pipeline" in info["log_url"]


@responses.activate
def test_failure_callback_posts_to_slack(settings, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)
    responses.post(WEBHOOK, body="ok", status=200)

    alerts.on_failure_callback(fake_context(exception=ValueError("bad")))

    assert len(responses.calls) == 1
    body = responses.calls[0].request.body.decode()
    assert "Airflow task FAILED" in body
    assert "ValueError: bad" in body


@responses.activate
def test_retry_callback_posts_when_enabled(settings, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)
    monkeypatch.setenv("ALERT_ON_RETRY", "true")
    responses.post(WEBHOOK, body="ok", status=200)

    alerts.on_retry_callback(fake_context(try_number=1))

    assert len(responses.calls) == 1
    assert "retrying" in responses.calls[0].request.body.decode()


@responses.activate
def test_retry_callback_silent_when_disabled(settings, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)
    monkeypatch.setenv("ALERT_ON_RETRY", "false")

    alerts.on_retry_callback(fake_context(try_number=1))

    assert len(responses.calls) == 0


@responses.activate
def test_without_webhook_alert_is_logged_not_sent(settings, caplog):
    with caplog.at_level(logging.WARNING):
        alerts.on_failure_callback(fake_context())

    assert len(responses.calls) == 0
    assert any("SLACK_WEBHOOK_URL not set" in r.message for r in caplog.records)
    assert any("Airflow task FAILED" in r.message for r in caplog.records)


@responses.activate
def test_slack_delivery_failure_never_raises(settings, monkeypatch, caplog):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK)
    responses.post(WEBHOOK, body="no", status=500)

    with caplog.at_level(logging.ERROR):
        alerts.on_failure_callback(fake_context())  # must not raise

    assert any("delivery failed" in r.message for r in caplog.records)


def test_callbacks_swallow_internal_errors(caplog):
    with caplog.at_level(logging.ERROR):
        alerts.on_failure_callback(None)  # type: ignore[arg-type]

    assert any("itself failed" in r.message for r in caplog.records)


def test_settings_parse_alert_flags(monkeypatch):
    monkeypatch.setenv("ALERT_ON_RETRY", "0")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    s = Settings.from_env()
    assert s.alert_on_retry is False
    assert s.slack_webhook_url is None
