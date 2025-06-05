from flask import Flask, render_template_string, request, send_file
import yt_dlp
import os
import uuid
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
    <style>
        body { font-family: Arial; background: #111; color: white; text-align: center; padding: 50px; }
        input[type=text] { width: 80%; padding: 10px; border-radius: 10px; border: none; }
        button { padding: 10px 20px; background: #00aaff; border: none; border-radius: 8px; cursor: pointer; }
        button:hover { background: #0077cc; }
        .format-list { margin-top: 20px; }
        .format-item { margin: 10px 0; }
        a.download-btn {
            display: inline-block;
            background: #00ff88;
            padding: 8px 15px;
            border-radius: 5px;
            text-decoration: none;
            color: black;
            font-weight: bold;
        }
        .audio-btn {
            background: #ffaa00;
        }
    </style>
</head>
<body>
    <h1>YouTube Video Downloader</h1>
    <form method="post">
        <input type="text" name="url" placeholder="Paste YouTube Link" required>
        <button type="submit">Get Download Options</button>
    </form>
    {% if formats %}
        <div class="format-list">
            {% for fmt in formats %}
                <div class="format-item">
                    <strong>{{ fmt['format_note'] }} | {{ fmt['ext'] }} | {{ fmt['filesize_mb'] }} MB</strong><br>
                    <a class="download-btn {% if fmt['format_note'] == 'Audio Only' %}audio-btn{% endif %}" href="/download?url={{ url }}&format_id={{ fmt['format_id'] }}&audioonly={{ fmt['format_note'] == 'Audio Only' }}">Download</a>
                </div>
            {% endfor %}
        </div>
    {% endif %}
</body>
</html>
"""

def format_size(bytes):
    if not bytes:
        return "Unknown"
    return round(bytes / 1024 / 1024, 2)

@app.route('/', methods=['GET', 'POST'])
def index():
    formats = []
    url = ""
    if request.method == 'POST':
        url = request.form['url']
        ydl_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                all_formats = info.get('formats', [])
                wanted_res = ['144p', '240p', '480p', '720p', '1080p']
                added_res = set()
                best_audio = None
                best_audio_size = 0

                for f in all_formats:
                    note = f.get('format_note', '')
                    if f.get('vcodec') == 'none':  # audio-only
                        size = f.get('filesize', 0)
                        if size > best_audio_size:
                            best_audio = f
                            best_audio_size = size
                    elif note in wanted_res and note not in added_res:
                        formats.append({
                            'format_id': f['format_id'],
                            'format_note': note,
                            'ext': f['ext'],
                            'filesize_mb': format_size(f.get('filesize'))
                        })
                        added_res.add(note)

                # add audio only option if found
                if best_audio:
                    formats.insert(0, {
                        'format_id': best_audio['format_id'],
                        'format_note': 'Audio Only',
                        'ext': best_audio['ext'],
                        'filesize_mb': format_size(best_audio.get('filesize'))
                    })

            except Exception as e:
                formats = [{'format_note': 'Error', 'ext': '', 'filesize_mb': str(e)}]

    return render_template_string(HTML_TEMPLATE, formats=formats, url=url)

@app.route('/download')
def download():
    url = request.args.get('url')
    format_id = request.args.get('format_id')
    audioonly = request.args.get('audioonly') == 'True'
    ext = 'mp3' if audioonly else 'mp4'
    tmp_filename = f"{uuid.uuid4()}.{ext}"

    ydl_opts = {
        'format': format_id,
        'outtmpl': tmp_filename,
        'merge_output_format': 'mp4',
        'quiet': True
    }

    if audioonly:
        ydl_opts.update({
            'format': format_id,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return send_file(tmp_filename, as_attachment=True)
    finally:
        def delayed_remove(file):
            time.sleep(10)
            if os.path.exists(file):
                os.remove(file)
        threading.Thread(target=delayed_remove, args=(tmp_filename,), daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
