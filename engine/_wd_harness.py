"""Tiny harness so streamlit AppTest can exercise wd_app.render() in isolation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wd_app  # noqa: E402

wd_app.render()
