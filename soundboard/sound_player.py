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
        if self._is_playing:
            self.stop_playback()
            time.sleep(0.05)
        
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
            self.logger.info(f"Playing: {sound_path} @ {volume}%")

            audio = self._load_and_process_audio(sound_path, volume)
            audio_data = np.array(audio.get_array_of_samples(), dtype=np.int16)

            self._current_sound_data = audio_data
            self._current_sound_pos = 0
            self._current_sound = sound_name
            self._is_playing = True

            duration = len(audio_data) / self._sample_rate
            time.sleep(duration)

            self.logger.info(f"Completed: {sound_name}")

        except Exception as e:
            self.logger.error(f"Playback error: {e}")
        finally:
            self._cleanup_playback()

    def _load_and_process_audio(self, sound_path: str, volume: int):
        try:
            audio = AudioSegment.from_file(sound_path)

            if len(audio) == 0:
                raise ValueError(f"Audio file appears to be empty: {sound_path}")

            if audio.sample_width != 2:
                audio = audio.set_sample_width(2)
            
            if audio.frame_rate != self._sample_rate:
                audio = audio.set_frame_rate(self._sample_rate)
            
            if audio.channels != self._channels:
                audio = audio.set_channels(self._channels)
            
            volume_adjustment = (volume / 100.0) - 1.0
            if abs(volume_adjustment) > 0.01:
                audio = audio + (volume_adjustment * 20)

            self.logger.debug(f"Loaded: {sound_path} -> {audio.channels}ch@{audio.frame_rate}Hz")
            return audio

        except Exception as e:
            self.logger.error(f"Failed to load audio file {sound_path}: {e}")
            raise RuntimeError(f"Unable to load audio file: {e}")

    def stop_playback(self):
        if self._is_playing:
            self.logger.info("Stopping playback")
            self._cleanup_playback()
            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=1.0)

    def _cleanup_playback(self):
        self._current_sound_data = None
        self._current_sound_pos = 0
        self._current_sound = None
        self._is_playing = False

    def is_playing(self) -> bool:
        return self._is_playing

    def get_current_sound(self) -> Optional[str]:
        return self._current_sound

    def get_current_sound_data(self) -> Optional[np.ndarray]:
        return self._current_sound_data

    def get_current_sound_pos(self) -> int:
        return self._current_sound_pos

    def get_next_audio_chunk(self, chunk_size: int) -> Optional[np.ndarray]:
        if not self._is_playing or self._current_sound_data is None:
            return None
        
        if self._current_sound_pos >= len(self._current_sound_data):
            self._cleanup_playback()
            return None
        
        start_pos = self._current_sound_pos
        end_pos = min(start_pos + chunk_size, len(self._current_sound_data))
        
        sound_chunk = self._current_sound_data[start_pos:end_pos]
        self._current_sound_pos = end_pos
        
        if len(sound_chunk) < chunk_size:
            sound_chunk = np.pad(sound_chunk, (0, chunk_size - len(sound_chunk)), 'constant')
        
        return sound_chunk