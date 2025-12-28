import pyaudio
import numpy as np
import threading
import time
import logging
import subprocess
import os
from typing import Optional, Callable
from pathlib import Path

from .config import Config

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    FFMPEG_AVAILABLE = True
except ImportError as e:
    logging.warning(f"pydub not available: {e}")
    FFMPEG_AVAILABLE = False
    AudioSegment = None
    normalize = None

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

class AudioPlayer:

    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self._pyaudio = None
        self._input_stream = None
        self._output_stream = None
        self._is_routing = False
        self._is_playing = False
        self._current_sound = None
        self._current_sound_data = None
        self._current_sound_pos = 0
        self._routing_thread = None
        self._playback_thread = None
        self._stop_event = threading.Event()

        self._input_device_index = None
        self._output_device_index = None
        self._sample_rate = config.sample_rate
        self._channels = config.channels

        if not FFMPEG_AVAILABLE:
            raise RuntimeError(
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

        self._initialize_audio()

    def _initialize_audio(self):
        try:
            self._pyaudio = pyaudio.PyAudio()

            self._input_device_index = self._pyaudio.get_default_input_device_info()['index']
            self._output_device_index = self._find_vb_cable_device()
            if self._output_device_index is None:
                self.logger.warning("VB-Cable device not found. Audio will play through default device.")
                self._output_device_index = self._pyaudio.get_default_output_device_info()['index']

            self.logger.info(f"Input device: {self._input_device_index}, Output device: {self._output_device_index}")

        except Exception as e:
            self.logger.error(f"Failed to initialize audio: {e}")
            raise

    def _find_vb_cable_device(self) -> Optional[int]:
        
        target_device = self.config.output_device.lower()

        for i in range(self._pyaudio.get_device_count()):
            device_info = self._pyaudio.get_device_info_by_index(i)
            device_name = device_info.get('name', '').lower()

            if target_device in device_name:
                if device_info.get('maxOutputChannels', 0) > 0:
                    self.logger.info(f"Found VB-Cable device: {device_info['name']}")
                    return i

        return None

    def play_sound(self, sound_name: str):
        self.stop_playback()

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

            self.logger.debug(f"Loaded audio: {sound_path}, {original_channels}ch@{original_rate}Hz -> {audio.channels}ch@{audio.frame_rate}Hz, {len(audio)}ms")

            return audio

        except Exception as e:
            error_msg = f"Failed to load audio file {sound_path}: {e}"

            try:
                self.logger.warning(f"Primary loading failed, trying fallback for {sound_path}")

                if sound_path.lower().endswith(('.mp3', '.m4a')):
                    audio = AudioSegment.from_file(sound_path, format="mp3")
                elif sound_path.lower().endswith('.wav'):
                    audio = AudioSegment.from_file(sound_path, format="wav")
                else:
                    raise e

                if len(audio) == 0:
                    raise ValueError(f"Fallback loading produced empty audio: {sound_path}")

                audio = audio.set_channels(self._channels).set_frame_rate(self._sample_rate)
                self.logger.info(f"Fallback loading succeeded for {sound_path}")
                return audio

            except Exception as fallback_e:
                self.logger.error(f"Fallback loading also failed for {sound_path}: {fallback_e}")

            self.logger.error(error_msg)
            raise RuntimeError(f"Unable to load audio file. This may be due to:\n"
                             f"• Unsupported audio format\n"
                             f"• Corrupted audio file\n"
                             f"• Missing audio codecs\n"
                             f"• File currently in use by another application\n\n"
                             f"Original error: {e}")

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

    def set_device(self, device_name: str):
        
        self.config.set("audio.output_device", device_name)
        self.config.save()

        self._cleanup_audio()
        self._device_index = None
        self._initialize_audio()

    def _cleanup_audio(self):
        
        self.stop_playback()

        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception as e:
                self.logger.warning(f"Error terminating PyAudio: {e}")
            self._pyaudio = None

    def get_input_devices(self) -> list:
        
        devices = []
        if self._pyaudio:
            for i in range(self._pyaudio.get_device_count()):
                device_info = self._pyaudio.get_device_info_by_index(i)
                if device_info.get('maxInputChannels', 0) > 0:
                    devices.append({
                        'index': i,
                        'name': device_info.get('name', f'Device {i}'),
                        'channels': device_info.get('maxInputChannels', 0),
                        'sample_rate': int(device_info.get('defaultSampleRate', 44100))
                    })
        return devices

    def get_output_devices(self) -> list:
        
        devices = []
        if self._pyaudio:
            for i in range(self._pyaudio.get_device_count()):
                device_info = self._pyaudio.get_device_info_by_index(i)
                if device_info.get('maxOutputChannels', 0) > 0:
                    devices.append({
                        'index': i,
                        'name': device_info.get('name', f'Device {i}'),
                        'channels': device_info.get('maxOutputChannels', 0),
                        'sample_rate': int(device_info.get('defaultSampleRate', 44100))
                    })
        return devices

    def set_input_device(self, device_index: int):
        
        if self._pyaudio:
            try:
                device_info = self._pyaudio.get_device_info_by_index(device_index)
                if device_info.get('maxInputChannels', 0) > 0:
                    self._input_device_index = device_index
                    self.logger.info(f"Input device set to: {device_info['name']}")
                    self.restart_routing_if_needed()
                else:
                    raise ValueError("Selected device is not an input device")
            except Exception as e:
                self.logger.error(f"Failed to set input device: {e}")
                raise

    def set_output_device(self, device_index: int):
        
        if self._pyaudio:
            try:
                device_info = self._pyaudio.get_device_info_by_index(device_index)
                if device_info.get('maxOutputChannels', 0) > 0:
                    self._output_device_index = device_index
                    self.logger.info(f"Output device set to: {device_info['name']}")
                    self.restart_routing_if_needed()
                else:
                    raise ValueError("Selected device is not an output device")
            except Exception as e:
                self.logger.error(f"Failed to set output device: {e}")
                raise

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
            self._input_stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                input_device_index=self._input_device_index,
                frames_per_buffer=1024
            )

            self._output_stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                output=True,
                output_device_index=self._output_device_index,
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
            if not self._is_playing or self._current_sound_data is None:
                return input_data

            input_array = np.frombuffer(input_data, dtype=np.int16)
            chunk_size = len(input_array)

            if self._current_sound_pos >= len(self._current_sound_data):
                self._is_playing = False
                self._current_sound_data = None
                self._current_sound_pos = 0
                self._current_sound = None
                return input_data

            start_pos = self._current_sound_pos
            end_pos = min(start_pos + chunk_size, len(self._current_sound_data))

            sound_chunk = self._current_sound_data[start_pos:end_pos]
            self._current_sound_pos = end_pos

            if len(sound_chunk) < chunk_size:
                sound_chunk = np.pad(sound_chunk, (0, chunk_size - len(sound_chunk)), 'constant')

            volume = self.config.get_sound(self._current_sound).get("volume", self.config.default_volume) / 100.0
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

    def __del__(self):
        
        self._cleanup_audio()
