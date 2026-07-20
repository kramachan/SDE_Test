
"""
**************************************************************************************************
@File : validate.py
@Date
: 19/07/2026
@Version: 1.0
@Author: Ram
@Change History

Description: Data profiling, validation, duplicate removing, 99 years balance lease calculation and cleaning logic
**************************************************************************************************
"""


from __future__ import annotations
from Source.config import COMPOSITE_KEY_COLUMNS, HDB_LEASE_YEARS, TO_END_DATE, FROM_START_DATE
import numpy as np
import pandas as pd
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from Source.logger import get_logger

logger = get_logger(__name__)
logger.info("Validate Started")

@dataclass
class ValidationResult:
    """Container for validation outcomes."""

    passed: pd.DataFrame
    failed: pd.DataFrame
    profile_report: dict[str, Any] = field(default_factory=dict)
    validation_rules: dict[str, Any] = field(default_factory=dict)

logger.info("Perform Data Profiling on the dataset Started")
def profile_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """
    2. Perform Data Profiling on the dataset. I am giving my own profiling rules or leverage on
        open-source data quality frameworks.
    """
    report: dict[str, Any] = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "null_counts": df.isnull().sum().to_dict(),
        "null_percentages": (df.isnull().mean() * 100).round(2).to_dict(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "duplicate_rows": int(df.duplicated().sum()),
    }

    categorical_cols = ["town", "flat_type", "flat_model", "storey_range"]
    report["cardinality"] = {
        col: int(df[col].nunique(dropna=True))
        for col in categorical_cols
        if col in df.columns
    }

    if "resale_price" in df.columns:
        price = pd.to_numeric(df["resale_price"], errors="coerce")
        report["resale_price_stats"] = {
            "min": float(price.min()),
            "max": float(price.max()),
            "mean": float(price.mean()),
            "median": float(price.median()),
            "std": float(price.std()),
            "q1": float(price.quantile(0.25)),
            "q3": float(price.quantile(0.75)),
        }

    if "month" in df.columns:
        months = df["month"].astype(str).str.strip()
        report["month_range"] = {"min": months.min(), "max": months.max()}

    return report

logger.info("Validate the following fields (i.e. Date, Town, Flat Type, FlatModel, storey_range) ")
def derive_validation_rules(df: pd.DataFrame) -> dict[str, Any]:
    """
    3. Design data validation rules to validate the following fields (i.e. Date, Town, Flat Type, Flat
        Model, storey_range) based on the statistical properties of this master dataset.
    """
    rules: dict[str, Any] = {}

    # Date / Month validation
    month_pattern = re.compile(r"^\d{4}-\d{2}$")
    valid_months = df["month"].astype(str).str.match(month_pattern)
    rules["month"] = {
        "description": "Month must be YYYY-MM format within 2012-01 to 2016-12",
        "pattern": month_pattern.pattern,
        "allowed_range": [FROM_START_DATE, TO_END_DATE],
        "valid_count": int(valid_months.sum()),
        "invalid_count": int((~valid_months).sum()),
    }

    # Town: must be non-null and in observed set (99.9% coverage heuristic)
    observed_towns = sorted(df["town"].dropna().astype(str).str.strip().unique())
    rules["town"] = {
        "description": "Town must be non-null and match known HDB towns in dataset",
        "allowed_values": observed_towns,
        "allowed_count": len(observed_towns),
    }

    # Flat Type
    observed_flat_types = sorted(
        df["flat_type"].dropna().astype(str).str.strip().unique()
    )
    rules["flat_type"] = {
        "description": "Flat type must match known categories in dataset",
        "allowed_values": observed_flat_types,
    }

    # Flat Model
    observed_models = sorted(
        df["flat_model"].dropna().astype(str).str.strip().unique()
    )
    rules["flat_model"] = {
        "description": "Flat model must match known categories in dataset",
        "allowed_values": observed_models,
    }

    # Storey Range: pattern like "01 TO 03" or "10 TO 12"
    storey_pattern = re.compile(r"^\d{2}\sTO\s\d{2}$", re.IGNORECASE)
    rules["storey_range"] = {
        "description": "Storey range must match NN TO NN pattern",
        "pattern": storey_pattern.pattern,
        "observed_values": sorted(
            df["storey_range"].dropna().astype(str).str.strip().unique()
        ),
    }

    return rules

logger.info("compute_remaining_lease Started ")
def compute_remaining_lease(
    df: pd.DataFrame, reference_date: date | None = None
) -> pd.DataFrame:
    """
    4. Assume HDB lease is 99 years old, recompute remaining lease as of today. Remaining lease
        should be rounded down to Years and Months.
    """
    ref = reference_date or date.today()
    out = df.copy()

    lease_year = pd.to_numeric(out["lease_commence_date"], errors="coerce")
    lease_start = pd.to_datetime(lease_year.astype("Int64").astype(str) + "-01-01")
    lease_end = lease_start + pd.DateOffset(years=HDB_LEASE_YEARS)

    ref_ts = pd.Timestamp(ref)
    remaining_days = (lease_end - ref_ts).dt.days
    remaining_days = remaining_days.clip(lower=0)

    total_months = (remaining_days // 30).astype("Int64")  # floor approximation
    # More precise: use date arithmetic
    years = []
    months = []
    for end, start_y in zip(lease_end, lease_year):
        if pd.isna(end) or pd.isna(start_y):
            years.append(np.nan)
            months.append(np.nan)
            continue
        end_date = end.date() if hasattr(end, "date") else end
        if end_date <= ref:
            years.append(0)
            months.append(0)
            continue
        total_m = (end_date.year - ref.year) * 12 + (end_date.month - ref.month)
        if end_date.day < ref.day:
            total_m -= 1
        total_m = max(total_m, 0)
        years.append(total_m // 12)
        months.append(total_m % 12)

    out["remaining_lease_years"] = years
    out["remaining_lease_months"] = months
    out["remaining_lease_recomputed"] = [
        f"{y} years {m} months" if pd.notna(y) else np.nan
        for y, m in zip(years, months)
    ]
    return out

logger.info("Apply validation logic  ")
def apply_validation_rules(
    df: pd.DataFrame, rules: dict[str, Any]
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Apply validation rules; return boolean pass mask and failure reason column.
    """
    reasons: list[list[str]] = [[] for _ in range(len(df))]

    def add_failure(mask: pd.Series, reason: str) -> None:
        indices = mask[mask].index
        for idx in indices:
            pos = df.index.get_loc(idx)
            reasons[pos].append(reason)

    # Month validation
    month_str = df["month"].astype(str).str.strip()
    month_valid = month_str.str.match(r"^\d{4}-\d{2}$")
    month_in_range = (month_str >= FROM_START_DATE) & (month_str <= TO_END_DATE)
    month_ok = month_valid & month_in_range
    add_failure(~month_ok, "invalid_month")

    # Town
    allowed_towns = set(rules["town"]["allowed_values"])
    town_ok = df["town"].astype(str).str.strip().isin(allowed_towns)
    add_failure(~town_ok, "invalid_town")

    # Flat type
    allowed_types = set(rules["flat_type"]["allowed_values"])
    flat_type_ok = df["flat_type"].astype(str).str.strip().isin(allowed_types)
    add_failure(~flat_type_ok, "invalid_flat_type")

    # Flat model
    allowed_models = set(rules["flat_model"]["allowed_values"])
    flat_model_ok = df["flat_model"].astype(str).str.strip().isin(allowed_models)
    add_failure(~flat_model_ok, "invalid_flat_model")

    # Storey range
    storey_ok = (
        df["storey_range"]
        .astype(str)
        .str.strip()
        .str.match(r"^\d{2}\sTO\s\d{2}$", case=False, na=False)
    )
    add_failure(~storey_ok, "invalid_storey_range")

    # Additional cleaning rules
    price = pd.to_numeric(df["resale_price"], errors="coerce")
    price_ok = price.notna() & (price > 0)
    add_failure(~price_ok, "invalid_resale_price")

    floor_area = pd.to_numeric(df["floor_area_sqm"], errors="coerce")
    floor_ok = floor_area.notna() & (floor_area > 0)
    add_failure(~floor_ok, "invalid_floor_area")

    lease_ok = pd.to_numeric(df["lease_commence_date"], errors="coerce").notna()
    add_failure(~lease_ok, "invalid_lease_commence_date")

    pass_mask = pd.Series([len(r) == 0 for r in reasons], index=df.index)
    reason_df = pd.DataFrame({"failure_reason": ["; ".join(r) if r else "" for r in reasons]})
    return pass_mask, reason_df

logger.info("Find detect_price_anomalies Started ")
def detect_price_anomalies(
    df: pd.DataFrame,
    iqr_multiplier: float = 3.0,
    min_price: float = 50000,
    max_price: float = 2000000,
) -> tuple[pd.Series, dict[str, Any]]:
    """
    Detect anomalous resale prices using documented heuristics.

    Heuristics:
    1. Global IQR: price outside [Q1 - 3*IQR, Q3 + 3*IQR] flagged as outlier
    2. Segment IQR: same rule within (town, flat_type) groups with n>=30
    3. Absolute bounds: price < $50,000 or > $2,000,000 (unlikely for HDB resale)
    4. Price per sqm: outside segment 3*IQR for (town, flat_type)

    Assumptions documented in returned metadata dict.
    """
    price = pd.to_numeric(df["resale_price"], errors="coerce")
    floor_area = pd.to_numeric(df["floor_area_sqm"], errors="coerce")
    price_per_sqm = price / floor_area

    anomaly = pd.Series(False, index=df.index)
    reasons: list[str] = [""] * len(df)

    # Global IQR
    q1, q3 = price.quantile(0.25), price.quantile(0.75)
    iqr = q3 - q1
    global_low = q1 - iqr_multiplier * iqr
    global_high = q3 + iqr_multiplier * iqr
    global_outlier = (price < global_low) | (price > global_high)

    # Absolute bounds
    abs_outlier = (price < min_price) | (price > max_price)

    # Segment-level
    segment_outlier = pd.Series(False, index=df.index)
    pps_outlier = pd.Series(False, index=df.index)
    group_cols = ["town", "flat_type"]
    for keys, group in df.groupby(group_cols):
        if len(group) < 30:
            continue
        gp = pd.to_numeric(group["resale_price"], errors="coerce")
        gq1, gq3 = gp.quantile(0.25), gp.quantile(0.75)
        giqr = gq3 - gq1
        seg_mask = (gp < gq1 - iqr_multiplier * giqr) | (
            gp > gq3 + iqr_multiplier * giqr
        )
        segment_outlier.loc[group.index[seg_mask.fillna(False)]] = True

        pps = gp / pd.to_numeric(group["floor_area_sqm"], errors="coerce")
        pq1, pq3 = pps.quantile(0.25), pps.quantile(0.75)
        piqr = pq3 - pq1
        pps_mask = (pps < pq1 - iqr_multiplier * piqr) | (
            pps > pq3 + iqr_multiplier * piqr
        )
        pps_outlier.loc[group.index[pps_mask.fillna(False)]] = True

    for i, idx in enumerate(df.index):
        r = []
        if global_outlier.loc[idx]:
            r.append("global_iqr_outlier")
        if abs_outlier.loc[idx]:
            r.append("absolute_bounds")
        if segment_outlier.loc[idx]:
            r.append("segment_iqr_outlier")
        if pps_outlier.loc[idx]:
            r.append("price_per_sqm_outlier")
        if r:
            anomaly.loc[idx] = True
            reasons[i] = "; ".join(r)

    metadata = {
        "heuristics": [
            f"Global IQR with multiplier={iqr_multiplier}",
            f"Segment IQR within (town, flat_type) where n>=30",
            f"Absolute bounds: ${min_price:,} - ${max_price:,}",
            "Price per sqm segment IQR outlier",
        ],
        "assumptions": [
            "HDB resale prices are generally right-skewed; 3*IQR is conservative",
            "Small segments (<30) use global rules only",
            "Anomalies are flagged for review; dataset may contain none",
        ],
        "global_iqr_bounds": [float(global_low), float(global_high)],
        "anomaly_count": int(anomaly.sum()),
    }

    return anomaly, {**metadata, "anomaly_reasons": reasons}

logger.info("Find deduplicate_composite_key Started ")
def deduplicate_composite_key(
    df: pd.DataFrame,
    key_columns: list[str],
    price_column: str = "resale_price",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Deduplicate by composite key; keep highest price, send lower to failed.

    Composite key = all columns except resale_price (per assignment spec).
    """
    available_keys = [c for c in key_columns if c in df.columns and c != price_column]
    work = df.copy()
    work[price_column] = pd.to_numeric(work[price_column], errors="coerce")

    # Identify duplicate groups
    dup_mask = work.duplicated(subset=available_keys, keep=False)
    failed_records = []

    if dup_mask.any():
        dup_groups = work[dup_mask].groupby(available_keys, dropna=False)
        keep_indices = []
        for _, group in dup_groups:
            sorted_g = group.sort_values(price_column, ascending=False)
            keep_indices.append(sorted_g.index[0])
            if len(sorted_g) > 1:
                losers = sorted_g.iloc[1:].copy()
                losers["failure_reason"] = "duplicate_composite_key_lower_price"
                failed_records.append(losers)

        # Non-duplicate rows
        non_dup = work[~dup_mask]
        kept_dup = work.loc[keep_indices]
        cleaned = pd.concat([non_dup, kept_dup], ignore_index=False)
    else:
        cleaned = work

    failed = pd.concat(failed_records, ignore_index=True) if failed_records else pd.DataFrame()
    return cleaned.reset_index(drop=True), failed.reset_index(drop=True)

logger.info("Execute full data quality pipeline")
def run_quality_pipeline(
    master: pd.DataFrame,
    reference_date: date | None = None,
    flag_anomalies: bool = True,
) -> ValidationResult:
    """Execute full data quality pipeline."""
    profile = profile_dataset(master)
    rules = derive_validation_rules(master)

    # Compute remaining lease
    with_lease = compute_remaining_lease(master, reference_date=reference_date)

    # Validation
    pass_mask, reason_df = apply_validation_rules(with_lease, rules)
    validated = with_lease[pass_mask].copy().reset_index(drop=True)
    validation_failed = with_lease[~pass_mask].copy().reset_index(drop=True)
    validation_failed["failure_reason"] = reason_df[~pass_mask]["failure_reason"].values

    # Anomaly detection (demonstrate mechanism; optionally move to failed)
    anomaly_mask, anomaly_meta = detect_price_anomalies(validated)
    profile["anomaly_detection"] = anomaly_meta
    validated["is_price_anomaly"] = anomaly_mask.values

    if flag_anomalies and anomaly_mask.any():
        anomaly_failed = validated[anomaly_mask].copy()
        anomaly_failed["failure_reason"] = [
            anomaly_meta["anomaly_reasons"][i]
            for i in range(len(validated))
            if anomaly_mask.iloc[i]
        ]
        validated = validated[~anomaly_mask].copy()
    else:
        anomaly_failed = pd.DataFrame()

    # Composite key deduplication (all source columns except resale_price)
    cleaned, dup_failed = deduplicate_composite_key(
        validated, COMPOSITE_KEY_COLUMNS
    )

    failed_parts = [validation_failed, anomaly_failed, dup_failed]
    failed = pd.concat([f for f in failed_parts if len(f) > 0], ignore_index=True)

    return ValidationResult(
        passed=cleaned,
        failed=failed,
        profile_report=profile,
        validation_rules=rules,
    )
logger.info("Validation Ended")