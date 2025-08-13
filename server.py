# server.py
from flask import Flask, request, render_template, jsonify, url_for
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import time
import piexif

app = Flask(__name__)

# ---- Config ----
UPLOAD_ROOT = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_ROOT
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB cap (adjust or remove)
os.makedirs(UPLOAD_ROOT, exist_ok=True)


# ---- Helpers ----
def _parse_captured_at(exif_dict) -> str | None:
    """Return 'YYYY-MM-DD HH:MM:SS' if available, else None."""
    # Prefer ImageDescription: 'CapturedAt=YYYY-MM-DD HH:MM:SS'
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

    # Fallback: Exif.DateTimeOriginal
    try:
        dto = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal, b"")
        if isinstance(dto, (bytes, bytearray)):
            dto = dto.decode("utf-8", errors="ignore").strip()
        return dto or None
    except Exception:
        return None


def extract_metadata(image_path: str | bytes):
    """Given a path or raw JPEG bytes, return {'captured_at': ...}."""
    try:
        exif_dict = piexif.load(image_path)
    except Exception:
        exif_dict = {}
    return {"captured_at": _parse_captured_at(exif_dict)}


def _dedupe_path(base_dir: str, filename: str) -> str:
    name, ext = os.path.splitext(filename)
    candidate = os.path.join(base_dir, filename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(base_dir, f"{name}_{i}{ext}")
        i += 1
    return candidate


def _fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def get_sorted_images(image_folder: str):
    """Walk subfolders and return image entries sorted by mtime desc."""
    items = []
    for root, _, files in os.walk(image_folder):
        for f in files:
            if not f.lower().endswith((".jpg", ".jpeg")):
                continue
            p = os.path.join(root, f)
            mtime = os.path.getmtime(p)
            rel_from_static = os.path.relpath(p, start="static").replace("\\", "/")
            items.append({
                "filename": f,
                "url": url_for("static", filename=rel_from_static, _external=False),
                "upload_time": _fmt_time(mtime),
                "metadata": extract_metadata(p),
                "mtime": mtime,
            })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    for it in items:
        it.pop("mtime", None)
    return items


# ---- Routes ----
@app.route("/")
def index():
    # Keep your existing template(s)
    return render_template("index.html")


@app.route("/gallery")
def gallery():
    return render_template("gallery.html")


@app.route("/receive", methods=["POST"])
def receive_image():
    """Accept a JPEG and store it under static/uploads/YYYYMMDD/ with de-duplication."""
    if "image" not in request.files:
        return jsonify({"error": "No image part"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg"}:
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)

    # Read into memory to inspect EXIF (safer than saving twice)
    data = file.read()

    # Decide day folder from EXIF CapturedAt or DateTimeOriginal; fallback = today
    try:
        meta_preview = extract_metadata(data)
        captured = meta_preview.get("captured_at") or ""
        day = (
            datetime.strptime(captured, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
            if len(captured) >= 10 else
            datetime.now().strftime("%Y%m%d")
        )
    except Exception:
        day = datetime.now().strftime("%Y%m%d")

    day_dir = os.path.join(app.config["UPLOAD_FOLDER"], day)
    os.makedirs(day_dir, exist_ok=True)

    # Atomic write: .part then replace
    final_path = _dedupe_path(day_dir, filename)
    tmp_path = final_path + ".part"
    with open(tmp_path, "wb") as out:
        out.write(data)
    os.replace(tmp_path, final_path)

    # Build response
    final_meta = extract_metadata(final_path)
    rel_path = f"uploads/{day}/{os.path.basename(final_path)}"
    img_url = url_for("static", filename=rel_path, _external=False)

    return jsonify({
        "message": "Image received",
        "filename": os.path.basename(final_path),
        "url": img_url,
        "subdir": day,
        "metadata": final_meta
    }), 200


@app.route("/get-images")
@app.route("/uploaded_images")  # legacy alias
def get_images():
    return jsonify(get_sorted_images(UPLOAD_ROOT))


# ---- Dev server ----
if __name__ == "__main__":
    # For development only; use a production WSGI server for deployment
    app.run(host="0.0.0.0", port=5000, debug=True)
