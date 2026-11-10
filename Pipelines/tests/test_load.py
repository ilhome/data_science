from __future__ import annotations

import json
from datetime import date

import pytest

from pipelines.load import count_rows, get_engine, load, partition_health
from pipelines.transform import transform
from tests.conftest import AS_OF, make_envelope


@pytest.fixture
def clean_file(settings, raw_file):
    return transform(raw_file, settings)


def test_load_creates_table_and_inserts_rows(settings, clean_file):
    rows = load(clean_file, settings)

    engine = get_engine(settings)
    assert rows == 3
    assert count_rows(engine, AS_OF, "USD") == 3
    assert partition_health(engine, AS_OF, "USD") == {
        "rows": 3,
        "non_positive": 0,
        "distinct_quotes": 3,
    }


def test_reload_replaces_partition_without_duplicates(settings, clean_file):
    load(clean_file, settings)

    # Second run for the same day brings a corrected EUR rate and drops JPY.
    settings.raw_dir.joinpath("2024-01-15.json").write_text(
        json.dumps(make_envelope(rates={"EUR": 0.9, "GBP": 0.8}))
    )
    clean_again = transform(settings.raw_dir / "2024-01-15.json", settings)
    rows = load(clean_again, settings)

    engine = get_engine(settings)
    assert rows == 2
    assert count_rows(engine, AS_OF, "USD") == 2


def test_other_partitions_are_untouched(settings, clean_file):
    load(clean_file, settings)

    other = make_envelope()
    other["as_of_date"] = "2024-01-16"
    settings.raw_dir.joinpath("2024-01-16.json").write_text(json.dumps(other))
    load(transform(settings.raw_dir / "2024-01-16.json", settings), settings)

    engine = get_engine(settings)
    assert count_rows(engine, AS_OF, "USD") == 3
    assert count_rows(engine, date(2024, 1, 16), "USD") == 3


def test_empty_partition_reports_zero(settings):
    engine = get_engine(settings)
    from pipelines.load import ensure_schema

    ensure_schema(engine)
    assert partition_health(engine, date(2030, 1, 1), "USD")["rows"] == 0
