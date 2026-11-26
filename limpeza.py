"""Limpeza do Markdown gerado a partir de PDFs.

- remove números de página no estilo "- 12 -" / "Página 3 de 10"
- remove cabeçalhos de página repetidos (a linha que aparece logo após cada quebra de página)
- transforma pontilhados de índice em "Título — pág. 12"
- remove restos de texto girado (sequências de linhas com 1 a 4 letras)
- junta frases quebradas no meio pelo layout do PDF
- tira negrito redundante de títulos e linhas em branco em excesso
"""
from __future__ import annotations

import re
from collections import Counter

RE_PAGINA = re.compile(
    r"^\s*(?:[-–—]\s*\d{1,4}\s*[-–—]?|\d{1,4}\s*[-–—]|"
    r"(?:p[áa]gina|page|p[áa]g\.?)\s*\d{1,4}(?:\s*(?:de|of|/)\s*\d{1,4})?)\s*$",
    re.IGNORECASE,
)
RE_PONTILHADO = re.compile(r"\s*(?:\.\s?){4,}\s*(\d{1,4})\b\s*")
RE_ESTRUTURA = re.compile(r"^\s*(?:#|\||>|```|[-*+]\s|\d+[.)]\s|!\[|<|---|\*\*\*)")
RE_MARCADOR = re.compile(r"^\(?\d{1,3}[).]?$|^[•▪■□◎]$")
RE_TITULO_NEGRITO = re.compile(r"^(#{1,6})\s+\*\*(.+?)\*\*\s*$")
RE_NUM_PASSO = re.compile(r"^(?:#{1,6}\s*)?(?:\*\*)?\(?\d{1,3}[.)]?(?:\*\*)?$")
RE_SUBLINHADO = re.compile(r"^\s*<u>(.+?)</u>\s*$")
RE_NAO_JUNTA = re.compile(r"^\s*(?:#|\||>|```|!\[|<|---|\*\*\*)")
RE_MARCA_PAG = re.compile(r"^\[pág\. \d+\]$")
RE_SUBPASSO = re.compile(r"^\(?\d{1,3}[.)]")
FIM_FRASE = tuple(".!?:;")


def _estrutural(linha: str) -> bool:
    return bool(RE_ESTRUTURA.match(linha))


def _remover_paginas_e_cabecalhos(linhas: list[str]) -> list[str]:
    rodapes = [i for i, l in enumerate(linhas) if RE_PAGINA.match(l)]
    marcas = [i for i, l in enumerate(linhas) if RE_MARCA_PAG.match(l.strip())]
    paginas = sorted(set(rodapes) | set(marcas))  # quebras de página
    if not paginas:
        return linhas

    # a primeira linha com cara de título depois de cada número de página é
    # candidata a cabeçalho (pula restos curtos de figura no caminho)
    def parece_titulo(t: str) -> bool:
        return (5 <= len(t) <= 90 and t[:1].isalpha() and t[:1].isupper()
                and not t.startswith("|") and not t.rstrip().endswith((".", ":", ",")))

    def prox_texto(j):
        for k in range(j + 1, min(j + 4, len(linhas))):
            if linhas[k].strip():
                return linhas[k].strip()
        return ""

    def cabecalho_apos(i):
        for j in range(i + 1, min(i + 12, len(linhas))):
            t = linhas[j].strip()
            if RE_PAGINA.match(linhas[j]) or RE_MARCA_PAG.match(t):
                return None
            if not t:
                continue
            if RE_NUM_PASSO.match(t):
                return None  # número de passo: o que vem depois é conteúdo, não cabeçalho
            if len(t) <= 4:
                continue  # resto de texto girado/figura
            if not parece_titulo(t):
                return None
            # frase que continua na linha seguinte ("Clique em [Start] e" / "em [Windows System].")
            # é começo de passo de outra coluna, não cabeçalho de página
            if _comeca_continuacao(prox_texto(j)):
                return None
            return j
        return None

    candidatos = Counter()
    pos_cand = {}
    for i in paginas:
        j = cabecalho_apos(i)
        if j is not None:
            t = linhas[j].strip()
            candidatos[t] += 1
            pos_cand.setdefault(t, []).append(j)

    minimo = 3 if len(paginas) >= 6 else 2
    remover = set(rodapes)  # o marcador [pág. N] fica
    for t, n in candidatos.items():
        if n >= minimo:
            remover.update(pos_cand[t])
            # cabeçalho da primeira página (antes do primeiro rodapé)
            for k in range(0, paginas[0]):
                if linhas[k].strip() == t:
                    remover.add(k)
                    break
    return [l for i, l in enumerate(linhas) if i not in remover]


def _normalizar(linhas: list[str]) -> list[str]:
    # cabeçalhos de página vêm sublinhados (<u>Seção</u>) e se repetem: remove todos
    sub = Counter(m.group(1).strip() for l in linhas if (m := RE_SUBLINHADO.match(l)))
    repetidos = {t for t, n in sub.items() if n >= 3 and not t.endswith(".")}
    saida = []
    for l in linhas:
        m = RE_SUBLINHADO.match(l)
        if m and m.group(1).strip() in repetidos:
            continue
        # subtítulos destacados (**<mark>Título</mark>**) viram ###
        l = re.sub(r"^\s*\*\*<mark>(.+?)</mark>\*\*\s*$", r"### \1", l)
        l = re.sub(r"</?(?:u|mark)>", "", l)
        l = l.replace("`•`", "•").replace("** **", " ")
        if l.lstrip().startswith("|"):
            l = re.sub(r"(?<=\|)Col\d+(?=\|)", "", l)          # cabeçalho sem nome
            l = re.sub(r"\|(?:\s*<br>)+\s*", "|", l)             # <br> no início da célula
            l = re.sub(r"\s*(?:<br>\s*)+\|", "|", l)             # <br> no fim da célula
            l = re.sub(r"(?:<br>\s*){2,}", "<br>", l)
        saida.append(l)
    return saida


def _hierarquia(linhas: list[str]) -> list[str]:
    """# 1 + ## Título -> # 1. Título; títulos de seção ###### -> ##."""
    saida, i = [], 0
    while i < len(linhas):
        l = linhas[i]
        m = re.match(r"^#{1,6}\s+(\d{1,2})\s*$", l)
        if m:
            j = i + 1
            while j < len(linhas) and not linhas[j].strip():
                j += 1
            mt = re.match(r"^#{1,6}\s+(.+)$", linhas[j]) if j < len(linhas) else None
            if mt:
                saida.append(f"# {m.group(1)}. {mt.group(1).strip()}")
                i = j + 1
                continue
        l = re.sub(r"^#{4,6}\s+", "## ", l)
        saida.append(l)
        i += 1
    return saida


def _remover_texto_girado(linhas: list[str]) -> list[str]:
    saida, i, n = [], 0, len(linhas)
    while i < n:
        j = i
        while (j < n and linhas[j].strip() and len(linhas[j].strip()) <= 4
               and not RE_MARCADOR.match(linhas[j].strip())
               and not _estrutural(linhas[j])):
            j += 1
        if j - i >= 4:
            i = j
            continue
        saida.append(linhas[i])
        i += 1
    return saida


def _pontilhados(linhas: list[str]) -> list[str]:
    saida = []
    for l in linhas:
        if RE_PONTILHADO.search(l) and not l.lstrip().startswith("|"):
            l = l.replace("**", "")
            partes = RE_PONTILHADO.sub(lambda m: f" — pág. {m.group(1)}\n", l).rstrip("\n")
            saida.extend(p.strip() for p in partes.split("\n") if p.strip())
        else:
            saida.append(l)
    return saida


def _comeca_continuacao(t: str) -> bool:
    c = t[:1]
    return bool(c) and (c.islower() or c in "[(,")


def _juntar_quebras(linhas: list[str]) -> list[str]:
    saida: list[str] = []
    i = 0
    while i < len(linhas):
        atual = linhas[i].rstrip()
        # número de passo sozinho ("**7**" / "7") + texto do passo na linha seguinte
        num = RE_NUM_PASSO.match(atual.strip())
        if (num and not atual.lstrip().startswith("#") and i + 1 < len(linhas)
                and linhas[i + 1].strip() and not _estrutural(linhas[i + 1])
                and linhas[i + 1].strip()[:1].isupper()):
            atual = atual.strip().replace("*", "") + " " + linhas[i + 1].strip()
            i += 1
        while True:
            if (not atual.strip() or RE_NAO_JUNTA.match(atual) or RE_MARCA_PAG.match(atual.strip())
                    or atual.rstrip().endswith(FIM_FRASE)):
                break
            # próxima linha direta ou separada por UMA linha em branco
            j = i + 1
            if j < len(linhas) and not linhas[j].strip():
                if len(atual.strip()) < 25:
                    break
                j += 1
            if j >= len(linhas):
                break
            prox = linhas[j].strip()
            if (not prox or _estrutural(linhas[j]) or RE_MARCADOR.match(prox)
                    or RE_SUBPASSO.match(prox) or prox.startswith("[pág.")
                    or prox.startswith(("[imagem", "[texto", "[página"))):
                break
            if not _comeca_continuacao(prox):
                break
            if re.search(r"[a-zà-ú]-$", atual) and prox[:1].islower():
                atual = atual[:-1] + prox  # hifenização: "dispo-" + "sitivo"
            else:
                atual = atual + " " + prox
            i = j
        saida.append(atual)
        i += 1
    return saida


def _final(linhas: list[str]) -> str:
    saida, vazias, anterior = [], 0, None
    for l in linhas:
        m = RE_TITULO_NEGRITO.match(l)
        if m:
            l = f"{m.group(1)} {m.group(2).strip()}"
        mt = re.match(r"^#{1,6}\s+(.+)$", l)
        if mt and anterior == mt.group(1).strip():
            # "Índice" solto logo antes de "# Índice": fica só o título
            while saida and saida[-1] == "":
                saida.pop()
            if saida and saida[-1].strip() == anterior:
                saida.pop()
        if not l.strip():
            vazias += 1
            if vazias > 1:
                continue
            saida.append("")
            continue
        vazias = 0
        t = l.strip()
        if t == anterior and not _estrutural(l) and not t.startswith("["):
            continue  # linha duplicada em sequência ("Índice" / "Índice")
        anterior = t
        saida.append(l.rstrip())
    return "\n".join(saida).strip() + "\n"


def limpar_markdown(md: str) -> str:
    linhas = md.replace("\r\n", "\n").replace(" ", " ").replace("\f", "\n").split("\n")
    linhas = _normalizar(linhas)
    linhas = _remover_paginas_e_cabecalhos(linhas)
    linhas = _hierarquia(linhas)
    linhas = _remover_texto_girado(linhas)
    linhas = _pontilhados(linhas)
    linhas = _juntar_quebras(linhas)
    return _final(linhas)
