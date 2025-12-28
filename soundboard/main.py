import sys
import threading
import logging

from PyQt6.QtWidgets import QApplication

from soundboard.main_window import MainWindow
from soundboard.keybind_handler import KeybindHandler
from soundboard.audio_player import AudioPlayer
from soundboard.config import Config


def main():
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Soundboard")
    qt_app.setApplicationVersion("1.0.0")

    try:
        config = Config()
        audio_player = AudioPlayer(config)
        keybind_handler = KeybindHandler(config)

        setup_logging(config)

        main_window = MainWindow(config, audio_player, keybind_handler)
        main_window.show()

        keybind_thread = threading.Thread(
            target=keybind_handler.start_listening,
            daemon=True
        )
        keybind_thread.start()

        return qt_app.exec()

    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        return 1


def setup_logging(config):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler()
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
