import pyaudio
import logging
from typing import Optional, List, Dict, Any

from .config import Config


class AudioDeviceManager:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._input_device_index: Optional[int] = None
        self._output_device_index: Optional[int] = None
        self._sample_rate: int = config.sample_rate
        self._channels: int = config.channels

    def initialize_audio(self):
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

    def set_device(self, device_name: str):
        self.config.set("audio.output_device", device_name)
        self.config.save()
        self._cleanup_audio()
        self.initialize_audio()

    def _get_devices(self, input_devices: bool) -> List[Dict[str, Any]]:
        devices = []
        if self._pyaudio:
            key = 'maxInputChannels' if input_devices else 'maxOutputChannels'
            for i in range(self._pyaudio.get_device_count()):
                device_info = self._pyaudio.get_device_info_by_index(i)
                if device_info.get(key, 0) > 0:
                    devices.append({
                        'index': i,
                        'name': device_info.get('name', f'Device {i}'),
                        'channels': device_info.get(key, 0),
                        'sample_rate': int(device_info.get('defaultSampleRate', 44100))
                    })
        return devices

    def get_input_devices(self) -> List[Dict[str, Any]]:
        return self._get_devices(True)

    def get_output_devices(self) -> List[Dict[str, Any]]:
        return self._get_devices(False)

    def set_input_device(self, device_index: int):
        if self._pyaudio:
            try:
                device_info = self._pyaudio.get_device_info_by_index(device_index)
                if device_info.get('maxInputChannels', 0) > 0:
                    self._input_device_index = device_index
                    self.logger.info(f"Input device set to: {device_info['name']}")
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
                else:
                    raise ValueError("Selected device is not an output device")
            except Exception as e:
                self.logger.error(f"Failed to set output device: {e}")
                raise

    def _cleanup_audio(self):
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception as e:
                self.logger.warning(f"Error terminating PyAudio: {e}")
            self._pyaudio = None

    def get_pyaudio_instance(self) -> Optional[pyaudio.PyAudio]:
        return self._pyaudio

    def get_input_device_index(self) -> Optional[int]:
        return self._input_device_index

    def get_output_device_index(self) -> Optional[int]:
        return self._output_device_index

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_channels(self) -> int:
        return self._channels
