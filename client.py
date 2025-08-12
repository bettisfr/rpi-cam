#!/usr/bin/env python3
from PIL import Image
import piexif
import os
import requests
from datetime import datetime
import subprocess
import logging

# -------------------------------------------------
# Config
# -------------------------------------------------
SERVER_URL = "http://141.250.25.160:5000/receive"
IMAGE_DIR = "img"

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def capture_photo() -> str | None:
    """Capture one photo using rpicam-still (no preview)."""
    ensure_dir(IMAGE_DIR)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    file_path = os.path.join(IMAGE_DIR, f"img_{timestamp}.jpg")
    logging.info("Capturing photo with rpicam-still (continuous AF)...")

    try:
        subprocess.run(
            [
                "rpicam-still",
                "-n",                       # no preview (headless)
                "-o", file_path,
                "--autofocus-mode", "continuous"
            ],
            check=True
        )
        logging.info(f"Photo saved as {file_path}")
        return file_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to capture photo: {e}")
        return None

def add_basic_metadata(image_path: str) -> None:
    """Add a simple EXIF comment with timestamp (no GPS/weather)."""
    timestamp_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_comment = f"CapturedAt={timestamp_human}"

    try:
        exif_dict = piexif.load(image_path)
    except Exception:
        # If the file has no EXIF yet, start from empty
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # ImageDescription and DateTimeOriginal
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = user_comment.encode("utf-8")
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = timestamp_human.encode("utf-8")

    exif_bytes = piexif.dump(exif_dict)
    with Image.open(image_path) as img:
        img.save(image_path, exif=exif_bytes, quality=90, optimize=True)

def send_image_to_server(file_path: str) -> bool:
    logging.info("Sending image to server...")
    try:
        with open(file_path, "rb") as img_file:
            response = requests.post(SERVER_URL, files={"image": img_file}, timeout=20)
        if 200 <= response.status_code < 300:
            logging.info("Upload OK")
            return True
        else:
            logging.error(f"Upload failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Error sending image: {e}")
        return False

# -------------------------------------------------
# Main (run-once for cron)
# -------------------------------------------------
def main():
    file_path = capture_photo()
    if not file_path:
        return
    try:
        add_basic_metadata(file_path)
    except Exception as e:
        logging.warning(f"Could not add EXIF metadata: {e}")
    send_image_to_server(file_path)

if __name__ == "__main__":
    main()
