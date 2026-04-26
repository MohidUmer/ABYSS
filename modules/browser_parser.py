import sqlite3
import shutil
import os
import logging
from pathlib import Path
import datetime
import csv
from .utils import calculate_hash, convert_webkit_timestamp, get_file_metadata, decode_base64_url, ensure_dir

def convert_firefox_timestamp(pr_timestamp):
    if not pr_timestamp:
        return " N/A"
    try:
        # PRTime is microseconds since Jan 1, 1970
        epoch_start = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        delta = datetime.timedelta(microseconds=int(pr_timestamp))
        date_str = (epoch_start + delta).strftime('%Y-%m-%d %H:%M:%S')
        return f" {date_str}"
    except Exception:
        return " Invalid Timestamp"

def extract_history_data(db_path, browser_name, profile_name="Default"):
    """Extracts history from browser databases for a specific profile."""
    ensure_dir("reports/temp")
    temp_db = os.path.join("reports", "temp", f"{browser_name}_{profile_name}_history.db")
    artifacts = []
    
    try:
        try:
            shutil.copy2(db_path, temp_db)
        except PermissionError:
            logging.warning(f"[{browser_name}] Database Locked. Initiating VSS Shadow Ghost Recovery...")
            import subprocess
            try:
                # Try to list shadow copies (Requires Admin)
                vss_result = subprocess.run(["vssadmin", "list", "shadows"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if "No items found" not in vss_result.stdout and vss_result.returncode == 0:
                    logging.info(f"[{browser_name}] Shadow Copies found! Manual forensic extraction required from VSS.")
                else:
                    logging.error(f"[{browser_name}] VSS Ghost Recovery Failed (No shadows or missing Admin privileges).")
            except Exception as e:
                logging.error(f"[{browser_name}] VSS Execution Error: {e}")
            return []
            
        initial_hash = calculate_hash(db_path)
        post_copy_hash = calculate_hash(temp_db)
        
        if initial_hash != post_copy_hash:
            logging.error(f"[{browser_name}] Hash mismatch! Integrity compromised during copy for {db_path}")
            return []
            
        logging.info(f"[{browser_name}] Integrity verified. Hash: {initial_hash}")
        
        ctime, mtime = get_file_metadata(db_path)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        if "Firefox" in browser_name or "Tor" in browser_name:
            # Firefox schema - join with visits table for complete history
            query = """
            SELECT moz_places.url, moz_places.title, moz_places.visit_count, 
                   moz_historyvisits.visit_date, moz_historyvisits.from_visit, moz_historyvisits.visit_type
            FROM moz_places
            JOIN moz_historyvisits ON moz_places.id = moz_historyvisits.place_id
            ORDER BY moz_historyvisits.visit_date DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                decoded_url = decode_base64_url(row[0])
                # Convert Firefox PR timestamp to Unix timestamp (seconds since epoch)
                unix_timestamp = 0
                if row[3]:
                    try:
                        epoch_start = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
                        delta = datetime.timedelta(microseconds=int(row[3]))
                        unix_timestamp = int((epoch_start + delta).timestamp())
                    except:
                        unix_timestamp = 0
                
                # Transition type mapping for Firefox
                transition_type = row[5] if len(row) > 5 else None
                transition_map = {
                    1: "LINK", 2: "TYPED", 3: "BOOKMARK", 4: "EMBED",
                    5: "PERMANENT", 6: "GENERATED", 7: "AUTO_BOOKMARK",
                    8: "DOWNLOAD", 9: "FRAMED_LINK", 10: "RELOAD"
                }
                transition_str = transition_map.get(transition_type, "UNKNOWN") if transition_type else "UNKNOWN"
                
                artifacts.append({
                    "Source": f"{browser_name} History",
                    "File Path": str(db_path),
                    "Content": decoded_url,
                    "Title/Extra": row[1],
                    "Visit Count": row[2],
                    "Timestamp": convert_firefox_timestamp(row[3]),
                    "Unix Timestamp": unix_timestamp,
                    "Transition Type": transition_str,
                    "File Created": ctime,
                    "File Modified": mtime,
                    "Evidence Hash": initial_hash
                })
        else:
            # Chromium schema - join with visits table for complete history
            query = """
            SELECT urls.url, urls.title, urls.visit_count, urls.last_visit_time,
                   visits.visit_time, visits.transition, visits.from_visit
            FROM urls
            LEFT JOIN visits ON urls.id = visits.url
            ORDER BY visits.visit_time DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                decoded_url = decode_base64_url(row[0])
                # Use visit_time if available, otherwise last_visit_time
                webkit_ts = row[4] if row[4] else row[3]
                
                # Convert WebKit timestamp to Unix timestamp (seconds since epoch)
                unix_timestamp = 0
                if webkit_ts:
                    try:
                        epoch_start = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
                        delta = datetime.timedelta(microseconds=int(webkit_ts))
                        unix_timestamp = int((epoch_start + delta).timestamp())
                    except:
                        unix_timestamp = 0
                
                # Transition type mapping for Chromium
                transition_code = row[5] if len(row) > 5 else None
                transition_map = {
                    0: "LINK", 1: "TYPED", 2: "AUTO_BOOKMARK", 3: "AUTO_SUBFRAME",
                    4: "MANUAL_SUBFRAME", 5: "GENERATED", 6: "START_PAGE", 7: "FORM_SUBMIT",
                    8: "RELOAD", 9: "KEYWORD", 10: "KEYWORD_GENERATED"
                }
                transition_str = transition_map.get(transition_code, "UNKNOWN") if transition_code else "UNKNOWN"
                
                artifacts.append({
                    "Source": f"{browser_name} History",
                    "File Path": str(db_path),
                    "Content": decoded_url,
                    "Title/Extra": row[1],
                    "Visit Count": row[2],
                    "Timestamp": convert_webkit_timestamp(webkit_ts),
                    "Unix Timestamp": unix_timestamp,
                    "Transition Type": transition_str,
                    "File Created": ctime,
                    "File Modified": mtime,
                    "Evidence Hash": initial_hash
                })
            
        conn.close()
        logging.info(f"[{browser_name}] Extracted {len(artifacts)} records from {db_path}.")
        
    except sqlite3.Error as e:
        logging.error(f"[{browser_name}] SQL Error in {db_path}: {e}")
    except Exception as e:
        logging.error(f"[{browser_name}] Error in {db_path}: {e}")
    finally:
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
                
    # --- Platinum Feature: Thumbnail Recovery ---
    try:
        top_sites_path = Path(db_path).parent / "Top Sites"
        if top_sites_path.exists() and is_sqlite3(str(top_sites_path)):
            temp_top = os.path.join("reports", f"temp_topsites_{browser_name}.db")
            shutil.copy2(top_sites_path, temp_top)
            conn = sqlite3.connect(temp_top)
            cursor = conn.cursor()
            
            # Check for thumbnails table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='thumbnails'")
            if cursor.fetchone():
                cursor.execute("SELECT url_rank, url, thumbnail FROM thumbnails WHERE thumbnail IS NOT NULL")
                rows = cursor.fetchall()
                for rank, url, blob in rows:
                    if blob:
                        ensure_dir(os.path.join("reports", "temp_thumbnails"))
                        safe_url = re.sub(r'[^A-Za-z0-9]', '_', str(url))[:30]
                        thumb_path = os.path.join("reports", "temp_thumbnails", f"{browser_name}_{safe_url}_{rank}.png")
                        with open(thumb_path, "wb") as f:
                            f.write(blob)
            conn.close()
            os.remove(temp_top)
    except Exception as e:
        logging.debug(f"[{browser_name}] No Top Sites thumbnails recovered: {e}")
            
    return artifacts

def is_sqlite3(filepath):
    """Quickly verify if a file is a SQLite3 database to avoid parsing invalid History files."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(16)
            return header == b'SQLite format 3\x00'
    except Exception:
        return False

def get_browser_paths():
    """Returns a list of tuples containing browser names, history paths, and profile names across all profiles and portable locations."""
    paths_found = []
    
    # 1. Standard AppData Scans
    users_dir = Path(os.environ.get('SystemDrive', 'C:') + "\\Users")
    if users_dir.exists():
        for user_folder in users_dir.iterdir():
            if not user_folder.is_dir():
                continue
                
            # Chromium Paths - Recursively scan ALL profiles
            chromium_roots = {
                "Chrome": user_folder / r"AppData\Local\Google\Chrome\User Data",
                "Edge": user_folder / r"AppData\Local\Microsoft\Edge\User Data",
                "Brave": user_folder / r"AppData\Local\BraveSoftware\Brave-Browser\User Data",
                "Vivaldi": user_folder / r"AppData\Local\Vivaldi\User Data",
            }
            
            for browser_name, root_path in chromium_roots.items():
                if root_path.exists():
                    # Scan for all profile directories containing History file
                    for profile_dir in root_path.iterdir():
                        if profile_dir.is_dir():
                            history_file = profile_dir / "History"
                            if history_file.exists() and is_sqlite3(str(history_file)):
                                # Extract profile name from directory
                                profile_name = profile_dir.name
                                if profile_name == "Default":
                                    profile_name = "Default"
                                paths_found.append((browser_name, str(history_file), profile_name))
            
            # Opera Paths (different structure)
            opera_roots = [
                (user_folder / r"AppData\Roaming\Opera Software\Opera Stable", "Opera"),
                (user_folder / r"AppData\Roaming\Opera Software\Opera GX Stable", "OperaGX"),
            ]
            
            for root_path, browser_name in opera_roots:
                if root_path.exists():
                    history_file = root_path / "History"
                    if history_file.exists() and is_sqlite3(str(history_file)):
                        paths_found.append((browser_name, str(history_file), "Default"))
                    # Also check Default subdirectory
                    default_history = root_path / "Default" / "History"
                    if default_history.exists() and is_sqlite3(str(default_history)):
                        paths_found.append((browser_name, str(default_history), "Default"))
                    
            # Firefox Paths (can have multiple profiles)
            firefox_profiles = user_folder / r"AppData\Roaming\Mozilla\Firefox\Profiles"
            if firefox_profiles.exists():
                for profile in firefox_profiles.iterdir():
                    if profile.is_dir():
                        places_db = profile / "places.sqlite"
                        if places_db.exists() and is_sqlite3(str(places_db)):
                            # Extract profile name from directory (e.g., "xyz.default" -> "xyz")
                            profile_name = profile.name.replace(".default", "").replace(".default-release", "")
                            if not profile_name:
                                profile_name = "Default"
                            paths_found.append(("Firefox", str(places_db), profile_name))
                            
            # Tor Browser Hardcoded Desktop Path
            tor_desktop = user_folder / r"Desktop\Tor Browser\Browser\TorBrowser\Data\Browser\profile.default\places.sqlite"
            if tor_desktop.exists() and is_sqlite3(str(tor_desktop)):
                paths_found.append(("Tor", str(tor_desktop), "Default"))

    # 2. Deep Scan for Portable Browsers (Tor, Portable Firefox/Chrome)
    # Target folders: Desktop, Documents, Downloads for all users, plus root of other drives (D:, E:, etc)
    scan_targets = []
    if users_dir.exists():
        for user_folder in users_dir.iterdir():
            if user_folder.is_dir():
                scan_targets.extend([
                    user_folder / "Desktop",
                    user_folder / "Documents",
                    user_folder / "Downloads"
                ])
                
    # Add other logical drives
    import string
    available_drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
    for drive in available_drives:
        if drive != os.environ.get('SystemDrive', 'C:'):
            scan_targets.append(Path(drive + "\\"))
            
    logging.info("ABYSS Deep Scan: Initiating heuristic scan for portable browser data on Desktop, Documents, Downloads, and secondary drives...")
    
    for target in scan_targets:
        if not target.exists():
            continue
        try:
            for root, dirs, files in os.walk(str(target)):
                # Skip massive system/game folders on D drives to save time if we can
                if any(skip in root.lower() for skip in ['windows', 'program files', 'steam', 'epic']):
                    continue
                    
                if "places.sqlite" in files:
                    db_path = os.path.join(root, "places.sqlite")
                    if is_sqlite3(db_path):
                        name = "Tor" if "tor browser" in root.lower() else "Firefox (Portable)"
                        profile_name = "Portable"
                        if (name, db_path, profile_name) not in paths_found:
                            paths_found.append((name, db_path, profile_name))
                            
                if "History" in files:
                    db_path = os.path.join(root, "History")
                    if is_sqlite3(db_path):
                        # Infer name based on folder structure
                        if "chrome" in root.lower(): name = "Chrome (Portable)"
                        elif "brave" in root.lower(): name = "Brave (Portable)"
                        elif "opera" in root.lower(): name = "Opera (Portable)"
                        else: name = "Chromium Based (Portable)"
                        profile_name = "Portable"
                        
                        if (name, db_path, profile_name) not in paths_found:
                            paths_found.append((name, db_path, profile_name))
        except Exception as e:
            # Skip unreadable folders
            pass
            
    return paths_found

def save_profile_csv(artifacts, browser_name, profile_name, output_dir):
    """Save artifacts to a profile-specific CSV file."""
    if not output_dir:
        logging.warning(f"[{browser_name}] No output directory provided, skipping CSV save")
        return None, None, None
    
    ensure_dir(output_dir)
    
    # Sanitize profile name for filename
    safe_profile_name = profile_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    csv_filename = f"{safe_profile_name}_History.csv"
    csv_path = os.path.join(output_dir, csv_filename)
    
    if not artifacts:
        logging.warning(f"[{browser_name}] No artifacts to save for profile {profile_name}")
        return csv_path, None, None
    
    # Determine date range
    valid_timestamps = [a.get("Unix Timestamp", 0) for a in artifacts if a.get("Unix Timestamp", 0) > 0]
    if valid_timestamps:
        min_ts = min(valid_timestamps)
        max_ts = max(valid_timestamps)
        start_date = datetime.datetime.fromtimestamp(min_ts).strftime('%Y-%m-%d %H:%M:%S')
        end_date = datetime.datetime.fromtimestamp(max_ts).strftime('%Y-%m-%d %H:%M:%S')
    else:
        start_date = "N/A"
        end_date = "N/A"
    
    # Write CSV
    fieldnames = ["Source", "File Path", "Content", "Title/Extra", "Visit Count", 
                  "Timestamp", "Unix Timestamp", "Transition Type", "File Created", 
                  "File Modified", "Evidence Hash"]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for artifact in artifacts:
            writer.writerow(artifact)
    
    logging.info(f"[{browser_name}] Saved {len(artifacts)} records to {csv_path}")
    return csv_path, start_date, end_date

def generate_metadata_log(browser_name, output_dir, profile_data):
    """Generate MetadataLog.txt with summary of extracted profiles."""
    log_path = os.path.join(output_dir, "MetadataLog.txt")
    
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"=== {browser_name} Browser History Extraction Metadata ===\n")
        f.write(f"Extraction Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Profiles Found: {len(profile_data)}\n\n")
        
        for profile_name, data in profile_data.items():
            f.write(f"--- Profile: {profile_name} ---\n")
            f.write(f"CSV File: {data['csv_path']}\n")
            f.write(f"Records Extracted: {data['record_count']}\n")
            f.write(f"Date Range: {data['start_date']} - {data['end_date']}\n\n")
        
        f.write("=" * 50 + "\n")
    
    logging.info(f"[{browser_name}] Generated metadata log at {log_path}")
    return log_path
