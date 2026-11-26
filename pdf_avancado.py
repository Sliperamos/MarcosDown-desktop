"""Leitor de PDF avançado (PyMuPDF4LLM): separa colunas, cria títulos pelo
tamanho da fonte e monta tabelas. Usa o modo clássico, que mantém a ordem
de leitura das colunas de forma mais previsível em manuais."""
from __future__ import annotations

import re

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
    return pdf_para_markdown_detalhado(caminho, usar_ocr=False)[0]


COBERTURA_MIN = 0.9


def _palavras(texto: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-zÀ-ú]{4,}", texto or "")}


def cobertura(pagina, md: str) -> float:
    """Fração das palavras da página que aparecem no Markdown gerado."""
    nat = _palavras(pagina.get_text())
    if len(nat) < 15:
        return 1.0
    return len(nat & _palavras(md)) / len(nat)


def texto_por_colunas(pagina) -> str:
    """Texto da página em ordem de leitura de 1 ou 2 colunas, sem perder nada."""
    blocos = [b for b in pagina.get_text("blocks") if b[6] == 0 and b[4].strip()]
    meio = pagina.rect.width / 2
    esq = [b for b in blocos if b[2] <= meio + 20]
    dir_ = [b for b in blocos if b[0] >= meio - 20]
    largos = [b for b in blocos if b not in esq and b not in dir_]
    if not esq or not dir_:
        ordem = sorted(blocos, key=lambda b: (round(b[1]), b[0]))
    else:
        topo_colunas = min(b[1] for b in esq + dir_)
        antes = sorted([b for b in largos if b[1] < topo_colunas], key=lambda b: b[1])
        depois = sorted([b for b in largos if b[1] >= topo_colunas], key=lambda b: b[1])
        ordem = antes + sorted(esq, key=lambda b: b[1]) + sorted(dir_, key=lambda b: b[1]) + depois
    return "\n\n".join(b[4].strip() for b in ordem)


# imagem que ocupa pelo menos esta fração da página entra no OCR de imagens
AREA_MIN_IMAGEM = 0.06
LETRAS_PAGINA_VAZIA = 25


def pdf_para_markdown_detalhado(caminho: str, usar_ocr: bool = True,
                                ocr_em_imagens: bool = True) -> tuple[str, dict]:
    """Converte página a página, com marcador [pág. N].

    - Página sem texto (escaneada) -> OCR da página inteira.
    - Página com texto e imagens grandes -> OCR só das imagens; o texto achado
      entra como citação "[texto na imagem]".
    """
    import pymupdf

    import ocr

    mod = _carregar()
    doc = pymupdf.open(caminho)
    if doc.needs_pass:
        raise RuntimeError("PDF protegido por senha")
    info = {"paginas": len(doc), "ocr_paginas": [], "imagens_lidas": 0,
            "imagens_sem_texto": 0, "paginas_refeitas": [], "avisos": []}
    usar_ocr = usar_ocr and ocr.ocr_disponivel()

    # margins=0: não corta nada; cabeçalhos e rodapés saem na limpeza
    paginas = mod.to_markdown(doc, margins=0, page_chunks=True, show_progress=False)
    partes = []
    for i, ch in enumerate(paginas):
        pagina = doc[i]
        md = ch.get("text", "") if isinstance(ch, dict) else str(ch)
        nativo = ocr.qtd_letras(pagina.get_text())

        # rede de segurança: se o leitor avançado perdeu texto desta página,
        # refaz a página lendo coluna por coluna (perde títulos, mas não perde texto)
        if nativo >= LETRAS_PAGINA_VAZIA and cobertura(pagina, md) < COBERTURA_MIN:
            md = texto_por_colunas(pagina)
            info["paginas_refeitas"].append(i + 1)

        if nativo < LETRAS_PAGINA_VAZIA:
            tem_conteudo = bool(pagina.get_images()) or bool(pagina.get_drawings())
            if usar_ocr and tem_conteudo:
                texto = ocr.ocr_pagina(pagina)
                if ocr.qtd_letras(texto) >= 10:
                    if not ocr.texto_confiavel(texto):
                        info["avisos"].append(f"OCR de baixa qualidade na pág. {i + 1}")
                    md = "[texto obtido por OCR — conferir nomes e números]\n\n" + texto
                    info["ocr_paginas"].append(i + 1)
                else:
                    md = "[página sem texto legível]"
            elif tem_conteudo and not md.strip():
                md = "[página escaneada — sem OCR]"
        elif usar_ocr and ocr_em_imagens:
            area_pag = abs(pagina.rect)
            extras = []
            for img in pagina.get_image_info():
                r = pymupdf.Rect(img["bbox"]) & pagina.rect
                if r.is_empty or abs(r) < area_pag * AREA_MIN_IMAGEM:
                    continue
                texto = ocr.ocr_regiao(pagina, r)
                if ocr.texto_confiavel(texto):
                    info["imagens_lidas"] += 1
                    citacao = "\n".join("> " + l if l else ">" for l in texto.split("\n"))
                    extras.append("> [texto na imagem — OCR]\n" + citacao)
                else:
                    info["imagens_sem_texto"] += 1
                    extras.append("[imagem]")
            if extras:
                md = md.rstrip() + "\n\n" + "\n\n".join(extras)

        partes.append(f"[pág. {i + 1}]\n\n{md.strip()}")

    if info["paginas_refeitas"]:
        info["avisos"].append("págs. lidas pelo modo simples (sem títulos): "
                              + ", ".join(map(str, info["paginas_refeitas"])))
    if info["ocr_paginas"]:
        info["avisos"].append("texto de OCR pode ter erros em nomes e números")
    if not usar_ocr and any("sem OCR" in p for p in partes):
        info["avisos"].append("há páginas escaneadas sem OCR")
    return "\n\n".join(partes) + "\n", info
