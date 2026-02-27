import io
import streamlit as st
import pandas as pd

from transformer import transform_dataframe

st.set_page_config(page_title="Registration CSV Formatter", layout="wide")

st.title("Registration CSV Formatter")
st.caption("Upload a raw registration CSV and download an upload-ready CSV in the required format.")

uploaded = st.file_uploader("Upload CSV", type=["csv"])

col1, col2 = st.columns([1, 1])

with col1:
    run = st.button("Convert", type="primary", disabled=uploaded is None)

if uploaded is not None and run:
    try:
        raw_bytes = uploaded.read()
        # Robust read: try utf-8 then fallback
        try:
            df_raw = pd.read_csv(io.BytesIO(raw_bytes))
        except UnicodeDecodeError:
            df_raw = pd.read_csv(io.BytesIO(raw_bytes), encoding="latin-1")

        cleaned_df, errors, summary, mapping = transform_dataframe(df_raw)

        st.subheader("Download")
        csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download cleaned CSV",
            data=csv_bytes,
            file_name="cleaned_registration_upload.csv",
            mime="text/csv",
        )

        st.subheader("Summary")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Rows processed", summary.get("rows", 0))
        s2.metric("Placeholders used (A–D)", summary.get("placeholder_primary_rows", 0))
        s3.metric("Coach blanked (H–K)", summary.get("coach_blanked_rows", 0))
        s4.metric("Invalid mobiles fixed", summary.get("invalid_mobile_fixed_rows", 0))

        with st.expander("Detected mapping (how your columns were interpreted)", expanded=False):
            st.json(mapping)

        st.subheader("Errors / Warnings")
        if not errors:
            st.success("No errors found.")
        else:
            st.warning(f"{len(errors)} issue(s) found.")
            st.write("\n".join(f"- {e}" for e in errors))

        st.subheader("Preview (first 50 rows)")
        st.dataframe(cleaned_df.head(50), use_container_width=True)

    except Exception as e:
        st.error(f"Failed to process file: {e}")
        st.exception(e)

with col2:
    st.markdown("### Locked Rules (high level)")
    st.markdown(
        """
- Output columns are fixed (template order)
- **external_id is always blank**
- Primary contact A–D: **Manager → Coach → Placeholder**
- Mobile must be **10 digits**, else `8888888888`
- If mobile is `8888888888`, then **country = US** and **postal_code = 90210**
- Postal code never blank: US **5 digits**; CA **A1A 1A1**; fallback **90210**
- Coach fields H–K blanked if:
  - coach email equals primary email, **or**
  - full A–D matches full H–K
- If coach_first_name exists but coach_last_name or coach_email missing → coach group is blanked
"""
    )
