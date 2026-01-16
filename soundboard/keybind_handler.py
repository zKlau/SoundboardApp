import keyboard
import logging
from typing import Dict, Callable, Optional
from PyQt6.QtCore import QObject, pyqtSignal

from .config import Config


class KeybindHandler(QObject):
    keybind_pressed = pyqtSignal(str)

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.logger = logging.getLogger(__name__)

        self._active_keybinds: Dict[str, str] = {}
        self._pressed_keys: set = set()
        self._modifier_state = {'ctrl': False, 'alt': False, 'shift': False}
        self._listening = False
        self._sound_player = None

        self._load_keybinds()
    
    def set_sound_player(self, sound_player):
        self._sound_player = sound_player

    def _load_keybinds(self):
        for sound_name, keybind in self.config.get_all_keybinds().items():
            self._active_keybinds[sound_name] = keybind

    def set_keybind(self, sound_name: str, keybind: str):
        if sound_name in self._active_keybinds:
            del self._active_keybinds[sound_name]

        normalized_keybind = self._normalize_keybind(keybind)

        for existing_sound, existing_keybind in self._active_keybinds.items():
            if existing_keybind == normalized_keybind and existing_sound != sound_name:
                raise ValueError(f"Keybind already assigned to '{existing_sound}'")

        try:
            self._active_keybinds[sound_name] = normalized_keybind
            self.config.set_keybind(sound_name, normalized_keybind)
            self.logger.info(f"Keybind set: {sound_name} -> {normalized_keybind}")
        except Exception as e:
            self._active_keybinds.pop(sound_name, None)
            raise RuntimeError(f"Failed to register keybind: {e}")

    def remove_keybind(self, sound_name: str):
        if sound_name in self._active_keybinds:
            del self._active_keybinds[sound_name]
            self.config.remove_keybind(sound_name)
            self.logger.info(f"Removed keybind: {sound_name}")

    def get_keybind(self, sound_name: str) -> Optional[str]:
        return self._active_keybinds.get(sound_name)

    def get_all_keybinds(self) -> Dict[str, str]:
        return self._active_keybinds.copy()

    def _normalize_keybind(self, keybind: str) -> str:
        return keybind.lower().strip()

    def _on_key_event(self, event):
        if not self._listening:
            return

        key = event.name.lower()

        if key in ['ctrl', 'alt', 'shift']:
            self._modifier_state[key] = (event.event_type == keyboard.KEY_DOWN)
            return

        modifiers = [m for m, pressed in self._modifier_state.items() if pressed]
        keybind_str = '+'.join(modifiers + [key]) if modifiers else key

        if event.event_type == keyboard.KEY_DOWN:
            if keybind_str not in self._pressed_keys:
                self._pressed_keys.add(keybind_str)
                
                if self._sound_player and self._sound_player.is_playing():
                    return
                
                for sound_name, bound_keybind in self._active_keybinds.items():
                    if bound_keybind == keybind_str:
                        self.logger.debug(f"Triggered: {sound_name}")
                        self.keybind_pressed.emit(sound_name)
                        break
        elif event.event_type == keyboard.KEY_UP:
            self._pressed_keys = {kb for kb in self._pressed_keys if key not in kb.split('+')}

    def _reset_state(self):
        self._pressed_keys.clear()
        self._modifier_state = {'ctrl': False, 'alt': False, 'shift': False}

    def start_listening(self):
        if self._listening:
            return
        self._listening = True
        self._reset_state()
        self.logger.info("Keybind listening started")
        try:
            keyboard.hook(self._on_key_event)
            keyboard.wait()
        except Exception as e:
            self.logger.error(f"Listening error: {e}")
        finally:
            self._listening = False

    def stop_listening(self):
        if not self._listening:
            return
        self._listening = False
        self._reset_state()
        self.logger.info("Keybind listening stopped")
        try:
            keyboard.unhook_all()
        except Exception as e:
            self.logger.error(f"Stop error: {e}")

    def is_listening(self) -> bool:
        return self._listening

    def __del__(self):
        self.stop_listening()
