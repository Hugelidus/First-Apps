"""Cliente HTTP base para scraping responsable.

- Rate limit por host (default 1 req/s).
- Comprobación de robots.txt antes de cada GET.
- User-Agent identificable.
- Caché en disco bajo ``data/raw/_cache/`` indexada por hash de URL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from src.config import RAW_DIR, get_settings

logger = logging.getLogger(__name__)

CACHE_DIR = RAW_DIR / "_cache"


@dataclass
class FetchResult:
    """Respuesta cacheable de un GET."""

    url: str
    status: int
    headers: dict[str, str]
    text: str

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status": self.status,
            "headers": self.headers,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FetchResult":
        return cls(url=d["url"], status=d["status"], headers=d["headers"], text=d["text"])


class _RateLimiter:
    """Limitador por host: garantiza ``min_interval`` segundos entre peticiones."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            delta = now - last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last[host] = time.monotonic()


class HttpClient:
    """Cliente con rate limit, robots.txt y caché en disco."""

    def __init__(
        self,
        user_agent: str | None = None,
        rate_per_host: float | None = None,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        cfg = get_settings()
        self.user_agent = user_agent or cfg.http_user_agent
        rate = rate_per_host or cfg.http_rate_limit_per_host
        # ``rate`` es peticiones por segundo → intervalo mínimo en s.
        self._limiter = _RateLimiter(min_interval=1.0 / max(rate, 0.01))
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- robots.txt ---

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                self._limiter.wait(parsed.netloc)
                resp = self._client.get(f"{base}/robots.txt")
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # Sin robots.txt accesible: permitimos por defecto.
                    rp.parse(["User-agent: *", "Allow: /"])
            except httpx.HTTPError as e:
                logger.warning("No se pudo leer robots.txt de %s: %s", base, e)
                rp.parse(["User-agent: *", "Allow: /"])
            self._robots[base] = rp
        return self._robots[base]

    def can_fetch(self, url: str) -> bool:
        """True si robots.txt permite que nuestro UA acceda a ``url``."""
        return self._robots_for(url).can_fetch(self.user_agent, url)

    # --- caché ---

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{h}.json"

    def _read_cache(self, url: str) -> FetchResult | None:
        p = self._cache_path(url)
        if not p.exists():
            return None
        try:
            return FetchResult.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Caché corrupta en %s: %s", p, e)
            return None

    def _write_cache(self, result: FetchResult) -> None:
        p = self._cache_path(result.url)
        p.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- fetch ---

    def get(self, url: str, *, force: bool = False) -> FetchResult:
        """GET con caché, rate limit y respeto de robots.txt.

        Lanza ``PermissionError`` si robots.txt prohíbe el path.
        """
        if not force:
            cached = self._read_cache(url)
            if cached is not None:
                logger.debug("Caché hit: %s", url)
                return cached

        if not self.can_fetch(url):
            raise PermissionError(f"robots.txt prohíbe acceder a {url}")

        host = urlparse(url).netloc
        self._limiter.wait(host)
        logger.info("GET %s", url)
        resp = self._client.get(url)
        result = FetchResult(
            url=str(resp.url),
            status=resp.status_code,
            headers=dict(resp.headers),
            text=resp.text,
        )
        if 200 <= resp.status_code < 300:
            self._write_cache(result)
        else:
            logger.warning("GET %s → %s", url, resp.status_code)
            resp.raise_for_status()
        return result
