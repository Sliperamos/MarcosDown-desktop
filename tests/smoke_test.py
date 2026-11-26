"""Teste rápido: gera arquivos de exemplo e confere se a conversão funciona."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import converter  # noqa: E402

PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 18 Tf 20 80 Td (Ola PDF teste) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""


def main():
    # Uso: smoke_test.py [pasta_saida]  -> se passar pasta, só gera os arquivos de exemplo
    if len(sys.argv) > 1:
        d = Path(sys.argv[1])
        d.mkdir(parents=True, exist_ok=True)
    else:
        d = Path(tempfile.mkdtemp())
    casos = {}

    (d / "a.html").write_text("<h1>Titulo HTML</h1><p>texto</p>", encoding="utf-8")
    casos["a.html"] = "# Titulo HTML"

    (d / "a.csv").write_text("nome,qtd\nP2,10\n", encoding="utf-8")
    casos["a.csv"] = "| nome | qtd |"

    (d / "a.pdf").write_bytes(PDF)
    casos["a.pdf"] = "Ola PDF teste"

    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["Modelo", "Qtd"])
    wb.active.append(["S920", 5])
    wb.save(d / "a.xlsx")
    casos["a.xlsx"] = "S920"

    from pptx import Presentation
    pr = Presentation()
    s = pr.slides.add_slide(pr.slide_layouts[1])
    s.shapes.title.text = "Slide Teste"
    pr.save(d / "a.pptx")
    casos["a.pptx"] = "Slide Teste"

    if len(sys.argv) > 1:
        print("Exemplos gerados em", d)
        return

    # PDF de duas colunas com cabeçalho/rodapé (parecido com manual de impressora)
    from gerar_pdf_manual import main as gerar_manual
    gerar_manual(str(d / "manual.pdf"))
    casos["manual.pdf"] = "## Configurações de papel"

    falhas = 0
    for nome, esperado in casos.items():
        try:
            md = converter(d / nome)
            ok = esperado in md
        except Exception as exc:  # noqa: BLE001
            md, ok = f"ERRO {exc}", False
        print(("OK   " if ok else "FALHA"), nome, "->", md.strip().splitlines()[:2])
        falhas += not ok
    # ordem das colunas e limpeza
    md = converter(d / "manual.pdf")
    checks = {
        "colunas na ordem (4 antes de 5)": md.find("4 Na aba") < md.find("5 Selecione"),
        "sem rodapé '- 2 -'": "- 2" not in md,
        "sem cabeçalho repetido": "Registrando um tamanho de papel" not in md,
        "tabela montada": "|Modo de corte|Trabalho|" in md,
        "índice sem pontilhado": "— pág. 2" in md,
    }
    for nome, ok in checks.items():
        print(("OK   " if ok else "FALHA"), nome)
        falhas += not ok
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
