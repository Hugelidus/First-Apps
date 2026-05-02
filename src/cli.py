"""CLI de CinemaIA: chat interactivo + comandos auxiliares."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from src.config import setup_logging
from src.chat.engine import ChatEngine
from src.chat.session import Modo, Session
from src.ingest.pipeline import load_processed_chunks
from src.retrieval.retriever import HybridRetriever

app = typer.Typer(
    name="cinemaia",
    help="Chat sobre 'Kraken. El libro negro de las horas' (MVP1).",
    no_args_is_help=True,
    add_completion=False,
)

logger = logging.getLogger(__name__)

HELP = """\
Comandos durante el chat:
  :modo pre|durante|post   Cambia el nivel de spoiler.
  :debug on|off            Muestra los chunks recuperados con tier/spoiler.
  :nose                    Vuelca el log de preguntas sin respuesta.
  :ayuda                   Muestra esta ayuda.
  :salir                   Termina la sesión (también Ctrl-D).
"""

_MODOS_ALIAS: dict[str, Modo] = {
    "pre": "pre_cine",
    "pre_cine": "pre_cine",
    "durante": "durante",
    "post": "post_cine",
    "post_cine": "post_cine",
}


def _print(msg: str) -> None:
    typer.echo(msg)


def _format_chunks(chunks) -> str:
    if not chunks:
        return "  (sin chunks recuperados)"
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(
            f"  [{i}] tier={c.tier} spoiler={c.spoiler_level} "
            f"canon={c.origen_canon} fuente={c.fuente} "
            f"bm25={c.bm25_score:.2f} dense={c.dense_score:.2f}"
        )
        snippet = c.text.replace("\n", " ")
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        lines.append(f"      {snippet}")
    return "\n".join(lines)


@app.command()
def chat(
    modo: str = typer.Option(
        "pre",
        "--modo",
        "-m",
        help="Nivel de spoiler inicial: pre, durante o post.",
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Muestra chunks recuperados en cada turno."
    ),
) -> None:
    """Abre el chat interactivo."""
    setup_logging()
    if modo not in _MODOS_ALIAS:
        _print(f"Modo inválido: {modo}. Usa pre, durante o post.")
        raise typer.Exit(code=2)
    session = Session(modo=_MODOS_ALIAS[modo])

    chunks = load_processed_chunks()
    if not chunks:
        _print(
            "⚠️  data/processed/chunks.jsonl está vacío. "
            "Ejecuta 'uv run python scripts/seed_kraken.py' antes."
        )
        raise typer.Exit(code=3)

    retriever = HybridRetriever(chunks=chunks)
    try:
        engine = ChatEngine(retriever=retriever)
    except Exception as e:  # noqa: BLE001
        _print(f"No se pudo inicializar el cliente Anthropic: {e}")
        _print("Comprueba que ANTHROPIC_API_KEY está en .env.")
        raise typer.Exit(code=4) from e

    _print(f"CinemaIA ▸ Kraken. Modo: {session.modo}. Comandos con ':'. Ctrl-D para salir.")
    if debug:
        _print("(modo debug activado)")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            _print("\nHasta otra.")
            return

        if not line:
            continue

        if line.startswith(":"):
            if not _handle_command(line, session, debug_holder=[debug]):
                return
            # Refrescar debug si cambió.
            continue

        try:
            ans = engine.answer(line, session)
        except Exception as e:  # noqa: BLE001
            _print(f"Error llamando al modelo: {e}")
            continue
        _print(ans.text)
        if debug:
            _print("\n[debug] chunks recuperados:")
            _print(_format_chunks(ans.retrieved))


def _handle_command(line: str, session: Session, *, debug_holder: list[bool]) -> bool:
    """Procesa un comando ':...'. Devuelve False si la sesión debe terminar."""
    parts = line[1:].split()
    if not parts:
        _print(HELP)
        return True
    cmd, args = parts[0].lower(), parts[1:]

    if cmd in ("salir", "quit", "exit"):
        _print("Hasta otra.")
        return False

    if cmd in ("ayuda", "help", "?"):
        _print(HELP)
        return True

    if cmd == "modo":
        if not args or args[0] not in _MODOS_ALIAS:
            _print("Uso: :modo pre|durante|post")
            return True
        session.set_modo(_MODOS_ALIAS[args[0]])
        _print(f"Modo: {session.modo}")
        return True

    if cmd == "debug":
        if not args or args[0] not in ("on", "off"):
            _print("Uso: :debug on|off")
            return True
        debug_holder[0] = args[0] == "on"
        _print(f"Debug: {'on' if debug_holder[0] else 'off'}")
        return True

    if cmd == "nose":
        records = session.read_no_se_log()
        if not records:
            _print("(no hay preguntas registradas como 'no sé')")
            return True
        _print(f"{len(records)} preguntas sin respuesta:")
        for r in records[-20:]:
            _print(f"  [{r.get('modo')}] {r.get('query')}")
        return True

    _print(f"Comando desconocido: :{cmd}. Escribe :ayuda para ver opciones.")
    return True


@app.command()
def info() -> None:
    """Muestra el estado del corpus procesado."""
    chunks = load_processed_chunks()
    if not chunks:
        _print("data/processed/chunks.jsonl no existe o está vacío.")
        raise typer.Exit(code=1)

    by_fuente: dict[str, int] = {}
    by_spoiler: dict[int, int] = {0: 0, 1: 0, 2: 0}
    by_canon: dict[str, int] = {}
    by_tier: dict[int, int] = {}
    for c in chunks:
        by_fuente[c.fuente] = by_fuente.get(c.fuente, 0) + 1
        by_spoiler[c.spoiler_level] = by_spoiler.get(c.spoiler_level, 0) + 1
        by_canon[c.origen_canon] = by_canon.get(c.origen_canon, 0) + 1
        by_tier[c.tier] = by_tier.get(c.tier, 0) + 1

    _print(f"Total chunks: {len(chunks)}")
    _print("Por fuente:    " + ", ".join(f"{k}={v}" for k, v in sorted(by_fuente.items())))
    _print("Por tier:      " + ", ".join(f"t{k}={v}" for k, v in sorted(by_tier.items())))
    _print("Por spoiler:   " + ", ".join(f"s{k}={v}" for k, v in sorted(by_spoiler.items())))
    _print("Por canon:     " + ", ".join(f"{k}={v}" for k, v in sorted(by_canon.items())))


@app.command()
def export_no_se(
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Ruta de salida"),
) -> None:
    """Exporta el log completo de preguntas sin respuesta como JSON."""
    sess = Session()
    records = sess.read_no_se_log()
    payload = json.dumps(records, ensure_ascii=False, indent=2)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        _print(f"Escritos {len(records)} registros en {out}")
    else:
        sys.stdout.write(payload + "\n")


if __name__ == "__main__":
    app()
