# ABYSS - Advanced Browser & System Yields Surveillance

**Advanced Digital Forensics and Incident Response (DFIR) Toolkit for Windows**

ABYSS is a comprehensive digital forensics toolkit designed for deep intelligence synthesis and artifact extraction on Windows systems. It provides both a graphical user interface (GUI) and a command-line interface (CLI) for forensic investigations.

## Tool Overview

ABYSS enables forensic investigators to extract, analyze, and preserve digital evidence from multiple sources including web browsers, system artifacts, and volatile memory. The tool maintains chain of custody through cryptographic signatures and hash verification.

### Key Features

- **Browser History Extraction**: Supports Chrome, Edge, Brave, Opera, Vivaldi, and Firefox with deep scan for portable installations
- **Notepad Tab Recovery**: Recovers unsaved Windows 11 Notepad tabs from binary files
- **System Profiling**: Collects comprehensive system information including installed software, network configuration, and user accounts
- **Digital Signature Verification**: Cryptographic locking of case metadata with signature verification
- **Chain of Custody**: Automatic hash logging for all extracted evidence
- **Intelligence Generation**: Automated user persona analysis and correlation reports
- **Deleted Data Recovery**: Lazarus module for carving deleted URLs from SQLite free-list
- **Zone Identifier Detection**: Identifies downloaded files through NTFS Alternate Data Streams
- **Dual Interface**: Both GUI (main.py) and CLI (abyss.py) versions available

## Installation Instructions

### Prerequisites

- **Operating System**: Windows 10 or Windows 11
- **Python Version**: Python 3.10 or higher
- **Administrator Privileges**: Required for full functionality (VSS recovery, registry access)

### Dependencies

Install the required Python packages:

```bash
pip install pandas customtkinter matplotlib seaborn wordcloud tldextract psutil
```

### Environment Setup

1. Clone or download the ABYSS repository
2. Navigate to the project directory
3. Install dependencies using the command above
4. Ensure the `modules` folder is present with all required module files

## Execution Steps

### GUI Version (main.py)

Run the graphical interface:

```bash
python main.py
```

**GUI Workflow:**
1. Launch the application
2. Choose between "New Investigation" or "Open Existing Report"
3. For new investigations:
   - Enter Case ID (format: ABYSS-YYYYMMDD-XXX)
   - Provide investigator name, agency, and digital signature
   - Select extraction vectors (Browser, Notepad, OS Memory)
   - Click "INITIATE PROTOCOL" to begin extraction
4. For existing reports:
   - Enter report path and digital signature
   - Click "OPEN REPORT" to load the case
5. View results in the Evidence Vault and Intelligence tabs

### CLI Version (abyss.py)

Run the command-line interface:

```bash
python abyss.py
```

**CLI Workflow:**
1. The tool displays the ABYSS ASCII art header
2. Enter Case ID in format ABYSS-YYYYMMDD-XXX
3. Provide investigator name, agency, digital signature
4. Hostname is auto-detected (can be modified)
5. Select output path (default: reports)
6. Enter case description
7. Select extraction vectors (1=Browser, 2=Notepad, 3=OS, 4=All)
8. Monitor extraction logs in real-time
9. Report location is displayed at completion

## Platform Compatibility

- **Supported Platforms**: Windows 10, Windows 11
- **Python Support**: Python 3.10+
- **Architecture**: x64 (64-bit)

## Troubleshooting

### Common Issues

**Issue: Permission Denied Errors**
- **Solution**: Run the application as Administrator
- **Reason**: Some operations require elevated privileges (registry access, VSS recovery)

**Issue: Database Locked**
- **Solution**: Close all browser instances before running extraction
- **Note**: ABYSS attempts VSS shadow copy recovery if database is locked

**Issue: Import Errors**
- **Solution**: Ensure all dependencies are installed using pip
- **Check**: Verify Python version is 3.10 or higher

**Issue: Signature Verification Failed**
- **Solution**: Ensure the digital signature matches the one used when the case was created
- **Note**: Legacy reports without signature.txt will allow access with a warning

**Issue: Empty Results**
- **Solution**: Verify browser history files exist in standard locations
- **Check**: Ensure the user has browser history to extract

**Issue: Encoding Errors in CLI**
- **Solution**: The CLI now includes UTF-8 encoding fixes for Windows
- **Note**: If issues persist, try running in PowerShell instead of CMD

### Performance Optimization

If the application lags when opening large files:
- The GUI has been optimized with slower logo animations and reduced preview sizes
- CSV previews are limited to 20 rows for faster loading
- Hex dump previews are limited to 32KB
- Logo animation is disabled after main GUI loads

## File Structure

```
HistoryParser/
├── main.py                 # GUI version
├── abyss.py                # CLI version
├── modules/
│   ├── browser_parser.py   # Browser history extraction
│   ├── notepad_parser.py   # Notepad tab recovery
│   ├── system_profiler.py  # System information collection
│   ├── report_generator.py # Report generation
│   ├── intelligence_engine.py # User persona analysis
│   ├── lazus_module.py     # Deleted data recovery
│   └── utils.py            # Utility functions
├── reports/                # Output directory for cases
└── assets/                 # Logo and image assets
```

## Output Structure

Each case generates a structured report directory:

```
reports/ABYSS-YYYYMMDD-XXX/
├── Case-Description.txt    # Case metadata
├── signature.txt           # Digital signature
├── Chain_of_Custody/
│   ├── evidence_hashes.log # SHA-256 hashes
│   ├── investigator_audit.log
│   └── metadata_signature.bin
├── System/
│   ├── sysinfo.txt
│   ├── network_baseline.json
│   └── user_profiles.csv
├── Extraction/
│   ├── Browsers/           # Browser artifacts
│   ├── Notepad/            # Notepad tabs
│   ├── Registry/           # Registry scrapes
│   └── DNSRecords/         # DNS leak detection
└── Hits/
    └── Intelligence/       # Persona reports
```

## Security Considerations

- All source files are copied to a temporary sandbox before processing
- SHA-256 hashes are calculated and verified for integrity
- Case metadata is cryptographically signed
- Evidence hashes are logged for chain of custody
- No modification of source files during extraction

## License

This tool is intended for authorized forensic investigations only. Users must comply with all applicable laws and regulations regarding digital forensics and privacy.
