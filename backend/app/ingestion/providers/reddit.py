"""Reddit provider (public search through the official API).

Only public post text, score, community and permalink are read. No account
level data is collected and no inference about accounts is made.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.ingestion.providers.base import ProviderError, RawReaction, ReactionProvider

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"


class RedditProvider(ReactionProvider):
    name = "reddit"

    def __init__(
        self, client_id: str, client_secret: str, user_agent: str, timeout: float = 15.0
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def configuration_hint(self) -> str:
        if self.is_configured():
            return "Configured."
        return "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to enable Reddit."

    def _access_token(self, client: httpx.Client) -> str:
        response = client.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
            headers={"User-Agent": self._user_agent},
        )
        if response.status_code != 200:
            raise ProviderError(f"Reddit authentication failed (HTTP {response.status_code}).")
        token = response.json().get("access_token")
        if not token:
            raise ProviderError("Reddit did not return an access token.")
        return str(token)

    def fetch_reactions(
        self,
        query: str,
        limit: int = 50,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        anchors: tuple[str, ...] = (),
    ) -> list[RawReaction]:
        _ = since, until, anchors  # Reddit search has no date-range parameter
        if not self.is_configured():
            return []
        try:
            with httpx.Client(timeout=self._timeout) as client:
                token = self._access_token(client)
                response = client.get(
                    SEARCH_URL,
                    params={"q": query, "limit": min(limit, 100), "sort": "relevance", "type": "link"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "User-Agent": self._user_agent,
                    },
                )
        except httpx.HTTPError as error:
            raise ProviderError(f"Reddit request failed: {error}") from error

        if response.status_code == 429:
            raise ProviderError("Reddit rate limit reached.")
        if response.status_code >= 400:
            raise ProviderError(f"Reddit returned HTTP {response.status_code}.")
        return parse_reddit_payload(response.json())


def parse_reddit_payload(payload: dict) -> list[RawReaction]:
    children = ((payload or {}).get("data") or {}).get("children") or []
    reactions: list[RawReaction] = []
    for child in children:
        data = (child or {}).get("data") or {}
        identifier = data.get("id")
        title = (data.get("title") or "").strip()
        if not identifier or not title:
            continue
        body = (data.get("selftext") or "").strip()
        created = data.get("created_utc")
        published = (
            datetime.fromtimestamp(float(created), tz=timezone.utc) if created else None
        )
        permalink = data.get("permalink")
        reactions.append(
            RawReaction(
                platform="reddit",
                external_id=str(identifier),
                content=f"{title}\n{body}".strip(),
                published_at=published,
                engagement=int(data.get("score") or 0),
                url=f"https://www.reddit.com{permalink}" if permalink else None,
                community=data.get("subreddit_name_prefixed") or data.get("subreddit"),
                provider="reddit",
            )
        )
    return reactions
