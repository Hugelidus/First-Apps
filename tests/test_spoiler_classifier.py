"""Tests del spoiler classifier.

- Test de parsing y caché en disco con un cliente mockeado.
- Test de fixtures contra clasificador real (skip si no hay API key).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from src.ingest.spoiler_classifier import (
    SpoilerClassifier,
    SpoilerLabel,
    _parse_response,
)


class _StubBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _StubResponse:
    def __init__(self, text: str) -> None:
        self.content = [_StubBlock(text)]


class _StubMessages:
    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _StubResponse(self._text)


class _StubClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _StubMessages(response_text)


def test_parse_respuesta_valida():
    raw = '{"level": 1, "confidence": 0.85, "reasoning": "menciona personaje secundario"}'
    label = _parse_response(raw)
    assert label.level == 1
    assert label.confidence == pytest.approx(0.85)
    assert "personaje" in label.reasoning


def test_parse_respuesta_con_texto_alrededor():
    raw = 'Aquí va: {"level": 2, "confidence": 0.9, "reasoning": "spoiler final"} fin.'
    label = _parse_response(raw)
    assert label.level == 2


def test_parse_respuesta_invalida_devuelve_nivel_2_conservador():
    label = _parse_response("no hay json aquí")
    assert label.level == 2
    assert label.confidence == 0.0


def test_classifier_cachea_por_hash(tmp_path: Path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(
        "src.ingest.spoiler_classifier.CACHE_PATH", cache_path
    )
    monkeypatch.setattr(
        "src.ingest.spoiler_classifier.BORDERLINE_PATH",
        tmp_path / "borderline.jsonl",
    )
    stub = _StubClient('{"level": 0, "confidence": 0.95, "reasoning": "premisa"}')
    cls = SpoilerClassifier(client=stub, model="claude-haiku-4-5-20251001", cache_path=cache_path)
    label1 = cls.classify("Texto cualquiera")
    label2 = cls.classify("Texto cualquiera")
    assert label1.level == 0
    assert label1 == label2
    # Solo se llamó al modelo una vez (segunda fue caché).
    assert len(stub.messages.calls) == 1
    saved = json.loads(cache_path.read_text())
    assert len(saved) == 1


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requiere ANTHROPIC_API_KEY para llamar al clasificador real",
)
def test_clasificador_real_acierta_fixtures(tmp_path: Path, monkeypatch):
    """Acepta hasta 2 fallos de 10 (margen para borderline)."""
    monkeypatch.setattr("src.ingest.spoiler_classifier.CACHE_PATH", tmp_path / "c.json")
    monkeypatch.setattr(
        "src.ingest.spoiler_classifier.BORDERLINE_PATH", tmp_path / "b.jsonl"
    )
    fixtures = json.loads(
        Path("tests/fixtures/spoiler_chunks.json").read_text(encoding="utf-8")
    )
    cls = SpoilerClassifier()
    fails = 0
    for fx in fixtures:
        label: SpoilerLabel = cls.classify(fx["text"])
        if label.level != fx["expected_level"]:
            fails += 1
    assert fails <= 2, f"clasificador falló en {fails}/{len(fixtures)} fixtures"
