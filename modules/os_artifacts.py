import os
import shutil
import logging
import re
import string
import getpass
from pathlib import Path
from datetime import datetime

# Simple string extractor for raw binary files (ESENT DBs)
def extract_strings_from_binary(filepath, min_length=8):
    """Extracts printable ASCII and UTF-16 strings from a raw binary file."""
    strings_found = set()
    try:
        with open(filepath, "rb") as f:
            data = f.read()
            # ASCII strings
            ascii_pattern = re.compile(b'[%s]{%d,}' % (re.escape(string.printable.encode()), min_length))
            for match in ascii_pattern.finditer(data):
                try:
                    s = match.group().decode('ascii')
                    if "http" in s or ":\\" in s:
                        strings_found.add(s)
                except: pass
                
            # UTF-16 strings
            utf16_pattern = re.compile(b'(?:[%s]\x00){%d,}' % (re.escape(string.printable.encode()), min_length))
            for match in utf16_pattern.finditer(data):
                try:
                    s = match.group().decode('utf-16-le')
                    if "http" in s or ":\\" in s:
                        strings_found.add(s)
                except: pass
    except Exception as e:
        logging.error(f"[OS Artifacts] Failed to extract strings from {filepath}: {e}")
        
    return list(strings_found)

def get_jump_lists():
    """Parses AutomaticDestinations (Jump Lists) for recent LNK activity."""
    artifacts = []
    user = getpass.getuser()
    dest_path = Path(os.environ.get('SystemDrive', 'C:') + f"\\Users\\{user}\\AppData\\Roaming\\Microsoft\\Windows\\Recent\\AutomaticDestinations")
    
    if not dest_path.exists():
        logging.warning("[OS Artifacts] Jump Lists directory not found.")
        return artifacts
        
    logging.info("[OS Artifacts] Parsing Taskbar Jump Lists...")
    try:
        import LnkParse3
        import olefile
        
        for file in dest_path.glob("*.automaticDestinations-ms"):
            try:
                # OLE Compound file
                if olefile.isOleFile(str(file)):
                    with olefile.OleFileIO(str(file)) as ole:
                        for entry in ole.listdir():
                            stream_name = entry[0]
                            if stream_name != "DestList":
                                stream_data = ole.openstream(stream_name).read()
                                try:
                                    lnk = LnkParse3.lnk_file(stream_data)
                                    target = lnk.get_json().get('link_info', {}).get('local_base_path', '')
                                    if not target:
                                        target = lnk.get_json().get('string_data', {}).get('name_string', '')
                                        
                                    if target:
                                        artifacts.append({
                                            "Source": "OS_JumpList",
                                            "AppID": file.stem,
                                            "Target": target,
                                            "Timestamp": datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                                        })
                                except:
                                    pass
            except Exception as e:
                logging.debug(f"[OS Artifacts] Error parsing Jump List {file}: {e}")
    except ImportError:
        logging.error("LnkParse3/olefile not installed. Cannot parse Jump Lists.")
        
    return artifacts

def get_search_index_ghosts():
    """Extracts raw strings from the Windows Search Database (Windows.db / Windows.edb)."""
    artifacts = []
    # Test for Windows 11 Windows.db
    db_paths = [
        r"C:\ProgramData\Microsoft\Search\Data\Applications\Windows\Windows.db",
        r"C:\ProgramData\Microsoft\Search\Data\Applications\Windows\Windows.edb"
    ]
    
    for path in db_paths:
        if os.path.exists(path):
            logging.info(f"[OS Artifacts] Scraping Windows Search Index Ghost Data: {path}")
            # The file is almost definitely locked by Windows Search. Try to copy it.
            temp_db = os.path.join("reports", "temp_windows_search.db")
            try:
                shutil.copy2(path, temp_db)
                strings = extract_strings_from_binary(temp_db)
                for s in strings:
                    if "http" in s or "www." in s or "C:\\Users\\" in s:
                        artifacts.append({
                            "Source": "OS_SearchIndex",
                            "Data": s,
                            "File": os.path.basename(path)
                        })
                os.remove(temp_db)
            except Exception as e:
                logging.error(f"[OS Artifacts] Windows Search Index is locked. VSS extraction required for {path}: {e}")
                
    return artifacts

def get_srum_data():
    """Extracts raw strings from System Resource Utilization Monitor (SRUDB.dat)."""
    artifacts = []
    path = r"C:\Windows\System32\sru\SRUDB.dat"
    if os.path.exists(path):
        logging.info("[OS Artifacts] Scraping SRUM Database for App Executables...")
        temp_db = os.path.join("reports", "temp_srudb.dat")
        try:
            shutil.copy2(path, temp_db)
            strings = extract_strings_from_binary(temp_db)
            for s in strings:
                if s.lower().endswith(".exe"):
                    artifacts.append({
                        "Source": "OS_SRUM",
                        "Executable": s,
                    })
            os.remove(temp_db)
        except Exception as e:
            logging.error(f"[OS Artifacts] SRUDB.dat is locked. VSS extraction required: {e}")
            
    return artifacts

def get_recall_snapshots():
    """Extracts basic data from Windows 11 Recall AI Snapshots if present."""
    artifacts = []
    user = getpass.getuser()
    recall_path = Path(os.environ.get('SystemDrive', 'C:') + f"\\Users\\{user}\\AppData\\Local\\CoreAIPlatform.00\\UKP")
    
    if recall_path.exists():
        logging.info("[OS Artifacts] Windows 11 Recall Snapshots found! Scraping...")
        for root, dirs, files in os.walk(recall_path):
            if 'ukg.db' in files:
                db_path = os.path.join(root, 'ukg.db')
                temp_db = os.path.join("reports", "temp_ukg.db")
                try:
                    shutil.copy2(db_path, temp_db)
                    strings = extract_strings_from_binary(temp_db)
                    for s in strings:
                        # Keep only substantial strings that might be OCR text
                        if len(s) > 20:
                            artifacts.append({
                                "Source": "OS_Recall",
                                "OCR_Text": s,
                            })
                    os.remove(temp_db)
                except Exception as e:
                    logging.error(f"[OS Artifacts] Recall ukg.db locked: {e}")
                    
    return artifacts
