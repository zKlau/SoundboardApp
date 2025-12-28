import numpy as np
import threading
import time
import logging
from pathlib import Path
from typing import Optional

from .config import Config

try:
    from pydub import AudioSegment
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    AudioSegment = None


class SoundPlayer:
    def __init__(self, config: Config, sample_rate: int, channels: int):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self._sample_rate = sample_rate
        self._channels = channels

        self._is_playing = False
        self._current_sound = None
        self._current_sound_data = None
        self._current_sound_pos = 0
        self._playback_thread = None

    def play_sound(self, sound_name: str):
        sound_data = self.config.get_sound(sound_name)
        if not sound_data:
            self.logger.error(f"Sound not found: {sound_name}")
            return

        sound_path = sound_data.get("path")
        if not sound_path or not Path(sound_path).exists():
            self.logger.error(f"Sound file not found: {sound_path}")
            return

        volume = sound_data.get("volume", self.config.default_volume)

        self._playback_thread = threading.Thread(
            target=self._play_sound_thread,
            args=(sound_path, volume, sound_name),
            daemon=True
        )
        self._playback_thread.start()

    def _play_sound_thread(self, sound_path: str, volume: int, sound_name: str):
        try:
            self.logger.info(f"Playing sound: {sound_path} at volume {volume}%")

            audio = self._load_and_process_audio(sound_path, volume)

            audio_data = np.array(audio.get_array_of_samples())
            audio_data = audio_data.astype(np.int16)

            if len(audio_data) == 0:
                raise ValueError(f"No audio data found in file: {sound_path}")

            self._current_sound_data = audio_data
            self._current_sound_pos = 0
            self._current_sound = sound_name
            self._is_playing = True

            duration = len(audio_data) / self._sample_rate
            time.sleep(duration)

            self.logger.info(f"Sound playback completed: {sound_name}")

        except Exception as e:
            self.logger.error(f"Error during sound playback: {e}")
        finally:
            self._current_sound_data = None
            self._current_sound_pos = 0
            self._current_sound = None
            self._is_playing = False

    def _load_and_process_audio(self, sound_path: str, volume: int):
        try:
            audio = AudioSegment.from_file(sound_path)

            if len(audio) == 0:
                raise ValueError(f"Audio file appears to be empty: {sound_path}")

            original_channels = audio.channels
            original_rate = audio.frame_rate

            if audio.channels != self._channels:
                audio = audio.set_channels(self._channels)
            if audio.frame_rate != self._sample_rate:
                audio = audio.set_frame_rate(self._sample_rate)

            self.logger.debug(f"Loaded audio: {sound_path}, {original_channels}ch@{original_rate}Hz -> {audio.channels}ch@{audio.frame_rate}Hz")

            return audio

        except Exception as e:
            self.logger.error(f"Failed to load audio file {sound_path}: {e}")
            raise RuntimeError(f"Unable to load audio file: {e}")

    def stop_playback(self):
        if self._is_playing:
            self.logger.info("Stopping audio playback")
            self._cleanup_playback()

            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=1.0)

    def _cleanup_playback(self):
        self._current_sound_data = None
        self._current_sound_pos = 0
        self._is_playing = False
        self._current_sound = None

    def is_playing(self) -> bool:
        return self._is_playing

    def get_current_sound(self) -> Optional[str]:
        return self._current_sound

    def get_current_sound_data(self) -> Optional[np.ndarray]:
        return self._current_sound_data

    def get_current_sound_pos(self) -> int:
        return self._current_sound_pos

    @property
    def current_sound_data(self):
        return self._current_sound_data

    @property
    def current_sound_pos(self):
        return self._current_sound_pos

    @current_sound_pos.setter
    def current_sound_pos(self, value):
        self._current_sound_pos = value
