from flask import Flask, request, send_file
from PIL import Image, ImageDraw, ImageFont
import srt
import io
import zipfile
import os

app = Flask(__name__)

# Configuration
IMAGE_WIDTH = 720
IMAGE_HEIGHT = 480
BG_COLOR = (0, 0, 255)  # Blue background
TEXT_COLOR = (255, 255, 255)  # White text
FONT_PATH = "Arial.ttf"  # Ensure this font is available
FONT_SIZE = 26

def create_tiff_from_subtitle(subtitle, index):
    # Create a blank image with blue background
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(image)
    
    # Load Arial font with fallback to system font
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except:
        font = ImageFont.load_default()  # Fallback if Arial fails
    
    # Arabic text with RTL
    text = subtitle.content
    text_width = draw.textlength(text, font=font)
    text_height = FONT_SIZE
    x = (IMAGE_WIDTH - text_width) / 2  # Centered horizontally
    y = IMAGE_HEIGHT - text_height - 20  # Near bottom
    
    # Draw text (white)
    draw.text((x, y), text, font=font, fill=TEXT_COLOR, direction="rtl")
    
    # Filename based on index
    filename = f"subtitle_{index:04d}.tiff"
    
    # Save to compressed TIFF in memory
    output = io.BytesIO()
    image.save(output, format="TIFF", compression="tiff_lzw")
    output.seek(0)
    return output, filename

@app.route("/", methods=["GET"])
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Arabic SRT to TIFF Converter</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            input, button { margin: 10px; }
        </style>
    </head>
    <body>
        <h1>Arabic SRT to TIFF Converter</h1>
        <input type="file" id="srtFile" accept=".srt">
        <button onclick="convert()">Convert to TIFF</button>
        <p id="status"></p>
        <script>
            async function convert() {
                const fileInput = document.getElementById("srtFile");
                const status = document.getElementById("status");
                if (!fileInput.files[0]) {
                    status.textContent = "Please select an SRT file.";
                    return;
                }
                const formData = new FormData();
                formData.append("srt_file", fileInput.files[0]);
                status.textContent = "Converting...";
                const response = await fetch("/convert", { method: "POST", body: formData });
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "subtitles_tiff.zip";
                    a.click();
                    status.textContent = "Download complete!";
                } else {
                    const errorText = await response.text();
                    status.textContent = `Error during conversion: ${errorText}`;
                }
            }
        </script>
    </body>
    </html>
    """

@app.route("/convert", methods=["POST"])
def convert_srt_to_tiff():
    if "srt_file" not in request.files:
        return "No file uploaded", 400
    
    srt_file = request.files["srt_file"]
    try:
        srt_content = srt_file.read().decode("utf-8")
    except UnicodeDecodeError:
        return "Invalid SRT file encoding. Please use UTF-8.", 400
    
    # Parse SRT
    try:
        subtitles = list(srt.parse_srt(srt_content))
    except Exception as e:
        return f"Error parsing SRT: {str(e)}", 400
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for index, subtitle in enumerate(subtitles, 1):
            tiff_buffer, filename = create_tiff_from_subtitle(subtitle, index)
            zip_file.writestr(filename, tiff_buffer.getvalue())
    
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name="subtitles_tiff.zip")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
