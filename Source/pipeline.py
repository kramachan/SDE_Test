from __future__ import annotations
from Source.logger import get_logger

logger = get_logger(__name__)
import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from Source.config import (
    CLEANED_FOLDER,
    FAILED_FOLDER,
    HASHED_FOLDER,
    OUTPUT_FOLDER,
    RAW_DATA_FOLDER,
    TRANSFORMED_FOLDER,
)
from Source.extract_load import combine_raw_datasets, extract_all
from Source.validate import run_quality_pipeline
from Source.transformation import add_hashed_column, transform_dataset


def ensure_all_dirs() -> None:
    """Create all output subdirectories."""
    for d in [RAW_DATA_FOLDER, CLEANED_FOLDER, TRANSFORMED_FOLDER, FAILED_FOLDER, HASHED_FOLDER]:
        d.mkdir(parents=True, exist_ok=True)

logger.info("Running Pipeline Started")

def run_pipeline(
    reference_date: date | None = None,
    flag_anomalies: bool = False,
) -> dict[str, pd.DataFrame | dict]:
    """
    Execute complete ETL pipeline and write output files.

    Parameters
    ----------
    reference_date : date, optional
        Reference date for remaining lease computation (default: today).
    flag_anomalies : bool
        If True, move price anomalies to failed dataset. Default False to
        retain data while still flagging anomalies in profile report.

    Returns
    -------
    dict with keys: raw, master, cleaned, transformed, failed, hashed, metadata
    """
    ensure_all_dirs()
    session = requests.Session()
    session.headers.update({"User-Agent": "HDB-ETL-Pipeline/1.0"})

    # Extract
    raw_datasets = extract_all(session=session)
    master = combine_raw_datasets(raw_datasets)
    master.to_csv(RAW_DATA_FOLDER / "master_combined.csv", index=False)

    # Quality
    quality_result = run_quality_pipeline(
        master,
        reference_date=reference_date,
        flag_anomalies=flag_anomalies,
    )
    cleaned = quality_result.passed
    failed_quality = quality_result.failed

    cleaned.to_csv(CLEANED_FOLDER / "hdb_resale_cleaned.csv", index=False)
    if len(failed_quality) > 0:
        failed_quality.to_csv(FAILED_FOLDER / "failed_quality.csv", index=False)

    # Transform
    transformed, failed_transform = transform_dataset(cleaned)
    transformed.to_csv(TRANSFORMED_FOLDER / "hdb_resale_transformed.csv", index=False)

    # Combine all failed
    failed_parts = [failed_quality, failed_transform]
    all_failed = pd.concat(
        [f for f in failed_parts if len(f) > 0], ignore_index=True
    )
    if len(all_failed) > 0:
        all_failed.to_csv(FAILED_FOLDER / "hdb_resale_failed.csv", index=False)

    # Hashed
    hashed = add_hashed_column(transformed)
    hashed.to_csv(HASHED_FOLDER / "hdb_resale_hashed.csv", index=False)

    # Metadata / profiling report
    metadata = {
        "profile_report": quality_result.profile_report,
        "validation_rules": quality_result.validation_rules,
        "output_counts": {
            "API_RAW_RECORD_COUNT": len(master),
            "CLEANED_RECORD_COUNT": len(cleaned),
            "TRANSFORMED_RECORD_COUNT": len(transformed),
            "FAILED_RECORD_COUNT": len(all_failed),
            "HASHED_RECORD_COUNT": len(hashed),
        },
    }
    metadata_path = OUTPUT_FOLDER / "HDB_pipeline_metadata.json"

    def json_serializer(obj):
        if isinstance(obj, (pd.Timestamp, date)):
            return str(obj)
        if hasattr(obj, "item"):
            return obj.item()
        raise TypeError(f"Not serializable: {type(obj)}")

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=json_serializer)

    return {
        "raw": master,
        "cleaned": cleaned,
        "transformed": transformed,
        "failed": all_failed,
        "hashed": hashed,
        "metadata": metadata,
    }


if __name__ == "__main__":
    results = run_pipeline()
    counts = results["metadata"]["output_counts"]
    print("Pipeline completed successfully.")
    logger.info("Pipeline completed successfully.")
    for k, v in counts.items():
        print(f"  {k}: {v}")
