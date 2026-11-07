# -*- coding: utf-8 -*-
"""As VERSÕES EXATAS dos ambientes do PC, pro servidor instalar igual (01/11, panelas de som). Lê cada ambiente do PC (uv pip freeze) e
grava servidor\\requisitos\\<ambiente>.txt — o preparar_tandera.sh instala ESTA lista (não «a mais nova»). Rode de novo quando um
ambiente do PC mudar:  apps\\TANDERA\\.venv\\Scripts\\python.exe servidor\\travas_do_pc.py
  tandera = apps\\TANDERA\\.venv           (o principal: torch 2.11.0+cu128, faster-whisper, beat-this, transnetv2, CED, Ovis…)
  sep     = apps\\REGUA\\.venv-sep          (BS-Roformer: audio-separator)
  cine    = apps\\separador-cinema\\venv   (BandIt Plus: msst; Python 3.13 no PC)
  ocr     = apps\\TANDERA\\.venv-ocr        (PaddleOCR 3.7 + paddlepaddle-gpu: as bibliotecas da NVIDIA dele brigam com as do torch)"""
import os, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__)); T = os.path.dirname(AQUI)
AMBIENTES = {
    "tandera": os.path.join(T, ".venv"),
    "sep": os.environ.get("TANDERA_VENV_SEP") or os.path.join(T, ".venv-sep"),      # pacote da Fly: no PC do Luan, as pastas dele
    "cine": os.environ.get("TANDERA_VENV_CINE") or os.path.join(T, ".venv-cine"),
    "ocr": os.path.join(T, ".venv-ocr"),
}
# só existem/servem no Windows, ou não são do ambiente (o próprio instalador) — fora da lista do Linux
SO_WINDOWS = {"pyreadline3", "pywin32", "pywin32-ctypes", "colorama", "pip", "uv", "setuptools", "truststore"}
# 01/11: não são usados pelas peças do servidor e puxam bibliotecas de tela/som do sistema (fica igual ao PC no resto)
FORA_DO_SERVIDOR = {"tandera": {"sounddevice"}}   # 06/11: o mediapipe VOLTOU (a peça corpo/pisada roda no servidor; libgl1 já vem no preparar)
# o «paddlepaddle-gpu» vem do índice da Paddle (cu129), à parte (o preparar instala antes, do storage)
A_PARTE = {"ocr": {"paddlepaddle-gpu"}}

os.makedirs(os.path.join(AQUI, "requisitos"), exist_ok=True)
uv = [os.path.join(T, ".venv", "Scripts", "python.exe"), "-m", "uv"]
for nome, amb in AMBIENTES.items():
    py = os.path.join(amb, "Scripts", "python.exe")
    ver = subprocess.run([py, "--version"], capture_output=True, text=True).stdout.split()[-1]
    linhas = subprocess.run(uv + ["pip", "freeze", "--python", py], capture_output=True, text=True, check=True).stdout.splitlines()
    fora = SO_WINDOWS | FORA_DO_SERVIDOR.get(nome, set()) | A_PARTE.get(nome, set())
    ok = [l for l in linhas if "==" in l and l.split("==")[0].lower() not in fora]
    with open(os.path.join(AQUI, "requisitos", nome + ".txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# python {ver} · tirado do PC ({amb}) por travas_do_pc.py\n" + "\n".join(ok) + "\n")
    print(f"{nome}: python {ver}, {len(ok)} pacotes (fora: {sorted(fora & {l.split('==')[0].lower() for l in linhas})})")

# 06/11: o OpenFace 3.0 da boca mora no WSL do PC (/opt/regua/.venv): a lista sai de lá (o servidor monta /root/venv_regua igual)
r = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "-u", "root", "--", "bash", "-c",
                    "/opt/regua/.venv/bin/python --version; /opt/regua/.venv/bin/python -m pip freeze"], capture_output=True, text=True)
if r.returncode == 0:
    ls = r.stdout.splitlines(); ver = ls[0].split()[-1]
    ok = [l for l in ls[1:] if "==" in l and not l.startswith("-e")]
    with open(os.path.join(AQUI, "requisitos", "regua.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# python {ver} · tirado do WSL do PC (/opt/regua/.venv) por travas_do_pc.py\n" + "\n".join(ok) + "\n")
    print(f"regua (WSL): python {ver}, {len(ok)} pacotes")
else:
    print("AVISO: não li o /opt/regua/.venv do WSL:", r.stderr[-300:])
