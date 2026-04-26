#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABYSS - Advanced Browser & System Yields Surveillance
Terminal-based CLI version
"""

import os
import sys
import logging
from datetime import datetime
from modules.browser_parser import get_browser_paths, extract_history_data
from modules.notepad_parser import parse_notepad_tabs
from modules.system_profiler import get_system_profile
from modules.report_generator import ReportGenerator
from modules.intelligence_engine import generate_user_persona, generate_master_correlator
from modules.lazarus_module import carve_sqlite_freelist, check_zone_identifiers
from modules.utils import ensure_dir

# Set UTF-8 encoding for stdout to handle special characters
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configure logging for CLI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

# ANSI color codes for terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header():
    """Display ABYSS ASCII art header"""
    header = f"""
{Colors.CYAN}{Colors.BOLD}
       _         ____   __     __   _____    _____ 
      / \\       |  _ \\  \\ \\   / /  / ____|  / ____|
     / _ \\      | |_) |  \\ \\_/ /  | (___   | (___  
    / ___ \\     |  _ <    \\   /    \\___ \\   \\___ \\ 
   / _/ \\_ \\    | |_) |    | |     ____) |  ____) |
  /_/     \\_\\   |____/     |_|    |_____/  |_____/
  
  Advanced Browser & System Yields Surveillance
  Terminal Edition v2.0
{Colors.END}
"""
    print(header)

def print_log_header():
    """Display log section header"""
    print(f"\n{Colors.YELLOW}{Colors.BOLD}{'='*70}")
    print("  EXECUTION LOGS")
    print(f"{'='*70}{Colors.END}\n")

def print_success(message):
    """Print success message in green"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message):
    """Print error message in red"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_info(message):
    """Print info message in cyan"""
    print(f"{Colors.CYAN}ℹ {message}{Colors.END}")

def print_warning(message):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

def get_input(prompt, default=None, required=True):
    """Get user input with optional default and validation"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    
    value = input(prompt).strip()
    
    if not value and default:
        return default
    
    if not value and required:
        print_error("This field is required.")
        return get_input(prompt, default, required)
    
    return value

def get_case_id():
    """Get and validate case ID in ABYSS-YYYYMMDD-XXX format"""
    while True:
        case_id = get_input("Enter Case ID (format: ABYSS-YYYYMMDD-XXX)")
        
        # Validate format
        parts = case_id.split('-')
        if len(parts) == 3 and parts[0] == "ABYSS" and len(parts[1]) == 8 and parts[1].isdigit():
            return case_id
        else:
            print_error("Invalid format. Use: ABYSS-YYYYMMDD-XXX (e.g., ABYSS-20260426-001)")

def select_extraction_vectors():
    """Let user select which extraction vectors to run"""
    print(f"\n{Colors.BOLD}Select Extraction Vectors:{Colors.END}")
    print("1. Browser History")
    print("2. Notepad Tabs")
    print("3. OS Memory/Artifacts")
    print("4. All of the above")
    
    choice = get_input("Enter choice (1-4)", default="4")
    
    vectors = {
        'browser': False,
        'notepad': False,
        'os': False
    }
    
    if choice == '1':
        vectors['browser'] = True
    elif choice == '2':
        vectors['notepad'] = True
    elif choice == '3':
        vectors['os'] = True
    elif choice == '4':
        vectors['browser'] = True
        vectors['notepad'] = True
        vectors['os'] = True
    else:
        print_warning("Invalid choice, defaulting to all vectors")
        vectors['browser'] = True
        vectors['notepad'] = True
        vectors['os'] = True
    
    return vectors

def run_forensic_extraction(case_metadata, vectors):
    """Run the forensic extraction process"""
    print_log_header()
    
    all_artifacts = []
    browser_paths = []
    carved_urls = []
    ads_targets = []
    
    # Browser extraction
    if vectors['browser']:
        print_info("Initiating Browser History Extraction...")
        try:
            browser_paths_found = get_browser_paths()
            print_info(f"Found {len(browser_paths_found)} browser(s)")
            
            for browser_name, history_path, profile_name in browser_paths_found:
                print_info(f"Extracting from {browser_name} ({profile_name})...")
                artifacts = extract_history_data(history_path, browser_name, profile_name)
                all_artifacts.extend(artifacts)
                browser_paths.append((browser_name, history_path))
                print_success(f"Extracted {len(artifacts)} artifacts from {browser_name}")
            
            # Run Lazarus for deleted history recovery
            print_info("Running Lazarus Module for deleted history recovery...")
            for browser_name, history_path in browser_paths:
                if os.path.exists(history_path):
                    recovered = carve_sqlite_freelist(history_path)
                    if recovered:
                        carved_urls.extend(recovered)
                        print_success(f"Recovered {len(recovered)} deleted URLs from {browser_name}")
        except Exception as e:
            print_error(f"Browser extraction failed: {e}")
    
    # Notepad extraction
    if vectors['notepad']:
        print_info("Initiating Notepad Tab Extraction...")
        try:
            artifacts = parse_notepad_tabs()
            all_artifacts.extend(artifacts)
            print_success(f"Extracted {len(artifacts)} notepad artifacts")
        except Exception as e:
            print_error(f"Notepad extraction failed: {e}")
    
    # OS extraction
    if vectors['os']:
        print_info("Initiating OS Memory/Artifacts Extraction...")
        try:
            # For CLI, we'll do basic system profiling
            profile = get_system_profile()
            print_success("System profile collected")
            
            # Add system info as artifacts
            all_artifacts.append({
                "Source": "OS_System",
                "File Path": "N/A",
                "Content": str(profile),
                "Title/Extra": "System Profile",
                "Visit Count": "N/A",
                "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "File Created": "N/A",
                "File Modified": "N/A",
                "Evidence Hash": "N/A",
                "Flagged": "No"
            })
        except Exception as e:
            print_error(f"OS extraction failed: {e}")
    
    # Check for Zone Identifier leaks
    print_info("Checking for Zone Identifier (ADS) leaks...")
    try:
        # Check common download locations
        paths_to_check = [
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents")
        ]
        ads_data = check_zone_identifiers(paths_to_check)
        if ads_data:
            ads_targets.extend(ads_data)
            print_success(f"Found {len(ads_data)} Zone Identifier leaks")
        else:
            print_info("No Zone Identifier leaks detected")
    except Exception as e:
        print_warning(f"Zone Identifier check failed: {e}")
    
    # Generate intelligence
    persona = None
    if all_artifacts:
        print_info("Generating User Persona Analysis...")
        try:
            persona = generate_user_persona(all_artifacts)
            print_success("User persona analysis complete")
        except Exception as e:
            print_warning(f"Persona generation failed: {e}")
    
    return all_artifacts, browser_paths, carved_urls, ads_targets, persona

def main():
    """Main CLI execution"""
    # Clear screen and show header
    os.system('cls' if os.name == 'nt' else 'clear')
    print_header()
    
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.BOLD}                    CASE INITIALIZATION{Colors.END}")
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.END}\n")
    
    # Collect case information
    case_id = get_case_id()
    investigator = get_input("Investigator Name", required=True)
    agency = get_input("Agency/ID", default="N/A")
    signature = get_input("Digital Signature", required=True)
    
    # Auto-detect hostname
    import socket
    detected_hostname = socket.gethostname()
    hostname = get_input("Hostname", default=detected_hostname)
    
    output_path = get_input("Output Path", default="reports")
    description = get_input("Case Description", required=True)
    
    # Select extraction vectors
    vectors = select_extraction_vectors()
    
    # Create metadata
    case_metadata = {
        "investigator": investigator,
        "agency": agency,
        "signature": signature,
        "case_id": case_id,
        "description": description,
        "hostname": hostname,
        "output_path": output_path
    }
    
    print(f"\n{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.END}")
    print(f"{Colors.BOLD}                  INITIATING EXTRACTION{Colors.END}")
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.END}")
    
    # Run extraction
    all_artifacts, browser_paths, carved_urls, ads_targets, persona = run_forensic_extraction(
        case_metadata, vectors
    )
    
    # Generate report
    print_info("Generating ABYSS Report...")
    try:
        report_gen = ReportGenerator(case_metadata)
        report_dir = report_gen.generate(
            all_artifacts,
            browser_paths,
            leaks=ads_targets,
            persona=persona,
            carved_urls=carved_urls
        )
        print_success(f"Report generated successfully at: {report_dir}")
        
        # Generate Neural Map HTML report
        print_info("Generating Neural Map HTML report...")
        try:
            from modules.neural_map import generate_neural_map_html
            html_path = generate_neural_map_html(report_dir)
            if html_path:
                print_success(f"Neural Map HTML generated at: {html_path}")
        except Exception as e:
            print_warning(f"Neural Map generation failed: {e}")
    except Exception as e:
        print_error(f"Report generation failed: {e}")
        return
    
    # Final summary
    print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*70}")
    print("  EXTRACTION COMPLETE")
    print(f"{'='*70}{Colors.END}\n")
    
    print(f"{Colors.BOLD}Case ID:{Colors.END} {case_id}")
    print(f"{Colors.BOLD}Investigator:{Colors.END} {investigator}")
    print(f"{Colors.BOLD}Total Artifacts:{Colors.END} {len(all_artifacts)}")
    print(f"{Colors.BOLD}Report Location:{Colors.END} {report_dir}")
    
    print(f"\n{Colors.CYAN}{Colors.BOLD}► Report folder:{Colors.END} {report_dir}")
    print(f"{Colors.CYAN}{Colors.BOLD}► To open folder, run:{Colors.END} explorer \"{report_dir}\"")
    print(f"{Colors.CYAN}{Colors.BOLD}► To open in terminal, run:{Colors.END} cd \"{report_dir}\"\n")
    
    print(f"{Colors.GREEN}{Colors.BOLD}ABYSS Protocol Complete.{Colors.END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠ Extraction interrupted by user.{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{Colors.RED}✗ Fatal error: {e}{Colors.END}")
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
