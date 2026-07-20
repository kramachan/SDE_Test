# HDB Resale Flat ETL Pipeline (2012–2016)

# Step 1:

Install required packages using requirements.txt

# Step 2: Run pipeline.py

Execute the pipeline

# Description

This project implements an end-to-end **Extract, Transform, and Load (ETL)** pipeline for processing **HDB resale flat transaction datasets** obtained from the Singapore Government Open Data portal (data.gov.sg).

The solution has been developed to support the **Data Science Team** by providing a high-quality, validated, and transformed dataset for downstream analytics and machine learning.

The implementation follows software engineering best practices and is designed to be:

- Fully automated
- Modular
- Maintainable
- Scalable
- Reproducible
- Well documented

No manual preprocessing or modification of the downloaded datasets is required.

# Project Objectives

The ETL pipeline satisfies all assignment requirements by:

- Automatically downloading HDB resale datasets from **January 2012 to December 2016**
- Combining all yearly datasets into a single master dataset
- Performing automated data profiling
- Applying configurable data quality validation rules
- Detecting duplicate records
- Computing the remaining lease as of today
- Identifying anomalous resale prices
- Transforming business attributes
- Generating a unique Resale Identifier
- Applying irreversible hashing while preserving uniqueness
- Producing cleaned, transformed and failed datasets


# Future Enhancements

- Apache Spark implementation for large datasets
- Apache Airflow workflow orchestration
- AWS Glue integration
- Delta Lake support
- Docker containerization
- CI/CD using GitHub Actions
- Unit testing with pytest
- Data quality dashboards
- Cloud deployment on AWS

# Author
Ram