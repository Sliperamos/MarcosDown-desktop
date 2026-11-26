"""OCR local (sem internet) usando o Tesseract embutido no PyMuPDF.

Só precisa dos arquivos de idioma em ./tessdata (por + eng).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pymupdf

IDIOMAS = "por+eng"
EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".jfif"}


def pasta_tessdata() -> str | None:
    candidatos = []
    if getattr(sys, "_MEIPASS", None):
        candidatos.append(Path(sys._MEIPASS) / "tessdata")
    candidatos.append(Path(__file__).resolve().parent / "tessdata")
    if os.environ.get("TESSDATA_PREFIX"):
        candidatos.append(Path(os.environ["TESSDATA_PREFIX"]))
    for c in candidatos:
        if (c / "por.traineddata").exists():
            return str(c)
    return None


def ocr_disponivel() -> bool:
    return pasta_tessdata() is not None


def qtd_letras(texto: str) -> int:
    return len(re.findall(r"[A-Za-zÀ-ú0-9]", texto or ""))


def _ocr_pixmap(pix: "pymupdf.Pixmap") -> str:
    """OCR de uma imagem já renderizada (1 pixel = 1 ponto)."""
    if pix.alpha or pix.n > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix) if pix.n - pix.alpha > 3 else pymupdf.Pixmap(pix, 0)
    # imagens pequenas: amplia 2x, o Tesseract erra muito em letra miúda
    escala = 2 if max(pix.width, pix.height) < 1400 else 1
    doc = pymupdf.open()
    pagina = doc.new_page(width=pix.width, height=pix.height)
    pagina.insert_image(pagina.rect, pixmap=pix)
    tp = pagina.get_textpage_ocr(language=IDIOMAS, dpi=72 * escala, full=True,
                                 tessdata=pasta_tessdata())
    return _arrumar(pagina.get_text(textpage=tp))


def _arrumar(texto: str) -> str:
    linhas = [l.rstrip() for l in texto.replace("\r", "").split("\n")]
    saida, vazias = [], 0
    for l in linhas:
        if not l.strip():
            vazias += 1
            if vazias <= 1:
                saida.append("")
            continue
        vazias = 0
        saida.append(l)
    return "\n".join(saida).strip()


def ocr_pagina(pagina: "pymupdf.Page", dpi: int = 300) -> str:
    return _ocr_pixmap(pagina.get_pixmap(dpi=dpi))


def ocr_regiao(pagina: "pymupdf.Page", rect: "pymupdf.Rect", dpi: int = 300) -> str:
    return _ocr_pixmap(pagina.get_pixmap(dpi=dpi, clip=rect))


def ocr_arquivo_imagem(caminho: str) -> tuple[str, int]:
    """Retorna (texto, nº de quadros). TIFF com várias páginas é suportado."""
    doc = pymupdf.open(caminho)
    textos = []
    for i, pag in enumerate(doc):
        # pagina de imagem: renderiza na resolução original da imagem
        info = pag.get_images(full=True)
        if info:
            pix = pymupdf.Pixmap(doc, info[0][0])
        else:
            pix = pag.get_pixmap(dpi=200)
        t = _ocr_pixmap(pix)
        textos.append(f"[pág. {i + 1}]\n\n{t}" if len(doc) > 1 else t)
    return "\n\n".join(textos).strip(), len(doc)


_RE_PALAVRA = re.compile(r"^[A-Za-zÀ-ú]{2,}[.,;:]?$")
_VOGAIS = set("aeiouáéíóúâêôãõàAEIOUÁÉÍÓÚÂÊÔÃÕÀyY")


def texto_confiavel(texto: str) -> bool:
    """Diz se o OCR parece texto de verdade e não lixo (ex.: captura de tela
    com letra miúda vira "Poomireressiuion", "Scrrege", linhas de 1 caractere)."""
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]
    if not linhas or qtd_letras(texto) < 15:
        return False
    curtas = sum(1 for l in linhas if qtd_letras(l) < 4)
    if curtas / len(linhas) > 0.3:
        return False
    tokens = texto.split()
    boas = 0
    for t in tokens:
        if re.fullmatch(r"[\d.,/\-–()%ºª°]+", t):  # números, datas, CPF etc.
            boas += 1
        elif _RE_PALAVRA.match(t) and any(c in _VOGAIS for c in t) \
                and not re.search(r"[bcdfghjklmnpqrstvwxz]{4,}", t.lower()):
            boas += 1
    return boas / max(1, len(tokens)) >= 0.7 and boas >= 5
