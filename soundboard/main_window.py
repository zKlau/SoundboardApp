import sys
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QLabel,
    QFileDialog, QInputDialog, QMessageBox, QSystemTrayIcon, QMenu,
    QProgressBar, QFrame, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QIcon, QAction

from .keybind_handler import KeybindHandler
from .audio_player import AudioPlayer
from .config import Config
from .dialogs import KeybindDialog

class MainWindow(QMainWindow):
    sound_added = pyqtSignal(str, str)
    sound_removed = pyqtSignal(str)
    keybind_changed = pyqtSignal(str, str)
    volume_changed = pyqtSignal(str, int)

    def __init__(self, config, audio_player, keybind_handler):
        super().__init__()
        self.config = config
        self.audio_player = audio_player
        self.keybind_handler = keybind_handler

        self.setup_ui()
        self.setup_connections()
        self.load_saved_sounds()
        self.populate_audio_devices()

        self.setup_system_tray()

    def setup_ui(self):
        self.setWindowTitle("Soundboard")
        self.setGeometry(100, 100, 600, 500)
        self.setWindowIcon(QIcon("icons/soundboard.png"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        self.sound_list = QListWidget()
        self.sound_list.setMinimumHeight(200)
        self.sound_list.itemSelectionChanged.connect(self.on_sound_selected)
        layout.addWidget(QLabel("Sounds:"))
        layout.addWidget(self.sound_list)

        button_layout = QHBoxLayout()

        self.add_button = QPushButton("Add Sound")
        self.add_button.clicked.connect(self.add_sound)
        button_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("Remove Sound")
        self.remove_button.clicked.connect(self.remove_sound)
        button_layout.addWidget(self.remove_button)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.change_volume)
        button_layout.addWidget(QLabel("Volume:"))
        button_layout.addWidget(self.volume_slider)

        layout.addLayout(button_layout)

        device_group = QGroupBox("Audio Devices")
        device_layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input Microphone:"))
        self.input_device_combo = QComboBox()
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)
        input_layout.addWidget(self.input_device_combo)
        device_layout.addLayout(input_layout)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Microphone:"))
        self.output_device_combo = QComboBox()
        self.output_device_combo.currentIndexChanged.connect(self.on_output_device_changed)
        output_layout.addWidget(self.output_device_combo)
        device_layout.addLayout(output_layout)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        keybind_layout = QHBoxLayout()
        self.keybind_button = QPushButton("Set Keybind")
        self.keybind_button.clicked.connect(self.set_keybind)
        keybind_layout.addWidget(self.keybind_button)

        self.current_keybind_label = QLabel("Current: None")
        keybind_layout.addWidget(self.current_keybind_label)

        layout.addLayout(keybind_layout)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def setup_connections(self):
        self.sound_added.connect(self.on_sound_added)
        self.sound_removed.connect(self.on_sound_removed)
        self.keybind_changed.connect(self.on_keybind_changed)
        self.volume_changed.connect(self.on_volume_changed)

        self.keybind_handler.keybind_pressed.connect(self.audio_player.play_sound)

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icons/soundboard.png"))

        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def add_sound(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sound File",
            str(self.config.sounds_dir),
            "Audio Files (*.wav *.mp3 *.ogg *.flac *.aac *.m4a)"
        )

        if not file_path:
            return

        sound_name, ok = QInputDialog.getText(
            self, "Sound Name",
            "Enter a name for this sound:",
            text=Path(file_path).stem
        )

        if not ok or not sound_name.strip():
            return

        try:
            self.config.add_sound(sound_name.strip(), file_path)
            self.sound_added.emit(sound_name.strip(), file_path)
            self.status_bar.showMessage(f"Added sound: {sound_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add sound: {e}")

    def remove_sound(self):
        current_item = self.sound_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a sound to remove.")
            return

        sound_name = current_item.text().split(" (")[0]

        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Are you sure you want to remove '{sound_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.config.remove_sound(sound_name)
                self.keybind_handler.remove_keybind(sound_name)
                self.sound_removed.emit(sound_name)
                self.status_bar.showMessage(f"Removed sound: {sound_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove sound: {e}")

    def set_keybind(self):
        current_item = self.sound_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a sound first.")
            return

        sound_name = current_item.text().split(" (")[0]

        dialog = KeybindDialog(self)
        if dialog.exec():
            keybind = dialog.get_keybind()
            if keybind:
                try:
                    self.keybind_handler.set_keybind(sound_name, keybind)
                    self.keybind_changed.emit(sound_name, keybind)
                    self.status_bar.showMessage(f"Set keybind for {sound_name}: {keybind}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to set keybind: {e}")

    def change_volume(self):
        current_item = self.sound_list.currentItem()
        if not current_item:
            return

        sound_name = current_item.text().split(" (")[0]
        volume = self.volume_slider.value()

        try:
            self.config.set_sound_volume(sound_name, volume)
            self.volume_changed.emit(sound_name, volume)
            self.status_bar.showMessage(f"Set volume for {sound_name}: {volume}%")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change volume: {e}")

    def load_saved_sounds(self):
        for sound_name, sound_data in self.config.get_all_sounds().items():
            keybind = self.keybind_handler.get_keybind(sound_name)
            display_text = f"{sound_name} ({keybind or 'no keybind'})"
            self.sound_list.addItem(display_text)

    def on_sound_added(self, name, path):
        keybind = self.keybind_handler.get_keybind(name)
        display_text = f"{name} ({keybind or 'no keybind'})"
        self.sound_list.addItem(display_text)

    def on_sound_removed(self, name):
        for i in range(self.sound_list.count()):
            item = self.sound_list.item(i)
            if item.text().startswith(f"{name} ("):
                self.sound_list.takeItem(i)
                break

    def on_keybind_changed(self, sound_name, keybind):
        for i in range(self.sound_list.count()):
            item = self.sound_list.item(i)
            if item.text().startswith(f"{sound_name} ("):
                item.setText(f"{sound_name} ({keybind})")
                break

    def on_volume_changed(self, sound_name, volume):
        pass

    def populate_audio_devices(self):
        input_devices = self.audio_player.get_input_devices()
        output_devices = self.audio_player.get_output_devices()

        self.input_device_combo.clear()
        self.output_device_combo.clear()

        for device in input_devices:
            self.input_device_combo.addItem(device['name'], device['index'])

        for device in output_devices:
            self.output_device_combo.addItem(device['name'], device['index'])

        self.select_default_devices()

    def select_default_devices(self):
        for i in range(self.output_device_combo.count()):
            device_name = self.output_device_combo.itemText(i).lower()
            if 'cable' in device_name or 'virtual' in device_name:
                self.output_device_combo.setCurrentIndex(i)
                break

        if self.input_device_combo.count() > 0:
            self.input_device_combo.setCurrentIndex(0)

    def on_input_device_changed(self, index):
        if index >= 0:
            device_index = self.input_device_combo.itemData(index)
            self.audio_player.set_input_device(device_index)
            self.status_bar.showMessage(f"Input device changed to: {self.input_device_combo.currentText()}")
            self.start_audio_routing_if_ready()

    def on_output_device_changed(self, index):
        if index >= 0:
            device_index = self.output_device_combo.itemData(index)
            self.audio_player.set_output_device(device_index)
            self.status_bar.showMessage(f"Output device changed to: {self.output_device_combo.currentText()}")
            self.start_audio_routing_if_ready()

    def start_audio_routing_if_ready(self):
        if (self.input_device_combo.currentIndex() >= 0 and
            self.output_device_combo.currentIndex() >= 0):
            self.audio_player.start_audio_routing()

    def on_sound_selected(self):
        current_item = self.sound_list.currentItem()
        if current_item:
            sound_name = current_item.text().split(" (")[0]
            current_volume = self.config.get_sound_volume(sound_name)
            self.volume_slider.setValue(current_volume)

    def closeEvent(self, event):
        self.config.save()
        self.keybind_handler.stop_listening()
        self.tray_icon.hide()
        event.accept()
