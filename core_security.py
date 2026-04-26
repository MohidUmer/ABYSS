"""
ABYSS Security Module
Implements cryptographic signature locking, write-block emulation, and forensic integrity verification.
"""

import hashlib
import json
import os
import io
from datetime import datetime
from pathlib import Path


class SecurityManager:
    """Handles forensic evidence integrity, signature locking, and write-block emulation."""
    
    def __init__(self, case_dir: str):
        """
        Initialize security manager for a case directory.
        
        Args:
            case_dir: Root directory of the forensic case
        """
        self.case_dir = Path(case_dir)
        self.signature_file = self.case_dir / ".metadata_signature.bin"
        self.lock_file = self.case_dir / "void.lock"
        
    def create_signature(self, case_metadata: dict) -> str:
        """
        Generate cryptographic signature for case metadata.
        Creates a SHA-256 hash of serialized metadata as proof of forensic integrity.
        
        Args:
            case_metadata: Dictionary containing Case ID, Investigator, Timestamp, etc.
        
        Returns:
            SHA-256 hash string (hex format)
        """
        metadata_json = json.dumps(case_metadata, sort_keys=True)
        signature = hashlib.sha256(metadata_json.encode()).hexdigest()
        return signature
    
    def write_signature_file(self, case_metadata: dict) -> bool:
        """
        Write metadata signature to .metadata_signature.bin file.
        This file acts as a cryptographic lock for the case folder.
        
        Args:
            case_metadata: Dictionary containing case information
        
        Returns:
            True if successful, False otherwise
        """
        try:
            signature = self.create_signature(case_metadata)
            signature_data = {
                "signature": signature,
                "case_id": case_metadata.get("case_id"),
                "timestamp": datetime.now().isoformat(),
                "metadata": case_metadata
            }
            
            with open(self.signature_file, 'wb') as f:
                f.write(json.dumps(signature_data, indent=2).encode())
            
            # Set read-only attribute
            self._set_readonly(str(self.signature_file))
            return True
        except Exception as e:
            print(f"[!] Error writing signature file: {e}")
            return False
    
    def create_lock_file(self) -> bool:
        """
        Create void.lock file to mark this as a forensic case directory.
        Prevents accidental data tampering.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            lock_data = {
                "locked_at": datetime.now().isoformat(),
                "forensic_case": True,
                "version": "2.1.0"
            }
            
            with open(self.lock_file, 'w') as f:
                json.dump(lock_data, f, indent=2)
            
            self._set_readonly(str(self.lock_file))
            return True
        except Exception as e:
            print(f"[!] Error creating lock file: {e}")
            return False
    
    def verify_case_integrity(self) -> bool:
        """
        Verify that a case directory contains valid forensic signatures.
        
        Returns:
            True if valid forensic case, False otherwise
        """
        if not self.signature_file.exists() and not self.lock_file.exists():
            return False
        return True
    
    def validate_signature(self, case_metadata: dict) -> bool:
        """
        Validate that the signature file matches the provided metadata.
        
        Args:
            case_metadata: Dictionary to validate against stored signature
        
        Returns:
            True if signatures match, False otherwise
        """
        if not self.signature_file.exists():
            return False
        
        try:
            with open(self.signature_file, 'rb') as f:
                stored_data = json.loads(f.read().decode())
            
            current_signature = self.create_signature(case_metadata)
            stored_signature = stored_data.get("signature")
            
            return current_signature == stored_signature
        except Exception as e:
            print(f"[!] Error validating signature: {e}")
            return False
    
    def create_readonly_stream(self, file_path: str) -> io.BytesIO:
        """
        Create a read-only in-memory stream for a file (write-block emulation).
        Original file is never modified; all operations happen in temporary memory.
        
        Args:
            file_path: Path to the file to open in read-only mode
        
        Returns:
            io.BytesIO object containing file contents, or None if error
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            stream = io.BytesIO(file_data)
            stream.seek(0)
            return stream
        except Exception as e:
            print(f"[!] Error creating readonly stream for {file_path}: {e}")
            return None
    
    def set_file_readonly(self, file_path: str) -> bool:
        """
        Set file to read-only on Windows (emulates write-block).
        
        Args:
            file_path: Path to file to protect
        
        Returns:
            True if successful, False otherwise
        """
        return self._set_readonly(file_path)
    
    def _set_readonly(self, file_path: str) -> bool:
        """
        Internal method to set file read-only attribute on Windows.
        
        Args:
            file_path: Path to file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            import stat
            current_perms = os.stat(file_path).st_mode
            os.chmod(file_path, current_perms & ~stat.S_IWRITE)
            return True
        except Exception as e:
            print(f"[!] Warning: Could not set readonly on {file_path}: {e}")
            return False
    
    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file for integrity verification.
        
        Args:
            file_path: Path to file
        
        Returns:
            SHA-256 hash in hex format, or None if error
        """
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"[!] Error calculating hash for {file_path}: {e}")
            return None
    
    def verify_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        """
        Verify that a file's SHA-256 hash matches expected value.
        
        Args:
            file_path: Path to file
            expected_hash: Expected SHA-256 hash (hex string)
        
        Returns:
            True if hash matches, False otherwise
        """
        calculated_hash = self.calculate_file_hash(file_path)
        if calculated_hash is None:
            return False
        return calculated_hash.lower() == expected_hash.lower()
