"""Sesión de chat: nivel de spoiler, historial y log de "no sé"."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from src.config import DATA_DIR
from src.chat.prompts import NO_CHAR_MARKER, NO_INFO_MARKER

logger = logging.getLogger(__name__)

Modo = Literal["pre_cine", "durante", "post_cine"]
DEFAULT_NO_SE_PATH = DATA_DIR / "processed" / "no_se.jsonl"


@dataclass
class Turn:
    """Un turno de conversación."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Session:
    """Estado de la sesión de chat.

    - ``modo`` determina el nivel máximo de spoiler que se recupera.
    - ``history`` guarda los últimos turnos para inyectar en el prompt.
    - ``no_se_log_path`` es el archivo donde volcar preguntas sin respuesta.
    """

    modo: Modo = "pre_cine"
    history: list[Turn] = field(default_factory=list)
    no_se_log_path: Path = DEFAULT_NO_SE_PATH

    def set_modo(self, modo: Modo) -> None:
        """Cambia el modo sin perder historial."""
        if modo not in ("pre_cine", "durante", "post_cine"):
            raise ValueError(f"modo inválido: {modo}")
        prev = self.modo
        self.modo = modo
        logger.info("Modo cambiado: %s → %s", prev, modo)

    def append_turn(self, user_msg: str, assistant_msg: str) -> None:
        """Añade un turno completo (user + assistant) al historial."""
        self.history.append(Turn(role="user", content=user_msg))
        self.history.append(Turn(role="assistant", content=assistant_msg))
        if self._is_no_se(assistant_msg):
            self._log_no_se(user_msg, assistant_msg)

    def render_last_n(self, n: int = 6) -> str:
        """Renderiza los últimos n mensajes como texto plano para el system prompt."""
        if not self.history:
            return "(sin historial)"
        last = self.history[-n:]
        lines = []
        for t in last:
            tag = "USUARIO" if t.role == "user" else "CINEMAIA"
            lines.append(f"{tag}: {t.content}")
        return "\n".join(lines)

    @staticmethod
    def _is_no_se(text: str) -> bool:
        return NO_INFO_MARKER in text or NO_CHAR_MARKER in text

    def _log_no_se(self, query: str, answer: str) -> None:
        self.no_se_log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modo": self.modo,
            "query": query,
            "answer": answer,
        }
        with self.no_se_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("Pregunta sin respuesta logueada en %s", self.no_se_log_path)

    def read_no_se_log(self) -> list[dict]:
        """Lee el log y devuelve la lista de registros."""
        if not self.no_se_log_path.exists():
            return []
        out: list[dict] = []
        for line in self.no_se_log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
