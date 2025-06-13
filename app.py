import os
import io
import zipfile
from PIL import Image, ImageDraw, ImageFont
import srt
import pysubs2
from datetime import timedelta
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import streamlit as st

# Configuration (same as before)
CONFIG = {
    "IMAGE_WIDTH": 720,
    "IMAGE_HEIGHT": 480,
    "BG_COLOR": (0, 0, 255),
    "TEXT_COLOR": (255, 255, 255),
    "FONT_SIZE": 26,
    "FONT_PATH": "arial.ttf",  # Ensure font file is available
    "LINE_SPACING": 8,
    "MARGIN_BOTTOM": 36,
    "OUTPUT_NAME": None
}

# Keep all your existing functions (create_tiff, generate_sst, etc.)

def main():
    st.title("Subtitle to TIFF/SST Converter (Web Version)")
    st.write("Upload an SRT or SSA/ASS file to convert to TIFF images + SST.")

    # File uploader
    uploaded_file = st.file_uploader("Choose a subtitle file", type
