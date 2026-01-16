import subprocess
import os
from typing import List


def check_ffmpeg_availability() -> List[str]:
    components = ['ffmpeg', 'ffprobe']
    missing = []
    
    for component in components:
        try:
            subprocess.run(
                [component, '-version'],
                capture_output=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(component)
    
    return missing
