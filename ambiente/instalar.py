# -*- coding: utf-8 -*-
"""Instala (ou confere) o ambiente do Tandera: .venv (principal) e .venv-ocr (PaddleOCR 3.7, separado como no servidor: as bibliotecas
da NVIDIA do paddle são de outra versão que as do torch). Log em ambiente\\instalar.log.
  .venv\\Scripts\\python.exe ambiente\\instalar.py [--ocr]"""
import os, subprocess, sys

T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(T, ".venv", "Scripts", "python.exe")
LOG = open(os.path.join(T, "ambiente", "instalar.log"), "a", encoding="utf-8")


def rodar(cmd):
    LOG.write("\n$ " + " ".join(cmd) + "\n"); LOG.flush()
    r = subprocess.run(cmd, stdout=LOG, stderr=subprocess.STDOUT, cwd=T)
    LOG.write(f"-> código {r.returncode}\n"); LOG.flush()
    return r.returncode


if "--ocr" not in sys.argv:
    rodar([PY, "-m", "uv", "pip", "install", "--python", PY, "-r", os.path.join(T, "ambiente", "requisitos.txt"),
           "--override", os.path.join(T, "ambiente", "travar.txt"), "--extra-index-url", "https://download.pytorch.org/whl/cu128",
           "--index-strategy", "unsafe-best-match"])
    # o faster-whisper puxa o «onnxruntime» só de processador, que sobrescreve o da placa: tira e põe o da placa por cima (igual ao servidor)
    rodar([PY, "-m", "uv", "pip", "uninstall", "--python", PY, "onnxruntime"])
    rodar([PY, "-m", "uv", "pip", "install", "--python", PY, "--reinstall", "--no-deps", "onnxruntime-gpu==1.23.2"])
else:
    PYO = os.path.join(T, ".venv-ocr", "Scripts", "python.exe")
    if not os.path.exists(PYO):
        rodar([PY, "-m", "uv", "venv", "--python", "3.12", os.path.join(T, ".venv-ocr")])
    c = rodar([PY, "-m", "uv", "pip", "install", "--python", PYO, "paddlepaddle-gpu==3.3.*", "--extra-index-url",
               "https://www.paddlepaddle.org.cn/packages/stable/cu129/", "--index-strategy", "unsafe-best-match"])
    if c:
        rodar([PY, "-m", "uv", "pip", "install", "--python", PYO, "paddlepaddle-gpu", "--extra-index-url",
               "https://www.paddlepaddle.org.cn/packages/stable/cu129/", "--index-strategy", "unsafe-best-match"])
    rodar([PY, "-m", "uv", "pip", "install", "--python", PYO, "paddleocr==3.7.*"])
LOG.write("FIM\n")
