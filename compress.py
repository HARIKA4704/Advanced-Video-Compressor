from flask import Flask, request, send_from_directory, render_template, jsonify
import os
import subprocess
import threading
import re
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Folder Configurations
UPLOAD_FOLDER = 'uploads'
COMPRESSED_FOLDER = 'compressed'
OVERLAY_IMAGE = 'overlay.png'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)

compression_progress = {}

def track_progress(filename, process):
    """Tracks FFmpeg progress based on actual encoding progress."""
    global compression_progress
    compression_progress[filename] = 0  # Start at 0%

    total_duration = None  # To store video duration
    for line in process.stderr:
        if "Duration" in line:
            duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line)
            if duration_match:
                hours, minutes, seconds = map(float, duration_match.groups())
                total_duration = (hours * 3600) + (minutes * 60) + seconds

        elif "time=" in line and total_duration:
            time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
            if time_match:
                h, m, s = map(float, time_match.groups())
                current_time = (h * 3600) + (m * 60) + s
                progress = int((current_time / total_duration) * 100)
                compression_progress[filename] = min(progress, 100)

    process.wait()
    compression_progress[filename] = 100  # Set to 100% when done

@app.route('/')
def index():
    return render_template('compress.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global compression_progress
    files = request.files.getlist("videos")
    resolution = request.form.get("resolution", "1280x720")
    crf = request.form.get("crf", "27")
    codec = request.form.get("codec", "libx264")

    responses = []

    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        compressed_filename = f"compressed_{filename}"
        compressed_filepath = os.path.join(COMPRESSED_FOLDER, compressed_filename)

        compression_progress[filename] = 0  # Reset progress tracking

        ffmpeg_command = [
            'ffmpeg', '-y', '-i', filepath, '-i', OVERLAY_IMAGE,
            "-filter_complex", "[1:v]scale=900:-1[wm];[0:v][wm]overlay=main_w-overlay_w-10:main_h-overlay_h-10[out]",
            '-map', '[out]', '-map', '0:a?',
            '-c:v', codec, '-crf', crf, '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k',
            '-s', resolution,
            '-metadata', 'title=Visit For More Cartoons [t.me/HV_CARTOONS_TELUGU_2]',
            compressed_filepath
        ]

        process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        threading.Thread(target=track_progress, args=(filename, process), daemon=True).start()

        responses.append({"filename": filename, "download_url": f"/download/{compressed_filename}"})

    return jsonify(responses)

@app.route('/progress/<filename>', methods=['GET'])
def get_progress(filename):
    return jsonify({"progress": compression_progress.get(filename, 0)})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(COMPRESSED_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
