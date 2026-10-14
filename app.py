"""
DJ Library Builder v2 - Flask Web Backend
Web-based GUI (no Tkinter / PySimpleGUI needed).
Audio processing lives in processor.py, progress_tracker.py and scraper.py.

Flow:
  1. User pastes playlist URL and clicks Start (or Resume).
  2. App scrapes the playlist metadata.
  3. App waits. The user starts the playlist in Apple Music, then clicks
     "I've started the playlist" in the web page.
  4. App records system audio via BlackHole, splits by silence, and
     transcodes each track to 320 kbps MP3 with tags.
  5. Each finished track is checkpointed, so Stop/Resume skips completed work.
"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging
import threading
import json
from pathlib import Path
from datetime import datetime
import shutil

from config import DJ_LIBRARY_PATH, TEMP_RECORDINGS_PATH, TARGET_BITRATE
from scraper import PlaylistScraper
from processor import AudioProcessor
from progress_tracker import ProgressTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

MAX_STATUS_LINES = 500

# Shared state (single user, single worker thread)
state_lock = threading.Lock()
processing = False            # True while the worker thread should keep running
waiting_for_playback = False  # True while we wait for the user's "playing" click
recording_go = threading.Event()
current_session_dir = None
progress_tracker = None
processing_thread = None
status_messages = []


def add_status_message(message: str):
    """Append a timestamped line to the status log shown in the web page."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"{timestamp} | {message}" if message else ""
    with state_lock:
        status_messages.append(line)
        if len(status_messages) > MAX_STATUS_LINES:
            del status_messages[:len(status_messages) - MAX_STATUS_LINES]
    logger.info(message)


def reset_status(first_line: str):
    with state_lock:
        status_messages.clear()
    add_status_message("=" * 70)
    add_status_message(first_line)
    add_status_message("=" * 70)


# ============================================================================
# Web page
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


# ============================================================================
# API
# ============================================================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Return current state for the web page. Polled once per second."""
    global current_session_dir, progress_tracker

    status = {
        'processing': processing,
        'waiting_for_playback': waiting_for_playback,
        'messages': list(status_messages),
        'session_found': False,
        'session_info': None,
    }

    # Look for a resumable session if nothing is active
    if not processing and current_session_dir is None:
        sessions_dir = TEMP_RECORDINGS_PATH / "sessions"
        if sessions_dir.exists():
            for session_dir in sorted(sessions_dir.glob('*'), reverse=True):
                progress_file = session_dir / "progress.json"
                if not progress_file.exists():
                    continue
                try:
                    with open(progress_file, 'r') as f:
                        session_state = json.load(f)

                    if session_state.get('current_phase') != 'done' and session_state.get('playlist_url'):
                        current_session_dir = session_dir
                        progress_tracker = ProgressTracker(session_dir)

                        completed = len(session_state.get('completed_tracks', []))
                        total = session_state.get('total_tracks', 0)
                        status['session_found'] = True
                        status['session_info'] = {
                            'playlist_url': session_state.get('playlist_url', ''),
                            'completed': completed,
                            'total': total,
                            'remaining': total - completed,
                            'phase': session_state.get('current_phase', 'unknown'),
                        }
                        break
                except Exception as e:
                    logger.warning(f"Could not read session {session_dir}: {e}")

    if progress_tracker is not None and current_session_dir is not None:
        info = progress_tracker.get_session_info()
        status['progress'] = {'completed': info['completed'], 'total': info['total_tracks']}

    return jsonify(status)


@app.route('/api/start', methods=['POST'])
def start_new_session():
    global processing, current_session_dir, progress_tracker, processing_thread

    data = request.get_json(silent=True) or {}
    playlist_url = (data.get('playlist_url') or '').strip()

    if not playlist_url:
        return jsonify({'error': 'Please enter an Apple Music playlist URL'}), 400
    if not playlist_url.startswith('https://music.apple.com'):
        return jsonify({'error': 'Invalid Apple Music URL'}), 400
    if processing:
        return jsonify({'error': 'Already processing a playlist'}), 400

    try:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = TEMP_RECORDINGS_PATH / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        current_session_dir = session_dir
        progress_tracker = ProgressTracker(session_dir)

        processing = True
        processing_thread = threading.Thread(
            target=process_playlist_background,
            args=(playlist_url, DJ_LIBRARY_PATH, False),
            daemon=True,
        )
        processing_thread.start()
        reset_status("STARTING NEW SESSION")

        return jsonify({'status': 'started', 'session_id': session_id})

    except Exception as e:
        processing = False
        return jsonify({'error': str(e)}), 500


@app.route('/api/resume', methods=['POST'])
def resume_session():
    global processing, progress_tracker, processing_thread

    if current_session_dir is None:
        return jsonify({'error': 'No session to resume'}), 400
    if processing:
        return jsonify({'error': 'Already processing'}), 400

    try:
        progress_tracker = ProgressTracker(current_session_dir)
        playlist_url = progress_tracker.state.get('playlist_url', '')

        processing = True
        processing_thread = threading.Thread(
            target=process_playlist_background,
            args=(playlist_url, DJ_LIBRARY_PATH, True),
            daemon=True,
        )
        processing_thread.start()
        reset_status("RESUMING SESSION")

        info = progress_tracker.get_session_info()
        add_status_message(f"Resuming: {info['completed']}/{info['total']} tracks completed")
        add_status_message(f"Remaining: {info['remaining']} tracks")

        return jsonify({'status': 'resumed', 'session_info': info})

    except Exception as e:
        processing = False
        return jsonify({'error': str(e)}), 500


@app.route('/api/begin-recording', methods=['POST'])
def begin_recording():
    """Called when the user says Apple Music is playing. Starts the recording."""
    if not waiting_for_playback:
        return jsonify({'error': 'Not waiting for playback'}), 400
    add_status_message("Playback confirmed. Recording started.")
    recording_go.set()
    return jsonify({'status': 'recording'})


@app.route('/api/stop', methods=['POST'])
def stop_processing():
    """Stop between tracks. A recording already in progress finishes first."""
    global processing

    if not processing:
        return jsonify({'status': 'not running'})

    processing = False
    add_status_message("")
    add_status_message("Stop requested. Finishing the current step, then pausing...")
    return jsonify({'status': 'stopping'})


@app.route('/api/clear', methods=['POST'])
def clear_session():
    global current_session_dir, progress_tracker

    if processing:
        return jsonify({'error': 'Stop processing before clearing'}), 400
    if current_session_dir is None:
        return jsonify({'error': 'No session to clear'}), 400

    try:
        shutil.rmtree(current_session_dir)
        current_session_dir = None
        progress_tracker = None
        reset_status("SESSION CLEARED")
        return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Background worker
# ============================================================================

def wait_for_user_to_start_playback() -> bool:
    """
    Block the worker until the user clicks "I've started the playlist".
    Returns False if the user pressed Stop while waiting.
    """
    global waiting_for_playback

    recording_go.clear()
    waiting_for_playback = True
    add_status_message("")
    add_status_message("[2/4] Ready to record")
    add_status_message("  1. Open Apple Music and select your playlist")
    add_status_message("  2. Press Play")
    add_status_message("  3. Click \"I've started the playlist\" on this page")

    try:
        while not recording_go.wait(timeout=0.5):
            if not processing:
                return False
        return True
    finally:
        waiting_for_playback = False


def process_playlist_background(playlist_url: str, output_dir: Path, resume: bool):
    global processing, current_session_dir, progress_tracker

    try:
        if not resume:
            add_status_message("")
            add_status_message("[1/4] Scraping playlist metadata...")
            scraper = PlaylistScraper()
            tracks = scraper.scrape_playlist(playlist_url)

            total_tracks = len(tracks)
            progress_tracker.start_new_session(playlist_url, total_tracks)
            add_status_message(f"Found {total_tracks} tracks")

            scraper.save_tracks_json(tracks, current_session_dir / "playlist_metadata.json")

        else:
            add_status_message("")
            add_status_message("[1/4] Loading saved track list...")
            with open(current_session_dir / "playlist_metadata.json", 'r') as f:
                tracks = json.load(f)

        if not processing:
            add_status_message("Paused before recording.")
            return

        processor = AudioProcessor(current_session_dir, output_dir, progress_tracker)

        recording_file = current_session_dir / "recording.wav"
        if not recording_file.exists():
            if not wait_for_user_to_start_playback():
                add_status_message("Paused before recording.")
                return

            estimated_duration = sum(t.get('duration', 0) for t in tracks)
            add_status_message(f"Recording about {int(estimated_duration // 60)} minutes of audio...")
            add_status_message("(Stop will take effect after the recording finishes.)")
            recording_file = processor.record_apple_music(duration=int(estimated_duration) + 10)
            add_status_message("Recording saved.")
        else:
            add_status_message("[2/4] Using existing recording.")

        if not processing:
            add_status_message("Paused. Click Resume to continue.")
            return

        add_status_message("")
        add_status_message("[3/4] Detecting track boundaries...")
        split_files = processor.split_by_silence(recording_file)
        add_status_message(f"Found {len(split_files)} track segments")

        if not processing:
            add_status_message("Paused. Click Resume to continue.")
            return

        add_status_message("")
        add_status_message("[4/4] Converting and organizing tracks...")
        processor.process_remaining_tracks(
            split_files,
            tracks,
            TARGET_BITRATE,
            add_status_message,
            should_stop=lambda: not processing,
        )

        if not processing:
            add_status_message("")
            add_status_message("Paused. Click Resume to continue.")
            return

        # Finished everything
        stats = progress_tracker.get_stats()
        add_status_message("")
        add_status_message("=" * 70)
        add_status_message("PROCESSING COMPLETE")
        add_status_message("=" * 70)
        add_status_message(f"Processed {stats['completed']} tracks")
        if stats['failed'] > 0:
            add_status_message(f"Failed: {stats['failed']} tracks (see progress.json)")
        add_status_message(f"Saved to: {output_dir}")

        processor.cleanup_temp_files(keep_splits=False)
        progress_tracker.complete_session()

    except Exception as e:
        add_status_message("")
        add_status_message(f"ERROR: {e}")
        logger.exception("Processing failed")

    finally:
        processing = False


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    DJ_LIBRARY_PATH.mkdir(parents=True, exist_ok=True)
    TEMP_RECORDINGS_PATH.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("DJ Library Builder v2")
    print("=" * 70)
    print("Open http://127.0.0.1:5000 in your browser")
    print("Press Ctrl+C in this window to quit the app")
    print("=" * 70 + "\n")

    app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
