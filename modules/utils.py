import hashlib
import os
import datetime
import logging
import base64
import urllib.parse
from pathlib import Path

def calculate_hash(file_path):
    """Calculates the SHA-256 hash of a file for forensic integrity."""
    if not os.path.exists(file_path):
        return None
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_file_metadata(file_path):
    """Returns the Creation and Last Modified dates of a file using os.stat."""
    if not os.path.exists(file_path):
        return "N/A", "N/A"
    try:
        stat = os.stat(file_path)
        creation_time = datetime.datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        return f" {creation_time}", f" {modified_time}"
    except Exception as e:
        logging.error(f"Error reading metadata for {file_path}: {e}")
        return " Error", " Error"

def convert_webkit_timestamp(webkit_timestamp):
    """Converts WebKit (Chrome/Edge) timestamp to human-readable UTC."""
    if not webkit_timestamp:
        return "N/A"
    try:
        epoch_start = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(microseconds=int(webkit_timestamp))
        date_str = (epoch_start + delta).strftime('%Y-%m-%d %H:%M:%S')
        return f" {date_str}"
    except Exception:
        return " Invalid Timestamp"

def decode_base64_url(text):
    """Attempts to decode base64 strings and URL encodings."""
    if not text:
        return text
    decoded = urllib.parse.unquote(text)
    try:
        # Check if it looks like base64
        if len(decoded) % 4 == 0 and len(decoded) > 8:
            b64_decoded = base64.b64decode(decoded).decode('utf-8')
            if b64_decoded.isprintable():
                return f"{decoded} [Decoded: {b64_decoded}]"
    except Exception:
        pass
    return decoded

def setup_logging():
    """Sets up a forensic log to track all actions."""
    log_dir = Path("reports/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"forensic_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return log_file

def ensure_dir(path):
    """Ensures a directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)
