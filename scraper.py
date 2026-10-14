"""
Apple Music Playlist Scraper
Extracts track metadata from Apple Music playlist URLs.

The original version depended on a package ("apple-music-scraper") that is
not on PyPI. This version fetches the playlist page directly and reads the
track data Apple embeds in the page as JSON. If Apple changes the page
layout, scrape_playlist() raises a clear error instead of returning nothing.
"""
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


class PlaylistScraper:
    """Scrapes Apple Music playlists for track metadata"""

    def scrape_playlist(self, playlist_url: str) -> List[Dict]:
        """
        Scrape an Apple Music playlist page and return its tracks.

        Returns:
            List of normalized track dictionaries (position, title, artist,
            album, duration in seconds, url, id).

        Raises:
            RuntimeError: if the page can't be fetched or contains no tracks.
        """
        logger.info(f"Scraping playlist: {playlist_url}")
        html = self._fetch_html(playlist_url)
        blobs = self._extract_embedded_json(html)

        raw_songs: List[Dict] = []
        for blob in blobs:
            self._collect_songs(blob, raw_songs)

        tracks = self._normalize_all(raw_songs)
        if not tracks:
            raise RuntimeError(
                "No tracks found on that page. Make sure the playlist is public, "
                "or Apple may have changed its page layout."
            )

        logger.info(f"Successfully scraped {len(tracks)} tracks")
        return tracks

    # ------------------------------------------------------------------
    # Fetching and parsing
    # ------------------------------------------------------------------

    def _fetch_html(self, url: str) -> str:
        import requests

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            raise RuntimeError(f"Could not download playlist page: {e}")

    def _extract_embedded_json(self, html: str) -> List[object]:
        """Pull every JSON <script> block out of the page."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        blobs = []
        for script in soup.find_all("script"):
            script_type = (script.get("type") or "").lower()
            if script.get("id") == "serialized-server-data" or script_type in (
                "application/json",
                "application/ld+json",
            ):
                text = script.string or script.get_text() or ""
                if not text.strip():
                    continue
                try:
                    blobs.append(json.loads(text))
                except json.JSONDecodeError:
                    logger.debug("Skipping script block that is not valid JSON")
        return blobs

    def _collect_songs(self, obj, out: List[Dict]) -> None:
        """Recursively find song objects (anything carrying a duration)."""
        if isinstance(obj, dict):
            attrs = obj.get("attributes") if isinstance(obj.get("attributes"), dict) else obj
            if "durationInMillis" in attrs and ("name" in attrs or "title" in attrs):
                out.append(obj)
                return
            for value in obj.values():
                self._collect_songs(value, out)
        elif isinstance(obj, list):
            for value in obj:
                self._collect_songs(value, out)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_all(self, raw_songs: List[Dict]) -> List[Dict]:
        tracks: List[Dict] = []
        seen_ids = set()
        for raw in raw_songs:
            track = self._normalize_track(raw, len(tracks) + 1)
            if track is None:
                continue
            # The same song can appear more than once in embedded data; keep the first copy.
            if track["id"]:
                if track["id"] in seen_ids:
                    continue
                seen_ids.add(track["id"])
            tracks.append(track)
        # Re-number positions after de-duplication
        for i, t in enumerate(tracks, 1):
            t["position"] = i
        return tracks

    def _normalize_track(self, track: Dict, position: int) -> Optional[Dict]:
        try:
            attrs = track.get("attributes") if isinstance(track.get("attributes"), dict) else track
            duration_ms = attrs.get("durationInMillis") or 0
            return {
                "position": position,
                "title": attrs.get("name") or attrs.get("title") or "Unknown",
                "artist": attrs.get("artistName") or "Unknown",
                "album": attrs.get("albumName") or "Unknown",
                "duration": float(duration_ms) / 1000.0,
                "url": attrs.get("url") or "",
                "id": str(track.get("id") or ""),
            }
        except Exception as e:
            logger.warning(f"Failed to normalize track: {e}")
            return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_tracks_json(self, tracks: List[Dict], output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(tracks, f, indent=2)
        logger.info(f"Saved {len(tracks)} tracks to {output_path}")
