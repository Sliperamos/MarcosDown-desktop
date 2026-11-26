# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller marcosdown.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("assets/icon.png", "assets")]
binaries = []
hiddenimports = []

# Pacotes que carregam arquivos de dados/modelos ou importam módulos dinamicamente
for pkg in ("markitdown", "magika", "tkinterdnd2", "pdfminer", "mammoth",
            "pptx", "openpyxl", "xlrd", "olefile", "charset_normalizer",
            "markdownify", "bs4", "defusedxml"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules(
    "onnxruntime", filter=lambda n: ".quantization" not in n and ".tools" not in n
    and ".transformers" not in n and ".backend" not in n)

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "IPython", "jupyter", "notebook", "pytest",
              "torch", "tensorflow", "scipy", "pandas.tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarcosDown",
    console=False,
    icon="assets/icon.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MarcosDown")
