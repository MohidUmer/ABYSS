import logging
from collections import Counter
import tldextract
import os
import json
import pandas as pd
from datetime import datetime

def generate_user_persona(artifacts):
    """
    Analyzes all recovered artifacts to build an automated 
    'ABYSS Intelligence' Suspect Persona Profile.
    """
    logging.info("[Intelligence] Generating User Persona Profile...")
    
    domains = []
    flagged_count = 0
    high_risk_hits = []
    
    for item in artifacts:
        # Tally flagged hits
        if item.get("Flagged", "No") != "No":
            flagged_count += 1
            if "crypto" in str(item.get("Title/Extra", "")).lower() or "seed" in str(item.get("Title/Extra", "")).lower() or "onion" in str(item.get("Content", "")).lower():
                high_risk_hits.append(str(item.get("Content", "")))
                
        # Extract Domains
        url = item.get("Content", "")
        try:
            ext = tldextract.extract(str(url))
            if ext.domain:
                domains.append(f"{ext.domain}.{ext.suffix}")
        except: pass
        
    top_domains = [domain for domain, count in Counter(domains).most_common(5)]
    
    # Simple Heuristic Profiling
    persona = "Unknown"
    interests = set()
    
    dev_domains = ["github.com", "stackoverflow.com", "python.org", "aws.amazon.com", "docker.com"]
    social_domains = ["facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com"]
    privacy_domains = ["protonmail.com", "duckduckgo.com", "torproject.org", "mullvad.net"]
    
    for d in top_domains:
        if d in dev_domains:
            persona = "Technical / Developer"
            interests.add("Software Engineering / Operations")
        elif d in privacy_domains:
            persona = "Privacy-Conscious / High OPSEC"
            interests.add("Encryption / Anonymity")
        elif d in social_domains:
            persona = "Standard Consumer"
            interests.add("Social Media / Networking")
            
    if persona == "Unknown":
        persona = "General User"
        interests.add("Broad Web Browsing")
        
    report = []
    report.append("=== ABYSS INTELLIGENCE: SUSPECT PERSONA ===")
    report.append(f"Primary Archetype : {persona}")
    report.append(f"Key Interests     : {', '.join(interests) if interests else 'N/A'}")
    report.append(f"Total Watchlist Hits: {flagged_count}")
    
    if high_risk_hits:
        report.append("\n[!] CRITICAL RISK FACTORS DETECTED [!]")
        report.append("Suspect exhibits high-risk indicators (Crypto / Dark Web / Bypasses).")
        report.append(f"Samples found: {len(high_risk_hits)}")
        
    report.append("\n=== Top Affiliated Networks ===")
    for d in top_domains:
        report.append(f"- {d}")

    return "\n".join(report)

def generate_master_correlator(export_dir):
    """
    Aggregates all browser and registry CSVs into a unified graph structure
    for the ABYSS Neural Map visualization.
    Optimized to limit nodes for performance.
    """
    logging.info("[Intelligence] Generating Master Correlator Graph...")
    
    graph = {
        "nodes": [],
        "edges": [],
        "metadata": {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_nodes": 0,
            "total_edges": 0
        }
    }
    
    # Identity Nucleus (User/Host)
    graph["nodes"].append({
        "id": "identity_nucleus",
        "type": "identity",
        "label": "Target System",
        "x": 0,
        "y": 0,
        "z": 0,
        "weight": 100,
        "color": "#C3073F"  # Neon Magenta
    })
    
    # Scan Extraction folder for CSVs
    extraction_dir = os.path.join(export_dir, "Extraction")
    if not os.path.exists(extraction_dir):
        logging.warning(f"[Intelligence] Extraction directory not found: {extraction_dir}")
        return graph
    
    # Limit total URL nodes for performance (max 2000)
    MAX_URL_NODES = 2000
    url_node_count = 0
    
    # Process browser history
    browsers_dir = os.path.join(extraction_dir, "Browsers")
    if os.path.exists(browsers_dir):
        for browser_name in os.listdir(browsers_dir):
            browser_path = os.path.join(browsers_dir, browser_name)
            if os.path.isdir(browser_path):
                raw_dir = os.path.join(browser_path, "raw")
                if os.path.exists(raw_dir):
                    for csv_file in os.listdir(raw_dir):
                        if csv_file.endswith("_History_Source.csv"):
                            csv_path = os.path.join(raw_dir, csv_file)
                            try:
                                df = pd.read_csv(csv_path)
                                
                                # Create browser node
                                browser_node_id = f"browser_{browser_name.lower()}"
                                graph["nodes"].append({
                                    "id": browser_node_id,
                                    "type": "browser",
                                    "label": browser_name,
                                    "x": 100,
                                    "y": 0,
                                    "z": 0,
                                    "weight": 50,
                                    "color": "#66FCF1"  # Cyan Frost
                                })
                                
                                # Edge from identity to browser
                                graph["edges"].append({
                                    "source": "identity_nucleus",
                                    "target": browser_node_id,
                                    "weight": 1,
                                    "color": "#66FCF1"
                                })
                                
                                # Process URLs as data points (sample for performance)
                                # Take first 500 URLs per browser, or sample evenly
                                sample_size = min(500, len(df))
                                if len(df) > sample_size:
                                    df_sampled = df.sample(n=sample_size, random_state=42)
                                else:
                                    df_sampled = df
                                
                                for idx, row in df_sampled.iterrows():
                                    if url_node_count >= MAX_URL_NODES:
                                        break
                                    
                                    url = str(row.get("Content", ""))
                                    # Use Unix Timestamp field directly (seconds since epoch)
                                    unix_timestamp = row.get("Unix Timestamp", 0)
                                    
                                    if url and len(url) > 10:
                                        # Create URL node
                                        url_node_id = f"url_{browser_name.lower()}_{url_node_count}"
                                        
                                        # Use Unix timestamp directly (already in seconds since epoch)
                                        z_pos = int(unix_timestamp) if unix_timestamp else 0
                                        
                                        graph["nodes"].append({
                                            "id": url_node_id,
                                            "type": "url",
                                            "label": url[:50],
                                            "full_url": url,
                                            "x": 200 + (url_node_count % 10) * 20,
                                            "y": (url_node_count // 10) * 20 - 100,
                                            "z": z_pos,
                                            "weight": 1,
                                            "color": "#66FCF1"
                                        })
                                        
                                        # Edge from browser to URL
                                        graph["edges"].append({
                                            "source": browser_node_id,
                                            "target": url_node_id,
                                            "weight": 1,
                                            "color": "#66FCF1"
                                        })
                                        
                                        url_node_count += 1
                                        
                            except Exception as e:
                                logging.warning(f"[Intelligence] Error processing {csv_file}: {e}")
    
    # Update metadata
    graph["metadata"]["total_nodes"] = len(graph["nodes"])
    graph["metadata"]["total_edges"] = len(graph["edges"])
    
    # Save to Intelligence folder
    intelligence_dir = os.path.join(export_dir, "Hits", "Intelligence")
    os.makedirs(intelligence_dir, exist_ok=True)
    
    correlator_path = os.path.join(intelligence_dir, "Master_Correlator.json")
    with open(correlator_path, "w") as f:
        json.dump(graph, f, indent=2)
    
    logging.info(f"[Intelligence] Master Correlator saved: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    
    return graph
