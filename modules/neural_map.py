import json
import os
import logging
import math
from collections import Counter, defaultdict

def load_master_correlator(export_dir):
    """Load the Master Correlator JSON file."""
    intelligence_dir = os.path.join(export_dir, "Hits", "Intelligence")
    correlator_path = os.path.join(intelligence_dir, "Master_Correlator.json")

    if not os.path.exists(correlator_path):
        logging.warning(f"[Neural Map] Master Correlator not found: {correlator_path}")
        return None

    with open(correlator_path, "r") as f:
        return json.load(f)

def extract_hierarchical_data(graph, max_visits_to_process=5000):
    """Extract data in the format expected by the new Neural Map 2.0 HTML."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    
    # Pre-filter URL nodes for performance
    url_nodes = [n for n in nodes if n.get("type") == "url"]
    if not url_nodes:
        return {
            'bc': {},
            'd': {},
            'dr': [0, 0]
        }

    # Browser colors matching the new HTML
    browser_colors = {
        'brave': '#FB542B',
        'chrome': '#4285F4',
        'edge': '#0078D4',
        'opera': '#FF1B2D',
        'firefox': '#FF7139',
        'safari': '#C0C0C0',
        'tor': '#7D4698',
        'unknown': '#66FCF1'
    }

    # Build edge lookup for faster browser detection
    node_to_browser = {}
    browser_nodes = {n['id']: n['label'].lower() for n in nodes if n.get('type') == 'browser'}
    for edge in edges:
        if edge.get('source') in browser_nodes:
            node_to_browser[edge.get('target')] = browser_nodes[edge.get('source')]

    # Domain data structure: {domain: {b: {browser: count}, ts: [timestamps], urls: [urls]}}
    domain_data = {}
    all_timestamps = []

    # Sort URL nodes by timestamp first for efficient sampling
    url_nodes.sort(key=lambda x: x.get('z', 0))
    
    # Sample if too many visits for performance
    if len(url_nodes) > max_visits_to_process:
        step = len(url_nodes) // max_visits_to_process
        url_nodes = url_nodes[::step]
    
    for node in url_nodes:
        url = node.get("full_url", "")
        label = node.get("label", "")
        timestamp = node.get('z', 0)

        if url:
            # Extract domain
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                if not domain:
                    domain = url.split('/')[0]
            except:
                domain = url.split('/')[0] if '/' in url else url

            if not domain:
                domain = label[:50] if label else 'unknown'

            # Fast browser lookup (lowercase)
            browser = node_to_browser.get(node.get('id'), 'unknown').lower()
            
            # Normalize browser name
            if browser not in browser_colors:
                browser = 'unknown'

            # Initialize domain entry if needed
            if domain not in domain_data:
                domain_data[domain] = {'b': {}, 'ts': [], 'urls': []}
            
            # Add browser count
            if browser not in domain_data[domain]['b']:
                domain_data[domain]['b'][browser] = 0
            domain_data[domain]['b'][browser] += 1
            
            # Add timestamp and URL
            domain_data[domain]['ts'].append(timestamp)
            domain_data[domain]['urls'].append(url)
            all_timestamps.append(timestamp)

    # Calculate date range
    # Filter out invalid timestamps (0 or very old values)
    valid_timestamps = [ts for ts in all_timestamps if ts > 1000000000]  # Filter out timestamps before 2001
    min_ts = min(valid_timestamps) if valid_timestamps else 0
    max_ts = max(valid_timestamps) if valid_timestamps else 0

    # If no valid timestamps, use current time
    if max_ts == 0:
        import time
        current_time = int(time.time())
        min_ts = current_time - 30 * 24 * 3600  # Default to 30 days ago
        max_ts = current_time

    return {
        'bc': browser_colors,
        'd': domain_data,
        'dr': [min_ts, max_ts]
    }

def generate_neural_map_html(export_dir):
    """Generate Neural Map 2.0 HTML with the new design."""
    graph = load_master_correlator(export_dir)
    if not graph:
        return None

    hierarchy_data = extract_hierarchical_data(graph)

    raw_json = json.dumps(hierarchy_data)

    # Generate Neural Map 2.0 HTML with new design
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ABYSS // Neural Map 2.0</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@300;400;600;700&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg: #060810;
    --panel-bg: rgba(6,8,16,0.92);
    --accent-cyan: #00f5d4;
    --accent-red: #C3073F;
    --accent-gold: #f5a623;
    --text: #c8d6e5;
    --text-dim: #4a5568;
    --brave: #FB542B;
    --chrome: #4285F4;
    --edge: #0078D4;
    --opera: #FF1B2D;
    --grid-color: rgba(0,245,212,0.04);
    --glow-cyan: 0 0 20px rgba(0,245,212,0.4);
    --glow-red: 0 0 20px rgba(195,7,63,0.5);
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    overflow: hidden;
    width: 100vw; height: 100vh;
    cursor: crosshair;
  }}

  /* Animated grid background */
  body::before {{
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(var(--grid-color) 1px, transparent 1px),
      linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }}

  /* Scan line effect */
  body::after {{
    content: '';
    position: fixed; inset: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,0.03) 2px,
      rgba(0,0,0,0.03) 4px
    );
    pointer-events: none;
    z-index: 0;
  }}

  #canvas-wrap {{
    position: fixed; inset: 0;
    z-index: 1;
  }}

  svg {{
    width: 100%; height: 100%;
  }}

  /* === HUD HEADER === */
  #hud-header {{
    position: fixed; top: 0; left: 0; right: 0;
    height: 54px;
    background: linear-gradient(180deg, rgba(6,8,16,0.98) 0%, transparent 100%);
    display: flex; align-items: center; padding: 0 24px;
    gap: 24px;
    z-index: 100;
    border-bottom: 1px solid rgba(0,245,212,0.08);
  }}

  #hud-header .logo {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 18px;
    color: var(--accent-cyan);
    letter-spacing: 4px;
    text-shadow: 0 0 12px rgba(0,245,212,0.6);
    white-space: nowrap;
  }}

  #hud-header .logo span {{
    color: var(--accent-red);
    text-shadow: 0 0 12px rgba(195,7,63,0.8);
  }}

  .hud-stat {{
    display: flex; flex-direction: column;
    border-left: 1px solid rgba(0,245,212,0.15);
    padding-left: 20px;
  }}
  .hud-stat .val {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 15px;
    color: var(--accent-cyan);
    line-height: 1;
  }}
  .hud-stat .lbl {{
    font-size: 10px;
    color: var(--text-dim);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 2px;
  }}

  .hud-flex {{ flex: 1; }}

  .hud-pill {{
    display: flex; align-items: center; gap: 8px;
    background: rgba(195,7,63,0.1);
    border: 1px solid rgba(195,7,63,0.3);
    border-radius: 4px;
    padding: 4px 12px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--accent-red);
    letter-spacing: 1px;
    animation: pulse-border 2s ease-in-out infinite;
  }}

  @keyframes pulse-border {{
    0%, 100% {{ border-color: rgba(195,7,63,0.3); box-shadow: none; }}
    50% {{ border-color: rgba(195,7,63,0.7); box-shadow: 0 0 8px rgba(195,7,63,0.3); }}
  }}

  .dot-blink {{
    width: 6px; height: 6px;
    background: var(--accent-red);
    border-radius: 50%;
    animation: blink 1.2s ease-in-out infinite;
  }}
  @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:0.2}} }}

  /* === TIMELINE === */
  #timeline-panel {{
    position: fixed;
    bottom: 0; left: 0; right: 0;
    height: 90px;
    background: linear-gradient(0deg, rgba(6,8,16,0.98) 0%, transparent 100%);
    z-index: 100;
    display: flex; align-items: center;
    padding: 0 24px 10px;
    gap: 16px;
    border-top: 1px solid rgba(0,245,212,0.06);
  }}

  #timeline-label {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: var(--accent-cyan);
    letter-spacing: 2px;
    white-space: nowrap;
    text-transform: uppercase;
  }}

  #timeline-wrap {{
    flex: 1;
    position: relative;
    height: 60px;
    display: flex; flex-direction: column; justify-content: center;
  }}

  #timeline-dates {{
    display: flex; justify-content: space-between;
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    color: var(--text-dim);
    margin-bottom: 8px;
  }}

  #timeline-track {{
    position: relative;
    height: 28px;
    display: flex; align-items: center;
    cursor: pointer;
  }}

  #timeline-bar-bg {{
    position: absolute; inset: 12px 0;
    background: rgba(0,245,212,0.06);
    border: 1px solid rgba(0,245,212,0.12);
    border-radius: 2px;
  }}

  #timeline-fill {{
    position: absolute; top: 12px; bottom: 12px; left: 0;
    background: linear-gradient(90deg, rgba(0,245,212,0.15), rgba(0,245,212,0.35));
    border-radius: 2px;
    transition: width 0.05s;
  }}

  /* Histogram bars in timeline */
  #timeline-histogram {{
    position: absolute; inset: 0;
    display: flex; align-items: flex-end;
    gap: 1px;
    padding: 0 2px;
    pointer-events: none;
  }}

  .hist-bar {{
    flex: 1;
    min-width: 2px;
    background: rgba(0,245,212,0.25);
    border-radius: 1px 1px 0 0;
    transition: background 0.2s;
  }}
  .hist-bar.active {{ background: rgba(0,245,212,0.7); }}

  #timeline-thumb {{
    position: absolute;
    top: 50%; transform: translateY(-50%);
    width: 3px; height: 24px;
    background: var(--accent-cyan);
    border-radius: 2px;
    box-shadow: 0 0 8px rgba(0,245,212,0.8);
    cursor: ew-resize;
    transition: left 0.05s;
  }}

  #timeline-cursor-label {{
    position: absolute;
    bottom: calc(100% + 4px);
    transform: translateX(-50%);
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    color: var(--accent-cyan);
    background: var(--bg);
    padding: 2px 6px;
    border: 1px solid rgba(0,245,212,0.3);
    white-space: nowrap;
    pointer-events: none;
  }}

  #timeline-controls {{
    display: flex; flex-direction: column; gap: 6px;
    min-width: 90px;
  }}

  .tl-btn {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    letter-spacing: 1px;
    background: rgba(0,245,212,0.06);
    border: 1px solid rgba(0,245,212,0.2);
    color: var(--accent-cyan);
    padding: 4px 8px;
    cursor: pointer;
    text-transform: uppercase;
    border-radius: 2px;
    transition: all 0.15s;
    text-align: center;
  }}
  .tl-btn:hover, .tl-btn.active {{
    background: rgba(0,245,212,0.15);
    border-color: var(--accent-cyan);
    box-shadow: var(--glow-cyan);
  }}

  /* === LEFT SIDEBAR === */
  #sidebar {{
    position: fixed;
    top: 54px; left: 0;
    width: 280px;
    bottom: 90px;
    z-index: 100;
    padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
    background: linear-gradient(90deg, rgba(6,8,16,0.85) 0%, transparent 100%);
    pointer-events: none;
  }}

  .side-section {{
    pointer-events: all;
  }}

  .side-title {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    letter-spacing: 3px;
    color: var(--text-dim);
    text-transform: uppercase;
    margin-bottom: 10px;
    display: flex; align-items: center; gap: 8px;
  }}
  .side-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: rgba(0,245,212,0.1);
  }}

  .browser-row {{
    display: flex; align-items: center; gap: 10px;
    padding: 6px 0;
    cursor: pointer;
    border-radius: 3px;
    padding: 6px 8px;
    transition: background 0.15s;
  }}
  .browser-row:hover {{ background: rgba(255,255,255,0.04); }}

  .browser-dot {{
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 6px currentColor;
  }}

  .browser-name {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    flex: 1;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}

  .browser-count {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text-dim);
  }}

  .browser-toggle {{
    width: 28px; height: 14px;
    background: rgba(0,245,212,0.2);
    border-radius: 7px;
    position: relative;
    transition: background 0.2s;
    border: 1px solid rgba(0,245,212,0.4);
  }}
  .browser-toggle::after {{
    content: '';
    position: absolute;
    top: 2px; left: 2px;
    width: 8px; height: 8px;
    background: var(--accent-cyan);
    border-radius: 50%;
    transition: left 0.2s;
    box-shadow: 0 0 4px var(--accent-cyan);
  }}
  .browser-row.off .browser-toggle {{ background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.1); }}
  .browser-row.off .browser-toggle::after {{ left: 16px; background: var(--text-dim); box-shadow: none; }}
  .browser-row.off .browser-name {{ color: var(--text-dim); }}

  /* === RIGHT DETAIL PANEL === */
  #detail-panel {{
    position: fixed;
    top: 54px; right: 0;
    width: 300px;
    bottom: 90px;
    z-index: 100;
    background: linear-gradient(270deg, rgba(6,8,16,0.92) 0%, transparent 100%);
    padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
    transform: translateX(320px);
    transition: transform 0.3s cubic-bezier(0.16,1,0.3,1);
    pointer-events: none;
  }}
  #detail-panel.visible {{
    transform: translateX(0);
    pointer-events: all;
  }}

  #detail-domain {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    color: var(--accent-cyan);
    word-break: break-all;
    text-shadow: var(--glow-cyan);
    border-bottom: 1px solid rgba(0,245,212,0.15);
    padding-bottom: 10px;
    margin-bottom: 4px;
  }}

  #detail-stats {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 8px;
  }}

  .detail-stat-box {{
    background: rgba(0,245,212,0.04);
    border: 1px solid rgba(0,245,212,0.1);
    border-radius: 3px;
    padding: 8px 10px;
  }}
  .detail-stat-box .dsb-val {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 18px;
    color: var(--accent-cyan);
    line-height: 1;
  }}
  .detail-stat-box .dsb-lbl {{
    font-size: 10px;
    color: var(--text-dim);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 3px;
  }}

  .detail-browser-bar {{
    display: flex; align-items: center; gap: 8px;
    margin-top: 4px;
  }}
  .dbb-name {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    width: 52px;
    text-transform: uppercase;
  }}
  .dbb-track {{
    flex: 1; height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
  }}
  .dbb-fill {{
    height: 100%; border-radius: 2px;
    transition: width 0.4s cubic-bezier(0.16,1,0.3,1);
  }}
  .dbb-count {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: var(--text-dim);
    width: 24px;
    text-align: right;
  }}

  .detail-url-list {{
    flex: 1; overflow-y: auto;
    display: flex; flex-direction: column; gap: 6px;
  }}
  .detail-url-list::-webkit-scrollbar {{ width: 3px; }}
  .detail-url-list::-webkit-scrollbar-track {{ background: transparent; }}
  .detail-url-list::-webkit-scrollbar-thumb {{ background: rgba(0,245,212,0.2); border-radius: 2px; }}

  .url-entry {{
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 3px;
    padding: 6px 8px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    color: var(--text-dim);
    word-break: break-all;
    line-height: 1.5;
    border-left: 2px solid;
  }}

  .url-ts {{
    color: var(--accent-cyan);
    font-size: 8px;
    display: block;
    margin-bottom: 3px;
  }}

  #detail-close {{
    align-self: flex-end;
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    color: var(--text-dim);
    background: none;
    border: 1px solid rgba(255,255,255,0.1);
    padding: 4px 10px;
    cursor: pointer;
    letter-spacing: 2px;
    border-radius: 2px;
    transition: all 0.15s;
  }}
  #detail-close:hover {{ color: var(--accent-red); border-color: var(--accent-red); }}

  /* === TOOLTIP === */
  #tooltip {{
    position: fixed;
    pointer-events: none;
    z-index: 200;
    background: rgba(6,8,16,0.95);
    border: 1px solid rgba(0,245,212,0.3);
    border-radius: 4px;
    padding: 10px 14px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text);
    max-width: 280px;
    opacity: 0;
    transition: opacity 0.15s;
    box-shadow: 0 0 20px rgba(0,245,212,0.15), 0 4px 20px rgba(0,0,0,0.5);
  }}
  #tooltip.visible {{ opacity: 1; }}
  #tooltip .tt-title {{ color: var(--accent-cyan); font-size: 12px; margin-bottom: 6px; }}
  #tooltip .tt-row {{ color: var(--text-dim); margin: 2px 0; }}
  #tooltip .tt-row span {{ color: var(--text); }}

  /* === ZOOM CONTROLS === */
  #zoom-controls {{
    position: fixed;
    right: 20px;
    top: 50%;
    transform: translateY(-50%);
    z-index: 100;
    display: flex; flex-direction: column; gap: 6px;
  }}
  .zoom-btn {{
    width: 32px; height: 32px;
    background: rgba(6,8,16,0.8);
    border: 1px solid rgba(0,245,212,0.2);
    color: var(--accent-cyan);
    font-size: 18px;
    cursor: pointer;
    border-radius: 3px;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
    font-family: 'Share Tech Mono', monospace;
  }}
  .zoom-btn:hover {{
    background: rgba(0,245,212,0.1);
    border-color: var(--accent-cyan);
    box-shadow: var(--glow-cyan);
  }}

  /* === ACTIVE COUNT === */
  #active-badge {{
    position: fixed;
    top: 70px; left: 50%;
    transform: translateX(-50%);
    z-index: 100;
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    letter-spacing: 2px;
    color: var(--accent-cyan);
    background: rgba(6,8,16,0.85);
    padding: 4px 14px;
    border: 1px solid rgba(0,245,212,0.15);
    border-radius: 20px;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
  }}
  #active-badge.visible {{ opacity: 1; }}

  /* Glow pulse on identity node */
  @keyframes identity-pulse {{
    0%,100% {{ filter: drop-shadow(0 0 12px #C3073F) drop-shadow(0 0 24px rgba(195,7,63,0.4)); }}
    50% {{ filter: drop-shadow(0 0 20px #C3073F) drop-shadow(0 0 40px rgba(195,7,63,0.7)); }}
  }}
  .identity-glow {{ animation: identity-pulse 3s ease-in-out infinite; }}

  @keyframes node-appear {{
    from {{ opacity: 0; transform: scale(0); }}
    to {{ opacity: 1; transform: scale(1); }}
  }}

  /* Loading overlay */
  #loading {{
    position: fixed; inset: 0;
    z-index: 999;
    background: var(--bg);
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 20px;
  }}
  #loading .ld-title {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 22px;
    color: var(--accent-cyan);
    letter-spacing: 8px;
    text-shadow: var(--glow-cyan);
  }}
  #loading .ld-sub {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: var(--text-dim);
    letter-spacing: 3px;
  }}
  #loading-bar-wrap {{
    width: 240px;
    height: 2px;
    background: rgba(0,245,212,0.1);
  }}
  #loading-bar {{
    height: 100%;
    background: var(--accent-cyan);
    width: 0%;
    transition: width 0.3s;
    box-shadow: 0 0 8px var(--accent-cyan);
  }}
</style>
</head>
<body>

<!-- Loading -->
<div id="loading">
  <div class="ld-title">ABYSS // NEURAL MAP</div>
  <div class="ld-sub">INITIALIZING CORRELATION ENGINE</div>
  <div id="loading-bar-wrap"><div id="loading-bar"></div></div>
  <div class="ld-sub" id="loading-status">PARSING DATA...</div>
</div>

<!-- HUD Header -->
<div id="hud-header">
  <div class="logo">ABY<span>SS</span> // NEURAL MAP <span style="font-size:11px;opacity:0.5">v2.0</span></div>
  <div class="hud-stat"><div class="val" id="stat-domains">0</div><div class="lbl">Domains</div></div>
  <div class="hud-stat"><div class="val" id="stat-visits">0</div><div class="lbl">Total Visits</div></div>
  <div class="hud-stat"><div class="val" id="stat-active">—</div><div class="lbl">Active Nodes</div></div>
  <div class="hud-stat"><div class="val" id="stat-timespan">—</div><div class="lbl">Time Window</div></div>
  <div class="hud-flex"></div>
  <div class="hud-pill"><div class="dot-blink"></div>CRITICAL RISK: <span id="risk-count">0</span> INDICATORS</div>
</div>

<!-- Left Sidebar -->
<div id="sidebar">
  <div class="side-section">
    <div class="side-title">Browsers</div>
    <div id="browser-filters"></div>
  </div>
  <div class="side-section" style="margin-top:8px;">
    <div class="side-title">Legend</div>
    <div style="display:flex;flex-direction:column;gap:8px;font-size:11px;padding-left:4px;">
      <div style="display:flex;align-items:center;gap:8px;"><svg width="16" height="16"><circle cx="8" cy="8" r="7" fill="none" stroke="#C3073F" stroke-width="1.5"/><circle cx="8" cy="8" r="3" fill="#C3073F"/></svg><span style="color:var(--text-dim)">Identity Nucleus</span></div>
      <div style="display:flex;align-items:center;gap:8px;"><svg width="16" height="16"><circle cx="8" cy="8" r="6" fill="rgba(0,245,212,0.15)" stroke="rgba(0,245,212,0.5)" stroke-width="1"/></svg><span style="color:var(--text-dim)">Browser Hub</span></div>
      <div style="display:flex;align-items:center;gap:8px;"><svg width="16" height="16"><circle cx="8" cy="8" r="4" fill="rgba(255,255,255,0.2)" stroke="rgba(255,255,255,0.4)" stroke-width="1"/></svg><span style="color:var(--text-dim)">Domain Node</span></div>
      <div style="display:flex;align-items:center;gap:8px;"><svg width="16" height="16"><circle cx="8" cy="8" r="4" fill="rgba(195,7,63,0.3)" stroke="#C3073F" stroke-width="1.5"/></svg><span style="color:var(--text-dim)">Cross-Browser</span></div>
    </div>
  </div>
  <div class="side-section" style="margin-top:auto;">
    <div class="side-title">Controls</div>
    <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:var(--text-dim);line-height:2;padding-left:4px;">
      SCROLL → Zoom<br>
      DRAG → Pan<br>
      CLICK NODE → Details<br>
      CLICK BG → Reset
    </div>
  </div>
</div>

<!-- Right Detail Panel -->
<div id="detail-panel">
  <button id="detail-close">[ CLOSE ]</button>
  <div id="detail-domain">—</div>
  <div id="detail-stats"></div>
  <div class="side-title" style="margin-top:8px;">Browser Distribution</div>
  <div id="detail-browsers"></div>
  <div class="side-title" style="margin-top:8px;">Sample URLs</div>
  <div class="detail-url-list" id="detail-urls"></div>
</div>

<!-- Canvas -->
<div id="canvas-wrap">
  <svg id="graph"></svg>
</div>

<!-- Tooltip -->
<div id="tooltip"></div>

<!-- Active Badge -->
<div id="active-badge"></div>

<!-- Timeline -->
<div id="timeline-panel">
  <div id="timeline-label">TIMELINE</div>
  <div id="timeline-wrap">
    <div id="timeline-dates">
      <span id="tl-start">—</span>
      <span id="tl-current" style="color:var(--accent-cyan)">ALL TIME</span>
      <span id="tl-end">—</span>
    </div>
    <div id="timeline-track">
      <div id="timeline-bar-bg"></div>
      <div id="timeline-fill"></div>
      <div id="timeline-histogram"></div>
      <div id="timeline-thumb">
        <div id="timeline-cursor-label"></div>
      </div>
    </div>
  </div>
  <div id="timeline-controls">
    <button class="tl-btn active" id="btn-all" onclick="setTimeRange('all')">ALL TIME</button>
    <button class="tl-btn" id="btn-month" onclick="setTimeRange('month')">LAST 30D</button>
    <button class="tl-btn" id="btn-week" onclick="setTimeRange('week')">LAST 7D</button>
  </div>
</div>

<!-- Zoom Controls -->
<div id="zoom-controls">
  <button class="zoom-btn" onclick="zoomBy(1.4)">+</button>
  <button class="zoom-btn" onclick="zoomBy(0.7)">−</button>
  <button class="zoom-btn" style="font-size:11px;letter-spacing:-1px;" onclick="resetZoom()">⌂</button>
</div>

<script>
// ============================================================
// DATA
// ============================================================
const RAW = {raw_json};

const BROWSER_COLORS = RAW.bc;
const DOMAIN_DATA = RAW.d;
const DATE_RANGE = RAW.dr;

// State
const state = {{
  timeRange: [DATE_RANGE[0], DATE_RANGE[1]],
  selectedDomain: null,
  activeBrowsers: new Set(['brave','chrome','edge','opera']),
  allTime: true
}};

// ============================================================
// PREPROCESS: Build flat domain list with browser visit counts
// ============================================================
setLoadingStatus('BUILDING DOMAIN GRAPH...', 30);

const allDomains = Object.entries(DOMAIN_DATA).map(([domain, info]) => {{
  const totalVisits = Object.values(info.b).reduce((a,b)=>a+b,0);
  const browsers = Object.keys(info.b);
  const crossBrowser = browsers.length > 1;
  return {{ domain, info, totalVisits, browsers, crossBrowser }};
}});

const totalVisits = allDomains.reduce((a,d)=>a+d.totalVisits,0);
document.getElementById('stat-visits').textContent = totalVisits.toLocaleString();
document.getElementById('stat-domains').textContent = allDomains.length;

// Count cross-browser domains for risk indicator
const crossBrowserCount = allDomains.filter(d => d.crossBrowser).length;
document.getElementById('risk-count').textContent = crossBrowserCount;

// ============================================================
// HISTOGRAM: Compute visit density across time
// ============================================================
const HIST_BINS = 60;
const histBins = new Array(HIST_BINS).fill(0);
const tsSpan = DATE_RANGE[1] - DATE_RANGE[0];

Object.values(DOMAIN_DATA).forEach(info => {{
  info.ts.forEach(ts => {{
    const idx = Math.min(HIST_BINS-1, Math.floor((ts - DATE_RANGE[0]) / tsSpan * HIST_BINS));
    histBins[idx]++;
  }});
}});

const maxHist = Math.max(...histBins);
const histContainer = document.getElementById('timeline-histogram');
histBins.forEach((count, i) => {{
  const bar = document.createElement('div');
  bar.className = 'hist-bar';
  bar.style.height = Math.max(2, (count/maxHist)*100) + '%';
  bar.dataset.bin = i;
  histContainer.appendChild(bar);
}});

// ============================================================
// D3 SVG SETUP
// ============================================================
setLoadingStatus('INITIALIZING FORCE SIMULATION...', 55);

const svg = d3.select('#graph');
const W = window.innerWidth, H = window.innerHeight;

const zoom = d3.zoom()
  .scaleExtent([0.05, 8])
  .on('zoom', (e) => {{ container.attr('transform', e.transform); }});

svg.call(zoom);
svg.on('click', (e) => {{
  if (e.target === svg.node() || e.target.tagName === 'svg') resetSelection();
}});

const container = svg.append('g');

// Defs for gradients and filters
const defs = svg.append('defs');

// Glow filter
['cyan','red','brave','chrome','edge','opera'].forEach(name => {{
  const colors = {{ cyan:'#00f5d4', red:'#C3073F', brave:'#FB542B', chrome:'#4285F4', edge:'#0078D4', opera:'#FF1B2D' }};
  const f = defs.append('filter').attr('id',`glow-${{name}}`).attr('x','-50%').attr('y','-50%').attr('width','200%').attr('height','200%');
  f.append('feGaussianBlur').attr('stdDeviation','4').attr('result','blur');
  const merge = f.append('feMerge');
  merge.append('feMergeNode').attr('in','blur');
  merge.append('feMergeNode').attr('in','SourceGraphic');
}});

// Cross-browser glow
const crossFilter = defs.append('filter').attr('id','glow-cross').attr('x','-80%').attr('y','-80%').attr('width','260%').attr('height','260%');
crossFilter.append('feGaussianBlur').attr('stdDeviation','6').attr('result','blur');
const crossMerge = crossFilter.append('feMerge');
crossMerge.append('feMergeNode').attr('in','blur');
crossMerge.append('feMergeNode').attr('in','SourceGraphic');

// ============================================================
// BUILD GRAPH NODES & LINKS
// ============================================================
// Nodes: identity center + browser hubs + domain nodes
const graphNodes = [];
const graphLinks = [];

// Identity
graphNodes.push({{ id:'_identity', type:'identity', label:'TARGET SYSTEM', x:0, y:0 }});

// Browsers
const BROWSERS = Object.keys(BROWSER_COLORS).filter(b => ['brave','chrome','edge','opera'].includes(b));
const BROWSER_LABELS = {{ brave:'Brave', chrome:'Chrome', edge:'Edge', opera:'Opera' }};
const browserVisitCounts = {{}};
BROWSERS.forEach(b => {{
  let total = 0;
  allDomains.forEach(d => {{ total += (d.info.b[b] || 0); }});
  browserVisitCounts[b] = total;
  graphNodes.push({{ id:`_browser_${{b}}`, type:'browser', browser:b, label:BROWSER_LABELS[b], visitCount:total }});
  graphLinks.push({{ source:'_identity', target:`_browser_${{b}}`, type:'identity_browser' }});
}});

// Domain nodes (top 150 by visits for performance)
const displayDomains = allDomains
  .filter(d => d.totalVisits > 0)
  .sort((a,b) => b.totalVisits - a.totalVisits)
  .slice(0, 150);

displayDomains.forEach(d => {{
  // Find dominant browser
  let domBrowser = null, domCount = 0;
  Object.entries(d.info.b).forEach(([b,c]) => {{ if(c>domCount){{ domCount=c; domBrowser=b; }} }});
  
  graphNodes.push({{
    id: `_domain_${{d.domain}}`,
    type: 'domain',
    domain: d.domain,
    info: d.info,
    totalVisits: d.totalVisits,
    browsers: d.browsers,
    crossBrowser: d.crossBrowser,
    domBrowser,
    active: true
  }});

  // Link to dominant browser (or all if cross-browser)
  d.browsers.forEach(b => {{
    if (BROWSERS.includes(b)) {{
      graphLinks.push({{ source:`_browser_${{b}}`, target:`_domain_${{d.domain}}`, type:'browser_domain', browser:b }});
    }}
  }});
}});

// ============================================================
// FORCE SIMULATION
// ============================================================
setLoadingStatus('RUNNING PHYSICS ENGINE...', 75);

const sim = d3.forceSimulation(graphNodes)
  .force('link', d3.forceLink(graphLinks).id(d=>d.id).distance(d => {{
    if(d.type==='identity_browser') return 180;
    return 80 + (1/(d.source?.totalVisits||1)) * 500;
  }}).strength(0.4))
  .force('charge', d3.forceManyBody().strength(d => {{
    if(d.type==='identity') return -3000;
    if(d.type==='browser') return -1500;
    return -120;
  }}))
  .force('center', d3.forceCenter(0,0))
  .force('collision', d3.forceCollide().radius(d => {{
    if(d.type==='identity') return 55;
    if(d.type==='browser') return 45;
    return 18 + Math.sqrt(d.totalVisits||1)*1.5;
  }}))
  .alphaDecay(0.03)
  .velocityDecay(0.4);

// ============================================================
// RENDER LINKS
// ============================================================
const linkGroup = container.append('g').attr('class','links');
const linkElems = linkGroup.selectAll('line')
  .data(graphLinks)
  .join('line')
  .attr('stroke', d => {{
    if(d.type==='identity_browser') return 'rgba(195,7,63,0.3)';
    return 'rgba(255,255,255,0.15)';
  }})
  .attr('stroke-width', d => d.type==='identity_browser' ? 1.5 : 0.8)
  .attr('stroke-dasharray', d => d.type==='identity_browser' ? '4,4' : 'none');

// ============================================================
// RENDER NODES
// ============================================================
const nodeGroup = container.append('g').attr('class','nodes');

// --- IDENTITY node ---
const identityG = nodeGroup.append('g')
  .attr('class','identity-glow')
  .style('cursor','default');

// Outer ring pulse
for(let i=3;i>=1;i--) {{
  identityG.append('circle')
    .attr('r', 25+i*12)
    .attr('fill','none')
    .attr('stroke','rgba(195,7,63,0.15)')
    .attr('stroke-width',0.5)
    .call(sel => {{
      sel.append('animate')
        .attr('attributeName','r')
        .attr('values',`${{25+i*12}};${{30+i*12}};${{25+i*12}}`)
        .attr('dur',`${{2+i*0.5}}s`)
        .attr('repeatCount','indefinite');
      sel.append('animate')
        .attr('attributeName','opacity')
        .attr('values','0.3;0.05;0.3')
        .attr('dur',`${{2+i*0.5}}s`)
        .attr('repeatCount','indefinite');
    }});
}}

identityG.append('circle').attr('r',28).attr('fill','rgba(195,7,63,0.12)').attr('stroke','rgba(195,7,63,0.4)').attr('stroke-width',1);
identityG.append('circle').attr('r',18).attr('fill','rgba(195,7,63,0.25)').attr('stroke','#C3073F').attr('stroke-width',1.5);
identityG.append('circle').attr('r',8).attr('fill','#C3073F');
identityG.append('text').text('◉').attr('text-anchor','middle').attr('dominant-baseline','central').attr('fill','#C3073F').attr('font-size',6).attr('dy',0);
identityG.append('text').text('TARGET').attr('text-anchor','middle').attr('dy',42).attr('fill','rgba(195,7,63,0.7)').attr('font-family',"'Share Tech Mono',monospace").attr('font-size',9).attr('letter-spacing',2);

// --- BROWSER nodes ---
const browserGs = {{}};
BROWSERS.forEach(b => {{
  const bNode = graphNodes.find(n=>n.id===`_browser_${{b}}`);
  const color = BROWSER_COLORS[b];
  const g = nodeGroup.append('g')
    .attr('class',`browser-node browser-${{b}}`)
    .style('cursor','pointer')
    .on('mouseover', (e) => showTooltip(e, bNode))
    .on('mouseout', hideTooltip)
    .on('click', (e) => {{ e.stopPropagation(); filterByBrowser(b); }});

  g.append('circle').attr('r',38).attr('fill',color+'08').attr('stroke',color+'20').attr('stroke-width',1);
  g.append('circle').attr('r',26).attr('fill',color+'15').attr('stroke',color+'60').attr('stroke-width',1.5)
    .attr('filter',`url(#glow-${{b}})`);
  g.append('circle').attr('r',16).attr('fill',color+'40').attr('stroke',color).attr('stroke-width',2);

  // Browser icon
  g.append('text')
    .text(BROWSER_LABELS[b][0])
    .attr('text-anchor','middle').attr('dominant-baseline','central')
    .attr('fill',color).attr('font-family',"'Share Tech Mono',monospace")
    .attr('font-size',13).attr('font-weight','bold');

  g.append('text')
    .text(BROWSER_LABELS[b])
    .attr('text-anchor','middle').attr('dy',50)
    .attr('fill',color).attr('font-family',"'Share Tech Mono',monospace")
    .attr('font-size',10).attr('letter-spacing',1).attr('opacity',0.8);

  g.append('text')
    .text(browserVisitCounts[b])
    .attr('text-anchor','middle').attr('dy',63)
    .attr('fill',color+'80').attr('font-family',"'Share Tech Mono',monospace")
    .attr('font-size',8).attr('letter-spacing',1);

  browserGs[b] = g;
  bNode._g = g;
}});

// --- DOMAIN nodes ---
const domainGs = {{}};
displayDomains.forEach(d => {{
  const node = graphNodes.find(n=>n.id===`_domain_${{d.domain}}`);
  const color = d.crossBrowser ? '#C3073F' : (BROWSER_COLORS[d.domBrowser] || '#ffffff');
  const r = 5 + Math.sqrt(d.totalVisits) * 1.2;

  const g = nodeGroup.append('g')
    .attr('class','domain-node')
    .style('cursor','pointer')
    .on('mouseover', (e) => showTooltip(e, node))
    .on('mouseout', hideTooltip)
    .on('click', (e) => {{ e.stopPropagation(); selectDomain(d.domain); }});

  g.append('circle')
    .attr('r', r+4)
    .attr('fill', color+'10')
    .attr('stroke','none');

  g.append('circle')
    .attr('r', r)
    .attr('fill', color+'30')
    .attr('stroke', d.crossBrowser ? '#C3073F' : color+'90')
    .attr('stroke-width', d.crossBrowser ? 1.5 : 0.8)
    .attr('filter', d.crossBrowser ? 'url(#glow-cross)' : `url(#glow-${{d.domBrowser}})`);

  // Label for top domains
  if(d.totalVisits > 20) {{
    g.append('text')
      .text(d.domain.replace('www.',''))
      .attr('text-anchor','middle')
      .attr('dy', r+12)
      .attr('fill', color+'90')
      .attr('font-family',"'Share Tech Mono',monospace")
      .attr('font-size', 8)
      .attr('pointer-events','none');
  }}

  domainGs[d.domain] = g;
  node._g = g;
  node._color = color;
  node._r = r;
}});

// ============================================================
// DRAG BEHAVIOR
// ============================================================
nodeGroup.call(d3.drag()
  .subject((e) => {{
    const t = container.node().getScreenCTM().inverse();
    const p = new DOMPoint(e.x, e.y).matrixTransform(t);
    return sim.find(p.x, p.y, 60);
  }})
  .on('start',(e)=>{{ if(!e.active) sim.alphaTarget(0.1).restart(); if(e.subject){{ e.subject.fx=e.subject.x; e.subject.fy=e.subject.y; }} }})
  .on('drag',(e)=>{{ if(e.subject){{ e.subject.fx=e.x; e.subject.fy=e.y; }} }})
  .on('end',(e)=>{{ if(!e.active) sim.alphaTarget(0); if(e.subject){{ e.subject.fx=null; e.subject.fy=null; }} }})
);

// ============================================================
// SIMULATION TICK
// ============================================================
sim.on('tick', () => {{
  linkElems
    .attr('x1', d=>d.source.x).attr('y1', d=>d.source.y)
    .attr('x2', d=>d.target.x).attr('y2', d=>d.target.y);

  identityG.attr('transform', () => {{
    const n = graphNodes.find(n=>n.id==='_identity');
    return `translate(${{n.x}},${{n.y}})`;
  }});

  BROWSERS.forEach(b => {{
    const n = graphNodes.find(n=>n.id===`_browser_${{b}}`);
    if(n) browserGs[b].attr('transform',`translate(${{n.x}},${{n.y}})`);
  }});

  displayDomains.forEach(d => {{
    const n = graphNodes.find(n=>n.id===`_domain_${{d.domain}}`);
    if(n && domainGs[d.domain]) domainGs[d.domain].attr('transform',`translate(${{n.x}},${{n.y}})`);
  }});
}});

sim.on('end', () => {{
  setLoadingStatus('READY', 100);
  setTimeout(() => {{
    document.getElementById('loading').style.opacity = '0';
    setTimeout(() => {{ document.getElementById('loading').style.display='none'; }}, 400);
  }}, 300);
  // Center view
  const bounds = container.node().getBBox();
  const cx = bounds.x + bounds.width/2;
  const cy = bounds.y + bounds.height/2;
  const scale = Math.min(0.65, 0.9/Math.max(bounds.width/W, bounds.height/H));
  svg.call(zoom.transform, d3.zoomIdentity.translate(W/2,H/2).scale(scale).translate(-cx,-cy));
}});

// ============================================================
// BROWSER FILTERS UI
// ============================================================
const filterContainer = document.getElementById('browser-filters');
BROWSERS.forEach(b => {{
  const color = BROWSER_COLORS[b];
  const row = document.createElement('div');
  row.className = 'browser-row';
  row.dataset.browser = b;
  row.innerHTML = `
    <div class="browser-dot" style="background:${{color}};color:${{color}};box-shadow:0 0 6px ${{color}}"></div>
    <div class="browser-name" style="color:${{color}}">${{BROWSER_LABELS[b]}}</div>
    <div class="browser-count">${{browserVisitCounts[b]}}</div>
    <div class="browser-toggle"></div>
  `;
  row.addEventListener('click', () => {{
    if(state.activeBrowsers.has(b) && state.activeBrowsers.size===1) return;
    if(state.activeBrowsers.has(b)) {{
      state.activeBrowsers.delete(b);
      row.classList.add('off');
    }} else {{
      state.activeBrowsers.add(b);
      row.classList.remove('off');
    }}
    updateVisualization();
  }});
  filterContainer.appendChild(row);
}});

// ============================================================
// SELECTION & FILTERING LOGIC
// ============================================================
function updateVisualization() {{
  // Determine which domains are active
  displayDomains.forEach(d => {{
    const node = graphNodes.find(n=>n.id===`_domain_${{d.domain}}`);
    const g = domainGs[d.domain];
    if(!g) return;

    // Browser filter
    const hasBrowser = d.browsers.some(b => state.activeBrowsers.has(b));

    // Time filter
    let visitsInRange = 0;
    if(!state.allTime) {{
      d.info.ts.forEach(ts => {{
        if(ts >= state.timeRange[0] && ts <= state.timeRange[1]) visitsInRange++;
      }});
    }} else {{
      visitsInRange = d.totalVisits;
    }}

    const isActive = hasBrowser && visitsInRange > 0;
    const isSelected = state.selectedDomain === d.domain;

    if(isSelected) {{
      g.attr('opacity',1).style('pointer-events','all');
      g.select('circle:nth-child(2)').attr('r', node._r+5);
    }} else if(isActive) {{
      g.attr('opacity', state.selectedDomain ? 0.25 : 1).style('pointer-events','all');
      g.select('circle:nth-child(2)').attr('r', node._r);
    }} else {{
      g.attr('opacity',0.04).style('pointer-events','none');
    }}

    node.active = isActive;
  }});

  // Update links
  linkElems.attr('opacity', d => {{
    if(d.type==='identity_browser') return state.activeBrowsers.has(d.target?.browser) ? 0.6 : 0.1;
    const domainId = d.target?.id?.replace('_domain_','');
    const domNode = graphNodes.find(n=>n.id===d.target?.id);
    if(!domNode?.active) return 0.01;
    if(state.selectedDomain && domainId !== state.selectedDomain) return 0.02;
    return 0.3;
  }});

  // Update active count
  const activeCount = displayDomains.filter(d => {{
    const n = graphNodes.find(n=>n.id===`_domain_${{d.domain}}`);
    return n?.active;
  }}).length;
  document.getElementById('stat-active').textContent = activeCount;

  // Histogram highlight
  if(!state.allTime) {{
    const pct0 = (state.timeRange[0]-DATE_RANGE[0])/tsSpan;
    const pct1 = (state.timeRange[1]-DATE_RANGE[0])/tsSpan;
    document.querySelectorAll('.hist-bar').forEach((bar,i) => {{
      const binPct = i/HIST_BINS;
      bar.classList.toggle('active', binPct>=pct0 && binPct<=pct1);
    }});
    document.getElementById('timeline-fill').style.width = (pct1*100)+'%';
    document.getElementById('timeline-thumb').style.left = (pct1*100)+'%';
  }} else {{
    document.querySelectorAll('.hist-bar').forEach(b=>b.classList.add('active'));
    document.getElementById('timeline-fill').style.width = '100%';
    document.getElementById('timeline-thumb').style.left = '100%';
  }}
}}

function selectDomain(domain) {{
  if(state.selectedDomain === domain) {{ resetSelection(); return; }}
  state.selectedDomain = domain;
  updateVisualization();
  showDetailPanel(domain);
}}

function resetSelection() {{
  state.selectedDomain = null;
  updateVisualization();
  document.getElementById('detail-panel').classList.remove('visible');
}}

function filterByBrowser(b) {{
  const btn = document.querySelector(`.browser-row[data-browser="${{b}}"]`);
  if(state.activeBrowsers.size === 1 && state.activeBrowsers.has(b)) return;
  if(state.activeBrowsers.has(b)) {{
    state.activeBrowsers.delete(b);
    btn?.classList.add('off');
  }} else {{
    state.activeBrowsers.add(b);
    btn?.classList.remove('off');
  }}
  updateVisualization();
}}

// ============================================================
// DETAIL PANEL
// ============================================================
function showDetailPanel(domain) {{
  const info = DOMAIN_DATA[domain];
  if(!info) return;
  const totalV = Object.values(info.b).reduce((a,b)=>a+b,0);
  const browsers = Object.keys(info.b);
  const crossB = browsers.length > 1;

  document.getElementById('detail-domain').textContent = domain;
  document.getElementById('detail-domain').style.color = crossB ? '#C3073F' : (BROWSER_COLORS[Object.keys(info.b)[0]] || '#00f5d4');

  document.getElementById('detail-stats').innerHTML = `
    <div class="detail-stat-box">
      <div class="dsb-val">${{totalV}}</div>
      <div class="dsb-lbl">Total Visits</div>
    </div>
    <div class="detail-stat-box">
      <div class="dsb-val" style="color:${{crossB?'#C3073F':'#00f5d4'}}">${{browsers.length}}</div>
      <div class="dsb-lbl">${{crossB?'⚠ Cross-Browser':'Single Browser'}}</div>
    </div>
  `;

  const browsersDiv = document.getElementById('detail-browsers');
  browsersDiv.innerHTML = '';
  BROWSERS.forEach(b => {{
    if(!info.b[b]) return;
    const count = info.b[b];
    const pct = Math.round(count/totalV*100);
    const color = BROWSER_COLORS[b];
    browsersDiv.innerHTML += `
      <div class="detail-browser-bar">
        <div class="dbb-name" style="color:${{color}}">${{BROWSER_LABELS[b]}}</div>
        <div class="dbb-track"><div class="dbb-fill" style="width:${{pct}}%;background:${{color}}"></div></div>
        <div class="dbb-count">${{count}}</div>
      </div>
    `;
  }});

  const urlsDiv = document.getElementById('detail-urls');
  urlsDiv.innerHTML = '';
  const domBrowser = Object.entries(info.b).sort((a,b)=>b[1]-a[1])[0]?.[0];
  const color = crossB ? '#C3073F' : (BROWSER_COLORS[domBrowser] || '#00f5d4');

  info.urls.forEach((url, i) => {{
    const ts = info.ts[i] ? new Date(info.ts[i]*1000).toLocaleString() : '—';
    urlsDiv.innerHTML += `
      <div class="url-entry" style="border-left-color:${{color}}40">
        <span class="url-ts">${{ts}}</span>
        ${{url.substring(0,120)}}${{url.length>120?'…':''}}
      </div>
    `;
  }});

  document.getElementById('detail-panel').classList.add('visible');
}}

document.getElementById('detail-close').addEventListener('click', resetSelection);

// ============================================================
// TOOLTIP
// ============================================================
const tooltip = document.getElementById('tooltip');

function showTooltip(e, node) {{
  if(!node) return;
  let html = '';
  if(node.type==='browser') {{
    const color = BROWSER_COLORS[node.browser];
    html = `<div class="tt-title" style="color:${{color}}">${{node.label}}</div>
      <div class="tt-row">Visits: <span>${{node.visitCount}}</span></div>
      <div class="tt-row">Click to isolate browser</div>`;
  }} else if(node.type==='domain') {{
    const color = node.crossBrowser ? '#C3073F' : (BROWSER_COLORS[node.domBrowser]||'#fff');
    html = `<div class="tt-title" style="color:${{color}}">${{node.domain}}</div>
      <div class="tt-row">Visits: <span>${{node.totalVisits}}</span></div>
      <div class="tt-row">Browsers: <span>${{node.browsers.map(b=>BROWSER_LABELS[b]).join(', ')}}</span></div>
      ${{node.crossBrowser ? '<div class="tt-row" style="color:#C3073F">⚠ CROSS-BROWSER TRACKING</div>' : ''}}
      <div class="tt-row" style="opacity:0.5">Click for details</div>`;
  }}
  tooltip.innerHTML = html;
  tooltip.classList.add('visible');
  moveTooltip(e);
}}

function moveTooltip(e) {{
  let x = e.clientX+16, y = e.clientY-10;
  if(x+300 > W) x = e.clientX-310;
  if(y+120 > window.innerHeight) y = window.innerHeight-130;
  tooltip.style.left = x+'px';
  tooltip.style.top = y+'px';
}}

function hideTooltip() {{ tooltip.classList.remove('visible'); }}

svg.on('mousemove', (e) => {{ if(tooltip.classList.contains('visible')) moveTooltip(e); }});

// ============================================================
// TIMELINE
// ============================================================
const tlTrack = document.getElementById('timeline-track');
const tlThumb = document.getElementById('timeline-thumb');
const tlCursorLabel = document.getElementById('timeline-cursor-label');
const tlFill = document.getElementById('timeline-fill');
const tlCurrent = document.getElementById('tl-current');

const fmtDate = ts => new Date(ts * 1000).toLocaleDateString('en-US',{{month:'short',day:'numeric',year:'2-digit'}});
document.getElementById('tl-start').textContent = fmtDate(DATE_RANGE[0]);
document.getElementById('tl-end').textContent = fmtDate(DATE_RANGE[1]);

let tlDragging = false;

function tlGetPct(e) {{
  const rect = tlTrack.getBoundingClientRect();
  return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
}}

function tlUpdate(pct) {{
  const ts = DATE_RANGE[0] + pct * tsSpan;
  const windowSize = tsSpan * 0.15;
  state.timeRange = [Math.max(DATE_RANGE[0], ts - windowSize), ts];
  state.allTime = false;

  const pct0 = (state.timeRange[0]-DATE_RANGE[0])/tsSpan;
  tlFill.style.width = (pct*100)+'%';
  tlFill.style.left = (pct0*100)+'%';
  tlThumb.style.left = (pct*100)+'%';
  tlCursorLabel.textContent = fmtDate(ts);
  tlCurrent.textContent = fmtDate(state.timeRange[0]) + ' → ' + fmtDate(ts);
  document.getElementById('stat-timespan').textContent = fmtDate(state.timeRange[0]).split(',')[0];

  ['btn-all','btn-month','btn-week'].forEach(id=>document.getElementById(id).classList.remove('active'));

  updateVisualization();
}}

tlTrack.addEventListener('mousedown', (e) => {{ tlDragging=true; tlUpdate(tlGetPct(e)); }});
window.addEventListener('mousemove', (e) => {{ if(tlDragging) tlUpdate(tlGetPct(e)); }});
window.addEventListener('mouseup', () => {{ tlDragging=false; }});
tlTrack.addEventListener('touchstart', (e) => {{ tlDragging=true; tlUpdate(tlGetPct(e.touches[0])); }});
window.addEventListener('touchmove', (e) => {{ if(tlDragging) tlUpdate(tlGetPct(e.touches[0])); }});
window.addEventListener('touchend', () => {{ tlDragging=false; }});

function setTimeRange(preset) {{
  ['btn-all','btn-month','btn-week'].forEach(id=>document.getElementById(id).classList.remove('active'));
  const now = DATE_RANGE[1];
  if(preset==='all') {{
    state.timeRange = [...DATE_RANGE];
    state.allTime = true;
    tlFill.style.left = '0%';
    tlFill.style.width = '100%';
    tlThumb.style.left = '100%';
    tlCurrent.textContent = 'ALL TIME';
    document.getElementById('stat-timespan').textContent = 'ALL';
    document.getElementById('btn-all').classList.add('active');
  }} else if(preset==='month') {{
    state.timeRange = [now - 30*24*3600, now];
    state.allTime = false;
    document.getElementById('btn-month').classList.add('active');
    tlCurrent.textContent = 'LAST 30 DAYS';
    document.getElementById('stat-timespan').textContent = '30D';
  }} else if(preset==='week') {{
    state.timeRange = [now - 7*24*3600, now];
    state.allTime = false;
    document.getElementById('btn-week').classList.add('active');
    tlCurrent.textContent = 'LAST 7 DAYS';
    document.getElementById('stat-timespan').textContent = '7D';
  }}
  updateVisualization();
}}

// ============================================================
// ZOOM
// ============================================================
function zoomBy(factor) {{
  svg.transition().duration(300).call(zoom.scaleBy, factor);
}}
function resetZoom() {{
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(W/2,H/2).scale(0.65));
}}

// ============================================================
// HELPERS
// ============================================================
function setLoadingStatus(msg, pct) {{
  const s = document.getElementById('loading-status');
  const b = document.getElementById('loading-bar');
  if(s) s.textContent = msg;
  if(b) b.style.width = pct+'%';
}}

// Resize
window.addEventListener('resize', () => {{
  const w = window.innerWidth, h = window.innerHeight;
  svg.attr('viewBox',`0 0 ${{w}} ${{h}}`);
}});

// Initial state
updateVisualization();
</script>
</body>
</html>"""

    # Save HTML
    intelligence_dir = os.path.join(export_dir, "Hits", "Intelligence")
    os.makedirs(intelligence_dir, exist_ok=True)

    html_path = os.path.join(intelligence_dir, "Neural_Map.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_template)

    logging.info(f"[Neural Map] Generated Neural Map 2.0: {html_path}")

    return html_path
