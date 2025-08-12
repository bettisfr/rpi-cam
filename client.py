from gpiozero import Button, PWMLED
from signal import pause
from PIL import Image
import piexif
import os
import requests
from datetime import datetime
import serial
import adafruit_dht
import board
import time
import logging
import smbus2
import bme280
import subprocess

# Configure logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)

# Constants
SERVER_URL = "http://141.250.25.160:5000/receive"
IMAGE_DIR = "img"

# GPIO setup
capture_button = Button(12)
led_green = PWMLED(4)
led_red = PWMLED(22)
led_blue = PWMLED(25)

led_green.value = 0
led_red.value = 0
led_blue.value = 0

# Device is busy, right led
led_red.blink(on_time=0.5, off_time=0.5, n=10, background=True)

# GPS
try:
    ser = serial.Serial("/dev/ttyACM0", 9600)
    logging.info("GPS found")
except:
    logging.warning("GPS is not attached")

# Temperature, Pressure, Humidity (not present)
address = 0x76
try:
    bus = smbus2.SMBus(1)
    par = bme280.load_calibration_params(bus, address)
    logging.info("Weather found")
except:
    logging.warning("Weather not found")

# Device is ready
led_green.value = 1
led_red.off()

def parse_coordinates(coord, direction):
    if not coord or not direction:
        return None
    degrees_length = 2 if direction in ['N', 'S'] else 3
    degrees = int(coord[:degrees_length])
    minutes = float(coord[degrees_length:])
    decimal = degrees + (minutes / 60)
    if direction in ['S', 'W']:
        decimal = -decimal
    return decimal

def get_gps_data():
    try:
        while True:
            received_data = ser.readline().decode('ascii', errors='ignore').strip()
            if received_data.startswith('$GPGGA'):
                try:
                    gpgga_data = received_data.split(',')
                    latitude = parse_coordinates(gpgga_data[2], gpgga_data[3])
                    longitude = parse_coordinates(gpgga_data[4], gpgga_data[5])
                    return latitude, longitude
                except (IndexError, ValueError):
                    logging.warning("Error parsing GPS")
                    return None, None
    except:
        logging.warning("No GPS coordinates")
        return None, None

def get_weather():
    try:
        data = bme280.sample(bus, address, par)
        return round(data.temperature, 2), round(data.pressure, 2), round(data.humidity, 2)
    except:
        logging.warning("No weather data")
        return None, None, None

def capture_photo() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    file_path = f"{IMAGE_DIR}/img_{timestamp}.jpg"
    logging.info("Capturing photo with libcamera-still (continuous autofocus)...")
    try:
        subprocess.run([
            "libcamera-still",
            "-n",
            "-o", file_path,
            "--autofocus-mode", "continuous"
        ], check=True)
        logging.info(f"Photo saved as {file_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to capture photo: {e}")
        return None
    return file_path

def add_gps_metadata(image_path, latitude=None, longitude=None, temperature=None, pressure=None, humidity=None):
    temperature = temperature or 0.0
    pressure = pressure or 0.0
    humidity = humidity or 0.0
    latitude = latitude or 0.0
    longitude = longitude or 0.0
    user_comment = f"Temperature={temperature}|Pressure={pressure}|Humidity={humidity}"

    def to_gps_format(value):
        degrees = int(value)
        minutes = int((value - degrees) * 60)
        seconds = int((value - degrees - minutes / 60) * 3600 * 100)
        return (degrees, 1), (minutes, 1), (seconds, 100)

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b'N' if latitude >= 0 else b'S',
        piexif.GPSIFD.GPSLatitude: to_gps_format(abs(latitude)),
        piexif.GPSIFD.GPSLongitudeRef: b'E' if longitude >= 0 else b'W',
        piexif.GPSIFD.GPSLongitude: to_gps_format(abs(longitude)),
    }

    exif_dict = piexif.load(image_path)
    exif_dict['GPS'] = gps_ifd
    exif_dict['0th'][piexif.ImageIFD.ImageDescription] = user_comment.encode('utf-8')
    exif_bytes = piexif.dump(exif_dict)
    image = Image.open(image_path)
    image.save(image_path, exif=exif_bytes, quality=90, optimize=True)

def send_image_to_server(file_path: str) -> None:
    print("Sending image to server...")
    with open(file_path, 'rb') as img_file:
        logging.info("Retrieving data...")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temperature, pressure, humidity = get_weather()
        latitude, longitude = get_gps_data()
        logging.info(f"Timestamp: {timestamp}")
        if latitude is not None and longitude is not None:
            logging.info(f"GPS Coordinates: Latitude={latitude:.6f}, Longitude={longitude:.6f}")
        if temperature is not None:
            logging.info(f"Temperature: {temperature:.2f}°C")
        if pressure is not None:
            logging.info(f"Pressure: {pressure:.2f}hPa")
        if humidity is not None:
            logging.info(f"Humidity: {humidity:.2f}%")

        add_gps_metadata(file_path, latitude, longitude, temperature, pressure, humidity)

        files = {'image': img_file}
        try:
            response = requests.post(SERVER_URL, files=files)
            return True
        except:
            logging.info("Error, server unreachable!")
            return False

def handle_button_press() -> None:
    led_green.value = 0
    led_blue.value = 1
    file_path = capture_photo()
    led_green.value = 0
    led_red.value = 1
    if file_path and send_image_to_server(file_path):
        led_blue.value = 0
        led_red.value = 0
        led_green.value = 1
    else:
        led_green.blink(on_time=0.5, off_time=0.5, n=1000, background=True)
        led_red.blink(on_time=0.5, off_time=0.5, n=1000, background=True)
        led_blue.blink(on_time=0.5, off_time=0.5, n=1000, background=True)

# Event binding
capture_button.when_pressed = handle_button_press

# Keep the program running to listen for button presses
pause()