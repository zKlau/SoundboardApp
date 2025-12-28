from setuptools import setup, find_packages
import os

readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()

setup(
    name="soundboard",
    version="1.0.0",
    description="A Python soundboard application that plays sounds through your microphone using VB-Cable",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Claudiu Padure",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PyQt6>=6.4.0",
        "pyaudio>=0.2.13",
        "keyboard>=0.13.5",
        "pydub>=0.25.1",
        "numpy>=1.24.0",
    ],
    extras_require={
        'windows': ['pywin32>=306'],
    },
    entry_points={
        'console_scripts': [
            'soundboard=soundboard.main:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Sound/Audio :: Players",
    ],
    python_requires=">=3.8",
)
