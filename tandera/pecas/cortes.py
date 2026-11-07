# -*- coding: utf-8 -*-
"""CORTES no quadro exato: AutoShot (1ª opinião, ~97% no quadro exato no EP01) UNIDO com a TransNetV2 (2ª opinião, ±1 quadro), como
a /sonoplastia decidiu em 01/11 (F2: o AutoShot sozinho perdeu 3 cortes macios do V009); a diferença de pixel marca POSSÍVEL jump cut
(não vira corte sozinha: conferir no olho). O corte é o 1º quadro do plano novo. Na placa quando dá (onnx CUDA / torch)."""
import os, subprocess

import numpy as np

from .. import base

LIMIAR_AUTOSHOT = 0.296
LIMIAR_TRANSNET = 0.5


def _quadros_pequenos(video, W=48, H=27, fmt="rgb24", c=3):
    def ler(hw):
        return subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *hw, "-i", video, "-map", "0:v:0", "-an", "-vf",
                               f"scale={W}:{H}:flags=bilinear", "-fps_mode", "passthrough", "-pix_fmt", fmt, "-f", "rawvideo", "-"],
                              capture_output=True, creationflags=base.SEM_JANELA)
    # 07/11: no servidor o 4K abre pelo chip de vídeo da placa (NVDEC); o processador só reduz. Se o chip recusar, o jeito de sempre
    r = ler(["-hwaccel", "cuda"]) if os.name != "nt" else None
    if r is None or r.returncode != 0 or not r.stdout: r = ler([])
    t = W * H * c
    q = np.frombuffer(r.stdout[: len(r.stdout) // t * t], np.uint8)
    return q.reshape(-1, H, W, c) if c > 1 else q.reshape(-1, H, W)


def prob_para_cortes(prob, limiar):
    """o corte é o quadro DEPOIS do pico de cada trecho acima do limiar"""
    out, i, n = [], 0, len(prob)
    while i < n:
        if prob[i] > limiar:
            p = i
            while i < n and prob[i] > limiar:
                if prob[i] > prob[p]: p = i
                i += 1
            if p < n - 1: out.append(p + 1)
        else:
            i += 1
    return out


def _autoshot_sessao(placa):
    return base.segurado(("autoshot", placa), lambda: base.ort_sessao(base.AUTOSHOT, placa))


def _transnet_modelo(dev):
    from transnetv2_pytorch import TransNetV2
    return base.segurado(("transnet", dev), lambda: TransNetV2(device=dev).eval())


def aquecer(ctx):
    """o lote: carrega o AutoShot e a TransNetV2 uma vez pro bloco inteiro"""
    _autoshot_sessao(ctx.placa); _transnet_modelo("cuda" if ctx.placa else "cpu")


def autoshot(q, placa=True):
    s = _autoshot_sessao(placa)
    n = len(q); resto = (50 - n % 50) if n % 50 else 0
    fila = np.concatenate([np.repeat(q[:1], 25, 0), q, np.repeat(q[-1:], 25 + resto, 0)]); prob = np.zeros(n, np.float32)
    for i in range(0, len(fila) - 99, 50):
        lg = s.run(None, {"frames": fila[i:i + 100].astype(np.float32)[None]})[0].reshape(-1)
        for k in range(25, 75):
            if i + k - 25 < n: prob[i + k - 25] = 1 / (1 + np.exp(-lg[k]))
    return prob_para_cortes(prob, LIMIAR_AUTOSHOT), s.get_providers()[0]


def transnet(q, placa=True):
    import torch
    dev = "cuda" if placa else "cpu"
    m = _transnet_modelo(dev)
    with torch.no_grad():
        sp, _ = m.predict_frames(torch.from_numpy(np.ascontiguousarray(q)).to(dev), quiet=True)
    out = prob_para_cortes(sp.cpu().numpy().reshape(-1), LIMIAR_TRANSNET)
    del m; base.liberar_torch()
    return out


def pixel(video, ja, cinza=None, tol=1):
    """3ª opinião, barata: salto de diferença de pixel (cinza 96×54) bem acima dos vizinhos (jump cut: mesmo ângulo, outro take)"""
    g = (cinza if cinza is not None else _quadros_pequenos(video, 96, 54, "gray", 1)).astype(np.int16)
    dif = np.zeros(len(g)); dif[1:] = np.abs(g[1:] - g[:-1]).mean(axis=(1, 2))
    out = []
    for f in range(1, len(dif)):
        viz = np.concatenate([dif[max(1, f - 12):max(1, f - 1)], dif[f + 2:f + 13]])
        if len(viz) and dif[f] > max(6.0, 3 * float(np.median(viz))) and dif[f] >= dif[max(0, f - 1):f + 2].max() and not any(abs(f - c) <= tol for c in ja):
            out.append({"q": int(f), "dif": round(float(dif[f]), 1), "vizinhos": round(float(np.median(viz)), 1)})
    return out


def rodar(A, ctx):
    pr = A["preparo"]
    if not pr["tem_imagem"]:
        return {"quadros": 0, "fps": 0, "cortes": [], "cortes_s": [], "planos": [], "sem_imagem": True}
    fps = pr["fps"]
    from concurrent.futures import ThreadPoolExecutor
    from . import preparo
    # SERVIDOR (lote RunPod 01/11): os quadros pequenos vêm da MESMA leitura do preparo (NVDEC) — não abre o vídeo de novo. No PC o
    # preparo não tira esses quadros (sairiam do 720 reduzido, não do original: o AutoShot veria outros pixels e a versão dos cortes teria
    # que subir) → preparo.raw() = None e a peça lê o vídeo como sempre
    q0, c0 = preparo.raw(A, "c48", 48, 27, 3), preparo.raw(A, "c96", 96, 54)
    with ThreadPoolExecutor(1) as pool:                  # o processador decodifica o cinza da 3ª opinião enquanto a placa roda as duas
        cinza = pool.submit(lambda: c0 if c0 is not None else _quadros_pequenos(A.video, 96, 54, "gray", 1))
        q = q0 if q0 is not None else _quadros_pequenos(A.video)
        ca, prov = autoshot(q, ctx.placa)
        ct = transnet(q, ctx.placa)
        so_a = [c for c in ca if not any(abs(c - x) <= 1 for x in ct)]
        so_t = [c for c in ct if not any(abs(c - x) <= 1 for x in ca)]
        cortes = sorted(ca + so_t)
        px = pixel(A.video, cortes, cinza.result())
    n = int(len(q)); bordas = [0] + cortes + [n]
    return {"quadros": n, "fps": fps, "cortes": cortes, "cortes_s": [round(c / fps, 3) for c in cortes],
            "planos": [[bordas[i], bordas[i + 1]] for i in range(len(bordas) - 1) if bordas[i + 1] > bordas[i]],
            "autoshot": ca, "transnet": ct, "so_autoshot": so_a, "so_transnet": so_t, "possiveis_pixel": px,
            "detector": "AutoShot ∪ TransNetV2 (±1 quadro)", "autoshot_em": prov,
            "quadros_de": "preparo (mesma leitura, reduzidos do 720)" if q0 is not None else "vídeo (leitura própria)"}
