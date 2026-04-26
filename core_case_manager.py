"""
ABYSS Case Manager
Handles case lifecycle, metadata management, and case folder structure initialization.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from core_security import SecurityManager
from styles import (
    CASE_FOLDER_PREFIX, RAW_DATA_DIR, HITS_DIR,
    SYSINFO_FILENAME, METADATA_SIGNATURE_FILENAME
)


class CaseManager:
    """Manages forensic case creation, validation, and lifecycle."""
    
    def __init__(self, case_root: str):
        """
        Initialize case manager for a root directory.
        
        Args:
            case_root: Root directory where cases will be stored (e.g., "reports/")
        """
        self.case_root = Path(case_root)
        self.case_root.mkdir(parents=True, exist_ok=True)
        self.current_case = None
        self.security = None
    
    def create_case(self, case_id: str, investigator: str, signature_seed: str = "") -> Optional[str]:
        """
        Create a new forensic case with directory structure and metadata.
        
        Args:
            case_id: Unique identifier for the case
            investigator: Name of the investigator
            signature_seed: Optional seed for cryptographic signature
        
        Returns:
            Full path to case directory if successful, None otherwise
        """
        try:
            # Create case directory
            case_dir_name = f"{CASE_FOLDER_PREFIX}{case_id}"
            case_path = self.case_root / case_dir_name
            case_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            raw_data_path = case_path / RAW_DATA_DIR
            hits_path = case_path / HITS_DIR
            raw_data_path.mkdir(exist_ok=True)
            hits_path.mkdir(exist_ok=True)
            
            # Generate metadata
            metadata = {
                "case_id": case_id,
                "investigator": investigator,
                "created_at": datetime.now().isoformat(),
                "version": "2.1.0",
                "signature_seed": signature_seed,
                "status": "active"
            }
            
            # Write metadata file
            metadata_file = case_path / "case_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Initialize security manager and create signatures
            self.security = SecurityManager(str(case_path))
            self.security.write_signature_file(metadata)
            self.security.create_lock_file()
            
            # Create sysinfo stub
            sysinfo_path = case_path / SYSINFO_FILENAME
            with open(sysinfo_path, 'w') as f:
                f.write(f"[CASE METADATA]\n")
                f.write(f"Case ID: {case_id}\n")
                f.write(f"Investigator: {investigator}\n")
                f.write(f"Created: {metadata['created_at']}\n")
                f.write(f"Version: 2.1.0\n")
            
            # Set sysinfo to read-only
            self.security.set_file_readonly(str(sysinfo_path))
            
            self.current_case = case_path
            print(f"[+] Case created successfully: {case_path}")
            return str(case_path)
            
        except Exception as e:
            print(f"[!] Error creating case: {e}")
            return None
    
    def open_case(self, case_path: str) -> bool:
        """
        Open an existing case and validate its forensic integrity.
        
        Args:
            case_path: Path to the case directory
        
        Returns:
            True if case is valid and opened, False otherwise
        """
        try:
            case_path_obj = Path(case_path)
            
            if not case_path_obj.exists():
                print(f"[!] CRITICAL: CASE DIRECTORY NOT FOUND. ACCESS DENIED.")
                return False
            
            # Initialize security manager
            self.security = SecurityManager(case_path)
            
            # Verify case integrity
            if not self.security.verify_case_integrity():
                print(f"[!] CRITICAL: NON-FORENSIC DIRECTORY DETECTED. ACCESS DENIED.")
                return False
            
            # Read and validate metadata
            metadata_file = case_path_obj / "case_metadata.json"
            if not metadata_file.exists():
                print(f"[!] CRITICAL: METADATA NOT FOUND. ACCESS DENIED.")
                return False
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Validate signature
            if not self.security.validate_signature(metadata):
                print(f"[!] WARNING: Signature validation failed. Case may be tampered.")
            
            self.current_case = case_path_obj
            print(f"[+] Case opened successfully: {case_path}")
            return True
            
        except Exception as e:
            print(f"[!] Error opening case: {e}")
            return False
    
    def get_case_metadata(self, case_path: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieve metadata for a case.
        
        Args:
            case_path: Path to case (uses current_case if not provided)
        
        Returns:
            Dictionary of metadata, or None if error
        """
        try:
            path = Path(case_path) if case_path else self.current_case
            if not path:
                return None
            
            metadata_file = path / "case_metadata.json"
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Error reading metadata: {e}")
            return None
    
    def list_cases(self) -> list:
        """
        List all cases in the case root directory.
        
        Returns:
            List of case directory names
        """
        try:
            cases = [d.name for d in self.case_root.iterdir() 
                    if d.is_dir() and d.name.startswith(CASE_FOLDER_PREFIX)]
            return sorted(cases)
        except Exception as e:
            print(f"[!] Error listing cases: {e}")
            return []
    
    def get_raw_data_path(self, case_path: Optional[str] = None) -> Optional[Path]:
        """Get path to Raw_Data directory for a case."""
        path = Path(case_path) if case_path else self.current_case
        if not path:
            return None
        return path / RAW_DATA_DIR
    
    def get_hits_path(self, case_path: Optional[str] = None) -> Optional[Path]:
        """Get path to Hits directory for a case."""
        path = Path(case_path) if case_path else self.current_case
        if not path:
            return None
        return path / HITS_DIR
    
    def add_raw_data_file(self, file_path: str, relative_name: str = "") -> bool:
        """
        Add a file to the Raw_Data directory (for extraction).
        
        Args:
            file_path: Full path to source file
            relative_name: Optional subdirectory path within Raw_Data
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.current_case:
                return False
            
            raw_data = self.get_raw_data_path()
            if not raw_data:
                return False
            
            # Create subdirectory if specified
            if relative_name:
                target_dir = raw_data / relative_name
                target_dir.mkdir(parents=True, exist_ok=True)
            else:
                target_dir = raw_data
            
            # Copy file
            import shutil
            dest = target_dir / Path(file_path).name
            shutil.copy2(file_path, dest)
            
            return True
        except Exception as e:
            print(f"[!] Error adding raw data file: {e}")
            return False
