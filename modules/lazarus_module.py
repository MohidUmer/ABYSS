import os
import re
import string
import logging

def carve_sqlite_freelist(filepath, known_urls):
    """
    Scrapes the raw binary of a SQLite database for URLs that exist
    in unallocated (free-list) pages, proving deleted history.
    """
    carved_urls = set()
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
            
        # Basic regex to find URLs in raw binary
        url_pattern = re.compile(b'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9%_.-]*)*')
        
        for match in url_pattern.finditer(data):
            try:
                url = match.group().decode('ascii')
                # If the URL is in the raw binary but NOT in the active database query results
                # it's highly likely to be a deleted entry sitting in a free-page.
                if url not in known_urls:
                    carved_urls.add(url)
            except: pass
            
    except Exception as e:
        logging.error(f"[Lazarus] Failed to carve {filepath}: {e}")
        
    return list(carved_urls)

def check_zone_identifiers(paths_to_check):
    """
    Checks for NTFS Alternate Data Streams (Zone.Identifier)
    to prove files were downloaded from the web (Mark of the Web).
    """
    ads_results = []
    
    for path in paths_to_check:
        ads_path = f"{path}:Zone.Identifier"
        try:
            if os.path.exists(ads_path):
                with open(ads_path, 'r') as f:
                    content = f.read()
                ads_results.append({
                    "File": path,
                    "ADS_Content": content.strip().replace('\n', ' | ')
                })
        except:
            # File might not have the ADS stream
            pass
            
    return ads_results
