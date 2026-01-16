import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    def __init__(self):
        self.app_dir = Path.home() / ".soundboard"
        self.sounds_dir = self.app_dir / "sounds"
        self.config_file = self.app_dir / "config.json"
        self.log_file = self.app_dir / "soundboard.log"

        self._config = {
            "audio": {
                "default_volume": 80,
                "output_device": "VB-Audio Virtual Cable",
                "sample_rate": 44100,
                "channels": 2
            },
            "sounds": {},
            "keybinds": {}
        }

        self._ensure_directories()
        self.load()
        self._auto_save_enabled = True

    def _ensure_directories(self):
        self.app_dir.mkdir(exist_ok=True)
        self.sounds_dir.mkdir(exist_ok=True)

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self._config.update(loaded_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file: {e}")

    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save config file: {e}")

    def _auto_save(self):
        if getattr(self, '_auto_save_enabled', False):
            self.save()

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def add_sound(self, name: str, path: str, volume: int = 80):
        self._config["sounds"][name] = {"path": str(path), "volume": volume}
        self._auto_save()

    def remove_sound(self, name: str):
        self._config["sounds"].pop(name, None)
        self._auto_save()

    def set_sound_volume(self, name: str, volume: int):
        if name in self._config["sounds"]:
            self._config["sounds"][name]["volume"] = volume
            self._auto_save()

    def get_sound_volume(self, name: str) -> int:
        sound = self.get_sound(name)
        return sound.get("volume", self.default_volume) if sound else self.default_volume

    def get_sound(self, name: str) -> Optional[Dict[str, Any]]:
        return self._config["sounds"].get(name)

    def get_all_sounds(self) -> Dict[str, Dict[str, Any]]:
        return self._config["sounds"].copy()

    def set_keybind(self, sound_name: str, keybind: str):
        self._config["keybinds"][sound_name] = keybind
        self._auto_save()

    def get_keybind(self, sound_name: str) -> Optional[str]:
        return self._config["keybinds"].get(sound_name)

    def remove_keybind(self, sound_name: str):
        self._config["keybinds"].pop(sound_name, None)
        self._auto_save()

    def get_all_keybinds(self) -> Dict[str, str]:
        return self._config["keybinds"].copy()

    @property
    def default_volume(self) -> int:
        return self.get("audio.default_volume", 80)

    @property
    def output_device(self) -> str:
        return self.get("audio.output_device", "VB-Audio Virtual Cable")

    @property
    def sample_rate(self) -> int:
        return self.get("audio.sample_rate", 44100)

    @property
    def channels(self) -> int:
        return self.get("audio.channels", 2)
