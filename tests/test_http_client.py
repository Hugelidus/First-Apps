"""Tests del cliente HTTP base (rate limit, robots, caché)."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

from src.ingest.sources.base import HttpClient, _RateLimiter


def test_rate_limiter_respeta_intervalo():
    rl = _RateLimiter(min_interval=0.1)
    t0 = time.monotonic()
    rl.wait("ejemplo.com")
    rl.wait("ejemplo.com")
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.1, f"el segundo wait no esperó (elapsed={elapsed:.3f}s)"


def test_cliente_cachea_y_respeta_robots(tmp_path: Path, monkeypatch):
    calls = {"robots": 0, "page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            calls["robots"] += 1
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        calls["page"] += 1
        return httpx.Response(200, text="<html><body>hola</body></html>")

    transport = httpx.MockTransport(handler)
    client = HttpClient(rate_per_host=100.0, cache_dir=tmp_path)
    client._client = httpx.Client(  # noqa: SLF001
        headers={"User-Agent": client.user_agent},
        transport=transport,
        follow_redirects=True,
    )

    r1 = client.get("https://ejemplo.com/foo")
    r2 = client.get("https://ejemplo.com/foo")
    assert r1.text == r2.text == "<html><body>hola</body></html>"
    # Segundo GET sirve de caché → solo 1 hit de página y 1 de robots.
    assert calls["page"] == 1
    assert calls["robots"] == 1
    client.close()


def test_cliente_rechaza_si_robots_prohibe(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: /privado\n")
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    client = HttpClient(rate_per_host=100.0, cache_dir=tmp_path)
    client._client = httpx.Client(  # noqa: SLF001
        headers={"User-Agent": client.user_agent},
        transport=transport,
        follow_redirects=True,
    )
    with pytest.raises(PermissionError):
        client.get("https://ejemplo.com/privado/secreto")
    client.close()
