import streamlit as st
import pandas as pd

from database import get_batch_types, get_metadata, get_transactions, import_batch
from ingestion import ingest_file

st.set_page_config(page_title='Receipt Processing Engine', layout='wide')
st.title('Receipt Processing Engine')
st.caption('Metadata-driven ingestion and SQL account allocation | Synthetic demo')
try:
    types = get_batch_types()
    type_id = st.selectbox('File configuration', list(types), format_func=types.get)
    metadata = get_metadata(type_id)
    with st.expander('Inspect JSON metadata'):
        st.json(metadata)
    file = st.file_uploader('Upload a sample statement', type=['csv', 'xlsx'])
    if file:
        df = ingest_file(file.getvalue(), file.name, metadata)
        st.subheader('Standardised transactions')
        st.dataframe(df, hide_index=True)
        if st.button('Import and allocate', type='primary'):
            st.session_state['batch_id'] = import_batch(type_id, file.name, df, metadata)
    if 'batch_id' in st.session_state:
        batch = st.session_state['batch_id']
        results = pd.DataFrame(get_transactions(batch))
        st.subheader(f'Allocation results — batch {batch}')
        cols = st.columns(3)
        for col, status in zip(cols, ['ALLOCATED', 'UNMATCHED', 'AMBIGUOUS']):
            col.metric(status.title(), int(results.allocation_status.eq(status).sum()))
        st.dataframe(results, hide_index=True)
except Exception as exc:
    st.error(str(exc))
