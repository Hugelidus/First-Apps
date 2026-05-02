"""Tests del chunker por tokens."""

from __future__ import annotations

from src.ingest.chunker import _get_tokenizer, chunk_text

_ENC = _get_tokenizer()


def _tokens(text: str) -> int:
    return len(_ENC.encode(text))


def test_chunker_genera_un_solo_chunk_para_texto_corto():
    text = "Este es un párrafo corto sobre Kraken."
    chunks = chunk_text(text, fuente="wikipedia_pelicula", url="http://x")
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].n_tokens == _tokens(text)


def test_chunker_respeta_tamano_y_solape():
    # Generamos un texto largo con párrafos numerados.
    para = (
        "Este es un párrafo de prueba con varias frases para alcanzar un "
        "tamaño suficiente. Hablamos de Vitoria, de Madrid, del Libro Negro "
        "de las Horas y de personajes como Unai y Esti repetidos."
    )
    text = "\n\n".join([f"{i}. {para}" for i in range(60)])
    chunks = chunk_text(text, fuente="wikipedia_pelicula", url="http://x", chunk_size=200, overlap=40)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.n_tokens <= 200, f"chunk excede tamaño: {c.n_tokens}"

    # Verifica solape: el final del chunk i aparece dentro del chunk i+1
    # (no comparamos texto exacto por re-decodificación, pero algunas
    # palabras finales del chunk previo deben estar en el siguiente).
    for prev, nxt in zip(chunks, chunks[1:]):
        last_words = prev.text.split()[-5:]
        assert any(w in nxt.text for w in last_words), "no hay solape detectable"


def test_chunker_chunk_ids_unicos_y_estables():
    text = "\n\n".join(f"Párrafo {i} sobre Kraken y Esti." for i in range(20))
    a = chunk_text(text, fuente="wikipedia_pelicula", url="http://x", chunk_size=80, overlap=10)
    b = chunk_text(text, fuente="wikipedia_pelicula", url="http://x", chunk_size=80, overlap=10)
    ids_a = [c.chunk_id for c in a]
    assert len(ids_a) == len(set(ids_a)), "ids duplicados"
    assert ids_a == [c.chunk_id for c in b], "ids no son estables entre runs"
