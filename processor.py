"""
Audio Processing Pipeline with Checkpoint Support
Handles recording, splitting, transcoding, tagging, and organizing tracks
Supports resuming from where you left off
"""
import logging
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Callable
import re

from progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Handles audio processing with checkpoint/resume capability"""

    def __init__(self, temp_dir: Path, output_dir: Path, progress_tracker: ProgressTracker):
        """
        Initialize processor

        Args:
            temp_dir: Temporary directory for intermediate files
            output_dir: Final output directory for processed tracks
            progress_tracker: ProgressTracker instance for checkpoints
        """
        self.temp_dir = Path(temp_dir)
        self.output_dir = Path(output_dir)
        self.progress = progress_tracker
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def record_apple_music(self, duration: int = None,
                          callback: Optional[Callable] = None) -> Path:
        """
        Record Apple Music playback via BlackHole

        Args:
            duration: Recording duration in seconds (None = until stopped)
            callback: Progress callback function

        Returns:
            Path to recorded audio file
        """
        logger.info("Starting Apple Music recording via BlackHole")

        output_file = self.temp_dir / "recording.wav"

        # ffmpeg command to record from BlackHole
        cmd = [
            'ffmpeg',
            '-f', 'avfoundation',
            '-i', ':BlackHole 2ch',
            '-t', str(duration) if duration else '999999',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            str(output_file)
        ]

        try:
            if callback:
                callback("Recording Apple Music...")

            # Run ffmpeg
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Wait for recording to complete
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                logger.error(f"Recording failed: {stderr}")
                raise RuntimeError(f"ffmpeg error: {stderr}")

            # Save recording path to progress tracker
            self.progress.set_recording_file(str(output_file))

            logger.info(f"Recording saved to {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Error recording: {str(e)}")
            raise

    def split_by_silence(self, audio_file: Path,
                        silence_threshold: float = -40,
                        silence_duration: float = 2.0,
                        callback: Optional[Callable] = None) -> List[Path]:
        """
        Split continuous audio into tracks using silence detection

        Args:
            audio_file: Path to audio file
            silence_threshold: Silence threshold in dB
            silence_duration: Minimum silence duration in seconds
            callback: Progress callback function

        Returns:
            List of split audio file paths
        """
        logger.info(f"Detecting silence in {audio_file}")

        if callback:
            callback("Detecting track boundaries...")

        # Use ffmpeg to detect silence and split
        cmd = [
            'ffmpeg',
            '-i', str(audio_file),
            '-af', f'silencedetect=n={silence_threshold}dB:d={silence_duration}',
            '-f', 'null',
            '-'
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            stdout, stderr = process.communicate()

            # Parse silence detection output
            silence_times = self._parse_silence_output(stderr)
            logger.info(f"Found {len(silence_times)} silence points")

            # Split audio at silence points
            split_files = self._create_splits(audio_file, silence_times, callback)

            # Save split file paths to progress tracker
            self.progress.set_split_files(split_files)

            return split_files

        except Exception as e:
            logger.error(f"Error splitting audio: {str(e)}")
            raise

    def _parse_silence_output(self, ffmpeg_output: str) -> List[float]:
        """Parse ffmpeg silence detection output"""
        times = []

        for line in ffmpeg_output.split('\n'):
            match = re.search(r'silence_end:\s+([\d.]+)', line)
            if match:
                time = float(match.group(1))
                times.append(time)

        return sorted(times)

    def _create_splits(self, audio_file: Path, split_times: List[float],
                      callback: Optional[Callable] = None) -> List[Path]:
        """Create individual audio files from split points"""
        split_files = []
        start_time = 0

        for i, end_time in enumerate(split_times):
            if end_time - start_time > 5:  # Skip very short segments
                output_file = self.temp_dir / f"track_{i+1:03d}.wav"

                cmd = [
                    'ffmpeg',
                    '-i', str(audio_file),
                    '-ss', str(start_time),
                    '-to', str(end_time),
                    '-c', 'copy',
                    str(output_file)
                ]

                try:
                    subprocess.run(cmd, check=True,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                    split_files.append(output_file)

                    if callback:
                        callback(f"Created track {i+1}")

                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to create split {i+1}: {str(e)}")

            start_time = end_time

        return split_files

    def transcode_to_mp3(self, audio_file: Path, bitrate: str = "320k",
                        callback: Optional[Callable] = None) -> Path:
        """
        Transcode audio to 320 kbps MP3

        Args:
            audio_file: Path to input audio
            bitrate: Target bitrate (default 320k)
            callback: Progress callback function

        Returns:
            Path to transcoded MP3 file
        """
        output_file = audio_file.with_suffix('.mp3')

        cmd = [
            'ffmpeg',
            '-i', str(audio_file),
            '-b:a', bitrate,
            '-q:a', '0',
            str(output_file)
        ]

        try:
            if callback:
                callback(f"Transcoding to {bitrate}...")

            subprocess.run(cmd, check=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

            logger.info(f"Transcoded to {output_file}")
            return output_file

        except subprocess.CalledProcessError as e:
            logger.error(f"Transcoding failed: {str(e)}")
            raise

    def tag_audio(self, audio_file: Path, metadata: Dict) -> None:
        """
        Tag MP3 file with ID3 metadata

        Args:
            audio_file: Path to MP3 file
            metadata: Dictionary with title, artist, album, etc.
        """
        try:
            from mutagen.easyid3 import EasyID3
        except ImportError:
            logger.warning("mutagen not installed, skipping tagging")
            return

        try:
            audio = EasyID3(str(audio_file))

            if 'title' in metadata:
                audio['title'] = metadata['title']
            if 'artist' in metadata:
                audio['artist'] = metadata['artist']
            if 'album' in metadata:
                audio['album'] = metadata['album']
            if 'position' in metadata:
                audio['tracknumber'] = str(metadata['position'])

            audio.save()
            logger.info(f"Tagged {audio_file}")

        except Exception as e:
            logger.warning(f"Failed to tag {audio_file}: {str(e)}")

    def organize_file(self, audio_file: Path, metadata: Dict) -> Path:
        """
        Move and organize audio file into library structure

        Args:
            audio_file: Path to audio file
            metadata: Track metadata dictionary

        Returns:
            Path to organized file in output directory
        """
        artist = metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        title = metadata.get('title', 'Unknown')

        artist_dir = self._sanitize_path(artist)
        album_dir = self._sanitize_path(album)
        filename = self._sanitize_path(title) + '.mp3'

        target_dir = self.output_dir / artist_dir / album_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / filename
        audio_file.rename(target_path)

        logger.info(f"Organized to {target_path}")
        return target_path

    def _sanitize_path(self, name: str) -> str:
        """Remove invalid characters from path names"""
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '', name)
        sanitized = sanitized.strip()
        return sanitized[:200] or 'Unknown'

    def match_tracks_to_metadata(self, track_files: List[Path],
                                metadata_list: List[Dict]) -> List[tuple]:
        """
        Match split audio files to metadata by duration

        Args:
            track_files: List of split audio file paths
            metadata_list: List of track metadata dictionaries

        Returns:
            List of (audio_file, metadata) tuples
        """
        matches = []

        for audio_file in track_files:
            duration = self._get_audio_duration(audio_file)

            best_match = None
            min_diff = 5.0

            for metadata in metadata_list:
                meta_duration = metadata.get('duration', 0)
                diff = abs(duration - meta_duration)

                if diff < min_diff:
                    best_match = metadata
                    min_diff = diff

            if best_match:
                matches.append((audio_file, best_match))
                metadata_list.remove(best_match)
            else:
                logger.warning(f"Could not match metadata for {audio_file}")
                matches.append((audio_file, {
                    'title': audio_file.stem,
                    'artist': 'Unknown',
                    'album': 'Unknown',
                    'duration': duration
                }))

        return matches

    def _get_audio_duration(self, audio_file: Path) -> float:
        """Get duration of audio file in seconds"""
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error',
                 '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1:noprint_wrappers=1',
                 str(audio_file)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get duration for {audio_file}: {str(e)}")

        return 0

    def process_remaining_tracks(self, track_files: List[Path],
                                metadata_list: List[Dict],
                                bitrate: str = "320k",
                                callback: Optional[Callable] = None,
                                should_stop: Optional[Callable[[], bool]] = None) -> None:
        """
        Process only tracks that haven't been completed yet

        Args:
            track_files: List of split audio files
            metadata_list: List of track metadata
            bitrate: Target bitrate
            callback: Progress callback function
            should_stop: Optional function returning True when the user has
                         pressed Stop; checked before each track
        """
        # Get remaining tracks from progress tracker
        remaining = self.progress.get_remaining_tracks(metadata_list)
        total_remaining = len(remaining)

        if total_remaining == 0:
            if callback:
                callback("All tracks already processed!")
            return

        logger.info(f"Processing {total_remaining} remaining tracks")

        # Match tracks to metadata
        matches = self.match_tracks_to_metadata(track_files, metadata_list)

        for idx, (audio_file, metadata) in enumerate(matches):
            if should_stop and should_stop():
                logger.info("Stop requested; pausing before next track")
                if callback:
                    callback("Paused by user")
                return

            track_index = metadata.get('position', idx) - 1

            # Skip if already completed
            if track_index in self.progress.state.get('completed_tracks', []):
                logger.info(f"Skipping already-processed track: {metadata.get('title')}")
                continue

            try:
                if callback:
                    callback(f"Processing {idx+1}/{len(matches)}: {metadata.get('artist')} - {metadata.get('title')}")

                # Transcode
                mp3_file = self.transcode_to_mp3(audio_file, bitrate, callback)

                # Tag
                self.tag_audio(mp3_file, metadata)

                # Organize
                self.organize_file(mp3_file, metadata)

                # Mark as completed
                self.progress.mark_track_completed(track_index, metadata)

            except Exception as e:
                logger.error(f"Failed to process track {track_index}: {str(e)}")
                self.progress.mark_track_failed(track_index, str(e))
                if callback:
                    callback(f"❌ Failed: {metadata.get('title')}")

    def cleanup_temp_files(self, keep_splits: bool = False) -> None:
        """
        Clean up temporary files

        Args:
            keep_splits: If True, keep split WAV files for potential resume
        """
        try:
            import shutil

            if keep_splits:
                # Only delete non-split files
                for f in self.temp_dir.glob('*.mp3'):
                    f.unlink()
                logger.info("Cleaned up transcoded files, kept split WAVs")
            else:
                # Delete everything
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up all temporary files")
        except Exception as e:
            logger.warning(f"Could not clean up temp files: {str(e)}")
