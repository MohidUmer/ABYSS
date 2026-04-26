import os
import subprocess
import logging

def get_mft_file_id(filepath):
    """Gets the MFT File ID using Windows fsutil."""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(['fsutil', 'file', 'queryfileid', filepath], capture_output=True, text=True, startupinfo=startupinfo)
        if result.returncode == 0:
            match = result.stdout.strip()
            if "File ID is" in match:
                return match.split("is")[1].strip()
    except Exception:
        pass
    return "N/A"

def generate_hex_dump(filepath, output_dir, max_bytes=1024):
    """
    Generates a WinHex style hex dump of the target file.
    Creates an MFT metadata snapshot text file.
    """
    filename = os.path.basename(filepath)
    dump_filename = f"{filename}_hex.txt"
    dump_path = os.path.join(output_dir, dump_filename)
    
    try:
        mft_id = get_mft_file_id(filepath)
        stat = os.stat(filepath)
        
        with open(dump_path, 'w') as out_f:
            # Write MFT Metadata Header
            out_f.write(f"=== ABYSS MFT METADATA & HEX PREVIEW ===\n")
            out_f.write(f"Target File : {filepath}\n")
            out_f.write(f"MFT File ID : {mft_id}\n")
            out_f.write(f"Inode       : {stat.st_ino}\n")
            out_f.write(f"Size        : {stat.st_size} bytes\n")
            out_f.write(f"Dev ID      : {stat.st_dev}\n")
            out_f.write(f"=========================================\n\n")
            
            with open(filepath, 'rb') as in_f:
                offset = 0
                while offset < max_bytes:
                    chunk = in_f.read(16)
                    if not chunk:
                        break
                        
                    # Format: 00000000  47 49 46 38 39 61 01 00  ...  ASCII
                    hex_str = ' '.join(f'{b:02X}' for b in chunk)
                    # Add extra space after 8th byte for readability
                    if len(chunk) > 8:
                        hex_part = hex_str[:23] + ' ' + hex_str[23:]
                    else:
                        hex_part = hex_str
                        
                    # Pad to 48 chars
                    hex_part = hex_part.ljust(48)
                    
                    # ASCII representation (printable only)
                    ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                    
                    out_f.write(f"{offset:08X}  {hex_part}  {ascii_str}\n")
                    offset += 16
                    
        return dump_path
    except Exception as e:
        logging.error(f"Failed to generate Hex Dump for {filename}: {e}")
        return None
