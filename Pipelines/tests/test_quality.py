from __future__ import annotations

import json
from datetime import date

import pytest
import sqlalchemy as sa

from pipelines.load import fx_rates, get_engine, load
from pipelines.quality import QualityCheckError, check_partition, find_problems
from pipelines.transform import transform
from tests.conftest import AS_OF, make_envelope


def test_find_problems_is_empty_for_healthy_partition():
    assert find_problems({"rows": 3, "non_positive": 0, "distinct_quotes": 3}, 3) == []


@pytest.mark.parametrize(
    "health, expected, message",
    [
        ({"rows": 0, "non_positive": 0, "distinct_quotes": 0}, 3, "no rows landed"),
        ({"rows": 2, "non_positive": 0, "distinct_quotes": 2}, 3, "expected 3 rows, found 2"),
        ({"rows": 3, "non_positive": 1, "distinct_quotes": 3}, 3, "non-positive"),
        ({"rows": 3, "non_positive": 0, "distinct_quotes": 2}, 3, "duplicate"),
    ],
)
def test_find_problems_names_each_violation(health, expected, message):
    assert any(message in p for p in find_problems(health, expected))


def test_check_partition_passes_after_load(settings, raw_file):
    rows = load(transform(raw_file, settings), settings)

    health = check_partition(get_engine(settings), AS_OF, "USD", rows)

    assert health["rows"] == 3


def test_check_partition_fails_when_rows_are_missing(settings, raw_file):
    load(transform(raw_file, settings), settings)

    with pytest.raises(QualityCheckError, match="expected 4 rows, found 3"):
        check_partition(get_engine(settings), AS_OF, "USD", 4)


def test_check_partition_catches_bad_data_written_behind_its_back(settings, raw_file):
    engine = get_engine(settings)
    load(transform(raw_file, settings), settings)
    with engine.begin() as conn:
        conn.execute(sa.update(fx_rates).where(fx_rates.c.quote_currency == "EUR").values(rate=-1))

    with pytest.raises(QualityCheckError, match="non-positive"):
        check_partition(engine, AS_OF, "USD", 3)


def test_check_partition_fails_for_empty_day(settings, raw_file):
    load(transform(raw_file, settings), settings)
    settings.raw_dir.joinpath("2024-01-16.json").write_text(json.dumps(make_envelope()))

    with pytest.raises(QualityCheckError, match="no rows landed"):
        check_partition(get_engine(settings), date(2024, 1, 16), "USD", 3)
