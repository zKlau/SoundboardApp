import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from soundboard.app import SoundboardApp


def main():
    try:
        app = SoundboardApp()
        return app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
