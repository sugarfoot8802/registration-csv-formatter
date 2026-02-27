# Registration CSV Formatter (Streamlit)

A small web app that converts messy registration CSV exports into a strict upload-ready CSV.

## What it does
- Upload a CSV
- Auto-detects the source schema by headers
- Applies locked business rules (manager → coach → placeholder, postal rules, etc.)
- Downloads a clean CSV in the exact required column order
- Shows errors/warnings inline

## Files
- `app.py` – Streamlit UI
- `transformer.py` – Transformation rules + schema detection
- `requirements.txt` – Python dependencies

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy in 5 minutes on Streamlit Community Cloud (free)
1. Create a GitHub repo and add these files: `app.py`, `transformer.py`, `requirements.txt`.
2. Go to Streamlit Community Cloud and click **New app**.
3. Select your repo.
4. Set **Main file path** to `app.py`.
5. Click **Deploy**.

That’s it — you’ll get a shareable URL.

## Notes
- Input must be CSV. (Easy to add XLSX support later if desired.)
- `external_id` is always blank by design.
