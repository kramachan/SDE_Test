"""
**************************************************************************************************
@File : extract_load.py
@Date
: 19/07/2026
@Version: 1.0
@Author: Ram
@Change History

Description: Data extraction from data.gov.sg public API.
**************************************************************************************************
"""


from __future__ import annotations
import pandas as pd
import requests
from typing import Any
import json
import time
from pathlib import Path
from Source.logger import get_logger

logger = get_logger(__name__)
logger.info("Extract Load Started")


from Source.config import (
    API_PAGE_LIMIT,
    API_DATASETS,
    DATASTORE_SEARCH_API_URL,
    RAW_DATA_FOLDER,
)


def ensure_output_dirs() -> None:
    """Create output directory structure if missing."""
    RAW_DATA_FOLDER.mkdir(parents=True, exist_ok=True)


def _month_range_list(start: str, end: str) -> list[str]:
    """Generate inclusive YYYY-MM strings between start and end."""
    months = pd.date_range(start=start, end=end, freq="MS")
    return [m.strftime("%Y-%m") for m in months]

logger.info("For each Load Started")
def fetch_dataset_page(
    dataset_id: str,
    offset: int = 0,
    limit: int = API_PAGE_LIMIT,
    filters: dict[str, str] | None = None,
    session: requests.Session | None = None,
    max_retries: int = 5,
) -> dict[str, Any]:
    """Fetch a single page of records from data.gov.sg datastore API."""
    client = session or requests
    params: dict[str, Any] = {
        "resource_id": dataset_id,
        "offset": offset,
        "limit": limit,
    }
    if filters:
        params["filters"] = json.dumps(filters)

    for attempt in range(max_retries):
        response = client.get(DATASTORE_SEARCH_API_URL, params=params, timeout=120)
        if response.status_code == 429:
            wait = 2 ** attempt
            time.sleep(wait)
            continue
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(f"API error for {dataset_id}: {payload}")
        return payload["result"]

    raise RuntimeError(f"Rate limited after {max_retries} retries for {dataset_id}")

logger.info("DownLoad  Dataset Started")
def download_dataset(
    dataset_id: str,
    name: str,
    date_filter_start: str | None = None,
    date_filter_end: str | None = None,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """
    Download dataset via paginated datastore_search API.

    When date filters are provided, fetches month-by-month to reduce payload
    and avoid rate limits on large historical datasets.
    """
    records: list[dict[str, Any]] = []

    if date_filter_start and date_filter_end:
        month_list = _month_range_list(date_filter_start, date_filter_end)
        for month in month_list:
            offset = 0
            while True:
                page = fetch_dataset_page(
                    dataset_id,
                    offset=offset,
                    filters={"month": month},
                    session=session,
                )
                batch = page["records"]
                records.extend(batch)
                if len(batch) < API_PAGE_LIMIT:
                    break
                offset += API_PAGE_LIMIT
                time.sleep(0.5)
            time.sleep(0.3)
    else:
        first = fetch_dataset_page(dataset_id, offset=0, session=session)
        total = int(first["total"])
        records = list(first["records"])
        offset = API_PAGE_LIMIT
        while offset < total:
            page = fetch_dataset_page(dataset_id, offset=offset, session=session)
            records.extend(page["records"])
            offset += API_PAGE_LIMIT
            time.sleep(0.5)

    df = pd.DataFrame(records)
    df.attrs["dataset_id"] = dataset_id
    df.attrs["dataset_name"] = name
    df.attrs["total_api_records"] = len(records)
    return df

logger.info("normalize_column_names Started")
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names across datasets."""
    rename_map = {}
    for col in df.columns:
        normalized = col.strip().lower().replace(" ", "_")
        if normalized in {"floor_area", "floor_area_sqm"}:
            rename_map[col] = "floor_area_sqm"
        elif normalized in {"lease_commencement_date", "lease_commence_date"}:
            rename_map[col] = "lease_commence_date"
        else:
            rename_map[col] = normalized
    return df.rename(columns=rename_map)

logger.info("filter_by_month_range Started")
def filter_by_month_range(
    df: pd.DataFrame, start: str | None, end: str | None
) -> pd.DataFrame:
    """Filter dataframe to inclusive YYYY-MM month range."""
    if start is None and end is None:
        return df.copy()
    out = df.copy()
    out["month"] = out["month"].astype(str).str.strip()
    if start:
        out = out[out["month"] >= start]
    if end:
        out = out[out["month"] <= end]
    return out

logger.info("save raw files")
def save_raw_files(datasets: dict[str, pd.DataFrame]) -> None:
    """Persist raw datasets as-is to output/raw/."""
    ensure_output_dirs()
    for key, df in datasets.items():
        path = RAW_DATA_FOLDER / f"{key}.csv"
        df.to_csv(path, index=False)


def extract_all(session: requests.Session | None = None) -> dict[str, pd.DataFrame]:
    """
    Extract all required datasets from data.gov.sg and save raw copies.

    Returns dict of raw dataframes keyed by dataset config key.
    """
    ensure_output_dirs()
    raw_datasets: dict[str, pd.DataFrame] = {}

    for key, meta in API_DATASETS.items():
        df = download_dataset(
            meta["dataset_id"],
            meta["name"],
            date_filter_start=meta.get("date_filter_start"),
            date_filter_end=meta.get("date_filter_end"),
            session=session,
        )
        df = normalize_column_names(df)

        # Drop internal API row id if present
        if "_id" in df.columns:
            df = df.drop(columns=["_id"])

        df = filter_by_month_range(
            df, meta.get("date_filter_start"), meta.get("date_filter_end")
        )
        df["source_dataset"] = key
        raw_datasets[key] = df

        # Save individual raw file
        df.to_csv(RAW_DATA_FOLDER / f"{key}.csv", index=False)

    return raw_datasets

logger.info("combine_raw_datasets files")
def combine_raw_datasets(raw_datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Combine datasets into master dataset with union of all attributes.

    Missing columns are filled with NaN so all attributes from all files appear.
    """
    frames = []
    all_columns: set[str] = set()

    for df in raw_datasets.values():
        all_columns.update(df.columns)

    ordered_columns = sorted(all_columns)

    for key, df in raw_datasets.items():
        aligned = df.reindex(columns=ordered_columns)
        frames.append(aligned)

    master = pd.concat(frames, ignore_index=True)
    master.attrs["combined_from"] = list(raw_datasets.keys())
    return master
logger.info("Extraction Load Ended")