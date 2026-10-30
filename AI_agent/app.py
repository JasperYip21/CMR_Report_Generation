#%%
# A simple Streamlit interface for your agent
import streamlit as st
import pandas as pd
from test import parse_cvi42_report  # Your parsing function

st.title("cvi42 Data Extraction & QC Agent")

uploaded_files = st.file_uploader(
    "Upload cvi42 Text Reports", type=["txt"], accept_multiple_files=True
)

if uploaded_files:
    results = []
    for file in uploaded_files:
        # Read file content handling UTF-16
        content = file.read().decode("utf-16", errors="ignore")
        parsed = parse_cvi42_report(content)
        parsed["filename"] = file.name
        results.append(parsed)

    df = pd.json_normalize(results)

    st.subheader("Extracted Metrics")
    st.dataframe(df)

    # Download ready-to-use CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Clean CSV for Statistics", csv, "cvi42_extracted.csv"
    )