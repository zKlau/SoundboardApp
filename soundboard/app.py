import sys
import threading
import logging

from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow
from .sound_manager import SoundManager
from .keybind_handler import KeybindHandler
from .audio_player import AudioPlayer
from .config import Config


class SoundboardApp:
    def __init__(self):
        self.qt_app = None
        self.main_window = None
        self.config = None
        self.sound_manager = None
        self.audio_player = None
        self.keybind_handler = None
        self.keybind_thread = None

    def run(self):
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Soundboard")
        self.qt_app.setApplicationVersion("1.0.0")

        try:
            self.initialize_components()
            self.main_window.show()

            self.keybind_thread = threading.Thread(
                target=self.keybind_handler.start_listening,
                daemon=True
            )
            self.keybind_thread.start()

            return self.qt_app.exec()

        except Exception as e:
            print(f"Error starting application: {e}")
            import traceback
            traceback.print_exc()
            return 1

    def initialize_components(self):
        self.config = Config()
        self.sound_manager = SoundManager(self.config)
        self.audio_player = AudioPlayer(self.config)
        self.keybind_handler = KeybindHandler(self.config)

        self.setup_logging()
        self.main_window = MainWindow(
            self.config,
            self.sound_manager,
            self.audio_player,
            self.keybind_handler
        )

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

