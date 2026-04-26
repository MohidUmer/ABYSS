import platform
import getpass
import psutil
import datetime
import socket
import ctypes
import subprocess
import time
import re
import os

def is_admin():
    """Checks if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def get_hardware_uuid():
    """Get hardware UUID via wmic."""
    try:
        result = subprocess.run('wmic csproduct get uuid', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if len(lines) > 1:
            return lines[1]
    except:
        pass
    return "N/A"

def get_mac_addresses():
    """Get all physical MAC addresses."""
    try:
        result = subprocess.run('getmac /fo csv /nh', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        macs = []
        for line in result.stdout.split('\n'):
            match = re.search(r'"([0-9A-F]{2}[:-]){5}([0-9A-F]{2})"', line, re.IGNORECASE)
            if match:
                macs.append(match.group(0).replace('"', ''))
        return macs if macs else ["N/A"]
    except:
        return ["N/A"]

def get_disk_serial():
    """Get disk serial number."""
    try:
        result = subprocess.run('wmic diskdrive get serialnumber', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if len(lines) > 1:
            return lines[1]
    except:
        pass
    return "N/A"

def get_dns_servers():
    """Get DNS servers."""
    try:
        result = subprocess.run('nslookup localhost', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        # Parse DNS from output
        dns_match = re.search(r'Server:\s*([\d.]+)', result.stdout)
        if dns_match:
            return dns_match.group(1)
    except:
        pass
    return "N/A"

def get_active_ports():
    """Get active TCP ports."""
    try:
        connections = psutil.net_connections(kind='inet')
        ports = set()
        for conn in connections:
            if conn.status == 'ESTABLISHED' and conn.laddr:
                ports.add(conn.laddr.port)
        return sorted(list(ports))[:10]  # Limit to first 10
    except:
        return []

def get_defender_status():
    """Check Windows Defender status."""
    try:
        result = subprocess.run('powershell "Get-MpComputerStatus"', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if 'AntivirusEnabled' in result.stdout and 'True' in result.stdout:
            return "ACTIVE"
        return "INACTIVE"
    except:
        return "UNKNOWN"

def get_firewall_status():
    """Check Windows Firewall status."""
    try:
        result = subprocess.run('netsh advfirewall show allprofiles state', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if 'ON' in result.stdout:
            return "ENABLED"
        return "DISABLED"
    except:
        return "UNKNOWN"

def get_autorun_entries():
    """Get auto-run entries from registry."""
    entries = []
    try:
        result = subprocess.run('reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in result.stdout.split('\n'):
            if 'REG_' in line:
                entries.append(line.strip())
    except:
        pass
    return entries[:5]  # Limit to first 5

def get_scheduled_tasks():
    """Get scheduled task names."""
    tasks = []
    try:
        result = subprocess.run('schtasks /query /fo LIST', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in result.stdout.split('\n'):
            if line.startswith('TaskName:'):
                tasks.append(line.replace('TaskName:', '').strip())
    except:
        pass
    return tasks[:5]  # Limit to first 5

def get_installed_browsers():
    """Get installed browsers dynamically from registry."""
    browsers = set()
    
    # Browser keywords to identify browsers (more flexible)
    browser_keywords = ["edge", "chrome", "firefox", "brave", "opera", "tor", "vivaldi", "chromium", "safari", "waterfox", "pale moon", "seamonkey", "maxthon"]
    
    # Exclude keywords to filter out non-browser applications
    exclude_keywords = ["webview2", "runtime", "hxd", "hex editor", "update", "assistant", "service", "installer", "setup", "redist"]
    
    # Browser name mapping for consistent output
    browser_name_map = {
        "microsoft edge": "Edge",
        "google chrome": "Chrome",
        "mozilla firefox": "Firefox",
        "brave browser": "Brave",
        "brave": "Brave",
        "opera": "Opera",
        "opera gx": "Opera",
        "tor browser": "Tor",
        "tor": "Tor",
        "vivaldi": "Vivaldi",
        "chromium": "Chromium",
        "safari": "Safari",
        "waterfox": "Waterfox",
        "pale moon": "Pale Moon",
        "seamonkey": "SeaMonkey",
        "maxthon": "Maxthon"
    }
    
    try:
        # Check registry for installed browsers (both HKLM and HKCU)
        uninstall_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        
        import winreg
        for hkey, key_path in uninstall_keys:
            try:
                key = winreg.OpenKey(hkey, key_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            display_name_lower = display_name.lower()
                            
                            # Check for exclude keywords first
                            excluded = False
                            for exclude in exclude_keywords:
                                if exclude in display_name_lower:
                                    excluded = True
                                    break
                            
                            if not excluded:
                                # Check if it contains any browser keyword
                                for keyword in browser_keywords:
                                    if keyword in display_name_lower:
                                        # Map to consistent browser name
                                        found = False
                                        for full_name, short_name in browser_name_map.items():
                                            if full_name in display_name_lower:
                                                browsers.add(short_name)
                                                found = True
                                                break
                                        if not found:
                                            # Use the keyword as the name if no mapping found
                                            browsers.add(keyword.capitalize())
                                        break
                        except:
                            pass
                        winreg.CloseKey(subkey)
                    except:
                        pass
                winreg.CloseKey(key)
            except:
                pass
        
        # Also check common paths as fallback (expanded list with more variations)
        browser_paths = [
            (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "Edge"),
            (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "Edge"),
            (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "Chrome"),
            (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "Chrome"),
            (r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
            (r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
            (r"C:\Program Files\Mozilla Firefox\firefox.exe", "Firefox"),
            (r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe", "Firefox"),
            (r"C:\Program Files\Opera\launcher.exe", "Opera"),
            (r"C:\Program Files (x86)\Opera\launcher.exe", "Opera"),
            (r"C:\Program Files\Opera GX\launcher.exe", "Opera"),
            (r"C:\Program Files (x86)\Opera GX\launcher.exe", "Opera"),
            (r"C:\Program Files\Opera\opera.exe", "Opera"),
            (r"C:\Program Files (x86)\Opera\opera.exe", "Opera"),
            (r"C:\Program Files\Tor Browser\Browser\firefox.exe", "Tor"),
            (r"C:\Users\*\AppData\Local\Tor Browser\Browser\firefox.exe", "Tor"),
            (r"C:\Program Files\Vivaldi\Application\vivaldi.exe", "Vivaldi"),
            (r"C:\Program Files (x86)\Vivaldi\Application\vivaldi.exe", "Vivaldi"),
            (r"C:\Program Files\Chromium\Application\chrome.exe", "Chromium"),
            (r"C:\Program Files (x86)\Chromium\Application\chrome.exe", "Chromium"),
            # User-specific installations
            (r"C:\Users\*\AppData\Local\Google\Chrome\Application\chrome.exe", "Chrome"),
            (r"C:\Users\*\AppData\Local\Microsoft\Edge\Application\msedge.exe", "Edge"),
            (r"C:\Users\*\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe", "Brave"),
            (r"C:\Users\*\AppData\Local\Programs\Opera\launcher.exe", "Opera"),
            (r"C:\Users\*\AppData\Local\Programs\Opera GX\launcher.exe", "Opera"),
            (r"C:\Users\*\AppData\Local\Programs\Mozilla Firefox\firefox.exe", "Firefox"),
        ]
        
        import glob
        for path_pattern, name in browser_paths:
            # Use glob to handle wildcards
            matches = glob.glob(path_pattern)
            for path in matches:
                if os.path.exists(path):
                    browsers.add(name)
                
    except Exception as e:
        pass
    
    return sorted(list(browsers)) if browsers else ["None detected"]

def get_system_profile():
    """Extracts advanced forensic system metadata in new format."""
    profile = {}
    
    # CORE IDENTITY
    profile["Hostname"] = platform.node()
    profile["User"] = f"{getpass.getuser()} (SID: N/A)"
    profile["OS Architecture"] = platform.machine()
    profile["Install Date"] = "N/A (Requires MFT analysis)"
    profile["Hardware UUID"] = get_hardware_uuid()
    
    # NETWORK VITALITY
    try:
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        profile["Internal IP"] = ip_addr
    except:
        profile["Internal IP"] = "N/A"
    
    macs = get_mac_addresses()
    profile["MAC Address"] = f"{macs[0] if macs else 'N/A'} (Physical Adapter)"
    profile["DNS Servers"] = get_dns_servers()
    ports = get_active_ports()
    profile["Active Ports"] = f"[TCP {', '.join(map(str, ports))}]" if ports else "[None]"
    
    # SECURITY LAYER
    profile["Windows Defender"] = f"[{get_defender_status()}]"
    profile["UAC Level"] = "[ALWAYS NOTIFY]" if is_admin() else "[STANDARD]"
    profile["Firewall"] = f"[{get_firewall_status()}]"
    profile["Secure Boot"] = "[UNKNOWN]"  # Requires BIOS access
    
    # STORAGE TOPOLOGY
    try:
        disk = psutil.disk_usage('C:\\')
        profile["C: Drive"] = f"{disk.free // (1024**3)}GB Free / {disk.total // (1024**3)}GB Total (Serial: {get_disk_serial()})"
    except:
        profile["C: Drive"] = "N/A"
    profile["USB Devices"] = "See usb_history.csv for detected devices"
    
    # GHOST HOOKS
    autorun = get_autorun_entries()
    profile["Auto-Run Entries"] = autorun if autorun else ["None detected"]
    
    tasks = get_scheduled_tasks()
    profile["Scheduled Tasks"] = tasks if tasks else ["None detected"]
    
    # INSTALLED BROWSERS
    profile["Installed Browsers"] = get_installed_browsers()
    
    return profile
