import os
import re
import shutil
import logging
from pathlib import Path
from .utils import calculate_hash, get_file_metadata, decode_base64_url, ensure_dir

# Regex patterns for interesting data
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
IP_REGEX = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

def parse_notepad_tabs():
    """Parses unsaved Notepad tabs from Windows 11 TabState directory for all users."""
    users_dir = Path(os.environ.get('SystemDrive', 'C:') + "\\Users")
    artifacts = []
    
    ensure_dir("reports/temp")
    
    if not users_dir.exists():
        logging.warning("Users directory not found.")
        return artifacts

    for user_folder in users_dir.iterdir():
        if not user_folder.is_dir():
            continue
            
        tab_state_path = user_folder / r"AppData\Local\Packages\Microsoft.WindowsNotepad_8wekyb3d8bbwe\LocalState\TabState"
        
        if not tab_state_path.exists():
            continue

        # Scan for .bin files (excluding settings)
        bin_files = list(tab_state_path.glob("*.bin"))
        
        for bin_file in bin_files:
            try:
                # 1. Integrity First: Copy to temp dir
                temp_bin = os.path.join("reports", "temp", f"notepad_{user_folder.name}_{bin_file.name}")
                
                shutil.copy2(bin_file, temp_bin)
                initial_hash = calculate_hash(str(bin_file))
                post_copy_hash = calculate_hash(temp_bin)
                
                if initial_hash != post_copy_hash:
                    logging.error(f"[Notepad] Hash mismatch! Integrity compromised during copy for {bin_file}")
                    continue
                
                ctime, mtime = get_file_metadata(str(bin_file))
                
                # Read from the temp file instead of the original
                with open(temp_bin, "rb") as f:
                    content = f.read()
                    
                # Forensic Methodology: Extract UTF-16LE strings
                try:
                    text_content = content.decode('utf-16le', errors='ignore')
                    
                    # Basic cleaning: remove common binary artifacts that might remain
                    clean_text = "".join(char for char in text_content if char.isprintable() or char in "\n\r\t").strip()
                    
                    if clean_text:
                        # Extract interesting patterns
                        emails = EMAIL_REGEX.findall(clean_text)
                        ips = IP_REGEX.findall(clean_text)
                        
                        extra_info = []
                        if emails: extra_info.append(f"Emails: {', '.join(emails)}")
                        if ips: extra_info.append(f"IPs: {', '.join(ips)}")
                        extra_info_str = " | ".join(extra_info) if extra_info else "N/A"
                        
                        decoded_text = decode_base64_url(clean_text)
                        
                        artifacts.append({
                            "Source": f"Notepad Tab {bin_file.name}",
                            "File Path": str(bin_file),
                            "Content": decoded_text,
                            "Title/Extra": extra_info_str,
                            "Visit Count": 1,
                            "Timestamp": mtime, # Best proxy for last edit
                            "File Created": ctime,
                            "File Modified": mtime,
                            "Evidence Hash": initial_hash
                        })
                        logging.info(f"[Notepad] Extracted data from {bin_file.name}")
                except Exception as decode_err:
                    logging.error(f"[Notepad] Decoding error for {bin_file.name}: {decode_err}")
                
            except Exception as e:
                logging.error(f"[Notepad] Error parsing {bin_file}: {e}")
            finally:
                if 'temp_bin' in locals() and os.path.exists(temp_bin):
                    try:
                        os.remove(temp_bin)
                    except Exception:
                        pass
                
    return artifacts
