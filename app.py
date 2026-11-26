"""MarcosDown - interface gráfica local para o Microsoft MarkItDown.

Converte PDF, Word, Excel, PowerPoint, HTML, CSV, JSON, XML, EPUB, ZIP,
e-mails do Outlook (.msg) e imagens (metadados) para Markdown.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_OK = True
except Exception:  # pragma: no cover - sem arrastar e soltar
    DND_OK = False

APP_NAME = "MarcosDown"
APP_VERSION = "1.2.4"

EXTENSOES = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".json", ".xml",
    ".html", ".htm", ".txt", ".md", ".epub", ".zip", ".msg", ".ipynb",
    ".jpg", ".jpeg", ".png", ".rss", ".atom",
    ".tif", ".tiff", ".bmp", ".webp", ".gif", ".jfif",
}

_md = None
_md_lock = threading.Lock()


def get_markitdown():
    """Carrega o MarkItDown só na primeira conversão (abre o app mais rápido)."""
    global _md
    with _md_lock:
        if _md is None:
            from markitdown import MarkItDown

            _md = MarkItDown(enable_plugins=False)
        return _md


TIPOS = {".pdf": "PDF", ".docx": "Word", ".pptx": "PowerPoint", ".xlsx": "Excel", ".xls": "Excel",
         ".csv": "CSV", ".html": "HTML", ".htm": "HTML", ".msg": "E-mail (Outlook)", ".epub": "EPUB",
         ".zip": "ZIP", ".txt": "Texto", ".json": "JSON", ".xml": "XML"}


def converter(caminho: Path, pdf_avancado: bool = True, limpar: bool = True,
              usar_ocr: bool = True, cabecalho: bool = False) -> str:
    return converter_detalhado(caminho, pdf_avancado, limpar, usar_ocr, cabecalho)[0]


def converter_detalhado(caminho: Path, pdf_avancado: bool = True, limpar: bool = True,
                        usar_ocr: bool = True, cabecalho: bool = True) -> tuple[str, dict]:
    """Converte um arquivo e devolve (markdown, info).

    - PDF: leitor avançado página a página com [pág. N]; OCR em páginas
      escaneadas e em imagens grandes; volta para o MarkItDown se falhar.
    - Imagens: OCR (português + inglês).
    - Demais formatos: MarkItDown.
    """
    import ocr

    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    info = {"tipo": TIPOS.get(ext, ext.lstrip(".").upper()), "avisos": [], "ocr": "não"}
    md = None

    if ext == ".pdf" and pdf_avancado:
        try:
            from pdf_avancado import pdf_para_markdown_detalhado

            md, det = pdf_para_markdown_detalhado(str(caminho), usar_ocr=usar_ocr)
            info["paginas"] = det["paginas"]
            info["avisos"] += det["avisos"]
            if det["ocr_paginas"]:
                pags = det["ocr_paginas"]
                info["ocr"] = ("todas as páginas" if len(pags) == det["paginas"]
                               else "págs. " + ", ".join(map(str, pags)))
            if det.get("paginas_formulario"):
                info["formulario"] = "págs. " + ", ".join(map(str, det["paginas_formulario"]))
            if det["imagens_lidas"]:
                info["imagens_com_texto"] = det["imagens_lidas"]
            if ocr.qtd_letras(md) < 20:
                info["avisos"].append("nenhum texto encontrado")
        except Exception as exc:
            if "senha" in str(exc):
                raise
            info["avisos"].append(f"leitor avançado falhou ({type(exc).__name__}); usado o simples")
            md = None
    elif ext in ocr.EXT_IMAGEM:
        info["tipo"] = "Imagem"
        if usar_ocr and ocr.ocr_disponivel():
            texto, quadros = ocr.ocr_arquivo_imagem(str(caminho))
            if quadros > 1:
                info["paginas"] = quadros
            if ocr.qtd_letras(texto) >= 10:
                md = "[texto obtido por OCR — conferir nomes e números]\n\n" + texto
                info["ocr"] = "sim"
                info["avisos"].append("texto de OCR pode ter erros em nomes e números")
            else:
                md = "[imagem sem texto legível]"
                info["avisos"].append("imagem sem texto legível")

    if md is None:
        md = get_markitdown().convert(str(caminho)).text_content or ""
    if ext == ".pdf" and limpar:
        from limpeza import limpar_markdown

        md = limpar_markdown(md)
    if cabecalho:
        md = montar_cabecalho(caminho, info) + md
    return md, info


def montar_cabecalho(caminho: Path, info: dict) -> str:
    """Bloco de dados no topo do .md: ajuda a IA a saber de onde veio cada trecho."""
    from datetime import datetime

    linhas = ["---", f"arquivo: {caminho.name}", f"tipo: {info['tipo']}"]
    if info.get("paginas"):
        linhas.append(f"paginas: {info['paginas']}")
    linhas.append(f"ocr: {info['ocr']}")
    if info.get("formulario"):
        linhas.append(f"formulario: {info['formulario']} (lido linha a linha: rótulos e, abaixo, os valores)")
    if info.get("imagens_com_texto"):
        linhas.append(f"imagens_com_texto: {info['imagens_com_texto']}")
    if info["avisos"]:
        linhas.append("avisos: " + "; ".join(dict.fromkeys(info["avisos"])))
    linhas.append(f"convertido_em: {datetime.now():%Y-%m-%d %H:%M} (MarcosDown {APP_VERSION})")
    linhas.append("---")
    return "\n".join(linhas) + "\n\n"


def abrir_no_sistema(caminho: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(caminho))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(caminho)])
        else:
            subprocess.Popen(["xdg-open", str(caminho)])
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"Não foi possível abrir:\n{exc}")


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.fila: queue.Queue = queue.Queue()
        self.itens: dict[str, dict] = {}  # id da linha -> {path, md, saida, erro}
        self.rodando = False

        root.title(APP_NAME)
        root.geometry("1100x800")
        root.minsize(820, 660)
        self._icone()
        self._estilo()
        self._montar()
        root.after(100, self._processar_fila)

    # ---------- aparência ----------
    def _icone(self):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
        ico = base / "assets" / "icon.png"
        if ico.exists():
            try:
                self._img_icone = tk.PhotoImage(file=str(ico))
                self.root.iconphoto(True, self._img_icone)
            except Exception:
                pass

    def _estilo(self):
        st = ttk.Style(self.root)
        if "vista" in st.theme_names():
            st.theme_use("vista")
        elif "clam" in st.theme_names():
            st.theme_use("clam")
        st.configure("Titulo.TLabel", font=("Segoe UI", 14, "bold"))
        st.configure("Sub.TLabel", foreground="#666")
        st.configure("Acao.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 6))
        st.configure("Treeview", rowheight=24)

    # ---------- layout ----------
    def _montar(self):
        topo = ttk.Frame(self.root, padding=(12, 10, 12, 4))
        topo.pack(fill="x")
        ttk.Label(topo, text="MarcosDown — Converter arquivos para Markdown",
                  style="Titulo.TLabel").pack(side="left")
        ttk.Label(topo, text=f"v{APP_VERSION}", style="Sub.TLabel").pack(side="right")

        painel = ttk.PanedWindow(self.root, orient="horizontal")
        painel.pack(fill="both", expand=True, padx=12, pady=6)

        # --- esquerda: lista de arquivos ---
        esq = ttk.Frame(painel)
        painel.add(esq, weight=2)

        barra = ttk.Frame(esq)
        barra.pack(fill="x", pady=(0, 6))
        ttk.Button(barra, text="Adicionar arquivos", command=self.add_arquivos).pack(side="left")
        ttk.Button(barra, text="Adicionar pasta", command=self.add_pasta).pack(side="left", padx=4)
        ttk.Button(barra, text="Remover", command=self.remover).pack(side="left")
        ttk.Button(barra, text="Limpar", command=self.limpar).pack(side="left", padx=4)

        dica = "Arraste arquivos ou pastas para a lista" if DND_OK else \
            "Use os botões acima para adicionar arquivos"
        ttk.Label(esq, text=dica, style="Sub.TLabel").pack(anchor="w")

        lista_fr = ttk.Frame(esq)
        lista_fr.pack(fill="both", expand=True, pady=(4, 0))
        self.lista = ttk.Treeview(lista_fr, columns=("arquivo", "status"),
                                  show="headings", selectmode="extended")
        self.lista.heading("arquivo", text="Arquivo")
        self.lista.heading("status", text="Status")
        self.lista.column("arquivo", width=330)
        self.lista.column("status", width=130, anchor="center")
        sb = ttk.Scrollbar(lista_fr, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=sb.set)
        self.lista.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.lista.tag_configure("ok", foreground="#1a7f37")
        self.lista.tag_configure("erro", foreground="#c62828")
        self.lista.bind("<<TreeviewSelect>>", lambda e: self.mostrar_previa())
        self.lista.bind("<Double-1>", lambda e: self.abrir_md())
        self.lista.bind("<Delete>", lambda e: self.remover())

        if DND_OK:
            for w in (self.lista, esq):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)

        # opções de saída
        opc = ttk.LabelFrame(esq, text="Onde salvar o .md", padding=8)
        opc.pack(fill="x", pady=(8, 0))
        self.modo_saida = tk.StringVar(value="mesma")
        ttk.Radiobutton(opc, text="Na mesma pasta do arquivo original",
                        variable=self.modo_saida, value="mesma").pack(anchor="w")
        linha = ttk.Frame(opc)
        linha.pack(fill="x", pady=(2, 0))
        ttk.Radiobutton(linha, text="Nesta pasta:", variable=self.modo_saida,
                        value="pasta").pack(side="left")
        self.pasta_saida = tk.StringVar(value=str(Path.home() / "Documents"))
        ttk.Entry(linha, textvariable=self.pasta_saida).pack(side="left", fill="x",
                                                             expand=True, padx=4)
        ttk.Button(linha, text="...", width=3, command=self.escolher_pasta_saida).pack(side="left")
        self.nao_salvar = tk.BooleanVar(value=False)
        ttk.Checkbutton(opc, text="Só converter (não salvar arquivo, apenas pré-visualizar)",
                        variable=self.nao_salvar).pack(anchor="w", pady=(4, 0))

        pdf = ttk.LabelFrame(esq, text="PDF, imagens e IA", padding=8)
        pdf.pack(fill="x", pady=(8, 0))
        self.pdf_avancado = tk.BooleanVar(value=True)
        ttk.Checkbutton(pdf, text="Leitor avançado (colunas na ordem, títulos e tabelas)",
                        variable=self.pdf_avancado).pack(anchor="w")
        self.limpar_pdf = tk.BooleanVar(value=True)
        ttk.Checkbutton(pdf, text="Limpar texto (rodapés, cabeçalhos, frases quebradas)",
                        variable=self.limpar_pdf).pack(anchor="w")
        self.usar_ocr = tk.BooleanVar(value=True)
        ttk.Checkbutton(pdf, text="OCR: ler escaneados, fotos e imagens (português)",
                        variable=self.usar_ocr).pack(anchor="w")
        self.cabecalho = tk.BooleanVar(value=True)
        ttk.Checkbutton(pdf, text="Cabeçalho com dados do arquivo (para IA)",
                        variable=self.cabecalho).pack(anchor="w")

        acao = ttk.Frame(esq)
        acao.pack(fill="x", pady=(8, 0))
        self.btn_converter = ttk.Button(acao, text="Converter", style="Acao.TButton",
                                        command=self.converter_todos)
        self.btn_converter.pack(side="left")
        self.progresso = ttk.Progressbar(acao, mode="determinate")
        self.progresso.pack(side="left", fill="x", expand=True, padx=8)

        # --- direita: prévia ---
        dir_ = ttk.Frame(painel)
        painel.add(dir_, weight=3)
        cab = ttk.Frame(dir_)
        cab.pack(fill="x", pady=(0, 6))
        ttk.Label(cab, text="Pré-visualização (Markdown)").pack(side="left")
        ttk.Button(cab, text="Salvar como...", command=self.salvar_como).pack(side="right")
        ttk.Button(cab, text="Copiar", command=self.copiar).pack(side="right", padx=4)
        ttk.Button(cab, text="Abrir pasta", command=self.abrir_pasta).pack(side="right")

        txt_fr = ttk.Frame(dir_)
        txt_fr.pack(fill="both", expand=True)
        self.previa = tk.Text(txt_fr, wrap="word", font=("Consolas", 10), undo=False,
                              relief="solid", borderwidth=1, padx=8, pady=6)
        sb2 = ttk.Scrollbar(txt_fr, orient="vertical", command=self.previa.yview)
        self.previa.configure(yscrollcommand=sb2.set)
        self.previa.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

        self.status = tk.StringVar(value="Pronto.")
        ttk.Label(self.root, textvariable=self.status, relief="sunken",
                  anchor="w", padding=(8, 2)).pack(fill="x", side="bottom")

    # ---------- lista ----------
    def adicionar(self, caminhos):
        existentes = {str(v["path"]).lower() for v in self.itens.values()}
        novos = 0
        ignorados = 0
        for c in caminhos:
            p = Path(c)
            arquivos = []
            if p.is_dir():
                arquivos = [f for f in sorted(p.rglob("*"))
                            if f.is_file() and f.suffix.lower() in EXTENSOES]
            elif p.is_file():
                arquivos = [p]
            for f in arquivos:
                if str(f).lower() in existentes:
                    continue
                if f.suffix.lower() not in EXTENSOES:
                    ignorados += 1
                    continue
                iid = self.lista.insert("", "end", values=(f.name, "Na fila"))
                self.itens[iid] = {"path": f, "md": None, "saida": None, "erro": None}
                existentes.add(str(f).lower())
                novos += 1
        msg = f"{novos} arquivo(s) adicionado(s)."
        if ignorados:
            msg += f" {ignorados} ignorado(s) (formato não suportado)."
        self.status.set(msg)

    def _on_drop(self, event):
        self.adicionar(self.root.tk.splitlist(event.data))

    def add_arquivos(self):
        tipos = [("Arquivos suportados", " ".join(f"*{e}" for e in sorted(EXTENSOES))),
                 ("Todos os arquivos", "*.*")]
        sel = filedialog.askopenfilenames(title="Escolha os arquivos", filetypes=tipos)
        if sel:
            self.adicionar(sel)

    def add_pasta(self):
        pasta = filedialog.askdirectory(title="Escolha uma pasta")
        if pasta:
            self.adicionar([pasta])

    def remover(self):
        if self.rodando:
            return
        for iid in self.lista.selection():
            self.lista.delete(iid)
            self.itens.pop(iid, None)
        self.previa.delete("1.0", "end")

    def limpar(self):
        if self.rodando:
            return
        self.lista.delete(*self.lista.get_children())
        self.itens.clear()
        self.previa.delete("1.0", "end")
        self.progresso["value"] = 0
        self.status.set("Lista limpa.")

    def escolher_pasta_saida(self):
        pasta = filedialog.askdirectory(title="Pasta de saída")
        if pasta:
            self.pasta_saida.set(pasta)
            self.modo_saida.set("pasta")

    # ---------- conversão ----------
    def converter_todos(self):
        if self.rodando:
            return
        pendentes = [iid for iid in self.lista.get_children()]
        if not pendentes:
            messagebox.showinfo(APP_NAME, "Adicione pelo menos um arquivo.")
            return
        destino = None
        if not self.nao_salvar.get() and self.modo_saida.get() == "pasta":
            destino = Path(self.pasta_saida.get())
            try:
                destino.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Pasta de saída inválida:\n{exc}")
                return
        self.rodando = True
        self.btn_converter.state(["disabled"])
        self._feitos = 0
        self.progresso.configure(maximum=len(pendentes), value=0)
        trabalho = [(iid, self.itens[iid]["path"]) for iid in pendentes]
        for iid in pendentes:
            self.lista.set(iid, "status", "Na fila")
            self.lista.item(iid, tags=())
        opcoes = {"pdf_avancado": self.pdf_avancado.get(), "limpar": self.limpar_pdf.get(),
                  "usar_ocr": self.usar_ocr.get(), "cabecalho": self.cabecalho.get()}
        threading.Thread(target=self._worker,
                         args=(trabalho, destino, self.nao_salvar.get(), opcoes),
                         daemon=True).start()

    def _worker(self, trabalho, destino, nao_salvar, opcoes):
        for iid, path in trabalho:
            self.fila.put(("inicio", iid, None))
            try:
                md, info = converter_detalhado(path, **opcoes)
                saida = None
                if not nao_salvar:
                    pasta = destino or path.parent
                    saida = pasta / (path.stem + ".md")
                    if saida.resolve() == path.resolve():
                        saida = pasta / (path.stem + ".convertido.md")
                    saida.write_text(md, encoding="utf-8")
                self.fila.put(("ok", iid, (md, saida, info)))
            except Exception as exc:
                self.fila.put(("erro", iid, f"{type(exc).__name__}: {exc}"))
        self.fila.put(("fim", None, None))

    def _processar_fila(self):
        try:
            while True:
                tipo, iid, dado = self.fila.get_nowait()
                if tipo == "inicio" and iid in self.itens:
                    self.lista.set(iid, "status", "Convertendo...")
                    self.status.set(f"Convertendo {self.itens[iid]['path'].name}...")
                elif tipo == "ok" and iid in self.itens:
                    md, saida, info = dado
                    self.itens[iid].update(md=md, saida=saida, erro=None)
                    rotulo = "Concluído"
                    if info.get("ocr", "não") != "não":
                        rotulo += " · OCR"
                    if any("nenhum texto" in a or "sem texto" in a or "falhou" in a
                           for a in info.get("avisos", [])):
                        rotulo = "Atenção"
                    self.lista.set(iid, "status", rotulo)
                    self.lista.item(iid, tags=("ok",))
                    self._feitos += 1
                    self.progresso.configure(value=self._feitos)
                    if not self.lista.selection():
                        self.lista.selection_set(iid)
                    elif iid in self.lista.selection():
                        self.mostrar_previa()
                elif tipo == "erro" and iid in self.itens:
                    self.itens[iid].update(md=None, saida=None, erro=dado)
                    self.lista.set(iid, "status", "Erro")
                    self.lista.item(iid, tags=("erro",))
                    self._feitos += 1
                    self.progresso.configure(value=self._feitos)
                elif tipo == "fim":
                    self.rodando = False
                    self.btn_converter.state(["!disabled"])
                    ok = sum(1 for v in self.itens.values() if v["md"] is not None)
                    erros = sum(1 for v in self.itens.values() if v["erro"])
                    self.status.set(f"Terminado: {ok} convertido(s), {erros} com erro.")
        except queue.Empty:
            pass
        except Exception as exc:  # nunca deixar o laço da tela morrer
            self.status.set(f"Erro interno: {exc}")
        finally:
            self.root.after(100, self._processar_fila)

    # ---------- prévia / ações ----------
    def _selecionado(self):
        sel = self.lista.selection()
        return self.itens.get(sel[0]) if sel else None

    def mostrar_previa(self):
        item = self._selecionado()
        self.previa.delete("1.0", "end")
        if not item:
            return
        if item["erro"]:
            self.previa.insert("1.0", f"Não foi possível converter este arquivo.\n\n{item['erro']}")
        elif item["md"] is not None:
            self.previa.insert("1.0", item["md"] or "(o arquivo não tem texto extraível)")
            if item["saida"]:
                self.status.set(f"Salvo em: {item['saida']}")
        else:
            self.previa.insert("1.0", "Ainda não convertido. Clique em Converter.")

    def copiar(self):
        texto = self.previa.get("1.0", "end-1c")
        if texto:
            self.root.clipboard_clear()
            self.root.clipboard_append(texto)
            self.status.set("Markdown copiado para a área de transferência.")

    def salvar_como(self):
        item = self._selecionado()
        texto = self.previa.get("1.0", "end-1c")
        if not texto or not item or item["md"] is None:
            messagebox.showinfo(APP_NAME, "Selecione um arquivo já convertido.")
            return
        destino = filedialog.asksaveasfilename(
            title="Salvar Markdown", defaultextension=".md",
            initialfile=item["path"].stem + ".md",
            filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")])
        if destino:
            Path(destino).write_text(texto, encoding="utf-8")
            self.status.set(f"Salvo em: {destino}")

    def abrir_md(self):
        item = self._selecionado()
        if item and item["saida"]:
            abrir_no_sistema(item["saida"])

    def abrir_pasta(self):
        item = self._selecionado()
        if item and item["saida"]:
            alvo = item["saida"].parent
        elif self.modo_saida.get() == "pasta":
            alvo = Path(self.pasta_saida.get())
        elif item:
            alvo = item["path"].parent
        else:
            return
        abrir_no_sistema(alvo)


def autoteste(saida: str, arquivos: list[str]) -> int:
    """Uso interno (CI): MarcosDown.exe --autoteste resultado.txt a.pdf b.docx"""
    linhas, erros = [], 0
    for a in arquivos:
        try:
            md = converter(Path(a))
            if Path(a).name == "manual.pdf" and "## Configurações de papel" not in md:
                raise RuntimeError("leitor de PDF avançado não funcionou no executável")
            if Path(a).stem.startswith("scan") and "PROCURA" not in md:
                raise RuntimeError("OCR não funcionou no executável")
            linhas.append(f"### {a}\n{md}")
        except Exception as exc:
            erros += 1
            linhas.append(f"### {a}\nERRO {type(exc).__name__}: {exc}")
    Path(saida).write_text("\n".join(linhas), encoding="utf-8")
    return 1 if erros else 0


def main():
    import multiprocessing

    multiprocessing.freeze_support()  # OCR em paralelo no .exe
    if len(sys.argv) > 2 and sys.argv[1] == "--autoteste":
        sys.exit(autoteste(sys.argv[2], sys.argv[3:]))
    root =TkinterDnD.Tk() if DND_OK else tk.Tk()
    app = App(root)
    if len(sys.argv) > 1:  # "Abrir com" / "Enviar para"
        app.adicionar(sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()
