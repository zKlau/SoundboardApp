import logging
from typing import List, Dict, Any

from .config import Config
from .audio_device_manager import AudioDeviceManager
from .sound_player import SoundPlayer
from .audio_router import AudioRouter
from .utils import check_ffmpeg_availability

try:
    from pydub import AudioSegment
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False
    AudioSegment = None

class AudioPlayer:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        if not FFMPEG_AVAILABLE:
            raise RuntimeError("pydub is required for audio processing")

        missing_ffmpeg = check_ffmpeg_availability()
        if missing_ffmpeg:
            raise RuntimeError(f"Missing FFmpeg: {', '.join(missing_ffmpeg)}")

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

    def is_playing(self):
        return self.sound_player.is_playing()

    def get_current_sound(self):
        return self.sound_player.get_current_sound()

    def get_input_devices(self):
        return self.device_manager.get_input_devices()

    def get_output_devices(self):
        return self.device_manager.get_output_devices()

    def set_input_device(self, device_index: int):
        self.device_manager.set_input_device(device_index)
        self.audio_router.restart_routing_if_needed()

    def set_output_device(self, device_index: int):
        self.device_manager.set_output_device(device_index)
        self.audio_router.restart_routing_if_needed()

    def start_audio_routing(self):
        self.audio_router.start_audio_routing()

    def __del__(self):
        self.device_manager._cleanup_audio()
