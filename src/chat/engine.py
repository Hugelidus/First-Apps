"""Motor de respuestas: monta el system prompt y llama a Claude."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from anthropic import Anthropic

from src.chat.prompts import SYSTEM_PROMPT, format_context
from src.chat.session import Session
from src.config import get_settings
from src.retrieval.retriever import HybridRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 800


@dataclass
class Answer:
    """Respuesta del motor con los chunks que se usaron."""

    text: str
    retrieved: list[RetrievedChunk]


class ChatEngine:
    """Orquesta retrieval + LLM."""

    def __init__(
        self,
        retriever: HybridRetriever,
        client: Anthropic | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        cfg = get_settings()
        self.retriever = retriever
        self.client = client or Anthropic(api_key=cfg.anthropic_api_key)
        self.model = model or cfg.chat_model
        self.max_tokens = max_tokens

    def answer(self, query: str, session: Session) -> Answer:
        """Recupera contexto, construye prompt y devuelve la respuesta."""
        chunks = self.retriever.search(query, modo=session.modo)
        system = SYSTEM_PROMPT.format(
            spoiler_level=session.modo,
            retrieved_context=format_context(chunks),
            historial=session.render_last_n(6),
        )
        logger.debug(
            "Llamando a %s con %d chunks recuperados (modo=%s)",
            self.model,
            len(chunks),
            session.modo,
        )
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": query}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()
        session.append_turn(query, text)
        return Answer(text=text, retrieved=chunks)
