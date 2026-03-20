"""
youtube_service.py – YouTube Data API v3 wrapper for PathForge.

Used to dynamically discover real, working course URLs for skills
not covered by the static course catalog (orphan gaps).

API Quota: Free tier gives 10,000 units/day.
  - search.list = 100 units/call
  - We batch search queries → ≤ 1 call per orphan skill per user session.

If YOUTUBE_API_KEY is not set, the service degrades gracefully and returns
a curated Google search URL instead (still functional, just not pre-verified).
"""

from __future__ import annotations

import asyncio
import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# YouTube Data API v3 endpoint
_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
_PLAYLIST_ENDPOINT = "https://www.googleapis.com/youtube/v3/playlists"

# Safe educational channel IDs to prefer results from (optional boost)
_EDU_CHANNELS = {
    "UCCTVrRjMtFkrFID-xuXb1KA",  # freeCodeCamp
    "UCWv7vMbMWH4-V0ZXdmDpPBA",  # Programming with Mosh
    "UCnUYZLuoy1rq1aVMwx4aTzw",  # Traversy Media
    "UC8butISFwT-Wl7EV0hUK0BQ",  # freeCodeCamp (alt)
    "UCWX3yGbODI3BHVjmMHMFGiA",  # Corey Schafer
}


class YouTubeService:
    """
    Thin async wrapper around YouTube Data API v3.
    Falls back to a Google Search URL if the API key is missing.
    """

    def __init__(self) -> None:
        self._api_key: Optional[str] = os.getenv("YOUTUBE_API_KEY")
        if not self._api_key:
            logger.warning(
                "YOUTUBE_API_KEY not set. Dynamic discovery will use Google Search fallback."
            )

    async def search_course(
        self,
        skill_name: str,
        skill_id: str,
        max_results: int = 3,
    ) -> Dict[str, Any]:
        """
        Search YouTube for the best free course/tutorial for a given skill.

        Returns a dict with:
            url       – direct YouTube or Google search URL
            title     – video/playlist title
            verified  – True if fetched from YouTube API, False if fallback
        """
        if self._api_key:
            return await self._search_youtube(skill_name, skill_id, max_results)
        return self._google_search_fallback(skill_name, skill_id)

    async def _search_youtube(
        self,
        skill_name: str,
        skill_id: str,
        max_results: int,
    ) -> Dict[str, Any]:
        """Call YouTube Data API and return the best result."""
        query = f"{skill_name} full course free tutorial"

        params = {
            "part": "snippet",
            "q": query,
            "type": "playlist",           # prefer playlists (multi-video courses)
            "maxResults": max_results,
            "relevanceLanguage": "en",
            "safeSearch": "strict",
            "videoDuration": "long",       # we want full courses not 3-min snippets
            "key": self._api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(_SEARCH_ENDPOINT, params=params)
                resp.raise_for_status()
                data = resp.json()

            items: List[Dict] = data.get("items", [])
            if not items:
                logger.warning("YouTube API returned 0 results for skill '%s'", skill_id)
                return self._google_search_fallback(skill_name, skill_id)

            # Pick first result (most relevant by YouTube ranking)
            best = items[0]
            snippet = best.get("snippet", {})
            video_id = best.get("id", {})

            if video_id.get("kind") == "youtube#playlist":
                playlist_id = video_id.get("playlistId", "")
                url = f"https://www.youtube.com/playlist?list={playlist_id}"
            else:
                vid_id = video_id.get("videoId", "")
                url = f"https://www.youtube.com/watch?v={vid_id}"

            title = snippet.get("title", f"{skill_name} Tutorial")
            channel = snippet.get("channelTitle", "YouTube")

            logger.info(
                "YouTube API found course for '%s': %s (%s)",
                skill_id, title, url
            )
            return {
                "url": url,
                "title": title,
                "provider": f"{channel} (YouTube)",
                "verified": True,
                "source": "youtube_api",
            }

        except httpx.HTTPStatusError as exc:
            logger.error(
                "YouTube API HTTP error for skill '%s': %s", skill_id, exc
            )
            return self._google_search_fallback(skill_name, skill_id)
        except Exception as exc:
            logger.error(
                "YouTube API unexpected error for skill '%s': %s", skill_id, exc
            )
            return self._google_search_fallback(skill_name, skill_id)

    def _google_search_fallback(
        self,
        skill_name: str,
        skill_id: str,
    ) -> Dict[str, Any]:
        """
        Construct a Google Site:YouTube search URL – always works, always fresh.
        User clicks through to real YouTube results for this skill.
        """
        query = urllib.parse.quote_plus(
            f"{skill_name} free course tutorial site:youtube.com"
        )
        url = f"https://www.google.com/search?q={query}"
        logger.info(
            "Using Google Search fallback for skill '%s': %s", skill_id, url
        )
        return {
            "url": url,
            "title": f"Search: {skill_name} Free Course",
            "provider": "Google Search (Dynamic)",
            "verified": False,
            "source": "google_fallback",
        }

    async def batch_search(
        self,
        skills: Dict[str, str],  # {skill_id: skill_name}
        delay_between_calls: float = 0.3,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Search for multiple skills with a small delay to respect API rate limits.
        Returns {skill_id: course_result_dict}
        """
        results: Dict[str, Dict[str, Any]] = {}
        for skill_id, skill_name in skills.items():
            result = await self.search_course(skill_name, skill_id)
            results[skill_id] = result
            if delay_between_calls > 0:
                await asyncio.sleep(delay_between_calls)
        return results
