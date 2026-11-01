"""Polite, cached page fetching for scripts.import_catalog.

Follows each site's robots.txt, waits SECONDS_BETWEEN_REQUESTS between requests
to the same site, and names the project in its User-Agent (like check_offers).
Pages are cached gzipped in backend/.crawl-cache/, keyed by the SHA-1 of the URL,
so a rerun reads them from disk instead of asking the store again.
"""

import gzip
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

USER_AGENT = "PC-Configurator-student-project/0.1 (+https://github.com/CsDevJs/PC-Configurator)"
SECONDS_BETWEEN_REQUESTS = 2.0
CACHE = Path(__file__).resolve().parent.parent / ".crawl-cache"


class Robots:
    """robots.txt rules for "User-agent: *", with the * and $ wildcards that most stores use
    (urllib.robotparser ignores them). The longest matching rule wins; Allow wins a tie."""

    def __init__(self, text: str):
        self.rules: list[tuple[int, bool, re.Pattern]] = []
        agents, in_rules, mine = [], False, False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if in_rules:
                    agents, in_rules = [], False
                agents.append(value)
                mine = "*" in agents
            elif key in ("allow", "disallow"):
                in_rules = True
                if mine and value:
                    pattern = re.escape(value).replace(r"\*", ".*")
                    pattern = pattern[:-2] + "$" if pattern.endswith(r"\$") else pattern
                    self.rules.append((len(value), key == "allow", re.compile(pattern)))

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best = (-1, True)
        for length, allow, pattern in self.rules:
            if pattern.match(path) and (length, allow) > best:
                best = (length, allow)
        return best[1]


class Fetcher:
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
        self.robots: dict[str, Robots] = {}
        self.last: dict[str, float] = {}
        CACHE.mkdir(exist_ok=True)

    def close(self):
        self.client.close()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        site = f"{parts.scheme}://{parts.netloc}"
        if site not in self.robots:
            try:
                response = self.client.get(f"{site}/robots.txt")
                # No robots.txt means everything is allowed. Darwin serves its rules with HTTP 404,
                # so the text is used whenever it has rules.
                has_rules = response.status_code == 200 or "user-agent" in response.text.lower()
                self.robots[site] = Robots(response.text if has_rules else "")
            except httpx.HTTPError:
                self.robots[site] = Robots("")
        return self.robots[site].allowed(url)

    def get(self, url: str) -> str | None:
        """The page's HTML, or None if robots.txt forbids it or it doesn't load (after one retry)."""
        path = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.html.gz"
        if self.use_cache and path.exists():
            return gzip.decompress(path.read_bytes()).decode("utf-8", "replace")
        if not self._allowed(url):
            return None
        host = urlsplit(url).netloc
        for attempt in range(2):
            wait = SECONDS_BETWEEN_REQUESTS - (time.monotonic() - self.last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.monotonic()
            try:
                response = self.client.get(url)
            except httpx.HTTPError:
                continue
            if response.status_code == 200:
                path.write_bytes(gzip.compress(response.content))
                return response.text
            if response.status_code < 500:
                return None
        return None
