"""Leitor de PDF avançado (PyMuPDF4LLM): separa colunas, cria títulos pelo
tamanho da fonte e monta tabelas. Usa o modo clássico, que mantém a ordem
de leitura das colunas de forma mais previsível em manuais."""
from __future__ import annotations

import threading

_lock = threading.Lock()
_mod = None


def _carregar():
    global _mod
    with _lock:
        if _mod is None:
            import pymupdf4llm

            try:
                pymupdf4llm.use_layout(False)
            except Exception:
                pass
            _mod = pymupdf4llm
        return _mod


def pdf_para_markdown(caminho: str) -> str:
    mod = _carregar()
    # margins=0: não corta nada da página; cabeçalhos e rodapés saem na limpeza
    return mod.to_markdown(caminho, margins=0, show_progress=False)
