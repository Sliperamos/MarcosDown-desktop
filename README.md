# MarcosDown

App para Windows que converte arquivos para Markdown usando o [Microsoft MarkItDown](https://github.com/microsoft/markitdown).

**Feito para preparar lotes de arquivos para IAs** (Claude, ChatGPT etc.): texto limpo, com página e origem marcadas, gasta menos tokens e é lido mais rápido.

**Formatos:** PDF, Word (.docx), Excel (.xlsx/.xls), PowerPoint (.pptx), HTML, CSV, JSON, XML, EPUB, ZIP, e-mails do Outlook (.msg), Jupyter (.ipynb) e imagens (só os metadados).

## Como usar
- Arraste arquivos ou pastas para a lista (ou use os botões).
- Escolha onde salvar o `.md` e clique em **Converter**.
- Clique num arquivo para ver a prévia. Dá para **Copiar** ou usar **Salvar como...**.
- Dê dois cliques num arquivo convertido para abrir o `.md`.
- Pelo instalador dá para adicionar **"Converter para Markdown"** ao menu *Enviar para* do Explorer.

## PDF: leitor avançado e limpeza
Para PDF, o MarcosDown usa por padrão o **PyMuPDF4LLM** em vez do leitor de PDF do MarkItDown:
- mantém a ordem de leitura de páginas em **duas colunas**;
- cria **títulos** (`#`, `##`) pelo tamanho da fonte e monta **tabelas** em Markdown.

Depois disso, uma **limpeza automática** remove os números de página ("- 12 -"), os cabeçalhos que se repetem
em toda página e os restos de texto girado, transforma os pontilhados do índice em "Título — pág. 12"
e junta as frases que o PDF quebrou no meio.

As duas opções podem ser desligadas na seção **PDF** da janela. Se o leitor avançado falhar
(PDF escaneado, por exemplo), o app volta sozinho para o MarkItDown.

> Imagens e ilustrações não são convertidas: o resultado é só o texto.

## OCR (escaneados, fotos e imagens)
Feito 100% no PC, sem internet (bom para documentos sigilosos). Usa o Tesseract que já vem no PyMuPDF,
com os idiomas português e inglês da pasta `tessdata/`.
- **PDF escaneado:** página sem texto passa pelo OCR inteira.
- **Imagem dentro de PDF** (documento digitalizado anexado, print): o texto achado entra como citação
  `> [texto na imagem — OCR]`. Imagem sem texto vira `[imagem]`.
- **Fotos e imagens soltas** (JPG, PNG, TIFF com várias páginas, BMP, WebP, GIF): viram texto.
- Todo texto de OCR sai marcado com *"conferir nomes e números"*.

## Pensado para IA
- `[pág. N]` no início de cada página do PDF, para a IA poder citar a página.
- Cabeçalho no topo de cada `.md` com arquivo de origem, tipo, páginas, onde houve OCR e avisos.
- Na lista, o status mostra **Concluído · OCR** ou **Atenção** (arquivo sem texto, leitor falhou etc.).

## Como gerar o instalador
O GitHub Actions compila sozinho a cada envio para a branch `main`:
1. Abra a aba **Actions** → execução **Build Windows** mais recente.
2. Em **Artifacts**, baixe `MarcosDown-Windows` (vem o instalador `.exe` e uma versão portátil `.zip`).

Para criar uma versão com página de download: crie uma tag, por exemplo `v1.0.0`. O instalador vai aparecer em **Releases**.

## Compilar no próprio PC (opcional)
```
pip install -r requirements.txt
pyinstaller marcosdown.spec --noconfirm
```
O app fica em `dist\MarcosDown\`.
