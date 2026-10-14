"""
Configuration and constants for DJ Library Builder
"""
import os
from pathlib import Path

# Output directory for processed tracks
DJ_LIBRARY_PATH = Path.home() / "Music" / "DJ-Library"
TEMP_RECORDINGS_PATH = Path.home() / ".dj_builder_cache"

# Audio settings
TARGET_BITRATE = "320k"  # 320 kbps MP3
SAMPLE_RATE = 44100
SILENCE_THRESHOLD = -40  # dB
SILENCE_DURATION = 2.0  # seconds (gap between tracks)

# Processing settings
MAX_WORKERS = 2  # Parallel processing threads
CHUNK_SIZE = 4096  # For audio processing

# Create directories if they don't exist
DJ_LIBRARY_PATH.mkdir(parents=True, exist_ok=True)
TEMP_RECORDINGS_PATH.mkdir(parents=True, exist_ok=True)
