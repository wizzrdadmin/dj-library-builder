"""
Progress Tracking and Checkpoint System
Tracks which tracks have been completed and allows resuming
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks processing progress and allows resuming sessions"""

    def __init__(self, session_dir: Path):
        """
        Initialize progress tracker

        Args:
            session_dir: Directory to store progress files
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.session_dir / "progress.json"
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load existing progress state if available"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load progress file: {str(e)}")

        # Default state structure
        return {
            'playlist_url': '',
            'total_tracks': 0,
            'completed_tracks': [],
            'failed_tracks': [],
            'current_phase': 'idle',  # idle, recording, processing, done
            'started_at': '',
            'last_updated': '',
            'recording_file': '',
            'split_files': []
        }

    def start_new_session(self, playlist_url: str, total_tracks: int) -> None:
        """
        Start a new processing session

        Args:
            playlist_url: Apple Music playlist URL
            total_tracks: Total number of tracks in playlist
        """
        self.state = {
            'playlist_url': playlist_url,
            'total_tracks': total_tracks,
            'completed_tracks': [],
            'failed_tracks': [],
            'current_phase': 'recording',
            'started_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'recording_file': '',
            'split_files': []
        }
        self._save_state()
        logger.info(f"Started new session: {playlist_url}")

    def resume_session(self) -> bool:
        """
        Check if there's a resumable session

        Returns:
            True if session can be resumed, False otherwise
        """
        if not self.progress_file.exists():
            return False

        # Can resume if we have a playlist URL and haven't completed
        if self.state.get('playlist_url') and self.state.get('current_phase') != 'done':
            return True

        return False

    def get_session_info(self) -> Dict:
        """Get current session info for display"""
        return {
            'playlist_url': self.state.get('playlist_url', ''),
            'total_tracks': self.state.get('total_tracks', 0),
            'completed': len(self.state.get('completed_tracks', [])),
            'failed': len(self.state.get('failed_tracks', [])),
            'remaining': self.state.get('total_tracks', 0) - len(self.state.get('completed_tracks', [])),
            'phase': self.state.get('current_phase', 'idle'),
            'progress_percent': self._calculate_progress()
        }

    def _calculate_progress(self) -> int:
        """Calculate progress percentage"""
        total = self.state.get('total_tracks', 1)
        completed = len(self.state.get('completed_tracks', []))
        return int((completed / total) * 100) if total > 0 else 0

    def set_recording_file(self, filepath: str) -> None:
        """Record the path to the recording file"""
        self.state['recording_file'] = str(filepath)
        self.state['current_phase'] = 'recording'
        self._save_state()

    def set_split_files(self, filepaths: List[str]) -> None:
        """Record split file paths"""
        self.state['split_files'] = [str(f) for f in filepaths]
        self.state['current_phase'] = 'processing'
        self._save_state()

    def mark_track_completed(self, track_index: int, metadata: Dict) -> None:
        """
        Mark a track as successfully processed

        Args:
            track_index: Index of track in playlist
            metadata: Track metadata
        """
        completed = self.state.get('completed_tracks', [])
        if track_index not in completed:
            completed.append(track_index)
        self.state['completed_tracks'] = completed
        self.state['last_updated'] = datetime.now().isoformat()
        self._save_state()

    def mark_track_failed(self, track_index: int, error: str) -> None:
        """
        Mark a track as failed

        Args:
            track_index: Index of track in playlist
            error: Error message
        """
        failed = self.state.get('failed_tracks', [])
        failed.append({
            'index': track_index,
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
        self.state['failed_tracks'] = failed
        self.state['last_updated'] = datetime.now().isoformat()
        self._save_state()

    def get_remaining_tracks(self, metadata_list: List[Dict]) -> List[tuple]:
        """
        Get tracks that still need processing

        Args:
            metadata_list: Full list of track metadata

        Returns:
            List of (index, metadata) tuples for remaining tracks
        """
        completed = set(self.state.get('completed_tracks', []))
        remaining = []

        for i, metadata in enumerate(metadata_list):
            if i not in completed:
                remaining.append((i, metadata))

        return remaining

    def complete_session(self) -> None:
        """Mark session as complete"""
        self.state['current_phase'] = 'done'
        self.state['last_updated'] = datetime.now().isoformat()
        self._save_state()

    def cancel_session(self) -> None:
        """Cancel session and clean up"""
        self.state['current_phase'] = 'cancelled'
        self.state['last_updated'] = datetime.now().isoformat()
        self._save_state()

    def _save_state(self) -> None:
        """Save progress state to file"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {str(e)}")

    def get_stats(self) -> Dict:
        """Get session statistics"""
        completed = len(self.state.get('completed_tracks', []))
        failed = len(self.state.get('failed_tracks', []))
        total = self.state.get('total_tracks', 0)

        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'remaining': total - completed - failed,
            'success_rate': (completed / total * 100) if total > 0 else 0,
            'started_at': self.state.get('started_at', ''),
            'last_updated': self.state.get('last_updated', '')
        }
