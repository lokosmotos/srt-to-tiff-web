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
FONT_SIZE = 24
LINE_SPACING = 8
MAX_LINES = 3  # Maximum lines to display
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

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
        logger.info("Fell back to Arial font")
    except:
        font = ImageFont.load_default()
        logger.warning("Using default font - Arabic display may be compromised")

def create_tiff_from_subtitle(subtitle, index):
    """Create a TIFF image from subtitle text with RTL support"""
    try:
        image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Process Arabic text
        arabic_text = subtitle.content.replace('\r', '')  # Remove carriage returns
        reshaped_text = reshape(arabic_text)
        bidi_text = get_display(reshaped_text)
        
        # Handle multiline text
        lines = [line for line in bidi_text.split('\n') if line.strip()][:MAX_LINES]
        line_height = FONT_SIZE + LINE_SPACING
        total_height = len(lines) * line_height
        
        # Start position (centered vertically)
        y = (IMAGE_HEIGHT - total_height) / 2
        
        # Draw each line
        for line in lines:
            try:
                text_width = draw.textlength(line, font=font)
                x = (IMAGE_WIDTH - text_width) / 2
                draw.text((x, y), line, font=font, fill=TEXT_COLOR)
                y += line_height
            except Exception as line_error:
                logger.error(f"Failed to draw line: {line_error}")
                continue
        
        # Save to compressed TIFF
        output = io.BytesIO()
        image.save(output, format="TIFF", compression="tiff_lzw")
        output.seek(0)
        
        return output, f"subtitle_{index:04d}.tiff"
    except Exception as e:
        logger.error(f"Image creation failed for subtitle {index}: {str(e)}")
        raise

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
            #status { margin-top: 20px; min-height: 20px; }
        </style>
    </head>
    <body>
        <h1>Arabic SRT to TIFF Converter</h1>
        <form id="uploadForm" enctype="multipart/form-data">
            <input type="file" id="srtFile" name="srt_file" accept=".srt" required>
            <button type="submit">Convert to TIFF</button>
        </form>
        <div id="status"></div>
        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const status = document.getElementById('status');
                status.innerHTML = '<p>Processing... Please wait</p>';
                
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
                        a.download = 'arabic_subtitles.zip';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        status.innerHTML = '<p>Conversion successful! Download should start automatically.</p>';
                    } else {
                        const error = await response.text();
                        status.innerHTML = `<p class="error">Error: ${error}</p>`;
                    }
                } catch (err) {
                    status.innerHTML = `<p class="error">Network error: ${err.message}</p>`;
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
            
        # Check file size
        srt_file.seek(0, os.SEEK_END)
        file_size = srt_file.tell()
        srt_file.seek(0)
        if file_size > MAX_FILE_SIZE:
            return f"File too large (max {MAX_FILE_SIZE/1024/1024}MB)", 400
            
        # Read and decode file
        try:
            srt_content = srt_file.read().decode('utf-8-sig')  # Handle BOM
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
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            success_count = 0
            for index, subtitle in enumerate(subtitles, 1):
                try:
                    tiff_buffer, filename = create_tiff_from_subtitle(subtitle, index)
                    zip_file.writestr(filename, tiff_buffer.getvalue())
                    success_count += 1
                except Exception as e:
                    logger.error(f"Skipped subtitle {index}: {str(e)}")
                    continue
            
            if success_count == 0:
                return "No valid subtitles could be processed", 400
            
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='arabic_subtitles.zip'
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in conversion: {str(e)}")
        return "Internal server error during conversion", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)
