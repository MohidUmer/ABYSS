# ABYSS Forensic Suite: User Guide

**ABYSS - A Windows-based digital forensics toolkit for extracting browser history, system artifacts, and volatile memory evidence with chain of custody verification.**

## Table of Contents
1. [Introduction to Tool and Forensic Domain](#1-introduction-to-tool-and-forensic-domain)
2. [Legal & Ethical Considerations](#2-legal--ethical-considerations)
3. [System Requirements](#3-system-requirements)
4. [Installation Steps](#4-installation-steps)
5. [Step-by-Step Usage Instructions](#5-step-by-step-usage-instructions)
6. [Example Cases](#6-example-cases)
7. [Interpretation of Results](#7-interpretation-of-results)
8. [Work Division](#8-work-division)

---

## 1. Introduction to Tool and Forensic Domain

### What is ABYSS?

ABYSS (Advanced Browser & System Yields Surveillance) is a comprehensive digital forensics and incident response (DFIR) toolkit designed for Windows systems. It enables forensic investigators to extract, analyze, and preserve digital evidence from multiple sources including web browsers, system artifacts, and volatile memory.

### Forensic Domain Context

Digital forensics is the application of scientific methods to digital evidence for legal purposes. ABYSS operates in the following forensic domains:

- **Browser Forensics**: Extraction and analysis of web browser history, cached data, and user activity patterns
- **System Forensics**: Collection of system configuration, user accounts, and network information
- **Memory Forensics**: Recovery of volatile data including unsaved documents and deleted records
- **Chain of Custody**: Maintaining the integrity and authenticity of digital evidence through cryptographic verification

### Tool Capabilities

ABYSS provides two interfaces for forensic investigations:

1. **Graphical User Interface (GUI)** - `main.py`: Full-featured interface with visual evidence vault
2. **Command Line Interface (CLI)** - `abyss.py`: Terminal-based interface for automated workflows

The tool supports extraction from:
- Web browsers (Chrome, Edge, Brave, Opera, Vivaldi, Firefox)
- Windows 11 Notepad (unsaved tab recovery)
- System profiles (hardware, network, user accounts)
- Deleted data (SQLite free-list carving)
- File metadata (Zone Identifier detection)

---

## 2. Legal & Ethical Considerations

### Legal Requirements

**IMPORTANT**: Use of ABYSS must comply with all applicable laws and regulations. Users must:

- Obtain proper legal authorization (warrants, court orders, or consent) before conducting forensic examinations
- Ensure the investigation scope matches the authorization granted
- Maintain proper chain of custody documentation for all evidence
- Follow local, state, and federal laws regarding digital privacy and computer crime

### Ethical Guidelines

Forensic investigators using ABYSS should:

- Only examine systems for which they have authorized access
- Protect the privacy of individuals not involved in the investigation
- Document all procedures and findings accurately
- Maintain professional standards and avoid conflicts of interest
- Report findings truthfully without bias or omission

### Evidence Integrity

ABYSS implements several features to maintain evidence integrity:

- **SHA-256 Hashing**: All extracted files are hashed and logged for verification
- **Digital Signatures**: Case metadata is cryptographically signed to prevent tampering
- **Sandbox Processing**: Source files are copied to temporary locations before analysis
- **Read-Only Operations**: Original evidence files are never modified during extraction

### Disclaimer

This tool is intended for authorized forensic investigations only. Misuse of this software for unauthorized access to computer systems or data may violate criminal laws. The developers assume no liability for misuse of this software.

---

## 3. System Requirements

### Hardware Requirements

- **Processor**: Intel Core i5 or equivalent (64-bit)
- **RAM**: Minimum 8GB, recommended 16GB for large datasets
- **Storage**: Minimum 10GB free space for temporary files and reports
- **Display**: 1920x1080 resolution recommended for GUI

### Software Requirements

- **Operating System**: Windows 10 or Windows 11
- **Python**: Version 3.10 or higher
- **Administrator Privileges**: Required for full functionality

### Network Requirements

- No active internet connection required for basic operation
- Some features may attempt network operations (e.g., opening reports in browser)

### Optional Software

- **Microsoft Excel**: For viewing CSV reports
- **Text Editor**: For viewing log files and raw data
- **Hex Editor**: For detailed binary analysis (optional)

---

## 4. Installation Steps

### Step 1: Obtain the Software

Download or clone the ABYSS repository to your local system. Ensure all files are present including:
- `main.py` (GUI version)
- `abyss.py` (CLI version)
- `modules/` directory with all Python modules
- `assets/` directory with logo and image files

### Step 2: Install Python

If Python is not already installed:

1. Download Python 3.10 or higher from [python.org](https://www.python.org/downloads/)
2. Run the installer with "Add Python to PATH" option checked
3. Verify installation by running: `python --version`

### Step 3: Install Dependencies

Open a command prompt or terminal in the ABYSS directory and run:

```bash
pip install pandas customtkinter matplotlib seaborn wordcloud tldextract psutil
```

### Step 4: Verify Installation

Test the installation by running:

```bash
python main.py
```

The GUI should launch successfully. If errors occur, verify:
- Python version is 3.10+
- All dependencies are installed
- You have administrator privileges
- All module files are present in the `modules/` directory

### Step 5: Configure (Optional)

Default configuration should work for most scenarios. Optional configuration includes:
- Custom output directory (default: `reports/`)
- Custom temporary directory (default: `reports/temp/`)

---

## 5. Step-by-Step Usage Instructions

### GUI Version (main.py)

#### Step 1: Launch the Application

Run the application with administrator privileges:

```bash
python main.py
```

#### Step 2: Initialize a New Case

1. Select "New Investigation" radio button
2. Enter the following information:
   - **Case ID**: Format as ABYSS-YYYYMMDD-XXX (e.g., ABYSS-20260426-001)
   - **Investigator Name**: Your name or badge ID
   - **Agency/ID**: Your organization or unit
   - **Digital Signature**: A unique signature for case verification
   - **Hostname**: Auto-detected, can be modified
   - **Output Path**: Default is `reports/`, can be changed
   - **Description**: Brief description of the investigation scope

3. Click "INITIATE PROTOCOL" to proceed

#### Step 3: Select Extraction Vectors

Choose which data sources to extract:

- **Browser**: Extract web browser history from all detected browsers
- **Notepad**: Recover unsaved Windows 11 Notepad tabs
- **OS Memory**: Collect system profile and configuration

#### Step 4: Monitor Extraction Progress

The Console tab displays real-time extraction logs showing:
- Detected browsers and their locations
- Number of artifacts extracted
- Any warnings or errors encountered
- Recovery of deleted data

#### Step 5: Review Results

After extraction completes:

1. **Evidence Vault Tab**: Browse extracted files in a hierarchical tree view
   - Navigate folders by clicking on directory names
   - Preview files by clicking on file names
   - View hex dumps for binary files
   - Toggle "Forensic Skin Mode" to see file hashes and metadata

2. **Intelligence Tab**: View generated reports
   - User Persona Report
   - System Profile
   - Case Summary

#### Step 6: Open Existing Report (Optional)

To view a previously created report:

1. Select "Open Existing Report" radio button
2. Enter the report path or use "Browse" button
3. Enter the digital signature used when the case was created
4. Click "OPEN REPORT"
5. The Evidence Vault will populate with the existing data

### CLI Version (abyss.py)

#### Step 1: Launch the CLI

Run the CLI version:

```bash
python abyss.py
```

The ABYSS ASCII art header will be displayed.

#### Step 2: Enter Case Information

Provide the following information when prompted:

1. **Case ID**: Format as ABYSS-YYYYMMDD-XXX
2. **Investigator Name**: Your name or badge ID
3. **Agency/ID**: Your organization (default: N/A)
4. **Digital Signature**: Unique signature for verification
5. **Hostname**: Auto-detected (can be modified)
6. **Output Path**: Default is `reports/`
7. **Case Description**: Brief investigation description

#### Step 3: Select Extraction Vectors

Choose from the following options:
- 1: Browser History only
- 2: Notepad Tabs only
- 3: OS Memory only
- 4: All vectors (default)

#### Step 4: Monitor Extraction

Watch the real-time logs showing:
- Color-coded status messages (green for success, red for errors, yellow for warnings)
- Number of artifacts extracted from each source
- Recovery of deleted URLs
- Zone Identifier leak detection

#### Step 5: Access Results

Upon completion, the CLI displays:
- Total artifacts extracted
- Report location
- Command to open the report folder in Windows Explorer

---

## 6. Example Cases

### Case 1: Browser History Analysis

**Scenario**: Investigate web browsing activity of a suspect's computer.

**Steps**:
1. Launch ABYSS GUI
2. Create new case with ID: ABYSS-20260426-001
3. Select "Browser" extraction vector
4. Run extraction
5. Review results in Evidence Vault under `Extraction/Browsers/`

**Expected Results**:
- CSV files containing complete browser history
- Search terms extracted from history
- Deleted URLs recovered via Lazarus module
- Timestamps for each visited page

**Forensic Relevance**: Establishes timeline of web activity, identifies visited domains, and may reveal intent or knowledge relevant to the investigation.

### Case 2: Notepad Tab Recovery

**Scenario**: Recover unsaved documents from a suspect's computer.

**Steps**:
1. Launch ABYSS GUI
2. Create new case with ID: ABYSS-20260426-002
3. Select "Notepad" extraction vector
4. Run extraction
5. Review results in Evidence Vault under `Extraction/Notepad/`

**Expected Results**:
- Recovered text from unsaved Notepad tabs
- Timestamps when tabs were last active
- Raw binary data for advanced analysis

**Forensic Relevance**: May recover critical information that was never saved, including notes, codes, or other relevant data.

### Case 3: System Profiling

**Scenario**: Collect comprehensive system information for evidence documentation.

**Steps**:
1. Launch ABYSS CLI
2. Create new case with ID: ABYSS-20260426-003
3. Select "OS Memory" extraction vector
4. Run extraction
5. Review `System/` directory in output

**Expected Results**:
- System hardware information
- Network configuration
- Installed software
- User accounts and SIDs
- Active network connections

**Forensic Relevance**: Documents the state of the system at the time of examination, provides context for other evidence, and may reveal unauthorized software or network activity.

### Case 4: Full Forensic Examination

**Scenario**: Comprehensive examination of a suspect's computer.

**Steps**:
1. Launch ABYSS GUI with administrator privileges
2. Create new case with ID: ABYSS-20260426-004
3. Select all extraction vectors (Browser, Notepad, OS Memory)
4. Run extraction
5. Review all evidence in Evidence Vault
6. Generate intelligence reports

**Expected Results**:
- Complete browser history from all detected browsers
- Recovered unsaved Notepad tabs
- System profile and configuration
- Deleted URL recovery
- Zone Identifier leak detection
- User persona analysis

**Forensic Relevance**: Provides comprehensive view of system activity, user behavior, and potential evidence across multiple data sources.

---

## 7. Interpretation of Results

### Browser History Files

**Location**: `Extraction/Browsers/[Browser Name]/raw/`

**File**: `[Browser]_History_Source.csv`

**Columns**:
- Source: Browser name
- File Path: Path to original history database
- Content: URL or page content
- Title/Extra: Page title
- Visit Count: Number of visits
- Timestamp: Visit date/time
- File Created: Database creation time
- File Modified: Database modification time
- Evidence Hash: SHA-256 hash
- Flagged: Whether content triggered any alerts

**Forensic Interpretation**:
- Establish timeline of web activity
- Identify frequently visited domains
- Correlate with other evidence (e.g., file access times)
- Detect attempts to clear history (gaps in timestamps)

### Notepad Tab Recovery

**Location**: `Extraction/Notepad/TabState_Archive/`

**Files**: `[Tab ID].csv`

**Columns**:
- Source: Notepad Tab
- File Path: Path to original .bin file
- Content: Recovered text content
- Title/Extra: Tab title
- Timestamp: Last activity time
- Evidence Hash: SHA-256 hash

**Forensic Interpretation**:
- Recover information that was never saved
- Establish timeline of document creation/editing
- May reveal passwords, codes, or other sensitive data
- Correlate with other system activity

### System Profile

**Location**: `System/sysinfo.txt`

**Contents**:
- Hostname and user information
- OS architecture and install date
- Network configuration (IP, MAC, DNS)
- Security settings (Defender, UAC, Firewall)
- Storage topology
- Auto-run entries (persistence mechanisms)
- Scheduled tasks
- Installed browsers

**Forensic Interpretation**:
- Documents system state at time of examination
- Identifies potential persistence mechanisms
- Reveals network configuration and connections
- May indicate unauthorized software or access

### Chain of Custody

**Location**: `Chain_of_Custody/evidence_hashes.log`

**Format**: `[Timestamp] [SHA-256 Hash] | [Filename] ([Description])`

**Forensic Interpretation**:
- Proves integrity of extracted evidence
- Allows verification that files have not been modified
- Required for admissibility in legal proceedings
- Each hash can be independently verified

### Digital Signature

**Location**: `signature.txt` and `Case-Description.txt`

**Purpose**: Cryptographic verification of case metadata

**Forensic Interpretation**:
- Prevents unauthorized modification of case information
- Provides verification that case was created by specific investigator
- Part of chain of custody documentation

### Deleted URL Recovery

**Location**: `Extraction/Browsers/[Browser Name]/recovered/`

**File**: `[Browser]_Deleted_History.txt` or `No_Recovery.txt`

**Forensic Interpretation**:
- Reveals URLs that were deleted from browser history
- May indicate attempts to hide activity
- Provides additional evidence of web activity
- Correlates with other timeline evidence

### Zone Identifier Leaks

**Location**: `Extraction/DNSRecords/Incognito_DNS_Leaks.csv`

**Columns**: File path, Zone Identifier data

**Forensic Interpretation**:
- Identifies files downloaded from the internet
- Proves physical download origin
- May reveal downloaded content even if files were deleted
- Correlates with browser history gaps

### User Persona Report

**Location**: `Hits/Intelligence/User_Persona_Report.txt`

**Contents**: Behavioral analysis based on extracted data

**Forensic Interpretation**:
- Provides insight into user behavior patterns
- Identifies technical proficiency level
- May reveal interests or intent
- Supports investigative theories

---

## 8. Work Division

### Module Development Contributions

The ABYSS forensic suite was developed through collaborative effort with the following technical contributions:

#### Browser Forensics Module
**File**: `modules/browser_parser.py`
- Implemented SQLite database parsing for multiple browser types
- Developed heuristic scanning for portable browser installations
- Created timestamp conversion for different browser formats
- Implemented file hash verification for integrity

#### Notepad Recovery Module
**File**: `modules/notepad_parser.py`
- Developed binary parsing for Windows 11 Notepad .bin files
- Implemented timestamp extraction from volatile memory
- Created text extraction algorithms for binary data
- Handled encoding issues for international characters

#### System Profiling Module
**File**: `modules/system_profiler.py`
- Implemented Windows system information collection
- Developed network configuration detection
- Created user account enumeration
- Implemented hardware profiling

#### Report Generation Module
**File**: `modules/report_generator.py`
- Designed hierarchical report structure
- Implemented chain of custody logging
- Created hash verification system
- Developed digital signature implementation

#### Intelligence Engine Module
**File**: `modules/intelligence_engine.py`
- Implemented user persona analysis algorithms
- Created correlation logic for multiple data sources
- Developed behavioral pattern recognition
- Implemented report generation for intelligence summaries

#### Lazarus Module (Deleted Data Recovery)
**File**: `modules/lazarus_module.py`
- Implemented SQLite free-list carving
- Developed URL pattern matching in binary data
- Created Zone Identifier detection logic
- Implemented deleted data recovery algorithms

#### GUI Development
**File**: `main.py`
- Designed and implemented graphical user interface
- Created Evidence Vault file browser
- Implemented real-time log display
- Developed wizard-style case initialization
- Created hex preview functionality
- Implemented digital signature verification UI

#### CLI Development
**File**: `abyss.py`
- Designed command-line interface
- Implemented ASCII art display
- Created interactive input system
- Developed color-coded log output
- Implemented automated workflow

#### Utility Functions
**File**: `modules/utils.py`
- Implemented hash calculation functions
- Created timestamp conversion utilities
- Developed file metadata extraction
- Implemented directory management functions

#### Integration and Testing
- Integrated all modules into cohesive system
- Implemented error handling and logging
- Created cross-module data flow
- Developed performance optimizations
- Implemented UTF-8 encoding fixes for Windows

### Documentation
- Created comprehensive user guide
- Developed installation instructions
- Documented forensic interpretation guidelines
- Created troubleshooting guide

---

## Appendix

### Common File Extensions

- `.csv`: Comma-separated values (data tables)
- `.txt`: Plain text files
- `.bin`: Binary data files
- `.json`: JavaScript Object Notation (structured data)
- `.log`: Log files (text)
- `.png`: Image files (visualizations)

### Error Codes

- **Permission Denied**: Run as administrator
- **Database Locked**: Close browser instances or use VSS recovery
- **File Not Found**: Verify file paths and locations
- **Hash Mismatch**: Evidence may have been modified
- **Signature Failed**: Incorrect digital signature provided

### Support

For technical issues or questions:
1. Check the troubleshooting section in README.md
2. Verify all dependencies are installed
3. Ensure administrator privileges
4. Check Python version compatibility

---

**Document Version**: 2.0  
**Last Updated**: April 2026  
**Tool Version**: ABYSS v2.0
