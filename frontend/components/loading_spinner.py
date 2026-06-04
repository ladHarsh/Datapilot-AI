import streamlit as st
from contextlib import contextmanager


@contextmanager
def loading_spinner(message="Processing..."):

    with st.spinner(message):

        yield