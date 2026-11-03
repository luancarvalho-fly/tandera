# -*- coding: utf-8 -*-
"""QUAL EFEITO: encaixe na onda (8 kHz, na placa) do stem de efeitos contra a biblioteca inteira, com coerência no tempo — diz o ARQUIVO
exato e onde ele começa no vídeo (≈9/10 certo, acha ~30%). Só os «confiáveis» (repetem ≥ 1 s) valem como fato. Biblioteca indexada da
régua (REGUA\\testes\\biblioteca: lista.txt + bib8k.npy); REGUA_BIB troca."""
import json, os, subprocess

import numpy as np

from .. import base


def rodar(A, ctx):
    from . import separacao
    ef = separacao.stem(A, "efeitos")
    if not ef: return {"achados": [], "sem_som": True}
    sai = os.path.join(A.dir("efeitos"), "sfx_video.json")
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("REGUA_BIB", os.path.join(base.REGUA, "testes", "biblioteca"))
    if not ctx.placa: env["REGUA_DISP"] = "cpu"
    subprocess.run([base.PY, os.path.join(os.path.dirname(__file__), "_sfx_video.py"), ef, sai, str(A["preparo"].get("folga_aac_s", 0.0))],
                   check=True, env=env, capture_output=True, creationflags=base.SEM_JANELA)
    ach = json.load(open(sai, encoding="utf-8"))["achados"]
    for a in ach:
        try:
            y = base.ler_audio(a["arquivo"], 8000); e = np.convolve(np.abs(y), np.ones(80) / 80, "same")
            a["ate_o_pico_ms"] = round(float(np.argmax(e)) / 8.0, 1); a["pico_no_video_s"] = round(a["inicio_do_arquivo_s"] + a["ate_o_pico_ms"] / 1000, 4)
        except Exception as x:
            a["ate_o_pico_ms"] = None; a["erro_pico"] = str(x)[:200]
    return {"achados": ach, "confiaveis": sum(1 for a in ach if a.get("confiavel"))}
