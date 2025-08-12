from flask import Flask, request, render_template, jsonify, url_for
from flask_socketio import SocketIO
import os, time
from werkzeug.utils import secure_filename
import piexif

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def _parse_captured_at(exif_dict) -> str | None:
    try:
        desc = exif_dict.get("0th", {}).get(piexif.ImageIFD.ImageDescription, b"")
        if isinstance(desc, (bytes, bytearray)):
            desc = desc.decode("utf-8", errors="ignore").strip()
        if isinstance(desc, str) and "=" in desc:
            k, v = desc.split("=", 1)
            if k.strip() == "CapturedAt":
                return v.strip()
    except Exception:
        pass
    try:
        dto = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal, b"")
        if isinstance(dto, (bytes, bytearray)):
            dto = dto.decode("utf-8", errors="ignore").strip()
        return dto or None
    except Exception:
        return None

def extract_metadata(image_path):
    try:
        exif_dict = piexif.load(image_path)
    except Exception:
        exif_dict = {}
    return {"captured_at": _parse_captured_at(exif_dict)}

def _dedupe_path(base_dir, filename):
    name, ext = os.path.splitext(filename)
    candidate = os.path.join(base_dir, filename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(base_dir, f"{name}_{i}{ext}")
        i += 1
    return candidate

def _fmt_time(ts):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))

def get_sorted_images(image_folder):
    files = [f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg"))]
    items = []
    for f in files:
        p = os.path.join(image_folder, f)
        items.append({
            "filename": f,
            "url": url_for('static', filename=f"uploads/{f}", _external=False),
            "upload_time": _fmt_time(os.path.getmtime(p)),
            "metadata": extract_metadata(p)
        })
    items.sort(key=lambda x: x["upload_time"], reverse=True)
    return items

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/receive', methods=['POST'])
def receive_image():
    if "image" not in request.files:
        return jsonify({"error": "No image part"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400
    if file.filename.rsplit(".", 1)[-1].lower() not in {"jpg", "jpeg"}:
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    save_path = _dedupe_path(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)
    filename = os.path.basename(save_path)

    meta = extract_metadata(save_path)
    img_url = url_for('static', filename=f"uploads/{filename}", _external=False)

    socketio.emit("new_image", {"filename": filename, "url": img_url, "metadata": meta})
    return jsonify({"message": "Image received", "filename": filename, "url": img_url, "metadata": meta}), 200

@app.route('/get-images')
@app.route('/uploaded_images')  # legacy alias
def get_images():
    return jsonify(get_sorted_images(UPLOAD_FOLDER))

if __name__ == "__main__":
    # For production: consider eventlet WSGI, e.g.:
    #   pip install eventlet
    #   python app.py
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
