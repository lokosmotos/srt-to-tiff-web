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
FONT_PATH = "Amiri-Regular.ttf"  # Make sure this font is in your project
FONT_SIZE = 26
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

# Verify font exists at startup
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError(f"Font file not found at {FONT_PATH}")

def create_tiff_from_subtitle(subtitle, index):
    """Create a TIFF image from subtitle text with RTL support"""
    try:
        # Create blank image
        image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # Load font
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Process Arabic text
        arabic_text = subtitle.content
        reshaped_text = reshape(arabic_text)  # Connect Arabic letters
        bidi_text = get_display(reshaped_text)  # Apply RTL
        
        # Calculate text position
        text_width = draw.textlength(bidi_text, font=font)
        text_height = FONT_SIZE
        x = (IMAGE_WIDTH - text_width) / 2
        y = IMAGE_HEIGHT - text_height - 20  # Position near bottom
        
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
        except UnicodeDecodeError:
            return "Invalid file encoding (use UTF-8)", 400
            
        # Parse subtitles
        try:
            subtitles = list(srt.parse(srt_content))
        except Exception as e:
            app.logger.error(f"SRT parsing failed: {str(e)}")
            return "Invalid SRT file format", 400
            
        # Process subtitles
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for index, subtitle in enumerate(subtitles, 1):
                try:
                    tiff_buffer, filename = create_tiff_from_subtitle(subtitle, index)
                    zip_file.writestr(filename, tiff_buffer.getvalue())
                except Exception as e:
                    app.logger.error(f"Failed to process subtitle {index}: {str(e)}")
                    continue  # Skip failed subtitles but continue with others
        
        if zip_file.namelist() == []:
            return "No valid subtitles could be processed", 400
            
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='arabic_subtitles.zip'
        )
        
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return "Internal server error", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
