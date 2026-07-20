
"""
**************************************************************************************************
@File : transformation.py
@Date
: 19/07/2026
@Version: 1.0
@Author: Ram
@Change History

Description: Data transformation: Resale Identifier generation and hashing
**************************************************************************************************
"""

from __future__ import annotations

import hashlib
import re

import pandas as pd
from Source.logger import get_logger

logger = get_logger(__name__)
logger.info("transformation Started")
logger.info("Resale Identifier generation Started")

def extract_block_digits(block: str) -> str:
    """
    Extract first 3 digits from block column after removing non-digits.

    Pad with leading zeros if fewer than 3 digits (e.g. '19' -> '019').
    """
    digits = re.sub(r"\D", "", str(block))
    if not digits:
        return "000"
    return digits[:3].zfill(3)


def compute_price_digits(df: pd.DataFrame) -> pd.Series:
    """
    Compute 2-digit price component from average resale price.

    Grouped by year-month, town, flat_type; take 1st and 2nd digit of
    integer average price (e.g. $230000 -> '23').
    """
    work = df.copy()
    work["resale_price"] = pd.to_numeric(work["resale_price"], errors="coerce")
    work["year_month"] = work["month"].astype(str).str.strip()

    avg_prices = (
        work.groupby(["year_month", "town", "flat_type"], dropna=False)["resale_price"]
        .transform("mean")
        .astype(int)
        .astype(str)
    )

    def first_two_digits(price_str: str) -> str:
        digits = re.sub(r"\D", "", price_str)
        if len(digits) >= 2:
            return digits[:2]
        return digits.zfill(2)

    return avg_prices.map(first_two_digits)

logger.info("build_resale_identifier Started")
def build_resale_identifier(df: pd.DataFrame) -> pd.Series:
    """
    Build Resale Identifier per assignment specification.

    Format: S + 3 block digits + 2 price digits + 2 month digits + town initial
    Example: S0192301A for block 19, avg price ~$230k, Jan, Ang Mo Kio
    """
    block_part = df["block"].map(extract_block_digits)
    price_part = compute_price_digits(df)
    month_part = df["month"].astype(str).str.strip().str[-2:]
    town_initial = df["town"].astype(str).str.strip().str[0].str.upper()

    identifier = (
        "S" + block_part + price_part + month_part + town_initial
    )
    return identifier

logger.info("hash_identifier Started")
def hash_identifier(
    identifiers: pd.Series,
    algorithm: str = "sha256",
) -> pd.Series:
    """
    Hash resale identifiers using irreversible SHA-256.

    SHA-256 is a cryptographic one-way hash function producing a 64-char hex
    digest. Collision resistance preserves uniqueness for distinct identifiers.
    Same identifier always produces same hash (deterministic).
    """
    if algorithm != "sha256":
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    return identifiers.astype(str).map(_hash)

logger.info("transform_dataset Started")
def transform_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply transformation requirements.

    1. Create Resale Identifier
    2. Deduplicate by identifier keeping higher price
    3. Return transformed dataset and failed duplicates
    """
    work = df.copy()
    work["resale_identifier"] = build_resale_identifier(work)
    work["resale_price"] = pd.to_numeric(work["resale_price"], errors="coerce")

    # Deduplicate by resale_identifier
    dup_mask = work.duplicated(subset=["resale_identifier"], keep=False)
    failed_records = []

    if dup_mask.any():
        keep_indices = []
        for _, group in work[dup_mask].groupby("resale_identifier"):
            sorted_g = group.sort_values("resale_price", ascending=False)
            keep_indices.append(sorted_g.index[0])
            if len(sorted_g) > 1:
                losers = sorted_g.iloc[1:].copy()
                losers["failure_reason"] = "duplicate_resale_identifier_lower_price"
                failed_records.append(losers)
        non_dup = work[~dup_mask]
        kept = work.loc[keep_indices]
        transformed = pd.concat([non_dup, kept], ignore_index=False)
    else:
        transformed = work

    failed = (
        pd.concat(failed_records, ignore_index=True)
        if failed_records
        else pd.DataFrame()
    )
    return transformed.reset_index(drop=True), failed.reset_index(drop=True)


def add_hashed_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add hashed resale identifier to cleaned+transformed data."""
    out = df.copy()
    if "resale_identifier" not in out.columns:
        out["resale_identifier"] = build_resale_identifier(out)
    out["resale_identifier_hash"] = hash_identifier(out["resale_identifier"])
    return out
logger.info("transformation Ended")