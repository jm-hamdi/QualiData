# QualiData — Automated Data Quality Pipeline

QualiData is a web application that automatically detects, scores, and cleans structured data (CSV or Excel files). Upload a file, click Analyse, and receive a detailed quality report alongside a cleaned dataset — all in under a second. The pipeline handles duplicate removal, phone/email normalization, postal code padding, address abbreviation expansion, and city casing, while tracking quality improvements with before/after metrics for every column.

## Tech Stack

- **Flask** — lightweight Python web framework for the REST API and HTML serving
- **Pandas** — dataframe engine for all data transformations
- **openpyxl** — Excel file generation with styled headers and conditional color fills
- **Vanilla JS** — zero-dependency frontend with drag-and-drop, fetch API, and Blob downloads

## Features

- **Automatic cleaning** — removes exact duplicate rows, normalizes phones, emails, addresses, postal codes, cities, SIRET/SIREN numbers
- **Quality scoring** — each column receives a composite score based on three metrics:
  - **Completeness (40%)** — percentage of non-missing values
  - **Validity (40%)** — percentage of values matching the expected format for the detected type
  - **Uniqueness (20%)** — percentage of non-duplicated values
- **Excel deliverable with 3 sheets**:
  1. *Données nettoyées* — the cleaned dataset
  2. *Rapport qualité* — per-column quality metrics with color-coded scores
  3. *Résumé* — global key metrics summary
- **Web dashboard** — dark-themed single-page app with drag-and-drop upload, animated loading, score cards, change log, column quality table, and data preview

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python app.py
```

Then open your browser at [http://localhost:5000](http://localhost:5000).

Upload a `.csv` or `.xlsx` file, click **ANALYSER**, and download your cleaned data and quality report.

## Project Structure

```
QualiData/
├── app.py                  # Flask application & API routes
├── requirements.txt        # Python dependencies
├── sample_data.csv         # Example French customer data with quality issues
├── README.md
├── core/
│   ├── __init__.py
│   ├── cleaner.py          # Column type detection, normalizers, scoring, pipeline
│   └── reporter.py         # Excel, CSV, and JSON report generation
├── templates/
│   └── index.html          # Single-file dark-theme dashboard (HTML + CSS + JS)
├── static/
│   ├── css/
│   └── js/
├── uploads/                # Temporary upload storage
└── outputs/                # Generated report outputs
```

## How to Extend

- **BAN API integration** — query the French address validation API (api-adresse.data.gouv.fr) inside `normalize_address` to verify and standardize addresses against the official database
- **NLP for address correction** — integrate a fuzzy matching library (e.g. `rapidfuzz`) or a pre-trained NER model to detect and correct misspelled street names and city names
- **Docker deployment** — add a `Dockerfile` with `gunicorn` as the WSGI server and a `docker-compose.yml` for easy one-command deployment, replacing the in-memory `SESSION_STORE` with Redis for multi-worker support
