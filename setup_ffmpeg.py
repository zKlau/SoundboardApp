#!/usr/bin/env python3

import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path

def download_ffmpeg():
    print("Setting up FFmpeg for Soundboard...")

    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = Path("ffmpeg_temp.zip")
    extract_path = Path("ffmpeg_temp")

    try:
        print("Downloading FFmpeg...")
        with urllib.request.urlopen(ffmpeg_url) as response:
            with open(zip_path, 'wb') as f:
                shutil.copyfileobj(response, f)

        print("Extracting FFmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        ffmpeg_dir = None
        for item in extract_path.iterdir():
            if item.is_dir() and 'ffmpeg' in item.name.lower():
                ffmpeg_dir = item
                break

        if not ffmpeg_dir:
            raise FileNotFoundError("Could not find FFmpeg directory in extracted files")

        bin_dir = ffmpeg_dir / "bin"
        if not bin_dir.exists():
            raise FileNotFoundError(f"bin directory not found in {ffmpeg_dir}")

        current_dir = Path.cwd()
        copied = []

        for exe in ['ffmpeg.exe', 'ffprobe.exe']:
            src = bin_dir / exe
            dst = current_dir / exe

            if src.exists():
                shutil.copy2(src, dst)
                copied.append(exe)
                print(f"Copied {exe} to {current_dir}")
            else:
                print(f"Warning: {exe} not found in {bin_dir}")

        if copied:
            print(f"\n[SUCCESS] FFmpeg setup complete! Copied: {', '.join(copied)}")
            print(f"Files are now available in: {current_dir}")
        else:
            print("\n[ERROR] No FFmpeg executables were found or copied.")

    except Exception as e:
        print(f"\n[ERROR] Error setting up FFmpeg: {e}")
        return False

    finally:
        try:
            if zip_path.exists():
                zip_path.unlink()
            if extract_path.exists():
                shutil.rmtree(extract_path)
        except Exception as e:
            print(f"Warning: Could not clean up temporary files: {e}")

    return True

def check_ffmpeg():
    """Check if FFmpeg is available."""
    import subprocess

    components = ['ffmpeg', 'ffprobe']
    available = []

    for component in components:
        try:
            result = subprocess.run([component, '-version'],
                                  capture_output=True,
                                  check=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            available.append(component)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    return available

def main():
    print("Soundboard FFmpeg Setup")
    print("=" * 30)

    available = check_ffmpeg()
    if available == ['ffmpeg', 'ffprobe']:
        print("[SUCCESS] FFmpeg is already properly installed!")
        return True

    print(f"FFmpeg components found: {available}")
    print("Missing components will be downloaded...")

    if download_ffmpeg():
        available_after = check_ffmpeg()
        if available_after == ['ffmpeg', 'ffprobe']:
            print("\n[SUCCESS] Setup successful! You can now run the soundboard application.")
            return True
        else:
            print(f"\n[WARNING] Setup completed but some components may be missing: {available_after}")
            return False
    else:
        print("\n[ERROR] Setup failed. Please install FFmpeg manually.")
        print("Download from: https://ffmpeg.org/download.html")
        return False

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)
