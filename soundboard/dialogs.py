from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence


class KeybindDialog(QInputDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Keybind")
        self.setLabelText("Press the key combination you want to use:")
        self.setTextValue("")
        self.keybind = ""

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")

        key_name = QKeySequence(key).toString().lower()
        if key_name:
            parts.append(key_name)

        if parts:
            self.keybind = "+".join(parts)
            self.setTextValue(self.keybind)

    def get_keybind(self):
        return self.keybind
