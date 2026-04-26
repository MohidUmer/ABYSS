"""
ABYSS Evidence Handler
Manages read-only file access, metadata extraction, and evidence viewing with write-block emulation.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Tuple
import json
from datetime import datetime
from core_security import SecurityManager
from styles import C_ACCENT, C_MUTED


class EvidenceHandler:
    """Handles read-only access to forensic evidence with write-block emulation."""
    
    def __init__(self, case_dir: str, security_manager: SecurityManager):
        """
        Initialize evidence handler for a case.
        
        Args:
            case_dir: Path to case directory
            security_manager: SecurityManager instance for the case
        """
        self.case_dir = Path(case_dir)
        self.security = security_manager
        self.raw_data_dir = self.case_dir / "Raw_Data"
        self.hits_dir = self.case_dir / "Hits"
    
    def list_raw_data_files(self, recursive: bool = True) -> list:
        """
        List all files in Raw_Data directory.
        
        Args:
            recursive: If True, recurse into subdirectories
        
        Returns:
            List of file paths relative to Raw_Data
        """
        try:
            if not self.raw_data_dir.exists():
                return []
            
            files = []
            if recursive:
                for file in self.raw_data_dir.rglob('*'):
                    if file.is_file():
                        files.append(str(file.relative_to(self.raw_data_dir)))
            else:
                for file in self.raw_data_dir.iterdir():
                    if file.is_file():
                        files.append(file.name)
            
            return sorted(files)
        except Exception as e:
            print(f"[!] Error listing raw data: {e}")
            return []
    
    def list_hits_files(self, recursive: bool = True) -> list:
        """
        List all files in Hits directory (forensic findings).
        
        Args:
            recursive: If True, recurse into subdirectories
        
        Returns:
            List of file paths relative to Hits
        """
        try:
            if not self.hits_dir.exists():
                return []
            
            files = []
            if recursive:
                for file in self.hits_dir.rglob('*'):
                    if file.is_file():
                        files.append(str(file.relative_to(self.hits_dir)))
            else:
                for file in self.hits_dir.iterdir():
                    if file.is_file():
                        files.append(file.name)
            
            return sorted(files)
        except Exception as e:
            print(f"[!] Error listing hits: {e}")
            return []
    
    def get_file_metadata(self, file_path: str, base_dir: str = "Raw_Data") -> Optional[Dict]:
        """
        Extract metadata for a file (hash, size, timestamps, etc.).
        
        Args:
            file_path: Relative path to file within case directory
            base_dir: Base directory ("Raw_Data" or "Hits")
        
        Returns:
            Dictionary of file metadata, or None if error
        """
        try:
            if base_dir == "Raw_Data":
                full_path = self.raw_data_dir / file_path
            elif base_dir == "Hits":
                full_path = self.hits_dir / file_path
            else:
                return None
            
            if not full_path.exists():
                return None
            
            stat_info = full_path.stat()
            
            # Calculate SHA-256 hash
            file_hash = self.security.calculate_file_hash(str(full_path))
            
            # Get modification time in ISO format
            mod_time = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
            creation_time = datetime.fromtimestamp(stat_info.st_ctime).isoformat()
            
            # Read-only status
            is_readonly = not os.access(full_path, os.W_OK)
            
            metadata = {
                "filename": full_path.name,
                "relative_path": file_path,
                "full_path": str(full_path),
                "size_bytes": stat_info.st_size,
                "size_readable": self._format_size(stat_info.st_size),
                "sha256": file_hash,
                "modified": mod_time,
                "created": creation_time,
                "readonly": is_readonly,
                "base_dir": base_dir
            }
            
            return metadata
        except Exception as e:
            print(f"[!] Error extracting metadata: {e}")
            return None
    
    def quick_view_file(self, file_path: str, base_dir: str = "Raw_Data", 
                       max_bytes: int = 10000) -> Optional[str]:
        """
        Quick view of file contents (read-only, in-memory stream).
        Implements write-block emulation by never touching the original file.
        
        Args:
            file_path: Relative path to file within case directory
            base_dir: Base directory ("Raw_Data" or "Hits")
            max_bytes: Maximum bytes to read (prevents huge file issues)
        
        Returns:
            File contents as string, or None if error
        """
        try:
            if base_dir == "Raw_Data":
                full_path = self.raw_data_dir / file_path
            elif base_dir == "Hits":
                full_path = self.hits_dir / file_path
            else:
                return None
            
            if not full_path.exists():
                return None
            
            # Create read-only in-memory stream
            stream = self.security.create_readonly_stream(str(full_path))
            if not stream:
                return None
            
            # Read up to max_bytes
            data = stream.read(max_bytes)
            stream.close()
            
            # Try to decode as text; fall back to hex if binary
            try:
                return data.decode('utf-8', errors='replace')
            except:
                return data.hex()
        except Exception as e:
            print(f"[!] Error quick viewing file: {e}")
            return None
    
    def hex_dump_file(self, file_path: str, base_dir: str = "Raw_Data",
                     max_bytes: int = 4096) -> Optional[str]:
        """
        Generate hex dump of file contents.
        
        Args:
            file_path: Relative path to file
            base_dir: Base directory
            max_bytes: Maximum bytes to dump
        
        Returns:
            Formatted hex dump string, or None if error
        """
        try:
            if base_dir == "Raw_Data":
                full_path = self.raw_data_dir / file_path
            elif base_dir == "Hits":
                full_path = self.hits_dir / file_path
            else:
                return None
            
            if not full_path.exists():
                return None
            
            stream = self.security.create_readonly_stream(str(full_path))
            if not stream:
                return None
            
            data = stream.read(max_bytes)
            stream.close()
            
            # Generate hex dump with ASCII sidebar
            hex_dump = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_part = ' '.join(f'{b:02x}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                hex_dump.append(f"{i:08x}  {hex_part:<48}  {ascii_part}")
            
            return '\n'.join(hex_dump)
        except Exception as e:
            print(f"[!] Error generating hex dump: {e}")
            return None
    
    def export_file_to_explorer(self, file_path: str, base_dir: str = "Raw_Data") -> bool:
        """
        Open file location in OS explorer (non-destructive).
        
        Args:
            file_path: Relative path to file
            base_dir: Base directory
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if base_dir == "Raw_Data":
                full_path = self.raw_data_dir / file_path
            elif base_dir == "Hits":
                full_path = self.hits_dir / file_path
            else:
                return False
            
            if not full_path.exists():
                return False
            
            # Open in Explorer
            import platform
            if platform.system() == 'Windows':
                import subprocess
                subprocess.Popen(f'explorer /select,"{full_path}"')
            elif platform.system() == 'Darwin':  # macOS
                import subprocess
                subprocess.Popen(['open', '-R', str(full_path)])
            else:  # Linux
                import subprocess
                subprocess.Popen(['xdg-open', str(full_path.parent)])
            
            return True
        except Exception as e:
            print(f"[!] Error opening in explorer: {e}")
            return False
    
    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def build_tree_structure(self) -> Dict:
        """
        Build hierarchical tree structure of case contents.
        
        Returns:
            Dictionary representing folder tree with metadata
        """
        tree = {
            "case_root": str(self.case_dir),
            "children": []
        }
        
        # Raw_Data branch
        if self.raw_data_dir.exists():
            raw_branch = {
                "name": "📂 Raw_Data",
                "path": str(self.raw_data_dir),
                "type": "folder",
                "children": self._build_tree_recursive(self.raw_data_dir)
            }
            tree["children"].append(raw_branch)
        
        # Hits branch
        if self.hits_dir.exists():
            hits_branch = {
                "name": "📂 Hits",
                "path": str(self.hits_dir),
                "type": "folder",
                "children": self._build_tree_recursive(self.hits_dir)
            }
            tree["children"].append(hits_branch)
        
        return tree
    
    def _build_tree_recursive(self, directory: Path, max_depth: int = 5, current_depth: int = 0) -> list:
        """Recursively build tree structure."""
        if current_depth >= max_depth:
            return []
        
        items = []
        try:
            for item in sorted(directory.iterdir()):
                if item.is_dir():
                    items.append({
                        "name": f"📁 {item.name}",
                        "path": str(item),
                        "type": "folder",
                        "children": self._build_tree_recursive(item, max_depth, current_depth + 1)
                    })
                else:
                    items.append({
                        "name": f"📄 {item.name}",
                        "path": str(item),
                        "type": "file",
                        "size": item.stat().st_size
                    })
        except:
            pass
        
        return items
