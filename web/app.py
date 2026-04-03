import asyncio

import streamlit as st

from research.flow import run_research
from research.schemas import ResearchRequest

st.set_page_config(page_title="Deep Research", layout="wide")
st.title("OpenClaw Deep Research")

query = st.text_input("Research query")
depth = st.slider("Depth", min_value=1, max_value=5, value=2)

if st.button("Run") and query.strip():
    with st.spinner("Researching..."):
        response = asyncio.run(run_research(ResearchRequest(query=query, depth=depth)))

    st.subheader("Summary")
    st.write(response.summary)

    st.subheader("Sources")
    for source in response.sources:
        st.markdown(f"- [{source.title}]({source.url})")
        st.caption(source.snippet)
