"""Tests de la sesión de chat."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.chat.session import Session


def test_set_modo_valido_e_invalido(tmp_path: Path):
    s = Session(no_se_log_path=tmp_path / "ns.jsonl")
    assert s.modo == "pre_cine"
    s.set_modo("post_cine")
    assert s.modo == "post_cine"
    with pytest.raises(ValueError):
        s.set_modo("inventado")  # type: ignore[arg-type]


def test_append_turn_loguea_no_se(tmp_path: Path):
    log = tmp_path / "ns.jsonl"
    s = Session(no_se_log_path=log)
    s.append_turn(
        "¿Quién es Sara?",
        "No tengo registrado a Sara. Puede que el nombre esté distinto.",
    )
    assert log.exists()
    records = s.read_no_se_log()
    assert len(records) == 1
    assert records[0]["query"] == "¿Quién es Sara?"


def test_no_se_no_loguea_respuestas_normales(tmp_path: Path):
    log = tmp_path / "ns.jsonl"
    s = Session(no_se_log_path=log)
    s.append_turn("¿De qué va?", "Es un thriller policíaco.")
    assert not log.exists()


def test_render_last_n_alterna_roles(tmp_path: Path):
    s = Session(no_se_log_path=tmp_path / "ns.jsonl")
    s.append_turn("hola", "qué tal")
    s.append_turn("¿quién dirige?", "Sanabria y Llamas")
    out = s.render_last_n(4)
    assert out.count("USUARIO:") == 2
    assert out.count("CINEMAIA:") == 2
