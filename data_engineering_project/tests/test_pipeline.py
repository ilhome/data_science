from __future__ import annotations

from pathlib import Path

from data_engineering_project.pipeline import run_pipeline


def test_run_pipeline_creates_outputs(tmp_path: Path) -> None:
    raw_file = Path("data/raw/sales.csv")
    output_dir = tmp_path / "curated"

    result = run_pipeline(raw_file, output_dir)

    assert result["cleaned_data"].exists()
    assert result["daily_metrics"].exists()
    assert output_dir.exists()
