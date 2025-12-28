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

        self._load_keybinds()

    def _load_keybinds(self):
        for sound_name, keybind in self.config.get_all_keybinds().items():
            self._active_keybinds[sound_name] = keybind

    def set_keybind(self, sound_name: str, keybind: str):
        if sound_name in self._active_keybinds:
            self._remove_keybind(sound_name)

        normalized_keybind = self._normalize_keybind(keybind)

        for existing_sound, existing_keybind in self._active_keybinds.items():
            if existing_keybind == normalized_keybind and existing_sound != sound_name:
                raise ValueError(f"Keybind '{keybind}' is already assigned to '{existing_sound}'")

        try:
            self._active_keybinds[sound_name] = normalized_keybind
            self.config.set_keybind(sound_name, normalized_keybind)
            self.config.save()

            self.logger.info(f"Set keybind for {sound_name}: {normalized_keybind}")

        except Exception as e:
            if sound_name in self._active_keybinds:
                del self._active_keybinds[sound_name]
            raise RuntimeError(f"Failed to register keybind: {e}")

    def remove_keybind(self, sound_name: str):
        if sound_name in self._active_keybinds:
            self._remove_keybind(sound_name)
            self.config.remove_keybind(sound_name)
            self.config.save()
            self.logger.info(f"Removed keybind for {sound_name}")

    def _remove_keybind(self, sound_name: str):
        if sound_name in self._active_keybinds:
            del self._active_keybinds[sound_name]

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
            if event.event_type == keyboard.KEY_DOWN:
                self._modifier_state[key] = True
            elif event.event_type == keyboard.KEY_UP:
                self._modifier_state[key] = False
            return

        modifiers = []
        if self._modifier_state['ctrl']:
            modifiers.append('ctrl')
        if self._modifier_state['alt']:
            modifiers.append('alt')
        if self._modifier_state['shift']:
            modifiers.append('shift')

        if modifiers:
            keybind_str = '+'.join(modifiers + [key])
        else:
            keybind_str = key

        if event.event_type == keyboard.KEY_DOWN:
            if keybind_str not in self._pressed_keys:
                self._pressed_keys.add(keybind_str)

                for sound_name, bound_keybind in self._active_keybinds.items():
                    if bound_keybind == keybind_str:
                        self.logger.debug(f"Keybind pressed for sound: {sound_name}")
                        self.keybind_pressed.emit(sound_name)
                        break

        elif event.event_type == keyboard.KEY_UP:
            keys_to_remove = set()
            for pressed_keybind in self._pressed_keys:
                pressed_parts = set(pressed_keybind.split('+'))
                if key in pressed_parts:
                    keys_to_remove.add(pressed_keybind)

            for keybind_to_remove in keys_to_remove:
                self._pressed_keys.discard(keybind_to_remove)

    def _on_keybind_pressed(self, sound_name: str):
        self.logger.debug(f"Keybind pressed for sound: {sound_name}")
        self.keybind_pressed.emit(sound_name)

    def start_listening(self):
        if self._listening:
            return

        self._listening = True
        self._pressed_keys.clear()
        self._modifier_state = {'ctrl': False, 'alt': False, 'shift': False}
        self.logger.info("Started keybind listening")

        try:
            keyboard.hook(self._on_key_event)
            keyboard.wait()

        except Exception as e:
            self.logger.error(f"Error in keybind listening: {e}")
        finally:
            self._listening = False

    def stop_listening(self):
        if not self._listening:
            return

        self._listening = False
        self._pressed_keys.clear()
        self._modifier_state = {'ctrl': False, 'alt': False, 'shift': False}
        self.logger.info("Stopped keybind listening")

        try:
            keyboard.unhook_all()

        except Exception as e:
            self.logger.error(f"Error stopping keybind listening: {e}")

    def is_listening(self) -> bool:
        return self._listening

    def __del__(self):
        self.stop_listening()
