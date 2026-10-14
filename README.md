# DJ Library Builder v2 - With Checkpoint/Resume Support

Simple macOS app to build a 320 kbps DJ library from Apple Music playlists with the ability to pause and resume anytime.

## What It Does

1. **Scrapes** your Apple Music playlist
2. **Records** Apple Music playback in lossless quality
3. **Detects** track boundaries automatically
4. **Splits** the continuous recording into individual tracks
5. **Transcodes** each track to 320 kbps MP3
6. **Tags** with artist, album, title metadata
7. **Organizes** into `~/Music/DJ-Library/Artist/Album/Track.mp3`

**NEW:** Saves progress at every step. Stop anytime, resume where you left off!

---

## Key Features

### ✅ Checkpoint System
- Automatically saves progress after each track
- Remembers which tracks are done
- Can stop and resume anytime

### ✅ Skip Completed Tracks
- If you resume, it won't re-process tracks you already completed
- Only processes tracks that still need work

### ✅ Graceful Stop
- Click "STOP" to pause processing
- Your session is saved
- Resume button appears when you restart the app

### ✅ Batch Processing
- Process one playlist, then another
- Each session saved separately
- Clear old sessions anytime

---

## Prerequisites

### Required Software

1. **Python 3.8+**
2. **ffmpeg** - audio processing
3. **ffprobe** - included with ffmpeg
4. **BlackHole** - virtual audio device

### Install BlackHole

```bash
brew install blackhole-2ch
```

### Install ffmpeg

```bash
brew install ffmpeg
```

---

## Installation

### Quick Setup (5 minutes)

```bash
cd ~/Downloads/dj_app_v2/
bash setup.sh
```

---

## Usage

### Start the App

```bash
cd ~/Downloads/dj_app_v2/
python3 dj_library_builder.py
```

### First Time: Start a New Session

1. Paste Apple Music playlist URL
2. Click **"START NEW SESSION"**
3. Follow on-screen instructions
4. Let it run

### Next Time: Resume Where You Left Off

1. App detects previous session
2. Shows resumable session info
3. Click **"RESUME SESSION"**
4. Continues processing remaining tracks

### Stop Anytime

Click **"STOP"** to pause processing. Your progress is saved.

When you restart the app and click "RESUME SESSION", it picks up right where it stopped.

---

## What Happens When You Stop?

### You Click "STOP"
- Processing halts immediately
- Current track might not be completed
- All progress so far is saved

### You Restart the App
- App shows "Found resumable session"
- Shows how many tracks are done
- Click "RESUME SESSION"
- Continues from where you stopped

### Already-Completed Tracks
- Skipped automatically
- Won't be re-processed
- Saves time on resume

---

## Example Workflow

**Day 1 (Evening):**
- Start recording at 6 PM
- Run for 4 hours (recording happens in background)
- Stop processing for the night
- Progress saved: 67/300 tracks

**Day 2 (Morning):**
- Open app
- Click "RESUME SESSION"
- Continues from track 68
- Finishes remaining 233 tracks
- Takes ~4 more hours
- Done by afternoon!

No need to re-record or re-process what you already did.

---

## Progress Tracking

### Session Directory

Each session saves to:
```
~/.dj_builder_cache/sessions/YYYYMMDD_HHMMSS/
  progress.json          - Current session state
  recording.wav          - Full audio recording
  track_001.wav          - Split audio files
  playlist_metadata.json - Track information
```

### Progress File

Shows:
- How many tracks completed
- How many failed
- Current phase (recording, processing, done)
- Original playlist URL

### View Progress

Open the Terminal during processing:
```bash
tail -f ~/.dj_builder_cache/sessions/*/progress.json
```

Or just check the app UI - it updates in real-time.

---

## Clear Old Sessions

To delete old sessions and free up space:

```bash
rm -rf ~/.dj_builder_cache/sessions/*
```

Or click "Clear Session" in the app.

---

## Troubleshooting

### "No resumable session found"
- Check `~/.dj_builder_cache/sessions/`
- Make sure previous session didn't complete (check progress.json)
- Sessions are only resumable if `current_phase` is NOT `done`

### Processing skips my tracks
- This is correct! Already-completed tracks are skipped
- Check the status log - it says "Skipping already-processed track"
- This saves time on resume

### "Out of disk space"
Clean up old sessions:
```bash
rm -rf ~/.dj_builder_cache/sessions/OLD_SESSION_DATE/
```

Each session uses ~5-10 GB (recording + temporary files)

### Recording file missing
- If recording.wav is deleted, you'll need to re-record
- But all processed tracks are already in `~/Music/DJ-Library/`
- Just start a new session

---

## File Structure

```
~/.dj_builder_cache/
  sessions/
    20240101_120000/
      progress.json
      recording.wav
      track_001.wav
      track_002.wav
      playlist_metadata.json
    20240102_140000/
      [another session...]

~/Music/DJ-Library/
  Artist A/
    Album 1/
      Track 1.mp3
      Track 2.mp3
  Artist B/
    Album 2/
      Track 3.mp3
```

---

## Technical Details

### Checkpoint Logic

After each track processed:
1. Add track index to `completed_tracks` list
2. Save to `progress.json`
3. Skip this track on resume

### Recovery

If app crashes:
- Restart the app
- Click "RESUME SESSION"
- Picks up from last checkpoint

### Cleanup

Final cleanup (after all tracks done):
- Delete temporary split WAV files (keeps recording.wav as backup)
- Mark session as `complete`
- Keep progress.json for reference

---

## Performance

### Timeline for 300 Tracks

**Recording:** 24 hours (real-time playback)
**Processing (first run):** 6-8 hours
**Processing (after stop/resume):** Only remaining tracks

**Example:**
- Start: 6 PM Monday
- Stop: 10 PM Monday (4 hours recorded = ~67 tracks)
- Session saved ✓
- Resume: 8 AM Tuesday
- Finish: 2 PM Tuesday (remaining 233 tracks)
- Total wall-clock: 20 hours across 2 days
- CPU time:  ~10 hours actual processing

---

## Questions?

Check `progress.json` in your session directory for detailed state.

Good luck! 🎵
