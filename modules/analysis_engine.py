import pandas as pd
import logging
import re
import winsound

SUSPICIOUS_KEYWORDS = [
    "hack", "download", "password", "dark web", 
    "bypass", "exploit", "crypto", "bitcoin", "login", 
    "admin", "shell", "payload"
]

REGEX_PATTERNS = {
    "Onion Link": r"\b[a-z2-7]{16,56}\.onion\b",
    "Credit Card": r"\b(?:\d[ -]*?){13,16}\b",
    "BIP39 Seed (Possible)": r"\b(?:[a-z]{3,8}\s){11}[a-z]{3,8}\b|\b(?:[a-z]{3,8}\s){23}[a-z]{3,8}\b"
}

def analyze_artifacts(artifacts):
    """
    Analyzes the extracted artifacts using Watchlist 2.0.
    - Flags suspicious keywords.
    - Uses Regex to identify Onion links, Credit Cards, and BIP39 Seed phrases.
    """
    if not artifacts:
        return []
        
    logging.info("Starting Analysis Engine (Watchlist 2.0)...")
    
    high_value_hit = False
    
    # Flagging
    for item in artifacts:
        item["Flagged"] = "No"
        item_content = str(item.get("Content", "")).lower()
        item_title = str(item.get("Title/Extra", "")).lower()
        
        found_flags = []
        
        # 1. Keyword Check
        for kw in SUSPICIOUS_KEYWORDS:
            if kw in item_content or kw in item_title:
                found_flags.append(f"KW:{kw}")
                
        # 2. Regex Check
        for name, pattern in REGEX_PATTERNS.items():
            if re.search(pattern, item_content) or re.search(pattern, item_title):
                found_flags.append(f"REGEX:{name}")
                high_value_hit = True
                
        if found_flags:
            item["Flagged"] = f"Yes ({', '.join(found_flags)})"
            
    if high_value_hit:
        try:
            winsound.Beep(1500, 200) # High pitch alert beep
            winsound.Beep(1500, 200)
            logging.warning("HIGH-VALUE REGEX HIT DETECTED! (Onion/CC/Crypto)")
        except Exception:
            pass
            
    # Sorting by Timestamp
    df = pd.DataFrame(artifacts)
    df['SortTime'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.sort_values(by='SortTime', ascending=False, na_position='last')
    df = df.drop(columns=['SortTime'])
    
    logging.info(f"Analysis complete. {len(df[df['Flagged'] != 'No'])} flagged items found.")
    return df.to_dict(orient='records')
