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
            self._output_device_index = self._find_vb_cable_device() or self._pyaudio.get_default_output_device_info()['index']
            
            if self._output_device_index == self._pyaudio.get_default_output_device_info()['index']:
                self.logger.warning("VB-Cable not found, using default device")
            
            self.logger.info(f"Devices - Input: {self._input_device_index}, Output: {self._output_device_index}")
        except Exception as e:
            self.logger.error(f"Audio init failed: {e}")
            raise

    def _find_vb_cable_device(self) -> Optional[int]:
        target = self.config.output_device.lower()
        for i in range(self._pyaudio.get_device_count()):
            device_info = self._pyaudio.get_device_info_by_index(i)
            if target in device_info.get('name', '').lower() and device_info.get('maxOutputChannels', 0) > 0:
                self.logger.info(f"Found VB-Cable: {device_info['name']}")
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

    def _set_device(self, device_index: int, is_input: bool):
        if not self._pyaudio:
            return
        try:
            device_info = self._pyaudio.get_device_info_by_index(device_index)
            channel_key = 'maxInputChannels' if is_input else 'maxOutputChannels'
            
            if device_info.get(channel_key, 0) <= 0:
                raise ValueError(f"Invalid {'input' if is_input else 'output'} device")
            
            if is_input:
                self._input_device_index = device_index
            else:
                self._output_device_index = device_index
            
            self.logger.info(f"{'Input' if is_input else 'Output'} device: {device_info['name']}")
        except Exception as e:
            self.logger.error(f"Failed to set device: {e}")
            raise

    def set_input_device(self, device_index: int):
        self._set_device(device_index, True)

    def set_output_device(self, device_index: int):
        self._set_device(device_index, False)

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
