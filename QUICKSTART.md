# DJ Library Builder v2 - Quick Start Guide

## NEW: Stop & Resume Anytime

Unlike v1, v2 **saves progress after each track**. You can:
- Stop processing anytime
- Resume where you left off
- Skip already-completed tracks automatically
- Process in chunks across multiple days

---

## Installation (5 minutes)

### 1. Extract and Setup

```bash
cd ~/Downloads/dj_app_v2
bash setup.sh
```

Done!

---

## Usage: First Time

### 1. Start the App

```bash
cd ~/Downloads/dj_app_v2
python3 dj_library_builder.py
```

### 2. Paste Playlist URL

In Apple Music, right-click playlist → Copy Link → Paste into app

### 3. Click "START NEW SESSION"

App will say:
```
⚠️  Make sure Apple Music is open
   Select your playlist
   Press SPACE to start playing
```

### 4. Play Your Playlist

- Open Apple Music
- Go to the same playlist
- Press Play (or spacebar)
- Go back to Terminal
- Press Enter

App starts recording and processing automatically.

---

## Usage: Stopping & Resuming

### Stop Processing

Click **"STOP"** button anytime.

App will say:
```
⏸️  Processing stopped by user
Your progress has been saved. Click 'RESUME SESSION' to continue.
```

**Your progress is saved!** No re-recording needed.

### Resume Later

Close and reopen the app:

```bash
python3 dj_library_builder.py
```

App automatically detects your previous session and shows:
```
Found resumable session:
  Playlist: https://...
  Progress: 67/300 tracks
  Click 'RESUME SESSION' to continue
```

Click **"RESUME SESSION"** button.

It skips the 67 completed tracks and continues with the remaining 233.

---

## Example: Process in Chunks

**Monday 6 PM:** Start recording
```
Click "START NEW SESSION"
Let it run for 4 hours
Stop at 10 PM
Progress: 67/300 tracks done ✓
```

**Tuesday 8 AM:** Resume processing
```
App shows "Found resumable session"
Click "RESUME SESSION"
Process remaining 233 tracks
Done by 2 PM ✓
```

**Total time:** 20 hours across 2 days instead of 30 hours straight!

---

## What Gets Saved

When you stop, your app saves:
- Which tracks are completed
- Which tracks failed
- Current phase (recording/processing)
- Playlist metadata
- Audio recording file

So you can pause for hours, days, or weeks and come back anytime.

---

## Clear Old Sessions

When you're done with a session and want to delete it:

Click **"Clear Session"** button, or from Terminal:

```bash
rm -rf ~/.dj_builder_cache/sessions/20240101_120000/
```

(Replace with your session date/time)

---

## Troubleshooting

### Q: Will re-processing take longer?
**A:** No! Already-completed tracks are skipped automatically. Only remaining tracks are processed.

### Q: Can I process multiple playlists?
**A:** Yes! Each gets its own session. Old sessions stay saved.

### Q: What if the app crashes?
**A:** Your progress is still saved. Just click "RESUME SESSION" when you restart.

### Q: Where does it save?
**A:** `~/.dj_builder_cache/sessions/` and `~/Music/DJ-Library/`

### Q: How much disk space?
**A:** ~10 GB per session (recording + temp files + final tracks)

---

## That's It!

You now have a smart DJ library downloader that works in chunks.

Process overnight, resume in the morning, no lost progress!

🎵
