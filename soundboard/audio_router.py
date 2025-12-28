import pyaudio
import numpy as np
import threading
import logging
from typing import Optional

from .sound_player import SoundPlayer


class AudioRouter:
    def __init__(self, device_manager, sound_player: SoundPlayer):
        self.device_manager = device_manager
        self.sound_player = sound_player
        self.logger = logging.getLogger(__name__)

        self._input_stream: Optional[pyaudio.Stream] = None
        self._output_stream: Optional[pyaudio.Stream] = None
        self._is_routing = False
        self._routing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_audio_routing(self):
        if self._is_routing:
            return

        self._is_routing = True
        self._routing_thread = threading.Thread(target=self._audio_routing_loop, daemon=True)
        self._routing_thread.start()
        self.logger.info("Audio routing started")

    def stop_audio_routing(self):
        if not self._is_routing:
            return

        self._is_routing = False
        if self._routing_thread and self._routing_thread.is_alive():
            self._routing_thread.join(timeout=1.0)
        self._cleanup_routing_streams()
        self.logger.info("Audio routing stopped")

    def restart_routing_if_needed(self):
        if self._is_routing:
            self.stop_audio_routing()
            self.start_audio_routing()

    def _audio_routing_loop(self):
        try:
            pyaudio_instance = self.device_manager.get_pyaudio_instance()
            if not pyaudio_instance:
                raise RuntimeError("PyAudio not initialized")

            self._input_stream = pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.device_manager.get_channels(),
                rate=self.device_manager.get_sample_rate(),
                input=True,
                input_device_index=self.device_manager.get_input_device_index(),
                frames_per_buffer=1024
            )

            self._output_stream = pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.device_manager.get_channels(),
                rate=self.device_manager.get_sample_rate(),
                output=True,
                output_device_index=self.device_manager.get_output_device_index(),
                frames_per_buffer=1024
            )

            self.logger.info("Audio routing streams opened")

            while self._is_routing and not self._stop_event.is_set():
                try:
                    input_data = self._input_stream.read(1024, exception_on_overflow=False)

                    output_data = self._mix_audio_with_sounds(input_data)

                    self._output_stream.write(output_data)

                except Exception as e:
                    self.logger.warning(f"Audio routing error: {e}")
                    break

        except Exception as e:
            self.logger.error(f"Failed to start audio routing: {e}")
        finally:
            self._cleanup_routing_streams()

    def _mix_audio_with_sounds(self, input_data):
        try:
            if not self.sound_player.is_playing() or self.sound_player.get_current_sound_data() is None:
                return input_data

            input_array = np.frombuffer(input_data, dtype=np.int16)
            chunk_size = len(input_array)

            if self.sound_player.current_sound_data is None:
                return input_data

            sound_pos = self.sound_player.current_sound_pos
            if sound_pos >= len(self.sound_player.current_sound_data):
                self.sound_player._is_playing = False
                self.sound_player._current_sound_data = None
                self.sound_player._current_sound_pos = 0
                self.sound_player._current_sound = None
                return input_data

            start_pos = sound_pos
            end_pos = min(start_pos + chunk_size, len(self.sound_player.current_sound_data))

            sound_chunk = self.sound_player.current_sound_data[start_pos:end_pos]
            self.sound_player.current_sound_pos = end_pos

            if len(sound_chunk) < chunk_size:
                sound_chunk = np.pad(sound_chunk, (0, chunk_size - len(sound_chunk)), 'constant')

            volume = self.device_manager.config.get_sound(self.sound_player.get_current_sound()).get("volume", self.device_manager.config.default_volume) / 100.0
            input_gain = 0.6
            soundboard_gain = 3.0 * volume

            mixed = (input_array.astype(np.int32) * input_gain) + (sound_chunk.astype(np.int32) * soundboard_gain)
            mixed = np.clip(mixed, -32768, 32767).astype(np.int16)

            return mixed.tobytes()

        except Exception as e:
            self.logger.error(f"Error in audio mixing: {e}")
            return input_data

    def _cleanup_routing_streams(self):
        if self._input_stream:
            try:
                self._input_stream.stop_stream()
                self._input_stream.close()
            except Exception as e:
                self.logger.warning(f"Error closing input stream: {e}")
            self._input_stream = None

        if self._output_stream:
            try:
                self._output_stream.stop_stream()
                self._output_stream.close()
            except Exception as e:
                self.logger.warning(f"Error closing output stream: {e}")
            self._output_stream = None

    def is_routing(self) -> bool:
        return self._is_routing
