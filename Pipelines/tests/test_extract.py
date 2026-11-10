from __future__ import annotations

import json

import pytest
import responses

from pipelines.extract import ExtractError, extract, fetch_rates
from tests.conftest import AS_OF, make_payload

URL = "https://example.test/v1/2024-01-15"


@responses.activate
def test_extract_writes_envelope_keyed_by_date(settings):
    responses.get(URL, json=make_payload(), status=200)

    out = extract(AS_OF, settings)

    assert out == settings.raw_dir / "2024-01-15.json"
    envelope = json.loads(out.read_text())
    assert envelope["as_of_date"] == "2024-01-15"
    assert envelope["payload"]["rates"]["EUR"] == 0.91366
    assert responses.calls[0].request.params == {"base": "USD"}


@responses.activate
def test_extract_passes_symbols_when_configured(settings, monkeypatch):
    monkeypatch.setenv("FX_SYMBOLS", "eur, gbp")
    from pipelines.config import Settings

    settings = Settings.from_env()
    responses.get(URL, json=make_payload(), status=200)

    fetch_rates(AS_OF, settings)

    assert responses.calls[0].request.params == {"base": "USD", "symbols": "EUR,GBP"}


@responses.activate
def test_extract_is_idempotent_on_rerun(settings):
    responses.get(URL, json=make_payload(), status=200)
    responses.get(URL, json=make_payload(rates={"EUR": 0.5}), status=200)

    extract(AS_OF, settings)
    out = extract(AS_OF, settings)

    assert len(list(settings.raw_dir.glob("*.json"))) == 1
    assert json.loads(out.read_text())["payload"]["rates"] == {"EUR": 0.5}


@responses.activate
def test_transient_5xx_is_retried_then_succeeds(settings):
    responses.get(URL, status=503)
    responses.get(URL, json=make_payload(), status=200)

    payload = fetch_rates(AS_OF, settings)

    assert payload["rates"]["GBP"] == 0.78643
    assert len(responses.calls) == 2


@responses.activate
def test_persistent_5xx_raises_for_airflow_to_retry(settings):
    responses.get(URL, status=500)
    responses.get(URL, status=500)

    with pytest.raises(ExtractError, match="HTTP 500"):
        fetch_rates(AS_OF, settings)


@responses.activate
def test_404_is_not_retried(settings):
    responses.get(URL, json={"message": "not found"}, status=404)

    with pytest.raises(ExtractError, match="HTTP 404"):
        fetch_rates(AS_OF, settings)
    assert len(responses.calls) == 1


@responses.activate
@pytest.mark.parametrize(
    "body",
    [{"base": "USD", "date": "2024-01-15"}, {"rates": {}}, ["not", "a", "dict"]],
)
def test_bad_payload_shape_raises(settings, body):
    responses.get(URL, json=body, status=200)

    with pytest.raises(ExtractError):
        fetch_rates(AS_OF, settings)
