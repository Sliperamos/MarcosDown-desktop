"""Gera um PDF de teste parecido com manuais de impressora:
cabeçalho repetido, rodapé "- N -", títulos grandes, passos em duas colunas,
índice com pontilhados, tabela e texto girado."""
import sys
from pathlib import Path

import pymupdf

W, H = 595, 842
COL_L = pymupdf.Rect(50, 140, 285, 780)
COL_R = pymupdf.Rect(310, 140, 545, 780)


def cabecalho_rodape(page, n, titulo_secao):
    page.insert_text((50, 40), titulo_secao, fontsize=9, fontname="helv")
    page.draw_line((50, 46), (545, 46), width=0.5)
    page.insert_text((285, 815), f"- {n} -", fontsize=9, fontname="helv")


def caixa(page, rect, texto, fs=10.5):
    sobra = page.insert_textbox(rect, texto, fontsize=fs, fontname="helv", align=0)
    assert sobra >= 0, f"texto não coube ({sobra})"


def main(saida: str):
    doc = pymupdf.open()
    secao = "Registrando um tamanho de papel"

    # Página 1: índice com pontilhados
    p = doc.new_page(width=W, height=H)
    cabecalho_rodape(p, 1, "Índice")
    p.insert_text((50, 100), "Índice", fontsize=22, fontname="hebo")
    y = 150
    for nome, pg in [("Configurações de papel", 2), ("Calibrando o Sensor", 3),
                     ("Tabela de menus", 4)]:
        p.insert_text((50, y), f"{nome} " + "." * 60 + f" {pg}", fontsize=10.5, fontname="helv")
        y += 20

    # Páginas 2-3: passos em duas colunas
    for n, (titulo, esq, dir_) in enumerate([
        ("Configurações de papel",
         "1 Clique em [Start] e selecione [Control Panel] em [Windows System].\n\n"
         "2 Clique em [View devices and printers].\n\n"
         "3 Clique com o botão direito do mouse no ícone [Pro1050 PCL6] e, em seguida, "
         "selecione [Printing preferences].\n\n"
         "4 Na aba [Setup], clique em [User-defined paper].",
         "5 Selecione uma gramatura de substrato para corresponder à espessura do papel.\n\n"
         "6 Digite as informações sobre o tamanho do papel. Use uma régua para medir, "
         "com a maior precisão possível, o tamanho real do substrato.\n\n"
         "7 Quando toda a entrada estiver concluída, clique em [Add]."),
        ("Calibrando o Sensor",
         "1 Abaixe a alavanca de abertura da tampa do desbobinador para abrir a sua tampa.\n\n"
         "2 Confirme a posição do sensor. A configuração de fábrica é esta posição.",
         "3 Gire o disco de ajuste da posição do sensor para ajustar a posição do sensor.\n\n"
         "4 Feche a tampa do desbobinador com cuidado para não prender os dedos."),
    ], start=2):
        p = doc.new_page(width=W, height=H)
        cabecalho_rodape(p, n, secao)
        p.insert_text((50, 100), titulo, fontsize=20, fontname="hebo")
        caixa(p, COL_L, esq)
        caixa(p, COL_R, dir_)
        # texto girado (legenda de figura)
        p.insert_text((560, 600), "A configuração de fábrica", fontsize=8, rotate=90)

    # Página 4: tabela
    p = doc.new_page(width=W, height=H)
    cabecalho_rodape(p, 4, secao)
    p.insert_text((50, 100), "Tabela de menus", fontsize=20, fontname="hebo")
    linhas = [("Item", "Valor", "Descrição"),
              ("Modo de corte", "Trabalho", "Corta no final de um trabalho."),
              ("Intervalo de corte", "1 ~ 9999", "Quantas páginas são cortadas a cada vez."),
              ("Peso do substrato", "Médio Leve", "Define a espessura do papel.")]
    xs = [50, 190, 300, 545]
    y0 = 130
    for i, linha in enumerate(linhas):
        y = y0 + i * 26
        for j, cel in enumerate(linha):
            p.insert_text((xs[j] + 4, y + 17), cel, fontsize=10,
                          fontname="hebo" if i == 0 else "helv")
        p.draw_line((50, y), (545, y), width=0.6)
    yf = y0 + len(linhas) * 26
    p.draw_line((50, yf), (545, yf), width=0.6)
    for x in xs:
        p.draw_line((x, y0), (x, yf), width=0.6)

    doc.save(saida)
    print("PDF gerado:", saida)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "manual_teste.pdf")


def gerar_scans(pasta: str):
    """Página 'escaneada' (só imagem) em PDF e PNG, para testar o OCR."""
    from pathlib import Path
    pasta = Path(pasta)
    d = pymupdf.open()
    p = d.new_page(width=595, height=842)
    y = 90
    for t in ["PROCURAÇÃO AD JUDICIA", "OUTORGANTE: João da Silva, CPF 123.456.789-00",
              "OUTORGADO: Dr. Antônio Pereira, OAB/SP 98.765",
              "PODERES: para o foro em geral, podendo propor ações e recorrer."]:
        p.insert_text((60, y), t, fontsize=13, fontname="helv")
        y += 30
    pix = p.get_pixmap(dpi=200)
    pix.save(str(pasta / "scan.png"))
    so_imagem = pymupdf.open()
    pg = so_imagem.new_page(width=595, height=842)
    pg.insert_image(pg.rect, pixmap=pix)
    so_imagem.save(str(pasta / "scan.pdf"))
