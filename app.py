from flask import Flask, request, send_file
from PIL import Image, ImageDraw, ImageFont
import srt
import io
import zipfile
import os
import logging
from arabic_reshaper import reshape
from bidi.algorithm import get_display

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
IMAGE_WIDTH = 720
IMAGE_HEIGHT = 480
BG_COLOR = (0, 0, 255)  # Blue background
TEXT_COLOR = (255, 255, 255)  # White text
FONT_SIZE = 26
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
LINE_SPACING = 10  # Space between lines for multiline text

# Font handling with fallback
try:
    FONT_PATH = os.path.join(os.path.dirname(__file__), "Amiri-Regular.ttf")
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    logger.info(f"Successfully loaded font from {FONT_PATH}")
except Exception as e:
    logger.warning(f"Failed to load Amiri font: {str(e)}")
    try:
        FONT_PATH = "arial.ttf"
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        logger.info(f"Fell back to Arial font")
    except:
        font = ImageFont.load_default()
        logger.warning("Using default font - Arabic display may be compromised")

def create_tiff_from_subtitle(subtitle, index):
    """Create a TIFF image from subtitle text with RTL and multiline support"""
    try:
        image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Split subtitle content into lines
        arabic_text = subtitle.content
        lines = arabic_text.split('\n')
        processed_lines = [(reshape(line), get_display(reshape(line))) for line in lines if line.strip()]
        
        if not processed_lines:
            logger.warning(f"Empty subtitle content for index {index}")
            return None, None
        
        # Calculate total height and max width
        total_height = len(processed_lines) * FONT_SIZE + (len(processed_lines) - 1) * LINE_SPACING
        max_width = 0
        for _, bidi_text in processed_lines:
            try:
                text_width = draw.textlength(bidi_text, font=font)
                max_width = max(max_width, text_width)
            except Exception as e:
                logger.error(f"Failed to measure text width for subtitle {index}: {str(e)}")
                return None, None
        
        # Calculate starting position (center horizontally, bottom-aligned vertically)
        x = (IMAGE_WIDTH - max_width) / 2
        y = IMAGE_HEIGHT - total_height - 20
        
        # Draw each line
        for _, bidi_text in processed_lines:
            try:
                draw.text((x, y), bidi_text, font=font, fill=TEXT_COLOR)
                y += FONT_SIZE + LINE_SPACING
            except Exception as e:
                logger.error(f"Failed to draw text for subtitle {index}: {str(e)}")
                return None, None
        
        # Save to compressed TIFF
        output = io.BytesIO()
        image.save(output, format="TIFF", compression="tiff_lzw")
        output.seek(0)
        
        return output, f"subtitle_{index:04d}.tiff"
    except Exception as e:
        logger.error(f"Image creation failed for subtitle {index}: {str(e)}")
        return None, None

@app.route("/", methods=["GET"])
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Arabic SRT to TIFF</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            input, button { margin: 10px; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1>Arabic SRT to TIFF Converter</h1>
        <form id="uploadForm" enctype="multipart/form-data">
            <input type="file" id="srtFile" name="srt_file" accept=".srt" required>
            <button type="submit">Convert to TIFF</button>
        </form>
        <p id="status"></p>
        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const status = document.getElementById('status');
                status.textContent = "Uploading...";
                
                const formData = new FormData();
                formData.append('srt_file', document.getElementById('srtFile').files[0]);
                
                try {
                    const response = await fetch('/convert', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'subtitles_tiff.zip';
                        a.click();
                        status.textContent = "Conversion successful!";
                    } else {
                        const error = await response.text();
                        status.innerHTML = `<span class="error">Error: ${error}</span>`;
                    }
                } catch (err) {
                    status.innerHTML = `<span class="error">Network error: ${err.message}</span>`;
                }
            });
        </script>
    </body>
    </html>
    """

@app.route("/convert", methods=["POST"])
def convert_srt_to_tiff():
    try:
        # Check file presence
        if 'srt_file' not in request.files:
            return "No file uploaded", 400
            
        srt_file = request.files['srt_file']
        
        # Validate file
        if not srt_file or srt_file.filename == '':
            return "No selected file", 400
            
        if not srt_file.filename.lower().endswith('.srt'):
            return "Only SRT files are allowed", 400
            
        # Read and decode file
        try:
            srt_content = srt_file.read().decode('utf-8-sig')  # Handle BOM
            srt_file.seek(0)  # Reset file pointer
        except UnicodeDecodeError:
            return "Invalid file encoding (use UTF-8)", 400
            
        # Parse subtitles
        try:
            subtitles = list(srt.parse(srt_content))
        except Exception as e:
            logger.error(f"SRT parsing failed: {str(e)}")
            return "Invalid SRT file format", 400
            
        # Process subtitles
        zip_buffer = io.BytesIO()
        valid_files = 0
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for index, subtitle in enumerate(subtitles, 1):
                try:
                    tiff_buffer, filename = create_tiff_from_subtitle(subtitle, index)
                    if tiff_buffer and filename:
                        zip_file.writestr(filename, tiff_buffer.getvalue())
                        valid_files += 1
                    else:
                        logger.warning(f"Skipped subtitle {index} due to processing error")
                except Exception as e:
                    logger.error(f"Unexpected error processing subtitle {index}: {str(e)}")
                    continue  # Skip failed subtitles
                
                # Optional: Log progress
                if index % 100 == 0:
                    logger.info(f"Processed {index} subtitles so far")
        
        if valid_files == 0:
            return "No valid subtitles could be processed", 400
            
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='arabic_subtitles.zip'
        )
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return "Internal server error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)
