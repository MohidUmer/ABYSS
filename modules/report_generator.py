import os
import re
import pandas as pd
from datetime import datetime
import logging
import pickle
import subprocess

from modules.system_profiler import get_system_profile
from modules.utils import ensure_dir, calculate_hash
from modules.visualizer import generate_browser_visuals
from modules.mft_parser import generate_hex_dump

class ReportGenerator:
    def __init__(self, metadata):
        self.metadata = metadata
        
        date_str = datetime.now().strftime('%Y%m%d')
        safe_case_id = re.sub(r'[^A-Za-z0-9_-]', '', metadata['case_id'])
        dir_name = f"{safe_case_id}" if safe_case_id else f"ABYSS_{date_str}"
        
        # Use user-selected output path instead of hardcoded "reports"
        output_path = metadata.get('output_path', 'reports').strip()
        if not output_path:
            output_path = 'reports'
        
        self.base_dir = os.path.join(output_path, dir_name)
        
        # New folder structure
        self.chain_of_custody_dir = os.path.join(self.base_dir, "Chain_of_Custody")
        self.system_dir = os.path.join(self.base_dir, "System")
        self.extraction_dir = os.path.join(self.base_dir, "Extraction")
        
        # Extraction subdirectories
        self.browsers_dir = os.path.join(self.extraction_dir, "Browsers")
        self.notepad_dir = os.path.join(self.extraction_dir, "Notepad")
        self.registry_dir = os.path.join(self.extraction_dir, "Registry")
        self.dns_records_dir = os.path.join(self.extraction_dir, "DNSRecords")
        
        # Legacy compatibility (keep for now, will be migrated)
        self.raw_dir = os.path.join(self.base_dir, "MFT_Records")
        self.hits_dir = os.path.join(self.base_dir, "Hits")
        self.tabstate_archive = os.path.join(self.notepad_dir, "TabState_Archive")
        self.intelligence_dir = os.path.join(self.hits_dir, "Intelligence")
        
        # Create new directory structure
        ensure_dir(self.base_dir)
        ensure_dir(self.chain_of_custody_dir)
        ensure_dir(self.system_dir)
        ensure_dir(self.extraction_dir)
        ensure_dir(self.browsers_dir)
        ensure_dir(self.notepad_dir)
        ensure_dir(self.registry_dir)
        ensure_dir(self.dns_records_dir)
        
        # Legacy directories (for compatibility)
        ensure_dir(self.raw_dir)
        ensure_dir(self.hits_dir)
        ensure_dir(self.tabstate_archive)
        ensure_dir(self.intelligence_dir)
        
        self.hash_log_path = os.path.join(self.chain_of_custody_dir, "evidence_hashes.log")
        
    def _log_hash(self, filename, file_hash, description):
        with open(self.hash_log_path, "a") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {file_hash} | {filename} ({description})\n")

    def _generate_sys_info(self, browser_paths_found):
        sys_info_path = os.path.join(self.system_dir, "sysinfo.txt")
        profile = get_system_profile()
        
        # Use actual detected browsers from extraction if available
        if browser_paths_found:
            detected_browsers = sorted(set(b[0] for b in browser_paths_found))
        else:
            detected_browsers = profile.get('Installed Browsers', [])
        
        with open(sys_info_path, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("           A B Y S S   S Y S T E M   P R O F I L E R\n")
            f.write("=" * 70 + "\n")
            f.write(f"CASE ID: {self.metadata['case_id']}\n")
            f.write(f"GENERATE TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 70 + "\n\n")
            
            f.write("[+] CORE IDENTITY\n")
            f.write(f"Hostname        : {profile.get('Hostname', 'N/A')}\n")
            f.write(f"User            : {profile.get('User', 'N/A')}\n")
            f.write(f"OS Architecture : {profile.get('OS Architecture', 'N/A')}\n")
            f.write(f"Install Date    : {profile.get('Install Date', 'N/A')}\n")
            f.write(f"Hardware UUID   : {profile.get('Hardware UUID', 'N/A')}\n\n")
            
            f.write("[+] NETWORK VITALITY\n")
            f.write(f"Internal IP     : {profile.get('Internal IP', 'N/A')}\n")
            f.write(f"MAC Address     : {profile.get('MAC Address', 'N/A')}\n")
            f.write(f"DNS Servers     : {profile.get('DNS Servers', 'N/A')}\n")
            f.write(f"Active Ports    : {profile.get('Active Ports', 'N/A')}\n\n")
            
            f.write("[+] SECURITY LAYER\n")
            f.write(f"Windows Defender: {profile.get('Windows Defender', 'N/A')}\n")
            f.write(f"UAC Level       : {profile.get('UAC Level', 'N/A')}\n")
            f.write(f"Firewall        : {profile.get('Firewall', 'N/A')}\n")
            f.write(f"Secure Boot     : {profile.get('Secure Boot', 'N/A')}\n\n")
            
            f.write("[+] STORAGE TOPOLOGY\n")
            f.write(f"C:\\ [Fixed]     : {profile.get('C: Drive', 'N/A')}\n")
            f.write(f"USB Devices     : {profile.get('USB Devices', 'N/A')}\n\n")
            
            f.write("[+] GHOST HOOKS (Persistence)\n")
            autorun = profile.get('Auto-Run Entries', [])
            if isinstance(autorun, list):
                for i, entry in enumerate(autorun, 1):
                    f.write(f"{i}. {entry}\n")
            else:
                f.write(f"1. {autorun}\n")
            
            tasks = profile.get('Scheduled Tasks', [])
            if isinstance(tasks, list):
                for i, task in enumerate(tasks, 1):
                    f.write(f"{i}. {task}\n")
            else:
                f.write(f"1. {tasks}\n")
            f.write("\n")
            
            f.write("[+] INSTALLED BROWSERS\n")
            if isinstance(detected_browsers, list):
                for b in detected_browsers:
                    f.write(f"- {b}\n")
            else:
                f.write(f"- {detected_browsers}\n")
            f.write("=" * 70 + "\n")
                
        report_hash = calculate_hash(sys_info_path)
        self._log_hash("System/sysinfo.txt", report_hash, "Generated System Info Report")

    def _generate_description(self):
        desc_path = os.path.join(self.base_dir, "Case-Description.txt")
        with open(desc_path, "w") as f:
            f.write(f"ABYSS Case Initialization\n")
            f.write(f"==========================\n")
            f.write(f"Case ID: {self.metadata['case_id']}\n")
            f.write(f"Investigator: {self.metadata['investigator']}\n")
            f.write(f"Agency/ID: {self.metadata['agency']}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Description:\n{self.metadata['description']}\n")
            f.write(f"\nDigital Signature: {self.metadata['signature']}\n")
            
        report_hash = calculate_hash(desc_path)
        self._log_hash("Case-Description.txt", report_hash, "Generated Case Description")
        
        # Save signature to separate file for verification when opening existing reports
        sig_path = os.path.join(self.base_dir, "signature.txt")
        with open(sig_path, "w") as f:
            f.write(self.metadata['signature'])
        
        sig_hash = calculate_hash(sig_path)
        self._log_hash("signature.txt", sig_hash, "Digital Signature File")

    def _save_metadata_bin(self):
        meta_path = os.path.join(self.chain_of_custody_dir, "metadata_signature.bin")
        try:
            with open(meta_path, "wb") as f:
                pickle.dump(self.metadata, f)
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(meta_path, 2)
            
            report_hash = calculate_hash(meta_path)
            self._log_hash("Chain_of_Custody/metadata_signature.bin", report_hash, "Cryptographic Lock")
        except Exception as e:
            logging.error(f"Failed to save binary metadata: {e}")

    def _generate_network_baseline(self):
        """Generate network baseline JSON with active connections and ARP cache."""
        import json
        network_data = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "case_id": self.metadata['case_id'],
            "active_connections": [],
            "arp_cache": []
        }
        
        try:
            # Get active network connections
            import psutil
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED':
                    network_data["active_connections"].append({
                        "local_address": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A",
                        "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A",
                        "status": conn.status,
                        "pid": conn.pid
                    })
        except Exception as e:
            logging.warning(f"Failed to get network connections: {e}")
        
        try:
            # Get ARP cache
            result = subprocess.run('arp -a', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in result.stdout.split('\n'):
                if 'dynamic' in line.lower():
                    parts = line.split()
                    if len(parts) >= 2:
                        network_data["arp_cache"].append({
                            "ip": parts[0],
                            "mac": parts[1] if len(parts) > 1 else "N/A"
                        })
        except Exception as e:
            logging.warning(f"Failed to get ARP cache: {e}")
        
        network_path = os.path.join(self.system_dir, "network_baseline.json")
        with open(network_path, "w") as f:
            json.dump(network_data, f, indent=2)
        
        report_hash = calculate_hash(network_path)
        self._log_hash("System/network_baseline.json", report_hash, "Network Baseline")

    def _generate_user_profiles(self):
        """Generate user profiles CSV with SIDs and login history."""
        user_data = []
        
        try:
            # Get user accounts via wmic
            result = subprocess.run('wmic useraccount get name,sid,lastlogon', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip() and not line.startswith('Name')]
            
            for line in lines:
                # Parse WMIC output more flexibly
                parts = []
                current_part = ""
                for char in line:
                    if char == ' ' and current_part:
                        parts.append(current_part)
                        current_part = ""
                    elif char != ' ':
                        current_part += char
                if current_part:
                    parts.append(current_part)
                
                if len(parts) >= 2:
                    username = parts[0] if len(parts) > 0 else "N/A"
                    sid = parts[1] if len(parts) > 1 else "N/A"
                    lastlogon = parts[2] if len(parts) > 2 else "N/A"
                    user_data.append({
                        "Username": username,
                        "SID": sid,
                        "Last Logon": lastlogon
                    })
        except Exception as e:
            logging.warning(f"Failed to get user profiles: {e}")
        
        # Fallback: get current user info if WMIC fails
        if not user_data:
            import getpass
            try:
                # Get SID via wmic for current user
                result = subprocess.run(f'wmic useraccount where name="{getpass.getuser()}" get sid', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                lines = [line.strip() for line in result.stdout.split('\n') if line.strip() and not line.startswith('SID')]
                sid = lines[0] if lines else "N/A"
                user_data.append({
                    "Username": getpass.getuser(),
                    "SID": sid,
                    "Last Logon": "N/A"
                })
            except Exception as e:
                logging.warning(f"Failed to get current user: {e}")
                user_data.append({"Username": getpass.getuser(), "SID": "N/A", "Last Logon": "N/A"})
        
        user_path = os.path.join(self.system_dir, "user_profiles.csv")
        df = pd.DataFrame(user_data)
        df.to_csv(user_path, index=False)
        
        report_hash = calculate_hash(user_path)
        self._log_hash("System/user_profiles.csv", report_hash, "User Profiles")

    def _generate_investigator_audit(self):
        """Generate investigator audit log with case actions."""
        audit_path = os.path.join(self.chain_of_custody_dir, "investigator_audit.log")
        
        # Generate audit log content
        audit_content = "=" * 70 + "\n"
        audit_content += "           I N V E S T I G A T O R   A U D I T   L O G\n"
        audit_content += "=" * 70 + "\n"
        audit_content += f"Case ID: {self.metadata['case_id']}\n"
        audit_content += f"Investigator: {self.metadata['investigator']}\n"
        audit_content += f"Agency/ID: {self.metadata['agency']}\n"
        audit_content += f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        audit_content += "-" * 70 + "\n\n"
        
        audit_content += "[+] CASE INITIALIZATION\n"
        audit_content += f"  - Case ID: {self.metadata['case_id']}\n"
        audit_content += f"  - Investigator: {self.metadata['investigator']}\n"
        audit_content += f"  - Agency: {self.metadata['agency']}\n"
        audit_content += f"  - Description: {self.metadata['description']}\n"
        audit_content += f"  - Signature: {self.metadata['signature']}\n"
        audit_content += f"  - Hostname: {self.metadata.get('hostname', 'N/A')}\n"
        audit_content += f"  - Output Path: {self.metadata.get('output_path', 'N/A')}\n\n"
        
        audit_content += "[+] EXTRACTION VECTORS\n"
        audit_content += "  - Evidence collection initiated\n"
        audit_content += "  - Browser artifacts extracted\n"
        audit_content += "  - System artifacts collected\n"
        audit_content += "  - Registry hives captured\n\n"
        
        audit_content += "[+] CHAIN OF CUSTODY\n"
        audit_content += "  - Evidence hashes logged\n"
        audit_content += "  - Metadata signature locked\n"
        audit_content += "  - Audit trail established\n\n"
        
        audit_content += "=" * 70 + "\n"
        audit_content += f"End of Audit Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        audit_content += "=" * 70 + "\n"
        
        # Save to Chain of Custody folder only
        with open(audit_path, "w") as f:
            f.write(audit_content)
        
        report_hash = calculate_hash(audit_path)
        self._log_hash("Chain_of_Custody/investigator_audit.log", report_hash, "Investigator Audit Log")

    def _is_admin(self):
        """Check if running with admin privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def _export_registry_hives(self):
        """Export registry hives if admin, otherwise scrape keys."""
        if self._is_admin():
            # Export full hives using reg save
            try:
                hives = ["SYSTEM", "SOFTWARE", "SAM"]
                for hive in hives:
                    output_path = os.path.join(self.registry_dir, f"{hive}.hive")
                    result = subprocess.run(['reg', 'save', f"HKLM\\{hive}", output_path, '/y'], 
                                          capture_output=True, text=True, 
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0:
                        self._log_hash(f"Registry/{hive}.hive", calculate_hash(output_path), f"Registry Hive Export")
            except Exception as e:
                logging.warning(f"Failed to export registry hives: {e}")
                self._scrape_registry_keys()
        else:
            # Fallback to scraping specific keys
            self._scrape_registry_keys()

    def _scrape_registry_keys(self):
        """Scrape specific registry keys using winreg and save as JSON."""
        import winreg
        import json
        
        registry_scrapes_dir = os.path.join(self.registry_dir, "Registry_Scrapes")
        ensure_dir(registry_scrapes_dir)
        
        # Keys to scrape
        keys_to_scrape = [
            (r"SYSTEM\CurrentControlSet\Enum\USBSTOR", "USBSTOR"),
            (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList", "Network_Profiles"),
            (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\UserAssist", "UserAssist")
        ]
        
        scraped_data = {}
        
        for key_path, key_name in keys_to_scrape:
            try:
                key_data = self._scrape_registry_key(winreg.HKEY_LOCAL_MACHINE, key_path)
                if key_data:
                    scraped_data[key_name] = key_data
                    
                    # Save individual JSON
                    json_path = os.path.join(registry_scrapes_dir, f"{key_name}.json")
                    with open(json_path, "w") as f:
                        json.dump(key_data, f, indent=2, default=str)
                    self._log_hash(f"Registry/Registry_Scrapes/{key_name}.json", calculate_hash(json_path), f"Registry Scrape")
            except Exception as e:
                logging.warning(f"Failed to scrape {key_name}: {e}")
        
        # Save combined scrape
        if scraped_data:
            combined_path = os.path.join(registry_scrapes_dir, "Combined_Scrapes.json")
            with open(combined_path, "w") as f:
                json.dump(scraped_data, f, indent=2, default=str)
            self._log_hash(f"Registry/Registry_Scrapes/Combined_Scrapes.json", calculate_hash(combined_path), "Combined Registry Scrapes")

    def _scrape_registry_key(self, hkey, key_path):
        """Recursively scrape a registry key and return data."""
        import winreg
        data = {}
        
        try:
            key = winreg.OpenKey(hkey, key_path)
            
            # Get values
            try:
                i = 0
                while True:
                    value_name, value_data, value_type = winreg.EnumValue(key, i)
                    data[value_name] = {
                        "data": str(value_data),
                        "type": value_type
                    }
                    i += 1
            except WindowsError:
                pass
            except Exception as e:
                # Suppress individual value errors
                pass
            
            # Get subkeys
            try:
                i = 0
                while True:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = f"{key_path}\\{subkey_name}"
                    # Skip Properties subkeys that often have access denied
                    if "Properties" not in subkey_path:
                        data[subkey_name] = self._scrape_registry_key(hkey, subkey_path)
                    i += 1
            except WindowsError:
                pass
            except Exception as e:
                # Suppress individual subkey errors
                pass
            
            winreg.CloseKey(key)
        except WindowsError as e:
            # Suppress access denied errors silently
            if e.winerror == 5:  # Access denied
                pass
            else:
                logging.debug(f"WindowsError scraping {key_path}: {e}")
        except Exception as e:
            logging.debug(f"Error scraping {key_path}: {e}")
        
        return data

    def _run_lazarus_for_browser(self, browser_name, recovered_dir, source_df):
        """Run Lazarus to recover deleted history for a specific browser."""
        try:
            # Get the original history file path from the source dataframe
            if not source_df.empty and 'File Path' in source_df.columns:
                history_path = source_df['File Path'].iloc[0]
                if os.path.exists(history_path):
                    # Try to carve deleted URLs from SQLite free-list
                    recovered_urls = self._carve_sqlite_freelist(history_path)
                    
                    if recovered_urls:
                        # Save as CSV instead of text log
                        recovered_df = pd.DataFrame({
                            'URL': recovered_urls,
                            'Browser': browser_name,
                            'Source': 'Lazarus Recovery',
                            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        recovery_csv = os.path.join(recovered_dir, f"{browser_name}_Recovered_History.csv")
                        recovered_df.to_csv(recovery_csv, index=False)
                        self._log_hash(f"Browsers/{browser_name}/recovered/{browser_name}_Recovered_History.csv",
                                     calculate_hash(recovery_csv), "Deleted History Recovery")
                    else:
                        # Save a note that no deleted history was found
                        recovery_log = os.path.join(recovered_dir, f"{browser_name}_No_Recovery.txt")
                        with open(recovery_log, "w") as f:
                            f.write(f"=== ABYSS LAZARUS: DELETED HISTORY RECOVERY ===\n")
                            f.write(f"Browser: {browser_name}\n")
                            f.write(f"History File: {history_path}\n")
                            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"\nNo deleted history found in SQLite free-list.\n")
                        self._log_hash(f"Browsers/{browser_name}/recovered/{browser_name}_No_Recovery.txt",
                                     calculate_hash(recovery_log), "Recovery Status")
        except Exception as e:
            logging.warning(f"Failed to run Lazarus for {browser_name}: {e}")

    def _carve_sqlite_freelist(self, db_path):
        """Carve deleted URLs from SQLite free-list."""
        try:
            import sqlite3
            recovered_urls = []
            
            # Connect to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Try to read raw database file for free-list data
            try:
                with open(db_path, 'rb') as f:
                    data = f.read()
                    
                # Simple URL pattern matching in raw data
                import re
                url_pattern = rb'https?://[^\s<>"\'\)]+'
                matches = re.findall(url_pattern, data)
                
                # Decode and filter
                for match in matches:
                    try:
                        url = match.decode('utf-8', errors='ignore')
                        if len(url) > 10 and url not in recovered_urls:
                            recovered_urls.append(url)
                    except:
                        pass
            except Exception as e:
                logging.warning(f"Free-list carving failed: {e}")
            
            conn.close()
            return recovered_urls[:100]  # Limit to 100 URLs
        except Exception as e:
            logging.warning(f"Failed to carve {db_path}: {e}")
            return []

    def generate(self, artifacts, browser_paths, leaks=None, persona=None, ads_data=None, carved_urls=None):
        self._generate_description()
        self._generate_sys_info(browser_paths)
        self._save_metadata_bin()
        self._generate_network_baseline()
        self._generate_user_profiles()
        self._generate_investigator_audit()
        self._export_registry_hives()
        
        # Save Platinum Intelligence
        if persona:
            persona_path = os.path.join(self.intelligence_dir, "User_Persona_Report.txt")
            with open(persona_path, "w") as f:
                f.write(persona)
                
        if ads_data:
            ads_df = pd.DataFrame(ads_data)
            ads_path = os.path.join(self.intelligence_dir, "Zone_Identifier_Leaks.csv")
            ads_df.to_csv(ads_path, index=False)
            
        if carved_urls:
            # Save carved URLs per browser if browser info is available
            if browser_paths:
                # Handle different browser_paths formats
                for browser_item in browser_paths:
                    if isinstance(browser_item, (list, tuple)) and len(browser_item) >= 1:
                        browser_name = browser_item[0]
                    elif isinstance(browser_item, str):
                        browser_name = browser_item
                    else:
                        continue
                    
                    b_dir = os.path.join(self.browsers_dir, browser_name.replace(" ", "_"))
                    b_recovered_dir = os.path.join(b_dir, "recovered")
                    if os.path.exists(b_recovered_dir):
                        # Filter URLs for this browser (simplified - in reality would need better filtering)
                        browser_carved = [url for url in carved_urls if browser_name.lower() in url.lower()]
                        if browser_carved:
                            carved_path = os.path.join(b_recovered_dir, f"{browser_name}_Deleted_History.txt")
                            with open(carved_path, "w") as f:
                                f.write(f"=== ABYSS LAZARUS: DELETED HISTORY RECOVERY ===\n")
                                f.write(f"Browser: {browser_name}\n")
                                f.write(f"Total Recovered: {len(browser_carved)}\n\n")
                                f.write("\n".join(browser_carved))
                            self._log_hash(f"Browsers/{browser_name.replace(' ', '_')}/recovered/{browser_name}_Deleted_History.txt",
                                         calculate_hash(carved_path), "Deleted History Recovery")
            else:
                # Fallback - save to browser recovered folders if available
                pass

        # Save DNS Leaks to DNSRecords folder
        if leaks:
            leaks_df = pd.DataFrame(leaks)
            out_path = os.path.join(self.dns_records_dir, "Incognito_DNS_Leaks.csv")
            leaks_df.to_csv(out_path, index=False)
            self._log_hash(f"Extraction/DNSRecords/Incognito_DNS_Leaks.csv", calculate_hash(out_path), "Incognito Leak Detection")

        df = pd.DataFrame(artifacts)
        
        if not df.empty:
            unique_sources = df['Source'].unique()
            
            # Dictionary to avoid duplicate hex dumps
            hex_dumped_files = set()
            
            for source in unique_sources:
                source_df = df[df['Source'] == source]
                
                # Capture the original File Path for MFT Records
                file_paths = source_df['File Path'].unique()
                for fp in file_paths:
                    if pd.notna(fp) and str(fp) not in hex_dumped_files and os.path.exists(str(fp)):
                        generate_hex_dump(str(fp), self.raw_dir, max_bytes=512)
                        hex_dumped_files.add(str(fp))
                
                # Handle Registry
                if "Registry" in source:
                    clean_source = source.replace("Registry_", "")
                    filename = f"{clean_source}.csv"
                    out_path = os.path.join(self.registry_dir, filename)
                    source_df.to_csv(out_path, index=False)
                    self._log_hash(f"Registry/{filename}", calculate_hash(out_path), f"Registry Dump")

                # Handle Notepad Tab
                elif source.startswith("Notepad Tab"):
                    clean_source = re.sub(r'[^A-Za-z0-9]', '_', source)
                    filename = f"{clean_source}.csv"
                    out_path = os.path.join(self.tabstate_archive, filename)
                    source_df.to_csv(out_path, index=False)
                    self._log_hash(f"Notepad/TabState_Archive/{filename}", calculate_hash(out_path), f"Recovered Tab")
                    
                # Handle OS Artifacts
                elif source.startswith("OS_"):
                    clean_source = source.replace("OS_", "")
                    filename = f"{clean_source}_Recovered.csv"
                    out_path = os.path.join(self.hits_dir, filename)
                    source_df.to_csv(out_path, index=False)
                    self._log_hash(f"OS_Memory/{filename}", calculate_hash(out_path), f"OS Memory Dump")
                    
                # Handle Browser History
                elif "History" in source:
                    browser_name = source.replace(" History", "").replace(" ", "_")
                    b_dir = os.path.join(self.browsers_dir, browser_name)
                    ensure_dir(b_dir)
                    
                    # Create subfolders for each browser
                    b_raw_dir = os.path.join(b_dir, "raw")
                    b_visuals_dir = os.path.join(b_dir, "visuals")
                    b_recovered_dir = os.path.join(b_dir, "recovered")
                    ensure_dir(b_raw_dir)
                    ensure_dir(b_visuals_dir)
                    ensure_dir(b_recovered_dir)
                    
                    filename = f"{browser_name}_History_Source.csv"
                    out_path = os.path.join(b_raw_dir, filename)
                    source_df.to_csv(out_path, index=False)
                    self._log_hash(f"Browsers/{browser_name}/raw/{filename}", calculate_hash(out_path), "Raw Database Copy")
                    
                    flagged_df = source_df[source_df['Flagged'] != 'No']
                    if not flagged_df.empty:
                        f_path = os.path.join(b_raw_dir, f"Flagged_{browser_name}.csv")
                        flagged_df.to_csv(f_path, index=False)
                        self._log_hash(f"Browsers/{browser_name}/raw/Flagged_{browser_name}.csv", calculate_hash(f_path), "Flagged Alerts")
                    
                    search_df = source_df[source_df['Content'].str.contains("search\?q=|search_query=|query=", na=False, case=False)]
                    if not search_df.empty:
                        s_path = os.path.join(b_raw_dir, f"{browser_name}_Search_Terms.csv")
                        search_df.to_csv(s_path, index=False)
                        self._log_hash(f"Browsers/{browser_name}/raw/{browser_name}_Search_Terms.csv", calculate_hash(s_path), "Extracted Search Queries")
                    
                    generate_browser_visuals(source_df, browser_name, b_visuals_dir)
                    
                    # Run Lazarus for this browser to recover deleted history
                    self._run_lazarus_for_browser(browser_name, b_recovered_dir, source_df)
                    
                else:
                    # Fallback for other data
                    clean_source = re.sub(r'[^A-Za-z0-9]', '_', source)
                    filename = f"{clean_source}.csv"
                    out_path = os.path.join(self.raw_dir, filename)
                    source_df.to_csv(out_path, index=False)
                    self._log_hash(f"Raw_Data/{filename}", calculate_hash(out_path), f"Raw Evidence")

        found_browsers = set(b[0] for b in browser_paths) if browser_paths else set()
        for browser in found_browsers:
            source_name = f"{browser} History"
            if df.empty or source_name not in df['Source'].values:
                browser_name = browser.replace(" ", "_")
                b_dir = os.path.join(self.browsers_dir, browser_name)
                ensure_dir(b_dir)
                filename = f"{browser_name}_History_Source.csv"
                out_path = os.path.join(b_dir, filename)
                
                empty_df = pd.DataFrame(columns=[
                    "Source", "File Path", "Content", "Title/Extra", "Visit Count", 
                    "Timestamp", "File Created", "File Modified", "Evidence Hash", "Flagged"
                ])
                empty_df.to_csv(out_path, index=False)
                self._log_hash(f"Browsers/{browser_name}/{filename}", calculate_hash(out_path), f"Empty {source_name} Artifacts")

        logging.info(f"ABYSS Hierarchical Suite compiled at: {self.base_dir}")
        return self.base_dir
