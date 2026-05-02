"""Tests del CLI con typer.testing."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli import app


runner = CliRunner()


def test_info_falla_si_no_hay_chunks(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("src.cli.load_processed_chunks", lambda: [])
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 1
    assert "no existe" in result.stdout or "vacío" in result.stdout


def test_info_imprime_resumen(monkeypatch):
    from src.ingest.pipeline import ProcessedChunk

    fakes = [
        ProcessedChunk(
            chunk_id=f"id{i}",
            text="x",
            fuente="wikipedia_pelicula" if i < 2 else "letterboxd",
            url="",
            n_tokens=1,
            tier=1 if i < 2 else 3,
            origen_canon="pelicula",
            spoiler_level=i % 3,
            spoiler_confidence=1.0,
            spoiler_reasoning="",
        )
        for i in range(3)
    ]
    monkeypatch.setattr("src.cli.load_processed_chunks", lambda: fakes)
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Total chunks: 3" in result.stdout
    assert "wikipedia_pelicula=2" in result.stdout
    assert "letterboxd=1" in result.stdout


def test_export_no_se_a_archivo(monkeypatch, tmp_path: Path):
    log = tmp_path / "ns.jsonl"
    log.write_text(
        json.dumps({"timestamp": "t", "modo": "pre_cine", "query": "Sara", "answer": "x"})
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("src.chat.session.DEFAULT_NO_SE_PATH", log)

    out = tmp_path / "out.json"
    result = runner.invoke(app, ["export-no-se", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    data = json.loads(out.read_text())
    assert data[0]["query"] == "Sara"


def test_chat_falla_sin_chunks(monkeypatch):
    monkeypatch.setattr("src.cli.load_processed_chunks", lambda: [])
    result = runner.invoke(app, ["chat"])
    assert result.exit_code == 3
    assert "vacío" in result.stdout
