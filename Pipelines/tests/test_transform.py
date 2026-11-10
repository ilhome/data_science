from __future__ import annotations

import pandas as pd
import pytest

from pipelines.transform import TransformError, envelope_to_frame, transform, validate
from tests.conftest import make_envelope


def test_envelope_unpivots_to_one_row_per_currency():
    frame = envelope_to_frame(make_envelope())

    assert len(frame) == 3
    assert set(frame["quote_currency"]) == {"EUR", "GBP", "JPY"}
    assert (frame["base_currency"] == "USD").all()
    assert (frame["as_of_date"] == "2024-01-15").all()


def test_weekend_request_keeps_both_dates():
    # The API answers a Saturday request with Friday's fixing.
    env = make_envelope(date="2024-01-12")
    env["as_of_date"] = "2024-01-13"

    frame = validate(envelope_to_frame(env))

    assert (frame["as_of_date"] == "2024-01-13").all()
    assert (frame["rate_date"] == "2024-01-12").all()


@pytest.mark.parametrize(
    "rates, message",
    [
        ({"EUR": -1}, "non-positive"),
        ({"EUR": 0}, "non-positive"),
        ({"EUR": "abc"}, "non-numeric"),
        ({"E1": 1.0}, "invalid quote_currency"),
        ({"USD": 1.0}, "own quote"),
    ],
)
def test_validation_rejects_bad_rates(rates, message):
    with pytest.raises(TransformError, match=message):
        validate(envelope_to_frame(make_envelope(rates=rates)))


def test_validation_rejects_empty_frame():
    with pytest.raises(TransformError, match="No rate rows"):
        validate(pd.DataFrame(columns=["rate", "base_currency", "quote_currency"]))


def test_validation_rejects_duplicate_pairs():
    frame = envelope_to_frame(make_envelope())
    doubled = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)

    with pytest.raises(TransformError, match="duplicate"):
        validate(doubled)


def test_transform_writes_sorted_csv(settings, raw_file):
    out = transform(raw_file, settings)

    assert out == settings.clean_dir / "2024-01-15.csv"
    frame = pd.read_csv(out)
    assert list(frame["quote_currency"]) == ["EUR", "GBP", "JPY"]
    assert list(frame.columns) == [
        "as_of_date",
        "rate_date",
        "base_currency",
        "quote_currency",
        "rate",
        "extracted_at",
    ]
