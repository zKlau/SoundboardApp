import logging
import subprocess
from typing import List, Dict, Any

from .config import Config
from .audio_device_manager import AudioDeviceManager
from .sound_player import SoundPlayer
from .audio_router import AudioRouter

try:
    from pydub import AudioSegment
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False
    AudioSegment = None

def check_ffmpeg_availability():
    components = ['ffmpeg', 'ffprobe']
    missing = []
    for component in components:
        try:
            subprocess.run([component, '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(component)
    return missing

class AudioPlayer:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        if not FFMPEG_AVAILABLE:
            raise RuntimeError("pydub is required for audio processing")

        missing_ffmpeg = check_ffmpeg_availability()
        if missing_ffmpeg:
            raise RuntimeError(f"Missing FFmpeg components: {', '.join(missing_ffmpeg)}")

        self.device_manager = AudioDeviceManager(config)
        self.device_manager.initialize_audio()

        self.sound_player = SoundPlayer(
            config,
            self.device_manager.get_sample_rate(),
            self.device_manager.get_channels()
        )

        self.audio_router = AudioRouter(self.device_manager, self.sound_player)

    def play_sound(self, sound_name: str):
        self.sound_player.play_sound(sound_name)

    def stop_playback(self):
        self.sound_player.stop_playback()

    def is_playing(self) -> bool:
        return self.sound_player.is_playing()

    def get_current_sound(self):
        return self.sound_player.get_current_sound()

    def set_device(self, device_name: str):
        self.device_manager.set_device(device_name)

    def get_input_devices(self) -> List[Dict[str, Any]]:
        return self.device_manager.get_input_devices()

    def get_output_devices(self) -> List[Dict[str, Any]]:
        return self.device_manager.get_output_devices()

    def set_input_device(self, device_index: int):
        self.device_manager.set_input_device(device_index)
        self.audio_router.restart_routing_if_needed()

    def set_output_device(self, device_index: int):
        self.device_manager.set_output_device(device_index)
        self.audio_router.restart_routing_if_needed()

    def start_audio_routing(self):
        self.audio_router.start_audio_routing()

    def stop_audio_routing(self):
        self.audio_router.stop_audio_routing()

    def restart_routing_if_needed(self):
        self.audio_router.restart_routing_if_needed()

    def __del__(self):
        self.device_manager._cleanup_audio()
