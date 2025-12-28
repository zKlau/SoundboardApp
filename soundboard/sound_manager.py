import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

try:
    from pydub import AudioSegment
    from pydub.utils import mediainfo
    PYDUB_AVAILABLE = True
except ImportError as e:
    PYDUB_AVAILABLE = False
    AudioSegment = None
    mediainfo = None

def check_ffmpeg_availability():
    import subprocess
    import os

    components = ['ffmpeg', 'ffprobe']
    missing = []

    for component in components:
        try:
            subprocess.run([component, '-version'],
                         capture_output=True,
                         check=True,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(component)

    return missing

from .config import Config

class SoundManager:
    SUPPORTED_FORMATS = {'.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a'}

    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        if not PYDUB_AVAILABLE:
            raise ImportError(
                "pydub is required for audio processing. Please install it with:\n"
                "pip install pydub\n"
                "Also ensure FFmpeg is installed and available in PATH."
            )

        missing_ffmpeg = check_ffmpeg_availability()
        if missing_ffmpeg:
            raise RuntimeError(
                f"FFmpeg components not found: {', '.join(missing_ffmpeg)}\n\n"
                "Please install FFmpeg:\n"
                "1. Download from: https://ffmpeg.org/download.html\n"
                "2. Extract the zip file\n"
                "3. Add the 'bin' folder to your system PATH, or\n"
                "4. Place ffmpeg.exe and ffprobe.exe in the application directory\n\n"
                "Required components: ffmpeg.exe, ffprobe.exe"
            )

        self.config.sounds_dir.mkdir(exist_ok=True)

    def _copy_file_with_retry(self, src_path: Path, dest_path: Path, max_retries: int = 3) -> bool:
        import time
        import os

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(max_retries):
            try:
                with open(src_path, 'rb') as f:
                    f.read(1)
                    f.seek(0)

                shutil.copy2(src_path, dest_path)

                if dest_path.exists() and dest_path.stat().st_size > 0:
                    self.logger.info(f"Successfully copied {src_path} to {dest_path}")
                    return True

            except (IOError, OSError) as e:
                self.logger.warning(f"Copy attempt {attempt + 1} failed: {e}")

                if attempt == max_retries - 1:
                    try:
                        self.logger.info("Trying manual binary copy...")
                        with open(src_path, 'rb') as src, open(dest_path, 'wb') as dst:
                            while True:
                                chunk = src.read(8192)
                                if not chunk:
                                    break
                                dst.write(chunk)

                        if dest_path.exists() and dest_path.stat().st_size > 0:
                            self.logger.info("Manual copy succeeded")
                            return True

                    except Exception as manual_e:
                        self.logger.error(f"Manual copy also failed: {manual_e}")

                if attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)
                    self.logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

        return False

    def _is_file_accessible(self, file_path: Path) -> bool:
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
            return True
        except (IOError, OSError):
            return False

    def add_sound(self, name: str, file_path: str, volume: int = None) -> bool:
        if not name or not name.strip():
            raise ValueError("Sound name cannot be empty")

        if name in self.config.get_all_sounds():
            raise ValueError(f"Sound '{name}' already exists")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Sound file not found: {file_path}")

        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported audio format: {file_path.suffix}")

        if not self._is_file_accessible(file_path):
            raise RuntimeError(
                f"Cannot access sound file: {file_path}\n"
                "The file may be locked by another application. "
                "Try closing any programs using this file, or copy it to a different location first."
            )

        try:
            audio = AudioSegment.from_file(str(file_path))
            if len(audio) == 0:
                raise RuntimeError("Audio file appears to be empty")

        except Exception as e:
            self.logger.error(f"Failed to validate audio file {file_path}: {e}")

            try:
                import os
                file_size = os.path.getsize(file_path)
            except Exception:
                pass

            raise RuntimeError(f"Cannot load audio file: {e}")

        dest_path = self.config.sounds_dir / f"{name}{file_path.suffix}"

        if not self._copy_file_with_retry(file_path, dest_path):
            raise RuntimeError(
                f"Failed to copy sound file: The file may be in use by another application.\n"
                f"Try closing any programs that might be using the file, or copy the file to a different location first.\n"
                f"Source: {file_path}\n"
                f"Destination: {dest_path}"
            )

        if volume is None:
            volume = self.config.default_volume

        self.config.add_sound(name, str(dest_path), volume)
        self.config.save()

        self.logger.info(f"Added sound: {name} from {file_path}")
        return True

    def remove_sound(self, name: str) -> bool:
        sound_data = self.config.get_sound(name)
        if not sound_data:
            return False

        try:
            sound_path = Path(sound_data["path"])
            if sound_path.exists():
                sound_path.unlink()
        except OSError as e:
            self.logger.warning(f"Failed to remove sound file: {e}")

        self.config.remove_sound(name)
        self.config.save()

        self.logger.info(f"Removed sound: {name}")
        return True

    def get_sound_path(self, name: str) -> Optional[str]:
        sound_data = self.config.get_sound(name)
        return sound_data.get("path") if sound_data else None

    def get_sound_volume(self, name: str) -> int:
        sound_data = self.config.get_sound(name)
        return sound_data.get("volume", self.config.default_volume) if sound_data else self.config.default_volume

    def set_volume(self, name: str, volume: int):
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100")

        sound_data = self.config.get_sound(name)
        if sound_data:
            sound_data["volume"] = volume
            self.config.save()
            self.logger.info(f"Set volume for {name}: {volume}%")

    def get_all_sounds(self) -> Dict[str, Dict[str, Any]]:
        
        return self.config.get_all_sounds()

    def get_sound_info(self, name: str) -> Optional[Dict[str, Any]]:
        sound_data = self.config.get_sound(name)
        if not sound_data:
            return None

        file_path = Path(sound_data["path"])
        if not file_path.exists():
            return None

        try:
            info = mediainfo(str(file_path))
            audio = AudioSegment.from_file(str(file_path))

            return {
                "name": name,
                "path": str(file_path),
                "volume": sound_data.get("volume", self.config.default_volume),
                "duration": len(audio) / 1000.0,
                "format": file_path.suffix[1:].upper(),
                "channels": audio.channels,
                "sample_rate": audio.frame_rate,
                "bitrate": info.get("bit_rate", "Unknown"),
                "size_bytes": file_path.stat().st_size
            }
        except Exception as e:
            self.logger.error(f"Failed to get sound info for {name}: {e}")
            return None

    def validate_sound_file(self, file_path: str) -> Dict[str, Any]:
        file_path = Path(file_path)

        result = {
            "valid": False,
            "error": None,
            "duration": 0,
            "format": None,
            "channels": 0,
            "sample_rate": 0
        }

        try:
            if not file_path.exists():
                result["error"] = "File does not exist"
                return result

            if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                result["error"] = f"Unsupported format: {file_path.suffix}"
                return result

            audio = AudioSegment.from_file(str(file_path))

            if len(audio) == 0:
                result["error"] = "Audio file is empty"
                return result

            result["valid"] = True
            result["duration"] = len(audio) / 1000.0
            result["format"] = file_path.suffix[1:].upper()
            result["channels"] = audio.channels
            result["sample_rate"] = audio.frame_rate

        except Exception as e:
            result["error"] = str(e)

        return result

    def cleanup_orphaned_files(self):
        configured_sounds = set()
        for sound_data in self.config.get_all_sounds().values():
            configured_sounds.add(Path(sound_data["path"]).name)

        for sound_file in self.config.sounds_dir.glob("*"):
            if sound_file.is_file() and sound_file.name not in configured_sounds:
                try:
                    sound_file.unlink()
                    self.logger.info(f"Removed orphaned sound file: {sound_file}")
                except OSError as e:
                    self.logger.warning(f"Failed to remove orphaned file {sound_file}: {e}")
