"""Leitor de PDF avançado (PyMuPDF4LLM): separa colunas, cria títulos pelo
tamanho da fonte e monta tabelas. Usa o modo clássico, que mantém a ordem
de leitura das colunas de forma mais previsível em manuais."""
from __future__ import annotations

import threading

_lock = threading.Lock()
_mod = None


def _corrigir_marcadores():
    """O PyMuPDF4LLM trata a letra "o" no começo da linha como marcador de lista
    (por causa do ◦ em fontes antigas). Em português "o" é artigo: "o protocolo"
    virava "- protocolo". Tira o "o" da lista de marcadores."""
    from pymupdf4llm.helpers import utils

    def sem_o(seq):
        return tuple(b for b in seq if b != "o")

    utils.BULLETS = sem_o(utils.BULLETS)
    try:
        from pymupdf4llm.helpers import document_layout

        document_layout.BULLETS = sem_o(document_layout.BULLETS)
    except Exception:
        pass


def _carregar():
    global _mod
    with _lock:
        if _mod is None:
            import pymupdf4llm

            try:
                pymupdf4llm.use_layout(False)
            except Exception:
                pass
            _corrigir_marcadores()
            _mod = pymupdf4llm
        return _mod


def pdf_para_markdown(caminho: str) -> str:
    mod = _carregar()
    # margins=0: não corta nada da página; cabeçalhos e rodapés saem na limpeza
    return mod.to_markdown(caminho, margins=0, show_progress=False)
