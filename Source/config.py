"""
**************************************************************************************************
@File : config.py
@Date
: 19/07/2026
@Version: 1.0
@Author: Ram
@Change History

Description: Configuration file
**************************************************************************************************
"""
from pathlib import Path
from datetime import datetime
from Source.logger import get_logger

logger = get_logger(__name__)
logger.info("Config Started")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
PROJECT_FOLDER= Path(__file__).resolve().parent.parent
OUTPUT_FOLDER = PROJECT_FOLDER / "output" / timestamp
RAW_DATA_FOLDER = OUTPUT_FOLDER / "raw"
CLEANED_FOLDER = OUTPUT_FOLDER / "cleaned"
TRANSFORMED_FOLDER = OUTPUT_FOLDER / "transformed"
FAILED_FOLDER = OUTPUT_FOLDER / "failed"
HASHED_FOLDER = OUTPUT_FOLDER / "hashed"


# data.gov.sg DATA COLLECTION HDB API

COLLECTION_ID = "189"
DATASTORE_SEARCH_API_URL = "https://data.gov.sg/api/action/datastore_search"
COLLECTION_API_METADATA_URL = (
    "https://api-production.data.gov.sg/v2/public/api/collections/{}/metadata"
)
DATASET_API_METADATA_URL = (
    "https://api-production.data.gov.sg/v2/public/api/datasets/{}/metadata"
)
# PAGINATION ASSIGNMENT

API_PAGE_LIMIT = 1000

# DATASET FROM  Jan 2012 TO Dec 2016
#
API_DATASETS = {
    "approval_2000_feb2012": {
        "dataset_id": "d_43f493c6c50d54243cc1eab0df142d6a",
        "name": "Resale Flat Prices (Approval Date), 2000 - Feb 2012",
        "date_filter_start": "2012-01",
        "date_filter_end": "2012-02",
    },
    "registration_mar2012_dec2014": {
        "dataset_id": "d_2d5ff9ea31397b66239f245f57751537",
        "name": "Resale Flat Prices (Registration Date), Mar 2012 - Dec 2014",
        "date_filter_start": "2012-03",
        "date_filter_end": "2014-12",
    },
    "registration_jan2015_dec2016": {
        "dataset_id": "d_ea9ed51da2787afaf8e51f827c304208",
        "name": "Resale Flat Prices (Registration Date), Jan 2015 - Dec 2016",
        "date_filter_start": "2015-01",
        "date_filter_end": "2016-12",
    },
}

# HDB TOTAL LEASE DECLARATION
HDB_LEASE_YEARS = 99

# DATE RANGE FROM START AND END

FROM_START_DATE = "2012-01"
TO_END_DATE = "2016-12"

# COMPOSITE KEY COLUMNS
COMPOSITE_KEY_COLUMNS = [
    "month",
    "town",
    "flat_type",
    "block",
    "street_name",
    "storey_range",
    "floor_area_sqm",
    "flat_model",
    "lease_commence_date",
    "remaining_lease",
]
logger.info("Config Ended")