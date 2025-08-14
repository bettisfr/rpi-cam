#!/usr/bin/env python3
import argparse
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from PIL import Image
import piexif

# -----------------------------
# Config
# -----------------------------
IMAGE_DIR = Path("img")
SERVER_URL = os.environ.get("SERVER_URL", "http://192.168.1.147:5000/receive")
TIMEOUT = 30  # seconds
EXTS = {".jpg", ".jpeg"}
# Choose one: "survey" (~3MP) or "detail" (~12MP on IMX708)
PHOTO_PRESET = "detail"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# -----------------------------
# Helpers
# -----------------------------
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def capture_photo() -> Optional[Path]:
    """Capture one photo with Pi Cam v3 AF, tuned for ~0.5 m foliage shots."""
    ensure_dir(IMAGE_DIR)
    ts = datetime.now()
    timestamp = ts.strftime("%Y%m%d-%H%M%S")
    file_path = IMAGE_DIR / f"img_{timestamp}.jpg"

    # --- Sensor / output ---
    width, height = 4608, 2592      # full-res IMX708 (16:9)
    quality = "92"                  # JPEG quality (balance size/detail)

    # --- AF/AE targeting ---
    roi = "0.3,0.3,0.4,0.4"         # center patch for AF/AE (x,y,w,h in 0..1)
    af_mode = "continuous"          # keep focusing as leaves move
    af_range = "normal"             # 0.5 m => use normal, not macro
    metering = "spot"               # meter the subject leaf, not bright background

    # --- Daylight anti-blur (reduce wind blur) ---
    # Use a shorter shutter during bright hours; adjust if images look too dark.
    shutter_args = ["--shutter", "8000"] if 9 <= ts.hour <= 17 else []  # 1/125 s

    cmd = [
        "rpicam-still",
        "-n",
        "--width", str(width),
        "--height", str(height),
        "--quality", quality,
        "--autofocus-mode", af_mode,
        "--autofocus-range", af_range,
        "--metering", metering,
        "--roi", roi,
        "--denoise", "auto",
        # Optional: lock white balance for consistency across the day:
        # "--awb", "sunlight",
        "-o", str(file_path),
    ] + shutter_args

    logging.info("Capturing photo: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        logging.warning("Capture failed; retrying once with single-shot AF.")
        # Force a refocus with single-shot AF
        cmd_retry = cmd.copy()
        for i, v in enumerate(cmd_retry):
            if v == "--autofocus-mode":
                cmd_retry[i+1] = "auto"
                break
        try:
            subprocess.run(cmd_retry, check=True)
        except subprocess.CalledProcessError as e2:
            logging.error("Failed to capture photo on retry: %s", e2)
            return None

    logging.info("Photo saved as %s", file_path)
    return file_path

def add_basic_metadata(image_path: Path) -> None:
    """Add EXIF: ImageDescription=CapturedAt=... and Exif.DateTimeOriginal."""
    timestamp_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_comment = f"CapturedAt={timestamp_human}"
    try:
        exif_dict = piexif.load(str(image_path))
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = user_comment.encode("utf-8")
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = timestamp_human.encode("utf-8")
    exif_bytes = piexif.dump(exif_dict)
    with Image.open(image_path) as img:
        img.save(image_path, exif=exif_bytes, quality=90, optimize=True)

def send_image_to_server(file_path: Path) -> bool:
    """POST one image to the Flask server."""
    try:
        with open(file_path, "rb") as f:
            r = requests.post(SERVER_URL, files={"image": f}, timeout=TIMEOUT)
        if 200 <= r.status_code < 300:
            return True
        logging.error("Upload failed %s: HTTP %s %s",
                      file_path.name, r.status_code, r.text[:200])
        return False
    except Exception as e:
        logging.error("Upload error %s: %s", file_path.name, e)
        return False

def pending_count() -> int:
    return sum(1 for p in IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS)

# -----------------------------
# Commands
# -----------------------------
def cmd_photo(args) -> int:
    p = capture_photo()
    if not p:
        return 1
    try:
        add_basic_metadata(p)
    except Exception as e:
        logging.warning("Could not add EXIF metadata to %s: %s", p.name, e)

    # Try immediate upload; delete on success
    if send_image_to_server(p):
        try:
            p.unlink()
            logging.info("Uploaded and deleted %s", p.name)
        except Exception as e:
            logging.error("Uploaded but failed to delete %s: %s", p.name, e)
    else:
        logging.info("Upload failed; keeping %s for later offload", p.name)

    logging.info("Pending images in img/: %d", pending_count())
    return 0

def cmd_offload(args) -> int:
    ensure_dir(IMAGE_DIR)
    files = sorted([p for p in IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS])
    if not files:
        logging.info("No images to offload.")
        return 0

    logging.info("Found %d images to offload.", len(files))
    success = 0
    fail = 0
    backoff = 5

    for p in files:
        ok = send_image_to_server(p)
        if ok:
            try:
                p.unlink()
                success += 1
                logging.info("Uploaded and deleted %s", p.name)
            except Exception as e:
                # Rare: uploaded but couldn't delete locally
                logging.error("Uploaded but failed to delete %s: %s", p.name, e)
            backoff = 5
        else:
            fail += 1
            logging.info("Will retry after %ss", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)

    remaining = pending_count()
    logging.info("Offload complete. OK=%d, FAIL=%d, Remaining=%d", success, fail, remaining)
    return 0

# -----------------------------
# Entry point
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Pi camera client: capture and offload images.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("photo", help="Capture a single photo, try immediate upload, delete on success.") \
       .set_defaults(func=cmd_photo)

    sub.add_parser("offload", help="Upload all photos in img/, deleting each on success.") \
       .set_defaults(func=cmd_offload)

    args = parser.parse_args()
    exit(args.func(args))

if __name__ == "__main__":
    main()
