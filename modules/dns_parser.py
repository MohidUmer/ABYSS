import subprocess
import re
import logging
import tldextract

def get_dns_cache():
    """Captures the current System DNS Cache using ipconfig /displaydns."""
    dns_records = set()
    try:
        # Hide the console window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(['ipconfig', '/displaydns'], capture_output=True, text=True, startupinfo=startupinfo)
        
        # Parse "Record Name . . . . . : example.com"
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith("Record Name") or line.startswith("Record Name . . . . . :"):
                parts = line.split(":")
                if len(parts) > 1:
                    domain = parts[1].strip()
                    # Filter out local reverse-lookup PTR records and local networking
                    if "in-addr.arpa" not in domain and "ip6.arpa" not in domain:
                        dns_records.add(domain.lower())
                        
        logging.info(f"[DNS Cache] Extracted {len(dns_records)} raw DNS records.")
    except Exception as e:
        logging.error(f"Failed to extract DNS Cache: {e}")
        
    return dns_records

def identify_private_leaks(dns_records, browser_artifacts):
    """
    Compares the active DNS cache against the recovered browser history.
    Any domain in the DNS cache that is NOT in the history is flagged as a potential
    Incognito/Private session leak.
    """
    if not dns_records:
        return []
        
    # Extract root domains from history
    history_domains = set()
    for artifact in browser_artifacts:
        url = artifact.get("Content", "")
        if url:
            try:
                ext = tldextract.extract(str(url))
                if ext.domain:
                    root = f"{ext.domain}.{ext.suffix}".lower()
                    history_domains.add(root)
            except:
                pass

    leaks = []
    for dns_entry in dns_records:
        try:
            ext = tldextract.extract(dns_entry)
            root = f"{ext.domain}.{ext.suffix}".lower()
            
            # Filter out standard Microsoft/Windows background noise
            if ext.domain in ["microsoft", "windows", "live", "msn", "skype", "azure", "bing"]:
                continue
                
            if root not in history_domains and root:
                leaks.append({
                    "DNS Request": dns_entry,
                    "Root Domain": root,
                    "Status": "Possible Incognito/Private Leak"
                })
        except:
            pass
            
    return leaks
