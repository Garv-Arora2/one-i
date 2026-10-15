"""YouTube Data API provider.

Collects public top-level comments posted under videos about an event. Only
videos whose title/description share the event's key words, and (when a
window is given) that were published around the event, are used. Each comment
keeps a link to itself and the name of the channel whose video it sits under;
commenter names are not stored.
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.analysis.textutils import content_tokens
from app.core.timeutil import as_utc, parse_iso
from app.ingestion.providers.base import ProviderError, RawReaction, ReactionProvider

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

SEARCH_RESULTS = 15
COMMENTS_PER_VIDEO = 100


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    title: str
    description: str
    channel: str | None
    published_at: datetime | None


class YouTubeProvider(ReactionProvider):
    name = "youtube"

    def __init__(self, api_key: str, timeout: float = 15.0, comment_videos: int = 3) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._comment_videos = comment_videos

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def configuration_hint(self) -> str:
        return "Configured." if self.is_configured() else "Set YOUTUBE_API_KEY to enable YouTube."

    def fetch_reactions(
        self,
        query: str,
        limit: int = 300,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        anchors: tuple[str, ...] = (),
    ) -> list[RawReaction]:
        if not self.is_configured() or not query.strip():
            return []
        params: dict[str, object] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "relevance",
            "relevanceLanguage": "en",
            "maxResults": SEARCH_RESULTS,
            "key": self._api_key,
        }
        if since is not None:
            params["publishedAfter"] = _rfc3339(since)
        if until is not None:
            params["publishedBefore"] = _rfc3339(until)
        reactions: list[RawReaction] = []
        try:
            with httpx.Client(timeout=self._timeout) as client:
                search = client.get(SEARCH_URL, params=params)
                self._raise_for_status(search)
                videos = [
                    video
                    for video in parse_youtube_videos(search.json())
                    if is_relevant_video(query, video, anchors)
                ][: self._comment_videos]
                for video in videos:
                    comments = client.get(
                        COMMENTS_URL,
                        params={
                            "part": "snippet",
                            "videoId": video.video_id,
                            "maxResults": COMMENTS_PER_VIDEO,
                            "order": "relevance",
                            "textFormat": "plainText",
                            "key": self._api_key,
                        },
                    )
                    if comments.status_code in (403, 404):
                        # Comments disabled or video unavailable: not an error.
                        continue
                    self._raise_for_status(comments)
                    reactions.extend(parse_youtube_comments(comments.json(), video))
        except httpx.HTTPError as error:
            raise ProviderError(f"YouTube request failed: {error}") from error
        return reactions[:limit]

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ProviderError("YouTube rate limit reached.")
        if response.status_code == 403 and "quota" in response.text.lower():
            raise ProviderError("YouTube daily quota used up; try again tomorrow.")
        if response.status_code >= 400:
            raise ProviderError(f"YouTube returned HTTP {response.status_code}.")


def _rfc3339(moment: datetime) -> str:
    return (as_utc(moment) or moment.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_relevant_video(query: str, video: YouTubeVideo, anchors: tuple[str, ...] = ()) -> bool:
    """True when the video's title/description carry the query's key words.

    YouTube search returns loosely related videos; a video counts when it
    shares two query words, or names every proper noun in the query ("Ebola"
    for "Ebola epidemic"). With anchors (names that pin a broad, ongoing topic
    to this event), it must also mention one of them.
    """
    wanted = set(content_tokens(query))
    if not wanted:
        return False
    found = set(content_tokens(f"{video.title} {video.description}"))
    if anchors and not any(set(content_tokens(anchor)) <= found for anchor in anchors):
        return False
    proper = {
        token
        for word in query.split()
        if word[:1].isupper()
        for token in content_tokens(word)
    }
    return len(wanted & found) >= min(2, len(wanted)) or bool(proper and proper <= found)


def parse_youtube_videos(payload: dict) -> list[YouTubeVideo]:
    videos: list[YouTubeVideo] = []
    for item in (payload or {}).get("items") or []:
        video_id = ((item or {}).get("id") or {}).get("videoId")
        snippet = (item or {}).get("snippet") or {}
        title = html.unescape(snippet.get("title") or "").strip()
        if not video_id or not title:
            continue
        videos.append(
            YouTubeVideo(
                video_id=str(video_id),
                title=title,
                description=html.unescape(snippet.get("description") or "").strip(),
                channel=snippet.get("channelTitle") or None,
                published_at=parse_iso(snippet.get("publishedAt")),
            )
        )
    return videos


def parse_youtube_comments(payload: dict, video: YouTubeVideo) -> list[RawReaction]:
    reactions: list[RawReaction] = []
    for item in (payload or {}).get("items") or []:
        comment = (
            ((item or {}).get("snippet") or {}).get("topLevelComment") or {}
        ).get("snippet") or {}
        identifier = (item or {}).get("id")
        text = (comment.get("textOriginal") or comment.get("textDisplay") or "").strip()
        if not identifier or not text:
            continue
        reactions.append(
            RawReaction(
                platform="youtube",
                external_id=str(identifier),
                content=text[:2000],
                published_at=parse_iso(comment.get("publishedAt")),
                engagement=int(comment.get("likeCount") or 0),
                url=f"https://www.youtube.com/watch?v={video.video_id}&lc={identifier}",
                community=(video.channel or "")[:200] or None,
                provider="youtube",
            )
        )
    return reactions
