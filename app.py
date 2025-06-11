from flask import Flask, request, send_file
from PIL import Image, ImageDraw, ImageFont
import srt
import io
import zipfile
import os
from arabic_reshaper import reshape
from bidi.algorithm import get_display

app = Flask(__name__)

# Configuration
IMAGE_WIDTH = 720
IMAGE_HEIGHT = 480
BG_COLOR = (0, 0, 255)  # Blue background
TEXT_COLOR = (255, 255, 255)  # White text
FONT_SIZE = 26
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

# Font handling with fallback
try:
    FONT_PATH = "Amiri-Regular.ttf"
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
except:
    try:
        # Try system Arabic font if available
        FONT_PATH = "arial.ttf"
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except:
        # Final fallback to default font
        font = ImageFont.load_default()
        app.logger.warning("Using default font - Arabic display may be compromised")

def create_tiff_from_subtitle(subtitle, index):
    """Create a TIFF image from subtitle text with RTL support"""
    try:
        image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Process Arabic text
        arabic_text = subtitle.content
        reshaped_text = reshape(arabic_text)
        bidi_text = get_display(reshaped_text)
        
        # Calculate text position
        text_width = draw.textlength(bidi_text, font=font)
        text_height = FONT_SIZE
        x = (IMAGE_WIDTH - text_width) / 2
        y = IMAGE_HEIGHT - text_height - 20
        
        # Draw text
        draw.text((x, y), bidi_text, font=font, fill=TEXT_COLOR)
        
        # Save to compressed TIFF
        output = io.BytesIO()
        image.save(output, format="TIFF", compression="tiff_lzw")
        output.seek(0)
        
        return output, f"subtitle_{index:04d}.tiff"
    except Exception as e:
        app.logger.error(f"Image creation failed: {str(e)}")
        raise

[... rest of your existing routes and code ...]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
