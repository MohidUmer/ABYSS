import winreg
import logging
import pandas as pd

def parse_registry_artifacts():
    """Extracts forensic evidence from the Windows Registry."""
    artifacts = []
    
    # 1. TypedURLs (Internet Explorer / Edge File Explorer)
    try:
        typed_urls_key = r"Software\Microsoft\Internet Explorer\TypedURLs"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, typed_urls_key) as key:
            try:
                i = 0
                while True:
                    name, value, type_ = winreg.EnumValue(key, i)
                    artifacts.append({
                        "Source": "Registry_TypedURLs",
                        "Key Name": name,
                        "Data": value,
                        "Type": "URL"
                    })
                    i += 1
            except OSError:
                pass # End of values
    except Exception as e:
        logging.warning(f"[Registry] TypedURLs not found or inaccessible: {e}")

    # 2. WordWheelQuery (File Explorer Searches)
    try:
        wordwheel_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, wordwheel_key) as key:
            try:
                i = 0
                while True:
                    name, value, type_ = winreg.EnumValue(key, i)
                    # WordWheelQuery stores searches as REG_BINARY (UTF-16LE)
                    if type_ == winreg.REG_BINARY:
                        try:
                            decoded = value.decode('utf-16-le', errors='ignore').rstrip('\x00')
                            artifacts.append({
                                "Source": "Registry_WordWheelQuery",
                                "Key Name": name,
                                "Data": decoded,
                                "Type": "Search Query"
                            })
                        except:
                            pass
                    i += 1
            except OSError:
                pass
    except Exception as e:
        logging.warning(f"[Registry] WordWheelQuery not found or inaccessible: {e}")

    return artifacts
